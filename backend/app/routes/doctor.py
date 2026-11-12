"""Doctor routes for application status, public discovery, and availability management."""

from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, require_doctor, require_doctor_applicant
from app.schemas.appointment import (
    AppointmentListResponse,
    AppointmentResponse,
    CancelAppointmentRequest,
)
from app.schemas.doctor import (
    CreateAvailabilityRequest,
    CreateBlockedTimeRequest,
    CreateLeaveRequest,
    DayAvailabilitySlots,
    DoctorApplicationStatusResponse,
    DoctorAvailabilityResponse,
    DoctorBlockedTimeResponse,
    DoctorCalendarOverviewResponse,
    DoctorDetailResponse,
    DoctorLeaveResponse,
    DoctorListResponse,
    DoctorWeeklyScheduleResponse,
    UpdateAvailabilityRequest,
    UpdateWeeklyScheduleRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.appointment_service import AppointmentService
from app.services.doctor_service import DoctorService

doctor_router = APIRouter(prefix="/doctors", tags=["Doctors"])


# ---------------------------------------------------------------------------
# DOCTOR MANAGEMENT ENDPOINTS (DOCTOR ROLE ONLY)
# Note: Defined before /{doctorId} to prevent route parameter collision.
# ---------------------------------------------------------------------------

@doctor_router.get(
    "/me/application-status",
    response_model=DoctorApplicationStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get doctor application status",
    description="Returns verification status and submission details for the authenticated doctor. Does not expose internal documents.",
)
def get_application_status(
    current_user: UserResponseSchema = Depends(require_doctor_applicant),
    db: Database = Depends(get_database),
) -> DoctorApplicationStatusResponse:
    """Fetch current doctor's application status."""
    return DoctorService.get_application_status(current_user.id, db)


@doctor_router.post(
    "/me/availability",
    response_model=DoctorAvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create doctor availability window",
    description="Allows an approved and active doctor to schedule availability windows.",
)
async def create_availability(
    req: CreateAvailabilityRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorAvailabilityResponse:
    """Create a new availability schedule for the authenticated doctor."""
    return await DoctorService.create_availability(
        db=db,
        doctor_user=current_user,
        req=req,
    )


@doctor_router.get(
    "/me/availability",
    response_model=List[DoctorAvailabilityResponse],
    status_code=status.HTTP_200_OK,
    summary="Get authenticated doctor's availability",
    description="Returns all availability windows defined by the authenticated doctor.",
)
async def get_my_availability(
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> List[DoctorAvailabilityResponse]:
    """Retrieve all availability schedules for the authenticated doctor."""
    return await DoctorService.get_doctor_availabilities(
        db=db,
        doctor_user=current_user,
    )


@doctor_router.put(
    "/me/availability/{availabilityId}",
    response_model=DoctorAvailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Update doctor availability window",
    description="Updates an existing availability window. Ownership is strictly enforced.",
)
async def update_availability(
    availabilityId: str,
    req: UpdateAvailabilityRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorAvailabilityResponse:
    """Update a specific availability window belonging to the authenticated doctor."""
    return await DoctorService.update_availability(
        db=db,
        doctor_user=current_user,
        availability_id=availabilityId,
        req=req,
    )


@doctor_router.delete(
    "/me/availability/{availabilityId}",
    status_code=status.HTTP_200_OK,
    summary="Delete / disable doctor availability window",
    description="Soft-disables an availability schedule. Preserves data for future appointment consistency.",
)
async def delete_availability(
    availabilityId: str,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> Dict[str, str]:
    """Remove / deactivate an availability window belonging to the authenticated doctor."""
    return await DoctorService.delete_availability(
        db=db,
        doctor_user=current_user,
        availability_id=availabilityId,
    )


# ---------------------------------------------------------------------------
# Phase 54: Weekly Schedule, Leave, Blocked Time & Calendar Overview
# ---------------------------------------------------------------------------

@doctor_router.get(
    "/me/weekly-schedule",
    response_model=DoctorWeeklyScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get doctor weekly recurring schedule",
    description="Returns doctor's configured weekly working hours, slot duration, and timezone.",
)
async def get_my_weekly_schedule(
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorWeeklyScheduleResponse:
    """Fetch weekly working schedule for the authenticated doctor."""
    return await DoctorService.get_doctor_weekly_schedule(
        db=db,
        doctor_user=current_user,
    )


@doctor_router.put(
    "/me/weekly-schedule",
    response_model=DoctorWeeklyScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update doctor weekly recurring schedule",
    description="Configures weekly working hours, slot duration, and timezone for an approved doctor.",
)
async def update_my_weekly_schedule(
    req: UpdateWeeklyScheduleRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorWeeklyScheduleResponse:
    """Update weekly working schedule for the authenticated doctor."""
    return await DoctorService.update_doctor_weekly_schedule(
        db=db,
        doctor_user=current_user,
        req=req,
    )


@doctor_router.post(
    "/me/leave",
    response_model=DoctorLeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for or schedule doctor leave",
    description="Creates a full-day, multi-day, or partial-day leave entry. Checks for appointment conflicts.",
)
async def create_my_leave(
    req: CreateLeaveRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorLeaveResponse:
    """Create a leave record for the doctor."""
    return await DoctorService.create_doctor_leave(
        db=db,
        doctor_user=current_user,
        req=req,
    )


@doctor_router.get(
    "/me/leave",
    response_model=List[DoctorLeaveResponse],
    status_code=status.HTTP_200_OK,
    summary="List doctor leave records",
    description="Returns all active or past leave entries configured by the doctor.",
)
async def list_my_leaves(
    status: Optional[str] = Query(None, description="Optional status filter: ACTIVE | CANCELLED"),
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> List[DoctorLeaveResponse]:
    """Retrieve leave records for the authenticated doctor."""
    return await DoctorService.list_doctor_leaves(
        db=db,
        doctor_user=current_user,
        status_filter=status,
    )


@doctor_router.delete(
    "/me/leave/{leaveId}",
    status_code=status.HTTP_200_OK,
    summary="Cancel doctor leave record",
    description="Cancels an active leave record, releasing blocked days back to working availability.",
)
async def cancel_my_leave(
    leaveId: str,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> Dict[str, str]:
    """Cancel a leave record."""
    return await DoctorService.cancel_doctor_leave(
        db=db,
        doctor_user=current_user,
        leave_id=leaveId,
    )


@doctor_router.post(
    "/me/blocked-time",
    response_model=DoctorBlockedTimeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Block a specific date and time range",
    description="Allows a doctor to block specific time windows on a particular date.",
)
async def create_my_blocked_time(
    req: CreateBlockedTimeRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorBlockedTimeResponse:
    """Create a blocked time interval."""
    return await DoctorService.create_doctor_blocked_time(
        db=db,
        doctor_user=current_user,
        req=req,
    )


@doctor_router.get(
    "/me/blocked-time",
    response_model=List[DoctorBlockedTimeResponse],
    status_code=status.HTTP_200_OK,
    summary="List doctor blocked times",
    description="Returns all blocked time intervals configured by the doctor.",
)
async def list_my_blocked_times(
    date: Optional[str] = Query(None, description="Optional date filter YYYY-MM-DD"),
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> List[DoctorBlockedTimeResponse]:
    """Retrieve blocked times for the authenticated doctor."""
    return await DoctorService.list_doctor_blocked_times(
        db=db,
        doctor_user=current_user,
        date_filter=date,
    )


@doctor_router.delete(
    "/me/blocked-time/{blockId}",
    status_code=status.HTTP_200_OK,
    summary="Delete blocked time interval",
    description="Removes a blocked time interval.",
)
async def delete_my_blocked_time(
    blockId: str,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> Dict[str, str]:
    """Delete a blocked time interval."""
    return await DoctorService.delete_doctor_blocked_time(
        db=db,
        doctor_user=current_user,
        block_id=blockId,
    )


@doctor_router.get(
    "/me/calendar-overview",
    response_model=DoctorCalendarOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get monthly calendar overview for doctor",
    description="Returns month-level daily summaries of available slots, booked appointments, leaves, and blocked times.",
)
async def get_my_calendar_overview(
    month: Optional[str] = Query(None, description="Month in YYYY-MM format (defaults to current month)"),
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorCalendarOverviewResponse:
    """Fetch calendar overview for the doctor."""
    return await DoctorService.get_doctor_calendar_overview(
        db=db,
        doctor_user=current_user,
        month_str=month,
    )


@doctor_router.get(
    "/me/appointments",
    response_model=AppointmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated doctor's appointments",
    description="Returns assigned appointments for the approved doctor with optional status and date filters.",
)
async def get_my_appointments(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    date: Optional[str] = Query(None, description="Filter by appointment date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter: PENDING | CONFIRMED | COMPLETED | CANCELLED"),
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> AppointmentListResponse:
    """Retrieve appointments for the authenticated doctor."""
    return await AppointmentService.list_doctor_appointments(
        db=db,
        doctor_user=current_user,
        page=page,
        limit=limit,
        date_filter=date,
        status_filter=status,
    )


@doctor_router.post(
    "/me/appointments/{appointmentId}/confirm",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Doctor confirms a pending appointment",
    description="Transition appointment from PENDING to CONFIRMED. Only the assigned doctor can confirm.",
)
async def confirm_appointment(
    appointmentId: str,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> AppointmentResponse:
    """Confirm a PENDING appointment."""
    return await AppointmentService.confirm_doctor_appointment(
        db=db,
        doctor_user=current_user,
        appointment_id=appointmentId,
    )


@doctor_router.post(
    "/me/appointments/{appointmentId}/complete",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Doctor marks appointment as completed",
    description="Transition appointment from CONFIRMED to COMPLETED. Consultation time must be reached or passed.",
)
async def complete_appointment(
    appointmentId: str,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> AppointmentResponse:
    """Mark a CONFIRMED appointment as completed."""
    return await AppointmentService.complete_doctor_appointment(
        db=db,
        doctor_user=current_user,
        appointment_id=appointmentId,
    )


@doctor_router.post(
    "/me/appointments/{appointmentId}/cancel",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Doctor cancels an appointment",
    description="Allows assigned doctor to cancel a PENDING or CONFIRMED appointment.",
)
async def cancel_doctor_appointment(
    appointmentId: str,
    req: CancelAppointmentRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> AppointmentResponse:
    """Doctor cancels an appointment."""
    return await AppointmentService.cancel_doctor_appointment(
        db=db,
        doctor_user=current_user,
        appointment_id=appointmentId,
        reason=req.reason if req else None,
    )


# ---------------------------------------------------------------------------
# PATIENT DISCOVERY & AVAILABILITY ENDPOINTS
# ---------------------------------------------------------------------------

@doctor_router.get(
    "",
    response_model=DoctorListResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover approved doctors",
    description="Lists and searches approved, active doctors with pagination and optional specialty filter.",
)
async def list_doctors(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    search: Optional[str] = Query(None, description="Search term for doctor name, specialty, or clinic"),
    specialty: Optional[str] = Query(None, description="Filter by specialty"),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> DoctorListResponse:
    """Patient-facing discovery of approved doctors."""
    return await DoctorService.list_approved_doctors(
        db=db,
        page=page,
        limit=limit,
        search=search,
        specialty=specialty,
    )


@doctor_router.get(
    "/{doctorId}/availability",
    response_model=Union[DayAvailabilitySlots, List[DayAvailabilitySlots]],
    status_code=status.HTTP_200_OK,
    summary="Get patient-visible available slots for an approved doctor",
    description="Returns derived time slots for active availability windows. Past slots are excluded.",
)
async def get_doctor_patient_slots(
    doctorId: str,
    date: Optional[str] = Query(None, description="Filter slots for a specific date (YYYY-MM-DD)"),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> Any:
    """Fetch generated available slots for a doctor."""
    return await DoctorService.get_doctor_patient_slots(
        db=db,
        doctor_id=doctorId,
        date_filter=date,
    )


@doctor_router.get(
    "/{doctorId}",
    response_model=DoctorDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get approved doctor public profile",
    description="Returns public details for an approved doctor. Inactive/pending/rejected doctors return 404.",
)
async def get_doctor_detail(
    doctorId: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> DoctorDetailResponse:
    """Retrieve detailed public profile for a specific approved doctor."""
    return await DoctorService.get_approved_doctor_detail(
        db=db,
        doctor_id=doctorId,
    )
