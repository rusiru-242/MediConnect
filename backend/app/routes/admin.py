"""Admin routes for doctor applications and verification workflow."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_admin
from app.schemas.admin import (
    AdminActionResponse,
    AdminAppointmentListResponse,
    AdminDoctorApplicationDetail,
    AdminDoctorApplicationSummary,
    AdminDoctorListResponse,
    AdminPaymentListResponse,
    AdminReviewListResponse,
    AdminUserListResponse,
    RejectDoctorRequest,
    UpdateUserStatusRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.admin_service import AdminService


router = APIRouter(
    prefix="/admin",
    tags=["Admin Doctor Verification"],
)


@router.get(
    "/doctors/applications",
    response_model=List[AdminDoctorApplicationSummary],
    status_code=status.HTTP_200_OK,
    summary="List doctor applications by status",
)
async def list_doctor_applications(
    status_filter: Optional[str] = Query(
        "PENDING",
        alias="status",
        description="Filter by status (PENDING, APPROVED, REJECTED, ALL). Default is PENDING.",
    ),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> List[AdminDoctorApplicationSummary]:
    """Retrieve doctor applications with status filtering. Requires ADMIN role."""
    return await AdminService.list_doctor_applications(db=db, status_filter=status_filter)


@router.get(
    "/doctors/applications/{doctorProfileId}",
    response_model=AdminDoctorApplicationDetail,
    status_code=status.HTTP_200_OK,
    summary="Get doctor application details for review",
)
async def get_doctor_application_detail(
    doctorProfileId: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminDoctorApplicationDetail:
    """Retrieve full application details and safe document metadata for review. Requires ADMIN role."""
    return await AdminService.get_doctor_application_detail(
        db=db,
        doctor_profile_id=doctorProfileId,
    )


@router.get(
    "/doctors/applications/{doctorProfileId}/documents/{documentId}",
    summary="Securely view or download a doctor verification document",
)
async def get_doctor_verification_document(
    doctorProfileId: str,
    documentId: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Serve a doctor verification document securely without exposing server filesystem paths. Requires ADMIN role."""
    file_path, filename, media_type = await AdminService.get_doctor_verification_document(
        db=db,
        doctor_profile_id=doctorProfileId,
        document_id=documentId,
    )

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
        content_disposition_type="inline",
    )


@router.post(
    "/doctors/{doctorProfileId}/approve",
    response_model=AdminActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve doctor application",
)
async def approve_doctor_application(
    doctorProfileId: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminActionResponse:
    """Approve a doctor application, activating their account. Requires ADMIN role."""
    return await AdminService.approve_doctor_application(
        db=db,
        doctor_profile_id=doctorProfileId,
        admin_user_id=current_admin.id,
    )


@router.post(
    "/doctors/{doctorProfileId}/reject",
    response_model=AdminActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject doctor application with reason",
)
async def reject_doctor_application(
    doctorProfileId: str,
    request: RejectDoctorRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminActionResponse:
    """Reject a doctor application with an explanatory reason. Requires ADMIN role."""
    return await AdminService.reject_doctor_application(
        db=db,
        doctor_profile_id=doctorProfileId,
        admin_user_id=current_admin.id,
        reason=request.reason,
    )


# -----------------------------------------------------------------------------
# User Administration Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=AdminUserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List users with privacy-safe admin view",
)
async def list_users(
    role: Optional[str] = Query(None, description="Role filter (PATIENT, DOCTOR, ADMIN, ALL)"),
    status: Optional[str] = Query(None, description="Account status filter (ACTIVE, SUSPENDED, PENDING, DEACTIVATED, ALL)"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    page: int = Query(1, ge=1, description="Page number"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminUserListResponse:
    """List users with privacy protection (no password hashes or medical history). Requires ADMIN role."""
    return await AdminService.list_users(
        db=db,
        role=role,
        status_filter=status,
        search=search,
        page=page,
        page_size=pageSize,
    )


@router.patch(
    "/users/{userId}/status",
    response_model=AdminActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a user's account status",
)
async def update_user_status(
    userId: str,
    request: UpdateUserStatusRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminActionResponse:
    """Modify user status (ACTIVE, SUSPENDED, DEACTIVATED). Self-suspension is blocked. Requires ADMIN role."""
    return await AdminService.update_user_status(
        db=db,
        user_id=userId,
        new_status=request.accountStatus,
        admin_user_id=current_admin.id,
    )


# -----------------------------------------------------------------------------
# Doctor Directory Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/doctors",
    response_model=AdminDoctorListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all doctors with verification and rating summaries",
)
async def list_doctors(
    specialty: Optional[str] = Query(None, description="Filter by specialty"),
    status: Optional[str] = Query(None, description="Filter by verification status (PENDING, APPROVED, REJECTED, ALL)"),
    search: Optional[str] = Query(None, description="Search by name, email, specialty, or clinic"),
    page: int = Query(1, ge=1, description="Page number"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminDoctorListResponse:
    """Directory of all doctors for administrative review. Requires ADMIN role."""
    return await AdminService.list_doctors(
        db=db,
        specialty=specialty,
        status_filter=status,
        search=search,
        page=page,
        page_size=pageSize,
    )


# -----------------------------------------------------------------------------
# Appointment Oversight Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/appointments",
    response_model=AdminAppointmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List platform appointments for admin monitoring",
)
async def list_appointments(
    status: Optional[str] = Query(None, description="Appointment status filter (PENDING, CONFIRMED, COMPLETED, CANCELLED, ALL)"),
    paymentStatus: Optional[str] = Query(None, description="Payment status filter (UNPAID, PAID, FAILED, REFUNDED, ALL)"),
    search: Optional[str] = Query(None, description="Search by patient name, doctor name, or specialty"),
    startDate: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    endDate: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminAppointmentListResponse:
    """Retrieve platform appointments without altering booking state machines. Requires ADMIN role."""
    return await AdminService.list_appointments(
        db=db,
        status_filter=status,
        payment_status=paymentStatus,
        search=search,
        start_date=startDate,
        end_date=endDate,
        page=page,
        page_size=pageSize,
    )


# -----------------------------------------------------------------------------
# Payment Oversight Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/payments",
    response_model=AdminPaymentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List platform payment transactions for financial oversight",
)
async def list_payments(
    status: Optional[str] = Query(None, description="Payment status filter (PENDING, SUCCEEDED, FAILED, CANCELLED, REFUNDED, ALL)"),
    currency: Optional[str] = Query(None, description="Currency filter (e.g. LKR, USD, ALL)"),
    startDate: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    endDate: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminPaymentListResponse:
    """Monitor platform payments with test/live mode flags and no sensitive card exposure. Requires ADMIN role."""
    return await AdminService.list_payments(
        db=db,
        status_filter=status,
        currency=currency,
        start_date=startDate,
        end_date=endDate,
        page=page,
        page_size=pageSize,
    )


# -----------------------------------------------------------------------------
# Review Oversight Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/reviews",
    response_model=AdminReviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all doctor reviews for admin oversight",
)
async def list_reviews(
    status: Optional[str] = Query(None, description="Review status filter (ALL, REPORTED, PUBLISHED, HIDDEN)"),
    page: int = Query(1, ge=1, description="Page number"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminReviewListResponse:
    """List reviews across all doctors with reported flags and moderation status. Requires ADMIN role."""
    return await AdminService.list_reviews(
        db=db,
        status_filter=status,
        page=page,
        page_size=pageSize,
    )
