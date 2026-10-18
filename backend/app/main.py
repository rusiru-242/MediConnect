import asyncio
import logging
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
)

from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


async def _run_reminder_worker():
    """Periodic background worker for 24-hour and 1-hour appointment reminders."""
    logger.info("Appointment reminder background worker started.")
    while True:
        try:
            await asyncio.sleep(settings.REMINDER_CHECK_INTERVAL_SECONDS)
            db_status = check_database_connection()
            if db_status.get("connected"):
                db = DatabaseManager.get_database()
                NotificationService.check_and_send_appointment_reminders(db)
        except asyncio.CancelledError:
            logger.info("Appointment reminder background worker stopping.")
            break
        except Exception as exc:
            logger.warning("Appointment reminder worker loop error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup validation, index creation, background workers, and shutdown cleanup."""
    if not settings.JWT_SECRET or not settings.JWT_SECRET.strip():
        raise RuntimeError("JWT_SECRET environment variable is missing. Refusing to start.")
    if settings.ENVIRONMENT == "production" and len(settings.JWT_SECRET.strip().encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 bytes (256 bits) in production mode.")
    if settings.ENVIRONMENT == "production" and (not settings.MONGODB_URI or not settings.MONGODB_URI.strip()):
        raise RuntimeError("MONGODB_URI environment variable is required in production mode.")
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

cors_origins = (
    [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
    if settings.ALLOWED_ORIGINS and settings.ALLOWED_ORIGINS != "*"
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
app.include_router(payment_router, prefix="/api")
app.include_router(notification_router, prefix="/api")
app.include_router(ai_recommendations_router, prefix="/api")
app.include_router(ai_booking_router, prefix="/api")
app.include_router(ai_health_chat_router, prefix="/api")
app.include_router(medical_record_router, prefix="/api")
app.include_router(prescription_router, prefix="/api")
app.include_router(medication_reminder_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(content_router, prefix="/api")
app.include_router(admin_content_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")



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
    return {
        "status": "healthy" if db_health["connected"] else "degraded",
        "api": "healthy",
        "database": {
            "connected": db_health["connected"],
            "status": db_health["status"],
            "message": db_health["message"],
        },
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
