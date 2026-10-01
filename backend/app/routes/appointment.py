"""Appointment routes for patient booking and doctor management."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, require_doctor, require_patient
from app.schemas.appointment import (
    AppointmentListResponse,
    AppointmentResponse,
    CancelAppointmentRequest,
    CreateAppointmentRequest,
    CreateAppointmentResponse,
    UpdateAppointmentStatusRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.appointment_service import AppointmentService

appointment_router = APIRouter(prefix="/appointments", tags=["Appointments"])


# ---------------------------------------------------------------------------
# PATIENT ENDPOINTS
# ---------------------------------------------------------------------------

@appointment_router.post(
    "",
    response_model=CreateAppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book an appointment",
    description="Patient books a time slot with an approved doctor. Backend validates the slot and prevents double-booking at the database level.",
)
async def create_appointment(
    req: CreateAppointmentRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> CreateAppointmentResponse:
    """Patient books an appointment."""
    return await AppointmentService.create_appointment(db=db, patient_user=current_user, req=req)


@appointment_router.get(
    "/me",
    response_model=AppointmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="Patient appointment history",
    description="Returns the authenticated patient's appointment list, optionally filtered by status.",
)
async def list_my_appointments(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter: PENDING | CONFIRMED | COMPLETED | CANCELLED"),
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> AppointmentListResponse:
    """Patient's own appointment history."""
    return await AppointmentService.list_patient_appointments(
        db=db,
        patient_user=current_user,
        page=page,
        limit=limit,
        status_filter=status,
    )


@appointment_router.post(
    "/{appointmentId}/cancel",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Patient cancels appointment",
    description="Patient cancels their own PENDING or CONFIRMED appointment. Completed appointments cannot be cancelled.",
)
async def cancel_appointment(
    appointmentId: str,
    req: CancelAppointmentRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> AppointmentResponse:
    """Patient cancels their own appointment."""
    return await AppointmentService.cancel_patient_appointment(
        db=db,
        patient_user=current_user,
        appointment_id=appointmentId,
        reason=req.reason if req else None,
    )


@appointment_router.get(
    "/{appointmentId}",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get appointment details",
    description="Returns appointment details. Requester must be the patient or the assigned doctor.",
)
async def get_appointment(
    appointmentId: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> AppointmentResponse:
    """Fetch a specific appointment (patient or doctor access)."""
    return await AppointmentService.get_appointment(
        db=db,
        requester=current_user,
        appointment_id=appointmentId,
    )


# ---------------------------------------------------------------------------
# DOCTOR ENDPOINTS
# ---------------------------------------------------------------------------

@appointment_router.get(
    "/doctor/list",
    response_model=AppointmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="Doctor's appointment list",
    description="Returns the authenticated doctor's appointments, optionally filtered by date and status.",
)
async def list_doctor_appointments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    date: Optional[str] = Query(None, description="Filter by date YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="Filter: PENDING | CONFIRMED | COMPLETED | CANCELLED"),
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> AppointmentListResponse:
    """Doctor's appointment list with optional date and status filters."""
    return await AppointmentService.list_doctor_appointments(
        db=db,
        doctor_user=current_user,
        page=page,
        limit=limit,
        date_filter=date,
        status_filter=status,
    )


@appointment_router.put(
    "/{appointmentId}/status",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Doctor updates appointment status",
    description="Doctor transitions appointment status. Strict state machine: PENDING→CONFIRMED, CONFIRMED→COMPLETED, PENDING/CONFIRMED→CANCELLED. Terminal states (COMPLETED, CANCELLED) cannot be modified.",
)
async def update_appointment_status(
    appointmentId: str,
    req: UpdateAppointmentStatusRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> AppointmentResponse:
    """Doctor updates the status of an appointment."""
    return await AppointmentService.update_appointment_status(
        db=db,
        doctor_user=current_user,
        appointment_id=appointmentId,
        req=req,
    )
