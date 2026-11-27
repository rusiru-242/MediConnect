"""Single choke point for every external LLM call (Phase 05, component 32).

Before Phase 05 the Gemini and OpenAI adapters each called ``requests.post`` directly: the Gemini parser put the API
key in the URL query string, nothing enforced a usage limit, and the provider-monitoring counters and circuit
breaker were never updated by a real call (they always showed their start-up values).

Every call now goes through :func:`send`, which

* refuses to call when the daily request limit (``AI_DAILY_REQUEST_LIMIT``, counted atomically in MongoDB across
  processes) is reached, or when the circuit breaker for that provider is open;
* sends credentials only in headers;
* classifies failures (auth_failed, quota_exhausted, rate_limited, timeout, invalid_model, server_error, network,
  invalid_output);
* retries once, only for transient rate limits, 5xx and connection errors (never for other 4xx, and never for an
  exhausted account quota), after a short bounded back-off (``Retry-After`` honoured up to 2 s);
* records privacy-preserving metrics per provider and Asia/Colombo day: request, success, failure-by-category and
  fallback counts, total latency, token usage when the provider reports it, and the model id. No prompt, reply,
  patient identifier or key is stored.

:func:`provider_status` derives a truthful state from configuration plus observed calls: ``not_configured``,
``disabled``, ``configured_not_verified``, ``available``, ``rate_limited``, ``degraded`` or ``unavailable``.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)
COLOMBO = ZoneInfo("Asia/Colombo")
COLLECTION = "ai_provider_usage"
PROVIDERS = ("gemini", "openai")

# Model lifecycle (A01, checked 2026-11-26 against the official Gemini models/deprecations pages and the OpenAI
# deprecations page, and confirmed with zero-token model lookups: gemini-1.5-flash returns 404, gemini-3.8-flash and
# gpt-6-luna exist, gpt-4o-mini reports shutdown_date 2027-01-14).
# Retired or deprecated Gemini ids are mapped to the current stable model so an old .env keeps working; the mapping is
# reported in provider status ("modelRemapped") instead of happening silently. Phase 05 mapped them to the alias
# gemini-flash-latest, whose target the documentation no longer states, so a pinned stable id is used instead.
GEMINI_STABLE_MODEL = "gemini-3.8-flash"
OPENAI_STABLE_MODEL = "gpt-6-luna"
RETIRED_GEMINI_MODELS = {
    "gemini-1.5-flash": GEMINI_STABLE_MODEL, "gemini-1.5-pro": GEMINI_STABLE_MODEL,
    "gemini-pro-vision": GEMINI_STABLE_MODEL, "gemini-pro": GEMINI_STABLE_MODEL,
    "gemini-2.0-flash": GEMINI_STABLE_MODEL, "gemini-2.0-flash-001": GEMINI_STABLE_MODEL,
    "gemini-2.5-flash": GEMINI_STABLE_MODEL, "gemini-3.5-flash": GEMINI_STABLE_MODEL,
    "gemini-3.7-flash": GEMINI_STABLE_MODEL, "gemini-3.1-flash-lite-preview": GEMINI_STABLE_MODEL,
}
# Models that still work but have an announced shutdown date (reported, not remapped).
MODEL_SHUTDOWN_DATES = {
    "gpt-4o-mini": "2027-01-14", "gpt-4o-mini-2024-07-18": "2027-01-14", "gpt-4.1-mini": "2027-01-14",
    "gpt-4.1-mini-2025-04-14": "2027-01-14", "gemini-3.1-flash-lite": "2027-05-07",
}
RETRY_BACKOFF_SECONDS = 0.5
MAX_RETRY_AFTER_SECONDS = 2.0


class ProviderCallError(Exception):
    def __init__(self, category: str, status_code: Optional[int] = None):
        super().__init__(category)
        self.category = category
        self.status_code = status_code


def resolve_gemini_model(model: str) -> str:
    name = (model or "").strip().removeprefix("models/")
    return RETIRED_GEMINI_MODELS.get(name, name or GEMINI_STABLE_MODEL)


def resolve_openai_model(model: str) -> str:
    return (model or "").strip() or OPENAI_STABLE_MODEL


def _db():
    from app.config.database import DatabaseManager
    return DatabaseManager.get_database()


def _day_key(provider: str) -> str:
    return f"{provider}:{datetime.now(COLOMBO).date().isoformat()}"


def _inc(provider: str, fields: Dict[str, float], sets: Optional[Dict[str, Any]] = None) -> Optional[dict]:
    try:
        from pymongo import ReturnDocument
        return _db()[COLLECTION].find_one_and_update(
            {"_id": _day_key(provider)},
            {"$inc": fields, "$set": {"provider": provider, "day": datetime.now(COLOMBO).date().isoformat(),
                                      "updatedAt": datetime.now(timezone.utc), **(sets or {})}},
            upsert=True, return_document=ReturnDocument.AFTER)
    except Exception as exc:  # metrics must never break a call
        logger.debug("AI usage metrics unavailable (%s)", type(exc).__name__)
        return None


def _monitor():
    from app.services.ai_provider_monitoring_service import AIProviderMonitoringService
    return AIProviderMonitoringService


def _classify(status_code: int, body: str) -> str:
    lowered = body.lower()
    if status_code in (401, 403):
        return "auth_failed"
    if status_code == 400 and ("api key not valid" in lowered or "api_key_invalid" in lowered):
        return "auth_failed"  # Gemini answers an invalid key with 400 INVALID_ARGUMENT, not 401
    if status_code == 429:
        # OpenAI answers 429 both for a transient rate limit and for an account without credits
        # ("insufficient_quota"). Retrying the latter only wastes time, and it is not a rate limit (A01-N02).
        if "insufficient_quota" in lowered or "credit_balance" in lowered:
            return "quota_exhausted"
        # Gemini free tier: "Generate content requests per day limit exceeded ... retry in 21h" is a daily quota,
        # not a per-minute rate limit; retrying it only spends another request.
        if "per day" in lowered or "perday" in lowered or "requests_per_day" in lowered:
            return "quota_exhausted"
        return "rate_limited"
    if status_code == 404 or (status_code == 400 and "model" in lowered):
        return "invalid_model"
    if status_code >= 500:
        return "server_error"
    return "bad_request"


def _tokens(provider: str, data: dict) -> Dict[str, int]:
    if provider == "gemini":
        usage = data.get("usageMetadata") or {}
        return {"promptTokens": int(usage.get("promptTokenCount") or 0),
                "completionTokens": int(usage.get("candidatesTokenCount") or 0)}
    usage = data.get("usage") or {}
    return {"promptTokens": int(usage.get("prompt_tokens") or 0),
            "completionTokens": int(usage.get("completion_tokens") or 0)}


def send(provider: str, model: str, url: str, headers: Dict[str, str], payload: dict, timeout: float) -> dict:
    """POST ``payload`` to the provider and return the decoded JSON, or raise :class:`ProviderCallError`."""
    from app.config.settings import settings
    limit = int(settings.AI_DAILY_REQUEST_LIMIT)
    if limit <= 0:
        raise ProviderCallError("disabled")
    if _monitor().is_circuit_open(provider):
        _inc(provider, {"refusedCircuitOpen": 1})
        raise ProviderCallError("circuit_open")
    counted = _inc(provider, {"requests": 1}, {"model": model})
    if counted and counted.get("requests", 0) > limit:
        _inc(provider, {"refusedUsageLimit": 1})
        raise ProviderCallError("usage_limit")

    started = time.monotonic()
    category: Optional[str] = None
    status_code: Optional[int] = None
    retry_after = 0.0
    for attempt in range(2):
        if attempt:
            # Bounded back-off before the single retry (A01-N04: the retry used to be immediate).
            time.sleep(min(retry_after or RETRY_BACKOFF_SECONDS, MAX_RETRY_AFTER_SECONDS))
        try:
            response = requests.post(url, headers={"Content-Type": "application/json", **headers}, json=payload,
                                     timeout=timeout)
        except requests.Timeout:
            category = "timeout"
            break
        except requests.ConnectionError:
            category = "network"
            if attempt == 0:
                continue
            break
        status_code = response.status_code
        if status_code == 200:
            try:
                data = response.json()
            except ValueError:
                category = "invalid_output"
                break
            latency = (time.monotonic() - started) * 1000
            _inc(provider, {"successes": 1, "latencyMsTotal": latency, **_tokens(provider, data)},
                 {"lastSuccessAt": datetime.now(timezone.utc), "lastStatus": "ok"})
            _monitor().record_success(provider, latency_ms=latency)
            return data
        category = _classify(status_code, response.text[:4000])  # the quota detail is far into the body
        try:
            retry_after = float(response.headers.get("Retry-After") or 0)
        except (TypeError, ValueError, AttributeError):
            retry_after = 0.0
        if attempt == 0 and category in {"rate_limited", "server_error"}:
            continue
        break
    latency = (time.monotonic() - started) * 1000
    _inc(provider, {"failures": 1, f"failure_{category}": 1, "latencyMsTotal": latency},
         {"lastFailureAt": datetime.now(timezone.utc), "lastStatus": category})
    _monitor().record_failure(provider, error_message=category, latency_ms=latency)
    raise ProviderCallError(category or "unknown", status_code)


def record_output_rejected(provider: str, reason: str) -> None:
    """The provider answered (HTTP 200) but the output failed validation; it is counted as a failure, not a success.

    Before A01 a 200 response whose JSON was unusable stayed counted as a success, so monitoring could show a provider
    as "available" while every answer was being discarded (A01-N03).
    """
    _inc(provider, {"successes": -1, "failures": 1, "failure_invalid_output": 1, "outputRejected": 1},
         {"lastFailureAt": datetime.now(timezone.utc), "lastStatus": "invalid_output",
          "lastRejectReason": str(reason)[:60]})
    try:
        _monitor().record_failure(provider, error_message="invalid_output")
    except Exception:
        pass


def record_fallback(provider: str, reason: str) -> None:
    """The deterministic engine answered instead of the provider."""
    _inc(provider, {"fallbacks": 1, f"fallback_{reason}": 1})
    try:
        _monitor().record_fallback_activation(provider)
    except Exception:
        pass


def provider_status(provider: str) -> Dict[str, Any]:
    """Truthful status from configuration and today's observed calls (no network call is made)."""
    from app.config.settings import settings
    key = (settings.GEMINI_API_KEY if provider == "gemini" else settings.OPENAI_API_KEY) or ""
    model = settings.GEMINI_MODEL if provider == "gemini" else settings.OPENAI_MODEL
    effective = resolve_gemini_model(model) if provider == "gemini" else resolve_openai_model(model)
    from app.agents.llm_client import provider_order, vision_model
    order = provider_order()
    base = {"provider": provider, "configured": bool(key.strip()), "model": effective,
            "configuredModel": model, "modelRemapped": effective != model, "dailyLimit": settings.AI_DAILY_REQUEST_LIMIT,
            "visionModel": vision_model(provider),
            "role": ("primary" if order[:1] == [provider] else "secondary" if provider in order else "unused"),
            "modelShutdownDate": MODEL_SHUTDOWN_DATES.get(effective)}
    if not key.strip():
        return {**base, "status": "not_configured"}
    if int(settings.AI_DAILY_REQUEST_LIMIT) <= 0:
        return {**base, "status": "disabled"}
    try:
        today = _db()[COLLECTION].find_one({"_id": _day_key(provider)}) or {}
    except Exception:
        today = {}
    usage = {k: today.get(k, 0) for k in ("requests", "successes", "failures", "fallbacks", "promptTokens",
                                           "completionTokens", "refusedUsageLimit", "refusedCircuitOpen",
                                           "outputRejected")}
    usage["averageLatencyMs"] = round(today.get("latencyMsTotal", 0) / max(1, usage["successes"] + usage["failures"]), 1)
    last = today.get("lastStatus")
    if _monitor().is_circuit_open(provider) or last in {"auth_failed", "invalid_model", "quota_exhausted"}:
        status = "unavailable"
    elif usage["refusedUsageLimit"]:
        status = "rate_limited"  # local daily limit reached
    elif last == "rate_limited":
        status = "rate_limited"
    elif not usage["successes"] and not usage["failures"]:
        status = "configured_not_verified"
    elif usage["failures"] and usage["failures"] / max(1, usage["successes"] + usage["failures"]) > 0.25:
        status = "degraded"
    else:
        status = "available"
    return {**base, "status": status, "lastResult": last, "today": usage,
            # True only when a real provider call succeeded today (tests use a separate database).
            "liveVerified": bool(usage["successes"] > 0),
            "lastSuccessAt": today.get("lastSuccessAt"), "lastFailureAt": today.get("lastFailureAt")}
