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
    RequesterTicketReplyRequest,
    SupportTicketStatusRequest,
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

    # Phase 05 (component 33): one shared, role-specific intent classifier instead of per-branch keyword lists.
    # It never executes anything; each intent maps to one read-only ADMIN tool below.
    from app.agents.intent_router import classify
    from app.agents.ai_provider import get_ai_provider
    classified = classify("ADMIN", req.message, provider=get_ai_provider())
    intent = classified.intent
    timeframe = classified.timeframe or "last_30_days"

    tool_called: Optional[str] = None
    tool_args: Dict[str, Any] = {}
    reply_text = ""
    result_data: Optional[Dict[str, Any]] = None
    date_range: Optional[Dict[str, str]] = None
    suggestions: List[str] = []

    # 1. Doctor verification intent
    if intent == "pending_doctor_verifications":
        tool_called = "get_pending_doctor_verifications"
        tool_args = {}
        res = await orch.execute(tool_called, tool_args, {tool_called})
        pending = res.get("pendingApplications", [])
        reply_text = f"There are currently {len(pending)} doctor verification application(s) pending administrative review."
        result_data = {"pendingCount": len(pending), "applications": pending[:5]}
        suggestions = ["Review oldest doctor verification", "Show doctor document checklist"]

    # 2. Payment reconciliation & discrepancy intent
    # "failed payments tika check karanna" (the assistant's own suggestion) has always run the reconciliation check.
    elif intent in {"payment_reconciliation", "failed_payments"}:
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
    elif intent == "refunds_attention":
        tool_called = "get_admin_report_data"
        tool_args = {"report_type": "refund_status"}
        res = await orch.execute(tool_called, tool_args, {tool_called})
        # The report's own summary is built from the same metrics, so the reply never adds a figure (P04-N05).
        reply_text = res.get("aiSummary") or "Refund figures are not available."
        result_data = res
        suggestions = ["Review pending refunds", "Show cancellation policy rules"]

    # 4. Support ticket intent
    elif intent == "support_tickets":
        tool_called = "get_support_tickets"
        tool_args = {"status": "open"}
        res = await orch.execute(tool_called, tool_args, {tool_called})
        items = res.get("items", [])
        reply_text = f"There are {len(items)} open customer support ticket(s) currently awaiting administrative response."
        result_data = {"openTickets": items[:5], "totalOpen": len(items)}
        suggestions = ["Draft response for top ticket", "View urgent support tickets"]

    # 5. Operational Analytics intent (appointments, revenue, conversion, Colombo area)
    elif intent in {"booking_analytics", "revenue", "payment_summary"}:
        tool_called = "get_admin_dashboard_metrics"
        tool_args = {"timeframe": timeframe}
        res = await orch.execute(tool_called, tool_args, {tool_called})
        date_range = res.get("dateRange")
        appts = res.get("appointments", {})
        fin = res.get("financials", {})

        period = f"{date_range.get('startDate')} to {date_range.get('endDate')} (Asia/Colombo)"
        if any(city in query for city in ["colombo", "kandy", "galle"]):
            # Appointments do not record a city; the former per-city counts were always 0 (P04-N05).
            reply_text = ("Appointments do not record a city or area, so MediConnect cannot count bookings by "
                          "location. Ask for total bookings instead.")
        elif intent == "payment_summary" or "success rate" in query:
            rate = fin.get("paymentSuccessRate")
            if "rate" not in query:
                # P05-N19: succeededTransactions excludes payments later fully refunded (status REFUNDED), so the
                # number of successful (captured) payments is the sum of both.
                captured = fin.get('succeededTransactions', 0) + fin.get('refundedTransactions', 0)
                reply_text = (f"{captured} payment(s) were captured successfully in {period} "
                              f"({fin.get('refundedTransactions', 0)} of them were later fully refunded); "
                              f"{fin.get('failedTransactions', 0)} attempt(s) failed.")
            elif rate is None:
                reply_text = f"No payments were attempted in {period}, so there is no payment success rate."
            else:
                reply_text = (f"Payment success rate is {rate}% ({fin.get('succeededTransactions', 0)} succeeded, "
                              f"{fin.get('refundedTransactions', 0)} later refunded, {fin.get('failedTransactions', 0)} "
                              f"failed) for {period}.")
        elif intent == "revenue":
            rows = fin.get("byCurrency") or {}
            if not rows:
                reply_text = f"No payments were captured in {period}."
            else:
                parts = [f"{cur.upper()}: gross collections {r['capturedAmount']:,.2f}, refunded {r['refundedAmount']:,.2f}, "
                         f"net collections {r['netCollected']:,.2f}" for cur, r in sorted(rows.items())]
                reply_text = f"{'; '.join(parts)} for {period}. {fin.get('note', '')}".strip()
        else:
            total_b = appts.get("totalAppointments", 0)
            conf_b = appts.get("confirmedAppointments", 0)
            reply_text = (f"Platform recorded {total_b} appointment booking(s) dated {period}: {conf_b} confirmed, "
                          f"{appts.get('completedAppointments', 0)} completed and {appts.get('cancelledAppointments', 0)} cancelled.")

        result_data = res
        suggestions = ["Show financial revenue breakdown", "Compare with last month", "Download operational report"]

    # 6. Notification delivery failures (Phase 05)
    elif intent == "notification_failures":
        tool_called = "get_notification_queue_status"
        metrics = await orch.execute(tool_called, {}, {tool_called})
        dead = await orch.execute("get_notification_failures", {}, {"get_notification_failures"})
        channels = metrics.get("byChannel") or []
        parts = ", ".join(f"{row.get('channel')}: {row.get('failed', 0)} failed ({row.get('providerStatus')})"
                          for row in channels if isinstance(row, dict)) or "not reported"
        reply_text = (f"Notification delivery by channel: {parts}. Dead-letter items awaiting review: "
                      f"{metrics.get('deadLetterQueueCount', 0)}. Channels that are not configured are reported as "
                      "not configured, never as delivered.")
        result_data = {"byChannel": channels, "deadLetterQueueCount": metrics.get("deadLetterQueueCount"),
                       "deadLetters": (dead.get("dead_letters") or [])[:5], "notes": metrics.get("notes")}
        suggestions = ["Open Notification Monitoring", "Retry a dead-letter item"]

    # 7. Fraud assessment explanation (Phase 05): signals for human review, never findings.
    elif intent == "fraud_explanation":
        assessment_id = (req.contextFilter or {}).get("assessmentId") if isinstance(req.contextFilter, dict) else None
        if assessment_id:
            tool_called = "get_fraud_review_details"
            res = await orch.execute(tool_called, {"assessment_id": str(assessment_id)}, {tool_called})
            if res.get("error"):
                reply_text = "That fraud assessment was not found."
            else:
                rules = ", ".join(res.get("triggeredRules") or []) or "no rule recorded"
                reply_text = (f"Assessment {res.get('assessmentId')} (risk {res.get('riskLevel')}, score "
                              f"{res.get('riskScore')}) was generated because these rules triggered: {rules}. "
                              f"{res.get('explanation', '')} This is a signal for human review, not a finding; no "
                              "account action is taken automatically.")
                result_data = {k: res.get(k) for k in ("assessmentId", "riskLevel", "riskScore", "triggeredRules",
                                                       "explanation", "reviewStatus")}
        else:
            tool_called = "get_fraud_alerts"
            res = await orch.execute(tool_called, {"status": "AWAITING_REVIEW"}, {tool_called})
            items = res.get("items") or []
            if not items:
                reply_text = "No fraud assessments are awaiting review."
            else:
                lines = [f"{i.get('assessmentId')}: {', '.join(i.get('triggeredRules') or [])}" for i in items[:5]]
                reply_text = (f"{res.get('total', len(items))} assessment(s) await review. Each was generated by "
                              "these rule triggers: " + "; ".join(lines) + ". Open one to see its full explanation; "
                              "these are signals for human review, not findings.")
            result_data = {"items": items[:5], "total": res.get("total", len(items))}
        suggestions = ["Open Fraud Monitoring"]

    # 8. Platform health (Phase 05)
    elif intent == "system_health":
        tool_called = "get_platform_health"
        res = await orch.execute(tool_called, {}, {tool_called})
        deps = res.get("dependencies") or []
        dep_text = ", ".join(f"{d.get('name')}: {d.get('status')}" for d in deps if isinstance(d, dict)) or "not reported"
        reply_text = (f"Overall status: {res.get('status', 'not reported')}. Dependencies: {dep_text}. Active "
                      f"incidents: {res.get('activeIncidentsCount', 0)}.")
        result_data = {k: res.get(k) for k in ("status", "dependencies", "workers", "activeIncidentsCount")}
        suggestions = ["Open System Monitoring"]

    elif intent == "ambiguous":
        labels = {"pending_doctor_verifications": "doctor verifications", "payment_reconciliation": "payment reconciliation",
                  "failed_payments": "failed payments", "payment_summary": "payment totals", "revenue": "collections",
                  "refunds_attention": "refunds", "support_tickets": "support tickets", "booking_analytics": "bookings",
                  "notification_failures": "notification failures", "fraud_explanation": "fraud assessments",
                  "system_health": "system health"}
        options = [labels.get(c, c) for c in classified.candidates]
        reply_text = "Your message mentions more than one topic: " + ", ".join(options) + ". Which one should I check first?"
        suggestions = [f"Show {o}" for o in options]

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
        intent=intent,
        intentSource=classified.source,
        language=classified.language,
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
    from app.services.support_ticket_service import ticket_view
    return SupportTicketResponse(**ticket_view(doc, current_user.role == "ADMIN"))


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


