"""MongoDB document models and database indexes for Structured Digital Prescriptions (Phase 21)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class PrescriptionStatus(str, Enum):
    ISSUED = "ISSUED"
    CANCELLED = "CANCELLED"
    DISPENSED = "DISPENSED"
    AMENDED = "AMENDED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class MedicationItem(BaseModel):
    """Structured item inside a digital prescription."""

    medicationName: str = Field(..., min_length=1, max_length=200, description="Name of medicine/drug")
    strength: str = Field(..., min_length=1, max_length=100, description="e.g. 500mg, 10mg/5ml, 2% w/w")
    dose: str = Field(..., min_length=1, max_length=100, description="e.g. 1 tablet, 2 capsules, 5ml")
    route: str = Field(default="Oral", max_length=100, description="e.g. Oral, Topical, Inhalation, Intravenous")
    frequency: str = Field(..., min_length=1, max_length=100, description="e.g. Once daily, Twice daily (BD), TDS, PRN")
    duration: str = Field(..., min_length=1, max_length=100, description="e.g. 5 days, 2 weeks, 1 month")
    quantity: str = Field(..., min_length=1, max_length=100, description="e.g. 10 tablets, 1 bottle")
    additionalInstructions: Optional[str] = Field(default=None, max_length=500, description="e.g. Take after food with water")


class PrescriptionDocument(BaseModel):
    """MongoDB document representation for a digital prescription."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    prescriptionId: str = Field(..., description="Unique human-readable reference ID e.g. RX-20261018-XXXX")
    medicalRecordId: str = Field(..., description="References medical_records._id")
    appointmentId: str = Field(..., description="References appointments._id")
    patientUserId: str = Field(..., description="References users._id of the patient")
    doctorUserId: str = Field(..., description="References users._id of the doctor")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")

    issuedAt: datetime = Field(default_factory=utc_now)
    status: PrescriptionStatus = Field(default=PrescriptionStatus.ISSUED)
    medicationItems: List[MedicationItem] = Field(..., min_length=1, description="List of medications entered and verified by doctor")
    instructions: Optional[str] = Field(default=None, max_length=2000, description="General patient advice/instructions")

    amendmentHistory: List[Dict[str, Any]] = Field(default_factory=list, description="Audit trail of prescription adjustments")
    auditLog: List[Dict[str, Any]] = Field(default_factory=list, description="Access log for views and PDF downloads")

    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("issuedAt", "createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


def get_prescription_collection(db: Database) -> Collection:
    """Return MongoDB collection for digital prescriptions."""
    return db["prescriptions"]


def create_prescription_indexes(db: Database) -> None:
    """Create indexes for performance and reference uniqueness."""
    coll = get_prescription_collection(db)
    coll.create_index([("prescriptionId", ASCENDING)], unique=True, name="idx_prescription_ref_id")
    coll.create_index([("medicalRecordId", ASCENDING)], name="idx_prescription_record_id")
    coll.create_index([("appointmentId", ASCENDING)], name="idx_prescription_appointment_id")
    coll.create_index(
        [("patientUserId", ASCENDING), ("issuedAt", DESCENDING)],
        name="idx_prescription_patient_issued",
    )
    coll.create_index(
        [("doctorUserId", ASCENDING), ("issuedAt", DESCENDING)],
        name="idx_prescription_doctor_issued",
    )
