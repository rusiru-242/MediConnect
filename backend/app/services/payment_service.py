"""Payment service: Stripe PaymentIntent creation, webhook verification, and status checking."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database
import stripe

from app.config.settings import settings
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
                    {"_id": appt_doc["_id"]},
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
        consultation_fee = float(doctor_profile.get("consultationFee", 2500.0))
        currency = (settings.STRIPE_CURRENCY or "lkr").lower()
        # Stripe expects smallest currency unit (e.g. cents / satang / paise)
        # For LKR, 1 LKR = 100 cents
        amount_in_cents = int(round(consultation_fee * 100))

        payment_col = get_payment_collection(db)

        # 6. Idempotency: Check if an active PENDING payment already exists for this appointment
        existing_payment = payment_col.find_one({
            "appointmentId": str(appt_doc["_id"]),
            "status": PaymentStatus.PENDING.value,
        })

        if existing_payment and existing_payment.get("stripePaymentIntentId"):
            intent_id = existing_payment["stripePaymentIntentId"]
            try:
                intent = stripe.PaymentIntent.retrieve(intent_id)
                if intent.status == "succeeded":
                    # Payment was already completed in Stripe
                    payment_col.update_one(
                        {"_id": existing_payment["_id"]},
                        {"$set": {"status": PaymentStatus.SUCCEEDED.value, "paidAt": now, "updatedAt": now}},
                    )
                    db["appointments"].update_one(
                        {"_id": appt_doc["_id"]},
                        {"$set": {"status": AppointmentStatus.CONFIRMED.value, "paymentStatus": AppointmentPaymentStatus.PAID.value, "updatedAt": now}},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This appointment has already been paid for and confirmed.",
                    )
                if intent.status in ["requires_payment_method", "requires_confirmation", "requires_action"]:
                    return CreatePaymentIntentResponse(
                        paymentIntentClientSecret=intent.client_secret,
                        paymentId=str(existing_payment["_id"]),
                        amount=amount_in_cents,
                        currency=currency,
                        publishableKey=settings.STRIPE_PUBLISHABLE_KEY,
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Could not retrieve existing PaymentIntent {intent_id}: {e}")

        # 7. Create new Stripe PaymentIntent with idempotency key
        idempotency_key = f"mediconnect_appt_{appt_doc['_id']}_{int(now.timestamp())}"
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
            logger.error(f"Stripe error creating PaymentIntent: {e}")
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

        # Update existing or insert new
        res = payment_col.insert_one(payment_doc.to_mongo_dict())
        payment_id = str(res.inserted_id)

        # Update appointment payment status to PENDING
        db["appointments"].update_one(
            {"_id": appt_doc["_id"]},
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

        # Handle payment_intent.succeeded
        if event_type == "payment_intent.succeeded":
            intent_id = data_object["id"]
            payment = payment_col.find_one({"stripePaymentIntentId": intent_id})
            if not payment:
                logger.warning(f"PaymentIntent {intent_id} not found in MediConnect DB.")
                return {"status": "ignored", "reason": "Payment record not found"}

            # Idempotency check: if already SUCCEEDED, return early
            if payment.get("status") == PaymentStatus.SUCCEEDED.value:
                return {"status": "already_processed"}

            # Mark payment as SUCCEEDED atomically (prevents concurrent race conditions)
            update_res = payment_col.update_one(
                {
                    "_id": payment["_id"],
                    "status": {"$ne": PaymentStatus.SUCCEEDED.value},
                },
                {
                    "$set": {
                        "status": PaymentStatus.SUCCEEDED.value,
                        "paidAt": now,
                        "updatedAt": now,
                    }
                },
            )
            if update_res.modified_count == 0:
                return {"status": "already_processed"}

            # Confirm appointment and mark paymentStatus = PAID
            appt_id_str = payment["appointmentId"]
            if ObjectId.is_valid(appt_id_str):
                db["appointments"].update_one(
                    {"_id": ObjectId(appt_id_str)},
                    {
                        "$set": {
                            "status": AppointmentStatus.CONFIRMED.value,
                            "paymentStatus": AppointmentPaymentStatus.PAID.value,
                            "updatedAt": now,
                        }
                    },
                )

            logger.info(f"Payment succeeded for appointment {appt_id_str}, intent {intent_id}.")
            return {"status": "success", "appointmentId": appt_id_str}

        # Handle payment_intent.payment_failed
        elif event_type == "payment_intent.payment_failed":
            intent_id = data_object["id"]
            payment = payment_col.find_one({"stripePaymentIntentId": intent_id})
            if not payment:
                return {"status": "ignored", "reason": "Payment record not found"}

            error_msg = data_object.get("last_payment_error", {}).get("message", "Payment failed")
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
                    {"_id": ObjectId(appt_id_str)},
                    {
                        "$set": {
                            "paymentStatus": AppointmentPaymentStatus.FAILED.value,
                            "updatedAt": now,
                        }
                    },
                )

            logger.info(f"Payment failed for appointment {appt_id_str}, intent {intent_id}: {error_msg}")
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
                if intent.status == "succeeded":
                    payment_col.update_one(
                        {"_id": payment["_id"]},
                        {"$set": {"status": PaymentStatus.SUCCEEDED.value, "paidAt": now, "updatedAt": now}},
                    )
                    payment["status"] = PaymentStatus.SUCCEEDED.value
                    payment["paidAt"] = now

                    appt_id_str = payment["appointmentId"]
                    if ObjectId.is_valid(appt_id_str):
                        db["appointments"].update_one(
                            {"_id": ObjectId(appt_id_str)},
                            {"$set": {"status": AppointmentStatus.CONFIRMED.value, "paymentStatus": AppointmentPaymentStatus.PAID.value, "updatedAt": now}},
                        )
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
                logger.warning(f"Fallback Stripe status sync failed for {payment_id}: {e}")

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
