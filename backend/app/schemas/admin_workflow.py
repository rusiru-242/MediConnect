"""Pydantic schemas for Admin AI Automation, Verification, Analytics, and Operations (Phase 5)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated


class StrictModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


# -----------------------------------------------------------------------------
# Support Ticket Schemas
# -----------------------------------------------------------------------------

class CreateSupportTicketRequest(StrictModel):
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=4000)]
    category: Optional[str] = Field(default="general_support")
    priority: Optional[str] = Field(default="medium")
    relatedEntityId: Optional[str] = Field(default=None)


class ReplySupportTicketRequest(StrictModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    status: Optional[Literal["in_progress", "waiting_for_user", "resolved", "closed"]] = Field(
        default=None, description="Optional new status (in_progress, waiting_for_user, resolved, closed)")
    resolve: Optional[bool] = Field(default=False)


class SupportMessageSchema(StrictModel):
    messageId: str
    senderId: str
    senderRole: str
    senderName: Optional[str] = None
    message: str
    sentAt: datetime


class SupportTicketResponse(StrictModel):
    id: str
    ticketId: str
    requesterId: str
    requesterRole: str
    requesterEmail: str = ""
    requesterName: str = ""
    category: str
    subject: str
    description: str
    status: str
    priority: str
    assignedAdminId: Optional[str] = None
    relatedEntityId: Optional[str] = None
    messages: List[SupportMessageSchema] = Field(default_factory=list)
    aiDraft: Optional[Dict[str, Any]] = None
    createdAt: datetime
    updatedAt: datetime
    resolvedAt: Optional[datetime] = None


class SupportTicketListResponse(StrictModel):
    items: List[SupportTicketResponse]
    total: int
    page: int
    pageSize: int


class AIDraftSupportResponse(StrictModel):
    ticketId: str
    suggestedCategory: str
    suggestedPriority: str
    issueSummary: str
    suggestedResolution: str
    draftResponse: str
    flags: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Refund Schemas
# -----------------------------------------------------------------------------

class CreateRefundRequest(StrictModel):
    appointmentId: str
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


class ApproveRefundRequest(StrictModel):
    approvedAmount: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class RejectRefundRequest(StrictModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


class RefundPolicyResultSchema(StrictModel):
    eligible: bool
    eligibleAmount: float
    penaltyAmount: float = 0.0
    ruleApplied: str
    isDisputed: bool = False
    alreadyRefunded: bool = False


class RefundRequestResponse(StrictModel):
    id: str
    refundId: str
    paymentId: str
    appointmentId: str
    patientUserId: str
    patientName: str = ""
    amount: float
    currency: str
    reason: str
    status: str
    policyEligibility: Optional[RefundPolicyResultSchema] = None
    aiSummary: Optional[Dict[str, Any]] = None
    stripeRefundId: Optional[str] = None
    idempotencyKey: str
    adminReviewerId: Optional[str] = None
    reviewNotes: Optional[str] = None
    failureReason: Optional[str] = None
    source: Optional[str] = Field(default=None, description="patient, doctor, leave or admin; None for legacy requests")
    cancelledBy: Optional[str] = None
    cancellationReason: Optional[str] = None
    approvedAmount: Optional[float] = None
    refundedAmount: Optional[float] = None
    stripeRefundStatus: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    completedAt: Optional[datetime] = None


class RefundRequestListResponse(StrictModel):
    items: List[RefundRequestResponse]
    total: int
    page: int
    pageSize: int


# -----------------------------------------------------------------------------
# Payment Monitoring & Reconciliation Schemas
# -----------------------------------------------------------------------------

class MonitoredPaymentItem(StrictModel):
    id: str
    paymentId: str
    appointmentId: Optional[str] = None
    stripePaymentIntentId: str
    amount: float
    currency: str
    status: str
    bookingStatus: Optional[str] = None
    patientName: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    isRefunded: bool = False


class ReconciliationDiscrepancy(StrictModel):
    discrepancyId: str
    type: str  # UNCONFIRMED_PAID_APPOINTMENT, MISSING_PAYMENT_EVIDENCE, DUPLICATE_PAYMENT, HOLD_EXPIRED_PAYMENT, STALE_REFUND, DELAYED_PENDING
    severity: str  # HIGH, MEDIUM, LOW
    paymentId: Optional[str] = None
    appointmentId: Optional[str] = None
    stripePaymentIntentId: Optional[str] = None
    description: str
    recommendation: str
    detectedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReconciliationReportResponse(StrictModel):
    discrepancies: List[ReconciliationDiscrepancy]
    totalChecked: int
    discrepanciesCount: int
    checkedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -----------------------------------------------------------------------------
# Doctor Verification Assistant Schemas
# -----------------------------------------------------------------------------

class DoctorVerificationAIDecision(StrictModel):
    doctorProfileId: str
    doctorName: str
    completenessScore: int = Field(ge=0, le=100)
    fieldCompleteness: Dict[str, bool]
    documentChecklist: Dict[str, bool]
    missingDocuments: List[str]
    inconsistencies: List[str]
    riskFlags: List[str]
    needsManualExternalCheck: bool = True
    summary: str
    recommendedAction: str  # APPROVE, REJECT, REQUEST_INFO, MANUAL_VERIFY
    registrationOfficiallyVerified: bool = False
    humanDecisionRequired: bool = True


# -----------------------------------------------------------------------------
# Operational Report Schemas
# -----------------------------------------------------------------------------

class GenerateReportRequest(StrictModel):
    # Only implemented reports. "weekly_booking" was accepted and silently answered with the refund report (P04-N17).
    reportType: Literal["daily_appointment", "monthly_payment", "doctor_verification_backlog",
                        "support_ticket_resolution", "refund_status"]
    startDate: Optional[str] = None
    endDate: Optional[str] = None


class AdminReportResponse(StrictModel):
    reportId: str
    reportType: str
    title: str
    dateRange: Dict[str, str]
    generatedAt: datetime
    dataDefinitions: Dict[str, str]
    metrics: Dict[str, Any]
    items: List[Dict[str, Any]]
    aiSummary: Optional[str] = None


# -----------------------------------------------------------------------------
# Admin AI Assistant Chat Schemas
# -----------------------------------------------------------------------------

class AdminAssistantChatRequest(StrictModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    contextFilter: Optional[Dict[str, Any]] = None


class AdminAssistantChatResponse(StrictModel):
    reply: str
    toolCalled: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    dateRange: Optional[Dict[str, str]] = None
    actionSuggestions: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Admin Audit Log Schemas
# -----------------------------------------------------------------------------

class AdminAuditLogItem(StrictModel):
    id: str
    auditId: str
    actorId: str
    actorEmail: Optional[str] = None
    actorRole: str
    actionType: str
    targetId: str
    targetType: str
    previousState: Optional[str] = None
    newState: Optional[str] = None
    reason: Optional[str] = None
    correlationId: Optional[str] = None
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class AdminAuditLogListResponse(StrictModel):
    items: List[AdminAuditLogItem]
    total: int
    page: int
    pageSize: int
