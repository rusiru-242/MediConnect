import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.user import UserResponseSchema


class PatientRegisterRequest(BaseModel):
    """Request schema for patient registration."""

    model_config = ConfigDict(populate_by_name=True)

    fullName: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(...)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("fullName", mode="before")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Full name must be a string.")
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        if len(trimmed) > 100:
            raise ValueError("Full name cannot exceed 100 characters.")
        return trimmed

    @field_validator("email", mode="before")
    @classmethod
    def validate_and_normalize_email(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Email must be a string.")
        return value.strip().lower()

    @field_validator("phone", mode="before")
    @classmethod
    def validate_and_normalize_phone(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Phone must be a string.")
        clean_phone = re.sub(r"[\s\-()]", "", value)
        
        # Valid Sri Lankan mobile formats:
        # 07X XXXXXXX (10 digits)
        # +94 7X XXXXXXX
        # 94 7X XXXXXXX
        # 0094 7X XXXXXXX
        if re.fullmatch(r"07[0-8]\d{7}", clean_phone):
            return f"+94{clean_phone[1:]}"
        if re.fullmatch(r"\+947[0-8]\d{7}", clean_phone):
            return clean_phone
        if re.fullmatch(r"947[0-8]\d{7}", clean_phone):
            return f"+{clean_phone}"
        if re.fullmatch(r"00947[0-8]\d{7}", clean_phone):
            return f"+{clean_phone[2:]}"
        
        raise ValueError(
            "Invalid Sri Lankan mobile number. Must be a valid 10-digit number (e.g., 0771234567) or in international format (+94771234567)."
        )

    @field_validator("password", mode="after")
    @classmethod
    def validate_strong_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError("Password must contain at least one special character.")
        return value


class PatientRegisterResponse(BaseModel):
    """Response schema returned on successful patient registration."""

    message: str = "Patient registered successfully."
    user: UserResponseSchema
