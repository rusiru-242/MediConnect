"""MongoDB document models and index creators for Phase 7: Workflow Monitoring & Safe Recovery."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone."""
    return datetime.now(timezone.utc)


class WorkflowType(str, Enum):
    """Types of tracked core business workflows."""
    AI_BOOKING = "AI_BOOKING"
    BOOKING_HOLD = "BOOKING_HOLD"
    PAYMENT_VERIFICATION = "PAYMENT_VERIFICATION"
    APPOINTMENT_CONFIRMATION = "APPOINTMENT_CONFIRMATION"
    MEDICATION_REMINDER_SYNC = "MEDICATION_REMINDER_SYNC"
    CARE_TASK_UPDATE = "CARE_TASK_UPDATE"
    DOCTOR_QUEUE = "DOCTOR_QUEUE"
    DOCTOR_VERIFICATION = "DOCTOR_VERIFICATION"
    REFUND_PROCESSING = "REFUND_PROCESSING"
    PRESCRIPTION_RENEWAL = "PRESCRIPTION_RENEWAL"
    CLINICAL_NOTE_SIGNING = "CLINICAL_NOTE_SIGNING"


class WorkflowStatus(str, Enum):
    """Statuses for monitored workflows."""
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    STUCK = "STUCK"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    RECOVERED = "RECOVERED"


class WorkflowMonitoringDocument(BaseModel):
    """Document tracking the lifecycle and health of an automated healthcare workflow."""
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True, arbitrary_types_allowed=True)

    id: Optional[str] = Field(default=None, alias="_id")
    workflowId: str = Field(..., description="Unique workflow identifier, e.g. WF-UUID")
    workflowType: WorkflowType
    status: WorkflowStatus = Field(default=WorkflowStatus.STARTED)
    relatedEntityId: str = Field(..., description="Target business entity ID, e.g. appointment or payment ID")
    retryCount: int = Field(default=0, ge=0)
    maxRetries: int = Field(default=3, ge=1)
    errorCategory: Optional[str] = None
    errorMessage: Optional[str] = None
    startedAt: datetime = Field(default_factory=utc_now)
    lastUpdatedAt: datetime = Field(default_factory=utc_now)
    completedAt: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def create_workflow_monitoring_indexes(db: Database) -> None:
    """Create indexes for workflow monitoring collection."""
    collection = db["workflow_monitoring_events"]
    collection.create_index([("workflowId", ASCENDING)], unique=True, name="idx_wf_monitoring_id")
    collection.create_index([("workflowType", ASCENDING), ("status", ASCENDING)], name="idx_wf_monitoring_type_status")
    collection.create_index([("relatedEntityId", ASCENDING)], name="idx_wf_monitoring_entity")
    collection.create_index([("lastUpdatedAt", DESCENDING)], name="idx_wf_monitoring_updated")
