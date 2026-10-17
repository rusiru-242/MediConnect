"""FastAPI route endpoints for Digital Prescriptions and Secure PDF Generation (Phase 21)."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, require_doctor
from app.models.user import UserRole
from app.schemas.prescription import (
    AmendPrescriptionRequest,
    CreatePrescriptionRequest,
    PrescriptionListResponse,
    PrescriptionResponseSchema,
)
from app.schemas.user import UserResponseSchema
from app.services.medical_record_service import MedicalRecordService

prescription_router = APIRouter(prefix="/prescriptions", tags=["Digital Prescriptions"])


@prescription_router.post(
    "",
    response_model=PrescriptionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Issue digital prescription",
    description="Allows approved doctors to issue an official structured digital prescription linked to a consultation record.",
)
async def create_prescription(
    req: CreatePrescriptionRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> PrescriptionResponseSchema:
    """Issue a digital prescription for a patient consultation."""
    return await MedicalRecordService.create_prescription(
        db=db, doctor_user=current_user, req=req
    )


@prescription_router.get(
    "/me",
    response_model=PrescriptionListResponse,
    summary="List my digital prescriptions",
    description="Returns prescriptions for the authenticated patient or doctor with pagination.",
)
async def list_my_prescriptions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    appointment_id: Optional[str] = Query(default=None),
    patient_id: Optional[str] = Query(default=None),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> PrescriptionListResponse:
    """List authenticated user's digital prescriptions."""
    if current_user.role == UserRole.DOCTOR.value:
        return await MedicalRecordService.list_doctor_prescriptions(
            db=db,
            doctor_user=current_user,
            appointment_id=appointment_id,
            patient_id=patient_id,
            page=page,
            page_size=page_size,
        )
    return await MedicalRecordService.list_patient_prescriptions(
        db=db, patient_user=current_user, page=page, page_size=page_size
    )


@prescription_router.get(
    "/{prescription_id}",
    response_model=PrescriptionResponseSchema,
    summary="Get digital prescription details",
    description="Retrieves a specific prescription with ownership verification and access logging.",
)
async def get_prescription(
    prescription_id: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> PrescriptionResponseSchema:
    """Retrieve digital prescription by ID."""
    return await MedicalRecordService.get_prescription(
        db=db, current_user=current_user, prescription_id=prescription_id
    )


@prescription_router.patch(
    "/{prescription_id}",
    response_model=PrescriptionResponseSchema,
    summary="Amend digital prescription",
    description="Allows the issuing doctor to adjust prescribed items with a mandatory reason and audit entry.",
)
async def amend_prescription(
    prescription_id: str,
    req: AmendPrescriptionRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> PrescriptionResponseSchema:
    """Controlled prescription correction."""
    return await MedicalRecordService.amend_prescription(
        db=db, doctor_user=current_user, prescription_id=prescription_id, req=req
    )


@prescription_router.get(
    "/{prescription_id}/pdf",
    summary="Download verified prescription PDF",
    description="Generates and streams an authenticated, tamper-evident digital prescription PDF.",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Returns raw PDF document bytes.",
        }
    },
)
async def download_prescription_pdf(
    prescription_id: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> Response:
    """Download official digital prescription PDF."""
    pdf_bytes = await MedicalRecordService.generate_prescription_pdf(
        db=db, current_user=current_user, prescription_id=prescription_id
    )

    clean_filename = f"prescription_{prescription_id}.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{clean_filename}"',
        "Content-Type": "application/pdf",
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
