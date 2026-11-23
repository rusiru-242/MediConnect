"""MongoDB document model and indexes for AI Health Symptom Guidance & Referral sessions."""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class TriageLevel(str, Enum):
    """Safety triage classification levels."""

    EMERGENCY = "emergency"
    PROMPT_CARE = "prompt_care"
    ROUTINE_CARE = "routine_care"
    GENERAL_INFO = "general_info"


class HealthMessageSender(str, Enum):
    """Sender identifier for health chat messages."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class HealthChatMessageDocument(BaseModel):
    """Individual chat turn in health guidance conversation."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()))
    sender: str = Field(..., description="'user' | 'assistant' | 'system'")
    content: str
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("id", mode="before")
    @classmethod
    def convert_id(cls, value: Any) -> str:
        if isinstance(value, ObjectId):
            return str(value)
        return str(value)

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return utc_now()


class HealthChatSessionDocument(BaseModel):
    """MongoDB document model for AI Health Chat sessions."""

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    patientUserId: str
    language: str = Field(default="en", description="'en' or 'si'")
    consentGiven: bool = Field(default=True)
    triageLevel: Optional[str] = Field(default=TriageLevel.GENERAL_INFO.value)
    recommendedSpecialty: Optional[str] = None
    messages: List[HealthChatMessageDocument] = Field(default_factory=list)

    # Privacy & lifecycle timestamps (UTC)
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)
    # Automatic 48-hour expiration for data minimization & privacy compliance
    expiresAt: datetime = Field(default_factory=lambda: utc_now() + timedelta(hours=48))

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("createdAt", "updatedAt", "expiresAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Serialize model for MongoDB insertion/update."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if "_id" in data and isinstance(data["_id"], str) and ObjectId.is_valid(data["_id"]):
            data["_id"] = ObjectId(data["_id"])
        return data


def get_health_chat_collection(db: Database) -> Collection:
    """Return the MongoDB 'health_chat_sessions' collection."""
    return db["health_chat_sessions"]


def create_health_chat_indexes(db: Database) -> None:
    """Create indexes on health_chat_sessions collection."""
    collection = get_health_chat_collection(db)
    collection.create_index(
        [("patientUserId", ASCENDING), ("updatedAt", DESCENDING)],
        name="idx_health_chat_patient_updated",
    )
    collection.create_index(
        [("expiresAt", ASCENDING)],
        expireAfterSeconds=0,
        name="idx_health_chat_ttl",
    )
