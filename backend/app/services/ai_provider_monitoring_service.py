"""AI Provider Monitoring Service: Latency tracking, error accounting, and circuit breaker protection."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.models.security_event import utc_now


class AIProviderMonitoringService:
    """Monitors Gemini / OpenAI provider reliability, computes rolling metrics, and maintains circuit breaker states."""

    FAILURE_THRESHOLD = 3
    COOLDOWN_SECONDS = 60

    # In-memory circuit breaker and telemetry store
    _state: Dict[str, Dict[str, Any]] = {
        "gemini": {
            "status": "healthy",
            "circuitBreakerState": "CLOSED",  # CLOSED, OPEN, HALF_OPEN
            "consecutiveFailures": 0,
            "openedAt": None,
            "totalRequests": 0,
            "successfulRequests": 0,
            "failedRequests": 0,
            "latencies": [],
            "fallbackActivations": 0,
            "lastError": None,
            "lastErrorTimestamp": None,
        },
        "openai": {
            "status": "healthy",
            "circuitBreakerState": "CLOSED",
            "consecutiveFailures": 0,
            "openedAt": None,
            "totalRequests": 0,
            "successfulRequests": 0,
            "failedRequests": 0,
            "latencies": [],
            "fallbackActivations": 0,
            "lastError": None,
            "lastErrorTimestamp": None,
        },
    }

    @classmethod
    def is_circuit_open(cls, provider: str = "gemini") -> bool:
        """Check whether the circuit breaker is active, auto-transitioning to HALF_OPEN when cooldown elapses."""
        data = cls._state.get(provider.lower())
        if not data:
            return False

        if data["circuitBreakerState"] == "OPEN":
            opened_at = data.get("openedAt")
            if opened_at and (utc_now() - opened_at).total_seconds() > cls.COOLDOWN_SECONDS:
                data["circuitBreakerState"] = "HALF_OPEN"
                data["status"] = "degraded"
                return False
            return True

        return False

    @classmethod
    def record_success(cls, provider: str = "gemini", latency_ms: float = 0.0) -> None:
        """Record successful provider response and reset failure counters."""
        data = cls._state.setdefault(provider.lower(), {})
        data["totalRequests"] = data.get("totalRequests", 0) + 1
        data["successfulRequests"] = data.get("successfulRequests", 0) + 1
        data["consecutiveFailures"] = 0
        data["circuitBreakerState"] = "CLOSED"
        data["status"] = "healthy"

        latencies = data.setdefault("latencies", [])
        latencies.append(latency_ms)
        if len(latencies) > 100:
            latencies.pop(0)

    @classmethod
    def record_failure(cls, provider: str = "gemini", error_message: str = "", latency_ms: float = 0.0) -> None:
        """Record provider error and trip circuit breaker if threshold is crossed."""
        data = cls._state.setdefault(provider.lower(), {})
        data["totalRequests"] = data.get("totalRequests", 0) + 1
        data["failedRequests"] = data.get("failedRequests", 0) + 1
        data["consecutiveFailures"] = data.get("consecutiveFailures", 0) + 1
        data["lastError"] = error_message
        data["lastErrorTimestamp"] = utc_now()

        latencies = data.setdefault("latencies", [])
        latencies.append(latency_ms)
        if len(latencies) > 100:
            latencies.pop(0)

        if data["consecutiveFailures"] >= cls.FAILURE_THRESHOLD:
            data["circuitBreakerState"] = "OPEN"
            data["status"] = "circuit_open"
            data["openedAt"] = utc_now()
        else:
            data["status"] = "degraded"

    @classmethod
    def record_fallback_activation(cls, provider: str = "gemini") -> None:
        """Increment fallback activation count when falling back to deterministic response."""
        data = cls._state.setdefault(provider.lower(), {})
        data["fallbackActivations"] = data.get("fallbackActivations", 0) + 1

    @classmethod
    def get_metrics(cls, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return metrics and circuit breaker telemetry for one or all providers."""
        providers = [provider.lower()] if provider else list(cls._state.keys())
        results = []

        for p in providers:
            data = cls._state.get(p, {})
            latencies = data.get("latencies", [])
            avg_lat = (sum(latencies) / len(latencies)) if latencies else 0.0

            from app.config.settings import settings as _settings
            key_name = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}.get(p)
            configured = bool((getattr(_settings, key_name, None) or "").strip()) if key_name else None
            status_value = data.get("status", "healthy")
            if configured is False:
                status_value = "not_configured"
            elif not data.get("totalRequests"):
                status_value = "not_verified"  # no call observed since start-up
            # Phase 05: status and today's counters come from the durable provider-gateway metrics.
            try:
                from app.agents.provider_gateway import provider_status
                durable = provider_status(p)
                status_value = durable["status"]
            except Exception:
                durable = {}
            results.append({
                "provider": p,
                "configured": configured,
                "model": durable.get("model"),
                "modelRemapped": durable.get("modelRemapped"),
                "today": durable.get("today"),
                "dailyLimit": durable.get("dailyLimit"),
                "status": status_value,
                "circuitBreakerState": data.get("circuitBreakerState", "CLOSED"),
                "totalRequests": data.get("totalRequests", 0),
                "successfulRequests": data.get("successfulRequests", 0),
                "failedRequests": data.get("failedRequests", 0),
                "averageLatencyMs": round(avg_lat, 2),
                "fallbackActivations": data.get("fallbackActivations", 0),
                "lastError": data.get("lastError"),
                "lastErrorTimestamp": data.get("lastErrorTimestamp"),
            })

        return results

    @classmethod
    def reset(cls) -> None:
        """Reset telemetry for test isolation."""
        for p in cls._state:
            cls._state[p]["status"] = "healthy"
            cls._state[p]["circuitBreakerState"] = "CLOSED"
            cls._state[p]["consecutiveFailures"] = 0
            cls._state[p]["openedAt"] = None
            cls._state[p]["totalRequests"] = 0
            cls._state[p]["successfulRequests"] = 0
            cls._state[p]["failedRequests"] = 0
            cls._state[p]["latencies"] = []
            cls._state[p]["fallbackActivations"] = 0
            cls._state[p]["lastError"] = None
            cls._state[p]["lastErrorTimestamp"] = None
