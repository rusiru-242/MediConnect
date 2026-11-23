"""MongoDB document models and database indexes for Patient Medical Consultation Records (Phase 21)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class MedicalRecordStatus(str, Enum):
    ACTIVE = "ACTIVE"
    AMENDED = "AMENDED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class MedicalRecordDocument(BaseModel):
    """MongoDB document representation for a consultation medical record."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    recordId: str = Field(..., description="Unique human-readable reference ID e.g. REC-20261018-XXXX")
    patientUserId: str = Field(..., description="References users._id of the patient")
    doctorUserId: str = Field(..., description="References users._id of the doctor")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    appointmentId: str = Field(..., description="References appointments._id")

    consultationDate: str = Field(..., description="Consultation date in YYYY-MM-DD")
    clinicalNotes: str = Field(..., min_length=1, max_length=5000, description="Symptoms, physical observations")
    assessment: str = Field(..., min_length=1, max_length=2000, description="Clinical evaluation / impression")
    treatmentPlan: str = Field(..., min_length=1, max_length=5000, description="Management plan and non-pharmacological care")
    followUpInstructions: Optional[str] = Field(default=None, max_length=2000, description="Post-consultation instructions")

    status: MedicalRecordStatus = Field(default=MedicalRecordStatus.ACTIVE)
    amendmentHistory: List[Dict[str, Any]] = Field(default_factory=list, description="Controlled audit trail of modifications")
    auditLog: List[Dict[str, Any]] = Field(default_factory=list, description="Access log for views and operations")

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


def get_medical_record_collection(db: Database) -> Collection:
    """Return MongoDB collection for medical records."""
    return db["medical_records"]


def create_medical_record_indexes(db: Database) -> None:
    """Create indexes for performance and ownership constraints."""
    coll = get_medical_record_collection(db)
    coll.create_index([("recordId", ASCENDING)], unique=True, name="idx_medical_record_record_id")
    coll.create_index([("appointmentId", ASCENDING)], unique=True, name="idx_medical_record_appointment_id")
    coll.create_index(
        [("patientUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_medical_record_patient_created",
    )
    coll.create_index(
        [("doctorUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_medical_record_doctor_created",
    )
