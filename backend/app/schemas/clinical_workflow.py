"""Pydantic schemas for Advanced Healthcare AI, Medical Records & Clinical Automation (Phase 6)."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


# ---------------------------------------------------------------------------
# Medical Records Schemas
# ---------------------------------------------------------------------------

class CreatePatientMedicalRecordRequest(StrictBase):
    recordType: str = Field(..., description="RecordType enum value")
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    clinicalDate: str = Field(..., description="Date YYYY-MM-DD")
    clinicalData: Dict[str, Any] = Field(default_factory=dict)
    patientUserId: Optional[str] = Field(default=None, description="Only authorized doctors or admins can specify another patient")


class DocumentDownloadTokenResponse(StrictBase):
    recordId: str
    fileName: str
    mimeType: str
    fileSize: int
    downloadUrl: str
    expiresAt: datetime


class PatientMedicalRecordResponse(StrictBase):
    id: Optional[str] = None
    recordId: str
    patientUserId: str
    recordType: str
    sourceType: str
    authorId: str
    authorRole: str
    authorName: Optional[str] = None
    title: str
    description: Optional[str] = None
    clinicalDate: str
    clinicalData: Dict[str, Any] = Field(default_factory=dict)
    hasAttachment: bool = False
    attachmentName: Optional[str] = None
    attachmentSize: Optional[int] = None
    attachmentMimeType: Optional[str] = None
    status: str
    version: int
    isAiGenerated: bool = False
    createdAt: datetime
    updatedAt: datetime


class PatientMedicalRecordListResponse(StrictBase):
    records: List[PatientMedicalRecordResponse]
    # Phase 05 (P4-O1): records that exist but could not be displayed, by reference.
    unreadableRecords: int = 0
    unreadableRecordRefs: List[str] = Field(default_factory=list)
    total: int
    page: int
    pageSize: int


class MedicalRecordSummaryResponse(StrictBase):
    patientUserId: str
    recordsAnalyzed: int
    dateRange: Dict[str, Optional[str]]
    summary: str
    diagnoses: List[str] = Field(default_factory=list)
    activeMedications: List[str] = Field(default_factory=list)
    documentedAllergies: List[str] = Field(default_factory=list)
    keyClinicalFindings: List[str] = Field(default_factory=list)
    missingInformationNotice: Optional[str] = None
    aiDisclaimer: str


# ---------------------------------------------------------------------------
# Clinical Documentation (SOAP Notes) Schemas
# ---------------------------------------------------------------------------

class SoapContentSchema(StrictBase):
    chiefComplaint: str = Field(..., min_length=2, max_length=500)
    historyOfPresentIllness: str = Field(..., min_length=2, max_length=3000)
    pastMedicalHistory: Optional[str] = Field(default=None, max_length=2000)
    examinationFindings: str = Field(..., min_length=1, max_length=3000)
    assessment: str = Field(..., min_length=2, max_length=2000)
    plan: str = Field(..., min_length=2, max_length=3000)
    followUpInstructions: Optional[str] = Field(default=None, max_length=1000)


class CreateClinicalNoteDraftRequest(StrictBase):
    patientUserId: str
    appointmentId: Optional[str] = None
    consultationSessionId: Optional[str] = None
    rawNotes: Optional[str] = Field(default=None, max_length=10000, description="Doctor-provided raw notes for AI SOAP formatting")
    content: Optional[SoapContentSchema] = None


class UpdateClinicalNoteDraftRequest(StrictBase):
    content: SoapContentSchema


class SignClinicalNoteRequest(StrictBase):
    confirmSign: Literal[True] = Field(..., description="Doctor explicit confirmation to sign note")


class AmendClinicalNoteRequest(StrictBase):
    justification: str = Field(..., min_length=5, max_length=1000)
    addendum: str = Field(..., min_length=2, max_length=3000)


class ClinicalNoteResponse(StrictBase):
    id: Optional[str] = None
    noteId: str
    patientUserId: str
    patientName: Optional[str] = None
    doctorUserId: str
    doctorName: Optional[str] = None
    doctorSpecialty: Optional[str] = None
    slmcRegistrationNumber: Optional[str] = None
    appointmentId: Optional[str] = None
    consultationSessionId: Optional[str] = None
    content: SoapContentSchema
    status: str
    isAiDraft: bool
    version: int
    signedAt: Optional[datetime] = None
    amendments: List[Dict[str, Any]] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime


class ClinicalNoteListResponse(StrictBase):
    notes: List[ClinicalNoteResponse]
    total: int


# ---------------------------------------------------------------------------
# Prescription Schemas & Assistant
# ---------------------------------------------------------------------------

def reject_repeated_medicines(items: List[Any]) -> List[Any]:
    """A04-BUG-002: the same medicine listed twice in one prescription gives two conflicting sets of instructions."""
    seen = set()
    for item in items:
        name = " ".join(str(getattr(item, "medicationName", "")).split()).casefold()
        if name in seen:
            raise ValueError(f"'{item.medicationName}' is listed more than once. Combine it into one medication item.")
        seen.add(name)
    return items


class PrescriptionMedicationDraftItem(StrictBase):
    # A04-BUG-001: whitespace-only values ("   ") passed min_length here (the P03-N13 fix covered only the older
    # schema) and then failed inside the service as an unhandled validation error (HTTP 500).
    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    medicationName: str = Field(..., min_length=1, max_length=200)
    strength: str = Field(..., min_length=1, max_length=100)
    dose: str = Field(..., min_length=1, max_length=100)
    route: str = Field(default="Oral", max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
    duration: str = Field(..., min_length=1, max_length=100)
    quantity: str = Field(..., min_length=1, max_length=100)
    additionalInstructions: Optional[str] = Field(default=None, max_length=500)


class CreatePrescriptionDraftRequest(StrictBase):
    patientUserId: str
    appointmentId: Optional[str] = None
    medicationItems: List[PrescriptionMedicationDraftItem]
    instructions: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("medicationItems")
    @classmethod
    def _no_repeats(cls, value):
        return reject_repeated_medicines(value)


class SignPrescriptionRequest(StrictBase):
    confirmSign: Literal[True]


INTERACTION_CHECK_NOTICE = (
    "Drug-interaction checking is not available: MediConnect has no clinically validated interaction source. "
    "No interaction result is implied. Check interactions with a pharmacist or a validated reference before signing."
)


class PrescriptionAssistantReviewResponse(StrictBase):
    patientUserId: str
    documentedAllergies: List[str]
    activeMedications: List[str]
    potentialDuplicates: List[str]
    # A04-BUG-004: the allergy match was computed by the safety service but this response had no field for it,
    # so a doctor never saw "POSSIBLE ALLERGY CONTRAINDICATION".
    allergyWarnings: List[str] = Field(default_factory=list)
    missingFieldsWarnings: List[str]
    interactionCheck: Literal["unavailable"] = "unavailable"
    interactionCheckNotice: str = INTERACTION_CHECK_NOTICE
    safetyGuidance: str


class DraftReviewItem(StrictBase):
    """A clinician-entered item as typed so far: every field may still be empty."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    medicationName: str = Field(default="", max_length=200)
    strength: str = Field(default="", max_length=100)
    dose: str = Field(default="", max_length=100)
    route: str = Field(default="", max_length=100)
    frequency: str = Field(default="", max_length=100)
    duration: str = Field(default="", max_length=100)
    quantity: str = Field(default="", max_length=100)
    additionalInstructions: Optional[str] = Field(default=None, max_length=500)


