"""MongoDB document model and indexes for doctor availability."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class DoctorAvailabilityDocument(BaseModel):
    """MongoDB document representation for Doctor Availability."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    doctorUserId: str = Field(..., description="References users._id")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    date: str = Field(..., description="Date in YYYY-MM-DD format (Sri Lanka local date)")
    startTime: str = Field(..., description="Start time in HH:MM format (24-hour)")
    endTime: str = Field(..., description="End time in HH:MM format (24-hour)")
    slotDurationMinutes: int = Field(default=30, description="Duration per appointment slot in minutes")
    isActive: bool = Field(default=True, description="Availability status toggle")
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("createdAt", "updatedAt", mode="before")
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


def get_doctor_availability_collection(db: Database) -> Collection:
    """Return the MongoDB 'doctor_availabilities' collection."""
    return db["doctor_availabilities"]


def create_doctor_availability_indexes(db: Database) -> None:
    """Create indexes on doctor_availabilities collection."""
    collection = get_doctor_availability_collection(db)
    collection.create_index(
        [("doctorUserId", ASCENDING), ("date", ASCENDING), ("isActive", ASCENDING)],
        name="idx_doctor_avail_user_date_active",
    )
    collection.create_index(
        [("doctorProfileId", ASCENDING), ("date", ASCENDING), ("isActive", ASCENDING)],
        name="idx_doctor_avail_profile_date_active",
    )
    collection.create_index(
        [("date", ASCENDING), ("isActive", ASCENDING)],
        name="idx_doctor_avail_date_active",
    )
