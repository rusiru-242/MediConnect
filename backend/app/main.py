from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI

from app.config.database import DatabaseManager, check_database_connection, ensure_indexes
from app.config.settings import settings
from app.routes import admin_router, appointment_router, auth_router, doctor_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup validation, index creation, and shutdown cleanup."""
    if not settings.JWT_SECRET or not settings.JWT_SECRET.strip():
        raise RuntimeError("JWT_SECRET environment variable is missing. Refusing to start.")
    db_status = check_database_connection()
    if db_status.get("connected"):
        ensure_indexes()
    yield
    DatabaseManager.close_connection()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router, prefix="/api")
app.include_router(doctor_router, prefix="/api")
app.include_router(appointment_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


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
