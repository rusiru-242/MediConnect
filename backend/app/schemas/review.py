"""Pydantic request and response schemas for Doctor Reviews and Ratings (Phase 23)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.review import ReviewStatus


class CreateReviewRequest(BaseModel):
    """Payload for submitting a verified appointment review."""

    appointmentId: str = Field(..., min_length=1, description="ID of the completed appointment")
    rating: int = Field(..., ge=1, le=5, description="Integer rating between 1 and 5")
    reviewText: Optional[str] = Field(default=None, max_length=1000, description="Optional written review text")

    @field_validator("reviewText")
    @classmethod
    def sanitize_review_text(cls, val: Optional[str]) -> Optional[str]:
        if val is None:
            return None
        cleaned = val.strip()
        return cleaned if cleaned else None


class UpdateReviewRequest(BaseModel):
    """Payload for updating an existing review by the patient."""

    rating: Optional[int] = Field(default=None, ge=1, le=5, description="Updated rating 1-5")
    reviewText: Optional[str] = Field(default=None, max_length=1000, description="Updated review text")

    @field_validator("reviewText")
    @classmethod
    def sanitize_review_text(cls, val: Optional[str]) -> Optional[str]:
        if val is None:
            return None
        cleaned = val.strip()
        return cleaned if cleaned else None


class ReportReviewRequest(BaseModel):
    """Payload for reporting an inappropriate review."""

    reason: str = Field(..., min_length=5, max_length=500, description="Explanation for reporting the review")

    @field_validator("reason")
    @classmethod
    def sanitize_reason(cls, val: str) -> str:
        return val.strip()


class ModerateReviewRequest(BaseModel):
    """Payload for admin review moderation (hide or restore)."""

    action: str = Field(..., description="HIDE or RESTORE")
    moderationNotes: Optional[str] = Field(default=None, max_length=500, description="Notes on moderation decision")

    @field_validator("action")
    @classmethod
    def validate_action(cls, val: str) -> str:
        upper = val.strip().upper()
        if upper not in ["HIDE", "RESTORE"]:
            raise ValueError("action must be either HIDE or RESTORE")
        return upper


class ReviewResponse(BaseModel):
    """Full review response schema."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    reviewId: str
    doctorUserId: str
    doctorProfileId: str
    patientUserId: str
    patientDisplayName: str
    appointmentId: str
    rating: int
    reviewText: Optional[str] = None
    status: ReviewStatus
    verifiedAppointment: bool = True
    createdAt: datetime
    updatedAt: datetime

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value


class PublicReviewItem(BaseModel):
    """Publicly displayed verified review item with privacy-safe reviewer name."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    reviewId: str
    rating: int
    reviewText: Optional[str] = None
    patientDisplayName: str
    verifiedAppointment: bool = True
    createdAt: datetime
    updatedAt: Optional[datetime] = None


class DoctorRatingSummaryResponse(BaseModel):
    """Aggregated verified ratings summary for a doctor."""

    doctorId: str
    doctorUserId: Optional[str] = None
    doctorProfileId: Optional[str] = None
    averageRating: Optional[float] = None
    totalReviews: int = 0
    ratingDistribution: Dict[str, int] = Field(
        default_factory=lambda: {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    )
    hasReviews: bool = False


class PublicReviewListResponse(BaseModel):
    """Paginated list of public verified reviews."""

    items: List[PublicReviewItem]
    total: int
    page: int
    pageSize: int
    totalPages: int
    summary: Optional[DoctorRatingSummaryResponse] = None


class PatientReviewItem(BaseModel):
    """Review item for the patient's own reviews dashboard."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    reviewId: str
    appointmentId: str
    doctorUserId: str
    doctorProfileId: str
    doctorName: Optional[str] = None
    doctorSpecialty: Optional[str] = None
    doctorHospital: Optional[str] = None
    rating: int
    reviewText: Optional[str] = None
    status: ReviewStatus
    createdAt: datetime
    updatedAt: datetime


class PatientReviewListResponse(BaseModel):
    """Paginated list of reviews written by the patient."""

    items: List[PatientReviewItem]
    total: int
    page: int
    pageSize: int
    totalPages: int


class AdminReportedReviewItem(BaseModel):
    """Reported review item for administrative moderation."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    reviewId: str
    appointmentId: str
    doctorUserId: str
    doctorName: Optional[str] = None
    patientUserId: str
    patientDisplayName: Optional[str] = None
    rating: int
    reviewText: Optional[str] = None
    status: ReviewStatus
    reportReason: Optional[str] = None
    reportedBy: Optional[str] = None
    reportedAt: Optional[datetime] = None
    createdAt: datetime
