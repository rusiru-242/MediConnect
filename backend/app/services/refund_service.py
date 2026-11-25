"""Refund service: deterministic policy evaluation, state transitions, and Stripe execution (Phase 5)."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.database import Database
import stripe

from app.config.settings import settings
from app.models.admin_audit import AdminAuditAction
from app.models.appointment import AppointmentStatus, PaymentStatus as ApptPaymentStatus
from app.models.payment import PaymentStatus
from app.models.refund_request import RefundPolicyResult, RefundRequestDocument, RefundStatus, utc_now
from app.services.admin_audit_service import AdminAuditService

logger = logging.getLogger(__name__)


def _init_stripe() -> None:
    if settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY


class RefundService:
    """Manages refund policy calculations, human approval, and idempotent Stripe refund executions."""

    @staticmethod
    def calculate_refund_eligibility(
        db: Database,
        appointment_id: str,
        payment_id: Optional[str] = None,
    ) -> RefundPolicyResult:
        """Evaluate deterministic refund policy rules for an appointment and payment."""
        if not ObjectId.is_valid(appointment_id):
            raise HTTPException(status_code=400, detail="Invalid appointment ID.")

        appt = db["appointments"].find_one({"_id": ObjectId(appointment_id)})
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found.")

        # Resolve payment record
        pay_query: Dict[str, Any] = {"appointmentId": appointment_id}
        if payment_id and ObjectId.is_valid(payment_id):
            pay_query = {"$or": [{"_id": ObjectId(payment_id)}, {"appointmentId": appointment_id}]}

        payment = db["payments"].find_one(pay_query)
        if not payment:
            return RefundPolicyResult(
                eligible=False,
                eligibleAmount=0.0,
                ruleApplied="No matching payment record found for this appointment.",
                isDisputed=True,
            )

        pay_amount = float(payment.get("amount", 0.0))

        # Check if already refunded
        existing_refund = db["refund_requests"].find_one({
            "appointmentId": appointment_id,
            "status": {"$in": [RefundStatus.APPROVED.value, RefundStatus.SUCCEEDED.value, RefundStatus.PROCESSING.value]},
        })
        if existing_refund or payment.get("status") == PaymentStatus.REFUNDED.value:
            return RefundPolicyResult(
                eligible=False,
                eligibleAmount=0.0,
                ruleApplied="Payment has already been refunded or is currently processing.",
                alreadyRefunded=True,
            )

        # Check appointment status
        appt_status = appt.get("status")
        if appt_status == AppointmentStatus.COMPLETED.value:
            return RefundPolicyResult(
                eligible=False,
                eligibleAmount=0.0,
                ruleApplied="Appointment has already been completed by the clinician. Dispute review required.",
                isDisputed=True,
            )

        # Calculate time until appointment
        appt_date_str = appt.get("appointmentDate")
        appt_time_str = appt.get("startTime", "09:00")
        try:
            appt_dt = datetime.fromisoformat(f"{appt_date_str}T{appt_time_str}:00+05:30")
            now = utc_now().astimezone(appt_dt.tzinfo)
            hours_until = (appt_dt - now).total_seconds() / 3600.0
        except Exception:
            hours_until = 48.0

        cancelled_by_doctor = appt.get("cancelledBy") == "DOCTOR"

        if cancelled_by_doctor:
            return RefundPolicyResult(
                eligible=True,
                eligibleAmount=pay_amount,
                penaltyAmount=0.0,
                ruleApplied="Appointment was cancelled by the doctor; 100% full refund guaranteed.",
            )

        if hours_until >= 24.0:
            return RefundPolicyResult(
                eligible=True,
                eligibleAmount=pay_amount,
                penaltyAmount=0.0,
                ruleApplied="Cancelled with more than 24 hours notice; 100% full refund eligible.",
            )
        elif hours_until > 0:
            # Late cancellation: 80% refund (20% platform/clinic administrative fee)
            penalty = round(pay_amount * 0.20, 2)
            eligible = round(pay_amount - penalty, 2)
            return RefundPolicyResult(
                eligible=True,
                eligibleAmount=eligible,
                penaltyAmount=penalty,
                ruleApplied="Late cancellation within 24 hours of slot; 80% partial refund eligible with 20% fee deduction.",
            )
        else:
            return RefundPolicyResult(
                eligible=False,
                eligibleAmount=0.0,
                ruleApplied="Appointment scheduled time has already elapsed.",
                isDisputed=True,
            )

    @classmethod
    def create_refund_request(
        cls,
        db: Database,
        patient_user_id: str,
        appointment_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Submit a new refund request for an appointment with policy calculation."""
        if not ObjectId.is_valid(appointment_id):
            raise HTTPException(status_code=400, detail="Invalid appointment ID.")

        appt = db["appointments"].find_one({"_id": ObjectId(appointment_id)})
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found.")

        # Check ownership
        if str(appt.get("patientUserId")) != str(patient_user_id):
            raise HTTPException(status_code=403, detail="You do not have access to this appointment.")

        payment = db["payments"].find_one({"appointmentId": appointment_id, "status": PaymentStatus.SUCCEEDED.value})
        if not payment:
            raise HTTPException(status_code=400, detail="No successful payment found for this appointment to refund.")

        # A refund belongs to a cancelled booking (the policy rules are cancellation rules), or to a completed
        # visit under dispute review. A patient cannot keep a confirmed appointment and also be refunded.
        if appt.get("status") not in {AppointmentStatus.CANCELLED.value, AppointmentStatus.COMPLETED.value}:
            raise HTTPException(status_code=409, detail="Cancel the appointment before requesting a refund.")
        open_request = db["refund_requests"].find_one({
            "appointmentId": appointment_id,
            "status": {"$in": [RefundStatus.REQUESTED.value, RefundStatus.UNDER_REVIEW.value,
                               RefundStatus.APPROVED.value, RefundStatus.PROCESSING.value]},
        }, {"refundId": 1})
        if open_request:
            raise HTTPException(status_code=400, detail="A refund request for this appointment is already open.")

        # Calculate policy eligibility
        eligibility = cls.calculate_refund_eligibility(db, appointment_id, str(payment["_id"]))
        if eligibility.alreadyRefunded:
            raise HTTPException(status_code=400, detail="This appointment has already been refunded.")

        patient_user = db["users"].find_one({"_id": ObjectId(patient_user_id)}) or {}
        refund_id = f"REF-{uuid4().hex[:10].upper()}"
        idempotency_key = f"ref_{refund_id}_{int(utc_now().timestamp())}"

        # AI summary narrative
        risk_flags = []
        if eligibility.isDisputed:
            risk_flags.append("Requires dispute review")
        if eligibility.penaltyAmount > 0:
            risk_flags.append("Late cancellation penalty applied")

        ai_summary = {
            "summary": f"Refund requested for appointment on {appt.get('appointmentDate')}. Reason: {reason}. {eligibility.ruleApplied}",
            "recommendation": "Approve refund" if eligibility.eligible else "Manual administrative review required",
            "riskFlags": risk_flags,
        }

        doc = {
            "refundId": refund_id,
            "paymentId": str(payment["_id"]),
            "appointmentId": appointment_id,
            "patientUserId": str(patient_user_id),
            "patientName": patient_user.get("fullName", "Patient"),
            "amount": float(payment.get("amount", 0.0)),
            "currency": payment.get("currency", "LKR"),
            "reason": reason,
            "status": RefundStatus.REQUESTED.value,
            "policyEligibility": eligibility.model_dump(),
            "aiSummary": ai_summary,
            "stripeRefundId": None,
            "idempotencyKey": idempotency_key,
            "adminReviewerId": None,
            "reviewNotes": None,
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
        }

        db["refund_requests"].insert_one(doc)
        return doc

    @staticmethod
    def list_refund_requests(
        db: Database,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List refund requests for admin review with filtering."""
        query: Dict[str, Any] = {}
        if status_filter and status_filter != "ALL":
            query["status"] = status_filter.lower()

        coll = db["refund_requests"]
        total = coll.count_documents(query)
        skip = max(0, (page - 1) * page_size)
        cursor = coll.find(query).sort("createdAt", -1).skip(skip).limit(page_size)

        items = []
        for r in cursor:
            items.append({
                "id": str(r["_id"]),
                "refundId": r.get("refundId", ""),
                "paymentId": r.get("paymentId", ""),
                "appointmentId": r.get("appointmentId", ""),
                "patientUserId": r.get("patientUserId", ""),
                "patientName": r.get("patientName", "Patient"),
                "amount": float(r.get("amount", 0.0)),
                "currency": r.get("currency", "LKR"),
                "reason": r.get("reason", ""),
                "status": r.get("status", RefundStatus.REQUESTED.value),
                "policyEligibility": r.get("policyEligibility"),
                "aiSummary": r.get("aiSummary"),
                "stripeRefundId": r.get("stripeRefundId"),
                "idempotencyKey": r.get("idempotencyKey", ""),
                "adminReviewerId": r.get("adminReviewerId"),
                "reviewNotes": r.get("reviewNotes"),
                "failureReason": r.get("failureReason"),
                "createdAt": r.get("createdAt", utc_now()),
                "updatedAt": r.get("updatedAt", utc_now()),
                "completedAt": r.get("completedAt"),
            })

        return {"items": items, "total": total, "page": page, "pageSize": page_size}

    @classmethod
    def get_refund_request(cls, db: Database, refund_id: str) -> Dict[str, Any]:
        """Get refund request detail by refundId or ObjectId."""
        query = {"refundId": refund_id} if refund_id.startswith("REF-") else {"_id": ObjectId(refund_id)}
        r = db["refund_requests"].find_one(query)
        if not r:
            raise HTTPException(status_code=404, detail="Refund request not found.")
        return {
            "id": str(r["_id"]),
            "refundId": r.get("refundId", ""),
            "paymentId": r.get("paymentId", ""),
            "appointmentId": r.get("appointmentId", ""),
            "patientUserId": r.get("patientUserId", ""),
            "patientName": r.get("patientName", "Patient"),
            "amount": float(r.get("amount", 0.0)),
            "currency": r.get("currency", "LKR"),
            "reason": r.get("reason", ""),
            "status": r.get("status", RefundStatus.REQUESTED.value),
            "policyEligibility": r.get("policyEligibility"),
            "aiSummary": r.get("aiSummary"),
            "stripeRefundId": r.get("stripeRefundId"),
            "idempotencyKey": r.get("idempotencyKey", ""),
            "adminReviewerId": r.get("adminReviewerId"),
            "reviewNotes": r.get("reviewNotes"),
            "failureReason": r.get("failureReason"),
            "createdAt": r.get("createdAt", utc_now()),
            "updatedAt": r.get("updatedAt", utc_now()),
            "completedAt": r.get("completedAt"),
        }

    @classmethod
    def approve_refund(
        cls,
        db: Database,
        admin_user_id: str,
        refund_id: str,
        approved_amount: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Admin approves and executes a refund through Stripe with idempotency protection."""
        _init_stripe()
        query = {"refundId": refund_id} if refund_id.startswith("REF-") else {"_id": ObjectId(refund_id)}
        r = db["refund_requests"].find_one(query)
        if not r:
            raise HTTPException(status_code=404, detail="Refund request not found.")

        current_status = r.get("status")
        if current_status in [RefundStatus.SUCCEEDED.value, RefundStatus.APPROVED.value]:
            raise HTTPException(status_code=400, detail="Refund has already been approved or processed.")
        if current_status == RefundStatus.REJECTED.value:
            raise HTTPException(status_code=409, detail="A rejected refund request cannot be approved.")

        payment = db["payments"].find_one({"_id": ObjectId(r["paymentId"])}) if ObjectId.is_valid(r["paymentId"]) else None
        payment_intent_id = (payment.get("stripePaymentIntentId") or payment.get("paymentIntentId")) if payment else None
        if not payment or not payment_intent_id:
            raise HTTPException(status_code=409, detail="The captured payment for this refund could not be verified.")
        if not settings.STRIPE_SECRET_KEY:
            # Never record a refund that did not happen.
            raise HTTPException(status_code=503, detail="The payment gateway is unavailable. No refund was issued.")

        # Amount: policy amount by default; an admin may set a different amount, but never more than what was
        # captured minus what was already refunded.
        captured = float(payment.get("amount", 0.0))
        already = float(payment.get("refundedAmount") or 0.0)
        remaining = round(captured - already, 2)
        policy = r.get("policyEligibility") or {}
        policy_amount = float(policy.get("eligibleAmount") or 0.0)
        amount_to_refund = round(float(approved_amount), 2) if approved_amount is not None else policy_amount
        if amount_to_refund <= 0:
            raise HTTPException(status_code=400, detail="Refund amount must be greater than 0.")
        if amount_to_refund > remaining:
            raise HTTPException(status_code=400, detail="The refund cannot exceed the captured amount still refundable.")

        # Atomic claim: only one approval can move this request into PROCESSING (no duplicate Stripe refunds).
        # A PROCESSING claim can be retaken only when it is stale (a request that crashed mid-way); a live
        # concurrent approval is rejected. Stripe's idempotency key makes the retaken call return the same refund.
        stale_before = utc_now() - timedelta(minutes=2)
        claimed = db["refund_requests"].update_one(
            {"_id": r["_id"], "$or": [
                {"status": {"$in": [RefundStatus.REQUESTED.value, RefundStatus.UNDER_REVIEW.value,
                                    RefundStatus.FAILED.value]}},
                {"status": RefundStatus.PROCESSING.value, "updatedAt": {"$lt": stale_before}},
            ]},
            {"$set": {"status": RefundStatus.PROCESSING.value, "adminReviewerId": str(admin_user_id),
                      "reviewNotes": notes, "approvedAmount": amount_to_refund, "updatedAt": utc_now()}},
        )
        if not claimed.matched_count:
            raise HTTPException(status_code=409, detail="This refund request is already being processed or changed.")

        amount_minor = int(round(amount_to_refund * 100))
        try:
            stripe_resp = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=amount_minor,
                idempotency_key=r.get("idempotencyKey", f"ref_{r['refundId']}"),
                reason="requested_by_customer",
            )
        except stripe.error.StripeError as exc:
            logger.error("Stripe refund error for %s (%s).", r["refundId"], type(exc).__name__)
            db["refund_requests"].update_one(
                {"_id": r["_id"]},
                {"$set": {"status": RefundStatus.FAILED.value, "failureReason": type(exc).__name__,
                          "updatedAt": utc_now()}},
            )
            AdminAuditService.log_action(
                db=db, actor_id=admin_user_id, actor_role="ADMIN", action_type=AdminAuditAction.REFUND_EXECUTION,
                target_id=r["refundId"], target_type="refund_request", status="FAILED", reason=type(exc).__name__,
            )
            raise HTTPException(status_code=502, detail="Stripe refund processing failed. The request can be retried.")

        stripe_refund_id = getattr(stripe_resp, "id", None)
        stripe_status = getattr(stripe_resp, "status", None)
        new_status = {"succeeded": RefundStatus.SUCCEEDED.value, "failed": RefundStatus.FAILED.value,
                      "canceled": RefundStatus.FAILED.value}.get(stripe_status, RefundStatus.PROCESSING.value)
        now = utc_now()
        db["refund_requests"].update_one(
            {"_id": r["_id"]},
            {"$set": {"status": new_status, "stripeRefundId": stripe_refund_id, "stripeRefundStatus": stripe_status,
                      "refundedAmount": amount_to_refund, "updatedAt": now,
                      **({"completedAt": now} if new_status == RefundStatus.SUCCEEDED.value else {})}},
        )
        if new_status == RefundStatus.SUCCEEDED.value:
            # Exactly once per refund request: the refund id guards the increment.
            updated_payment = db["payments"].find_one_and_update(
                {"_id": payment["_id"], "refundRequestIds": {"$ne": r["refundId"]}},
                {"$inc": {"refundedAmount": amount_to_refund}, "$push": {"refundRequestIds": r["refundId"]},
                 "$set": {"updatedAt": now}},
                return_document=ReturnDocument.AFTER,
            ) or db["payments"].find_one({"_id": payment["_id"]})
            refunded_total = round(float(updated_payment.get("refundedAmount") or 0.0), 2)
            full = refunded_total >= captured
            if full:
                db["payments"].update_one({"_id": payment["_id"]}, {"$set": {"status": PaymentStatus.REFUNDED.value}})
            if full and ObjectId.is_valid(r["appointmentId"]):
                db["appointments"].update_one(
                    {"_id": ObjectId(r["appointmentId"])},
                    {"$set": {"paymentStatus": ApptPaymentStatus.REFUNDED.value, "updatedAt": now}},
                )
            try:
                from app.services.appointment_events import record_appointment_event
                record_appointment_event(db, r["appointmentId"], "REFUND_SUCCEEDED", actor_role="ADMIN",
                                         actor_id=str(admin_user_id),
                                         details={"refundId": r["refundId"], "amount": amount_to_refund, "full": full},
                                         idempotency_key=f"refund_succeeded_{r['refundId']}")
            except Exception:
                pass

        # Audit log
        AdminAuditService.log_action(
            db=db,
            actor_id=admin_user_id,
            actor_role="ADMIN",
            action_type=AdminAuditAction.REFUND_APPROVAL,
            target_id=r["refundId"],
            target_type="refund_request",
            previous_state=current_status,
            new_state=new_status,
            reason=notes or "Admin approved refund",
            metadata={"amount": amount_to_refund, "stripeRefundId": stripe_refund_id, "stripeStatus": stripe_status},
        )

        message = {
            RefundStatus.SUCCEEDED.value: f"Refund of LKR {amount_to_refund:,.2f} succeeded in Stripe.",
            RefundStatus.PROCESSING.value: f"Refund of LKR {amount_to_refund:,.2f} was submitted and is pending in Stripe.",
        }.get(new_status, "Stripe reported the refund as failed.")
        return {
            "message": message,
            "refundId": r["refundId"],
            "stripeRefundId": stripe_refund_id,
            "status": new_status,
            "amount": amount_to_refund,
        }

    @classmethod
    def reject_refund(
        cls,
        db: Database,
        admin_user_id: str,
        refund_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Admin rejects a refund request with an explanatory reason."""
        query = {"refundId": refund_id} if refund_id.startswith("REF-") else {"_id": ObjectId(refund_id)}
        r = db["refund_requests"].find_one(query)
        if not r:
            raise HTTPException(status_code=404, detail="Refund request not found.")

        current_status = r.get("status")
        if current_status in [RefundStatus.SUCCEEDED.value, RefundStatus.APPROVED.value, RefundStatus.PROCESSING.value]:
            raise HTTPException(status_code=400, detail="Cannot reject a refund that is processing or settled.")

        now = utc_now()
        db["refund_requests"].update_one(
            {"_id": r["_id"]},
            {
                "$set": {
                    "status": RefundStatus.REJECTED.value,
                    "adminReviewerId": str(admin_user_id),
                    "reviewNotes": reason,
                    "updatedAt": now,
                }
            }
        )

        # Audit log
        AdminAuditService.log_action(
            db=db,
            actor_id=admin_user_id,
            actor_role="ADMIN",
            action_type=AdminAuditAction.REFUND_REJECTION,
            target_id=r["refundId"],
            target_type="refund_request",
            previous_state=current_status,
            new_state=RefundStatus.REJECTED.value,
            reason=reason,
        )

        return {
            "message": "Refund request rejected.",
            "refundId": r["refundId"],
            "status": RefundStatus.REJECTED.value,
        }