@router.post(
    "/tickets/{ticketId}/messages",
    response_model=SupportTicketResponse,
    status_code=status.HTTP_200_OK,
    summary="The requester adds a follow-up message to their own ticket (A05)",
)
async def add_ticket_message(
    ticketId: str,
    req: RequesterTicketReplyRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> SupportTicketResponse:
    if current_user.role == "ADMIN":
        raise HTTPException(status_code=403, detail="Administrators reply through the authorized reply action.")
    return SupportTicketResponse(**SupportTicketService.add_requester_reply(db, current_user, ticketId, req.message))


@router.post(
    "/tickets/{ticketId}/status",
    status_code=status.HTTP_200_OK,
    summary="Admin changes a support ticket status without a message (A05)",
)
async def update_ticket_status(
    ticketId: str,
    req: SupportTicketStatusRequest,
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    return SupportTicketService.update_status(db, str(current_admin.id), ticketId, req.status)


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
    source: Optional[str] = Query(None, description="patient, doctor, leave or ALL"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> RefundRequestListResponse:
    res = RefundService.list_refund_requests(db, status_filter=status, page=page, page_size=pageSize,
                                             source_filter=source)
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
        source="patient",
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
    AdminAuditService.log_action(
        db=db, actor_id=str(current_admin.id), actor_role="ADMIN", actor_email=current_admin.email,
        action_type="REPORT_GENERATED", target_id=report["reportId"], target_type="report",
        metadata={"reportType": report["reportType"], **report["dateRange"]},
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
    # Exports leave the platform, so each one is audited (P04-N19); no report content is copied into the log.
    AdminAuditService.log_action(
        db=db, actor_id=str(current_admin.id), actor_role="ADMIN", actor_email=current_admin.email,
        action_type="REPORT_EXPORTED", target_id=req.reportType, target_type="report",
        metadata={"format": "csv", "startDate": req.startDate, "endDate": req.endDate},
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


@router.post("/refunds/sync-pending", summary="Re-read pending Stripe refunds and apply final states (Phase 05)")
async def sync_pending_refunds_now(
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Admin-triggered version of the worker's pending-refund check. It never creates a refund."""
    from app.services.stripe_webhook_service import sync_pending_refunds
    return sync_pending_refunds(db, older_than_minutes=0)
