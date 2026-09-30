"""Admin routes for doctor applications and verification workflow."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_admin
from app.schemas.admin import (
    AdminActionResponse,
    AdminDoctorApplicationDetail,
    AdminDoctorApplicationSummary,
    RejectDoctorRequest,
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
