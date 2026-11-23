"""MongoDB document model and indexes for doctor leave management."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class LeaveType(str, Enum):
    """Supported types of doctor leave."""

    PERSONAL = "PERSONAL"
    MEDICAL = "MEDICAL"
    VACATION = "VACATION"
    PUBLIC_HOLIDAY = "PUBLIC_HOLIDAY"
    OTHER = "OTHER"


class LeaveStatus(str, Enum):
    """Status of doctor leave record."""

    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class DoctorLeaveDocument(BaseModel):
    """MongoDB document representation for doctor leave."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    doctorUserId: str = Field(..., description="References users._id")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    leaveType: LeaveType = Field(default=LeaveType.PERSONAL)
    startDate: str = Field(..., description="Start date in YYYY-MM-DD format")
    endDate: str = Field(..., description="End date in YYYY-MM-DD format")
    startTime: Optional[str] = Field(default=None, description="Optional start time HH:MM for partial-day leave")
    endTime: Optional[str] = Field(default=None, description="Optional end time HH:MM for partial-day leave")
    reason: Optional[str] = Field(default=None, description="Doctor's private reason for leave")
    status: LeaveStatus = Field(default=LeaveStatus.ACTIVE)
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


def get_doctor_leave_collection(db: Database) -> Collection:
    """Return MongoDB collection for doctor leaves."""
    return db["doctor_leaves"]


def create_doctor_leave_indexes(db: Database) -> None:
    """Create indexes for doctor leaves collection."""
    coll = get_doctor_leave_collection(db)
    coll.create_index(
        [("doctorUserId", ASCENDING), ("status", ASCENDING), ("startDate", ASCENDING), ("endDate", ASCENDING)],
        name="idx_doctor_leave_lookup",
    )
    coll.create_index([("doctorProfileId", ASCENDING)], name="idx_doctor_leave_profile")
