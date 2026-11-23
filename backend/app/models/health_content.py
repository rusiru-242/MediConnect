"""MongoDB document models and database indexes for Health & Wellness Content (Phase 24)."""

from datetime import datetime, timezone
from enum import Enum
import math
import re
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.collection import Collection
from pymongo.database import Database

SUPPORTED_CATEGORIES = [
    "Health News",
    "Healthy Food",
    "Nutrition",
    "Exercise",
    "Mental Wellness",
    "Preventive Healthcare",
    "General Health Tips",
]


class ContentStatus(str, Enum):
    """Publishing status of health content articles."""
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def calculate_reading_time(text: str) -> int:
    """Estimate reading time in minutes assuming 200 words per minute."""
    if not text:
        return 1
    words = len(re.findall(r"\w+", text))
    return max(1, math.ceil(words / 200))


class HealthContentDocument(BaseModel):
    """MongoDB document representation for an educational health article."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    contentId: str = Field(..., description="Unique human-readable article ID e.g. CNT-20261018-XXXX")

    title: str = Field(..., min_length=3, max_length=250, description="Article title")
    summary: str = Field(..., min_length=10, max_length=600, description="Brief introductory summary")
    body: str = Field(..., min_length=20, max_length=50000, description="Full article content in Markdown/text")

    category: str = Field(..., description="Health topic category")
    coverImage: Optional[str] = Field(default=None, max_length=1000, description="Image URL or local asset reference")
    tags: List[str] = Field(default_factory=list, description="Descriptive search tags")
    sources: Optional[str] = Field(default=None, max_length=1000, description="Educational references and sources")

    authorAdminId: str = Field(..., description="References users._id of creating admin")
    authorName: Optional[str] = Field(default="MediConnect Editorial Team", description="Author display name")

    status: ContentStatus = Field(default=ContentStatus.DRAFT)
    readingTimeMinutes: int = Field(default=1, ge=1)

    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)
    publishedAt: Optional[datetime] = Field(default=None)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        matched = next((c for c in SUPPORTED_CATEGORIES if c.lower() == value.strip().lower()), None)
        if not matched:
            raise ValueError(
                f"Invalid category '{value}'. Supported categories: {', '.join(SUPPORTED_CATEGORIES)}"
            )
        return matched

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("createdAt", "updatedAt", "publishedAt", mode="before")
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


class ContentBookmarkDocument(BaseModel):
    """MongoDB document representation for a user's bookmarked article."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    bookmarkId: str = Field(...)
    userId: str = Field(..., description="References users._id")
    contentId: str = Field(..., description="References health_content.contentId or health_content._id")
    createdAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value


def get_health_content_collection(db: Database) -> Collection:
    """Return MongoDB collection for health content."""
    return db["health_content"]


def get_content_bookmark_collection(db: Database) -> Collection:
    """Return MongoDB collection for user content bookmarks."""
    return db["content_bookmarks"]


def create_health_content_indexes(db: Database) -> None:
    """Create indexes for health content articles and user bookmarks."""
    coll = get_health_content_collection(db)
    coll.create_index([("contentId", ASCENDING)], unique=True, name="idx_content_ref_id")
    coll.create_index(
        [("status", ASCENDING), ("publishedAt", DESCENDING)],
        name="idx_content_status_published",
    )
    coll.create_index(
        [("category", ASCENDING), ("status", ASCENDING), ("publishedAt", DESCENDING)],
        name="idx_content_category_status_published",
    )
    coll.create_index(
        [("title", TEXT), ("summary", TEXT), ("tags", TEXT)],
        name="idx_content_text_search",
        default_language="english",
    )

    bm_coll = get_content_bookmark_collection(db)
    bm_coll.create_index([("bookmarkId", ASCENDING)], unique=True, name="idx_bookmark_ref_id")
    bm_coll.create_index(
        [("userId", ASCENDING), ("contentId", ASCENDING)],
        unique=True,
        name="idx_bookmark_user_content_unique",
    )
    bm_coll.create_index(
        [("userId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_bookmark_user_created",
    )
