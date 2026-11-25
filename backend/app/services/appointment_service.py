import logging
from datetime import datetime as _dt, timedelta, timezone
import math
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

from app.agents.doctor_ranking import coerce_fee
from app.models.appointment import (
    AppointmentDocument,
    AppointmentStatus,
    PaymentStatus,
    get_appointment_collection,
    utc_now,
)
from app.models.doctor_availability import get_doctor_availability_collection
from app.models.doctor_profile import DoctorVerificationStatus, get_doctor_profile_collection
from app.models.user import AccountStatus, UserRole
from app.schemas.appointment import (
    AppointmentListResponse,
    AppointmentResponse,
    CancelAppointmentRequest,
    CreateAppointmentRequest,
    CreateAppointmentResponse,
    RescheduleAppointmentRequest,
    UpdateAppointmentStatusRequest,
)
from app.schemas.user import UserResponseSchema

# Sri Lanka Standard Time (Asia/Colombo = UTC+05:30)
SL_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def stop_open_payment_intents(db: Database, appointment_id: str, now) -> str:
    """Make every open Stripe PaymentIntent of an unpaid reservation unpayable before the slot is released.

    Returns "stopped" when no intent can be paid any more, or "paid" when an intent had already succeeded (it is
    then settled through the exactly-once path and the caller must treat the booking as paid). Raises 409 while a
    payment is still processing, 503 without a configured gateway and 502 when Stripe cannot be reached.
    Shared by the patient's Release Reservation (BUG-063) and doctor cancellation (P03-N04).
    """
    import stripe
    from app.config.settings import settings
    from app.models.payment import PaymentStatus as RecordStatus
    from app.services.payment_service import settle_succeeded_intent

    open_payments = list(db["payments"].find({
        "appointmentId": appointment_id, "status": {"$in": [RecordStatus.PENDING.value, RecordStatus.FAILED.value]},
    }))
    for payment in open_payments:
        intent_id = payment.get("stripePaymentIntentId")
        if not intent_id:
            continue
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(503, "The payment gateway is unavailable, so the reservation cannot be released safely yet.")
        try:
            intent = stripe.PaymentIntent.retrieve(intent_id, api_key=settings.STRIPE_SECRET_KEY)
            if intent.status not in {"succeeded", "processing", "canceled"}:
                intent = stripe.PaymentIntent.cancel(intent_id, api_key=settings.STRIPE_SECRET_KEY,
                                                     cancellation_reason="abandoned")
        except stripe.error.StripeError:
            try:  # the cancel can fail because the payment completed in the meantime
                intent = stripe.PaymentIntent.retrieve(intent_id, api_key=settings.STRIPE_SECRET_KEY)
            except stripe.error.StripeError as exc:
                raise HTTPException(502, "Could not verify the payment. Please retry.") from exc
        if intent.status == "succeeded":
            settle_succeeded_intent(db, payment, intent, now)
            return "paid"
        if intent.status != "canceled":
            raise HTTPException(409, "A payment is still being processed. Wait a moment and refresh.")
        db["payments"].update_one(
            {"_id": payment["_id"], "status": {"$ne": RecordStatus.SUCCEEDED.value}},
            {"$set": {"status": RecordStatus.CANCELLED.value, "updatedAt": now, "cancelledAt": now}},
        )
    return "stopped"


def doctor_cancel_appointment_record(db: Database, appt: Dict[str, Any], doctor_user_id: str, reason: Optional[str],
                                     *, source: str = "doctor") -> Dict[str, Any]:
    """Cancel one of the doctor's appointments safely (doctor cancellation and leave conflicts, P03-N03/N04/N05).

    - An unpaid reservation first has its Stripe PaymentIntent stopped, so the patient cannot pay for a slot that
      no longer exists; if the payment had already succeeded, the booking is handled as paid.
    - The status change is conditional on the state that was read, so a concurrent change is reported (409).
    - A paid booking gets a refund request under the existing policy (doctor cancellation: 100%); money moves only
      after an administrator approves it, as for patient cancellations.
    Returns {"appointment": updated document, "refundRequest": request or None}.
    """
    from app.services.appointment_events import record_appointment_event

    appointment_id = str(appt["_id"])
    current_status = appt["status"]
    if "CANCELLED" not in _ALLOWED_TRANSITIONS.get(current_status, set()):
        raise HTTPException(status_code=400, detail=f"Cannot cancel an appointment with status: {current_status}.")
    now = utc_now()
    unpaid = current_status in {"HOLD", "PENDING"} and appt.get("paymentStatus") != PaymentStatus.PAID.value
    if unpaid and stop_open_payment_intents(db, appointment_id, now) == "paid":
        appt = _get_appointment_or_404(db, appointment_id)
        current_status = appt["status"]
        unpaid = False
    changes = {"status": AppointmentStatus.CANCELLED.value, "cancelledBy": "DOCTOR",
               "cancellationReason": reason, "updatedAt": now}
    condition = {"_id": appt["_id"], "doctorUserId": str(doctor_user_id), "status": current_status}
    if unpaid:
        condition["paymentStatus"] = {"$ne": PaymentStatus.PAID.value}
        changes["paymentStatus"] = PaymentStatus.UNPAID.value  # nothing was taken
    if not get_appointment_collection(db).update_one(condition, {"$set": changes}).matched_count:
        raise HTTPException(409, "This appointment changed. Refresh it before cancelling.")
    refund_request = None
    if appt.get("paymentStatus") == PaymentStatus.PAID.value:
        try:
            from app.services.refund_service import RefundService
            refund_request = RefundService.create_refund_request(
                db, str(appt["patientUserId"]), appointment_id, reason or "Doctor cancelled the appointment",
                source=source if source in {"doctor", "leave"} else "doctor", requested_by=str(doctor_user_id))
        except HTTPException as refund_exc:
            logger.warning("Refund request was not opened automatically (%s).", refund_exc.status_code)
    record_appointment_event(db, appointment_id, "APPOINTMENT_CANCELLED", actor_role="DOCTOR", actor_id=str(doctor_user_id),
                             from_status=current_status, to_status="CANCELLED",
                             details={"source": source, "refundRequestId": (refund_request or {}).get("refundId")},
                             idempotency_key=f"cancelled_{appointment_id}")
    return {"appointment": _get_appointment_or_404(db, appointment_id), "refundRequest": refund_request}

# ---------------------------------------------------------------------------
# VALID STATE TRANSITIONS
# ---------------------------------------------------------------------------
_ALLOWED_TRANSITIONS: Dict[str, set] = {
    AppointmentStatus.HOLD.value: {
        AppointmentStatus.CONFIRMED.value,
        AppointmentStatus.CANCELLED.value,
    },
    AppointmentStatus.PENDING.value: {
        AppointmentStatus.CONFIRMED.value,
        AppointmentStatus.CANCELLED.value,
    },
    AppointmentStatus.CONFIRMED.value: {
        AppointmentStatus.COMPLETED.value,
        AppointmentStatus.CANCELLED.value,
    },
    AppointmentStatus.COMPLETED.value: set(),   # terminal
    AppointmentStatus.CANCELLED.value: set(),   # terminal
}


