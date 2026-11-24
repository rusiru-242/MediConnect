"""FastAPI router for Phase 7: Advanced Security, Fraud Detection, Monitoring & Reliability."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_admin
from app.models.fraud_assessment import FraudRiskLevel, FraudReviewStatus
from app.models.operational_incident import IncidentCategory, IncidentSeverity, IncidentStatus
from app.models.security_event import SecurityEventCategory, SecuritySeverity
from app.models.workflow_monitoring import WorkflowStatus, WorkflowType
from app.schemas.security_monitoring import (
    AdminMonitoringChatRequest,
    AdminMonitoringChatResponse,
    DeadLetterNotificationResponse,
    FraudAssessmentListResponse,
    FraudAssessmentResponse,
    FraudReviewDecisionRequest,
    IncidentUpdateRequest,
    NotificationMonitoringMetricsResponse,
    NotificationRetryResponse,
    OperationalIncidentCreateRequest,
    OperationalIncidentListResponse,
    OperationalIncidentResponse,
    PlatformHealthResponse,
    SecurityEventCreateRequest,
    SecurityEventListResponse,
    SecurityEventResponse,
    WorkflowMonitoringResponse,
    WorkflowRecoveryRequest,
    WorkflowRecoveryResponse,
    AIProviderMetricsResponse,
)
from app.schemas.user import UserResponseSchema
from app.services.admin_monitoring_assistant import AdminMonitoringAssistant
from app.services.ai_provider_monitoring_service import AIProviderMonitoringService
from app.services.fraud_detection_service import FraudDetectionService
from app.services.incident_management_service import IncidentManagementService
from app.services.notification_monitoring_service import NotificationMonitoringService
from app.services.platform_monitoring_service import PlatformMonitoringService
from app.services.security_event_service import SecurityEventService
from app.services.workflow_monitoring_service import WorkflowMonitoringService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Security, Monitoring & Reliability"])


# ===========================================================================
# 1. Non-Destructive Public Health Checks (Liveness & Readiness)
# ===========================================================================

@router.get("/health/live", summary="Liveness probe indicating process responsiveness")
@router.get("/live", summary="Liveness probe alias")
def liveness_check() -> Dict[str, Any]:
    """Lightweight check verifying the application process is running."""
    return {
        "status": "live",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptimeSeconds": round(PlatformMonitoringService.get_uptime_seconds(), 1),
    }


@router.get("/health/ready", summary="Readiness probe verifying core dependencies")
@router.get("/ready", summary="Readiness probe alias")
def readiness_check(response: Response, db: Database = Depends(get_database)) -> Dict[str, Any]:
    """Readiness check validating database availability without exposing secrets."""
    db_health = PlatformMonitoringService.check_database_health(db)
    if db_health["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unready",
            "message": "Database dependency is not available.",
            "database": db_health["status"],
        }
    return {
        "status": "ready",
        "message": "Application ready to serve requests.",
        "database": "connected",
    }


# ===========================================================================
# 2. Security Events Telemetry
# ===========================================================================

@router.get("/security/events", response_model=SecurityEventListResponse, summary="List security events")
def list_security_events(
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    actorId: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Retrieve security audit telemetry with filters and pagination."""
    res = SecurityEventService.list_security_events(
        category=category, severity=severity, actor_id=actorId, limit=limit, skip=skip, db=db
    )
    return SecurityEventListResponse(
        items=[SecurityEventResponse(**item.model_dump()) for item in res["items"]],
        total=res["total"],
    )


