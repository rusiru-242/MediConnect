"""Single choke point for every external LLM call (Phase 05, component 32).

Before Phase 05 the Gemini and OpenAI adapters each called ``requests.post`` directly: the Gemini parser put the API
key in the URL query string, nothing enforced a usage limit, and the provider-monitoring counters and circuit
breaker were never updated by a real call (they always showed their start-up values).

Every call now goes through :func:`send`, which

* refuses to call when the daily request limit (``AI_DAILY_REQUEST_LIMIT``, counted atomically in MongoDB across
  processes) is reached, or when the circuit breaker for that provider is open;
* sends credentials only in headers;
* classifies failures (auth_failed, rate_limited, timeout, invalid_model, server_error, network, invalid_output);
* retries once, only for rate limits, 5xx and connection errors (never for 4xx);
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

# Model identifiers that providers have retired. They are mapped to the provider's maintained alias so an old
# .env keeps working, and the mapping is reported in provider status instead of happening silently.
RETIRED_GEMINI_MODELS = {"gemini-1.5-flash": "gemini-flash-latest", "gemini-1.5-pro": "gemini-pro-latest",
                         "gemini-2.5-flash": "gemini-flash-latest"}


class ProviderCallError(Exception):
    def __init__(self, category: str, status_code: Optional[int] = None):
        super().__init__(category)
        self.category = category
        self.status_code = status_code


def resolve_gemini_model(model: str) -> str:
    name = (model or "").strip().removeprefix("models/")
    return RETIRED_GEMINI_MODELS.get(name, name or "gemini-flash-latest")


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
    if status_code in (401, 403):
        return "auth_failed"
    if status_code == 429:
        return "rate_limited"
    if status_code == 404 or (status_code == 400 and "model" in body.lower()):
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
    for attempt in range(2):
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
        category = _classify(status_code, response.text[:300])
        if attempt == 0 and category in {"rate_limited", "server_error"}:
            continue
        break
    latency = (time.monotonic() - started) * 1000
    _inc(provider, {"failures": 1, f"failure_{category}": 1, "latencyMsTotal": latency},
         {"lastFailureAt": datetime.now(timezone.utc), "lastStatus": category})
    _monitor().record_failure(provider, error_message=category, latency_ms=latency)
    raise ProviderCallError(category or "unknown", status_code)


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
    effective = resolve_gemini_model(model) if provider == "gemini" else model
    base = {"provider": provider, "configured": bool(key.strip()), "model": effective,
            "configuredModel": model, "modelRemapped": effective != model, "dailyLimit": settings.AI_DAILY_REQUEST_LIMIT}
    if not key.strip():
        return {**base, "status": "not_configured"}
    if int(settings.AI_DAILY_REQUEST_LIMIT) <= 0:
        return {**base, "status": "disabled"}
    try:
        today = _db()[COLLECTION].find_one({"_id": _day_key(provider)}) or {}
    except Exception:
        today = {}
    usage = {k: today.get(k, 0) for k in ("requests", "successes", "failures", "fallbacks", "promptTokens",
                                           "completionTokens", "refusedUsageLimit", "refusedCircuitOpen")}
    usage["averageLatencyMs"] = round(today.get("latencyMsTotal", 0) / max(1, usage["successes"] + usage["failures"]), 1)
    last = today.get("lastStatus")
    if _monitor().is_circuit_open(provider) or last in {"auth_failed", "invalid_model"}:
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
            "lastSuccessAt": today.get("lastSuccessAt"), "lastFailureAt": today.get("lastFailureAt")}
