"""MongoDB document model and indexes for doctor weekly recurring schedules."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class WorkingSession(BaseModel):
    """A working consultation window within a day."""

    startTime: str = Field(..., description="Start time in HH:MM format (24-hour)")
    endTime: str = Field(..., description="End time in HH:MM format (24-hour)")


class WeekdaySchedule(BaseModel):
    """Working schedule configuration for a specific weekday."""

    day: str = Field(..., description="monday, tuesday, wednesday, thursday, friday, saturday, sunday")
    isEnabled: bool = Field(default=True, description="Whether doctor is available on this day")
    sessions: List[WorkingSession] = Field(default_factory=list, description="Working sessions for the day")


class DoctorWeeklyScheduleDocument(BaseModel):
    """MongoDB document representation for doctor recurring weekly schedule."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    doctorUserId: str = Field(..., description="References users._id")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    timezone: str = Field(default="Asia/Colombo", description="Configured IANA time zone")
    slotDurationMinutes: int = Field(default=30, description="Duration per appointment slot in minutes (10-120)")
    weekdays: List[WeekdaySchedule] = Field(default_factory=list, description="Weekly schedule config for 7 days")
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


def get_doctor_weekly_schedule_collection(db: Database) -> Collection:
    """Return MongoDB collection for doctor weekly schedules."""
    return db["doctor_weekly_schedules"]


def create_doctor_weekly_schedule_indexes(db: Database) -> None:
    """Create indexes for doctor weekly schedules collection."""
    coll = get_doctor_weekly_schedule_collection(db)
    coll.create_index([("doctorUserId", ASCENDING)], unique=True, name="idx_weekly_schedule_doctor_user_id")
    coll.create_index([("doctorProfileId", ASCENDING)], name="idx_weekly_schedule_doctor_profile_id")
