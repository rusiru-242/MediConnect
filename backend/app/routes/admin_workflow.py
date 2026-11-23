"""Admin AI Automation, Verification, Analytics, and Operations routes (Phase 5)."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pymongo.database import Database

from app.agents.orchestrator import AIOrchestrator
from app.config.database import get_database
from app.middleware.auth import get_current_user, require_admin
from app.schemas.admin_workflow import (
    AdminAssistantChatRequest,
    AdminAssistantChatResponse,
    AdminAuditLogListResponse,
    AdminReportResponse,
    ApproveRefundRequest,
    CreateRefundRequest,
    CreateSupportTicketRequest,
    DoctorVerificationAIDecision,
    GenerateReportRequest,
    ReconciliationReportResponse,
    RefundRequestListResponse,
    RefundRequestResponse,
    RejectRefundRequest,
    ReplySupportTicketRequest,
    SupportTicketListResponse,
    SupportTicketResponse,
)
from app.schemas.user import UserResponseSchema
from app.services.admin_analytics_assistant import AdminAnalyticsAssistant
from app.services.admin_audit_service import AdminAuditService
from app.services.admin_report_service import AdminReportService
from app.services.doctor_verification_assistant import DoctorVerificationAssistant
from app.services.payment_monitoring_service import PaymentMonitoringService
from app.services.refund_service import RefundService
from app.services.support_ticket_service import SupportTicketService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/workflow",
    tags=["Admin AI Workflow & Automation"],
)


# -----------------------------------------------------------------------------
# 1. Admin Conversational AI Assistant
# -----------------------------------------------------------------------------

@router.post(
    "/assistant",
    response_model=AdminAssistantChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin Conversational AI Assistant supporting English, Sinhala, and Romanized Sinhala",
)
async def admin_assistant(
    req: AdminAssistantChatRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminAssistantChatResponse:
    """Interprets administrative requests, securely invokes bounded tools, and returns verified facts."""
    query = req.message.casefold().strip()
    orch = AIOrchestrator(db, current_admin, None)

    # Determine timeframe if mentioned
    timeframe = "last_30_days"
    if any(w in query for w in ["today", "ada", "අද", "இன்று"]):
        timeframe = "today"
    elif any(w in query for w in ["7 days", "week", "sathiya", "සතිය", "வாரம்"]):
        timeframe = "last_7_days"
    elif any(w in query for w in ["month", "mase", "මාසය", "மாதம்", "30 days"]):
        timeframe = "last_30_days"

    tool_called: Optional[str] = None
    tool_args: Dict[str, Any] = {}
    reply_text = ""
    result_data: Optional[Dict[str, Any]] = None
    date_range: Optional[Dict[str, str]] = None
    suggestions: List[str] = []

    # 1. Doctor verification intent
    if any(w in query for w in ["doctor verification", "pending doctor", "pending doc", "verification backlog", "වෛද්‍ය", "மருத்துவர்"]):
        tool_called = "get_pending_doctor_verifications"
        tool_args = {}
        res = await orch.execute(tool_called, tool_args, {tool_called})
        pending = res.get("pendingApplications", [])
        reply_text = f"There are currently {len(pending)} doctor verification application(s) pending administrative review."
        result_data = {"pendingCount": len(pending), "applications": pending[:5]}
        suggestions = ["Review oldest doctor verification", "Show doctor document checklist"]

    # 2. Payment reconciliation & discrepancy intent
    elif any(w in query for w in ["reconcil", "discrepanc", "unmatched", "mismatch", "failed payment", "ගෙවීම්", "பணம்"]):
        tool_called = "get_payment_reconciliation_issues"
        tool_args = {}
        res = await orch.execute(tool_called, tool_args, {tool_called})
        disc_count = res.get("discrepanciesCount", 0)
        discrepancies = res.get("discrepancies", [])
        if disc_count == 0:
            reply_text = f"Payment reconciliation check passed: all {res.get('totalChecked', 0)} monitored transactions match booking statuses with zero discrepancies."
        else:
            reply_text = f"Payment reconciliation identified {disc_count} discrepancy item(s) requiring administrative review."
        result_data = res
        suggestions = ["Show unconfirmed paid bookings", "Check delayed pending transactions"]

    # 3. Refund request intent
    elif any(w in query for w in ["refund", "money back", "cancellation settlement", "මුදල් ආපසු"]):
        tool_called = "get_admin_report_data"
        tool_args = {"report_type": "refund_status"}
        res = await orch.execute(tool_called, tool_args, {tool_called})
        metrics = res.get("metrics", {})
        reply_text = f"Found {metrics.get('totalRequests', 0)} refund request(s). {metrics.get('succeededCount', 0)} settled (LKR {metrics.get('totalRefundedLKR', 0):,.2f}), {metrics.get('pendingCount', 0)} pending review."
        result_data = res
        suggestions = ["Review pending refunds", "Show cancellation policy rules"]

    # 4. Support ticket intent
    elif any(w in query for w in ["support ticket", "customer support", "tickets summary", "උපකාරක"]):
        tool_called = "get_support_tickets"
        tool_args = {"status": "open"}
        res = await orch.execute(tool_called, tool_args, {tool_called})
        items = res.get("items", [])
        reply_text = f"There are {len(items)} open customer support ticket(s) currently awaiting administrative response."
        result_data = {"openTickets": items[:5], "totalOpen": len(items)}
        suggestions = ["Draft response for top ticket", "View urgent support tickets"]

    # 5. Operational Analytics intent (appointments, revenue, conversion, Colombo area)
    elif any(w in query for w in ["booking", "revenue", "analytics", "appointment", "success rate", "conversion", "colombo", "kandy", "galle", "keeyada", "monawada"]):
        tool_called = "get_admin_dashboard_metrics"
        tool_args = {"timeframe": timeframe}
        res = await orch.execute(tool_called, tool_args, {tool_called})
        date_range = res.get("dateRange")
        appts = res.get("appointments", {})
        fin = res.get("financials", {})

        if "colombo" in query:
            count = appts.get("locations", {}).get("Colombo", 0)
            reply_text = f"There are {count} appointment(s) in the Colombo area for the timeframe ({date_range.get('startDate')} to {date_range.get('endDate')})."
        elif "success rate" in query:
            rate = fin.get("paymentSuccessRate", 100.0)
            reply_text = f"Payment success rate is {rate}% ({fin.get('succeededTransactions', 0)} succeeded, {fin.get('failedTransactions', 0)} failed) for {timeframe.replace('_', ' ')}."
        elif any(w in query for w in ["revenue", "gross", "income"]):
            gross = fin.get("grossProcessedPayments", 0.0)
            net = fin.get("netPaymentAmount", 0.0)
            reply_text = f"Gross processed payments: LKR {gross:,.2f}, Net payment volume: LKR {net:,.2f} ({date_range.get('startDate')} to {date_range.get('endDate')})."
        else:
            total_b = appts.get("totalAppointments", 0)
            conf_b = appts.get("confirmedAppointments", 0)
            reply_text = f"Platform recorded {total_b} appointment booking(s) ({conf_b} confirmed) with a {appts.get('bookingConversionRate', 0)}% conversion rate for {timeframe.replace('_', ' ')}."

        result_data = res
        suggestions = ["Show financial revenue breakdown", "Compare with last month", "Download operational report"]

    # Fallback response
    else:
        reply_text = (
            "I am the MediConnect Admin AI Assistant. You can ask me in English, Sinhala, or Romanized Sinhala about "
            "doctor verification backlogs, payment reconciliation, bookings analytics, revenue metrics, support tickets, or refunds."
        )
        suggestions = [
            "pending doctors keeyak innawada?",
            "me month eke bookings keeyak thiyenawada?",
            "failed payments tika check karanna",
            "refund requests monawada?",
        ]

    return AdminAssistantChatResponse(
        reply=reply_text,
        toolCalled=tool_called,
        data=result_data,
        dateRange=date_range,
        actionSuggestions=suggestions,
    )


# -----------------------------------------------------------------------------
# 2. Doctor Verification AI Assistant
# -----------------------------------------------------------------------------

@router.get(
    "/doctor-verification/{profileId}/ai-review",
    response_model=DoctorVerificationAIDecision,
    status_code=status.HTTP_200_OK,
    summary="Get structured AI verification review and document completeness",
)
async def get_doctor_ai_review(
    profileId: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> DoctorVerificationAIDecision:
    """Analyze doctor application for missing documents, format inconsistencies, and credential risk."""
    review = DoctorVerificationAssistant.analyze_application(db, profileId)
    return DoctorVerificationAIDecision(**review)


# -----------------------------------------------------------------------------
# 3. Payment Monitoring & Reconciliation
# -----------------------------------------------------------------------------

@router.get(
    "/payments",
    status_code=status.HTTP_200_OK,
    summary="List monitored payments with booking correlation and privacy masking",
)
async def list_monitored_payments(
    status: Optional[str] = Query(None, description="Payment status filter"),
    startDate: Optional[str] = Query(None, description="Start date filter"),
    endDate: Optional[str] = Query(None, description="End date filter"),
    appointmentId: Optional[str] = Query(None, description="Filter by appointment ID"),
    search: Optional[str] = Query(None, description="Search by ID or payment intent"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    return PaymentMonitoringService.list_monitored_payments(
        db=db,
        status=status,
        start_date=startDate,
        end_date=endDate,
        appointment_id=appointmentId,
        search=search,
        page=page,
        page_size=pageSize,
    )


@router.post(
    "/reconciliation/run",
    response_model=ReconciliationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Run deterministic payment and booking reconciliation checks",
)
async def run_reconciliation(
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> ReconciliationReportResponse:
    """Execute deterministic cross-system reconciliation across Stripe and MongoDB."""
    report = PaymentMonitoringService.run_reconciliation_checks(db)
    return ReconciliationReportResponse(**report)


@router.get(
    "/reconciliation/issues",
    response_model=ReconciliationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detected reconciliation issues and discrepancies",
)
async def get_reconciliation_issues(
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> ReconciliationReportResponse:
    report = PaymentMonitoringService.run_reconciliation_checks(db)
    return ReconciliationReportResponse(**report)


# -----------------------------------------------------------------------------
# 4. Customer Support Ticketing & AI Drafting
# -----------------------------------------------------------------------------

@router.get(
    "/tickets",
    response_model=SupportTicketListResponse,
    status_code=status.HTTP_200_OK,
    summary="List support tickets with role-based filtering",
)
async def list_support_tickets(
    status: Optional[str] = Query(None, description="Filter by status (open, in_progress, resolved, closed)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> SupportTicketListResponse:
    is_admin = current_user.role == "ADMIN"
    res = SupportTicketService.list_tickets(
        db=db,
        user_id=str(current_user.id),
        is_admin=is_admin,
        status_filter=status,
        category=category,
        priority=priority,
        page=page,
        page_size=pageSize,
    )
    return SupportTicketListResponse(**res)


@router.post(
    "/tickets",
    response_model=SupportTicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer support ticket",
)
async def create_support_ticket(
    req: CreateSupportTicketRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> SupportTicketResponse:
    doc = SupportTicketService.create_ticket(
        db=db,
        user_id=str(current_user.id),
        user_role=current_user.role,
        user_email=current_user.email,
        user_name=current_user.fullName,
        subject=req.subject,
        description=req.description,
        category=req.category,
        priority=req.priority,
        related_entity_id=req.relatedEntityId,
    )
    return SupportTicketResponse(id=str(doc.get("_id", doc.get("ticketId"))), **doc)


@router.get(
    "/tickets/{ticketId}",
    response_model=SupportTicketResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer support ticket details and conversation thread",
)
async def get_support_ticket(
    ticketId: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> SupportTicketResponse:
    is_admin = current_user.role == "ADMIN"
    doc = SupportTicketService.get_ticket(db, ticketId, str(current_user.id), is_admin=is_admin)
    return SupportTicketResponse(**doc)


@router.post(
    "/tickets/{ticketId}/ai-draft",
    status_code=status.HTTP_200_OK,
    summary="Generate or refresh grounded AI draft response for a support ticket",
)
async def generate_support_draft(
    ticketId: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    return SupportTicketService.generate_ai_ticket_draft(db, ticketId)


@router.post(
    "/tickets/{ticketId}/reply",
    status_code=status.HTTP_200_OK,
    summary="Admin sends authorized reply to a support ticket",
)
async def reply_support_ticket(
    ticketId: str,
    req: ReplySupportTicketRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    return SupportTicketService.send_admin_reply(
        db=db,
        admin_user_id=str(current_admin.id),
        admin_name=current_admin.fullName,
        ticket_id=ticketId,
        message=req.message,
        new_status=req.status,
        resolve=bool(req.resolve),
    )


# -----------------------------------------------------------------------------
# 5. Refund Review & Execution Workflow
# -----------------------------------------------------------------------------

@router.get(
    "/refunds",
    response_model=RefundRequestListResponse,
    status_code=status.HTTP_200_OK,
    summary="List refund requests with status filter",
)
async def list_refund_requests(
    status: Optional[str] = Query(None, description="Refund status filter"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> RefundRequestListResponse:
    res = RefundService.list_refund_requests(db, status_filter=status, page=page, page_size=pageSize)
    return RefundRequestListResponse(**res)


@router.post(
    "/refunds",
    response_model=RefundRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a refund request for an appointment",
)
async def create_refund_request(
    req: CreateRefundRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> RefundRequestResponse:
    doc = RefundService.create_refund_request(
        db=db,
        patient_user_id=str(current_user.id),
        appointment_id=req.appointmentId,
        reason=req.reason,
    )
    return RefundRequestResponse(id=str(doc.get("_id", doc.get("refundId"))), **doc)


@router.get(
    "/refunds/{refundId}",
    response_model=RefundRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Get refund request detail and policy eligibility breakdown",
)
async def get_refund_request_detail(
    refundId: str,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> RefundRequestResponse:
    doc = RefundService.get_refund_request(db, refundId)
    return RefundRequestResponse(**doc)


@router.post(
    "/refunds/{refundId}/approve",
    status_code=status.HTTP_200_OK,
    summary="Admin approves and executes refund through Stripe with idempotency",
)
async def approve_refund(
    refundId: str,
    req: ApproveRefundRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    return RefundService.approve_refund(
        db=db,
        admin_user_id=str(current_admin.id),
        refund_id=refundId,
        approved_amount=req.approvedAmount,
        notes=req.notes,
    )


@router.post(
    "/refunds/{refundId}/reject",
    status_code=status.HTTP_200_OK,
    summary="Admin rejects refund request with mandatory reason",
)
async def reject_refund(
    refundId: str,
    req: RejectRefundRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    return RefundService.reject_refund(
        db=db,
        admin_user_id=str(current_admin.id),
        refund_id=refundId,
        reason=req.reason,
    )


# -----------------------------------------------------------------------------
# 6. Operational Reports & CSV Export
# -----------------------------------------------------------------------------

@router.post(
    "/reports/generate",
    response_model=AdminReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate operational report with grounded AI executive summary",
)
async def generate_operational_report(
    req: GenerateReportRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminReportResponse:
    report = AdminReportService.generate_report(
        db=db,
        report_type=req.reportType,
        start_date=req.startDate,
        end_date=req.endDate,
    )
    return AdminReportResponse(**report)


@router.post(
    "/reports/export-csv",
    status_code=status.HTTP_200_OK,
    summary="Export operational report data as downloadable CSV",
)
async def export_report_csv(
    req: GenerateReportRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    csv_content = AdminReportService.export_csv(
        db=db,
        report_type=req.reportType,
        start_date=req.startDate,
        end_date=req.endDate,
    )
    filename = f"mediconnect_{req.reportType}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# -----------------------------------------------------------------------------
# 7. Administrative Audit Log Querying
# -----------------------------------------------------------------------------

@router.get(
    "/audit-logs",
    response_model=AdminAuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Query tamper-resistant administrative audit logs",
)
async def list_audit_logs(
    actionType: Optional[str] = Query(None, description="Action filter"),
    targetType: Optional[str] = Query(None, description="Target entity type"),
    actorId: Optional[str] = Query(None, description="Filter by admin actor ID"),
    startDate: Optional[str] = Query(None, description="Start date filter"),
    endDate: Optional[str] = Query(None, description="End date filter"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AdminAuditLogListResponse:
    res = AdminAuditService.query_audit_logs(
        db=db,
        action_type=actionType,
        target_type=targetType,
        actor_id=actorId,
        start_date=startDate,
        end_date=endDate,
        page=page,
        page_size=pageSize,
    )
    return AdminAuditLogListResponse(**res)
