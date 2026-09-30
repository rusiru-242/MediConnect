from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import AccountStatus, UserRole, utc_now


class UserBaseSchema(BaseModel):
    """Shared user attributes across input and output schemas."""

    model_config = ConfigDict(populate_by_name=True)

    fullName: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=30)
    role: UserRole = Field(default=UserRole.PATIENT)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("fullName", mode="before")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class UserCreateSchema(UserBaseSchema):
    """Input schema for creating a new user."""

    password: str = Field(..., min_length=8, max_length=128)


class UserInDBSchema(UserBaseSchema):
    """Database schema representing a stored user (internal use only)."""

    id: str = Field(..., alias="_id")
    passwordHash: str = Field(..., exclude=True)
    emailVerified: bool = Field(default=False)
    accountStatus: AccountStatus = Field(default=AccountStatus.PENDING)
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def stringify_id(cls, value: Any) -> str:
        return str(value)

    @field_validator("createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


class UserResponseSchema(UserBaseSchema):
    """Public API output schema for User. Never includes passwordHash."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str
    emailVerified: bool
    accountStatus: AccountStatus
    createdAt: datetime
    updatedAt: datetime

    @field_validator("id", mode="before")
    @classmethod
    def stringify_id(cls, value: Any) -> str:
        return str(value)

    @field_validator("createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value
