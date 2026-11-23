"""MongoDB document model and indexes for payment refund requests and tracking (Phase 5)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database


class RefundStatus(str, Enum):
    REQUESTED = "requested"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class RefundPolicyResult(BaseModel):
    """Deterministic refund policy calculation details."""
    eligible: bool
    eligibleAmount: float
    penaltyAmount: float = 0.0
    ruleApplied: str
    isDisputed: bool = False
    alreadyRefunded: bool = False


class RefundRequestDocument(BaseModel):
    """MongoDB document representation of a Refund Request."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    refundId: str = Field(..., description="Unique reference code, e.g. REF-...")
    paymentId: str = Field(..., description="References payments._id")
    appointmentId: str = Field(..., description="References appointments._id")
    patientUserId: str = Field(..., description="References users._id")
    patientName: str = Field(default="")
    amount: float = Field(..., ge=0, description="Original requested refund amount")
    currency: str = Field(default="LKR")
    reason: str = Field(..., min_length=3, max_length=1000)
    status: RefundStatus = Field(default=RefundStatus.REQUESTED)
    policyEligibility: Optional[RefundPolicyResult] = Field(default=None)
    aiSummary: Optional[Dict[str, Any]] = Field(default=None, description="AI-assisted review narrative and risk checks")
    stripeRefundId: Optional[str] = Field(default=None)
    idempotencyKey: str = Field(..., description="Unique idempotency key for preventing duplicate Stripe refunds")
    adminReviewerId: Optional[str] = Field(default=None)
    reviewNotes: Optional[str] = Field(default=None)
    failureReason: Optional[str] = Field(default=None)
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)
    completedAt: Optional[datetime] = Field(default=None)


def create_refund_request_indexes(db: Database) -> None:
    """Create essential MongoDB indexes for refund requests."""
    coll = db["refund_requests"]
    coll.create_index([("refundId", ASCENDING)], unique=True)
    coll.create_index([("paymentId", ASCENDING)])
    coll.create_index([("appointmentId", ASCENDING)])
    coll.create_index([("patientUserId", ASCENDING)])
    coll.create_index([("status", ASCENDING)])
    coll.create_index([("idempotencyKey", ASCENDING)], unique=True, sparse=True)
    coll.create_index([("createdAt", DESCENDING)])