class PrescriptionDraftReviewRequest(StrictBase):
    patientUserId: str = Field(..., min_length=1, max_length=64)
    medicationItems: List[DraftReviewItem] = Field(..., min_length=1, max_length=20)


class DraftItemFinding(StrictBase):
    index: int
    medicationName: str
    missingFields: List[str]
    notes: List[str]


class PrescriptionDraftReviewResponse(PrescriptionAssistantReviewResponse):
    """Structured check of a draft. Nothing is stored or signed; the items are returned exactly as entered."""
    status: Literal["unapproved_draft"] = "unapproved_draft"
    approved: Literal[False] = False
    readyToSign: bool
    items: List[DraftItemFinding]
    repeatedMedicines: List[str]
    draft: List[DraftReviewItem]
    source: Literal["deterministic"] = "deterministic"


# ---------------------------------------------------------------------------
# Prescription Renewal Schemas
# ---------------------------------------------------------------------------

class CreatePrescriptionRenewalRequest(StrictBase):
    originalPrescriptionId: str = Field(..., description="Reference to existing prescription")
    medicationName: str = Field(..., min_length=1, max_length=200)
    patientReason: Optional[str] = Field(default=None, max_length=1000)


class ReviewPrescriptionRenewalRequest(StrictBase):
    decision: Literal["approve", "reject", "needs_consultation"]
    reason: str = Field(..., min_length=3, max_length=1000)
    consultationDetails: Optional[str] = Field(default=None, max_length=1000)
    adjustedDuration: Optional[str] = Field(default=None, max_length=100)


