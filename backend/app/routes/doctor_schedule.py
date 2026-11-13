"""Routes for Doctor Daily Schedule & Consultation Management (Phase 57)."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_doctor
from app.schemas.consultation import (
    CompleteConsultationRequest,
    ConsultationDetailResponse,
    ConsultationSessionResponse,
    DailyScheduleStats,
    DoctorDailyScheduleResponse,
    StartConsultationRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.consultation_service import ConsultationService

doctor_schedule_router = APIRouter(prefix="/doctor", tags=["Doctor Schedule & Consultations"])


# ---------------------------------------------------------------------------
# SCHEDULE ENDPOINTS
# ---------------------------------------------------------------------------

@doctor_schedule_router.get(
    "/schedule/today",
    response_model=DoctorDailyScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get today's schedule for doctor",
    description="Returns today's appointments in chronological order, next eligible patient, and daily stats in doctor's timezone.",
)
async def get_today_schedule(
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorDailyScheduleResponse:
    """Fetch today's schedule for authenticated approved doctor."""
    return await ConsultationService.get_doctor_daily_schedule(
        db=db,
        doctor_user=current_user,
        date_str=None,
    )


@doctor_schedule_router.get(
    "/schedule",
    response_model=DoctorDailyScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get doctor schedule by date",
    description="Returns appointments for a specific date in chronological order, next eligible patient, and daily stats.",
)
async def get_schedule_by_date(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (defaults to doctor local today)"),
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorDailyScheduleResponse:
    """Fetch schedule for a specific date."""
    return await ConsultationService.get_doctor_daily_schedule(
        db=db,
        doctor_user=current_user,
        date_str=date,
    )


@doctor_schedule_router.get(
    "/schedule/summary",
    response_model=DailyScheduleStats,
    status_code=status.HTTP_200_OK,
    summary="Get daily appointment statistics",
    description="Returns aggregate counts (total, upcoming, waiting, in-progress, completed, cancelled) for doctor on a specific date.",
)
async def get_schedule_summary(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DailyScheduleStats:
    """Fetch daily statistics summary."""
    return await ConsultationService.get_doctor_schedule_summary(
        db=db,
        doctor_user=current_user,
        date_str=date,
    )


# ---------------------------------------------------------------------------
# CONSULTATION ENDPOINTS
# ---------------------------------------------------------------------------

@doctor_schedule_router.get(
    "/consultations/{appointmentId}",
    response_model=ConsultationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get consultation details for appointment",
    description="Returns patient details, consultation status, notes, and links to existing prescriptions, medical records, and care plans.",
)
async def get_consultation_details(
    appointmentId: str,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> ConsultationDetailResponse:
    """Fetch consultation details for an assigned appointment."""
    return await ConsultationService.get_consultation_details(
        db=db,
        doctor_user=current_user,
        appointment_id=appointmentId,
    )


@doctor_schedule_router.post(
    "/consultations/{appointmentId}/start",
    response_model=ConsultationSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Start consultation",
    description="Transitions consultation state to IN_PROGRESS. Idempotent on retries. Fails if appointment is cancelled or already completed.",
)
async def start_consultation(
    appointmentId: str,
    req: Optional[StartConsultationRequest] = None,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> ConsultationSessionResponse:
    """Start consultation session."""
    return await ConsultationService.start_consultation(
        db=db,
        doctor_user=current_user,
        appointment_id=appointmentId,
        notes=req.notes if req else None,
    )


@doctor_schedule_router.post(
    "/consultations/{appointmentId}/complete",
    response_model=ConsultationSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete consultation",
    description="Transitions consultation state to COMPLETED and marks appointment as COMPLETED. Requires consultation to be IN_PROGRESS.",
)
async def complete_consultation(
    appointmentId: str,
    req: Optional[CompleteConsultationRequest] = None,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> ConsultationSessionResponse:
    """Complete consultation session."""
    return await ConsultationService.complete_consultation(
        db=db,
        doctor_user=current_user,
        appointment_id=appointmentId,
        notes=req.notes if req else None,
    )
