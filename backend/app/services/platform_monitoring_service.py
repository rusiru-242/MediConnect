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

    @classmethod
    def check_database_health(cls, db: Optional[Database] = None) -> Dict[str, Any]:
        """Verify database connectivity and measure command ping latency."""
        t0 = time.time()
        try:
            if db is None:
                db = get_database()
            db.command("ping")
            latency = (time.time() - t0) * 1000.0
            return {
                "name": "MongoDB Atlas",
                "status": "healthy",
                "latencyMs": round(latency, 2),
                "message": "Connected and responsive.",
            }
        except Exception as exc:
            latency = (time.time() - t0) * 1000.0
            return {
                "name": "MongoDB Atlas",
                "status": "unavailable",
                "latencyMs": round(latency, 2),
                "message": f"Connection check failed: {type(exc).__name__}",
            }

    @classmethod
    def check_stripe_health(cls) -> Dict[str, Any]:
        """Check Stripe integration configuration without processing real charges."""
        configured = bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_SECRET_KEY.strip())
        return {
            "name": "Stripe Payments",
            "status": "healthy" if configured else "unconfigured",
            "latencyMs": None,
            "message": "API keys configured." if configured else "Stripe key not configured.",
        }

    @classmethod
    def check_notification_providers_health(cls) -> Dict[str, Any]:
        """Check SMS and Email outbound provider configuration status."""
        twilio_configured = bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))
        email_configured = bool(settings.SMTP_HOST and settings.SMTP_USERNAME)

        if twilio_configured and email_configured:
            status = "healthy"
            msg = "Email (SMTP) and SMS (Twilio) configured."
        elif email_configured or twilio_configured:
            status = "degraded"
            msg = "Partial provider configuration."
        else:
            status = "unconfigured"
            msg = "Email and SMS providers unconfigured."

        return {
            "name": "Notification Providers",
            "status": status,
            "latencyMs": None,
            "message": msg,
        }

    @classmethod
    def record_worker_heartbeat(
        cls,
        worker_name: str,
        job_count: int = 0,
        duration_seconds: float = 0.0,
        failed_count: int = 0,
        db: Optional[Database] = None,
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
                    "status": "active",
                    "updatedAt": now,
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
            is_stale = last_hb is None or last_hb < threshold
            results.append({
                "workerName": w.get("workerName", "unknown"),
                "status": "stale" if is_stale else "active",
                "lastHeartbeat": last_hb or now,
                "lastDurationSeconds": w.get("lastDurationSeconds", 0.0),
                "pendingJobCount": w.get("pendingJobCount", 0),
                "failedJobCount": w.get("failedJobCount", 0),
            })

        # Ensure default workers are represented even before first run
        known_names = {r["workerName"] for r in results}
        if "reminder_care_worker" not in known_names:
            results.append({
                "workerName": "reminder_care_worker",
                "status": "active",
                "lastHeartbeat": now,
                "lastDurationSeconds": 0.0,
                "pendingJobCount": 0,
                "failedJobCount": 0,
            })

        return results

    @classmethod
    def get_platform_health_snapshot(cls, db: Optional[Database] = None) -> Dict[str, Any]:
        """Aggregate comprehensive platform health snapshot."""
        if db is None:
            db = get_database()

        db_health = cls.check_database_health(db)
        stripe_health = cls.check_stripe_health()
        notification_health = cls.check_notification_providers_health()

        dependencies = [db_health, stripe_health, notification_health]
        workers = cls.get_worker_heartbeats(db)

        # Count active incidents & open fraud assessments
        active_incidents = db["operational_incidents"].count_documents({"status": {"$in": ["OPEN", "ACKNOWLEDGED", "INVESTIGATING"]}})
        open_fraud = db["fraud_risk_assessments"].count_documents({"reviewStatus": {"$in": ["DETECTED", "AWAITING_REVIEW", "INVESTIGATING"]}})

        # Determine overall status
        if db_health["status"] == "unavailable":
            overall_status = "critical"
        elif any(d["status"] in ("degraded", "unavailable") for d in dependencies) or any(w["status"] == "stale" for w in workers):
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
        }
