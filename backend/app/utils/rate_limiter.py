"""Rate limiting shared by every backend process (Phase 05, historical BUG-038).

Before Phase 05 each limiter kept its counters in a Python dict, so running N worker processes multiplied every limit
by N and a restart reset them. Counters now live in MongoDB:

* one document per (limiter, key, fixed window) with an atomic ``$inc`` upsert, so concurrent processes share counts;
* the decision uses a sliding-window estimate: ``previous_window * (1 - elapsed_fraction) + current_window``, which
  avoids the double burst a plain fixed window allows at a window boundary;
* every counter carries ``expiresAt`` and a TTL index removes it after two windows, so storage stays bounded;
* keys (IP addresses, user ids) are stored only as truncated SHA-256 digests.

If MongoDB is unreachable the limiter falls back to the previous in-process sliding window for that process, so the
API keeps a limit and never fails because the counter store is down.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

COLLECTION = "rate_limit_counters"
_index_ready = False
_index_lock = threading.Lock()


def _collection():
    global _index_ready
    from app.config.database import DatabaseManager
    coll = DatabaseManager.get_database()[COLLECTION]
    if not _index_ready:
        with _index_lock:
            if not _index_ready:
                coll.create_index("expiresAt", expireAfterSeconds=0, name="idx_rate_limit_ttl")
                _index_ready = True
    return coll


class SlidingWindowRateLimiter:
    """Shared (MongoDB) sliding-window limiter with an in-process fallback."""

    def __init__(self, max_requests: int, window_seconds: int = 60, name: str = "request",
                 detail: Optional[str] = None, shared: bool = True):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self.detail = detail or f"Too many requests for {name}. Please try again later."
        self.shared = shared
        self._buckets: Dict[str, List[float]] = {}

    def _digest(self, key: str) -> str:
        return hashlib.sha256(f"{self.name}|{key}".encode("utf-8")).hexdigest()[:24]

    def _reject(self) -> None:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=self.detail,
                            headers={"Retry-After": str(self.window_seconds)})

    def _check_local(self, key: str) -> None:
        now = time.time()
        history = self._buckets.setdefault(key, [])
        while history and history[0] <= now - self.window_seconds:
            history.pop(0)
        if len(history) >= self.max_requests:
            self._reject()
        history.append(now)

    def _check_shared(self, key: str) -> bool:
        """Count this attempt in MongoDB; return True when it must be rejected."""
        from pymongo import ReturnDocument
        coll = _collection()
        now = time.time()
        window = int(now // self.window_seconds)
        elapsed = (now % self.window_seconds) / self.window_seconds
        digest = self._digest(key)
        expires = datetime.fromtimestamp((window + 2) * self.window_seconds, tz=timezone.utc)
        current = coll.find_one_and_update(
            {"_id": f"{digest}:{window}"},
            {"$inc": {"count": 1}, "$setOnInsert": {"limiter": self.name, "expiresAt": expires}},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
        previous = coll.find_one({"_id": f"{digest}:{window - 1}"}, {"count": 1}) or {}
        estimate = (previous.get("count", 0) * (1 - elapsed)) + current["count"]
        return estimate > self.max_requests

    def check(self, key: str) -> None:
        """Record an attempt for key and raise HTTP 429 when the limit is exceeded."""
        if self.shared:
            try:
                rejected = self._check_shared(key)
            except HTTPException:
                raise
            except Exception as exc:  # counter store unavailable: keep a per-process limit
                logger.warning("Shared rate limiter unavailable (%s); using the in-process limit.",
                               type(exc).__name__)
            else:
                if rejected:
                    self._reject()
                return
        self._check_local(key)

    def reset(self) -> None:
        """Clear recorded attempts for this limiter (tests and administration)."""
        self._buckets.clear()
        if self.shared:
            try:
                _collection().delete_many({"limiter": self.name})
            except Exception:
                pass


class LimiterResetHandle(dict):
    """Kept for code that cleared the old module-level bucket dict: ``clear()`` now resets the shared limiter."""

    def __init__(self, limiter: SlidingWindowRateLimiter):
        super().__init__()
        self._limiter = limiter

    def clear(self) -> None:  # noqa: D401
        super().clear()
        self._limiter.reset()


def get_client_ip(request: Request) -> str:
    """Client IP. X-Forwarded-For / X-Real-IP are honoured because the API is deployed behind a proxy; a direct
    deployment must strip these headers at the edge (documented in the Phase 05 security report)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


# Pre-configured limiters (limits unchanged from the per-process versions unless noted).
auth_login_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=60, name="login")
auth_register_limiter = SlidingWindowRateLimiter(max_requests=15, window_seconds=60, name="registration")
auth_otp_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60, name="verification OTP")
auth_password_reset_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60, name="password reset")
auth_refresh_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60, name="token refresh")  # new
payment_intent_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60, name="payment intent creation")
upload_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=60, name="file upload")  # new
booking_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=60, name="booking")  # new
admin_action_limiter = SlidingWindowRateLimiter(max_requests=120, window_seconds=60, name="admin action")  # new
EMERGENCY_HINT = ("If this is a medical emergency, call 1990 (Suwa Seriya ambulance) or go to the nearest "
                  "Emergency Treatment Unit now.")
ai_booking_limiter = SlidingWindowRateLimiter(
    max_requests=30, window_seconds=60, name="ai booking",
    detail="Too many requests to the AI Booking Assistant. Please wait a moment before sending another message. "
           + EMERGENCY_HINT)
ai_health_chat_limiter = SlidingWindowRateLimiter(
    max_requests=30, window_seconds=60, name="ai health chat",
    detail="Too many requests to the AI Health Assistant. Please wait a moment before sending another message. "
           + EMERGENCY_HINT)
ai_recommendation_limiter = SlidingWindowRateLimiter(
    max_requests=20, window_seconds=60, name="ai recommendation",
    detail="Too many AI recommendation requests. Please wait a moment before trying again.")
ai_assistant_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60, name="ai assistant",
                                                detail="Too many assistant requests. Please wait a moment.")  # new


def limit_by_user(limiter: SlidingWindowRateLimiter):
    """FastAPI dependency factory: count requests per authenticated user."""
    from fastapi import Depends
    from app.middleware.auth import get_current_user

    def dependency(current_user=Depends(get_current_user)):
        limiter.check(str(current_user.id))
        return current_user
    return dependency


def limit_by_ip(limiter: SlidingWindowRateLimiter):
    def dependency(request: Request):
        limiter.check(get_client_ip(request))
    return dependency
