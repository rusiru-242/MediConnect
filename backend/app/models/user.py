from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class UserRole(str, Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    SUSPENDED = "SUSPENDED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class UserDocument(BaseModel):
    """Internal MongoDB document representation for a User."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    fullName: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=30)
    passwordHash: Optional[str] = Field(default=None)
    role: UserRole = Field(default=UserRole.PATIENT)
    emailVerified: bool = Field(default=False)
    accountStatus: AccountStatus = Field(default=AccountStatus.PENDING)
    authProviders: list[str] = Field(default_factory=lambda: ["LOCAL"])
    googleSub: Optional[str] = None
    profileImage: Optional[str] = None
    emailVerification: Optional[Dict[str, Any]] = None
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> datetime:
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
        data["email"] = data["email"].lower()
        return data


def get_user_collection(db: Database) -> Collection:
    """Return the MongoDB 'users' collection."""
    return db["users"]


def create_user_indexes(db: Database) -> None:
    """Create indexes on users collection for unique email and googleSub."""
    collection = get_user_collection(db)
    collection.create_index(
        [("email", ASCENDING)],
        unique=True,
        name="idx_users_email_unique",
    )
    collection.create_index(
        [("googleSub", ASCENDING)],
        unique=True,
        sparse=True,
        name="idx_users_google_sub_unique",
    )
