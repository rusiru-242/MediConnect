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

        # Check 1: captured payments whose booking is not an active or completed visit (P04-N11).
        # Before Phase 04 every such payment was "UNCONFIRMED_PAID_APPOINTMENT" with the advice "Confirm appointment
        # booking immediately", including bookings the doctor had cancelled with a refund request already open.
        # Confirming a cancelled booking from monitoring would bypass the booking state machine, so the advice now
        # only ever points at the refund queue or the reconciliation refund action.
        succeeded_payments = list(db["payments"].find({
            "status": {"$in": [PaymentStatus.SUCCEEDED.value, PaymentStatus.REFUNDED.value]},
        }).sort("createdAt", -1).limit(500))

        appt_ids = [p.get("appointmentId") for p in succeeded_payments if p.get("appointmentId")]
        valid_oids = [ObjectId(a) for a in appt_ids if ObjectId.is_valid(a)]
        appts_map = {str(a["_id"]): a for a in db["appointments"].find({"_id": {"$in": valid_oids}})}
        refunds_by_appt: Dict[str, List[Dict[str, Any]]] = {}
        for r in db["refund_requests"].find({"appointmentId": {"$in": appt_ids}},
                                            {"appointmentId": 1, "status": 1, "refundId": 1}):
            refunds_by_appt.setdefault(r["appointmentId"], []).append(r)

        appt_payment_counts: Dict[str, int] = {}
        intent_counts: Dict[str, List[str]] = {}
        for p in succeeded_payments:
            appt_id = p.get("appointmentId")
            intent_id = p.get("stripePaymentIntentId") or p.get("paymentIntentId") or str(p["_id"])
            if p.get("stripePaymentIntentId"):
                intent_counts.setdefault(p["stripePaymentIntentId"], []).append(str(p["_id"]))
            if not appt_id:
                discrepancies.append({
                    "discrepancyId": f"DISC-NOAPPT-{p['_id']}", "type": "PAYMENT_WITHOUT_APPOINTMENT",
                    "severity": "HIGH", "paymentId": str(p["_id"]), "stripePaymentIntentId": intent_id,
                    "description": "A captured payment is not linked to any appointment.",
                    "recommendation": "Investigate the payment in Stripe test mode and refund it through the reconciliation action if no booking exists.",
                    "detectedAt": now,
                })
                continue
            fully_refunded = p.get("status") == PaymentStatus.REFUNDED.value
            if not fully_refunded:
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
                    "description": f"Payment {intent_id} was captured but linked appointment {appt_id} does not exist.",
                    "recommendation": "Investigate the booking failure and refund the payment; do not create a booking manually.",
                    "detectedAt": now,
                })
                continue

            # Amount and currency must match what the booking accepted.
            expected_minor = appt.get("acceptedAmountMinor")
            if not isinstance(expected_minor, int):
                # Older bookings and the standard booking path lock the fee in consultationFee.
                from app.agents.doctor_ranking import coerce_fee
                locked = coerce_fee(appt.get("consultationFee"))
                expected_minor = int(round(locked * 100)) if locked is not None else None
            paid_minor = int(round(float(p.get("amount") or 0.0) * 100))
            if isinstance(expected_minor, int) and expected_minor != paid_minor:
                discrepancies.append({
                    "discrepancyId": f"DISC-AMOUNT-{intent_id}", "type": "AMOUNT_MISMATCH", "severity": "HIGH",
                    "paymentId": str(p["_id"]), "appointmentId": appt_id, "stripePaymentIntentId": intent_id,
                    "description": f"Payment amount {paid_minor / 100:,.2f} differs from the amount accepted at booking ({expected_minor / 100:,.2f}).",
                    "recommendation": "Compare with the PaymentIntent in Stripe test mode before any refund or status change.",
                    "detectedAt": now,
                })
            booking_currency = (appt.get("bookingCurrency") or "").lower()
            if booking_currency and (p.get("currency") or "").lower() != booking_currency:
                discrepancies.append({
                    "discrepancyId": f"DISC-CURRENCY-{intent_id}", "type": "CURRENCY_MISMATCH", "severity": "HIGH",
                    "paymentId": str(p["_id"]), "appointmentId": appt_id, "stripePaymentIntentId": intent_id,
                    "description": f"Payment currency {(p.get('currency') or '?').upper()} differs from the booking currency {booking_currency.upper()}.",
                    "recommendation": "Compare with the PaymentIntent in Stripe test mode before any refund or status change.",
                    "detectedAt": now,
                })

            status_now = appt.get("status")
            if fully_refunded or status_now in [AppointmentStatus.CONFIRMED.value, AppointmentStatus.COMPLETED.value]:
                continue
            refunds = refunds_by_appt.get(appt_id, [])
            open_refund = next((r for r in refunds if r.get("status") in
                                ("requested", "under_review", "approved", "processing", "failed")), None)
            refunded_amount = float(p.get("refundedAmount") or 0.0)
            if status_now == AppointmentStatus.CANCELLED.value and open_refund:
                discrepancies.append({
                    "discrepancyId": f"DISC-REFUNDQ-{intent_id}", "type": "CANCELLED_AWAITING_REFUND_DECISION",
                    "severity": "LOW", "paymentId": str(p["_id"]), "appointmentId": appt_id,
                    "stripePaymentIntentId": intent_id,
                    "description": f"Cancelled booking with a captured payment; refund request {open_refund.get('refundId')} is {open_refund.get('status')}.",
                    "recommendation": "Review the refund request in the Refunds queue.",
                    "detectedAt": now,
                })
            elif status_now == AppointmentStatus.CANCELLED.value and (refunded_amount > 0 or any(r.get("status") in ("succeeded", "rejected") for r in refunds)):
                continue  # refund decided (partial refund or rejection under the existing policy)
            elif status_now == AppointmentStatus.CANCELLED.value:
                discrepancies.append({
                    "discrepancyId": f"DISC-NOREFUND-{intent_id}", "type": "CANCELLED_PAID_WITHOUT_REFUND_REQUEST",
                    "severity": "HIGH", "paymentId": str(p["_id"]), "appointmentId": appt_id,
                    "stripePaymentIntentId": intent_id,
                    "description": f"Booking was cancelled by {appt.get('cancelledBy') or 'unknown'} but the captured payment has no refund request.",
                    "recommendation": "Open a refund review under the existing cancellation policy; do not re-confirm the booking.",
                    "detectedAt": now,
                })
            else:
                discrepancies.append({
                    "discrepancyId": f"DISC-UNCONF-{intent_id}",
                    "type": "UNCONFIRMED_PAID_APPOINTMENT",
                    "severity": "HIGH",
                    "paymentId": str(p["_id"]),
                    "appointmentId": appt_id,
                    "stripePaymentIntentId": intent_id,
                    "description": f"Payment {intent_id} was captured, but the booking is in state '{status_now}' (reconciliation state: {p.get('reconciliationState') or 'none'}).",
                    "recommendation": "Let payment verification finish or the hold expire; if it cannot confirm, use the reconciliation refund action. Never confirm the booking from monitoring.",
                    "detectedAt": now,
                })

        # Check 2: duplicate captured payments for one appointment, and one PaymentIntent recorded twice.
        for appt_id, count in appt_payment_counts.items():
            if count > 1:
                discrepancies.append({
                    "discrepancyId": f"DISC-DUP-{appt_id}",
                    "type": "DUPLICATE_PAYMENT",
                    "severity": "HIGH",
                    "appointmentId": appt_id,
                    "description": f"Found {count} captured, unrefunded payments for the same appointment {appt_id}.",
                    "recommendation": "Review the duplicate transactions and refund the redundant payment after checking Stripe test mode.",
                    "detectedAt": now,
                })
        for intent_id, payment_ids in intent_counts.items():
            if len(payment_ids) > 1:
                discrepancies.append({
                    "discrepancyId": f"DISC-DUPPI-{intent_id}", "type": "DUPLICATE_PAYMENT_INTENT_REFERENCE",
                    "severity": "HIGH", "stripePaymentIntentId": intent_id,
                    "description": f"PaymentIntent {intent_id} is referenced by {len(payment_ids)} payment records ({', '.join(payment_ids)}).",
                    "recommendation": "Only one payment record may represent a PaymentIntent; investigate before any refund.",
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
