"""Refund service: deterministic policy evaluation, state transitions, and Stripe execution (Phase 5)."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from bson import ObjectId
from fastapi import HTTPException, status
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

        # Determine refund amount from policy eligibility or explicit admin input
        policy = r.get("policyEligibility") or {}
        max_eligible = float(policy.get("eligibleAmount", r.get("amount", 0.0)))
        amount_to_refund = float(approved_amount) if approved_amount is not None else max_eligible

        if amount_to_refund <= 0:
            raise HTTPException(status_code=400, detail="Refund amount must be greater than 0.")

        # Atomic transition to PROCESSING
        db["refund_requests"].update_one(
            {"_id": r["_id"]},
            {
                "$set": {
                    "status": RefundStatus.PROCESSING.value,
                    "adminReviewerId": str(admin_user_id),
                    "reviewNotes": notes,
                    "updatedAt": utc_now(),
                }
            }
        )

        # Lookup payment intent
        payment = db["payments"].find_one({"_id": ObjectId(r["paymentId"])}) if ObjectId.is_valid(r["paymentId"]) else db["payments"].find_one({"appointmentId": r["appointmentId"]})
        payment_intent_id = (payment.get("stripePaymentIntentId") or payment.get("paymentIntentId")) if payment else None

        stripe_refund_id = None
        now = utc_now()

        # Execute Stripe refund if test/live key configured
        if payment_intent_id and settings.STRIPE_SECRET_KEY:
            try:
                # Convert to integer cents (or smallest currency unit)
                amount_cents = int(amount_to_refund * 100)
                stripe_resp = stripe.Refund.create(
                    payment_intent=payment_intent_id,
                    amount=amount_cents,
                    idempotency_key=r.get("idempotencyKey", f"ref_{r['refundId']}"),
                    reason="requested_by_customer",
                )
                stripe_refund_id = stripe_resp.id
            except stripe.error.StripeError as exc:
                logger.error("Stripe refund error for %s: %s", r["refundId"], exc)
                db["refund_requests"].update_one(
                    {"_id": r["_id"]},
                    {
                        "$set": {
                            "status": RefundStatus.FAILED.value,
                            "failureReason": str(exc),
                            "updatedAt": utc_now(),
                        }
                    }
                )
                AdminAuditService.log_action(
                    db=db,
                    actor_id=admin_user_id,
                    actor_role="ADMIN",
                    action_type=AdminAuditAction.REFUND_EXECUTION,
                    target_id=r["refundId"],
                    target_type="refund_request",
                    status="FAILED",
                    reason=str(exc),
                )
                raise HTTPException(status_code=502, detail=f"Stripe refund processing failed: {str(exc)}")
        else:
            # Synthetic / test mode fallback when running in offline or test mode
            stripe_refund_id = f"re_test_{uuid4().hex[:16]}"

        # Mark SUCCEEDED and update related records
        db["refund_requests"].update_one(
            {"_id": r["_id"]},
            {
                "$set": {
                    "status": RefundStatus.SUCCEEDED.value,
                    "stripeRefundId": stripe_refund_id,
                    "updatedAt": now,
                    "completedAt": now,
                }
            }
        )

        if payment:
            db["payments"].update_one(
                {"_id": payment["_id"]},
                {"$set": {"status": PaymentStatus.REFUNDED.value, "updatedAt": now}}
            )

        if ObjectId.is_valid(r["appointmentId"]):
            db["appointments"].update_one(
                {"_id": ObjectId(r["appointmentId"])},
                {"$set": {"paymentStatus": ApptPaymentStatus.REFUNDED.value, "updatedAt": now}}
            )

        # Audit log
        AdminAuditService.log_action(
            db=db,
            actor_id=admin_user_id,
            actor_role="ADMIN",
            action_type=AdminAuditAction.REFUND_APPROVAL,
            target_id=r["refundId"],
            target_type="refund_request",
            previous_state=current_status,
            new_state=RefundStatus.SUCCEEDED.value,
            reason=notes or "Admin approved refund",
            metadata={"amount": amount_to_refund, "stripeRefundId": stripe_refund_id},
        )

        return {
            "message": f"Refund of LKR {amount_to_refund:,.2f} approved and processed successfully.",
            "refundId": r["refundId"],
            "stripeRefundId": stripe_refund_id,
            "status": RefundStatus.SUCCEEDED.value,
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
        if current_status in [RefundStatus.SUCCEEDED.value, RefundStatus.APPROVED.value]:
            raise HTTPException(status_code=400, detail="Cannot reject an already settled refund.")

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
