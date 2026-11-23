"""MongoDB document models and indexes for Patient Prescription Renewal Requests (Phase 6).

Implements prescription renewal workflow:
REQUESTED -> AWAITING_REVIEW -> (APPROVED | REJECTED | NEEDS_CONSULTATION | CANCELLED)

Enforces:
- Patients can request renewal of active or previous prescriptions.
- AI never independently approves or signs a renewal.
- Only authorized doctors can approve, reject, or request a follow-up consultation.
- Approved renewals generate a valid doctor-signed prescription and sync to medication reminders.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class RenewalStatus(str, Enum):
    REQUESTED = "requested"
    AWAITING_REVIEW = "awaiting_review"
    NEEDS_CONSULTATION = "needs_consultation"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PrescriptionRenewalDocument(BaseModel):
    """MongoDB document representation for a prescription renewal request."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    renewalId: str = Field(..., description="Unique human-readable reference e.g. REN-20261124-XXXX")
    patientUserId: str = Field(..., description="References users._id of requesting patient")
    originalPrescriptionId: str = Field(..., description="References prescriptions.prescriptionId or _id")

    medicationName: str = Field(..., min_length=1, max_length=200, description="Name of medication to renew")
    medicationDetails: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured medication item details (strength, dose, frequency, duration)",
    )

    doctorUserId: str = Field(..., description="Assigned doctor userId for review")
    doctorProfileId: Optional[str] = Field(default=None, description="References doctor_profiles._id")

    status: RenewalStatus = Field(default=RenewalStatus.REQUESTED)
    patientReason: Optional[str] = Field(default=None, max_length=1000, description="Patient's stated reason for renewal")

    # Doctor review decisions
    doctorDecisionReason: Optional[str] = Field(default=None, max_length=1000, description="Doctor justification for decision")
    consultationDetails: Optional[str] = Field(default=None, max_length=1000, description="Notes if doctor requests follow-up consultation")
    resultingPrescriptionId: Optional[str] = Field(default=None, description="References new prescription if approved")

    requestedAt: datetime = Field(default_factory=utc_now)
    reviewedAt: Optional[datetime] = None
    reviewedByDoctorId: Optional[str] = None
    reviewedByDoctorName: Optional[str] = None

    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("requestedAt", "reviewedAt", "createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


def get_prescription_renewal_collection(db: Database) -> Collection:
    return db["prescription_renewals"]


def create_prescription_renewal_indexes(db: Database) -> None:
    coll = get_prescription_renewal_collection(db)
    coll.create_index([("renewalId", ASCENDING)], unique=True, name="idx_renewal_id")
    coll.create_index(
        [("patientUserId", ASCENDING), ("requestedAt", DESCENDING)],
        name="idx_renewal_patient_requested",
    )
    coll.create_index(
        [("doctorUserId", ASCENDING), ("status", ASCENDING), ("requestedAt", DESCENDING)],
        name="idx_renewal_doctor_status",
    )
    coll.create_index(
        [("originalPrescriptionId", ASCENDING)],
        name="idx_renewal_orig_prescription",
    )