class PrescriptionRenewalResponse(StrictBase):
    id: Optional[str] = None
    renewalId: str
    patientUserId: str
    patientName: Optional[str] = None
    originalPrescriptionId: str
    medicationName: str
    medicationDetails: Dict[str, Any] = Field(default_factory=dict)
    doctorUserId: str
    doctorName: Optional[str] = None
    status: str
    patientReason: Optional[str] = None
    doctorDecisionReason: Optional[str] = None
    consultationDetails: Optional[str] = None
    resultingPrescriptionId: Optional[str] = None
    requestedAt: datetime
    reviewedAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime


class PrescriptionRenewalListResponse(StrictBase):
    renewals: List[PrescriptionRenewalResponse]
    total: int


# ---------------------------------------------------------------------------
# Health Measurement Schemas
# ---------------------------------------------------------------------------

class RecordHealthMeasurementRequest(StrictBase):
    metric: str = Field(..., description="MeasurementMetric value")
    value: float = Field(..., description="Measurement reading")
    secondary: Optional[float] = Field(default=None, description="Diastolic reading for blood pressure")
    unit: Optional[str] = Field(default=None, description="Optional unit override; defaults to standardized unit")
    source: Optional[str] = Field(default="patient_reported", description="patient_reported or device_reported")
    notes: Optional[str] = Field(default=None, max_length=500)
    measuredAt: Optional[datetime] = None


class CorrectHealthMeasurementRequest(StrictBase):
    newValue: float
    newSecondary: Optional[float] = None
    reason: str = Field(..., min_length=3, max_length=500)


class HealthMeasurementResponse(StrictBase):
    id: Optional[str] = None
    measurementId: str
    patientUserId: str
    metric: str
    value: float
    secondary: Optional[float] = None
    unit: str
    source: str
    verificationStatus: str
    notes: Optional[str] = None
    criticalAlert: Optional[str] = None
    measuredAt: datetime
    recordedAt: datetime


class HealthMeasurementListResponse(StrictBase):
    items: List[HealthMeasurementResponse]
    total: int


class MetricTrendSummary(StrictBase):
    metric: str
    unit: str
    count: int
    latestValue: Optional[float] = None
    latestSecondary: Optional[float] = None
    latestDate: Optional[datetime] = None
    sevenDayAverage: Optional[float] = None
    thirtyDayAverage: Optional[float] = None
    minValue: Optional[float] = None
    maxValue: Optional[float] = None
    trendDirection: Literal["RISING", "FALLING", "STABLE", "INSUFFICIENT_DATA"]
    clinicalNotice: Optional[str] = None


class HealthTrendsResponse(StrictBase):
    patientUserId: str
    trends: List[MetricTrendSummary]
    criticalAlerts: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# AI Clinical Assistant Chat Schemas
# ---------------------------------------------------------------------------

class ClinicalAIChatRequest(StrictBase):
    message: str = Field(..., min_length=1, max_length=1000)
    patientUserId: Optional[str] = Field(default=None, description="Required for doctor query context; implicit for patients")


class ClinicalAIChatResponse(StrictBase):
    query: str
    intent: str
    response: str
    structuredData: Optional[Dict[str, Any]] = None
    requiresDoctorAction: bool = False
    emergencyEscalation: bool = False
    aiDisclaimer: str
