"""MongoDB document models and database indexes for Smart Medication Reminder System (Phase 22)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class ReminderStatus(str, Enum):
    """Lifecycle status of a medication reminder schedule."""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class EventStatus(str, Enum):
    """Status recorded for a single scheduled medication occurrence."""

    TAKEN = "TAKEN"
    SKIPPED = "SKIPPED"
    SNOOZED = "SNOOZED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class MedicationReminderDocument(BaseModel):
    """MongoDB document representation for a patient medication reminder schedule."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    reminderId: str = Field(..., description="Unique human-readable reference ID e.g. REM-20261018-XXXX")
    patientUserId: str = Field(..., description="References users._id of the patient")
    prescriptionId: str = Field(..., description="Prescription human-readable reference e.g. RX-20261018-XXXX")
    prescriptionDbId: str = Field(..., description="References prescriptions._id")
    prescriptionMedicationIndex: int = Field(default=0, ge=0, description="Index of medication in prescription medicationItems list")

    medicationName: str = Field(..., min_length=1, max_length=200, description="Prescribed medication name")
    strength: str = Field(..., min_length=1, max_length=100, description="Prescribed drug strength e.g. 500mg")
    dose: str = Field(..., min_length=1, max_length=100, description="Prescribed dose e.g. 1 tablet")
    route: str = Field(default="Oral", max_length=100, description="Administration route e.g. Oral")
    frequency: str = Field(..., min_length=1, max_length=100, description="Doctor-prescribed frequency e.g. Twice daily")
    duration: str = Field(..., min_length=1, max_length=100, description="Prescribed duration e.g. 5 days")

    scheduledTimes: List[str] = Field(
        ...,
        min_length=1,
        description="Daily reminder times in HH:MM (24-hour format) e.g. ['08:00', '20:00']",
    )
    patientTimezone: str = Field(
        default="Asia/Colombo",
        min_length=1,
        max_length=100,
        description="Patient time zone e.g. Asia/Colombo",
    )
    startDate: datetime = Field(..., description="Start date of medication schedule")
    endDate: datetime = Field(..., description="End date of medication schedule")
    enabled: bool = Field(default=True, description="Whether notifications are currently enabled")
    status: ReminderStatus = Field(default=ReminderStatus.ACTIVE)

    additionalInstructions: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Doctor's intake instructions e.g. Take after meals",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Patient personal organizational notes",
    )

    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("startDate", "endDate", "createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


class MedicationEventDocument(BaseModel):
    """MongoDB document representation for a single medication intake event (taken, skipped, snoozed)."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    eventId: str = Field(..., description="Unique event reference ID e.g. EVT-20261018-XXXX")
    reminderId: str = Field(..., description="References medication_reminders.reminderId")
    reminderDbId: str = Field(..., description="References medication_reminders._id")
    patientUserId: str = Field(..., description="References users._id of the patient")

    scheduledOccurrenceTime: datetime = Field(
        ...,
        description="The scheduled timestamp (UTC) for this dose occurrence",
    )
    status: EventStatus = Field(..., description="Event status: TAKEN, SKIPPED, SNOOZED")
    recordedAt: datetime = Field(default_factory=utc_now)
    snoozeMinutes: Optional[int] = Field(default=None, ge=1, le=120)
    notes: Optional[str] = Field(default=None, max_length=300)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("scheduledOccurrenceTime", "recordedAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


def get_medication_reminder_collection(db: Database) -> Collection:
    """Return MongoDB collection for medication reminders."""
    return db["medication_reminders"]


def get_medication_event_collection(db: Database) -> Collection:
    """Return MongoDB collection for medication intake events."""
    return db["medication_events"]


def create_medication_reminder_indexes(db: Database) -> None:
    """Create indexes for medication reminder schedules and tracking events."""
    reminder_coll = get_medication_reminder_collection(db)
    reminder_coll.create_index([("reminderId", ASCENDING)], unique=True, name="idx_reminder_ref_id")
    reminder_coll.create_index(
        [("patientUserId", ASCENDING), ("status", ASCENDING), ("enabled", ASCENDING)],
        name="idx_reminder_patient_status",
    )
    reminder_coll.create_index(
        [
            ("patientUserId", ASCENDING),
            ("prescriptionDbId", ASCENDING),
            ("prescriptionMedicationIndex", ASCENDING),
        ],
        name="idx_reminder_prescription_item",
    )

    event_coll = get_medication_event_collection(db)
    event_coll.create_index([("eventId", ASCENDING)], unique=True, name="idx_event_ref_id")
    # Compound unique index for idempotent occurrence updates per reminder and scheduled slot
    event_coll.create_index(
        [("reminderDbId", ASCENDING), ("scheduledOccurrenceTime", ASCENDING)],
        unique=True,
        name="idx_event_reminder_occurrence_unique",
    )
    event_coll.create_index(
        [("patientUserId", ASCENDING), ("scheduledOccurrenceTime", DESCENDING)],
        name="idx_event_patient_occurrence",
    )
