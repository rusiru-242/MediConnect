"""Payment service: Stripe PaymentIntent creation, webhook verification, and status checking."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
import stripe

from app.agents.doctor_ranking import coerce_fee
from app.config.settings import settings
from app.services.ai_booking_proposal import settle_ai_payment
from app.models.appointment import (
    AppointmentStatus,
    PaymentStatus as AppointmentPaymentStatus,
    utc_now,
)
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.payment import PaymentDocument, PaymentStatus, get_payment_collection
from app.models.user import AccountStatus, UserRole
from app.schemas.payment import (
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    PaymentHistoryItem,
    PaymentHistoryResponse,
    PaymentStatusResponse,
)
from app.schemas.user import UserResponseSchema

logger = logging.getLogger(__name__)


def _init_stripe() -> None:
    if settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY


def _intent_value(intent, key):
    return intent.get(key) if isinstance(intent, dict) else getattr(intent, key, None)


def _livemode_mismatch(obj) -> bool:
    """A live-mode Stripe object must never settle a booking on a test-key backend (and vice versa)."""
    livemode = _intent_value(obj, "livemode")
    if livemode is None:
        return False
    return bool(livemode) != (settings.STRIPE_SECRET_KEY or "").startswith("sk_live_")


def settle_legacy_payment(db: Database, payment: Dict[str, Any], intent: Any, now: datetime) -> str:
    """Confirm a non-AI booking from a succeeded PaymentIntent, exactly once (Phase 02).

    Confirms only when the intent id, received amount, currency and patient all match the server-owned
    payment record and the reservation is still valid. Anything else is kept as a durable
    REVIEW_REQUIRED record for an authorized refund decision; money is never silently applied.
    Returns "success", "already_processed" or "reconciliation_required".
    """
    if payment.get("status") == PaymentStatus.SUCCEEDED.value and payment.get("reconciliationState") == "CONFIRMED":
        return "already_processed"
    expected_minor = int(round(float(payment.get("amount") or 0) * 100))
    received = _intent_value(intent, "amount_received")
    if received is None:
        received = _intent_value(intent, "amount")
    valid = (
        _intent_value(intent, "id") == payment.get("stripePaymentIntentId")
        and received == expected_minor and expected_minor > 0
        and (_intent_value(intent, "currency") or "").lower() == (payment.get("currency") or "").lower()
        and not _livemode_mismatch(intent)
    )
    appointment_id = payment.get("appointmentId")
    confirmed = False
    if valid and ObjectId.is_valid(str(appointment_id)):
        updated = db["appointments"].find_one_and_update(
            {"_id": ObjectId(appointment_id), "patientUserId": payment["patientUserId"],
             "paymentStatus": {"$ne": AppointmentPaymentStatus.PAID.value},
             "$or": [{"status": {"$in": [AppointmentStatus.HOLD.value, AppointmentStatus.PENDING.value]},
                      "holdExpiresAt": {"$gt": now}},
                     {"status": AppointmentStatus.CONFIRMED.value}]},
            {"$set": {"status": AppointmentStatus.CONFIRMED.value, "paymentStatus": AppointmentPaymentStatus.PAID.value,
                      "stripePaymentIntentId": payment["stripePaymentIntentId"], "confirmedAt": now, "updatedAt": now}},
            return_document=ReturnDocument.AFTER,
        )
        current = updated or db["appointments"].find_one({"_id": ObjectId(appointment_id)}) or {}
        confirmed = (current.get("paymentStatus") == AppointmentPaymentStatus.PAID.value
                     and current.get("stripePaymentIntentId") == payment["stripePaymentIntentId"])
    if confirmed:
        result = get_payment_collection(db).update_one(
            {"_id": payment["_id"], "reconciliationState": {"$ne": "CONFIRMED"}},
            {"$set": {"status": PaymentStatus.SUCCEEDED.value, "paidAt": payment.get("paidAt") or now,
                      "updatedAt": now, "reconciliationState": "CONFIRMED"}, "$unset": {"failureReason": ""}},
        )
        if not result.modified_count:
            return "already_processed"
        from app.services.appointment_events import record_appointment_event
        record_appointment_event(db, appointment_id, "PAYMENT_CONFIRMED", actor_role="SYSTEM", to_status="CONFIRMED",
                                 details={"paymentId": str(payment["_id"]), "amountMinor": expected_minor},
                                 idempotency_key=f"payment_confirmed_{payment['_id']}")
        return "success"
    get_payment_collection(db).update_one(
        {"_id": payment["_id"], "reconciliationState": {"$nin": ["CONFIRMED", "REFUND_PENDING", "REFUNDED", "REFUND_FAILED"]}},
        {"$set": {"status": PaymentStatus.SUCCEEDED.value, "paidAt": now, "updatedAt": now,
                  "reconciliationState": "REVIEW_REQUIRED",
                  "reconciliationReason": "booking_unavailable" if valid else "amount_currency_or_mode_mismatch"}},
    )
    return "reconciliation_required"


def settle_succeeded_intent(db: Database, payment: Dict[str, Any], intent: Any, now: datetime) -> str:
    outcome = settle_ai_payment(db, payment, intent, now)
    return outcome if outcome is not None else settle_legacy_payment(db, payment, intent, now)


def _notify_payment_success(db: Database, payment: Dict[str, Any]) -> None:
    try:
        from app.models.notification import NotificationType
        from app.services.notification_service import NotificationService

        amount = coerce_fee(payment.get("amount"))
        NotificationService.create_notification(
            db=db, recipient_user_id=str(payment["patientUserId"]), type=NotificationType.PAYMENT_SUCCESS,
            title="Payment Successful",
            body=(f"Your payment of LKR {amount:,.0f} was successful. Your appointment has been confirmed."
                  if amount is not None else "Your payment was successful. Your appointment has been confirmed."),
            related_appointment_id=str(payment["appointmentId"]), related_payment_id=str(payment["_id"]),
            idempotency_key=f"pay_success_{payment['_id']}",
        )
        NotificationService.create_notification(
            db=db, recipient_user_id=str(payment["doctorUserId"]), type=NotificationType.APPOINTMENT_CONFIRMED,
            title="Appointment Confirmed", body="A patient has completed payment and confirmed their appointment.",
            related_appointment_id=str(payment["appointmentId"]), related_payment_id=str(payment["_id"]),
            idempotency_key=f"doc_confirmed_{payment['_id']}",
        )
    except Exception as notif_err:
        logger.warning("Failed to send payment success notification (%s).", type(notif_err).__name__)


class PaymentService:
    """Business logic for payments, Stripe integration, and webhooks."""

    # -------------------------------------------------------------------------
    # 1. Create PaymentIntent
    # -------------------------------------------------------------------------
    @staticmethod
    async def create_payment_intent(
        db: Database,
        patient_user: UserResponseSchema,
        req: CreatePaymentIntentRequest,
    ) -> CreatePaymentIntentResponse:
        """Create or reuse a Stripe PaymentIntent for an appointment hold.
        
        Security rules:
        - Authenticated user must have PATIENT role.
        - Appointment must belong to the authenticated patient.
        - Appointment must be in PENDING/HOLD status and hold must not be expired.
        - Doctor must be APPROVED and ACTIVE.
        - Payment amount is derived exclusively by the backend from doctor's consultation fee.
        - Idempotent: reuses active intent if already created for this appointment hold.
        """
        _init_stripe()

        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can make payments.",
            )

        # 1. Resolve appointment
        if not ObjectId.is_valid(req.appointmentId):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid appointmentId format.",
            )

        appt_doc = db["appointments"].find_one({"_id": ObjectId(req.appointmentId)})
        if not appt_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )

        # 2. Ownership check
        if str(appt_doc.get("patientUserId")) != str(patient_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this appointment.",
            )

        # 3. Check appointment status and hold validity
        appt_status = appt_doc.get("status")
        if appt_doc.get("paymentStatus") == AppointmentPaymentStatus.PAID.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This appointment has already been paid for and confirmed.",
            )

        if appt_status not in [AppointmentStatus.PENDING.value, AppointmentStatus.HOLD.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot initiate payment for appointment in '{appt_status}' status.",
            )

        now = utc_now()
        hold_expires_at = appt_doc.get("holdExpiresAt")
        if hold_expires_at:
            if hold_expires_at.tzinfo is None:
                hold_expires_at = hold_expires_at.replace(tzinfo=timezone.utc)
            if hold_expires_at <= now:
                # Mark as cancelled
                db["appointments"].update_one(
                    {"_id": appt_doc["_id"], "status": {"$in": ["HOLD", "PENDING"]},
                     "paymentStatus": {"$ne": "PAID"}},
                    {
                        "$set": {
                            "status": AppointmentStatus.CANCELLED.value,
                            "cancellationReason": "Booking hold expired",
                            "cancelledBy": "SYSTEM",
                            "updatedAt": now,
                        }
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This booking session has expired. Please select the time slot again.",
                )

        # 4. Validate doctor status
        doctor_user_id = str(appt_doc["doctorUserId"])
        doctor_profile = db["doctor_profiles"].find_one({
            "$or": [
                {"userId": doctor_user_id},
                {"_id": ObjectId(appt_doc["doctorProfileId"]) if ObjectId.is_valid(str(appt_doc["doctorProfileId"])) else None},
            ]
        })

        if not doctor_profile or doctor_profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor is no longer active or approved.",
            )

        doctor_user = db["users"].find_one({"_id": ObjectId(doctor_user_id)})
        if not doctor_user or doctor_user.get("accountStatus") != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor account is not active.",
            )

        # 5. Determine consultation fee exclusively from backend
        if appt_doc.get("bookingSource") == "ai_agent":
            amount_in_cents = appt_doc["acceptedAmountMinor"]
            consultation_fee = amount_in_cents / 100
            currency = appt_doc["bookingCurrency"]
            if amount_in_cents <= 0:
                raise HTTPException(409, "This booking does not require payment.")
        else:
            # The fee recorded on the appointment when the slot was reserved (server-derived at that time);
            # a later profile change must not alter what this booking costs.
            consultation_fee = coerce_fee(appt_doc.get("consultationFee"))
            if consultation_fee is None:
                # Never charge an invented default amount (BUG-028).
                raise HTTPException(409, "This doctor has not listed a consultation fee, so payment cannot be started.")
            currency = (settings.STRIPE_CURRENCY or "lkr").lower()
            amount_in_cents = int(round(consultation_fee * 100))

        payment_col = get_payment_collection(db)

        # Reuse the last intent, including an intent that can accept a new card after a decline.
        existing_payment = payment_col.find_one({
            "appointmentId": str(appt_doc["_id"]),
            "status": {"$in": [PaymentStatus.PENDING.value, PaymentStatus.FAILED.value]},
        }, sort=[("createdAt", -1)])

        attempt = "first"
        if existing_payment and existing_payment.get("stripePaymentIntentId"):
            intent_id = existing_payment["stripePaymentIntentId"]
            try:
                intent = stripe.PaymentIntent.retrieve(intent_id)
                if intent.status == "succeeded":
                    # Duplicate submission after a payment that already succeeded: settle once, never charge again.
                    outcome = settle_succeeded_intent(db, existing_payment, intent, now)
                    if outcome == "success" and appt_doc.get("bookingSource") != "ai_agent":
                        _notify_payment_success(db, existing_payment)
                    if appt_doc.get("bookingSource") == "ai_agent":
                        raise HTTPException(409, "Payment received. Check booking status." if outcome == "success"
                                            else "Payment received and awaiting reconciliation.")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=("This appointment has already been paid for and confirmed."
                                if outcome in {"success", "already_processed"}
                                else "Payment received and awaiting reconciliation."),
                    )
                if intent.status in ["requires_payment_method", "requires_confirmation", "requires_action", "processing"]:
                    if existing_payment["status"] == PaymentStatus.FAILED.value:
                        payment_col.update_one(
                            {"_id": existing_payment["_id"], "status": PaymentStatus.FAILED.value},
                            {"$set": {"status": PaymentStatus.PENDING.value, "updatedAt": now},
                             "$unset": {"failureReason": ""}},
                        )
                    return CreatePaymentIntentResponse(
                        paymentIntentClientSecret=intent.client_secret,
                        paymentId=str(existing_payment["_id"]),
                        amount=amount_in_cents,
                        currency=currency,
                        publishableKey=settings.STRIPE_PUBLISHABLE_KEY,
                    )
                if intent.status != "canceled":
                    raise HTTPException(409, "The current payment is still being verified.")
                attempt = str(existing_payment["_id"])
            except HTTPException:
                raise
            except stripe.error.StripeError as exc:
                raise HTTPException(502, "Could not verify the existing payment. Please retry.") from exc

        # A retry after a timeout must reuse the same Stripe intent.
        idempotency_key = f"mediconnect_appt_{appt_doc['_id']}_{attempt}"
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency=currency,
                metadata={
                    "appointmentId": str(appt_doc["_id"]),
                    "patientUserId": str(patient_user.id),
                    "doctorUserId": doctor_user_id,
                },
                description=f"MediConnect Consultation - Dr. {doctor_user.get('fullName', 'Doctor')}",
                automatic_payment_methods={"enabled": True},
                idempotency_key=idempotency_key,
            )
        except stripe.error.StripeError as e:
            logger.error("Stripe PaymentIntent creation failed (%s).", type(e).__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment gateway communication failed. Please try again.",
            )

        # 8. Record Payment document in database
        payment_doc = PaymentDocument(
            appointmentId=str(appt_doc["_id"]),
            patientUserId=str(patient_user.id),
            doctorUserId=doctor_user_id,
            stripePaymentIntentId=intent.id,
            amount=consultation_fee,
            currency=currency,
            status=PaymentStatus.PENDING,
            createdAt=now,
            updatedAt=now,
        )

        try:
            res = payment_col.insert_one(payment_doc.to_mongo_dict())
            payment_id = str(res.inserted_id)
        except DuplicateKeyError:
            existing = payment_col.find_one({"stripePaymentIntentId": intent.id})
            if not existing or existing["appointmentId"] != str(appt_doc["_id"]):
                raise
            payment_id = str(existing["_id"])

        # Update appointment payment status to PENDING
        db["appointments"].update_one(
            {"_id": appt_doc["_id"], "paymentStatus": {"$ne": AppointmentPaymentStatus.PAID.value}},
            {
                "$set": {
                    "paymentStatus": AppointmentPaymentStatus.PENDING.value,
                    "updatedAt": now,
                }
            },
        )

        return CreatePaymentIntentResponse(
            paymentIntentClientSecret=intent.client_secret,
            paymentId=payment_id,
            amount=amount_in_cents,
            currency=currency,
            publishableKey=settings.STRIPE_PUBLISHABLE_KEY,
        )

    # -------------------------------------------------------------------------
    # 2. Webhook Handler
    # -------------------------------------------------------------------------
    @staticmethod
    async def handle_webhook(
        db: Database,
        payload: bytes,
        sig_header: Optional[str],
    ) -> Dict[str, Any]:
        """Verify Stripe webhook signature and process event idempotently."""
        _init_stripe()

        if not sig_header:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Stripe-Signature header.",
            )

        if not settings.STRIPE_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="STRIPE_WEBHOOK_SECRET is not configured on server.",
            )

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook payload.",
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Stripe webhook signature.",
            )

        event_type = event["type"]
        data_object = event["data"]["object"]
        now = utc_now()

        payment_col = get_payment_collection(db)

        if _livemode_mismatch(event):
            logger.warning("Ignored a Stripe event whose livemode does not match the configured key.")
            return {"status": "ignored", "reason": "livemode_mismatch"}

        # Handle payment_intent.succeeded
        if event_type == "payment_intent.succeeded":
            intent_id = data_object["id"]
            payment = payment_col.find_one({"stripePaymentIntentId": intent_id})
            if not payment:
                logger.warning("A PaymentIntent from a webhook is not linked to a MediConnect payment.")
                return {"status": "ignored", "reason": "Payment record not found"}

            outcome = settle_ai_payment(db, payment, data_object, now)
            if outcome is not None:
                return {"status": outcome, "appointmentId": payment["appointmentId"]}

            outcome = settle_legacy_payment(db, payment, data_object, now)
            if outcome == "success":
                logger.info("Payment confirmed for appointment %s.", payment["appointmentId"])
                _notify_payment_success(db, payment)
            return {"status": outcome, "appointmentId": payment["appointmentId"]}

        # Handle payment_intent.payment_failed
        elif event_type == "payment_intent.payment_failed":
            intent_id = data_object["id"]
            payment = payment_col.find_one({"stripePaymentIntentId": intent_id})
            if not payment:
                return {"status": "ignored", "reason": "Payment record not found"}

            error_msg = (data_object.get("last_payment_error") or {}).get("message", "Payment failed")
            payment_col.update_one(
                {
                    "_id": payment["_id"],
                    "status": {"$ne": PaymentStatus.SUCCEEDED.value},
                },
                {
                    "$set": {
                        "status": PaymentStatus.FAILED.value,
                        "failureReason": error_msg,
                        "updatedAt": now,
                    }
                },
            )

            appt_id_str = payment["appointmentId"]
            if ObjectId.is_valid(appt_id_str):
                db["appointments"].update_one(
                    {"_id": ObjectId(appt_id_str), "paymentStatus": {"$ne": "PAID"},
                     "status": {"$in": ["HOLD", "PENDING"]}},
                    {
                        "$set": {
                            "paymentStatus": AppointmentPaymentStatus.FAILED.value,
                            "updatedAt": now,
                        }
                    },
                )

            logger.info("Payment failure received for appointment %s", appt_id_str)

            # Send failure notification safely
            try:
                from app.models.notification import NotificationType
                from app.services.notification_service import NotificationService

                NotificationService.create_notification(
                    db=db,
                    recipient_user_id=str(payment["patientUserId"]),
                    type=NotificationType.PAYMENT_FAILED,
                    title="Payment Failed",
                    body="Your payment transaction could not be completed. Please try again to confirm your appointment.",
                    related_appointment_id=appt_id_str,
                    related_payment_id=str(payment["_id"]),
                    idempotency_key=f"pay_failed_{payment['_id']}",
                )
            except Exception as notif_err:
                logger.warning("Failed to send payment failure notification: %s", notif_err)

            return {"status": "failed_recorded", "appointmentId": appt_id_str}

        return {"status": "ignored", "event_type": event_type}

    # -------------------------------------------------------------------------
    # 3. Query Payment Status
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_payment_status(
        db: Database,
        payment_id: str,
        patient_user: UserResponseSchema,
    ) -> PaymentStatusResponse:
        """Query authoritative payment and appointment status.
        
        Includes Stripe sync fallback if webhook hasn't arrived yet.
        """
        _init_stripe()

        if not ObjectId.is_valid(payment_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid paymentId format.",
            )

        payment_col = get_payment_collection(db)
        payment = payment_col.find_one({"_id": ObjectId(payment_id)})
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found.",
            )

        # Ownership check
        if str(payment.get("patientUserId")) != str(patient_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this payment.",
            )

        # Fallback sync: if status is PENDING, verify with Stripe directly
        if payment.get("status") == PaymentStatus.PENDING.value and payment.get("stripePaymentIntentId"):
            try:
                intent = stripe.PaymentIntent.retrieve(payment["stripePaymentIntentId"])
                now = utc_now()
                outcome = settle_succeeded_intent(db, payment, intent, now) if intent.status == "succeeded" else None
                if outcome:
                    if outcome == "success" and not db["appointments"].find_one(
                            {"_id": ObjectId(payment["appointmentId"]), "bookingSource": "ai_agent"}, {"_id": 1}):
                        _notify_payment_success(db, payment)
                    payment = payment_col.find_one({"_id": payment["_id"]}) or payment
                elif intent.status in ["canceled", "requires_payment_method"]:
                    if intent.last_payment_error:
                        payment_col.update_one(
                            {"_id": payment["_id"]},
                            {
                                "$set": {
                                    "status": PaymentStatus.FAILED.value,
                                    "failureReason": intent.last_payment_error.message,
                                    "updatedAt": now,
                                }
                            },
                        )
                        payment["status"] = PaymentStatus.FAILED.value
            except Exception as e:
                logger.warning("Fallback Stripe status sync failed (%s)", type(e).__name__)

        # Resolve appointment status
        appt_status = "UNKNOWN"
        appt_id_str = payment.get("appointmentId")
        if ObjectId.is_valid(appt_id_str):
            appt = db["appointments"].find_one({"_id": ObjectId(appt_id_str)})
            if appt:
                appt_status = appt.get("status", "UNKNOWN")

        return PaymentStatusResponse(
            paymentId=str(payment["_id"]),
            appointmentId=str(payment.get("appointmentId", "")),
            paymentStatus=payment.get("status", PaymentStatus.PENDING.value),
            appointmentStatus=appt_status,
            reconciliationState=payment.get("reconciliationState"),
            amount=payment.get("amount", 0.0),
            currency=payment.get("currency", "lkr"),
            paidAt=payment.get("paidAt"),
        )

    # -------------------------------------------------------------------------
    # 4. List Patient Payments (Payment History)
    # -------------------------------------------------------------------------
    @staticmethod
    async def list_patient_payments(
        db: Database,
        patient_user: UserResponseSchema,
    ) -> PaymentHistoryResponse:
        """Return safe payment history for the authenticated patient."""
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can view payment history.",
            )

        payment_col = get_payment_collection(db)
        payments = list(
            payment_col.find({"patientUserId": str(patient_user.id)}).sort([("createdAt", -1)])
        )

        items: List[PaymentHistoryItem] = []
        for p in payments:
            doc_user_id = p.get("doctorUserId")
            doctor_name = "Doctor"
            if doc_user_id and ObjectId.is_valid(str(doc_user_id)):
                doc_user = db["users"].find_one({"_id": ObjectId(str(doc_user_id))})
                if doc_user:
                    doctor_name = doc_user.get("fullName", "Doctor")

            items.append(
                PaymentHistoryItem(
                    paymentId=str(p["_id"]),
                    appointmentId=p.get("appointmentId", ""),
                    doctorName=doctor_name,
                    amount=float(p.get("amount", 0.0)),
                    currency=p.get("currency", "lkr"),
                    status=p.get("status", PaymentStatus.PENDING.value),
                    paidAt=p.get("paidAt"),
                    createdAt=p.get("createdAt", utc_now()),
                )
            )

        return PaymentHistoryResponse(items=items, total=len(items))
