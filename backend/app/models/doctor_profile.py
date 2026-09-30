from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class DoctorVerificationStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class DoctorProfileDocument(BaseModel):
    """MongoDB document representation for a Doctor Profile."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    userId: str = Field(..., description="References users._id")
    doctorId: str = Field(..., description="Unique human-readable doctor identifier")
    specialty: str = Field(..., min_length=1)
    medicalRegistrationNumber: str = Field(..., min_length=1)
    qualifications: str = Field(..., min_length=1)
    hospitalOrClinic: str = Field(..., min_length=1)
    experienceYears: int = Field(default=0, ge=0, le=70)
    bio: Optional[str] = Field(default=None, max_length=1000)
    verificationDocuments: Dict[str, Any] = Field(default_factory=dict)
    verificationStatus: DoctorVerificationStatus = Field(default=DoctorVerificationStatus.PENDING)
    rejectionReason: Optional[str] = Field(default=None)
    submittedAt: datetime = Field(default_factory=utc_now)
    verifiedAt: Optional[datetime] = None
    verifiedBy: Optional[str] = Field(default=None, description="Admin userId who verified the application")
    previousStatus: Optional[str] = Field(default=None, description="Previous verification status for audit")
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("submittedAt", "verifiedAt", "createdAt", "updatedAt", mode="before")
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


def get_doctor_profile_collection(db: Database) -> Collection:
    """Return the MongoDB 'doctor_profiles' collection."""
    return db["doctor_profiles"]


def create_doctor_profile_indexes(db: Database) -> None:
    """Create indexes on doctor_profiles collection for uniqueness and lookups."""
    collection = get_doctor_profile_collection(db)
    collection.create_index(
        [("userId", ASCENDING)],
        unique=True,
        name="idx_doctor_profiles_user_id_unique",
    )
    collection.create_index(
        [("medicalRegistrationNumber", ASCENDING)],
        unique=True,
        name="idx_doctor_profiles_med_reg_no_unique",
    )
    collection.create_index(
        [("doctorId", ASCENDING)],
        unique=True,
        name="idx_doctor_profiles_doctor_id_unique",
    )
    collection.create_index(
        [("specialty", ASCENDING)],
        name="idx_doctor_profiles_specialty",
    )
    collection.create_index(
        [("verificationStatus", ASCENDING)],
        name="idx_doctor_profiles_verification_status",
    )
