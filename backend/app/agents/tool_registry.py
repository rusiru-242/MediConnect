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
        "weekly_booking",
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
