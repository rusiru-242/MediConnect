"""Admin operational report generation and CSV export service (Phase 5)."""

import csv
from datetime import datetime, timezone
import io
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pymongo.database import Database

from app.models.appointment import AppointmentStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.payment import PaymentStatus
from app.models.refund_request import RefundStatus
from app.models.support_ticket import TicketStatus
from app.services.admin_analytics_assistant import resolve_date_bounds

logger = logging.getLogger(__name__)


def _sanitize_csv_cell(val: Any) -> str:
    """Escape text to prevent CSV injection formula execution."""
    s = str(val or "")
    if s.startswith(("=", "+", "-", "@")):
        return f"'{s}"
    return s


class AdminReportService:
    """Generates structured operational reports and safe CSV data exports."""

    @classmethod
    def generate_report(
        cls,
        db: Database,
        report_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compile a verified operational report with data definitions and grounded executive summary."""
        report_id = f"RPT-{uuid4().hex[:10].upper()}"
        start_dt, end_dt, start_str, end_str = resolve_date_bounds("custom" if (start_date and end_date) else "last_30_days", start_date, end_date)
        date_range = {"startDate": start_str, "endDate": end_str}
        now = datetime.now(timezone.utc)

        if report_type == "daily_appointment":
            title = f"Daily Appointment Operations Report ({start_str})"
            data_defs = {
                "totalAppointments": "Count of all appointments scheduled for the target date range",
                "completed": "Appointments successfully completed by doctor",
                "confirmed": "Appointments active and awaiting clinician attendance",
                "cancelled": "Appointments cancelled by doctor or patient",
            }
            appts = list(db["appointments"].find({
                "appointmentDate": {"$gte": start_str, "$lte": end_str}
            }).sort("startTime", 1).limit(500))

            total = len(appts)
            completed = sum(1 for a in appts if a.get("status") == AppointmentStatus.COMPLETED.value)
            confirmed = sum(1 for a in appts if a.get("status") == AppointmentStatus.CONFIRMED.value)
            cancelled = sum(1 for a in appts if a.get("status") == AppointmentStatus.CANCELLED.value)

            metrics = {
                "totalAppointments": total,
                "completed": completed,
                "confirmed": confirmed,
                "cancelled": cancelled,
                "completionRate": round((completed / total) * 100.0, 1) if total > 0 else 0.0,
            }
            items = [{
                "appointmentId": str(a["_id"]),
                "date": a.get("appointmentDate"),
                "startTime": a.get("startTime"),
                "status": a.get("status"),
                "paymentStatus": a.get("paymentStatus"),
            } for a in appts]

            ai_summary = (
                f"Operational report for {start_str} to {end_str}: Recorded {total} total appointments with a {metrics['completionRate']}% completion rate. "
                f"{confirmed} appointments remain confirmed and active, while {cancelled} were cancelled."
            )

        elif report_type == "monthly_payment":
            title = f"Monthly Payment and Financial Summary ({start_str} to {end_str})"
            data_defs = {
                "grossProcessed": "Total monetary volume of SUCCEEDED patient payments (LKR)",
                "totalRefunds": "Total refunded amounts processed via Stripe (LKR)",
                "netRevenue": "Gross Processed Payments minus Total Refunds (LKR)",
                "platformFee": "10% facilitation commission retained by MediConnect platform (LKR)",
            }
            pays = list(db["payments"].find({
                "createdAt": {"$gte": start_dt, "$lte": end_dt}
            }).sort("createdAt", -1).limit(500))

            succeeded = [p for p in pays if p.get("status") == PaymentStatus.SUCCEEDED.value]
            gross = sum(float(p.get("amount", 0.0)) for p in succeeded)

            refunds = list(db["refund_requests"].find({
                "updatedAt": {"$gte": start_dt, "$lte": end_dt},
                "status": RefundStatus.SUCCEEDED.value,
            }))
            total_refunds = sum(float(r.get("amount", 0.0)) for r in refunds)
            net_revenue = round(gross - total_refunds, 2)
            platform_fee = round(net_revenue * 0.10, 2)

            metrics = {
                "succeededTransactions": len(succeeded),
                "totalTransactions": len(pays),
                "grossProcessedLKR": round(gross, 2),
                "totalRefundsLKR": round(total_refunds, 2),
                "netRevenueLKR": net_revenue,
                "platformFeeLKR": platform_fee,
            }
            items = [{
                "paymentId": p.get("paymentId") or str(p["_id"]),
                "appointmentId": p.get("appointmentId"),
                "amount": float(p.get("amount", 0.0)),
                "currency": p.get("currency", "LKR"),
                "status": p.get("status"),
                "createdAt": p.get("createdAt", now).isoformat() if isinstance(p.get("createdAt"), datetime) else str(p.get("createdAt")),
            } for p in pays]

            ai_summary = (
                f"Financial Summary ({start_str} to {end_str}): Processed LKR {gross:,.2f} across {len(succeeded)} successful transactions. "
                f"Total refunds amounted to LKR {total_refunds:,.2f}, resulting in net processed volume of LKR {net_revenue:,.2f} and platform commission of LKR {platform_fee:,.2f}."
            )

        elif report_type == "doctor_verification_backlog":
            title = "Doctor Verification Backlog & Credentialing Report"
            data_defs = {
                "pendingProfiles": "Doctors awaiting admin verification and SLMC credentials check",
                "approvedProfiles": "Active verified medical clinicians",
                "rejectedProfiles": "Submissions rejected with explanatory reason",
            }
            profs = list(db["doctor_profiles"].find({}).sort("submittedAt", -1).limit(200))
            pending = [p for p in profs if p.get("verificationStatus") in [DoctorVerificationStatus.PENDING.value, DoctorVerificationStatus.PENDING_ADMIN_APPROVAL.value]]
            approved = [p for p in profs if p.get("verificationStatus") == DoctorVerificationStatus.APPROVED.value]
            rejected = [p for p in profs if p.get("verificationStatus") == DoctorVerificationStatus.REJECTED.value]

            metrics = {
                "totalSubmissions": len(profs),
                "pendingCount": len(pending),
                "approvedCount": len(approved),
                "rejectedCount": len(rejected),
            }
            items = [{
                "doctorProfileId": str(p["_id"]),
                "specialty": p.get("specialty"),
                "regNumber": p.get("medicalRegistrationNumber"),
                "status": p.get("verificationStatus"),
                "submittedAt": p.get("submittedAt", now).isoformat() if isinstance(p.get("submittedAt"), datetime) else str(p.get("submittedAt")),
            } for p in profs]

            ai_summary = (
                f"Doctor Verification Overview: Currently {len(pending)} clinician applications awaiting verification. "
                f"{len(approved)} approved active doctors and {len(rejected)} rejected applications on record."
            )

        elif report_type == "support_ticket_resolution":
            title = "Customer Support Resolution Report"
            data_defs = {
                "openTickets": "Tickets awaiting initial or follow-up response",
                "resolvedTickets": "Tickets successfully resolved by administration",
                "totalTickets": "Total support tickets created within period",
            }
            tickets = list(db["support_tickets"].find({
                "createdAt": {"$gte": start_dt, "$lte": end_dt}
            }).sort("createdAt", -1).limit(500))

            total_t = len(tickets)
            open_t = sum(1 for t in tickets if t.get("status") in [TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value])
            resolved_t = sum(1 for t in tickets if t.get("status") in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value])

            metrics = {
                "totalTickets": total_t,
                "openCount": open_t,
                "resolvedCount": resolved_t,
                "resolutionRate": round((resolved_t / total_t) * 100.0, 1) if total_t > 0 else 0.0,
            }
            items = [{
                "ticketId": t.get("ticketId"),
                "category": t.get("category"),
                "priority": t.get("priority"),
                "status": t.get("status"),
                "subject": t.get("subject"),
                "createdAt": t.get("createdAt", now).isoformat() if isinstance(t.get("createdAt"), datetime) else str(t.get("createdAt")),
            } for t in tickets]

            ai_summary = (
                f"Support Ticket Report: {total_t} tickets handled between {start_str} and {end_str}. "
                f"Resolution rate stands at {metrics['resolutionRate']}% with {open_t} open cases currently in queue."
            )

        else:  # refund_status or default
            report_type = "refund_status"
            title = f"Refund Status and Cancellation Settlement Report ({start_str} to {end_str})"
            data_defs = {
                "succeededRefunds": "Refunds confirmed by Stripe payment processor",
                "pendingReviews": "Refund requests under review by human administrators",
                "rejectedRefunds": "Refund requests rejected due to policy ineligibility",
            }
            refunds = list(db["refund_requests"].find({
                "createdAt": {"$gte": start_dt, "$lte": end_dt}
            }).sort("createdAt", -1).limit(500))

            succeeded_r = sum(1 for r in refunds if r.get("status") == RefundStatus.SUCCEEDED.value)
            pending_r = sum(1 for r in refunds if r.get("status") in [RefundStatus.REQUESTED.value, RefundStatus.UNDER_REVIEW.value])
            rejected_r = sum(1 for r in refunds if r.get("status") == RefundStatus.REJECTED.value)
            total_refunded_amt = sum(float(r.get("amount", 0.0)) for r in refunds if r.get("status") == RefundStatus.SUCCEEDED.value)

            metrics = {
                "totalRequests": len(refunds),
                "succeededCount": succeeded_r,
                "pendingCount": pending_r,
                "rejectedCount": rejected_r,
                "totalRefundedLKR": round(total_refunded_amt, 2),
            }
            items = [{
                "refundId": r.get("refundId"),
                "appointmentId": r.get("appointmentId"),
                "amount": float(r.get("amount", 0.0)),
                "currency": r.get("currency", "LKR"),
                "status": r.get("status"),
                "reason": r.get("reason"),
                "stripeRefundId": r.get("stripeRefundId"),
            } for r in refunds]

            ai_summary = (
                f"Refund Report ({start_str} to {end_str}): Evaluated {len(refunds)} total refund requests. "
                f"{succeeded_r} refunds were approved and settled for LKR {total_refunded_amt:,.2f}. {pending_r} requests remain pending review."
            )

        return {
            "reportId": report_id,
            "reportType": report_type,
            "title": title,
            "dateRange": date_range,
            "generatedAt": now,
            "dataDefinitions": data_defs,
            "metrics": metrics,
            "items": items,
            "aiSummary": ai_summary,
        }

    @classmethod
    def export_csv(cls, db: Database, report_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """Export report dataset as a sanitized CSV string."""
        report = cls.generate_report(db, report_type, start_date, end_date)
        output = io.StringIO()
        writer = csv.writer(output)

        # Write metadata headers
        writer.writerow(["# MediConnect Operational Report", report["title"]])
        writer.writerow(["# Generated At", report["generatedAt"].isoformat()])
        writer.writerow(["# Date Range", f"{report['dateRange']['startDate']} to {report['dateRange']['endDate']}"])
        writer.writerow([])

        # Write metrics
        writer.writerow(["Metric", "Value"])
        for k, v in report["metrics"].items():
            writer.writerow([k, _sanitize_csv_cell(v)])
        writer.writerow([])

        # Write data table items
        items = report["items"]
        if items:
            headers = list(items[0].keys())
            writer.writerow(headers)
            for row in items:
                writer.writerow([_sanitize_csv_cell(row.get(h, "")) for h in headers])
        else:
            writer.writerow(["No matching records found for the selected timeframe."])

        return output.getvalue()
