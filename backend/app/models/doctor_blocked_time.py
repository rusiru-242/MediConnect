"""MongoDB document model and indexes for doctor blocked time ranges."""

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


class DoctorBlockedTimeDocument(BaseModel):
    """MongoDB document representation for doctor blocked time slot/interval."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    doctorUserId: str = Field(..., description="References users._id")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    startTime: str = Field(..., description="Start time HH:MM format")
    endTime: str = Field(..., description="End time HH:MM format")
    reason: Optional[str] = Field(default=None, description="Optional note for blocked period")
    createdAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("createdAt", mode="before")
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


def get_doctor_blocked_time_collection(db: Database) -> Collection:
    """Return MongoDB collection for doctor blocked times."""
    return db["doctor_blocked_times"]


def create_doctor_blocked_time_indexes(db: Database) -> None:
    """Create indexes for doctor blocked times collection."""
    coll = get_doctor_blocked_time_collection(db)
    coll.create_index(
        [("doctorUserId", ASCENDING), ("date", ASCENDING), ("startTime", ASCENDING)],
        name="idx_doctor_blocked_time_lookup",
    )
