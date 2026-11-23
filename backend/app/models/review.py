"""MongoDB document model and database indexes for Doctor Reviews and Ratings (Phase 23)."""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class ReviewStatus(str, Enum):
    """Lifecycle status of a patient review."""
    PUBLISHED = "PUBLISHED"
    HIDDEN = "HIDDEN"
    REPORTED = "REPORTED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def mask_patient_name(full_name: Optional[str]) -> str:
    """Return privacy-preserving display name for public review listings."""
    if not full_name or not full_name.strip():
        return "Verified Patient"
    cleaned = re.sub(r"\s+", " ", full_name.strip())
    parts = cleaned.split(" ")
    if len(parts) == 1:
        first = parts[0]
        if len(first) <= 2:
            return "Verified Patient"
        return f"{first[0]}***"
    first = parts[0]
    last_initial = parts[-1][0].upper()
    return f"{first} {last_initial}."


class ReviewDocument(BaseModel):
    """MongoDB document representation for a verified appointment Doctor Review."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    reviewId: str = Field(..., description="Unique human-readable reference ID e.g. REV-20261018-XXXX")

    # Linked entities
    doctorUserId: str = Field(..., description="References users._id of the doctor")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    patientUserId: str = Field(..., description="References users._id of the reviewing patient")
    patientDisplayName: Optional[str] = Field(default=None, description="Full or cached patient name for auditing")
    appointmentId: str = Field(..., description="References appointments._id - strictly unique per review")

    # Review content
    rating: int = Field(..., ge=1, le=5, description="Integer rating between 1 and 5")
    reviewText: Optional[str] = Field(default=None, max_length=1000, description="Optional written review feedback")

    # Status & Moderation
    status: ReviewStatus = Field(default=ReviewStatus.PUBLISHED, description="Current publication status")
    reportReason: Optional[str] = Field(default=None, max_length=500, description="Reason if reported by user/doctor")
    reportedBy: Optional[str] = Field(default=None, description="User ID who reported this review")
    reportedAt: Optional[datetime] = Field(default=None, description="Timestamp when review was reported")
    moderationNotes: Optional[str] = Field(default=None, max_length=500, description="Audit notes recorded by administrator")
    moderatedBy: Optional[str] = Field(default=None, description="Admin user ID who moderated this review")
    moderatedAt: Optional[datetime] = Field(default=None, description="Timestamp of moderation action")

    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("reportedAt", "moderatedAt", "createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Serialize model for MongoDB insertion/update."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if "_id" in data and isinstance(data["_id"], str) and ObjectId.is_valid(data["_id"]):
            data["_id"] = ObjectId(data["_id"])
        return data


def get_review_collection(db: Database) -> Collection:
    """Return MongoDB collection for doctor reviews."""
    return db["doctor_reviews"]


def create_review_indexes(db: Database) -> None:
    """Create indexes for doctor reviews including unique constraint per appointment."""
    coll = get_review_collection(db)
    coll.create_index([("reviewId", ASCENDING)], unique=True, name="idx_review_ref_id")
    # Enforce strictly one review per appointment
    coll.create_index([("appointmentId", ASCENDING)], unique=True, name="idx_review_appointment_unique")
    coll.create_index(
        [("doctorUserId", ASCENDING), ("status", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_review_doctor_status_created",
    )
    coll.create_index(
        [("doctorProfileId", ASCENDING), ("status", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_review_doctor_profile_status_created",
    )
    coll.create_index(
        [("patientUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_review_patient_created",
    )
    coll.create_index(
        [("status", ASCENDING), ("reportedAt", DESCENDING)],
        name="idx_review_reported_status",
    )