def _build_appointment_response(
    doc: Dict[str, Any],
    doctor_id: Optional[str] = None,
    patient_name: Optional[str] = None,
    patient_email: Optional[str] = None,
    doctor_name: Optional[str] = None,
    specialty: Optional[str] = None,
    hospital_or_clinic: Optional[str] = None,
    payment_details: Optional[Dict[str, Any]] = None,
) -> AppointmentResponse:
    """Build an AppointmentResponse from a raw MongoDB document with optional enriched fields."""
    return AppointmentResponse(
        id=str(doc["_id"]),
        patientUserId=str(doc.get("patientUserId", "")),
        doctorUserId=str(doc.get("doctorUserId", "")),
        doctorProfileId=str(doc.get("doctorProfileId", "")),
        availabilityId=str(doc.get("availabilityId", "")),
        appointmentDate=doc.get("appointmentDate") or doc.get("date", ""),
        startTime=doc.get("startTime", ""),
        endTime=doc.get("endTime", ""),
        status=doc.get("status", "PENDING"),
        paymentStatus=doc.get("paymentStatus", "UNPAID"),
        consultationFee=coerce_fee(doc.get("consultationFee")),
        holdExpiresAt=doc.get("holdExpiresAt"),
        patientNote=doc.get("patientNote"),
        cancelledBy=doc.get("cancelledBy"),
        cancellationReason=doc.get("cancellationReason"),
        createdAt=doc.get("createdAt") or _dt.now(timezone.utc),
        updatedAt=doc.get("updatedAt") or _dt.now(timezone.utc),
        doctorId=doctor_id or doc.get("doctorId"),
        patientName=patient_name,
        patientEmail=patient_email,
        doctorName=doctor_name,
        specialty=specialty,
        hospitalOrClinic=hospital_or_clinic,
        appointmentVersion=int(doc.get("appointmentVersion", 1)),
        bookingReference=str(doc["_id"]),
        visitType="IN_PERSON",
        **(payment_details or {}),
    )


def _payment_details(db: Database, doc: Dict[str, Any]) -> Dict[str, Any]:
    """Authoritative payment facts for one appointment (BUG-058/BUG-059).

    The fee is the amount stored on the appointment when it was booked, never the doctor's current
    profile fee. "amountPaid" is reported only from a verified payment record; nothing is inferred.
    """
    appointment_id = str(doc["_id"])
    currency = (doc.get("bookingCurrency") or "").lower() or None
    fee_at_booking = (doc["acceptedAmountMinor"] / 100) if isinstance(doc.get("acceptedAmountMinor"), int)         else coerce_fee(doc.get("consultationFee"))
    payment = db["payments"].find_one(
        {"appointmentId": appointment_id, "status": {"$in": ["SUCCEEDED", "REFUNDED"]}},
        sort=[("createdAt", -1)],
    )
    details: Dict[str, Any] = {"consultationFeeAtBooking": fee_at_booking, "currency": currency}
    if payment:
        details.update(
            amountPaid=coerce_fee(payment.get("amount")), paidAt=payment.get("paidAt"),
            paymentId=str(payment["_id"]), currency=(payment.get("currency") or currency or "").lower() or None,
            paymentReconciliationState=payment.get("reconciliationState"),
        )
        if payment.get("refundedAmount") is not None:
            details["refundedAmount"] = coerce_fee(payment.get("refundedAmount"))
    refund = db["refund_requests"].find_one({"appointmentId": appointment_id}, sort=[("createdAt", -1)])
    if refund:
        details["refundStatus"] = refund.get("status")
        details["refundId"] = refund.get("refundId")
    return details


