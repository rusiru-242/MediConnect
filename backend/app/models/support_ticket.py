"""MongoDB document model and indexes for customer support tickets (Phase 5)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database


class TicketCategory(str, Enum):
    APPOINTMENT_ISSUE = "appointment_issue"
    PAYMENT_ISSUE = "payment_issue"
    REFUND_REQUEST = "refund_request"
    DOCTOR_VERIFICATION = "doctor_verification"
    ACCOUNT_ACCESS = "account_access"
    NOTIFICATION_ISSUE = "notification_issue"
    GENERAL_SUPPORT = "general_support"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_USER = "waiting_for_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class SupportMessage(BaseModel):
    """A message in a support ticket thread."""
    messageId: str = Field(default_factory=lambda: ObjectId().binary.hex())
    senderId: str
    senderRole: str  # PATIENT, DOCTOR, ADMIN, SYSTEM
    senderName: Optional[str] = None
    message: str
    sentAt: datetime = Field(default_factory=utc_now)


class SupportTicketDocument(BaseModel):
    """MongoDB document for customer support tickets."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    ticketId: str = Field(..., description="Unique ticket reference code, e.g. TCK-...")
    requesterId: str = Field(..., description="References users._id")
    requesterRole: str = Field(..., description="Role of requester (PATIENT, DOCTOR)")
    requesterEmail: str = Field(default="")
    requesterName: str = Field(default="")
    category: TicketCategory = Field(default=TicketCategory.GENERAL_SUPPORT)
    subject: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=5, max_length=4000)
    status: TicketStatus = Field(default=TicketStatus.OPEN)
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM)
    assignedAdminId: Optional[str] = Field(default=None)
    relatedEntityId: Optional[str] = Field(default=None, description="Optional appointmentId, paymentId, etc.")
    messages: List[SupportMessage] = Field(default_factory=list)
    aiDraft: Optional[Dict[str, Any]] = Field(default=None, description="AI-assisted draft response and classification")
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)
    resolvedAt: Optional[datetime] = Field(default=None)


def create_support_ticket_indexes(db: Database) -> None:
    """Create essential MongoDB indexes for support tickets."""
    coll = db["support_tickets"]
    coll.create_index([("ticketId", ASCENDING)], unique=True)
    coll.create_index([("requesterId", ASCENDING), ("status", ASCENDING)])
    coll.create_index([("category", ASCENDING), ("status", ASCENDING)])
    coll.create_index([("priority", ASCENDING), ("status", ASCENDING)])
    coll.create_index([("createdAt", DESCENDING)])
    coll.create_index([("updatedAt", DESCENDING)], name="idx_support_tickets_updated")
    # A05-BUG-007: the same requester submitting the same subject and message twice (double tap, retry after a
    # timeout) created two tickets. ``openDedupeKey`` exists while the ticket is open and is removed on resolve/close.
    coll.create_index([("openDedupeKey", ASCENDING)], unique=True, name="idx_support_tickets_open_dedupe",
                      partialFilterExpression={"openDedupeKey": {"$exists": True}})
