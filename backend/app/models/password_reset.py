from datetime import datetime, timezone
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class PasswordResetDocument(BaseModel):
    """Database document representing an active or completed password reset request."""

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[str] = Field(default=None, alias="_id")
    userId: str
    email: str
    otpHash: str
    expiresAt: datetime
    attempts: int = 0
    lastSentAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    used: bool = False
    usedAt: Optional[datetime] = None
    resetTokenHash: Optional[str] = None
    resetTokenExpiresAt: Optional[datetime] = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def get_password_reset_collection(db: Database) -> Collection:
    """Return the MongoDB 'password_resets' collection."""
    return db["password_resets"]


def create_password_reset_indexes(db: Database) -> None:
    """Create indexes for password reset challenges."""
    collection = get_password_reset_collection(db)
    collection.create_index(
        [("email", ASCENDING)],
        name="idx_password_resets_email",
    )
    collection.create_index(
        [("userId", ASCENDING)],
        name="idx_password_resets_user_id",
    )
    collection.create_index(
        [("resetTokenHash", ASCENDING)],
        sparse=True,
        name="idx_password_resets_token_hash",
    )
    collection.create_index(
        [("expiresAt", ASCENDING)],
        expireAfterSeconds=86400,  # Auto-cleanup records 24h after expiration
        name="idx_password_resets_ttl",
    )
