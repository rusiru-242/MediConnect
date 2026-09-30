from datetime import datetime, timezone
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class RefreshTokenDocument(BaseModel):
    """Database document representing a stored refresh token hash."""

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[str] = Field(default=None, alias="_id")
    userId: str
    tokenHash: str
    expiresAt: datetime
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    revokedAt: Optional[datetime] = None
    deviceInfo: Optional[str] = None


def get_token_collection(db: Database) -> Collection:
    """Return the MongoDB 'refresh_tokens' collection."""
    return db["refresh_tokens"]


def create_token_indexes(db: Database) -> None:
    """Create indexes for refresh token storage and fast lookup."""
    collection = get_token_collection(db)
    collection.create_index(
        [("tokenHash", ASCENDING)],
        unique=True,
        name="idx_refresh_tokens_hash_unique",
    )
    collection.create_index(
        [("userId", ASCENDING)],
        name="idx_refresh_tokens_user_id",
    )
    collection.create_index(
        [("expiresAt", ASCENDING)],
        expireAfterSeconds=0,
        name="idx_refresh_tokens_ttl",
    )
