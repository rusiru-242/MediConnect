"""MongoDB document model and indexes for patient appointments."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class AppointmentStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class AppointmentDocument(BaseModel):
    """MongoDB document representation for a patient Appointment."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")

    # Patient
    patientUserId: str = Field(..., description="References users._id (patient)")

    # Doctor references
    doctorUserId: str = Field(..., description="References users._id (doctor)")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    availabilityId: str = Field(..., description="References doctor_availabilities._id")

    # Appointment slot (Sri Lanka local date/time strings)
    appointmentDate: str = Field(..., description="Appointment date YYYY-MM-DD (Sri Lanka local)")
    startTime: str = Field(..., description="Slot start time HH:MM (24-hour)")
    endTime: str = Field(..., description="Slot end time HH:MM (24-hour)")

    # Status machine
    status: AppointmentStatus = Field(default=AppointmentStatus.PENDING)

    # Optional patient note
    patientNote: Optional[str] = Field(default=None, max_length=500)

    # Cancellation metadata
    cancelledBy: Optional[str] = Field(default=None, description="PATIENT | DOCTOR | ADMIN")
    cancellationReason: Optional[str] = Field(default=None, max_length=500)

    # Audit timestamps (UTC)
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("createdAt", "updatedAt", mode="before")
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


def get_appointment_collection(db: Database) -> Collection:
    """Return the MongoDB appointments collection."""
    return db["appointments"]


def create_appointment_indexes(db: Database) -> None:
    """Create indexes on appointments collection.

    The partial unique index on (doctorUserId, appointmentDate, startTime) for
    non-cancelled appointments provides database-level double-booking protection.
    """
    collection = get_appointment_collection(db)

    # Patient lookup
    collection.create_index(
        [("patientUserId", ASCENDING), ("appointmentDate", ASCENDING), ("startTime", ASCENDING)],
        name="idx_appt_patient_date",
    )

    # Doctor lookup
    collection.create_index(
        [("doctorUserId", ASCENDING), ("appointmentDate", ASCENDING), ("startTime", ASCENDING)],
        name="idx_appt_doctor_date",
    )

    # Double-booking protection: unique per active slot (excludes CANCELLED)
    collection.create_index(
        [
            ("doctorUserId", ASCENDING),
            ("appointmentDate", ASCENDING),
            ("startTime", ASCENDING),
        ],
        unique=True,
        partialFilterExpression={
            "status": {"$in": [
                AppointmentStatus.PENDING.value,
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.COMPLETED.value,
            ]}
        },
        name="idx_appt_doctor_slot_unique_active",
    )

    # Availability linkage index
    collection.create_index(
        [("availabilityId", ASCENDING), ("status", ASCENDING)],
        name="idx_appt_availability_status",
    )
