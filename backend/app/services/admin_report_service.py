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
from app.services.financial_metrics import NO_REVENUE_MODEL_NOTE, payment_refunded_amount, payment_time_query, platform_financials

logger = logging.getLogger(__name__)


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "|", "%")


def _sanitize_csv_cell(val: Any) -> str:
    """Render one CSV cell safely (P04-N17).

    - Numbers are written as numbers; 0 is "0" (the former ``str(val or "")`` blanked every zero).
    - None is an empty cell.
    - Text that a spreadsheet could evaluate as a formula (leading =, +, -, @, tab, carriage return, | or %, also
      after leading spaces) is prefixed with a single quote so it is shown as text.
    """
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    s = str(val)
    if s.lstrip(" ").startswith(_FORMULA_PREFIXES) or s.startswith(_FORMULA_PREFIXES):
        return f"'{s}"
    return s


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def _rate(part: int, whole: int) -> Optional[float]:
    """A percentage, or None when there is nothing to divide by (never an invented 0% or 100%)."""
    return round(part / whole * 100.0, 1) if whole else None


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
        # Asia/Colombo days; one given date means that single day; an invalid date is a 400 (P04-N06).
        start_dt, end_dt, start_str, end_str = resolve_date_bounds("custom" if (start_date or end_date) else "last_30_days", start_date, end_date)
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
                "completionRate": _rate(completed, total),
            }
            items = [{
                "appointmentId": str(a["_id"]),
                "date": a.get("appointmentDate"),
                "startTime": a.get("startTime"),
                "status": a.get("status"),
                "paymentStatus": a.get("paymentStatus"),
            } for a in appts]

            ai_summary = (
                f"Operational report for {start_str} to {end_str}: Recorded {total} total appointments"
                + (f" with a {metrics['completionRate']}% completion rate. " if metrics['completionRate'] is not None else ". ") +
                f"{confirmed} appointments remain confirmed and active, while {cancelled} were cancelled."
            )

        elif report_type == "monthly_payment":
            title = f"Payment and Collections Summary ({start_str} to {end_str})"
            data_defs = {
                "capturedAmount": "Gross collections: payments captured in the range (SUCCEEDED or REFUNDED), per currency",
                "refundedAmount": "Money returned on those payments, including partial refunds",
                "netCollected": "Gross collections minus refunds. This is not platform profit",
                "pendingRefunds": "Refund requests still open and the amount set for them (not yet returned)",
                "platformRevenue": "Not calculated: no platform fee or doctor payout model is configured",
            }
            fin = platform_financials(db, start_dt, end_dt)
            pays = list(db["payments"].find(payment_time_query(start_dt, end_dt)).sort("createdAt", -1).limit(500))
            metrics = {
                "totalTransactions": len(pays),
                "succeededTransactions": fin["paymentCounts"]["SUCCEEDED"],
                "refundedTransactions": fin["paymentCounts"]["REFUNDED"],
                "failedTransactions": fin["paymentCounts"]["FAILED"],
                "paymentSuccessRate": fin["paymentSuccessRate"],
                "platformRevenue": None,
            }
            for cur, row in sorted(fin["byCurrency"].items()):
                code = cur.upper()
                metrics[f"capturedAmount{code}"] = row["capturedAmount"]
                metrics[f"refundedAmount{code}"] = row["refundedAmount"]
                metrics[f"netCollected{code}"] = row["netCollected"]
            for cur, row in sorted(fin["pendingRefunds"].items()):
                metrics[f"pendingRefundAmount{cur.upper()}"] = row["amount"]
                metrics[f"pendingRefundCount{cur.upper()}"] = row["count"]
            items = [{
                "paymentId": str(p["_id"]),
                "appointmentId": p.get("appointmentId"),
                "amount": float(p.get("amount") or 0.0),
                "refundedAmount": payment_refunded_amount(p) if p.get("status") in ("SUCCEEDED", "REFUNDED") else 0.0,
                "currency": (p.get("currency") or "lkr").upper(),
                "status": p.get("status"),
                "paidAt": _iso(p.get("paidAt")),
                "createdAt": _iso(p.get("createdAt")),
            } for p in pays]
            totals = "; ".join(
                f"{c.upper()} gross collections {r['capturedAmount']:,.2f}, refunded {r['refundedAmount']:,.2f}, "
                f"net collections {r['netCollected']:,.2f}" for c, r in sorted(fin["byCurrency"].items())
            ) or "no captured payments"
            ai_summary = (
                f"Collections summary ({start_str} to {end_str}, Asia/Colombo): {totals}. "
                f"{fin['paymentCounts']['SUCCEEDED'] + fin['paymentCounts']['REFUNDED']} captured payment(s). "
                + NO_REVENUE_MODEL_NOTE
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
                "submittedAt": _iso(p.get("submittedAt") or p.get("createdAt")),
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
                "resolutionRate": _rate(resolved_t, total_t),
            }
            items = [{
                "ticketId": t.get("ticketId"),
                "category": t.get("category"),
                "priority": t.get("priority"),
                "status": t.get("status"),
                "subject": t.get("subject"),
                "createdAt": _iso(t.get("createdAt")),
            } for t in tickets]

            ai_summary = (
                f"Support Ticket Report: {total_t} tickets handled between {start_str} and {end_str}. "
                + (f"Resolution rate stands at {metrics['resolutionRate']}% " if metrics['resolutionRate'] is not None else "")
                + f"with {open_t} open cases currently in queue."
            )

        elif report_type == "refund_status":
            title = f"Refund Status and Cancellation Settlement Report ({start_str} to {end_str})"
            data_defs = {
                "succeededRefunds": "Refunds confirmed by Stripe payment processor",
                "pendingReviews": "Refund requests under review by human administrators",
                "rejectedRefunds": "Refund requests rejected due to policy ineligibility",
            }
            refunds = list(db["refund_requests"].find({
                "createdAt": {"$gte": start_dt, "$lte": end_dt}
            }).sort("createdAt", -1).limit(500))

            succeeded = [r for r in refunds if r.get("status") == RefundStatus.SUCCEEDED.value]
            pending_r = sum(1 for r in refunds if r.get("status") in [RefundStatus.REQUESTED.value, RefundStatus.UNDER_REVIEW.value])
            processing_r = sum(1 for r in refunds if r.get("status") in [RefundStatus.APPROVED.value, RefundStatus.PROCESSING.value])
            failed_r = sum(1 for r in refunds if r.get("status") == RefundStatus.FAILED.value)
            rejected_r = sum(1 for r in refunds if r.get("status") == RefundStatus.REJECTED.value)

            def refunded_of(r):
                # The amount actually sent to Stripe, not the original payment amount the request was opened for.
                return float(r.get("refundedAmount") if r.get("refundedAmount") is not None else (r.get("approvedAmount") or 0.0))

            refunded_by_cur: Dict[str, float] = {}
            for r in succeeded:
                cur = (r.get("currency") or "lkr").upper()
                refunded_by_cur[cur] = round(refunded_by_cur.get(cur, 0.0) + refunded_of(r), 2)
            metrics = {
                "totalRequests": len(refunds),
                "succeededCount": len(succeeded),
                "pendingCount": pending_r,
                "processingCount": processing_r,
                "failedCount": failed_r,
                "rejectedCount": rejected_r,
                **{f"refundedAmount{cur}": amt for cur, amt in sorted(refunded_by_cur.items())},
            }
            items = [{
                "refundId": r.get("refundId"),
                "appointmentId": r.get("appointmentId"),
                "source": r.get("source") or ("doctor" if r.get("cancelledBy") == "DOCTOR" else None),
                "paymentAmount": float(r.get("amount") or 0.0),
                "eligibleAmount": (r.get("policyEligibility") or {}).get("eligibleAmount"),
                "refundedAmount": refunded_of(r) if r.get("status") == RefundStatus.SUCCEEDED.value else None,
                "currency": (r.get("currency") or "lkr").upper(),
                "status": r.get("status"),
                "reason": r.get("reason"),
                "stripeRefundId": r.get("stripeRefundId"),
                "createdAt": _iso(r.get("createdAt")),
            } for r in refunds]
            refunded_text = ", ".join(f"{c} {a:,.2f}" for c, a in sorted(refunded_by_cur.items())) or "nothing"
            ai_summary = (
                f"Refund Report ({start_str} to {end_str}, Asia/Colombo): {len(refunds)} refund request(s) opened. "
                f"{len(succeeded)} settled in Stripe ({refunded_text} returned), {pending_r} awaiting review, "
                f"{processing_r} processing, {failed_r} failed and retryable, {rejected_r} rejected."
            )

        else:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=f"Unsupported report type '{report_type}'.")

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
