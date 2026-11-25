"""Typed read-only capabilities for the conversation orchestrator."""
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from app.models.appointment import AppointmentStatus
from app.schemas.user import UserResponseSchema
from app.services.appointment_service import AppointmentService
from app.services.doctor_service import DoctorService, get_sl_today_str
from app.services.care_plan_service import CarePlanService

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,100}$")]


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Search(Arguments):
    specialty: ShortText | None = None
    city: ShortText | None = None
    name: ShortText | None = None
    hospital: ShortText | None = None
    max_fee: float | None = Field(default=None, ge=0, le=1000000)


class Doctor(Arguments):
    doctor_id: Identifier


class Availability(Doctor):
    requested_date: date
    requested_time: Annotated[str, StringConstraints(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")] | None = None


class Appointments(Arguments):
    status: AppointmentStatus | None = None
    from_date: date | None = None
    to_date: date | None = None


class Session(Arguments):
    session_id: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{24}$")]


@dataclass(frozen=True)
class ToolContext:
    db: object
    user: UserResponseSchema


@dataclass(frozen=True)
class Tool:
    description: str
    arguments: type[Arguments]
    run: Callable[[ToolContext, Arguments], Awaitable[dict]]
    roles: frozenset[str] = frozenset({"PATIENT"})


def public_doctor(profile):
    fields = ("doctorId", "fullName", "specialty", "hospitalOrClinic", "city", "consultationFee",
              "qualifications", "experienceYears", "profileImage", "verificationStatus")
    return {field: getattr(profile, field) for field in fields
            if getattr(profile, field, None) is not None}


async def search_doctors(ctx, args):
    response = await DoctorService.list_approved_doctors(
        ctx.db, limit=5, specialty=args.specialty, search=args.name,
        city=args.city, hospital=args.hospital, max_fee=args.max_fee, specialty_variants=True,
    )
    return {"doctors": [public_doctor(row) for row in response.items]}


async def doctor_profile(ctx, args):
    profile = await DoctorService.get_approved_doctor_detail(ctx.db, args.doctor_id)
    return {"doctors": [public_doctor(profile)]}


async def availability(ctx, args):
    if args.requested_date.isoformat() < get_sl_today_str():
        return {"error": "date_in_past"}
    day = await DoctorService.get_doctor_patient_slots(ctx.db, args.doctor_id, args.requested_date.isoformat())
    profile = await DoctorService.get_approved_doctor_detail(ctx.db, args.doctor_id)
    slots = [
        {**slot.model_dump(mode="json"), "date": day.date}
        for slot in day.slots
    ]
    if args.requested_time:
        target = int(args.requested_time[:2]) * 60 + int(args.requested_time[3:])
        slots.sort(key=lambda slot: abs(
            int(slot["startTime"][:2]) * 60 + int(slot["startTime"][3:]) - target
        ))
    slots = slots[:20]
    return {"doctor_id": profile.doctorId, "date": day.date, "timezone": "Asia/Colombo",
            "location": profile.hospitalOrClinic, "requested_time": args.requested_time, "slots": slots}


async def appointments(ctx, args):
    if args.from_date and args.to_date and args.from_date > args.to_date:
        return {"error": "invalid_date_range"}
    result = await AppointmentService.list_patient_appointments(
        ctx.db, ctx.user, limit=10, status_filter=args.status,
        from_date=args.from_date.isoformat() if args.from_date else None,
        to_date=args.to_date.isoformat() if args.to_date else None,
    )
    fields = {"appointmentDate", "startTime", "endTime", "status", "paymentStatus"}
    return {"appointments": [item.model_dump(mode="json", include=fields) for item in result.items]}


async def booking_status(ctx, args):
    from app.services.booking_session_service import BookingSessionService

    session = BookingSessionService._get_session_or_404(ctx.db, ctx.user, args.session_id)
    # Synchronize in memory. The interactive API owns MongoDB writes.
    BookingSessionService._sync_hold_and_payment_status(ctx.db, session)
    return {"booking_state": session["state"]}


async def care_tasks(ctx, args):
    plans = await CarePlanService.list_patient_care_plans(ctx.db, ctx.user, status_filter="ACTIVE")
    tasks = [{"title": task.title, "completed": task.isCompleted}
             for plan in plans.plans for task in plan.tasks]
    return {"tasks": tasks[:20]}


class CareAgenda(Arguments):
    day: date
    days: int = Field(default=1, ge=1, le=7)
    kind: Literal["all", "medication", "appointment", "test", "follow_up", "measurement"] = "all"


async def care_agenda(ctx, args):
    from app.routes.care_automation import get_agenda

    rows = get_agenda(ctx.db, str(ctx.user.id), args.day, args.days)
    return {"items": [
        {**row, "scheduledAt": row["scheduledAt"].isoformat()}
        for row in rows if args.kind == "all" or row["kind"] == args.kind
    ][:20]}


async def tracking_summary(ctx, args):
    rows = ctx.db["patient_health_measurements"].find(
        {"patientUserId": str(ctx.user.id)}, {"_id": 0, "patientUserId": 0, "recordedAt": 0},
    ).sort("recordedAt", -1).limit(5)
    return {"items": list(rows)}


TOOLS = {
    "get_my_care_agenda": Tool("Read the signed-in patient's scheduled care tasks.", CareAgenda, care_agenda),
    "get_my_health_tracking_summary": Tool("Read the signed-in patient's recent self-reported readings.", Arguments, tracking_summary),
    "search_verified_doctors": Tool("Find approved active doctors with matching public filters.", Search, search_doctors),
    "get_doctor_profile": Tool("Read an approved doctor's public profile.", Doctor, doctor_profile),
    "check_doctor_availability": Tool("Check slots and alternatives on a date in Asia/Colombo.", Availability, availability),
    "get_patient_appointments": Tool("Read the signed-in patient's appointments.", Appointments, appointments),
    "get_patient_care_tasks": Tool("Read assigned care tasks for the signed-in patient.", Arguments, care_tasks),
    "get_booking_session_status": Tool("Read the signed-in patient's booking state.", Session, booking_status),
}


class DoctorDates(Arguments):
    start: date
    end: date | None = None


class DoctorAppointment(Arguments):
    appointment_id: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{24}$")]


async def doctor_schedule(ctx, args):
    from app.services.doctor_workflow import schedule

    return {"appointments": schedule(ctx.db, ctx.user, args.start, args.end or args.start)}


async def doctor_slots(ctx, args):
    from app.services.consultation_service import ConsultationService

    profile = ConsultationService._verify_approved_doctor(ctx.db, ctx.user)
    return await availability(ctx, Availability(doctor_id=str(profile["_id"]), requested_date=args.start))


async def doctor_queue(ctx, args):
    from app.services.doctor_workflow import patient_queue

    return patient_queue(ctx.db, ctx.user, args.start)


async def doctor_next(ctx, args):
    queue = await doctor_queue(ctx, args)
    return {"nextPatient": queue["nextPatient"]}


async def doctor_preparation(ctx, args):
    from app.services.doctor_workflow import preparation

    return preparation(ctx.db, ctx.user, args.appointment_id)


async def doctor_analytics(ctx, args):
    from app.services.doctor_workflow import analytics

    return analytics(ctx.db, ctx.user, args.start, args.end or args.start)


async def doctor_follow_ups(ctx, args):
    from app.services.doctor_workflow import follow_ups

    return {"followUps": follow_ups(ctx.db, ctx.user)}


# These capabilities are selected locally by the doctor assistant. Only public
# search tools are exposed to external providers by the orchestrator.
DOCTOR_ROLES = frozenset({"DOCTOR"})
TOOLS.update({
    "get_my_doctor_schedule": Tool("Read your appointments.", DoctorDates, doctor_schedule, DOCTOR_ROLES),
    "get_my_available_slots": Tool("Read your available slots.", DoctorDates, doctor_slots, DOCTOR_ROLES),
    "get_my_patient_queue": Tool("Read your daily queue.", DoctorDates, doctor_queue, DOCTOR_ROLES),
    "get_next_queue_patient": Tool("Read the next eligible patient.", DoctorDates, doctor_next, DOCTOR_ROLES),
    "get_consultation_preparation": Tool("Prepare an assigned consultation.", DoctorAppointment, doctor_preparation, DOCTOR_ROLES),
    "get_my_follow_up_tasks": Tool("Read your follow-up plans.", Arguments, doctor_follow_ups, DOCTOR_ROLES),
    "get_my_doctor_analytics": Tool("Read your operational metrics.", DoctorDates, doctor_analytics, DOCTOR_ROLES),
})


# -----------------------------------------------------------------------------
# Phase 5: Admin AI Workflow and Automation Tools
# -----------------------------------------------------------------------------

class AdminTimeframeArgs(Arguments):
    timeframe: Literal["today", "last_7_days", "last_30_days", "custom"] = "last_30_days"
    start_date: str | None = None
    end_date: str | None = None


class AdminDoctorReviewArgs(Arguments):
    doctor_profile_id: Identifier


class AdminPaymentsArgs(Arguments):
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    search: str | None = None


class AdminSupportTicketArgs(Arguments):
    status: str | None = None
    category: str | None = None
    priority: str | None = None


class AdminTicketDetailArgs(Arguments):
    ticket_id: Identifier


class AdminRefundArgs(Arguments):
    refund_id: Identifier


class AdminReportArgs(Arguments):
    report_type: Literal[
        "daily_appointment",
        "monthly_payment",
        "doctor_verification_backlog",
        "support_ticket_resolution",
        "refund_status",
    ]
    start_date: str | None = None
    end_date: str | None = None


async def admin_dashboard_metrics(ctx, args):
    from app.services.admin_analytics_assistant import AdminAnalyticsAssistant
    return AdminAnalyticsAssistant.get_platform_analytics(
        ctx.db, args.timeframe, args.start_date, args.end_date
    )


async def admin_pending_doctor_verifications(ctx, args):
    from app.services.admin_service import AdminService
    apps = await AdminService.list_doctor_applications(ctx.db, "PENDING")
    return {"pendingApplications": [app.model_dump(mode="json") for app in apps]}


async def admin_doctor_verification_review(ctx, args):
    from app.services.doctor_verification_assistant import DoctorVerificationAssistant
    return DoctorVerificationAssistant.analyze_application(ctx.db, args.doctor_profile_id)


async def admin_payment_transactions(ctx, args):
    from app.services.payment_monitoring_service import PaymentMonitoringService
    return PaymentMonitoringService.list_monitored_payments(
        ctx.db, args.status, args.start_date, args.end_date, None, args.search, 1, 20
    )


async def admin_payment_reconciliation_issues(ctx, args):
    from app.services.payment_monitoring_service import PaymentMonitoringService
    return PaymentMonitoringService.run_reconciliation_checks(ctx.db)


async def admin_support_tickets(ctx, args):
    from app.services.support_ticket_service import SupportTicketService
    return SupportTicketService.list_tickets(
        ctx.db, str(ctx.user.id), is_admin=True, status_filter=args.status, category=args.category, priority=args.priority, page=1, page_size=20
    )


async def admin_draft_support_response(ctx, args):
    from app.services.support_ticket_service import SupportTicketService
    return SupportTicketService.generate_ai_ticket_draft(ctx.db, args.ticket_id)


async def admin_refund_request_details(ctx, args):
    from app.services.refund_service import RefundService
    return RefundService.get_refund_request(ctx.db, args.refund_id)


async def admin_report_data(ctx, args):
    from app.services.admin_report_service import AdminReportService
    report = AdminReportService.generate_report(ctx.db, args.report_type, args.start_date, args.end_date)
    return {
        "reportId": report["reportId"],
        "title": report["title"],
        "metrics": report["metrics"],
        "aiSummary": report["aiSummary"],
        "dateRange": report["dateRange"],
    }


ADMIN_ROLES = frozenset({"ADMIN"})
TOOLS.update({
    "get_admin_dashboard_metrics": Tool("Read operational and financial platform metrics.", AdminTimeframeArgs, admin_dashboard_metrics, ADMIN_ROLES),
    "get_pending_doctor_verifications": Tool("Read pending doctor verification submissions.", Arguments, admin_pending_doctor_verifications, ADMIN_ROLES),
    "get_doctor_verification_review": Tool("Analyze a doctor application for missing documents and credentials.", AdminDoctorReviewArgs, admin_doctor_verification_review, ADMIN_ROLES),
    "prepare_doctor_verification_decision": Tool("Prepare a structured recommendation for doctor approval or rejection.", AdminDoctorReviewArgs, admin_doctor_verification_review, ADMIN_ROLES),
    "get_payment_transactions": Tool("Read monitored platform payment records.", AdminPaymentsArgs, admin_payment_transactions, ADMIN_ROLES),
    "get_payment_reconciliation_issues": Tool("Detect payment and booking discrepancies across Stripe and MongoDB.", Arguments, admin_payment_reconciliation_issues, ADMIN_ROLES),
    "get_support_tickets": Tool("Read customer support tickets.", AdminSupportTicketArgs, admin_support_tickets, ADMIN_ROLES),
    "draft_support_response": Tool("Generate a grounded AI draft response for a customer support ticket.", AdminTicketDetailArgs, admin_draft_support_response, ADMIN_ROLES),
    "get_refund_request_details": Tool("Read refund request details and calculated policy eligibility.", AdminRefundArgs, admin_refund_request_details, ADMIN_ROLES),
    "prepare_refund_review": Tool("Prepare refund review summary and eligibility calculation.", AdminRefundArgs, admin_refund_request_details, ADMIN_ROLES),
    "get_admin_report_data": Tool("Read compiled operational and financial report metrics.", AdminReportArgs, admin_report_data, ADMIN_ROLES),
    "prepare_admin_report": Tool("Generate an operational report draft with grounded executive summary.", AdminReportArgs, admin_report_data, ADMIN_ROLES),
})


# -----------------------------------------------------------------------------
# Phase 6: Clinical Workflow, Medical Records & Healthcare AI Tools
# -----------------------------------------------------------------------------

class PatientRecordsArgs(Arguments):
    record_type: str | None = None
    page: int = 1
    page_size: int = 20


class PatientMeasurementsArgs(Arguments):
    metric: str | None = None
    limit: int = 50


class DoctorPatientTargetArgs(Arguments):
    patient_id: Identifier


class DoctorPatientRecordsArgs(DoctorPatientTargetArgs):
    record_type: str | None = None
    page: int = 1
    page_size: int = 20


class DoctorPatientMeasurementsArgs(DoctorPatientTargetArgs):
    metric: str | None = None
    limit: int = 50


class NoteDraftArgs(DoctorPatientTargetArgs):
    appointment_id: str | None = None
    raw_notes: str | None = None


class RenewalQueueArgs(Arguments):
    status: str | None = None


class MedicalRecordSummaryArgs(Arguments):
    patient_id: Identifier | None = None


class PrescriptionDocArgs(DoctorPatientTargetArgs):
    medications: list[str]


class RenewalRequestDraftArgs(Arguments):
    original_prescription_id: str
    medication_name: str
    reason: str | None = None


async def patient_medical_records(ctx, args):
    from app.services.patient_medical_record_service import PatientMedicalRecordService
    res = PatientMedicalRecordService.list_medical_records(
        ctx.db, ctx.user, record_type=args.record_type, page=args.page, page_size=args.page_size
    )
    return res.model_dump(mode="json")


async def patient_prescriptions(ctx, args):
    rows = list(ctx.db["prescriptions"].find(
        {"patientUserId": str(ctx.user.id), "status": {"$in": ["ISSUED", "ACTIVE", "signed"]}}
    ).sort("issuedAt", -1).limit(20))
    for r in rows:
        r["_id"] = str(r["_id"])
    return {"prescriptions": rows}


async def patient_measurements(ctx, args):
    from app.services.health_tracking_service import HealthTrackingService
    res = HealthTrackingService.list_measurements(
        ctx.db, ctx.user, metric=args.metric, limit=args.limit
    )
    return res.model_dump(mode="json")


async def patient_renewal_requests(ctx, args):
    from app.services.prescription_workflow_service import PrescriptionWorkflowService
    res = PrescriptionWorkflowService.list_renewal_requests(ctx.db, ctx.user)
    return res.model_dump(mode="json")


async def doctor_patient_records(ctx, args):
    from app.services.patient_medical_record_service import PatientMedicalRecordService
    res = PatientMedicalRecordService.list_medical_records(
        ctx.db, ctx.user, patient_id=args.patient_id, record_type=args.record_type, page=args.page, page_size=args.page_size
    )
    return res.model_dump(mode="json")


async def doctor_patient_measurements(ctx, args):
    from app.services.health_tracking_service import HealthTrackingService
    res = HealthTrackingService.list_measurements(
        ctx.db, ctx.user, patient_id=args.patient_id, metric=args.metric, limit=args.limit
    )
    return res.model_dump(mode="json")


async def doctor_patient_prescriptions(ctx, args):
    from app.services.clinical_safety_service import ClinicalSafetyService
    ClinicalSafetyService.verify_doctor_patient_care_relationship(ctx.db, str(ctx.user.id), args.patient_id)
    rows = list(ctx.db["prescriptions"].find(
        {"patientUserId": args.patient_id, "status": {"$in": ["ISSUED", "ACTIVE", "signed"]}}
    ).sort("issuedAt", -1).limit(20))
    for r in rows:
        r["_id"] = str(r["_id"])
    return {"prescriptions": rows}


async def doctor_consultation_note_draft(ctx, args):
    from app.services.clinical_documentation_service import ClinicalDocumentationService
    from app.schemas.clinical_workflow import CreateClinicalNoteDraftRequest
    if args.raw_notes:
        draft = ClinicalDocumentationService.create_note_draft(
            ctx.db, ctx.user, CreateClinicalNoteDraftRequest(
                patientUserId=args.patient_id,
                appointmentId=args.appointment_id,
                rawNotes=args.raw_notes,
            )
        )
        return draft.model_dump(mode="json")
    notes = ClinicalDocumentationService.list_notes(ctx.db, ctx.user, patient_id=args.patient_id)
    return notes.model_dump(mode="json")


async def doctor_prescription_renewal_queue(ctx, args):
    from app.services.prescription_workflow_service import PrescriptionWorkflowService
    res = PrescriptionWorkflowService.list_renewal_requests(ctx.db, ctx.user, status_filter=args.status)
    return res.model_dump(mode="json")


async def prepare_medical_record_summary(ctx, args):
    from app.services.patient_medical_record_service import PatientMedicalRecordService
    res = PatientMedicalRecordService.summarize_patient_history(ctx.db, ctx.user, patient_id=args.patient_id)
    return res.model_dump(mode="json")


async def prepare_clinical_note_draft(ctx, args):
    from app.services.clinical_documentation_service import ClinicalDocumentationService
    from app.schemas.clinical_workflow import CreateClinicalNoteDraftRequest
    draft = ClinicalDocumentationService.create_note_draft(
        ctx.db, ctx.user, CreateClinicalNoteDraftRequest(
            patientUserId=args.patient_id,
            appointmentId=args.appointment_id,
            rawNotes=args.raw_notes or "Review of symptoms and clinical examination.",
        )
    )
    return draft.model_dump(mode="json")


async def prepare_prescription_documentation(ctx, args):
    from app.services.prescription_workflow_service import PrescriptionWorkflowService
    res = PrescriptionWorkflowService.review_prescription_draft(
        ctx.db, ctx.user, args.patient_id, args.medications
    )
    return res.model_dump(mode="json")


async def prepare_renewal_request(ctx, args):
    from app.services.prescription_workflow_service import PrescriptionWorkflowService
    from app.schemas.clinical_workflow import CreatePrescriptionRenewalRequest
    res = PrescriptionWorkflowService.request_prescription_renewal(
        ctx.db, ctx.user, CreatePrescriptionRenewalRequest(
            originalPrescriptionId=args.original_prescription_id,
            medicationName=args.medication_name,
            patientReason=args.reason,
        )
    )
    return res.model_dump(mode="json")


PATIENT_ROLES = frozenset({"PATIENT"})
DOCTOR_ROLES = frozenset({"DOCTOR"})
PATIENT_AND_DOCTOR_ROLES = frozenset({"PATIENT", "DOCTOR"})

TOOLS.update({
    # Patient read tools
    "get_my_medical_records": Tool("Read your documented longitudinal medical records.", PatientRecordsArgs, patient_medical_records, PATIENT_ROLES),
    "get_my_prescriptions": Tool("Read your active doctor-prescribed medications.", Arguments, patient_prescriptions, PATIENT_ROLES),
    "get_my_health_measurements": Tool("Read your logged vital signs and health measurements.", PatientMeasurementsArgs, patient_measurements, PATIENT_ROLES),
    "get_my_renewal_requests": Tool("Read your submitted prescription renewal requests.", Arguments, patient_renewal_requests, PATIENT_ROLES),

    # Doctor read tools
    "get_authorized_patient_records": Tool("Read authorized patient longitudinal medical records.", DoctorPatientRecordsArgs, doctor_patient_records, DOCTOR_ROLES),
    "get_authorized_patient_measurements": Tool("Read authorized patient vital sign measurements and trends.", DoctorPatientMeasurementsArgs, doctor_patient_measurements, DOCTOR_ROLES),
    "get_authorized_patient_prescriptions": Tool("Read authorized patient active prescriptions and medications.", DoctorPatientTargetArgs, doctor_patient_prescriptions, DOCTOR_ROLES),
    "get_consultation_note_draft": Tool("Retrieve or prepare clinical consultation note draft.", NoteDraftArgs, doctor_consultation_note_draft, DOCTOR_ROLES),
    "get_prescription_renewal_queue": Tool("Read pending prescription renewal requests awaiting clinician review.", RenewalQueueArgs, doctor_prescription_renewal_queue, DOCTOR_ROLES),

    # Proposal & draft tools
    "prepare_medical_record_summary": Tool("Synthesize an authorized, source-grounded longitudinal medical record summary.", MedicalRecordSummaryArgs, prepare_medical_record_summary, PATIENT_AND_DOCTOR_ROLES),
    "prepare_clinical_note_draft": Tool("Organize consultation findings into a structured SOAP draft for doctor review.", NoteDraftArgs, prepare_clinical_note_draft, DOCTOR_ROLES),
    "prepare_prescription_documentation": Tool("Review proposed medications against patient allergies and active prescriptions.", PrescriptionDocArgs, prepare_prescription_documentation, DOCTOR_ROLES),
    "prepare_renewal_request": Tool("Draft and submit a prescription renewal request for clinician review.", RenewalRequestDraftArgs, prepare_renewal_request, PATIENT_ROLES),
})


# -----------------------------------------------------------------------------
# Phase 7: Advanced Security, Fraud Detection & Platform Reliability Tools
# -----------------------------------------------------------------------------

class IncidentArgs(Arguments):
    incident_id: str | None = None
    category: str | None = None
    status: str | None = None


class FraudAssessmentArgs(Arguments):
    assessment_id: str | None = None
    status: str | None = None


class WorkflowArgs(Arguments):
    status: str | None = None
    workflow_type: str | None = None


class DeadLetterArgs(Arguments):
    dead_letter_id: str | None = None


class SecuritySummaryArgs(Arguments):
    hours: int = 24


async def admin_platform_health(ctx, args):
    from app.services.platform_monitoring_service import PlatformMonitoringService
    return PlatformMonitoringService.get_platform_health_snapshot(ctx.db)


async def admin_fraud_alerts(ctx, args):
    from app.services.fraud_detection_service import FraudDetectionService
    res = FraudDetectionService.list_assessments(status=args.status, db=ctx.db)
    return {"items": [item.model_dump() for item in res["items"]], "total": res["total"]}


async def admin_fraud_review_details(ctx, args):
    if not args.assessment_id:
        return {"error": "assessment_id_required"}
    doc = ctx.db["fraud_risk_assessments"].find_one({"assessmentId": args.assessment_id})
    if doc:
        doc["_id"] = str(doc["_id"])
        return doc
    return {"error": "assessment_not_found"}


async def admin_security_events(ctx, args):
    from app.services.security_event_service import SecurityEventService
    res = SecurityEventService.list_security_events(limit=20, db=ctx.db)
    return {"items": [item.model_dump() for item in res["items"]], "total": res["total"]}


async def admin_notification_failures(ctx, args):
    from app.services.notification_monitoring_service import NotificationMonitoringService
    items = NotificationMonitoringService.list_dead_letters(limit=20, db=ctx.db)
    return {"dead_letters": items}


async def admin_notification_queue_status(ctx, args):
    from app.services.notification_monitoring_service import NotificationMonitoringService
    return NotificationMonitoringService.get_notification_metrics(ctx.db)


async def admin_worker_status(ctx, args):
    from app.services.platform_monitoring_service import PlatformMonitoringService
    workers = PlatformMonitoringService.get_worker_heartbeats(ctx.db)
    return {"workers": workers}


async def admin_ai_provider_metrics(ctx, args):
    from app.services.ai_provider_monitoring_service import AIProviderMonitoringService
    metrics = AIProviderMonitoringService.get_metrics()
    return {"ai_providers": metrics}


async def admin_stuck_workflows(ctx, args):
    from app.services.workflow_monitoring_service import WorkflowMonitoringService
    stuck = WorkflowMonitoringService.detect_stuck_workflows(ctx.db)
    return {"stuck_workflows": [item.model_dump() for item in stuck]}


async def admin_open_incidents(ctx, args):
    from app.services.incident_management_service import IncidentManagementService
    res = IncidentManagementService.list_incidents(status=args.status, category=args.category, db=ctx.db)
    return {"items": [item.model_dump() for item in res["items"]], "total": res["total"]}


async def admin_prepare_incident_summary(ctx, args):
    from app.services.incident_management_service import IncidentManagementService
    if not args.incident_id:
        return {"error": "incident_id_required"}
    return IncidentManagementService.generate_ai_incident_summary(args.incident_id, db=ctx.db)


async def admin_prepare_security_report(ctx, args):
    from app.services.security_event_service import SecurityEventService
    return SecurityEventService.get_security_summary(hours=args.hours, db=ctx.db)


TOOLS.update({
    "get_platform_health": Tool("Read comprehensive platform health and dependency status.", Arguments, admin_platform_health, ADMIN_ROLES),
    "get_fraud_alerts": Tool("Read pending fraud assessments and flagged suspicious activity.", FraudAssessmentArgs, admin_fraud_alerts, ADMIN_ROLES),
    "get_fraud_review_details": Tool("Read supporting evidence and rule triggers for a fraud assessment.", FraudAssessmentArgs, admin_fraud_review_details, ADMIN_ROLES),
    "get_security_events": Tool("Read recent security audit events and defensive blocks.", Arguments, admin_security_events, ADMIN_ROLES),
    "get_notification_failures": Tool("Read notification outbox failure and dead-letter items.", Arguments, admin_notification_failures, ADMIN_ROLES),
    "get_notification_queue_status": Tool("Read delivery rates, channel metrics, and outbox backlogs.", Arguments, admin_notification_queue_status, ADMIN_ROLES),
    "get_worker_status": Tool("Read background worker heartbeats and execution latencies.", Arguments, admin_worker_status, ADMIN_ROLES),
    "get_ai_provider_metrics": Tool("Read Gemini and OpenAI latency, error rates, and circuit breaker status.", Arguments, admin_ai_provider_metrics, ADMIN_ROLES),
    "get_stuck_workflows": Tool("Scan for automated healthcare workflows stuck in intermediate states.", Arguments, admin_stuck_workflows, ADMIN_ROLES),
    "get_open_incidents": Tool("Read active operational platform incidents.", IncidentArgs, admin_open_incidents, ADMIN_ROLES),
    "prepare_incident_summary": Tool("Generate structured investigation steps and contextual summary for an incident.", IncidentArgs, admin_prepare_incident_summary, ADMIN_ROLES),
    "prepare_security_report": Tool("Generate security posture breakdown and threat summary.", SecuritySummaryArgs, admin_prepare_security_report, ADMIN_ROLES),
})