@router.get("/security/events/summary", summary="Get 24-hour security event breakdown")
def get_security_summary(
    hours: int = Query(24, ge=1, le=168),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Aggregate security events grouped by severity and category."""
    return SecurityEventService.get_security_summary(hours=hours, db=db)


@router.post("/security/events", response_model=SecurityEventResponse, status_code=status.HTTP_201_CREATED, summary="Record a security event")
def create_security_event(
    req: SecurityEventCreateRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Manually ingest or test security event audit logging."""
    ev = SecurityEventService.record_security_event(
        category=req.category,
        severity=req.severity,
        description=req.description,
        actor_id=req.actorId or str(current_admin.id),
        actor_role=req.actorRole or current_admin.role,
        ip_address=req.ipAddress,
        endpoint=req.endpoint,
        metadata=req.metadata,
        db=db,
    )
    return SecurityEventResponse(**ev.model_dump())


# ===========================================================================
# 3. Fraud Detection & Risk Scoring
# ===========================================================================

@router.get("/security/fraud/assessments", response_model=FraudAssessmentListResponse, summary="List fraud risk assessments")
def list_fraud_assessments(
    statusFilter: Optional[str] = Query(None, alias="status"),
    riskLevel: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Retrieve explainable fraud risk assessments for review."""
    res = FraudDetectionService.list_assessments(status=statusFilter, risk_level=riskLevel, limit=limit, skip=skip, db=db)
    return FraudAssessmentListResponse(
        items=[FraudAssessmentResponse(**item.model_dump()) for item in res["items"]],
        total=res["total"],
    )


@router.post("/security/fraud/assessments/evaluate", response_model=Optional[FraudAssessmentResponse], summary="Evaluate fraud risk for an account")
def evaluate_fraud_risk(
    accountId: str = Query(..., description="Target patient or user ID to evaluate"),
    entityRef: Optional[str] = Query(None),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Evaluate real behavioral signals against deterministic risk rules."""
    assessment = FraudDetectionService.evaluate_account_risk(account_id=accountId, entity_ref=entityRef, db=db)
    if not assessment:
        return None
    return FraudAssessmentResponse(**assessment.model_dump())


@router.post("/security/fraud/assessments/{assessment_id}/review", response_model=FraudAssessmentResponse, summary="Submit admin fraud review decision")
def review_fraud_assessment(
    assessment_id: str,
    req: FraudReviewDecisionRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Authoritatively record admin decision on flagged fraud assessment (dismiss, confirm, investigate, resolve)."""
    reviewed = FraudDetectionService.review_assessment(
        assessment_id=assessment_id,
        decision=req.decision,
        admin_id=str(current_admin.id),
        notes=req.notes,
        action_required=req.actionRequired,
        db=db,
    )
    if not reviewed:
        raise HTTPException(status_code=404, detail="Fraud assessment not found.")
    return FraudAssessmentResponse(**reviewed.model_dump())


# ===========================================================================
# 4. Operational Incident Management
# ===========================================================================

@router.get("/security/incidents", response_model=OperationalIncidentListResponse, summary="List operational incidents")
def list_incidents(
    statusFilter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """List operational incidents with filters."""
    res = IncidentManagementService.list_incidents(status=statusFilter, category=category, severity=severity, limit=limit, skip=skip, db=db)
    return OperationalIncidentListResponse(
        items=[OperationalIncidentResponse(**item.model_dump()) for item in res["items"]],
        total=res["total"],
    )


@router.post("/security/incidents", response_model=OperationalIncidentResponse, status_code=status.HTTP_201_CREATED, summary="Create operational incident")
def create_incident(
    req: OperationalIncidentCreateRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Manually or programmatically declare a new operational incident."""
    inc = IncidentManagementService.create_incident(
        title=req.title,
        category=req.category,
        severity=req.severity,
        description=req.description,
        affected_service=req.affectedService,
        supporting_events=req.supportingEventReferences,
        db=db,
    )
    return OperationalIncidentResponse(**inc.model_dump())


@router.post("/security/incidents/{incident_id}/acknowledge", response_model=OperationalIncidentResponse, summary="Acknowledge incident")
def acknowledge_incident(
    incident_id: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Assign and acknowledge an operational incident."""
    inc = IncidentManagementService.acknowledge_incident(incident_id=incident_id, admin_id=str(current_admin.id), db=db)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return OperationalIncidentResponse(**inc.model_dump())


@router.post("/security/incidents/{incident_id}/resolve", response_model=OperationalIncidentResponse, summary="Resolve incident")
def resolve_incident(
    incident_id: str,
    notes: str = Query(..., min_length=3),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Resolve an operational incident with post-incident review notes."""
    inc = IncidentManagementService.resolve_incident(incident_id=incident_id, admin_id=str(current_admin.id), resolution_notes=notes, db=db)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return OperationalIncidentResponse(**inc.model_dump())


@router.get("/security/incidents/{incident_id}/ai-summary", summary="AI-assisted incident breakdown and investigation steps")
def get_ai_incident_summary(
    incident_id: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Generate structured investigation steps and contextual summary for an incident."""
    summary = IncidentManagementService.generate_ai_incident_summary(incident_id=incident_id, db=db)
    if "error" in summary:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return summary


# ===========================================================================
# 5. Platform Monitoring Telemetry
# ===========================================================================

@router.get("/security/monitoring/platform", response_model=PlatformHealthResponse, summary="Comprehensive platform health snapshot")
def get_platform_monitoring(
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Aggregate health telemetry across database, workers, providers, and incidents."""
    snapshot = PlatformMonitoringService.get_platform_health_snapshot(db)
    return PlatformHealthResponse(**snapshot)


@router.post("/security/monitoring/workers/heartbeat", summary="Record background worker heartbeat")
def record_worker_heartbeat(
    workerName: str = Query(...),
    jobCount: int = Query(0),
    durationSeconds: float = Query(0.0),
    failedCount: int = Query(0),
    db: Database = Depends(get_database),
):
    """Background worker ingestion endpoint for durable heartbeat telemetry."""
    PlatformMonitoringService.record_worker_heartbeat(
        worker_name=workerName,
        job_count=jobCount,
        duration_seconds=durationSeconds,
        failed_count=failedCount,
        db=db,
    )
    return {"status": "heartbeat_recorded", "timestamp": datetime.now(timezone.utc).isoformat()}


# ===========================================================================
# 6. Notification Monitoring & Dead Letters
# ===========================================================================

@router.get("/security/monitoring/notifications", response_model=NotificationMonitoringMetricsResponse, summary="Notification telemetry & outbox metrics")
def get_notification_monitoring_metrics(
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Retrieve delivery rates, backlogs, and dead-letter counts across channels."""
    metrics = NotificationMonitoringService.get_notification_metrics(db)
    return NotificationMonitoringMetricsResponse(**metrics)


@router.post("/security/monitoring/notifications/process-retries", summary="Trigger notification retries with bounded backoff")
def trigger_notification_retries(
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Process pending notification retries with context revalidation and dead-letter routing."""
    res = NotificationMonitoringService.process_notification_retries(db)
    return res


@router.get("/security/monitoring/notifications/dead-letters", response_model=List[DeadLetterNotificationResponse], summary="List dead-lettered notifications")
def list_dead_letters(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Query notifications that exceeded maximum retries for human inspection."""
    items = NotificationMonitoringService.list_dead_letters(limit=limit, skip=skip, db=db)
    return [DeadLetterNotificationResponse(**item) for item in items]


@router.post("/security/monitoring/notifications/dead-letters/{dead_letter_id}/retry", response_model=NotificationRetryResponse, summary="Manually retry dead-letter notification")
def manual_retry_dead_letter(
    dead_letter_id: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Admin-authorized requeue of a dead-lettered notification."""
    success = NotificationMonitoringService.manual_retry_dead_letter(dead_letter_id=dead_letter_id, admin_id=str(current_admin.id), db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Dead-letter notification not found.")
    return NotificationRetryResponse(success=True, retriedCount=1, message="Notification successfully requeued.")


# ===========================================================================
# 7. Workflow Monitoring & Idempotent Recovery
# ===========================================================================

@router.get("/security/monitoring/workflows", response_model=List[WorkflowMonitoringResponse], summary="List monitored workflows")
def list_monitored_workflows(
    statusFilter: Optional[str] = Query(None, alias="status"),
    workflowType: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Retrieve monitored automated healthcare workflows."""
    items = WorkflowMonitoringService.list_workflows(status=statusFilter, workflow_type=workflowType, limit=limit, skip=skip, db=db)
    return [WorkflowMonitoringResponse(**item.model_dump()) for item in items]


@router.post("/security/monitoring/workflows/stuck", response_model=List[WorkflowMonitoringResponse], summary="Detect stuck workflows")
def detect_stuck_workflows(
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Scan and flag workflows stuck in intermediate states longer than the threshold."""
    stuck = WorkflowMonitoringService.detect_stuck_workflows(db)
    return [WorkflowMonitoringResponse(**item.model_dump()) for item in stuck]


@router.post("/security/monitoring/workflows/{workflow_id}/recover", response_model=WorkflowRecoveryResponse, summary="Safely recover stuck workflow")
def recover_stuck_workflow(
    workflow_id: str,
    req: WorkflowRecoveryRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Execute idempotent recovery for a stuck workflow without duplicate side-effects."""
    res = WorkflowMonitoringService.recover_workflow(
        workflow_id=workflow_id,
        force=req.force,
        recovery_reason=req.recoveryReason,
        db=db,
    )
    if not res.get("recovered") and "not found" in res.get("message", "").lower():
        raise HTTPException(status_code=404, detail=res["message"])
    return WorkflowRecoveryResponse(**res)


# ===========================================================================
# 8. AI Provider Reliability Metrics
# ===========================================================================

@router.get("/security/monitoring/ai-providers", response_model=List[AIProviderMetricsResponse], summary="AI provider latencies, errors, and circuit breaker status")
def get_ai_provider_metrics(
    provider: Optional[str] = Query(None),
    current_admin: UserResponseSchema = Depends(require_admin),
):
    """Retrieve real-time metrics and circuit breaker telemetry for Gemini and OpenAI."""
    metrics = AIProviderMonitoringService.get_metrics(provider=provider)
    return [AIProviderMetricsResponse(**m) for m in metrics]


# ===========================================================================
# 9. Admin AI Monitoring Assistant Chat
# ===========================================================================

@router.post("/security/ai-assistant/chat", response_model=AdminMonitoringChatResponse, summary="Bilingual natural language monitoring assistant")
def admin_monitoring_chat(
    req: AdminMonitoringChatRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Query platform health, failed payments, notifications, and fraud alerts in English or Romanized Sinhala."""
    res = AdminMonitoringAssistant.handle_query(message=req.message, db=db)
    return AdminMonitoringChatResponse(**res)
