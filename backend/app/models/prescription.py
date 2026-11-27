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


# A04-BUG-007: an amended or dispensed prescription is still the patient's current prescription. Several readers
# (AI tools, the allergy/duplicate check) only looked at ISSUED and missed it. "ACTIVE"/"signed" are legacy values.
CURRENT_PRESCRIPTION_STATUSES = ("ISSUED", "AMENDED", "DISPENSED", "ACTIVE", "signed")


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def submission_key(doctor_id: str, patient_id: str, visit_ref: Optional[str], items: List[Dict[str, Any]]) -> str:
    """Stable key of one prescription submission: same doctor, patient, visit and medication items."""
    import hashlib
    import json
    canonical = json.dumps([doctor_id, patient_id, visit_ref or "", items], sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def claim_submission(db: Database, key: str, window_minutes: int = 10) -> bool:
    """Atomically claim a submission key across processes (A04-BUG-003).

    The duplicate checks read and then insert, so simultaneous identical submissions all passed the read. The claim
    is a document whose ``_id`` is the key: the first request inserts it, an identical request within the window hits
    the unique ``_id`` and is refused. An older claim is taken over (a deliberate re-issue later is allowed).
    Returns False when another request holds the claim.
    """
    from datetime import timedelta
    from pymongo.errors import DuplicateKeyError
    now = utc_now()
    try:
        db["prescription_submission_claims"].find_one_and_update(
            {"_id": key, "claimedAt": {"$lt": now - timedelta(minutes=window_minutes)}},
            {"$set": {"claimedAt": now}}, upsert=True,
        )
        return True
    except DuplicateKeyError:
        return False


def release_submission(db: Database, key: str) -> None:
    """Release a claim whose prescription was not stored, so a corrected retry is not refused."""
    db["prescription_submission_claims"].delete_one({"_id": key})


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
    # Optional: a prescription signed outside a documented consultation has no record or visit to reference.
    # Never fill these with generated ids (P03-N07): a reference must point at a real record.
    medicalRecordId: Optional[str] = Field(default=None, description="References medical_records._id")
    appointmentId: Optional[str] = Field(default=None, description="References appointments._id")
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
    claims = db["prescription_submission_claims"]
    claims.create_index([("claimedAt", ASCENDING)], expireAfterSeconds=24 * 3600, name="idx_rx_claim_ttl")
