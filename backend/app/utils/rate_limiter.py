"""Sliding-window in-memory rate limiting utility for FastAPI endpoints."""

import time
from typing import Dict, List, Optional
from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """Sliding-window in-memory rate limiter per client IP or key."""

    def __init__(self, max_requests: int, window_seconds: int = 60, name: str = "request"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._buckets: Dict[str, List[float]] = {}

    def check(self, key: str) -> None:
        """Record an attempt for key and raise HTTP 429 if limit exceeded."""
        now = time.time()
        cutoff = now - self.window_seconds
        history = self._buckets.setdefault(key, [])

        # Prune timestamps older than window
        while history and history[0] <= cutoff:
            history.pop(0)

        if len(history) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests for {self.name}. Please try again later.",
            )

        history.append(now)

    def reset(self) -> None:
        """Clear recorded attempts (useful for testing)."""
        self._buckets.clear()


def get_client_ip(request: Request) -> str:
    """Safely extract client IP from request headers or direct client connection."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


# Pre-configured rate limiters for sensitive endpoints
auth_login_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=60, name="login")
auth_register_limiter = SlidingWindowRateLimiter(max_requests=15, window_seconds=60, name="registration")
auth_otp_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60, name="verification OTP")
auth_password_reset_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60, name="password reset")
payment_intent_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60, name="payment intent creation")
