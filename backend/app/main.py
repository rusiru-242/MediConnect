import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.config.database import DatabaseManager, check_database_connection, ensure_indexes
from app.config.settings import settings
from app.routes import (
    admin_router,
    ai_booking_router,
    ai_health_chat_router,
    ai_recommendations_router,
    appointment_router,
    auth_router,
    doctor_router,
    medical_record_router,
    medication_reminder_router,
    notification_router,
    payment_router,
    prescription_router,
    review_router,
    content_router,
    admin_content_router,
    analytics_router,
    care_plan_router,
    doctor_schedule_router,
    patient_timeline_router,
)

from app.routes.ai_conversations import router as ai_conversations_router
from app.services.booking_notifications import run_confirmation_outbox
from app.services.care_scheduler import run_scheduler
from app.services.appointment_service import AppointmentService
from app.routes.doctor_workflow import router as doctor_workflow_router
from app.services.doctor_communications import run_communications
from app.routes.care_automation import router as care_automation_router
from app.routes.admin_workflow import router as admin_workflow_router
from app.routes.clinical_workflow import clinical_workflow_router
from app.routes.security_monitoring import probe_router, router as security_monitoring_router
from app.services.platform_monitoring_service import PlatformMonitoringService

logger = logging.getLogger(__name__)


async def _run_reminder_worker():
    """Process durable care and booking-confirmation jobs."""
    logger.info("Appointment reminder background worker started.")
    while True:
        try:
            await asyncio.sleep(settings.REMINDER_CHECK_INTERVAL_SECONDS)
            db_status = check_database_connection()
            if db_status.get("connected"):
                db = DatabaseManager.get_database()
                t0 = asyncio.get_event_loop().time()
                await asyncio.to_thread(run_scheduler, db)
                await asyncio.to_thread(AppointmentService.release_expired_holds, db)
                # A03-BUG-005: a released hold's open PaymentIntent must not be payable any more.
                await asyncio.to_thread(AppointmentService.stop_intents_of_released_holds, db)
                await asyncio.to_thread(run_confirmation_outbox, db)
                await asyncio.to_thread(run_communications, db)
                # A05 (Agent 25): rule-based review signals for recently active accounts; no account action.
                from app.services.fraud_detection_service import FraudDetectionService
                await asyncio.to_thread(FraudDetectionService.run_detection_sweep, db)
                # B3 fallback (Phase 05): refunds that stayed pending are re-read from Stripe until webhooks are
                # delivered to this backend.
                from app.services.stripe_webhook_service import sync_pending_refunds
                await asyncio.to_thread(sync_pending_refunds, db)
                duration = asyncio.get_event_loop().time() - t0
                # job_count was a constant 3 (the number of job types), shown as "pending jobs"; it is not recorded
                # now because the worker does not measure a backlog (P04-N14).
                PlatformMonitoringService.record_worker_heartbeat("reminder_care_worker", duration_seconds=duration, db=db)
        except asyncio.CancelledError:
            logger.info("Appointment reminder background worker stopping.")
            break
        except Exception as exc:
            logger.warning("Care worker iteration failed (%s)", type(exc).__name__)
            try:
                PlatformMonitoringService.record_worker_heartbeat(
                    "reminder_care_worker", failed_count=1, db=DatabaseManager.get_database(), error=type(exc).__name__)
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup validation, index creation, background workers, and shutdown cleanup."""
    from app.config.runtime_safety import startup_errors
    problems = startup_errors(settings)
    if problems:
        # Messages never contain secret values.
        raise RuntimeError("Refusing to start: " + " ".join(problems))
    db_status = check_database_connection()
    if db_status.get("connected"):
        ensure_indexes()

    worker_task = asyncio.create_task(_run_reminder_worker())

    yield

    worker_task.cancel()
    try:
        await worker_task
    except (asyncio.CancelledError, Exception):
        pass

    DatabaseManager.close_connection()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

configured_origins = (
    [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
    if settings.ALLOWED_ORIGINS and settings.ALLOWED_ORIGINS != "*"
    else []
)

cors_origins = list(dict.fromkeys(default_origins + configured_origins))

cors_origin_regex = (
    os.getenv("CORS_ORIGIN_REGEX")
    or r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://([a-zA-Z0-9_-]+\.)*vercel\.app$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Enforce defensive security response headers across all HTTP endpoints."""
    response = await call_next(request)
    if settings.SECURE_HEADERS_ENABLED:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(auth_router, prefix="/api")
app.include_router(doctor_router, prefix="/api")
app.include_router(appointment_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(admin_workflow_router, prefix="/api")
app.include_router(payment_router, prefix="/api")
app.include_router(notification_router, prefix="/api")
app.include_router(ai_recommendations_router, prefix="/api")
app.include_router(ai_booking_router, prefix="/api")
app.include_router(ai_conversations_router, prefix="/api")
app.include_router(ai_health_chat_router, prefix="/api")
app.include_router(medical_record_router, prefix="/api")
app.include_router(prescription_router, prefix="/api")
app.include_router(medication_reminder_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(content_router, prefix="/api")
app.include_router(admin_content_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(care_plan_router, prefix="/api")
app.include_router(care_automation_router, prefix="/api")
app.include_router(doctor_schedule_router, prefix="/api")
app.include_router(doctor_workflow_router, prefix="/api")
app.include_router(patient_timeline_router, prefix="/api")
app.include_router(clinical_workflow_router, prefix="/api")
app.include_router(security_monitoring_router, prefix="/api")
app.include_router(probe_router, prefix="/api")
app.include_router(probe_router)



@app.get("/")
def root() -> Dict[str, str]:
    """Root status endpoint."""
    return {
        "app": "MediConnect",
        "status": "running",
    }


@app.get("/health")
@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Report API and database connectivity without exposing sensitive configuration."""
    db_health = check_database_connection()
    database = {
        "connected": db_health["connected"],
        "status": db_health["status"],
        "message": db_health["message"],
    }
    if (settings.ENVIRONMENT or "").lower() != "production":
        # Lets integration tests refuse to run against anything but an isolated local test database
        # (Phase 02). A boolean only: no database name, host or URI is exposed.
        from urllib.parse import urlsplit
        host = (urlsplit(settings.MONGODB_URI or "").hostname or "").lower()
        name = (settings.DATABASE_NAME or "").strip()
        database["isolatedTestData"] = host in {"localhost", "127.0.0.1"} and name.endswith(("_uat", "_test"))
    return {
        "status": "healthy" if db_health["connected"] else "degraded",
        "api": "healthy",
        "database": database,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready")
@app.get("/api/ready")
def readiness_check(response: Response) -> Dict[str, Any]:
    """Readiness probe for container orchestrators (k8s/ECS/Cloud Run)."""
    db_health = check_database_connection()
    if not db_health["connected"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unready",
            "message": "Database is not connected.",
        }
    return {
        "status": "ready",
        "message": "All dependencies healthy.",
    }
