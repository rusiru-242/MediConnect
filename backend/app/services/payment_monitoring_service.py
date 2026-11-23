"""Payment monitoring and deterministic reconciliation service (Phase 5)."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.database import Database

from app.models.appointment import AppointmentStatus, PaymentStatus as ApptPaymentStatus
from app.models.payment import PaymentStatus

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaymentMonitoringService:
    """Monitors platform payment transactions and performs deterministic reconciliation."""

    @staticmethod
    def list_monitored_payments(
        db: Database,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        appointment_id: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Retrieve paginated payment transactions with associated booking statuses and masked details."""
        query: Dict[str, Any] = {}

        if status and status != "ALL":
            query["status"] = status.upper()

        if appointment_id:
            query["appointmentId"] = appointment_id

        if start_date or end_date:
            date_filter: Dict[str, Any] = {}
            if start_date:
                try:
                    date_filter["$gte"] = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                except Exception:
                    pass
            if end_date:
                try:
                    date_filter["$lte"] = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                except Exception:
                    pass
            if date_filter:
                query["createdAt"] = date_filter

        if search:
            query["$or"] = [
                {"stripePaymentIntentId": {"$regex": search, "$options": "i"}},
                {"paymentIntentId": {"$regex": search, "$options": "i"}},
                {"appointmentId": {"$regex": search, "$options": "i"}},
                {"paymentId": {"$regex": search, "$options": "i"}},
            ]

        coll = db["payments"]
        total = coll.count_documents(query)
        skip = max(0, (page - 1) * page_size)
        cursor = coll.find(query).sort("createdAt", -1).skip(skip).limit(page_size)

        # Bulk load appointment statuses
        payments = list(cursor)
        appt_ids = [p.get("appointmentId") for p in payments if p.get("appointmentId")]
        valid_oids = [ObjectId(a) for a in appt_ids if ObjectId.is_valid(a)]
        appts = {str(a["_id"]): a for a in db["appointments"].find({"_id": {"$in": valid_oids}})}

        # Bulk load patient names
        user_ids = [p.get("patientUserId") for p in payments if p.get("patientUserId")]
        valid_user_oids = [ObjectId(u) for u in user_ids if ObjectId.is_valid(u)]
        users = {str(u["_id"]): u for u in db["users"].find({"_id": {"$in": valid_user_oids}})}

        items = []
        for p in payments:
            appt_id = p.get("appointmentId")
            appt = appts.get(appt_id, {})
            u_id = p.get("patientUserId")
            user = users.get(u_id, {})

            # Mask patient name for privacy
            raw_name = user.get("fullName", "")
            masked_name = f"{raw_name[:2]}***{raw_name[-1]}" if len(raw_name) > 3 else "Patient"

            intent_id = p.get("stripePaymentIntentId") or p.get("paymentIntentId", "")
            items.append({
                "id": str(p["_id"]),
                "paymentId": p.get("paymentId") or str(p["_id"]),
                "appointmentId": appt_id,
                "stripePaymentIntentId": intent_id,
                "amount": float(p.get("amount", 0)),
                "currency": p.get("currency", "LKR"),
                "status": p.get("status", PaymentStatus.PENDING.value),
                "bookingStatus": appt.get("status", "UNKNOWN"),
                "patientName": masked_name,
                "createdAt": p.get("createdAt", _utc_now()),
                "updatedAt": p.get("updatedAt", _utc_now()),
                "isRefunded": p.get("status") == PaymentStatus.REFUNDED.value or appt.get("paymentStatus") == ApptPaymentStatus.REFUNDED.value,
            })

        return {"items": items, "total": total, "page": page, "pageSize": page_size}

    @staticmethod
    def run_reconciliation_checks(db: Database) -> Dict[str, Any]:
        """Perform deterministic reconciliation across payments and appointments."""
        discrepancies: List[Dict[str, Any]] = []
        now = _utc_now()
        thirty_mins_ago = now - timedelta(minutes=30)

        # Check 1: Succeeded Stripe payments where appointment is NOT confirmed or completed
        succeeded_payments = list(db["payments"].find({
            "status": PaymentStatus.SUCCEEDED.value,
        }).sort("createdAt", -1).limit(500))

        appt_ids = [p.get("appointmentId") for p in succeeded_payments if p.get("appointmentId")]
        valid_oids = [ObjectId(a) for a in appt_ids if ObjectId.is_valid(a)]
        appts_map = {str(a["_id"]): a for a in db["appointments"].find({"_id": {"$in": valid_oids}})}

        appt_payment_counts: Dict[str, int] = {}
        for p in succeeded_payments:
            appt_id = p.get("appointmentId")
            if not appt_id:
                continue

            intent_id = p.get("stripePaymentIntentId") or p.get("paymentIntentId", str(p["_id"]))
            appt_payment_counts[appt_id] = appt_payment_counts.get(appt_id, 0) + 1
            appt = appts_map.get(appt_id)

            if not appt:
                discrepancies.append({
                    "discrepancyId": f"DISC-MAPPT-{intent_id}",
                    "type": "MISSING_APPOINTMENT_FOR_PAYMENT",
                    "severity": "HIGH",
                    "paymentId": str(p["_id"]),
                    "appointmentId": appt_id,
                    "stripePaymentIntentId": intent_id,
                    "description": f"Payment {intent_id} succeeded but linked appointment {appt_id} does not exist.",
                    "recommendation": "Investigate appointment creation failure and initiate refund or manual booking confirmation.",
                    "detectedAt": now,
                })
            elif appt.get("status") not in [AppointmentStatus.CONFIRMED.value, AppointmentStatus.COMPLETED.value]:
                discrepancies.append({
                    "discrepancyId": f"DISC-UNCONF-{intent_id}",
                    "type": "UNCONFIRMED_PAID_APPOINTMENT",
                    "severity": "HIGH",
                    "paymentId": str(p["_id"]),
                    "appointmentId": appt_id,
                    "stripePaymentIntentId": intent_id,
                    "description": f"Payment {intent_id} succeeded, but appointment is currently in state '{appt.get('status')}'.",
                    "recommendation": "Confirm appointment booking immediately or issue refund if hold was abandoned.",
                    "detectedAt": now,
                })

        # Check 2: Duplicate payments for the same appointment
        for appt_id, count in appt_payment_counts.items():
            if count > 1:
                discrepancies.append({
                    "discrepancyId": f"DISC-DUP-{appt_id}",
                    "type": "DUPLICATE_PAYMENT",
                    "severity": "HIGH",
                    "appointmentId": appt_id,
                    "description": f"Found {count} successful payments referencing the same appointment {appt_id}.",
                    "recommendation": "Review duplicate transactions and refund the redundant payment immediately.",
                    "detectedAt": now,
                })

        # Check 3: Appointments marked PAID without a valid successful payment record
        paid_appts = list(db["appointments"].find({
            "paymentStatus": ApptPaymentStatus.PAID.value,
        }).sort("createdAt", -1).limit(200))

        for appt in paid_appts:
            aid = str(appt["_id"])
            matching_pay = db["payments"].find_one({
                "appointmentId": aid,
                "status": PaymentStatus.SUCCEEDED.value,
            })
            if not matching_pay:
                discrepancies.append({
                    "discrepancyId": f"DISC-NOPAY-{aid}",
                    "type": "MISSING_PAYMENT_EVIDENCE",
                    "severity": "HIGH",
                    "appointmentId": aid,
                    "description": f"Appointment {aid} is marked as PAID but has no verified SUCCEEDED payment record.",
                    "recommendation": "Check Stripe payment logs for manual charges or revert appointment payment status.",
                    "detectedAt": now,
                })

        # Check 4: Delayed pending payments (pending > 30 minutes)
        delayed_pending = list(db["payments"].find({
            "status": PaymentStatus.PENDING.value,
            "createdAt": {"$lt": thirty_mins_ago},
        }).limit(50))

        for p in delayed_pending:
            intent_id = p.get("stripePaymentIntentId") or p.get("paymentIntentId", str(p["_id"]))
            discrepancies.append({
                "discrepancyId": f"DISC-DELAY-{intent_id}",
                "type": "DELAYED_PENDING",
                "severity": "MEDIUM",
                "paymentId": str(p["_id"]),
                "appointmentId": p.get("appointmentId"),
                "stripePaymentIntentId": intent_id,
                "description": f"Payment {intent_id} has been pending for over 30 minutes.",
                "recommendation": "Check webhook status in Stripe Dashboard or expire stale checkout session.",
                "detectedAt": now,
            })

        total_checked = len(succeeded_payments) + len(paid_appts) + len(delayed_pending)
        return {
            "discrepancies": discrepancies,
            "totalChecked": total_checked,
            "discrepanciesCount": len(discrepancies),
            "checkedAt": now,
        }
