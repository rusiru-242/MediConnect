"""Doctor routes for application status, public discovery, and availability management."""

from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, require_doctor
from app.schemas.doctor import (
    CreateAvailabilityRequest,
    DayAvailabilitySlots,
    DoctorApplicationStatusResponse,
    DoctorAvailabilityResponse,
    DoctorDetailResponse,
    DoctorListResponse,
    UpdateAvailabilityRequest,
)
from app.schemas.user import UserResponseSchema
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
    current_user: UserResponseSchema = Depends(require_doctor),
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
