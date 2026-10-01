import logging
from typing import Any, Dict, Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConfigurationError, ConnectionFailure, PyMongoError

from app.config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages reusable MongoDB client and database connections."""

    _client: Optional[MongoClient] = None
    _db: Optional[Database] = None

    @classmethod
    def get_client(cls) -> MongoClient:
        """Return a reusable MongoClient instance or raise ConnectionError if unconfigured."""
        if cls._client is None:
            if not settings.MONGODB_URI or not settings.MONGODB_URI.strip():
                raise ConnectionError("MONGODB_URI environment variable is not configured.")
            try:
                try:
                    import dns.resolver

                    resolver = dns.resolver.get_default_resolver()
                    resolver.nameservers = ["8.8.8.8", "1.1.1.1"] + [
                        ns for ns in resolver.nameservers if ns not in ["8.8.8.8", "1.1.1.1"]
                    ]
                except Exception:
                    pass

                cls._client = MongoClient(
                    settings.MONGODB_URI,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=10000,
                    tz_aware=True,
                )
            except (ConfigurationError, PyMongoError) as exc:
                logger.error("Failed to initialize MongoDB client.")
                raise ConnectionError("Invalid MongoDB configuration.") from exc
        return cls._client

    @classmethod
    def get_database(cls) -> Database:
        """Return the configured MongoDB Database instance."""
        if cls._db is None:
            client = cls.get_client()
            cls._db = client[settings.DATABASE_NAME]
        return cls._db

    @classmethod
    def close_connection(cls) -> None:
        """Close the MongoDB client connection cleanly."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None


def get_database() -> Database:
    """Dependency/helper to obtain the application's MongoDB database."""
    return DatabaseManager.get_database()


def ensure_indexes(db: Optional[Database] = None) -> bool:
    """Create required MongoDB indexes for users, refresh tokens, and password resets."""
    from app.models.appointment import create_appointment_indexes
    from app.models.doctor_availability import create_doctor_availability_indexes
    from app.models.doctor_profile import create_doctor_profile_indexes
    from app.models.password_reset import create_password_reset_indexes
    from app.models.token import create_token_indexes
    from app.models.user import create_user_indexes

    try:
        target_db = db if db is not None else DatabaseManager.get_database()
        create_user_indexes(target_db)
        create_token_indexes(target_db)
        create_password_reset_indexes(target_db)
        create_doctor_profile_indexes(target_db)
        create_doctor_availability_indexes(target_db)
        create_appointment_indexes(target_db)
        return True
    except (ConnectionError, ConnectionFailure, PyMongoError) as exc:
        logger.warning("Could not create MongoDB indexes at this time: %s", type(exc).__name__)
        return False


def check_database_connection() -> Dict[str, Any]:
    """Check MongoDB connectivity without exposing sensitive credentials."""
    if not settings.MONGODB_URI or not settings.MONGODB_URI.strip():
        return {
            "connected": False,
            "status": "not_configured",
            "message": "Database URI is not configured.",
        }

    try:
        client = DatabaseManager.get_client()
        client.admin.command("ping")
        return {
            "connected": True,
            "status": "connected",
            "message": "Database connection is healthy.",
        }
    except (ConnectionError, ConnectionFailure, PyMongoError):
        return {
            "connected": False,
            "status": "disconnected",
            "message": "Unable to establish database connection.",
        }