class AppointmentService:
    """Business logic for appointment booking, listing, and status management."""

    # -------------------------------------------------------------------------
    # PATIENT: Create appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def create_appointment(
        db: Database,
        patient_user: UserResponseSchema,
        req: CreateAppointmentRequest,
        *, accepted_proposal=None, proposal_slot=None, sms_consent=False,
    ) -> CreateAppointmentResponse:
        """Book a time slot for a patient.

        Security rules:
        - Patient must have ACTIVE account with verified email.
        - Doctor must be APPROVED and ACTIVE.
        - Slot must exist in the availability window and not be in the past.
        - Backend derives and validates endTime; never trusts client-supplied endTime.
        - Database-level unique index prevents race-condition double-bookings.
        """
        # 1. Role check
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can book appointments.",
            )

        if patient_user.accountStatus != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only active accounts can book appointments.",
            )

        if accepted_proposal:
            existing = db["appointments"].find_one({
                "_id": ObjectId(accepted_proposal["proposalId"]), "patientUserId": str(patient_user.id),
            })
            if existing:
                return CreateAppointmentResponse(appointment=_build_appointment_response(existing))

        # 2. Resolve doctor via doctorId string (from discovery)
        clean_doctor_id = req.doctorId.strip()
        profile_query: Dict[str, Any] = {}
        if ObjectId.is_valid(clean_doctor_id):
            profile_query = {
                "$or": [
                    {"doctorId": clean_doctor_id},
                    {"_id": ObjectId(clean_doctor_id)},
                ]
            }
        else:
            profile_query = {"doctorId": clean_doctor_id}

        doctor_profile = db["doctor_profiles"].find_one(profile_query)
        if not doctor_profile or doctor_profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found or is not currently accepting appointments.",
            )

        doctor_user_id_raw = doctor_profile.get("userId")
        doctor_user_obj_query = (
            {"$or": [{"_id": ObjectId(doctor_user_id_raw)}, {"_id": doctor_user_id_raw}]}
            if ObjectId.is_valid(str(doctor_user_id_raw))
            else {"_id": doctor_user_id_raw}
        )
        doctor_user_doc = db["users"].find_one(doctor_user_obj_query)
        if (
            not doctor_user_doc
            or doctor_user_doc.get("role") != UserRole.DOCTOR.value
            or doctor_user_doc.get("accountStatus") != AccountStatus.ACTIVE.value
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found or is not currently accepting appointments.",
            )

        doctor_user_id = str(doctor_user_doc["_id"])
        doctor_profile_id = str(doctor_profile["_id"])
        target_date = req.appointmentDate or req.date

        booking_fields = {}
        if accepted_proposal:
            from app.services.ai_booking_proposal import minor_units
            from app.config.settings import settings
            from app.services.doctor_service import DoctorService

            price = minor_units(doctor_profile.get("consultationFee"))
            if (price != minor_units(accepted_proposal["totalAmount"])
                or (doctor_profile.get("hospitalOrClinic") or "") != (accepted_proposal.get("hospitalOrClinic") or "")
                or (doctor_profile.get("specialty") or "Specialty not listed") != accepted_proposal["specialty"]
                or doctor_profile.get("city") != accepted_proposal.get("city")
                or (doctor_user_doc.get("fullName") or "Name unavailable") != accepted_proposal["doctorName"]
                or (settings.STRIPE_CURRENCY or "lkr").lower() != accepted_proposal["currency"]):
                raise HTTPException(409, "The booking price or location changed. Request a new proposal.")
            day = await DoctorService.get_doctor_patient_slots(db, clean_doctor_id, target_date)
            if not any(slot.startTime == req.startTime and slot.endTime == proposal_slot["endTime"]
                       and slot.availabilityId == req.availabilityId for slot in day.slots):
                raise HTTPException(409, "The accepted slot has changed. Request a new proposal.")
            booking_fields = {
                "_id": ObjectId(accepted_proposal["proposalId"]), "bookingSource": "ai_agent",
                "smsConsent": sms_consent, "smsDestinationHash": accepted_proposal.get("smsDestinationHash"),
                "acceptedAmountMinor": price, "bookingCurrency": accepted_proposal["currency"],
                "hospitalOrClinic": doctor_profile.get("hospitalOrClinic"),
                "bookingDoctorName": accepted_proposal["doctorName"], "bookingSpecialty": accepted_proposal["specialty"],
            }

        req_start_h, req_start_m = _parse_hhmm(req.startTime)
        req_start_total = req_start_h * 60 + req_start_m

        # Phase 54: Check doctor active leaves covering this date
        active_leaves = list(db["doctor_leaves"].find({
            "doctorUserId": doctor_user_id,
            "status": "ACTIVE",
            "startDate": {"$lte": target_date},
            "endDate": {"$gte": target_date},
        }))
        for l in active_leaves:
            l_start = l.get("startTime")
            l_end = l.get("endTime")
            if not l_start or not l_end:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor is on leave on this date.")
            lh_s, lm_s = _parse_hhmm(l_start)
            if req.startTime < l_end and (req_start_total + 15) > (lh_s * 60 + lm_s):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor is on leave during this time slot.")

        # Phase 54: Check doctor blocked times covering this date
        blocked_records = list(db["doctor_blocked_times"].find({
            "doctorUserId": doctor_user_id,
            "date": target_date,
        }))
        for b in blocked_records:
            b_start = b.get("startTime")
            b_end = b.get("endTime")
            if b_start and b_end:
                bh_s, bm_s = _parse_hhmm(b_start)
                if req.startTime < b_end and (req_start_total + 15) > (bh_s * 60 + bm_s):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This time slot is blocked by the doctor.")

        # 3. Resolve and validate the availability window
        avail_doc = None
        if req.availabilityId and req.availabilityId.strip():
            avail_id_raw = req.availabilityId.strip()
            if ObjectId.is_valid(avail_id_raw):
                avail_doc = db["doctor_availabilities"].find_one({"_id": ObjectId(avail_id_raw)})
        if not avail_doc:
            # Lookup active availability window for this doctor matching date
            avail_doc = db["doctor_availabilities"].find_one({
                "doctorUserId": doctor_user_id,
                "date": target_date,
                "isActive": True,
                "startTime": {"$lte": req.startTime},
                "endTime": {"$gt": req.startTime},
            })

        # Phase 54: If no specific date availability record, check recurring weekly schedule
        if not avail_doc:
            weekday_name = _dt.strptime(target_date, "%Y-%m-%d").strftime("%A").lower()
            ws_doc = db["doctor_weekly_schedules"].find_one({"doctorUserId": doctor_user_id})
            if ws_doc:
                for w in ws_doc.get("weekdays", []):
                    if w.get("day") == weekday_name and w.get("isEnabled"):
                        for sess in w.get("sessions", []):
                            if sess.get("startTime") <= req.startTime and sess.get("endTime") > req.startTime:
                                avail_doc = {
                                    "_id": str(ws_doc["_id"]),
                                    "doctorUserId": doctor_user_id,
                                    "doctorProfileId": doctor_profile_id,
                                    "date": target_date,
                                    "startTime": sess.get("startTime"),
                                    "endTime": sess.get("endTime"),
                                    "slotDurationMinutes": int(ws_doc.get("slotDurationMinutes", 30)),
                                    "isActive": True,
                                }
                                break

        if not avail_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability window not found for this schedule.",
            )

        # Security: availability must belong to the resolved doctor
        if str(avail_doc.get("doctorUserId")) != doctor_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Availability does not belong to this doctor.",
            )

        if not avail_doc.get("isActive", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This availability window is no longer active.",
            )

        if avail_doc.get("date") != target_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment date does not match the availability window date.",
            )

        # 4. Backend derives valid slots for the window and validates requested startTime
        slot_duration = int(avail_doc.get("slotDurationMinutes", 30))
        window_start = avail_doc["startTime"]  # "HH:MM"
        window_end = avail_doc["endTime"]      # "HH:MM"

        req_start_h, req_start_m = _parse_hhmm(req.startTime)
        req_start_total = req_start_h * 60 + req_start_m

        # Compute derived endTime
        derived_end_total = req_start_total + slot_duration
        derived_end_str = f"{derived_end_total // 60:02d}:{derived_end_total % 60:02d}"

        # Validate slot falls exactly within window boundaries and aligns with slotDuration
        win_start_h, win_start_m = _parse_hhmm(window_start)
        win_end_h, win_end_m = _parse_hhmm(window_end)
        win_start_total = win_start_h * 60 + win_start_m
        win_end_total = win_end_h * 60 + win_end_m

        slot_valid = (
            req_start_total >= win_start_total
            and derived_end_total <= win_end_total
            and (req_start_total - win_start_total) % slot_duration == 0
        )
        if not slot_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Selected time slot ({req.startTime} - {derived_end_str}) is not a valid slot in this availability window.",
            )

        # 5. Ensure slot is not in the past (Sri Lanka local time)
        sl_now = _dt.now(SL_TIMEZONE)
        try:
            slot_dt_naive = _dt.strptime(f"{target_date} {req.startTime}", "%Y-%m-%d %H:%M")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date or time format.")

        slot_dt = slot_dt_naive.replace(tzinfo=SL_TIMEZONE)
        if slot_dt <= sl_now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book an appointment in the past.",
            )

        # 6. Check if slot is already occupied by any active appointment
        now = utc_now()
        active_bookings = list(db["appointments"].find({
            "doctorUserId": doctor_user_id,
            "appointmentDate": target_date,
            "startTime": req.startTime,
            "status": {"$in": [
                AppointmentStatus.HOLD.value,
                AppointmentStatus.PENDING.value,
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.COMPLETED.value,
            ]},
        }))

        for b in active_bookings:
            b_status = b.get("status")
            b_hold = b.get("holdExpiresAt")
            b_paid = b.get("paymentStatus") == PaymentStatus.PAID.value
            # Check if this booking is an expired hold
            if b_status in [AppointmentStatus.HOLD.value, AppointmentStatus.PENDING.value] and not b_paid:
                if b_hold:
                    if b_hold.tzinfo is None:
                        b_hold = b_hold.replace(tzinfo=timezone.utc)
                    if b_hold <= now:
                        # Cancel expired hold to release slot and remove it from active unique index
                        db["appointments"].update_one(
                            {"_id": b["_id"], "status": {"$in": ["HOLD", "PENDING"]}, "paymentStatus": {"$ne": "PAID"}},
                            {
                                "$set": {
                                    "status": AppointmentStatus.CANCELLED.value,
                                    "cancellationReason": "Booking hold expired",
                                    "cancelledBy": "SYSTEM",
                                    "updatedAt": now,
                                }
                            }
                        )
                        continue
            # Slot is actively occupied
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This time slot is no longer available.",
            )

        # 7. Insert appointment with temporary 10-minute hold - database unique index guards concurrent race conditions
        avail_id_str = str(avail_doc["_id"])
        # Charge only the doctor's listed fee; never a default (BUG-028).
        consultation_fee = coerce_fee(doctor_profile.get("consultationFee"))
        if consultation_fee is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This doctor has not listed a consultation fee yet, so the appointment cannot be booked.",
            )
        hold_expires_at = now + timedelta(minutes=10)

        appt_doc = AppointmentDocument(
            patientUserId=str(patient_user.id),
            doctorUserId=doctor_user_id,
            doctorProfileId=doctor_profile_id,
            availabilityId=avail_id_str,
            appointmentDate=target_date,
            startTime=req.startTime,
            endTime=derived_end_str,
            status=AppointmentStatus.PENDING,
            paymentStatus=PaymentStatus.UNPAID.value,
            consultationFee=consultation_fee,
            holdExpiresAt=hold_expires_at,
            patientNote=req.patientNote,
            createdAt=now,
            updatedAt=now,
        )

        appointment_data = {**appt_doc.to_mongo_dict(), **booking_fields}
        if booking_fields and booking_fields["acceptedAmountMinor"] == 0:
            from app.services.ai_booking_proposal import notification_entries
            appointment_data.update(status="CONFIRMED", paymentStatus="NOT_REQUIRED", confirmedAt=now, holdExpiresAt=None,
                                    confirmationOutbox=notification_entries(now))
        try:
            result = get_appointment_collection(db).insert_one(appointment_data)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This time slot is no longer available.",
            )

        if booking_fields:
            return CreateAppointmentResponse(appointment=_build_appointment_response(appointment_data))
        # Notify doctor of new booking created
        try:
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService

            NotificationService.create_notification(
                db=db,
                recipient_user_id=doctor_user_id,
                type=NotificationType.BOOKING_CREATED,
                title="New Booking Request",
                body=f"New appointment booked by {patient_user.fullName or 'a patient'} for {target_date} at {req.startTime}.",
                related_appointment_id=str(result.inserted_id),
                idempotency_key=f"booking_created_{result.inserted_id}",
            )
        except Exception as notif_err:
            logger.warning("Failed to send booking created notification: %s", notif_err)

        appt_response = _build_appointment_response(
            {**appt_doc.to_mongo_dict(), "_id": result.inserted_id},
            doctor_id=str(doctor_profile.get("doctorId", "")),
            doctor_name=doctor_user_doc.get("fullName"),
            specialty=doctor_profile.get("specialty"),
            hospital_or_clinic=doctor_profile.get("hospitalOrClinic"),
            patient_name=patient_user.fullName,
            patient_email=patient_user.email,
        )

        return CreateAppointmentResponse(
            message="Appointment request created successfully.",
            appointment=appt_response,
        )

    # -------------------------------------------------------------------------
    # PATIENT: List own appointments
    # -------------------------------------------------------------------------
    @staticmethod
    async def list_patient_appointments(
        db: Database,
        patient_user: UserResponseSchema,
        page: int = 1,
        limit: int = 20,
        status_filter: Optional[str] = None,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> AppointmentListResponse:
        """Return paginated appointment history for the authenticated patient."""
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can access this.")

        page = max(1, page)
        limit = max(1, min(50, limit))
        skip = (page - 1) * limit

        query: Dict[str, Any] = {"patientUserId": str(patient_user.id)}
        if status_filter and status_filter.strip():
            clean = status_filter.strip().upper()
            if clean not in AppointmentStatus.__members__:
                raise HTTPException(status_code=400, detail=f"Invalid status filter: {status_filter}.")
            query["status"] = clean

        bounds = {op: value for op, value in (("$gte", from_date), ("$lte", to_date)) if value}
        if bounds:
            query["appointmentDate"] = bounds
        collection = get_appointment_collection(db)
        total = collection.count_documents(query)
        cursor = (
            collection.find(query)
            .sort([("appointmentDate", DESCENDING), ("startTime", DESCENDING)])
            .skip(skip)
            .limit(limit)
        )

        items = []
        for doc in cursor:
            dr_user = db["users"].find_one({"_id": ObjectId(doc["doctorUserId"])}) if ObjectId.is_valid(doc.get("doctorUserId", "")) else None
            dr_profile = db["doctor_profiles"].find_one({"_id": ObjectId(doc["doctorProfileId"])}) if ObjectId.is_valid(doc.get("doctorProfileId", "")) else None
            items.append(_build_appointment_response(
                doc,
                doctor_id=dr_profile.get("doctorId") if dr_profile else None,
                doctor_name=dr_user.get("fullName") if dr_user else None,
                specialty=dr_profile.get("specialty") if dr_profile else None,
                hospital_or_clinic=doc.get("hospitalOrClinic") or (dr_profile.get("hospitalOrClinic") if dr_profile else None),
                patient_name=patient_user.fullName,
                patient_email=patient_user.email,
                payment_details=_payment_details(db, doc),
            ))

        return AppointmentListResponse(
            items=items,
            page=page,
            limit=limit,
            total=total,
            totalPages=math.ceil(total / limit) if total > 0 else 0,
        )

    # -------------------------------------------------------------------------
    # PATIENT: Cancel own appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def cancel_patient_appointment(
        db: Database,
        patient_user: UserResponseSchema,
        appointment_id: str,
        reason: Optional[Any] = None,
        *, only_hold: bool = False,
    ) -> AppointmentResponse:
        """Allow patient to cancel their own appointment (only PENDING or CONFIRMED)."""
        if hasattr(reason, "reason"):
            reason = reason.reason

        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can cancel appointments.")

        appt = _get_appointment_or_404(db, appointment_id)

        # Ownership check
        if str(appt["patientUserId"]) != str(patient_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to cancel this appointment.",
            )

        current_status = appt["status"]
        if only_hold and current_status not in {"HOLD", "PENDING"}:
            raise HTTPException(409, "The hold was already settled. Check My Appointments.")
        if "CANCELLED" not in _ALLOWED_TRANSITIONS.get(current_status, set()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel an appointment with status: {current_status}.",
            )
        if current_status in {"HOLD", "PENDING"} and appt.get("paymentStatus") != PaymentStatus.PAID.value:
            # An unpaid reservation is released through the race-safe path that first stops any open
            # Stripe PaymentIntent, so no payment can be captured for a released slot (BUG-063).
            return await AppointmentService.release_unpaid_hold(db, patient_user, appointment_id, reason)

        now = utc_now()
        # Conditional on the status read above: two concurrent cancellations cannot both apply (P-05o).
        condition = {"_id": ObjectId(appointment_id), "status": current_status}
        if only_hold:
            condition.update(paymentStatus={"$ne": "PAID"})
        mutation = get_appointment_collection(db).update_one(
            condition,
            {
                "$set": {
                    "status": AppointmentStatus.CANCELLED.value,
                    "cancelledBy": "PATIENT",
                    "cancellationReason": reason,
                    "updatedAt": now,
                }
            },
        )

        if not mutation.matched_count:
            raise HTTPException(409, "This appointment changed. Refresh it before cancelling.")

        from app.services.appointment_events import record_appointment_event
        record_appointment_event(db, appointment_id, "APPOINTMENT_CANCELLED", actor_role="PATIENT",
                                 actor_id=str(patient_user.id), from_status=current_status, to_status="CANCELLED",
                                 idempotency_key=f"cancelled_{appointment_id}")
        refund_request = None
        if appt.get("paymentStatus") == PaymentStatus.PAID.value:
            # Paid cancellation: open a refund request under the configured refund policy. Money moves only
            # after an administrator approves it (human approval preserved).
            try:
                from app.services.refund_service import RefundService
                refund_request = RefundService.create_refund_request(
                    db, str(patient_user.id), appointment_id, reason or "Patient cancelled the appointment",
                    source="patient",
                )
            except HTTPException as refund_exc:
                logger.warning("Refund request was not opened automatically (%s).", refund_exc.status_code)

        # Notify patient and doctor of cancellation
        try:
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService

            dr_user_doc = db["users"].find_one({"_id": ObjectId(appt["doctorUserId"])}) if ObjectId.is_valid(str(appt.get("doctorUserId", ""))) else None
            dr_name = (dr_user_doc.get("fullName") if dr_user_doc else None) or "Doctor"
            if not dr_name.startswith("Dr.") and not dr_name.startswith("Dr "):
                dr_name = f"Dr. {dr_name}"

            # In-app notification to patient
            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(appt["patientUserId"]),
                type=NotificationType.APPOINTMENT_CANCELLED,
                title="Appointment Cancelled",
                body=f"Your appointment with {dr_name} on {appt.get('appointmentDate')} at {appt.get('startTime')} has been cancelled.",
                related_appointment_id=str(appt["_id"]),
                idempotency_key=f"patient_cancelled_self_{appt['_id']}",
            )

            # In-app notification to doctor
            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(appt["doctorUserId"]),
                type=NotificationType.APPOINTMENT_CANCELLED,
                title="Appointment Cancelled",
                body=f"Appointment with {patient_user.fullName or 'a patient'} on {appt.get('appointmentDate')} at {appt.get('startTime')} has been cancelled.",
                related_appointment_id=str(appt["_id"]),
                idempotency_key=f"patient_cancelled_{appt['_id']}",
            )
        except Exception as notif_err:
            logger.warning("Failed to send patient cancellation notification: %s", notif_err)

        updated = _get_appointment_or_404(db, appointment_id)
        dr_user = db["users"].find_one({"_id": ObjectId(updated["doctorUserId"])}) if ObjectId.is_valid(updated.get("doctorUserId", "")) else None
        dr_profile = db["doctor_profiles"].find_one({"_id": ObjectId(updated["doctorProfileId"])}) if ObjectId.is_valid(updated.get("doctorProfileId", "")) else None
        return _build_appointment_response(
            updated,
            doctor_id=dr_profile.get("doctorId") if dr_profile else None,
            doctor_name=dr_user.get("fullName") if dr_user else None,
            specialty=dr_profile.get("specialty") if dr_profile else None,
            hospital_or_clinic=dr_profile.get("hospitalOrClinic") if dr_profile else None,
            patient_name=patient_user.fullName,
            patient_email=patient_user.email,
            payment_details=_payment_details(db, updated),
        )

    # -------------------------------------------------------------------------
    # PATIENT: Cancellation preview (refund implications before confirming)
    # -------------------------------------------------------------------------
    @staticmethod
    async def cancellation_preview(
        db: Database, patient_user: UserResponseSchema, appointment_id: str,
    ) -> Dict[str, Any]:
        """What cancelling would mean, computed from the configured refund rules. Changes nothing."""
        appt = _get_appointment_or_404(db, appointment_id)
        if patient_user.role != UserRole.PATIENT.value or str(appt["patientUserId"]) != str(patient_user.id):
            raise HTTPException(status_code=403, detail="You do not have permission to view this appointment.")
        current = appt["status"]
        can_cancel = "CANCELLED" in _ALLOWED_TRANSITIONS.get(current, set())
        paid = appt.get("paymentStatus") == PaymentStatus.PAID.value
        preview: Dict[str, Any] = {
            "appointmentId": appointment_id, "status": current, "canCancel": can_cancel, "isPaid": paid,
            "isUnpaidReservation": current in {"HOLD", "PENDING"} and not paid,
            "refund": None, "requiresAdminApproval": False,
        }
        if can_cancel and paid:
            from app.services.refund_service import RefundService
            payment = db["payments"].find_one({"appointmentId": appointment_id, "status": "SUCCEEDED"}, {"_id": 1})
            eligibility = RefundService.calculate_refund_eligibility(db, appointment_id, str(payment["_id"]) if payment else None)
            preview["refund"] = {
                "eligible": eligibility.eligible, "eligibleAmount": eligibility.eligibleAmount,
                "penaltyAmount": eligibility.penaltyAmount, "ruleApplied": eligibility.ruleApplied,
                "currency": (appt.get("bookingCurrency") or "lkr").lower(),
            }
            preview["requiresAdminApproval"] = True
        return preview

    # -------------------------------------------------------------------------
    # SYSTEM: Release expired unpaid holds (durable, restart-safe sweep)
    # -------------------------------------------------------------------------
    @staticmethod
    def release_expired_holds(db: Database, now=None, *, limit: int = 100) -> int:
        """Cancel unpaid HOLD/PENDING reservations whose server-owned holdExpiresAt has passed.

        Each hold is claimed with a conditional update, so concurrent workers never release the same hold
        twice and a payment that settles first always wins (paymentStatus PAID is excluded).
        """
        from app.services.appointment_events import record_appointment_event

        now = now or utc_now()
        released = 0
        collection = get_appointment_collection(db)
        for _ in range(limit):
            doc = collection.find_one_and_update(
                {"status": {"$in": [AppointmentStatus.HOLD.value, AppointmentStatus.PENDING.value]},
                 "paymentStatus": {"$ne": PaymentStatus.PAID.value}, "holdExpiresAt": {"$lte": now}},
                {"$set": {"status": AppointmentStatus.CANCELLED.value, "cancelledBy": "SYSTEM",
                          "cancellationReason": "Booking hold expired", "paymentStatus": PaymentStatus.UNPAID.value,
                          "updatedAt": now}},
            )
            if not doc:
                break
            released += 1
            record_appointment_event(db, str(doc["_id"]), "HOLD_EXPIRED", actor_role="SYSTEM",
                                     from_status=doc["status"], to_status="CANCELLED",
                                     idempotency_key=f"hold_expired_{doc['_id']}")
        return released

    # -------------------------------------------------------------------------
    # PATIENT: Release an unpaid reservation hold (BUG-063)
    # -------------------------------------------------------------------------
    @staticmethod
    async def release_unpaid_hold(
        db: Database,
        patient_user: UserResponseSchema,
        appointment_id: str,
        reason: Optional[str] = None,
    ) -> AppointmentResponse:
        """Release the patient's own unpaid HOLD/PENDING reservation now instead of waiting for expiry.

        Race safety with payment confirmation:
        1. Every open Stripe PaymentIntent for the hold is cancelled first. A cancelled intent can no
           longer succeed, so no money can be captured for a released slot.
        2. If Stripe reports the intent already succeeded (or is processing), nothing is released: the
           payment is settled through the normal exactly-once path and the patient is told to check status.
        3. The appointment is then cancelled with a conditional update (still HOLD/PENDING, not PAID).
        A paid appointment can never be cancelled through this path.
        """
        from app.services.appointment_events import record_appointment_event

        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(status_code=403, detail="Only patients can release a reservation.")
        appt = _get_appointment_or_404(db, appointment_id)
        if str(appt["patientUserId"]) != str(patient_user.id):
            raise HTTPException(status_code=403, detail="You do not have permission to change this reservation.")
        if appt["status"] == AppointmentStatus.CANCELLED.value:
            return _build_appointment_response(appt, payment_details=_payment_details(db, appt))  # idempotent
        if appt["status"] not in {AppointmentStatus.HOLD.value, AppointmentStatus.PENDING.value} or \
                appt.get("paymentStatus") == PaymentStatus.PAID.value:
            raise HTTPException(409, "This appointment is already paid or confirmed. Use Cancel Appointment instead.")

        now = utc_now()
        open_payments = db["payments"].count_documents({"appointmentId": appointment_id,
                                                         "stripePaymentIntentId": {"$exists": True}})
        if stop_open_payment_intents(db, appointment_id, now) == "paid":
            raise HTTPException(409, "Your payment was already received, so the reservation was not released. "
                                     "Refresh the booking status.")

        released = get_appointment_collection(db).find_one_and_update(
            {"_id": ObjectId(appointment_id), "patientUserId": str(patient_user.id),
             "status": {"$in": [AppointmentStatus.HOLD.value, AppointmentStatus.PENDING.value]},
             "paymentStatus": {"$ne": PaymentStatus.PAID.value}},
            {"$set": {"status": AppointmentStatus.CANCELLED.value, "cancelledBy": "PATIENT",
                      "cancellationReason": reason or "Reservation released by patient before payment",
                      # No money was taken: a released hold is "not paid", not "payment pending".
                      "paymentStatus": PaymentStatus.UNPAID.value,
                      "holdReleasedAt": now, "updatedAt": now}},
        )
        if not released:
            raise HTTPException(409, "The reservation changed. Refresh the booking status.")
        record_appointment_event(db, appointment_id, "HOLD_RELEASED", actor_role="PATIENT", actor_id=str(patient_user.id),
                                 from_status=appt["status"], to_status="CANCELLED",
                                 details={"paymentIntentsChecked": open_payments},
                                 idempotency_key=f"hold_released_{appointment_id}")
        if appt.get("bookingSource") != "ai_agent":
            # The doctor saw a "New Booking Request" for manual holds; tell them it was withdrawn.
            try:
                from app.models.notification import NotificationType
                from app.services.notification_service import NotificationService
                NotificationService.create_notification(
                    db=db, recipient_user_id=str(appt["doctorUserId"]), type=NotificationType.APPOINTMENT_CANCELLED,
                    title="Reservation Released",
                    body=f"An unpaid reservation for {appt.get('appointmentDate')} at {appt.get('startTime')} was released.",
                    related_appointment_id=appointment_id, idempotency_key=f"hold_released_doctor_{appointment_id}",
                )
            except Exception as notif_err:
                logger.warning("Failed to send hold release notification (%s).", type(notif_err).__name__)
        updated = _get_appointment_or_404(db, appointment_id)
        return _build_appointment_response(updated, payment_details=_payment_details(db, updated))

    # -------------------------------------------------------------------------
    # DOCTOR: List assigned appointments
    # -------------------------------------------------------------------------
    @staticmethod
    async def list_doctor_appointments(
        db: Database,
        doctor_user: UserResponseSchema,
        page: int = 1,
        limit: int = 20,
        date_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> AppointmentListResponse:
        """Return paginated appointment list for the authenticated doctor."""
        _assert_doctor_approved_and_active(db, doctor_user)

        page = max(1, page)
        limit = max(1, min(50, limit))
        skip = (page - 1) * limit

        query: Dict[str, Any] = {"doctorUserId": str(doctor_user.id)}

        query["$or"] = [
            {"bookingSource": {"$ne": "ai_agent"}},
            {"confirmedAt": {"$exists": True}},
        ]
        if date_filter and date_filter.strip():
            query["appointmentDate"] = date_filter.strip()

        if status_filter and status_filter.strip():
            clean = status_filter.strip().upper()
            if clean not in AppointmentStatus.__members__:
                raise HTTPException(status_code=400, detail=f"Invalid status filter: {status_filter}.")
            query["status"] = clean

        collection = get_appointment_collection(db)
        total = collection.count_documents(query)
        cursor = (
            collection.find(query)
            .sort([("appointmentDate", ASCENDING), ("startTime", ASCENDING)])
            .skip(skip)
            .limit(limit)
        )

        items = []
        for doc in cursor:
            pt_user = db["users"].find_one({"_id": ObjectId(doc["patientUserId"])}) if ObjectId.is_valid(doc.get("patientUserId", "")) else None
            dr_profile = db["doctor_profiles"].find_one({"_id": ObjectId(doc["doctorProfileId"])}) if ObjectId.is_valid(doc.get("doctorProfileId", "")) else None
            items.append(_build_appointment_response(
                doc,
                doctor_id=dr_profile.get("doctorId") if dr_profile else None,
                patient_name=pt_user.get("fullName") if pt_user else None,
                patient_email=pt_user.get("email") if pt_user else None,
                doctor_name=doctor_user.fullName,
                payment_details=_payment_details(db, doc),
            ))

        return AppointmentListResponse(
            items=items,
            page=page,
            limit=limit,
            total=total,
            totalPages=math.ceil(total / limit) if total > 0 else 0,
        )

    # -------------------------------------------------------------------------
    # DOCTOR: Confirm appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def confirm_doctor_appointment(
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
    ) -> AppointmentResponse:
        """Allow doctor to confirm a PENDING appointment."""
        _assert_doctor_approved_and_active(db, doctor_user)

        appt = _get_appointment_or_404(db, appointment_id)

        # Ownership check
        if str(appt["doctorUserId"]) != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this appointment.",
            )

        if appt.get("bookingSource") == "ai_agent" and not appt.get("confirmedAt"):
            raise HTTPException(409, "The patient must complete booking acceptance and payment.")
        current_status = appt["status"]
        if current_status != AppointmentStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm an appointment with status: {current_status}.",
            )
        if appt.get("paymentStatus") not in {PaymentStatus.PAID.value, PaymentStatus.NOT_REQUIRED.value}:
            # Never confirm before payment verification where payment is required (Phase 02).
            raise HTTPException(409, "This appointment cannot be confirmed until the patient's payment is verified.")

        now = utc_now()
        result = get_appointment_collection(db).update_one(
            {"_id": ObjectId(appointment_id), "status": AppointmentStatus.PENDING.value},
            {"$set": {"status": AppointmentStatus.CONFIRMED.value, "updatedAt": now}},
        )
        if not result.matched_count:
            raise HTTPException(409, "This appointment changed. Refresh it.")

        # Notify patient and doctor of appointment confirmation
        try:
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService

            dr_name = doctor_user.fullName or "Doctor"
            if not dr_name.startswith("Dr.") and not dr_name.startswith("Dr "):
                dr_name = f"Dr. {dr_name}"

            # In-app notification to patient
            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(appt["patientUserId"]),
                type=NotificationType.APPOINTMENT_CONFIRMED,
                title="Appointment Confirmed",
                body=f"Your appointment with {dr_name} is confirmed for {appt.get('appointmentDate')} at {appt.get('startTime')}.",
                related_appointment_id=str(appt["_id"]),
                idempotency_key=f"doctor_confirmed_{appt['_id']}",
            )

            # In-app notification to doctor
            pt_user_doc = db["users"].find_one({"_id": ObjectId(appt["patientUserId"])}) if ObjectId.is_valid(str(appt.get("patientUserId", ""))) else None
            patient_name = (pt_user_doc.get("fullName") if pt_user_doc else None) or "a patient"
            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(appt["doctorUserId"]),
                type=NotificationType.APPOINTMENT_CONFIRMED,
                title="Appointment Confirmed",
                body=f"Appointment with {patient_name} on {appt.get('appointmentDate')} at {appt.get('startTime')} is confirmed.",
                related_appointment_id=str(appt["_id"]),
                idempotency_key=f"doctor_confirmed_self_{appt['_id']}",
            )
        except Exception as notif_err:
            logger.warning("Failed to send doctor confirmation notification: %s", notif_err)

        updated = _get_appointment_or_404(db, appointment_id)
        pt_user = db["users"].find_one({"_id": ObjectId(updated["patientUserId"])}) if ObjectId.is_valid(updated.get("patientUserId", "")) else None
        return _build_appointment_response(
            updated,
            patient_name=pt_user.get("fullName") if pt_user else None,
            patient_email=pt_user.get("email") if pt_user else None,
            doctor_name=doctor_user.fullName,
        )

    # -------------------------------------------------------------------------
    # DOCTOR: Complete appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def complete_doctor_appointment(
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
    ) -> AppointmentResponse:
        """Allow doctor to complete a CONFIRMED appointment at or after scheduled time."""
        _assert_doctor_approved_and_active(db, doctor_user)

        appt = _get_appointment_or_404(db, appointment_id)

        # Ownership check
        if str(appt["doctorUserId"]) != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this appointment.",
            )

        current_status = appt["status"]
        if current_status != AppointmentStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete an appointment with status: {current_status}.",
            )

        # Validation: Consultation time must have been reached or passed
        sl_now = _dt.now(SL_TIMEZONE)
        slot_dt = _dt.strptime(f"{appt['appointmentDate']} {appt['startTime']}", "%Y-%m-%d %H:%M").replace(tzinfo=SL_TIMEZONE)
        if slot_dt > sl_now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot mark an appointment as completed before its scheduled consultation time.",
            )

        now = utc_now()
        moved = get_appointment_collection(db).update_one(
            {"_id": ObjectId(appointment_id), "doctorUserId": str(doctor_user.id), "status": AppointmentStatus.CONFIRMED.value},
            {"$set": {"status": AppointmentStatus.COMPLETED.value, "updatedAt": now}},
        )
        if not moved.matched_count:  # a concurrent cancellation or completion won (P03-N05)
            raise HTTPException(409, "This appointment changed. Refresh it.")
        from app.services.appointment_events import record_appointment_event
        record_appointment_event(db, appointment_id, "APPOINTMENT_COMPLETED", actor_role="DOCTOR", actor_id=str(doctor_user.id),
                                 from_status="CONFIRMED", to_status="COMPLETED", idempotency_key=f"completed_{appointment_id}")

        # Notify patient of appointment completion
        try:
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService

            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(appt["patientUserId"]),
                type=NotificationType.APPOINTMENT_COMPLETED,
                title="Appointment Completed",
                body=f"Your consultation on {appt.get('appointmentDate')} has been marked as completed.",
                related_appointment_id=str(appt["_id"]),
                idempotency_key=f"doctor_completed_{appt['_id']}",
            )
        except Exception as notif_err:
            logger.warning("Failed to send appointment completion notification: %s", notif_err)

        updated = _get_appointment_or_404(db, appointment_id)
        pt_user = db["users"].find_one({"_id": ObjectId(updated["patientUserId"])}) if ObjectId.is_valid(updated.get("patientUserId", "")) else None
        return _build_appointment_response(
            updated,
            patient_name=pt_user.get("fullName") if pt_user else None,
            patient_email=pt_user.get("email") if pt_user else None,
            doctor_name=doctor_user.fullName,
        )

    # -------------------------------------------------------------------------
    # DOCTOR: Cancel appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def cancel_doctor_appointment(
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
        reason: Optional[Any] = None,
    ) -> AppointmentResponse:
        """Allow doctor to cancel an appointment."""
        if hasattr(reason, "reason"):
            reason = reason.reason

        _assert_doctor_approved_and_active(db, doctor_user)

        appt = _get_appointment_or_404(db, appointment_id)

        # Ownership check
        if str(appt["doctorUserId"]) != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this appointment.",
            )

        outcome = doctor_cancel_appointment_record(db, appt, str(doctor_user.id), reason)
        refund_request = outcome["refundRequest"]

        # Notify patient and doctor of cancellation
        try:
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService

            dr_name = doctor_user.fullName or "Doctor"
            if not dr_name.startswith("Dr.") and not dr_name.startswith("Dr "):
                dr_name = f"Dr. {dr_name}"

            pt_user_doc = db["users"].find_one({"_id": ObjectId(appt["patientUserId"])}) if ObjectId.is_valid(str(appt.get("patientUserId", ""))) else None
            patient_name = (pt_user_doc.get("fullName") if pt_user_doc else None) or "a patient"

            # In-app notification to patient
            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(appt["patientUserId"]),
                type=NotificationType.APPOINTMENT_CANCELLED,
                title="Appointment Cancelled",
                body=(f"Your appointment with {dr_name} on {appt.get('appointmentDate')} at {appt.get('startTime')} has been cancelled."
                      + (" A full refund request was opened and is reviewed by MediConnect." if refund_request else "")),
                related_appointment_id=str(appt["_id"]),
                idempotency_key=f"doctor_cancelled_{appt['_id']}",
            )

            # In-app notification to doctor
            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(appt["doctorUserId"]),
                type=NotificationType.APPOINTMENT_CANCELLED,
                title="Appointment Cancelled",
                body=f"Appointment with {patient_name} on {appt.get('appointmentDate')} at {appt.get('startTime')} has been cancelled.",
                related_appointment_id=str(appt["_id"]),
                idempotency_key=f"doctor_cancelled_self_{appt['_id']}",
            )
        except Exception as notif_err:
            logger.warning("Failed to send doctor cancellation notification: %s", notif_err)

        updated = _get_appointment_or_404(db, appointment_id)
        pt_user = db["users"].find_one({"_id": ObjectId(updated["patientUserId"])}) if ObjectId.is_valid(updated.get("patientUserId", "")) else None
        return _build_appointment_response(
            updated,
            patient_name=pt_user.get("fullName") if pt_user else None,
            patient_email=pt_user.get("email") if pt_user else None,
            doctor_name=doctor_user.fullName,
        )

    # -------------------------------------------------------------------------
    # DOCTOR: Update appointment status (generic dispatcher)
    # -------------------------------------------------------------------------
    @staticmethod
    async def update_appointment_status(
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
        req: UpdateAppointmentStatusRequest,
    ) -> AppointmentResponse:
        """Generic doctor appointment status updater."""
        target_status = req.status.upper()
        if target_status == AppointmentStatus.CONFIRMED.value:
            return await AppointmentService.confirm_doctor_appointment(db, doctor_user, appointment_id)
        elif target_status == AppointmentStatus.COMPLETED.value:
            return await AppointmentService.complete_doctor_appointment(db, doctor_user, appointment_id)
        elif target_status == AppointmentStatus.CANCELLED.value:
            return await AppointmentService.cancel_doctor_appointment(db, doctor_user, appointment_id, reason=req.reason)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target status: {req.status}",
            )

    # -------------------------------------------------------------------------
    # SHARED: Get single appointment (with ownership guard)
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_appointment(
        db: Database,
        requester: UserResponseSchema,
        appointment_id: str,
    ) -> AppointmentResponse:
        """Fetch a single appointment; requester must be the patient, doctor, or admin."""
        appt = _get_appointment_or_404(db, appointment_id)

        is_patient = requester.role == UserRole.PATIENT.value and str(appt["patientUserId"]) == str(requester.id)
        is_doctor = requester.role == UserRole.DOCTOR.value and str(appt["doctorUserId"]) == str(requester.id)
        is_admin = requester.role == UserRole.ADMIN.value

        if not (is_patient or is_doctor or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this appointment.",
            )

        pt_user = db["users"].find_one({"_id": ObjectId(appt["patientUserId"])}) if ObjectId.is_valid(appt.get("patientUserId", "")) else None
        dr_user = db["users"].find_one({"_id": ObjectId(appt["doctorUserId"])}) if ObjectId.is_valid(appt.get("doctorUserId", "")) else None
        dr_profile = db["doctor_profiles"].find_one({"_id": ObjectId(appt["doctorProfileId"])}) if ObjectId.is_valid(appt.get("doctorProfileId", "")) else None

        return _build_appointment_response(
            appt,
            doctor_id=dr_profile.get("doctorId") if dr_profile else None,
            patient_name=pt_user.get("fullName") if pt_user else None,
            patient_email=pt_user.get("email") if pt_user else None,
            doctor_name=dr_user.get("fullName") if dr_user else None,
            specialty=dr_profile.get("specialty") if dr_profile else None,
            hospital_or_clinic=appt.get("hospitalOrClinic") or (dr_profile.get("hospitalOrClinic") if dr_profile else None),
            payment_details=_payment_details(db, appt),
        )

    # -------------------------------------------------------------------------
    # SHARED: Reschedule appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def reschedule_appointment(
        db: Database,
        requester: UserResponseSchema,
        appointment_id: str,
        req: RescheduleAppointmentRequest,
    ) -> AppointmentResponse:
        """Reschedule an existing appointment to a new date and time slot.

        Validations:
        - Requester must be the patient who booked it, the assigned doctor, or an admin.
        - Appointment must be in PENDING or CONFIRMED status.
        - New slot date and time must be valid and in the future (SL time).
        - No conflicting appointment exists for the doctor at that time slot.
        - Resets remindersSent to [] and bumps appointmentVersion.
        - Sends reschedule notifications to both patient and doctor.
        """
        appt = _get_appointment_or_404(db, appointment_id)
        if appt.get("bookingSource") == "ai_agent" and not appt.get("confirmedAt"):
            raise HTTPException(409, "Cancel this hold and accept a new proposal for a different time.")

        is_patient = requester.role == UserRole.PATIENT.value and str(appt["patientUserId"]) == str(requester.id)
        is_doctor = requester.role == UserRole.DOCTOR.value and str(appt["doctorUserId"]) == str(requester.id)
        is_admin = requester.role == UserRole.ADMIN.value

        if not (is_patient or is_doctor or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to reschedule this appointment.",
            )

        current_status = appt["status"]
        if current_status not in (AppointmentStatus.PENDING.value, AppointmentStatus.CONFIRMED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reschedule an appointment with status: {current_status}.",
            )

        if (appt.get("clinicQueue") or {}).get("status") == "in_consultation":
            raise HTTPException(409, "An appointment in consultation cannot be rescheduled.")

        new_date = req.newDate.strip()
        new_start_time = req.newStartTime.strip()

        # Parse and validate new date & time
        try:
            new_slot_dt = _dt.strptime(f"{new_date} {new_start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=SL_TIMEZONE)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date or time format.")

        sl_now = _dt.now(SL_TIMEZONE)
        if new_slot_dt <= sl_now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reschedule an appointment to a past time slot.",
            )

        # Calculate new end time if not supplied
        if req.newEndTime and req.newEndTime.strip():
            new_end_time = req.newEndTime.strip()
            _parse_hhmm(new_end_time)
        else:
            old_start_h, old_start_m = _parse_hhmm(appt.get("startTime", "09:00"))
            old_end_h, old_end_m = _parse_hhmm(appt.get("endTime", "09:30"))
            duration_minutes = (old_end_h * 60 + old_end_m) - (old_start_h * 60 + old_start_m)
            if duration_minutes <= 0:
                duration_minutes = 30
            new_s_h, new_s_m = _parse_hhmm(new_start_time)
            new_end_total = new_s_h * 60 + new_s_m + duration_minutes
            new_end_time = f"{new_end_total // 60:02d}:{new_end_total % 60:02d}"

        # The new time must be a real open slot in the doctor's schedule (not any clock time), P-05q.
        new_availability_id = appt.get("availabilityId")
        if not is_admin:
            from app.services.doctor_service import DoctorService
            dr_profile_doc = db["doctor_profiles"].find_one(
                {"_id": ObjectId(appt["doctorProfileId"])} if ObjectId.is_valid(str(appt.get("doctorProfileId")))
                else {"userId": str(appt["doctorUserId"])}) or {}
            open_day = await DoctorService.get_doctor_patient_slots(db, dr_profile_doc.get("doctorId") or "", new_date) \
                if dr_profile_doc.get("doctorId") else None
            slot = next((item for item in getattr(open_day, "slots", []) if item.startTime == new_start_time), None)
            if not slot:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The doctor is not available at the selected date and time.",
                )
            new_end_time = slot.endTime
            new_availability_id = slot.availabilityId or new_availability_id

        # Check for conflict with existing active appointments for the same doctor
        conflict = get_appointment_collection(db).find_one({
            "_id": {"$ne": ObjectId(appointment_id)},
            "doctorUserId": str(appt["doctorUserId"]),
            "appointmentDate": new_date,
            "status": {"$in": [AppointmentStatus.HOLD.value, AppointmentStatus.PENDING.value,
                               AppointmentStatus.CONFIRMED.value, AppointmentStatus.COMPLETED.value]},
            "startTime": new_start_time,
        })
        if conflict and not (conflict["status"] in {"HOLD", "PENDING"} and conflict.get("holdExpiresAt")
                             and (conflict["holdExpiresAt"].replace(tzinfo=timezone.utc)
                                  if conflict["holdExpiresAt"].tzinfo is None else conflict["holdExpiresAt"]) <= utc_now()
                             and conflict.get("paymentStatus") != PaymentStatus.PAID.value):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The doctor is not available at the selected date and time.",
            )
        if conflict:  # an expired unpaid hold no longer owns the slot
            AppointmentService.release_expired_holds(db)

        new_version = int(appt.get("appointmentVersion", 1)) + 1
        now = utc_now()

        # A single atomic move: the booking keeps its payment and status, so a failed move never loses the
        # existing confirmed appointment. The unique active-slot index rejects a slot taken concurrently.
        try:
            updated_slot = get_appointment_collection(db).update_one(
                {"_id": ObjectId(appointment_id), "status": current_status,
                 "appointmentVersion": appt.get("appointmentVersion", {"$exists": False}),
                 "clinicQueue.status": {"$ne": "in_consultation"}},
                {
                    "$set": {
                        "appointmentDate": new_date,
                        "startTime": new_start_time,
                        "endTime": new_end_time,
                        "availabilityId": new_availability_id,
                        "appointmentVersion": new_version,
                        "remindersSent": [],  # Invalidate previously scheduled reminders
                        "updatedAt": now,
                    },
                    "$push": {"rescheduleHistory": {
                        "fromDate": appt.get("appointmentDate"), "fromStartTime": appt.get("startTime"),
                        "toDate": new_date, "toStartTime": new_start_time, "byRole": requester.role, "at": now,
                    }},
                },
            )
        except DuplicateKeyError:
            raise HTTPException(409, "That time was just booked by someone else. Your original appointment is unchanged.")

        if updated_slot.matched_count != 1:
            raise HTTPException(409, "The appointment changed. Refresh before rescheduling.")
        from app.services.appointment_events import record_appointment_event
        record_appointment_event(db, appointment_id, "APPOINTMENT_RESCHEDULED", actor_role=requester.role,
                                 actor_id=str(requester.id), from_status=current_status, to_status=current_status,
                                 details={"from": f"{appt.get('appointmentDate')} {appt.get('startTime')}",
                                          "to": f"{new_date} {new_start_time}", "version": new_version},
                                 idempotency_key=f"rescheduled_{appointment_id}_v{new_version}")

        # Notify patient and doctor
        try:
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService

            dr_user_doc = db["users"].find_one({"_id": ObjectId(appt["doctorUserId"])}) if ObjectId.is_valid(str(appt.get("doctorUserId", ""))) else None
            pt_user_doc = db["users"].find_one({"_id": ObjectId(appt["patientUserId"])}) if ObjectId.is_valid(str(appt.get("patientUserId", ""))) else None
            patient_name = (pt_user_doc.get("fullName") if pt_user_doc else None) or "a patient"

            # Patient notification: "Your appointment has been moved to [New Date] at [New Time]."
            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(appt["patientUserId"]),
                type=NotificationType.APPOINTMENT_RESCHEDULED,
                title="Appointment Rescheduled",
                body=f"Your appointment has been moved to {new_date} at {new_start_time}.",
                related_appointment_id=str(appt["_id"]),
                idempotency_key=f"rescheduled_patient_{appt['_id']}_v{new_version}",
            )

            # Doctor notification
            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(appt["doctorUserId"]),
                type=NotificationType.APPOINTMENT_RESCHEDULED,
                title="Appointment Rescheduled",
                body=f"Appointment with {patient_name} has been moved to {new_date} at {new_start_time}.",
                related_appointment_id=str(appt["_id"]),
                idempotency_key=f"rescheduled_doctor_{appt['_id']}_v{new_version}",
            )
        except Exception as notif_err:
            logger.warning("Failed to send reschedule notifications: %s", notif_err)

        updated = _get_appointment_or_404(db, appointment_id)
        pt_user = db["users"].find_one({"_id": ObjectId(updated["patientUserId"])}) if ObjectId.is_valid(updated.get("patientUserId", "")) else None
        dr_user = db["users"].find_one({"_id": ObjectId(updated["doctorUserId"])}) if ObjectId.is_valid(updated.get("doctorUserId", "")) else None
        dr_profile = db["doctor_profiles"].find_one({"_id": ObjectId(updated["doctorProfileId"])}) if ObjectId.is_valid(updated.get("doctorProfileId", "")) else None

        return _build_appointment_response(
            updated,
            doctor_id=dr_profile.get("doctorId") if dr_profile else None,
            patient_name=pt_user.get("fullName") if pt_user else None,
            patient_email=pt_user.get("email") if pt_user else None,
            doctor_name=dr_user.get("fullName") if dr_user else None,
            specialty=dr_profile.get("specialty") if dr_profile else None,
            hospital_or_clinic=dr_profile.get("hospitalOrClinic") if dr_profile else None,
        )


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """Parse HH:MM string into (hours, minutes). Raises 400 on invalid format."""
    parts = time_str.split(":")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Time must be in HH:MM format.")
    try:
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError()
        return h, m
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time values in HH:MM.")


def _get_appointment_or_404(db: Database, appointment_id: str) -> Dict[str, Any]:
    """Fetch appointment document by ID or raise 404."""
    if not ObjectId.is_valid(appointment_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid appointment ID format.")

    appt = get_appointment_collection(db).find_one({"_id": ObjectId(appointment_id)})
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    return appt


def _assert_doctor_approved_and_active(db: Database, doctor_user: UserResponseSchema) -> Dict[str, Any]:
    """Ensure doctor user is DOCTOR, account is ACTIVE, and doctor profile is APPROVED."""
    if doctor_user.role != UserRole.DOCTOR.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can access this.")

    if doctor_user.accountStatus != AccountStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your doctor account is not active or verified.",
        )

    profile = db["doctor_profiles"].find_one({"userId": str(doctor_user.id)})
    if not profile or profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only approved doctors with active accounts can manage appointments.",
        )
    return profile
