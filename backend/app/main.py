import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.database import DatabaseManager, check_database_connection, ensure_indexes
from app.config.settings import settings
from app.routes import (
    admin_router,
    ai_recommendations_router,
    appointment_router,
    auth_router,
    doctor_router,
    notification_router,
    payment_router,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(doctor_router, prefix="/api")
app.include_router(appointment_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(payment_router, prefix="/api")
app.include_router(notification_router, prefix="/api")
app.include_router(ai_recommendations_router, prefix="/api")


@app.get("/")
def root() -> Dict[str, str]:
    """Root status endpoint."""
    return {
        "app": "MediConnect",
        "status": "running",
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Report API and database connectivity without exposing sensitive configuration."""
    db_health = check_database_connection()
    return {
        "api": "healthy",
        "database": {
            "connected": db_health["connected"],
            "status": db_health["status"],
            "message": db_health["message"],
        },
    }
