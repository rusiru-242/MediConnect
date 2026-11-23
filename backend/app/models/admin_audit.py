"""MongoDB document model and indexes for administrative audit logging (Phase 5)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database


class AdminAuditAction(str, Enum):
    DOCTOR_VERIFICATION_DECISION = "DOCTOR_VERIFICATION_DECISION"
    REFUND_APPROVAL = "REFUND_APPROVAL"
    REFUND_REJECTION = "REFUND_REJECTION"
    REFUND_EXECUTION = "REFUND_EXECUTION"
    SUPPORT_TICKET_RESOLVED = "SUPPORT_TICKET_RESOLVED"
    SUPPORT_RESPONSE_SENT = "SUPPORT_RESPONSE_SENT"
    PAYMENT_RECONCILIATION_ACTION = "PAYMENT_RECONCILIATION_ACTION"
    USER_STATUS_CHANGE = "USER_STATUS_CHANGE"
    REPORT_GENERATED = "REPORT_GENERATED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class AdminAuditDocument(BaseModel):
    """Immutable audit trail document recording sensitive administrative operations."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    auditId: str = Field(..., description="Unique audit event reference, e.g. AUD-...")
    actorId: str = Field(..., description="User ID of the admin actor")
    actorEmail: Optional[str] = Field(default=None)
    actorRole: str = Field(default="ADMIN")
    actionType: AdminAuditAction = Field(...)
    targetId: str = Field(..., description="ID of affected entity")
    targetType: str = Field(..., description="doctor_profile, refund_request, support_ticket, payment, user, report")
    previousState: Optional[str] = Field(default=None)
    newState: Optional[str] = Field(default=None)
    reason: Optional[str] = Field(default=None)
    correlationId: Optional[str] = Field(default=None)
    status: str = Field(default="SUCCESS")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Sanitized metadata without secrets or full card details")
    timestamp: datetime = Field(default_factory=utc_now)


def create_admin_audit_indexes(db: Database) -> None:
    """Create essential MongoDB indexes for administrative audit logs."""
    coll = db["admin_audit_logs"]
    coll.create_index([("auditId", ASCENDING)], unique=True)
    coll.create_index([("actionType", ASCENDING), ("timestamp", DESCENDING)])
    coll.create_index([("targetType", ASCENDING), ("targetId", ASCENDING)])
    coll.create_index([("actorId", ASCENDING), ("timestamp", DESCENDING)])
    coll.create_index([("timestamp", DESCENDING)])
