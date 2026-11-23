"""MongoDB document model and indexes for Smart Follow-up Care Plans (Phase 56)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class CarePlanStatus(str, Enum):
    """Lifecycle statuses for a patient follow-up care plan."""

    ACTIVE = "ACTIVE"
    FOLLOW_UP_BOOKED = "FOLLOW_UP_BOOKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    OVERDUE = "OVERDUE"


class CareTask(BaseModel):
    """Non-medication actionable task assigned to patient."""

    model_config = ConfigDict(populate_by_name=True)

    taskId: str = Field(default_factory=lambda: str(ObjectId()), description="Unique task identifier")
    title: str = Field(..., min_length=2, max_length=200, description="Task title")
    description: Optional[str] = Field(None, max_length=500, description="Optional detailed instructions")
    isCompleted: bool = Field(default=False, description="Completion status")
    completedAt: Optional[datetime] = Field(None, description="Timestamp when task was marked completed")


class CarePlanAuditEntry(BaseModel):
    """Audit trail record for care plan modifications."""

    model_config = ConfigDict(populate_by_name=True)

    action: str = Field(..., description="CREATED, UPDATED, CANCELLED, TASK_COMPLETED, APPOINTMENT_LINKED")
    performedBy: str = Field(..., description="User ID who performed action")
    performedByRole: str = Field(..., description="Role of the actor: DOCTOR, PATIENT, SYSTEM")
    timestamp: datetime = Field(default_factory=utc_now)
    note: Optional[str] = Field(None, description="Optional context or reason")


class CarePlanDocument(BaseModel):
    """MongoDB document representation for a Smart Follow-up Care Plan."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")

    # Patient & Doctor Links
    patientUserId: str = Field(..., description="References users._id of patient")
    doctorUserId: str = Field(..., description="References users._id of doctor")
    doctorProfileId: str = Field(..., description="References doctor_profiles._id")
    appointmentId: str = Field(..., description="References appointments._id of the consultation")

    # Dates
    followUpDate: str = Field(..., description="Target follow-up date YYYY-MM-DD")
    followUpDateEnd: Optional[str] = Field(None, description="Optional date range end YYYY-MM-DD")

    # Clinical details
    reason: str = Field(..., min_length=3, max_length=300, description="Reason for follow-up")
    instructions: str = Field(..., min_length=5, max_length=2000, description="Clinical care instructions")
    recommendedConsultationType: str = Field(default="IN_PERSON", description="IN_PERSON, VIDEO, or AUDIO")

    # Actionable items & records
    tasks: List[CareTask] = Field(default_factory=list, description="Non-medication tasks for patient")
    linkedPrescriptionIds: List[str] = Field(default_factory=list, description="References prescriptions._id")
    linkedMedicalRecordIds: List[str] = Field(default_factory=list, description="References medical_records._id")

    # Follow-up booking connection
    bookedAppointmentId: Optional[str] = Field(None, description="Linked follow-up appointment._id once booked")

    # Status & Audit
    status: CarePlanStatus = Field(default=CarePlanStatus.ACTIVE)
    version: int = Field(default=1, ge=1)
    createdBy: str = Field(..., description="Doctor user id who authored plan")
    updatedBy: str = Field(..., description="User id of last editor")
    auditLog: List[CarePlanAuditEntry] = Field(default_factory=list)
    remindersSent: List[str] = Field(default_factory=list, description="Reminder codes sent: 7D, 1D, DUE")

    # Timestamps
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


def get_care_plan_collection(db: Database) -> Collection:
    """Return the MongoDB 'care_plans' collection."""
    return db["care_plans"]


def create_care_plan_indexes(db: Database) -> None:
    """Create optimized compound indexes for Care Plans."""
    coll = get_care_plan_collection(db)
    coll.create_index([("patientUserId", ASCENDING), ("status", ASCENDING)], name="idx_care_plan_patient_status")
    coll.create_index([("doctorUserId", ASCENDING), ("status", ASCENDING)], name="idx_care_plan_doctor_status")
    coll.create_index([("appointmentId", ASCENDING)], name="idx_care_plan_appointment")
    coll.create_index([("followUpDate", ASCENDING), ("status", ASCENDING)], name="idx_care_plan_date_status")
    coll.create_index([("bookedAppointmentId", ASCENDING)], sparse=True, name="idx_care_plan_booked_appt")
