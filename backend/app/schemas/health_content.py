"""Pydantic schemas for Health & Wellness Content Management (Phase 24)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.health_content import ContentStatus, SUPPORTED_CATEGORIES


class CreateContentRequest(BaseModel):
    """Admin payload to create a new health article."""

    title: str = Field(..., min_length=3, max_length=250, description="Article title")
    summary: str = Field(..., min_length=10, max_length=600, description="Brief summary")
    body: str = Field(..., min_length=20, max_length=50000, description="Full article markdown/text")
    category: str = Field(..., description="Category from SUPPORTED_CATEGORIES")
    coverImage: Optional[str] = Field(default=None, max_length=1000)
    tags: List[str] = Field(default_factory=list)
    sources: Optional[str] = Field(default=None, max_length=1000)
    status: ContentStatus = Field(default=ContentStatus.DRAFT)

    @field_validator("category")
    @classmethod
    def validate_category(cls, val: str) -> str:
        matched = next((c for c in SUPPORTED_CATEGORIES if c.lower() == val.strip().lower()), None)
        if not matched:
            raise ValueError(f"Invalid category '{val}'. Valid options: {', '.join(SUPPORTED_CATEGORIES)}")
        return matched

    @field_validator("title", "summary", "body")
    @classmethod
    def strip_text(cls, val: str) -> str:
        return val.strip()


class UpdateContentRequest(BaseModel):
    """Admin payload to edit an existing health article."""

    title: Optional[str] = Field(default=None, min_length=3, max_length=250)
    summary: Optional[str] = Field(default=None, min_length=10, max_length=600)
    body: Optional[str] = Field(default=None, min_length=20, max_length=50000)
    category: Optional[str] = None
    coverImage: Optional[str] = Field(default=None, max_length=1000)
    tags: Optional[List[str]] = None
    sources: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[ContentStatus] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, val: Optional[str]) -> Optional[str]:
        if val is None:
            return None
        matched = next((c for c in SUPPORTED_CATEGORIES if c.lower() == val.strip().lower()), None)
        if not matched:
            raise ValueError(f"Invalid category '{val}'. Valid options: {', '.join(SUPPORTED_CATEGORIES)}")
        return matched


class ContentResponse(BaseModel):
    """Full article response schema."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    contentId: str
    title: str
    summary: str
    body: str
    category: str
    coverImage: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    sources: Optional[str] = None
    authorAdminId: str
    authorName: Optional[str] = "MediConnect Team"
    status: ContentStatus
    readingTimeMinutes: int = 1
    createdAt: datetime
    updatedAt: datetime
    publishedAt: Optional[datetime] = None
    isBookmarked: bool = False

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value


class ContentSummaryItem(BaseModel):
    """Card item schema for article feeds and lists."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    contentId: str
    title: str
    summary: str
    category: str
    coverImage: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    authorName: Optional[str] = "MediConnect Team"
    readingTimeMinutes: int = 1
    status: ContentStatus
    createdAt: datetime
    publishedAt: Optional[datetime] = None
    isBookmarked: bool = False

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value


class CategoryCountItem(BaseModel):
    """Category name and published article count."""
    category: str
    count: int


class ContentListResponse(BaseModel):
    """Paginated response for article listings."""

    items: List[ContentSummaryItem]
    total: int
    page: int
    pageSize: int
    totalPages: int
    categories: List[CategoryCountItem] = Field(default_factory=list)


class BookmarkActionResponse(BaseModel):
    """Bookmark toggle response."""
    success: bool
    isBookmarked: bool
    message: str
