"""FastAPI router for Advanced Healthcare AI, Medical Records & Clinical Automation (Phase 6)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, require_doctor, require_patient
from app.schemas.clinical_workflow import (
    AmendClinicalNoteRequest,
    ClinicalAIChatRequest,
    ClinicalAIChatResponse,
    ClinicalNoteListResponse,
    ClinicalNoteResponse,
    CorrectHealthMeasurementRequest,
    CreateClinicalNoteDraftRequest,
    CreatePatientMedicalRecordRequest,
    CreatePrescriptionDraftRequest,
    CreatePrescriptionRenewalRequest,
    HealthMeasurementListResponse,
    HealthMeasurementResponse,
    HealthTrendsResponse,
    MedicalRecordSummaryResponse,
    PatientMedicalRecordListResponse,
    PatientMedicalRecordResponse,
    PrescriptionAssistantReviewResponse,
    PrescriptionRenewalListResponse,
    PrescriptionRenewalResponse,
    RecordHealthMeasurementRequest,
    ReviewPrescriptionRenewalRequest,
    SignClinicalNoteRequest,
    UpdateClinicalNoteDraftRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.clinical_documentation_service import ClinicalDocumentationService
from app.services.health_tracking_service import HealthTrackingService
from app.services.patient_medical_record_service import PatientMedicalRecordService
from app.services.prescription_workflow_service import PrescriptionWorkflowService

clinical_workflow_router = APIRouter(prefix="/clinical", tags=["Clinical Workflow"])


# ===========================================================================
# 1. Longitudinal Medical Records & Secure Document Upload
# ===========================================================================

@clinical_workflow_router.post(
    "/records/documents/upload",
    response_model=PatientMedicalRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload private medical document (PDF, JPG, PNG)",
)
async def upload_medical_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    recordType: str = Form(...),
    clinicalDate: str = Form(...),
    description: Optional[str] = Form(None),
    targetPatientId: Optional[str] = Form(None),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> PatientMedicalRecordResponse:
    """Securely store clinical document with magic-byte verification, hashing, and access controls."""
    return await PatientMedicalRecordService.upload_medical_document(
        db=db,
        current_user=current_user,
        file=file,
        title=title,
        record_type=recordType,
        clinical_date=clinicalDate,
        description=description,
        target_patient_id=targetPatientId,
    )


@clinical_workflow_router.post(
    "/records",
    response_model=PatientMedicalRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create structured medical record entry (diagnosis, allergy, etc.)",
)
def create_medical_record_entry(
    req: CreatePatientMedicalRecordRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> PatientMedicalRecordResponse:
    """Create a structured patient medical record without file attachment."""
    return PatientMedicalRecordService.create_medical_record(
        db=db, current_user=current_user, req=req
    )


@clinical_workflow_router.get(
    "/records",
    response_model=PatientMedicalRecordListResponse,
    summary="List patient medical records with access control and pagination",
)
def list_medical_records(
    patientId: Optional[str] = Query(default=None),
    recordType: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> PatientMedicalRecordListResponse:
    """Retrieve authorized medical records."""
    return PatientMedicalRecordService.list_medical_records(
        db=db,
        current_user=current_user,
        patient_id=patientId,
        record_type=recordType,
        page=page,
        page_size=pageSize,
    )


@clinical_workflow_router.get(
    "/records/summary",
    response_model=MedicalRecordSummaryResponse,
    summary="Get source-grounded longitudinal medical record summary",
)
def get_medical_record_summary(
    patientId: Optional[str] = Query(default=None),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> MedicalRecordSummaryResponse:
    """Produce an authorized, grounded clinical summary with citations and disclaimers."""
    return PatientMedicalRecordService.summarize_patient_history(
        db=db, current_user=current_user, patient_id=patientId
    )


@clinical_workflow_router.get(
    "/records/{record_id}",
    response_model=PatientMedicalRecordResponse,
    summary="Get details of a specific medical record",
)
def get_medical_record_detail(
    record_id: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> PatientMedicalRecordResponse:
    """Retrieve record with access enforcement and view audit logging."""
    return PatientMedicalRecordService.get_medical_record(
        db=db, current_user=current_user, record_id=record_id
    )


@clinical_workflow_router.get(
    "/records/{record_id}/download",
    summary="Securely stream document file to authorized patient or doctor",
)
def download_medical_document(
    record_id: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> FileResponse:
    """Stream private document file with authorization checks and access auditing."""
    return PatientMedicalRecordService.stream_document_file(
        db=db, current_user=current_user, record_id=record_id
    )


# ===========================================================================
# 2. Clinical Documentation (SOAP Notes) & Signature Workflow
# ===========================================================================

@clinical_workflow_router.post(
    "/notes/draft",
    response_model=ClinicalNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or organize clinical SOAP note draft (Doctor only)",
)
def create_clinical_note_draft(
    req: CreateClinicalNoteDraftRequest,
    doctor_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> ClinicalNoteResponse:
    """Create a draft clinical note. Drafts are not officially signed records until confirmed."""
    return ClinicalDocumentationService.create_note_draft(
        db=db, doctor_user=doctor_user, req=req
    )


@clinical_workflow_router.put(
    "/notes/{note_id}/draft",
    response_model=ClinicalNoteResponse,
    summary="Edit an unsigned clinical note draft (Doctor only)",
)
def update_clinical_note_draft(
    note_id: str,
    req: UpdateClinicalNoteDraftRequest,
    doctor_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> ClinicalNoteResponse:
    """Update draft clinical note before digital signature."""
    return ClinicalDocumentationService.update_note_draft(
        db=db, doctor_user=doctor_user, note_id=note_id, req=req
    )


@clinical_workflow_router.post(
    "/notes/{note_id}/sign",
    response_model=ClinicalNoteResponse,
    summary="Authorize and digitally sign clinical note (Doctor only)",
)
def sign_clinical_note(
    note_id: str,
    req: SignClinicalNoteRequest,
    doctor_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> ClinicalNoteResponse:
    """Doctor explicitly reviews and signs clinical note. Once signed, notes are immutable."""
    return ClinicalDocumentationService.sign_clinical_note(
        db=db, doctor_user=doctor_user, note_id=note_id
    )


@clinical_workflow_router.post(
    "/notes/{note_id}/amend",
    response_model=ClinicalNoteResponse,
    summary="Amend signed clinical note with justification (Doctor only)",
)
def amend_clinical_note(
    note_id: str,
    req: AmendClinicalNoteRequest,
    doctor_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> ClinicalNoteResponse:
    """Append a controlled amendment to a previously signed note with clinical justification."""
    return ClinicalDocumentationService.amend_clinical_note(
        db=db, doctor_user=doctor_user, note_id=note_id, req=req
    )


@clinical_workflow_router.get(
    "/notes",
    response_model=ClinicalNoteListResponse,
    summary="List clinical notes for patient or doctor",
)
def list_clinical_notes(
    patientId: Optional[str] = Query(default=None),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> ClinicalNoteListResponse:
    """Retrieve clinical notes with role and care-relationship enforcement."""
    return ClinicalDocumentationService.list_notes(
        db=db, current_user=current_user, patient_id=patientId
    )


# ===========================================================================
# 3. Prescriptions & Prescription Renewal Workflow
# ===========================================================================

@clinical_workflow_router.post(
    "/prescriptions/assistant-review",
    response_model=PrescriptionAssistantReviewResponse,
    summary="Review draft prescription items against allergies and active meds (Doctor only)",
)
def review_prescription_assistant(
    patientUserId: str = Query(...),
    medications: List[str] = Query(...),
    doctor_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> PrescriptionAssistantReviewResponse:
    """Check proposed medications for duplicate active prescriptions and allergy conflicts."""
    return PrescriptionWorkflowService.review_prescription_draft(
        db=db,
        doctor_user=doctor_user,
        patient_user_id=patientUserId,
        medication_names=medications,
    )


@clinical_workflow_router.post(
    "/prescriptions/sign",
    status_code=status.HTTP_201_CREATED,
    summary="Authorize and issue digital prescription (Doctor only)",
)
def sign_and_issue_prescription(
    req: CreatePrescriptionDraftRequest,
    doctor_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
):
    """Doctor explicitly signs prescription and schedules Phase 3 medication reminders."""
    return PrescriptionWorkflowService.sign_prescription(
        db=db, doctor_user=doctor_user, req=req
    )


@clinical_workflow_router.post(
    "/prescriptions/renewals",
    response_model=PrescriptionRenewalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request renewal of an existing prescription (Patient only)",
)
def request_prescription_renewal(
    req: CreatePrescriptionRenewalRequest,
    patient_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> PrescriptionRenewalResponse:
    """Patient creates a renewal request. The AI assistant does not autonomously authorize renewals."""
    return PrescriptionWorkflowService.request_prescription_renewal(
        db=db, patient_user=patient_user, req=req
    )


@clinical_workflow_router.get(
    "/prescriptions/renewals",
    response_model=PrescriptionRenewalListResponse,
    summary="List prescription renewal requests",
)
def list_prescription_renewals(
    statusFilter: Optional[str] = Query(default=None),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> PrescriptionRenewalListResponse:
    """List renewal queue for assigned doctor or patient."""
    return PrescriptionWorkflowService.list_renewal_requests(
        db=db, current_user=current_user, status_filter=statusFilter
    )


@clinical_workflow_router.post(
    "/prescriptions/renewals/{renewal_id}/review",
    response_model=PrescriptionRenewalResponse,
    summary="Doctor review decision on renewal request (Doctor only)",
)
def review_prescription_renewal(
    renewal_id: str,
    req: ReviewPrescriptionRenewalRequest,
    doctor_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> PrescriptionRenewalResponse:
    """Doctor authorizes, rejects, or requests consultation for a prescription renewal."""
    return PrescriptionWorkflowService.review_renewal_request(
        db=db, doctor_user=doctor_user, renewal_id=renewal_id, req=req
    )


# ===========================================================================
# 4. Advanced Health Tracking & Vitals Analytics
# ===========================================================================

@clinical_workflow_router.post(
    "/measurements",
    response_model=HealthMeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record health measurement with physiologic range validation",
)
def record_health_measurement(
    req: RecordHealthMeasurementRequest,
    targetPatientId: Optional[str] = Query(default=None),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> HealthMeasurementResponse:
    """Validate and record blood pressure, glucose, weight, temp, heart rate, or SpO2."""
    return HealthTrackingService.record_measurement(
        db=db, current_user=current_user, req=req, target_patient_id=targetPatientId
    )


@clinical_workflow_router.patch(
    "/measurements/{measurement_id}/correct",
    response_model=HealthMeasurementResponse,
    summary="Correct an erroneous measurement with an immutable audit trail",
)
def correct_health_measurement(
    measurement_id: str,
    req: CorrectHealthMeasurementRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> HealthMeasurementResponse:
    """Record auditable correction to a measurement."""
    return HealthTrackingService.correct_measurement(
        db=db, current_user=current_user, measurement_id=measurement_id, req=req
    )


@clinical_workflow_router.get(
    "/measurements",
    response_model=HealthMeasurementListResponse,
    summary="List patient measurements with date filtering",
)
def list_health_measurements(
    patientId: Optional[str] = Query(default=None),
    metric: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> HealthMeasurementListResponse:
    """Retrieve patient measurements."""
    return HealthTrackingService.list_measurements(
        db=db, current_user=current_user, patient_id=patientId, metric=metric, limit=limit
    )


@clinical_workflow_router.get(
    "/measurements/trends",
    response_model=HealthTrendsResponse,
    summary="Get deterministic 7-day, 30-day averages, trends, and safety alerts",
)
def get_health_measurement_trends(
    patientId: Optional[str] = Query(default=None),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> HealthTrendsResponse:
    """Calculate deterministic trend analytics across all 6 physiologic metrics."""
    return HealthTrackingService.calculate_health_trends(
        db=db, current_user=current_user, patient_id=patientId
    )


# ===========================================================================
# 5. AI Clinical Assistant Chat (English & Romanized Sinhala)
# ===========================================================================

@clinical_workflow_router.post(
    "/ai-assistant/chat",
    response_model=ClinicalAIChatResponse,
    summary="Query AI clinical assistant (English & Romanized Sinhala supported)",
)
def chat_clinical_ai_assistant(
    req: ClinicalAIChatRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> ClinicalAIChatResponse:
    """Handle conversational inquiries regarding medical records, vitals, or renewals."""
    result = HealthTrackingService.answer_health_query(
        db=db, current_user=current_user, query=req.message, patient_id=req.patientUserId
    )
    return ClinicalAIChatResponse(
        query=result["query"],
        intent=result["intent"],
        response=result["response"],
        structuredData=result.get("structuredData"),
        requiresDoctorAction=result.get("requiresDoctorAction", False),
        emergencyEscalation=result.get("emergencyEscalation", False),
        aiDisclaimer=result.get("aiDisclaimer", "Assistive healthcare notice."),
    )
