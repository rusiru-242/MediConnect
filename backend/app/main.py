from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI

from app.config.database import DatabaseManager, check_database_connection, ensure_indexes
from app.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup index creation and shutdown connection cleanup."""
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
