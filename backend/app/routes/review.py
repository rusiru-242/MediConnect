"""FastAPI route endpoints for Doctor Reviews & Ratings (Phase 23)."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, require_admin, require_patient
from app.schemas.review import (
    AdminReportedReviewItem,
    CreateReviewRequest,
    DoctorRatingSummaryResponse,
    ModerateReviewRequest,
    PatientReviewListResponse,
    PublicReviewListResponse,
    ReportReviewRequest,
    ReviewResponse,
    UpdateReviewRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.review_service import ReviewService

review_router = APIRouter(tags=["Reviews & Ratings"])


@review_router.post(
    "/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a verified doctor review",
    description="Allows authenticated patients to review a doctor for a completed appointment.",
)
async def create_review(
    req: CreateReviewRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> ReviewResponse:
    """Submit a verified review for a completed appointment."""
    return await ReviewService.create_review(
        db=db,
        patient_user=current_user,
        req=req,
    )


@review_router.get(
    "/doctors/{doctor_id}/reviews",
    response_model=PublicReviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="List public verified reviews for a doctor",
    description="Returns verified patient reviews with privacy-safe display names.",
)
async def get_doctor_reviews(
    doctor_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Database = Depends(get_database),
) -> PublicReviewListResponse:
    """List public verified reviews for a doctor."""
    return await ReviewService.list_doctor_public_reviews(
        db=db,
        doctor_identifier=doctor_id,
        page=page,
        page_size=page_size,
    )


@review_router.get(
    "/doctors/{doctor_id}/rating-summary",
    response_model=DoctorRatingSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get verified rating summary for a doctor",
    description="Calculates average rating, total verified reviews, and 1-5 star distribution.",
)
async def get_doctor_rating_summary(
    doctor_id: str,
    db: Database = Depends(get_database),
) -> DoctorRatingSummaryResponse:
    """Get verified rating summary for a doctor."""
    return await ReviewService.get_doctor_rating_summary(
        db=db,
        doctor_identifier=doctor_id,
    )


@review_router.get(
    "/reviews/me",
    response_model=PatientReviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="List current patient's reviews",
    description="Returns all reviews authored by the authenticated patient.",
)
async def list_my_reviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> PatientReviewListResponse:
    """List authenticated patient's reviews."""
    return await ReviewService.list_patient_reviews(
        db=db,
        patient_user=current_user,
        page=page,
        page_size=page_size,
    )


@review_router.patch(
    "/reviews/{review_id}",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a review",
    description="Allows the reviewing patient to update their rating or review text.",
)
async def update_review(
    review_id: str,
    req: UpdateReviewRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> ReviewResponse:
    """Update own review."""
    return await ReviewService.update_review(
        db=db,
        review_id=review_id,
        patient_user=current_user,
        req=req,
    )


@review_router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a review",
    description="Allows the reviewing patient or an administrator to delete a review.",
)
async def delete_review(
    review_id: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> Dict[str, Any]:
    """Delete a review."""
    return await ReviewService.delete_review(
        db=db,
        review_id=review_id,
        current_user=current_user,
    )


@review_router.post(
    "/reviews/{review_id}/report",
    status_code=status.HTTP_200_OK,
    summary="Report an inappropriate review",
    description="Flags a review for administrator moderation with an explanation.",
)
async def report_review(
    review_id: str,
    req: ReportReviewRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> Dict[str, Any]:
    """Report a review for moderation."""
    return await ReviewService.report_review(
        db=db,
        review_id=review_id,
        current_user=current_user,
        req=req,
    )


@review_router.get(
    "/admin/reviews/reported",
    response_model=List[AdminReportedReviewItem],
    status_code=status.HTTP_200_OK,
    summary="List reported reviews for admin moderation",
    description="Administrative endpoint to inspect reported reviews awaiting decision.",
)
async def list_reported_reviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> List[AdminReportedReviewItem]:
    """List reported reviews for moderation."""
    return await ReviewService.list_reported_reviews(
        db=db,
        admin_user=current_admin,
        page=page,
        page_size=page_size,
    )


@review_router.patch(
    "/reviews/{review_id}/moderate",
    status_code=status.HTTP_200_OK,
    summary="Moderate a reported review",
    description="Allows an administrator to hide or restore a review. Does not alter patient rating value.",
)
async def moderate_review(
    review_id: str,
    req: ModerateReviewRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> Dict[str, Any]:
    """Hide or restore a review as an administrator."""
    return await ReviewService.moderate_review(
        db=db,
        review_id=review_id,
        admin_user=current_admin,
        req=req,
    )
