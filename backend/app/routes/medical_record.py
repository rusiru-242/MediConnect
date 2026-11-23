"""FastAPI route endpoints for Patient Consultation Medical Records (Phase 21)."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, require_doctor
from app.models.user import UserRole
from app.schemas.medical_record import (
    AmendMedicalRecordRequest,
    CreateMedicalRecordRequest,
    MedicalRecordListResponse,
    MedicalRecordResponseSchema,
)
from app.schemas.user import UserResponseSchema
from app.services.medical_record_service import MedicalRecordService

medical_record_router = APIRouter(prefix="/medical-records", tags=["Medical Records"])


@medical_record_router.post(
    "",
    response_model=MedicalRecordResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create medical consultation record",
    description="Allows verified, approved doctors to document a completed appointment consultation with clinical notes, assessment, and care plan.",
)
async def create_medical_record(
    req: CreateMedicalRecordRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> MedicalRecordResponseSchema:
    """Document a consultation record for a completed appointment."""
    return await MedicalRecordService.create_medical_record(
        db=db, doctor_user=current_user, req=req
    )


@medical_record_router.get(
    "/me",
    response_model=MedicalRecordListResponse,
    summary="List my consultation records",
    description="Returns consultation records for the authenticated patient or doctor with pagination.",
)
async def list_my_medical_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    appointment_id: Optional[str] = Query(default=None),
    patient_id: Optional[str] = Query(default=None),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> MedicalRecordListResponse:
    """List authenticated user's consultation records."""
    if current_user.role == UserRole.DOCTOR.value:
        return await MedicalRecordService.list_doctor_records(
            db=db,
            doctor_user=current_user,
            appointment_id=appointment_id,
            patient_id=patient_id,
            page=page,
            page_size=page_size,
        )
    return await MedicalRecordService.list_patient_records(
        db=db, patient_user=current_user, page=page, page_size=page_size
    )


@medical_record_router.get(
    "/{record_id}",
    response_model=MedicalRecordResponseSchema,
    summary="Get medical record details",
    description="Retrieves a specific consultation record with ownership verification and audit trail logging.",
)
async def get_medical_record(
    record_id: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> MedicalRecordResponseSchema:
    """Retrieve consultation record by ID."""
    return await MedicalRecordService.get_medical_record(
        db=db, current_user=current_user, record_id=record_id
    )


@medical_record_router.patch(
    "/{record_id}",
    response_model=MedicalRecordResponseSchema,
    summary="Amend clinical record",
    description="Allows the assigned doctor to correct a clinical record with a required justification and tamper-evident history.",
)
async def amend_medical_record(
    record_id: str,
    req: AmendMedicalRecordRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> MedicalRecordResponseSchema:
    """Controlled clinical record amendment."""
    return await MedicalRecordService.amend_medical_record(
        db=db, doctor_user=current_user, record_id=record_id, req=req
    )
