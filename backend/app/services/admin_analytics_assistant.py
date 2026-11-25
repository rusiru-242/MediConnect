"""Admin analytics calculation service and AI narrative interpretation (Phase 5)."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from pymongo.database import Database

from app.services.financial_metrics import PLATFORM_TZ_NAME, platform_financials, platform_range
from app.models.appointment import AppointmentStatus, PaymentStatus as ApptPaymentStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.payment import PaymentStatus
from app.models.refund_request import RefundStatus
from app.models.user import UserRole

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_date_bounds(
    timeframe: str = "last_30_days",
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> tuple[datetime, datetime, str, str]:
    """Asia/Colombo calendar-day bounds (P04-N06).

    Before Phase 04 these were UTC instants: "today" was the UTC day, and a custom range "2026-11-25 to 2026-11-25"
    ended at 00:00, so it excluded the whole end day. An invalid custom date silently became "last 30 days"; it is
    now a 400. "last_7_days" and "last_30_days" include today.
    """
    if timeframe == "custom" and (start_date_str or end_date_str):
        return platform_range(start_date_str or end_date_str, end_date_str or start_date_str)
    days = {"today": 1, "last_7_days": 7}.get(timeframe, 30)
    return platform_range(None, None, default_days=days)


class AdminAnalyticsAssistant:
    """Calculates operational and financial platform metrics using authoritative MongoDB records."""

    @staticmethod
    def get_platform_analytics(
        db: Database,
        timeframe: str = "last_30_days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compute accurate platform metrics across accounts, appointments, and payments."""
        start_dt, end_dt, start_str, end_str = resolve_date_bounds(timeframe, start_date, end_date)

        # 1. Accounts Metrics
        total_patients = db["users"].count_documents({"role": UserRole.PATIENT.value})
        total_doctors = db["users"].count_documents({"role": UserRole.DOCTOR.value})
        approved_doctors = db["doctor_profiles"].count_documents({
            "verificationStatus": DoctorVerificationStatus.APPROVED.value
        })
        pending_verifications = db["doctor_profiles"].count_documents({
            "verificationStatus": {
                "$in": [
                    DoctorVerificationStatus.PENDING.value,
                    DoctorVerificationStatus.PENDING_ADMIN_APPROVAL.value,
                ]
            }
        })

        # 2. Appointments Metrics within date range
        appt_query: Dict[str, Any] = {
            "appointmentDate": {"$gte": start_str, "$lte": end_str}
        }
        total_appts = db["appointments"].count_documents(appt_query)
        confirmed_appts = db["appointments"].count_documents({**appt_query, "status": AppointmentStatus.CONFIRMED.value})
        completed_appts = db["appointments"].count_documents({**appt_query, "status": AppointmentStatus.COMPLETED.value})
        cancelled_appts = db["appointments"].count_documents({**appt_query, "status": AppointmentStatus.CANCELLED.value})

        successful_bookings = confirmed_appts + completed_appts
        booking_conversion_rate = round((successful_bookings / total_appts) * 100.0, 1) if total_appts > 0 else 0.0

        # Appointments are in person at the doctor's clinic; there is no appointment location field to group by,
        # so no city breakdown is reported (the former Colombo/Kandy/Galle counts were always 0).

        # Money: the shared refund-aware calculation (P04-N05). No platform revenue is invented.
        fin = platform_financials(db, start_dt, end_dt)
        by_currency = fin["byCurrency"]
        counts = fin["paymentCounts"]

        return {
            "timeframe": timeframe,
            "dateRange": {"startDate": start_str, "endDate": end_str},
            "accounts": {
                "totalRegisteredPatients": total_patients,
                "totalRegisteredDoctors": total_doctors,
                "approvedDoctors": approved_doctors,
                "pendingDoctorVerifications": pending_verifications,
            },
            "appointments": {
                "totalAppointments": total_appts,
                "confirmedAppointments": confirmed_appts,
                "completedAppointments": completed_appts,
                "cancelledAppointments": cancelled_appts,
                "bookingConversionRate": booking_conversion_rate,
            },
            "financials": {
                "byCurrency": by_currency,
                "pendingRefunds": fin["pendingRefunds"],
                "paymentSuccessRate": fin["paymentSuccessRate"],
                "succeededTransactions": counts["SUCCEEDED"],
                "refundedTransactions": counts["REFUNDED"],
                "failedTransactions": counts["FAILED"],
                "pendingTransactions": counts["PENDING"],
                "platformRevenue": None,
                "doctorEarnings": None,
                "note": fin["note"],
            },
            "timezone": PLATFORM_TZ_NAME,
            "generatedAt": _utc_now().isoformat(),
        }
