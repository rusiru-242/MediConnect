"""Pydantic schemas for Phase 7: Advanced Security, Fraud Detection, Monitoring & Reliability."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.fraud_assessment import FraudRiskLevel, FraudReviewStatus
from app.models.operational_incident import IncidentCategory, IncidentSeverity, IncidentStatus
from app.models.security_event import SecurityEventCategory, SecuritySeverity, utc_now
from app.models.workflow_monitoring import WorkflowStatus, WorkflowType


class StrictBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)


# ---------------------------------------------------------------------------
# 1. Security Event Schemas
# ---------------------------------------------------------------------------

class SecurityEventCreateRequest(StrictBase):
    category: SecurityEventCategory
    severity: SecuritySeverity
    actorId: Optional[str] = None
    actorRole: Optional[str] = None
    ipAddress: Optional[str] = None
    endpoint: Optional[str] = None
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SecurityEventResponse(StrictBase):
    eventId: str
    category: str
    severity: str
    actorId: Optional[str] = None
    actorRole: Optional[str] = None
    ipAddress: Optional[str] = None
    endpoint: Optional[str] = None
    description: str
    metadata: Dict[str, Any]
    timestamp: datetime


class SecurityEventListResponse(StrictBase):
    items: List[SecurityEventResponse]
    total: int


# ---------------------------------------------------------------------------
# 2. Fraud Detection & Assessment Schemas
# ---------------------------------------------------------------------------

class FraudAssessmentResponse(StrictBase):
    assessmentId: str
    relatedAccountId: Optional[str] = None
    relatedEntityReference: str
    riskScore: float
    riskLevel: str
    triggeredRules: List[str]
    supportingEventReferences: List[str]
    explanation: str
    reviewStatus: str
    investigationNotes: List[Dict[str, Any]]
    assignedAdminId: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime


class FraudAssessmentListResponse(StrictBase):
    items: List[FraudAssessmentResponse]
    total: int


class FraudReviewDecisionRequest(StrictBase):
    decision: str = Field(..., description="'dismiss', 'confirm', 'investigate', or 'resolve'")
    notes: str = Field(..., min_length=3, max_length=1000)
    actionRequired: Optional[str] = None


# ---------------------------------------------------------------------------
# 3. Operational Incident Schemas
# ---------------------------------------------------------------------------

class OperationalIncidentCreateRequest(StrictBase):
    title: str = Field(..., min_length=3, max_length=200)
    category: IncidentCategory
    severity: IncidentSeverity
    description: str
    affectedService: str
    supportingEventReferences: List[str] = Field(default_factory=list)


class IncidentUpdateRequest(StrictBase):
    status: Optional[IncidentStatus] = None
    assignedAdminId: Optional[str] = None
    resolutionNotes: Optional[str] = None


class OperationalIncidentResponse(StrictBase):
    incidentId: str
    title: str
    category: str
    severity: str
    status: str
    description: str
    affectedService: str
    supportingEventReferences: List[str]
    assignedAdminId: Optional[str] = None
    resolutionNotes: Optional[str] = None
    createdAt: datetime
    acknowledgedAt: Optional[datetime] = None
    resolvedAt: Optional[datetime] = None


class OperationalIncidentListResponse(StrictBase):
    items: List[OperationalIncidentResponse]
    total: int


# ---------------------------------------------------------------------------
# 4. Platform Monitoring Schemas
# ---------------------------------------------------------------------------

class DependencyHealth(StrictBase):
    name: str
    status: str  # healthy, degraded, unavailable, unconfigured
    latencyMs: Optional[float] = None
    message: Optional[str] = None


class WorkerHeartbeatResponse(StrictBase):
    workerName: str
    status: str  # active, stale, stopped
    lastHeartbeat: datetime
    lastDurationSeconds: float
    pendingJobCount: int
    failedJobCount: int


class PlatformHealthResponse(StrictBase):
    status: str  # healthy, degraded, critical
    uptimeSeconds: float
    timestamp: datetime
    dependencies: List[DependencyHealth]
    workers: List[WorkerHeartbeatResponse]
    activeIncidentsCount: int
    openFraudAssessmentsCount: int


# ---------------------------------------------------------------------------
# 5. Notification Monitoring Schemas
# ---------------------------------------------------------------------------

class NotificationStateMetrics(StrictBase):
    channel: str
    pending: int = 0
    processing: int = 0
    delivered: int = 0
    failed: int = 0
    retryScheduled: int = 0
    deadLettered: int = 0
    total: int = 0


class NotificationMonitoringMetricsResponse(StrictBase):
    timestamp: datetime
    byChannel: List[NotificationStateMetrics]
    totalBacklog: int
    failureRatePercent: float
    deadLetterQueueCount: int


class DeadLetterNotificationResponse(StrictBase):
    deadLetterId: str
    notificationId: Optional[str] = None
    recipientUserId: str
    channel: str
    reason: str
    retryCount: int
    createdAt: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationRetryResponse(StrictBase):
    success: bool
    retriedCount: int
    message: str


# ---------------------------------------------------------------------------
# 6. Workflow Monitoring & Recovery Schemas
# ---------------------------------------------------------------------------

class WorkflowMonitoringResponse(StrictBase):
    workflowId: str
    workflowType: str
    status: str
    relatedEntityId: str
    retryCount: int
    maxRetries: int
    errorCategory: Optional[str] = None
    errorMessage: Optional[str] = None
    startedAt: datetime
    lastUpdatedAt: datetime
    completedAt: Optional[datetime] = None
    metadata: Dict[str, Any]


class WorkflowRecoveryRequest(StrictBase):
    workflowId: str
    force: bool = False
    recoveryReason: str


class WorkflowRecoveryResponse(StrictBase):
    workflowId: str
    previousStatus: str
    currentStatus: str
    recovered: bool
    actionTaken: str
    message: str


# ---------------------------------------------------------------------------
# 7. AI Provider Reliability Schemas
# ---------------------------------------------------------------------------

class AIProviderMetricsResponse(StrictBase):
    provider: str  # gemini, openai, fallback
    status: str  # healthy, degraded, circuit_open
    circuitBreakerState: str  # CLOSED, OPEN, HALF_OPEN
    totalRequests: int
    successfulRequests: int
    failedRequests: int
    averageLatencyMs: float
    fallbackActivations: int
    lastError: Optional[str] = None
    lastErrorTimestamp: Optional[datetime] = None


# ---------------------------------------------------------------------------
# 8. Admin AI Monitoring Chat Schemas
# ---------------------------------------------------------------------------

class AdminMonitoringChatRequest(StrictBase):
    message: str = Field(..., min_length=1, max_length=1000)


class AdminMonitoringChatResponse(StrictBase):
    intent: str
    response: str
    relevantMetrics: Optional[Dict[str, Any]] = None
    suggestedActions: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)
