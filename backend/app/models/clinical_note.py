"""MongoDB document models and indexes for Doctor Clinical Documentation (SOAP Notes) (Phase 6).

Implements strict doctor note approval workflow:
DRAFT -> UNDER_REVIEW -> SIGNED -> AMENDED -> VOIDED

Enforces:
- Signed notes are immutable.
- Subsequent changes require an explicit amendment workflow with justification.
- Records doctor signature identity, timestamp, and SLMC number.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class NoteStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    SIGNED = "signed"
    AMENDED = "amended"
    VOIDED = "voided"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SoapContent(BaseModel):
    """Structured clinical documentation fields (SOAP)."""

    chiefComplaint: str = Field(..., min_length=2, max_length=500, description="Patient presenting complaint")
    historyOfPresentIllness: str = Field(..., min_length=2, max_length=3000, description="HPI narrative")
    pastMedicalHistory: Optional[str] = Field(default=None, max_length=2000, description="Relevant medical/surgical history")
    examinationFindings: str = Field(..., min_length=1, max_length=3000, description="Physical and systemic exam observations")
    assessment: str = Field(..., min_length=2, max_length=2000, description="Clinical evaluation / impression")
    plan: str = Field(..., min_length=2, max_length=3000, description="Management, diagnostic orders, and treatment plan")
    followUpInstructions: Optional[str] = Field(default=None, max_length=1000, description="Instructions and follow-up timing")


class NoteAmendment(BaseModel):
    """Immutable record of clinical note corrections or addendums."""

    amendedAt: datetime = Field(default_factory=utc_now)
    amendedByDoctorId: str = Field(..., description="Doctor who made the amendment")
    doctorName: str = Field(..., description="Doctor full name")
    justification: str = Field(..., min_length=5, max_length=1000, description="Clinical reason for amendment")
    previousAssessment: Optional[str] = None
    previousPlan: Optional[str] = None
    newAddendum: str = Field(..., min_length=2, max_length=3000, description="Additional clinical notes or corrections")


class ClinicalNoteDocument(BaseModel):
    """MongoDB document representation for a consultation clinical note."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    noteId: str = Field(..., description="Unique human-readable reference e.g. NOTE-20261124-XXXX")
    patientUserId: str = Field(..., description="References users._id of patient")
    doctorUserId: str = Field(..., description="References users._id of doctor")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    appointmentId: Optional[str] = Field(default=None, description="Optional references appointments._id")
    consultationSessionId: Optional[str] = Field(default=None, description="Optional references consultation_sessions._id")

    # Content
    content: SoapContent = Field(..., description="Structured SOAP documentation")

    # Workflow state
    status: NoteStatus = Field(default=NoteStatus.DRAFT)
    isAiDraft: bool = Field(default=False, description="Flag indicating note started as an AI-assisted draft")
    version: int = Field(default=1, ge=1)

    # Doctor Digital Signature
    signedAt: Optional[datetime] = None
    signedByDoctorId: Optional[str] = None
    signedDoctorName: Optional[str] = None
    slmcRegistrationNumber: Optional[str] = None

    # Versioning & Audit
    amendments: List[Dict[str, Any]] = Field(default_factory=list)
    auditLog: List[Dict[str, Any]] = Field(default_factory=list)

    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("signedAt", "createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


def get_clinical_note_collection(db: Database) -> Collection:
    return db["clinical_notes"]


def create_clinical_note_indexes(db: Database) -> None:
    coll = get_clinical_note_collection(db)
    coll.create_index([("noteId", ASCENDING)], unique=True, name="idx_clinical_note_id")
    coll.create_index(
        [("patientUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_clinical_note_patient_created",
    )
    coll.create_index(
        [("doctorUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_clinical_note_doctor_created",
    )
    coll.create_index(
        [("appointmentId", ASCENDING)],
        name="idx_clinical_note_appointment",
        sparse=True,
    )
