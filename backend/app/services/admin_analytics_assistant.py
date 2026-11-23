"""Admin analytics calculation service and AI narrative interpretation (Phase 5)."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from pymongo.database import Database

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
    """Calculate exact datetime and YYYY-MM-DD boundaries."""
    now = _utc_now()
    if timeframe == "today":
        start_dt = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=timezone.utc)
    elif timeframe == "last_7_days":
        start_dt = now - timedelta(days=7)
        end_dt = now
    elif timeframe == "custom" and start_date_str and end_date_str:
        try:
            start_dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        except Exception:
            start_dt = now - timedelta(days=30)
            end_dt = now
    else:  # last_30_days default
        start_dt = now - timedelta(days=30)
        end_dt = now

    return start_dt, end_dt, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


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

        # Geographical breakdown
        geo_colombo = db["appointments"].count_documents({
            **appt_query,
            "consultationLocation": {"$regex": "colombo", "$options": "i"},
        })
        geo_kandy = db["appointments"].count_documents({
            **appt_query,
            "consultationLocation": {"$regex": "kandy", "$options": "i"},
        })
        geo_galle = db["appointments"].count_documents({
            **appt_query,
            "consultationLocation": {"$regex": "galle", "$options": "i"},
        })

        # 3. Payments & Financial Metrics within date range
        pay_query: Dict[str, Any] = {
            "createdAt": {"$gte": start_dt, "$lte": end_dt}
        }
        succeeded_payments_cursor = db["payments"].find({
            **pay_query,
            "status": PaymentStatus.SUCCEEDED.value,
        })
        gross_processed = sum(float(p.get("amount", 0.0)) for p in succeeded_payments_cursor)

        failed_payments_count = db["payments"].count_documents({
            **pay_query,
            "status": PaymentStatus.FAILED.value,
        })
        succeeded_payments_count = db["payments"].count_documents({
            **pay_query,
            "status": PaymentStatus.SUCCEEDED.value,
        })
        total_payment_attempts = succeeded_payments_count + failed_payments_count
        payment_success_rate = (
            round((succeeded_payments_count / total_payment_attempts) * 100.0, 1)
            if total_payment_attempts > 0 else 100.0
        )

        # Refunds within date range
        refunds_cursor = db["refund_requests"].find({
            "updatedAt": {"$gte": start_dt, "$lte": end_dt},
            "status": RefundStatus.SUCCEEDED.value,
        })
        refund_totals = sum(float(r.get("amount", 0.0)) for r in refunds_cursor)

        # Net payments formula: Gross Processed Payments - Refunds
        net_payment_amount = round(gross_processed - refund_totals, 2)

        # Platform Revenue: 10% platform facilitation fee on net consultation volume
        platform_revenue = round(net_payment_amount * 0.10, 2)

        return {
            "timeframe": timeframe,
            "dateRange": {"startDate": start_str, "endDate": end_str},
            "currency": "LKR",
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
                "locations": {
                    "Colombo": geo_colombo,
                    "Kandy": geo_kandy,
                    "Galle": geo_galle,
                },
            },
            "financials": {
                "grossProcessedPayments": round(gross_processed, 2),
                "refundTotals": round(refund_totals, 2),
                "netPaymentAmount": net_payment_amount,
                "platformRevenue": platform_revenue,
                "paymentSuccessRate": payment_success_rate,
                "succeededTransactions": succeeded_payments_count,
                "failedTransactions": failed_payments_count,
            },
            "generatedAt": _utc_now().isoformat(),
        }
