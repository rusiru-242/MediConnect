"""Platform Monitoring Service: Non-destructive health telemetry, dependency checks, and worker heartbeats."""

from datetime import datetime, timedelta, timezone
import os
import time
from typing import Any, Dict, List, Optional
from pymongo.database import Database

from app.config.database import DatabaseManager, check_database_connection, get_database
from app.config.settings import settings
from app.models.security_event import utc_now


_PROCESS_START_TIME = time.time()


class PlatformMonitoringService:
    """Provides non-destructive system health monitoring and background worker telemetry."""

    @classmethod
    def get_uptime_seconds(cls) -> float:
        """Return application uptime in seconds."""
        return max(0.0, time.time() - _PROCESS_START_TIME)

    # Status vocabulary (P04-N14): healthy and unavailable are measured; "not_configured" means no credentials;
    # "configured_not_verified" means credentials exist but nothing proved the provider works; "disabled" means
    # switched off on purpose. A configured provider is never reported as healthy without a successful call.

    @classmethod
    def check_database_health(cls, db: Optional[Database] = None) -> Dict[str, Any]:
        """Verify database connectivity and measure command ping latency (no host names are returned)."""
        t0 = time.time()
        try:
            if db is None:
                db = get_database()
            db.command("ping")
            latency = (time.time() - t0) * 1000.0
            return {
                "name": "MongoDB",
                "status": "healthy",
                "latencyMs": round(latency, 2),
                "message": "Ping succeeded.",
            }
        except Exception as exc:
            latency = (time.time() - t0) * 1000.0
            return {
                "name": "MongoDB",
                "status": "unavailable",
                "latencyMs": round(latency, 2),
                "message": f"Connection check failed: {type(exc).__name__}",
            }

    @classmethod
    def check_stripe_health(cls) -> Dict[str, Any]:
        """Report Stripe configuration and mode. No Stripe API call is made from monitoring (no paid operation)."""
        key = (settings.STRIPE_SECRET_KEY or "").strip()
        if not key:
            return {"name": "Stripe Payments", "status": "not_configured", "latencyMs": None,
                    "message": "No Stripe secret key is configured."}
        mode = "test" if key.startswith("sk_test_") else ("live" if key.startswith("sk_live_") else "unknown")
        return {"name": "Stripe Payments", "status": "configured_not_verified", "latencyMs": None,
                "message": f"A {mode}-mode key is configured. Monitoring does not call Stripe, so availability is not verified."}

    @classmethod
    def check_notification_providers_health(cls) -> Dict[str, Any]:
        """Combined email/SMS/push configuration (kept for callers that expect one entry)."""
        rows = cls.check_notification_channels()
        configured = [r["name"] for r in rows if r["status"] != "not_configured"]
        return {
            "name": "Notification Providers",
            "status": "configured_not_verified" if configured else "not_configured",
            "latencyMs": None,
            "message": (f"Configured, not verified: {', '.join(configured)}." if configured
                        else "Email, SMS and push providers are not configured; only in-app notifications are stored."),
        }

    @classmethod
    def check_notification_channels(cls) -> List[Dict[str, Any]]:
        def entry(name, configured, detail):
            return {"name": name, "status": "configured_not_verified" if configured else "not_configured",
                    "latencyMs": None, "message": detail if configured else f"{name} is not configured."}
        smtp = bool((settings.SMTP_HOST or "").strip() and (settings.SMTP_USERNAME or "").strip())
        twilio = bool((os.getenv("TWILIO_ACCOUNT_SID") or "").strip() and (os.getenv("TWILIO_AUTH_TOKEN") or "").strip())
        fcm = bool((settings.FIREBASE_CREDENTIALS_PATH or "").strip() or (settings.FIREBASE_SERVICE_ACCOUNT_JSON or "").strip())
        return [
            entry("Email (SMTP)", smtp, "SMTP credentials are configured; delivery is not verified by monitoring."),
            entry("SMS (Twilio)", twilio, "Twilio credentials are configured; delivery is not verified by monitoring."),
            entry("Push (FCM)", fcm, "Firebase credentials are configured; delivery is not verified by monitoring."),
        ]

    @classmethod
    def check_ai_provider_health(cls) -> Dict[str, Any]:
        gemini = bool((settings.GEMINI_API_KEY or "").strip())
        openai = bool((getattr(settings, "OPENAI_API_KEY", None) or "").strip())
        if not (gemini or openai):
            return {"name": "AI Providers", "status": "disabled", "latencyMs": None,
                    "message": "No Gemini or OpenAI key is configured; the deterministic engine answers."}
        # Phase 05: derived from calls actually observed today (provider gateway), never assumed.
        from app.agents.provider_gateway import provider_status
        states = [provider_status(p) for p, ok in (("gemini", gemini), ("openai", openai)) if ok]
        order = ["unavailable", "rate_limited", "degraded", "configured_not_verified", "disabled", "available"]
        worst = min((s["status"] for s in states), key=lambda v: order.index(v) if v in order else 0)
        return {"name": "AI Providers", "status": worst, "latencyMs": None,
                "message": "; ".join(f"{s['provider']}: {s['status']} (model {s['model']})" for s in states)}

    @classmethod
    def record_worker_heartbeat(
        cls,
        worker_name: str,
        job_count: Optional[int] = None,
        duration_seconds: float = 0.0,
        failed_count: int = 0,
        db: Optional[Database] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record or update a background worker's heartbeat in durable storage."""
        if db is None:
            db = get_database()

        now = utc_now()
        db["worker_heartbeats"].update_one(
            {"workerName": worker_name},
            {
                "$set": {
                    "lastHeartbeat": now,
                    "lastDurationSeconds": round(duration_seconds, 3),
                    "pendingJobCount": job_count,
                    "failedJobCount": failed_count,
                    "status": "error" if error else "active",
                    "lastError": error,
                    "updatedAt": now,
                    **({} if error else {"lastSuccessAt": now}),
                }
            },
            upsert=True,
        )

    @classmethod
    def get_worker_heartbeats(cls, db: Optional[Database] = None) -> List[Dict[str, Any]]:
        """Retrieve background worker heartbeats, flagging stale workers (> 5 minutes)."""
        if db is None:
            db = get_database()

        now = utc_now()
        threshold = now - timedelta(minutes=5)
        workers = list(db["worker_heartbeats"].find({}))

        results = []
        for w in workers:
            last_hb = w.get("lastHeartbeat")
            if isinstance(last_hb, datetime) and last_hb.tzinfo is None:
                last_hb = last_hb.replace(tzinfo=timezone.utc)
            is_stale = last_hb is None or last_hb < threshold
            last_state = w.get("status")
            results.append({
                "workerName": w.get("workerName", "unknown"),
                "status": "stale" if is_stale else ("error" if last_state == "error" else "active"),
                "lastHeartbeat": last_hb,
                "lastDurationSeconds": w.get("lastDurationSeconds"),
                "pendingJobCount": w.get("pendingJobCount"),
                "failedJobCount": w.get("failedJobCount", 0),
                "lastError": w.get("lastError"),
                "lastSuccessAt": w.get("lastSuccessAt"),
            })

        # The built-in worker is listed even before its first heartbeat, but as "not_reported" (it used to be
        # reported "active" with a heartbeat of "now", which hid a worker that never ran) (P04-N14).
        known_names = {r["workerName"] for r in results}
        if "reminder_care_worker" not in known_names:
            results.append({
                "workerName": "reminder_care_worker",
                "status": "not_reported",
                "lastHeartbeat": None,
                "lastDurationSeconds": None,
                "pendingJobCount": None,
                "failedJobCount": None,
            })

        return results

    @classmethod
    def get_platform_health_snapshot(cls, db: Optional[Database] = None) -> Dict[str, Any]:
        """Aggregate comprehensive platform health snapshot."""
        if db is None:
            db = get_database()

        db_health = cls.check_database_health(db)
        stripe_health = cls.check_stripe_health()

        dependencies = [db_health, stripe_health, *cls.check_notification_channels(), cls.check_ai_provider_health()]
        workers = cls.get_worker_heartbeats(db)

        # Count active incidents & open fraud assessments
        active_incidents = db["operational_incidents"].count_documents({"status": {"$in": ["OPEN", "ACKNOWLEDGED", "INVESTIGATING"]}})
        open_fraud = db["fraud_risk_assessments"].count_documents({"reviewStatus": {"$in": ["DETECTED", "AWAITING_REVIEW", "INVESTIGATING"]}})

        # Determine overall status
        if db_health["status"] == "unavailable":
            overall_status = "critical"
        elif any(d["status"] in ("degraded", "unavailable") for d in dependencies) or any(
                w["status"] in ("stale", "error", "not_reported") for w in workers):
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "uptimeSeconds": round(cls.get_uptime_seconds(), 1),
            "timestamp": utc_now(),
            "dependencies": dependencies,
            "workers": workers,
            "activeIncidentsCount": active_incidents,
            "openFraudAssessmentsCount": open_fraud,
            "aiAgentRuns24h": cls.ai_agent_run_summary(db),
        }

    @classmethod
    def ai_agent_run_summary(cls, db: Database) -> Dict[str, Any]:
        """Measured AI assistant executions in the last 24 hours (Phase 05, component 38): counts by outcome."""
        since = utc_now() - timedelta(hours=24)
        try:
            runs = db["ai_agent_runs"].count_documents({"startedAt": {"$gte": since}})
            with_errors = db["ai_agent_runs"].count_documents({"startedAt": {"$gte": since}, "errors": {"$gt": 0}})
            outcomes = {row["_id"]: row["n"] for row in db["ai_agent_runs"].aggregate([
                {"$match": {"startedAt": {"$gte": since}}}, {"$unwind": "$tools"},
                {"$group": {"_id": "$tools.outcome", "n": {"$sum": 1}}}])}
        except Exception:
            return {"status": "not_reported"}
        return {"runs": runs, "runsWithToolErrors": with_errors, "toolOutcomes": outcomes}
