"""MongoDB document models and indexes for Longitudinal Patient Medical Records (Phase 6).

Supports 10 distinct record types:
- consultation_notes
- diagnoses
- prescriptions
- allergies
- laboratory_results
- imaging_reports
- discharge_summaries
- medical_documents
- care_plans
- medical_history

Enforces provenance, source distinction, versioning, and access auditing.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class RecordType(str, Enum):
    CONSULTATION_NOTE = "consultation_note"
    DIAGNOSIS = "diagnosis"
    PRESCRIPTION = "prescription"
    ALLERGY = "allergy"
    LABORATORY_RESULT = "laboratory_result"
    IMAGING_REPORT = "imaging_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    MEDICAL_DOCUMENT = "medical_document"
    CARE_PLAN = "care_plan"
    MEDICAL_HISTORY = "medical_history"


class SourceType(str, Enum):
    CLINICIAN_AUTHORED = "clinician_authored"
    PATIENT_UPLOADED = "patient_uploaded"
    IMPORTED = "imported"
    AI_GENERATED_DRAFT = "ai_generated_draft"


class RecordStatus(str, Enum):
    ACTIVE = "active"
    AMENDED = "amended"
    ARCHIVED = "archived"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentMetadata(BaseModel):
    """Secure metadata for uploaded clinical files (PDF, JPG, PNG)."""

    fileKey: str = Field(..., description="Internal randomized storage object key")
    fileName: str = Field(..., description="Sanitized original file name")
    fileSize: int = Field(..., description="File size in bytes")
    mimeType: str = Field(..., description="MIME content type (e.g. application/pdf, image/png)")
    fileHash: str = Field(..., description="SHA-256 integrity hash of document content")
    uploadedAt: datetime = Field(default_factory=utc_now)


class PatientMedicalRecordDocument(BaseModel):
    """MongoDB document representation for a longitudinal patient medical record."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    recordId: str = Field(..., description="Unique human-readable reference e.g. MED-20261124-XXXX")
    patientUserId: str = Field(..., description="References users._id of patient")
    recordType: RecordType = Field(..., description="Classification category of the clinical record")
    sourceType: SourceType = Field(..., description="Provenance source of the medical record")
    authorId: str = Field(..., description="User ID of author or uploader")
    authorRole: str = Field(..., description="Role of author: PATIENT, DOCTOR, SYSTEM")
    authorName: Optional[str] = Field(default=None, description="Display name of author")

    title: str = Field(..., min_length=2, max_length=200, description="Record title or report name")
    description: Optional[str] = Field(default=None, max_length=2000, description="Clinical summary or observations")
    clinicalDate: str = Field(..., description="Effective clinical observation date YYYY-MM-DD")

    clinicalData: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured clinical values, e.g. findings, lab values, allergen, severity",
    )
    documentMetadata: Optional[DocumentMetadata] = Field(
        default=None,
        description="Optional attachment metadata for stored files",
    )

    status: RecordStatus = Field(default=RecordStatus.ACTIVE)
    version: int = Field(default=1, ge=1)
    isAiGenerated: bool = Field(default=False)
    amendmentHistory: List[Dict[str, Any]] = Field(default_factory=list)
    auditLog: List[Dict[str, Any]] = Field(default_factory=list)

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


def get_patient_medical_record_collection(db: Database) -> Collection:
    return db["patient_medical_records"]


def create_patient_medical_record_indexes(db: Database) -> None:
    coll = get_patient_medical_record_collection(db)
    coll.create_index([("recordId", ASCENDING)], unique=True, name="idx_pmr_record_id")
    coll.create_index(
        [("patientUserId", ASCENDING), ("clinicalDate", DESCENDING)],
        name="idx_pmr_patient_clinical_date",
    )
    coll.create_index(
        [("patientUserId", ASCENDING), ("recordType", ASCENDING)],
        name="idx_pmr_patient_record_type",
    )
    coll.create_index(
        [("authorId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_pmr_author_created",
    )
