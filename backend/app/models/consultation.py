"""MongoDB document model and indexes for Consultation Sessions (Phase 57).

Separates the clinical consultation progress lifecycle (NOT_STARTED -> IN_PROGRESS -> COMPLETED)
from the patient appointment booking status (PENDING / CONFIRMED / COMPLETED / CANCELLED).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError


class ConsultationStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class ConsultationSessionDocument(BaseModel):
    """MongoDB document representation for an active doctor consultation session."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    appointmentId: str = Field(..., description="References appointments._id (Unique per appointment)")
    doctorUserId: str = Field(..., description="References users._id (doctor)")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    patientUserId: str = Field(..., description="References users._id (patient)")

    status: ConsultationStatus = Field(default=ConsultationStatus.NOT_STARTED)
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    startedBy: Optional[str] = Field(default=None, description="Doctor userId who started the consultation")
    completedBy: Optional[str] = Field(default=None, description="Doctor userId who completed the consultation")
    notes: Optional[str] = Field(default=None, max_length=2000)

    version: int = Field(default=1)
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("startedAt", "completedAt", "createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc(cls, value: Any) -> Optional[datetime]:
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


def get_consultation_collection(db: Database) -> Collection:
    """Return the consultation_sessions collection."""
    return db["consultation_sessions"]


def create_consultation_indexes(db: Database) -> None:
    """Create indexes for consultation_sessions collection.

    Unique index on appointmentId guarantees database-level concurrency protection
    against multiple simultaneous consultation creation attempts.
    """
    coll = get_consultation_collection(db)
    existing = {idx.get("name") for idx in coll.list_indexes()}

    # Unique index on appointmentId
    if "idx_consultation_appointment_unique" not in existing:
        try:
            coll.create_index(
                [("appointmentId", ASCENDING)],
                unique=True,
                name="idx_consultation_appointment_unique",
            )
        except PyMongoError:
            pass

    # Doctor lookup index
    if "idx_consultation_doctor_status" not in existing:
        try:
            coll.create_index(
                [("doctorUserId", ASCENDING), ("status", ASCENDING)],
                name="idx_consultation_doctor_status",
            )
        except PyMongoError:
            pass

    # Patient lookup index
    if "idx_consultation_patient" not in existing:
        try:
            coll.create_index(
                [("patientUserId", ASCENDING)],
                name="idx_consultation_patient",
            )
        except PyMongoError:
            pass
