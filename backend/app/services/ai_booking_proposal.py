"""Server-owned proposals and payment finalization for AI bookings."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

from app.config.settings import settings
from app.models.appointment import utc_now
from app.services.doctor_service import DoctorService
from app.services.booking_notifications import normalize_phone, phone_fingerprint


def minor_units(value):
    try:
        amount = Decimal(str(value)) * 100
        if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
            raise ValueError
        return int(amount)
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(409, "The consultation price could not be verified.") from None


def masked_contacts(user):
    preferences = user.get("notificationPreferences") or {}
    enabled = preferences.get("appointmentConfirmation") is not False
    email = user.get("email") or ""
    phone = user.get("phone") or ""
    return {
        "maskedEmail": email[:1] + "***@" + email.split("@")[-1] if (
            enabled and user.get("emailVerified") and "@" in email
        ) else None,
        "maskedPhone": "***" + phone[-4:] if (
            enabled and normalize_phone(phone)
        ) else None,
    }


async def prepare_proposal(db, patient, doc, *, automatic=False):
    from app.agents.booking_agent import BookingAgent

    doctor, slot = doc.get("selectedDoctor"), doc.get("selectedSlot")
    if automatic:
        if doc.get("appointmentId") or doc.get("activeIntent") != "BOOK_APPOINTMENT":
            return
        if (doc["messages"][-1].get("metadata") or {}).get("type") not in {"doctor_options", "no_results"}:
            return
        prefs = doc.get("preferences") or {}
        date, time = prefs.get("date"), prefs.get("requestedTime")
        window = {"morning": (0, 12 * 60), "afternoon": (12 * 60, 17 * 60), "evening": (17 * 60, 24 * 60)}.get(
            prefs.get("timeRange"),
        )
        if not date or not (time or window):
            return
        if doc.get("phase2Proposal"):
            doc.update(selectedSlot=None, bookingSummary=None, state="AWAITING_DOCTOR_SELECTION")
        options = []
        eligible = []
        page = 1
        while True:
            result = await DoctorService.list_approved_doctors(
                db, page=page, limit=50, specialty=prefs.get("specialty"),
                search=prefs.get("doctorName"), city=prefs.get("city"), hospital=prefs.get("hospital"),
                max_fee=prefs.get("maxFee"), specialty_variants=True,
            )
            for candidate in result.items:
                if candidate.consultationFee is None or not candidate.doctorId:
                    continue
                eligible.append(candidate)
                day = await DoctorService.get_doctor_patient_slots(db, candidate.doctorId, date)
                options.extend((candidate.model_dump(), {**available.model_dump(), "date": date})
                               for available in day.slots if available.availabilityId)
            if page >= result.totalPages:
                break
            page += 1
        if not options:
            alternatives = []
            for candidate in eligible:
                available = await DoctorService.get_doctor_patient_slots(db, candidate.doctorId)
                days = available if isinstance(available, list) else [available]
                day = next((item for item in days if item.date != date and item.slots), None)
                if day:
                    alternatives.append({
                        **candidate.model_dump(), "requestedDate": day.date,
                        "availableSlots": [{**slot.model_dump(), "date": day.date} for slot in day.slots[:4]],
                    })
                if len(alternatives) >= 5:
                    break
            doc.update(candidateDoctors=alternatives, selectedDoctor=None, selectedSlot=None,
                       bookingSummary=None, state="AWAITING_DOCTOR_SELECTION" if alternatives else "COLLECTING_PREFERENCES")
            if alternatives:
                doc["phase2Proposal"] = True
            doc["messages"][-1].update(
                content=(f"No slot was open on {date}. These doctors have openings on other dates. Choose a date to review."
                         if alternatives else "No matching doctor has an open slot. Try another date or location."),
                metadata={"type": "doctor_options", "doctors": alternatives} if alternatives else {"type": "no_results"},
            )
            return
        def minutes(value):
            hour, minute = map(int, value.split(":"))
            return hour * 60 + minute
        def rank(pair):
            start = minutes(pair[1]["startTime"])
            priority = abs(start - minutes(time)) if time else int(not window[0] <= start < window[1])
            return (priority, minor_units(pair[0]["consultationFee"]), pair[0]["doctorId"], pair[1]["startTime"])

        ranked = sorted(options, key=rank)
        doctor, slot = ranked[0]
        cards = {}
        for candidate, available in ranked:
            key = candidate["doctorId"]
            if key not in cards:
                if len(cards) == 5:
                    continue
                cards[key] = {**candidate, "availableSlots": [], "requestedDate": date, "requestedTime": time}
            if len(cards[key]["availableSlots"]) < 8:
                cards[key]["availableSlots"].append(available)
        doc["candidateDoctors"] = list(cards.values())
        doc["messages"][-1]["metadata"] = {"type": "doctor_options", "doctors": doc["candidateDoctors"]}
        doc["messages"][-1]["content"] = "Here are doctors with open slots on your requested date."
    if not doctor or not slot:
        return
    profile = await DoctorService.get_approved_doctor_detail(db, doctor["doctorId"])
    amount = minor_units(profile.consultationFee)
    slots = await DoctorService.get_doctor_patient_slots(db, doctor["doctorId"], slot["date"])
    match = next((item for item in slots.slots if item.startTime == slot["startTime"]
                  and item.availabilityId == slot["availabilityId"]), None)
    if not match:
        if automatic:
            return
        raise HTTPException(409, "That slot is no longer available.")
    slot = {**slot, "endTime": match.endTime}
    doctor = {**doctor, **profile.model_dump(), "consultationFee": amount / 100}
    user = db["users"].find_one({"_id": ObjectId(str(patient.id))}) or {}
    summary = BookingAgent._build_booking_summary(doctor, slot)
    requested = (doc.get("preferences") or {}).get("requestedTime")
    summary.update(
        doctorId=doctor["doctorId"], acceptedSlot=slot.copy(),
        proposalId=str(ObjectId()), proposalExpiresAt=utc_now() + timedelta(minutes=10),
        timezone="Asia/Colombo", currency=(settings.STRIPE_CURRENCY or "lkr").lower(), city=profile.city,
        patientName=patient.fullName, requestedTime=requested,
        # BUG-055: only an automatic proposal can be "closest"; a slot the patient picked is described as such.
        selectionReason=("Selected by you." if not automatic
                         else "Closest available time on the requested date." if requested and requested != slot["startTime"]
                         else "Exact match for your requested time." if requested
                         else "Matching slot. Ties are ranked by fee and doctor ID."),
        smsDestinationHash=phone_fingerprint(user.get("phone")), **masked_contacts(user),
    )
    doc["phase2Proposal"] = True
    doc.update(selectedDoctor=doctor, selectedSlot=slot, bookingSummary=summary,
               state="AWAITING_BOOKING_CONFIRMATION")
    if automatic and not requested and window:
        if not window[0] <= minutes(slot["startTime"]) < window[1]:
            summary["selectionReason"] = "No slot was open in your preferred time range. Review this alternative."
        else:
            summary["selectionReason"] = "Available in your preferred time range. Ties are ranked by fee and doctor ID."
    if automatic:
        doc["messages"].append({
            "id": str(ObjectId()), "sender": "assistant", "timestamp": utc_now(),
            "content": "Review the proposed appointment below. Your booking requires your acceptance."
            if not requested or requested == slot["startTime"] else
            f"{requested} was unavailable. The closest option is {slot['startTime']} on {slot['date']}. Review it below.",
            "metadata": {"type": "booking_proposal", "proposalId": summary["proposalId"]},
        })


def notification_entries(now):
    return {channel: {"status": "pending", "nextAttemptAt": now, "attempts": 0}
            for channel in ("email", "sms", "doctor")}


def _notify_patient_confirmed(db, payment, appointment):
    """A03-BUG-020: the patient's in-app confirmation of an AI booking (the doctor's comes from the outbox).

    Before, only a decline produced an in-app notice, so after a decline and a successful retry the patient's latest
    payment notice still said "Payment Failed". Same idempotency key as the standard booking path (exactly once).
    """
    try:
        from app.models.notification import NotificationType
        from app.services.notification_service import NotificationService
        minor = appointment.get("acceptedAmountMinor")
        paid = f"Your payment of LKR {minor / 100:,.0f} was successful." if isinstance(minor, int) and minor > 0             else "Your payment was successful."
        NotificationService.create_notification(
            db=db, recipient_user_id=str(payment["patientUserId"]), type=NotificationType.PAYMENT_SUCCESS,
            title="Payment Successful", body=f"{paid} Your appointment has been confirmed.",
            related_appointment_id=str(payment["appointmentId"]), related_payment_id=str(payment["_id"]),
            idempotency_key=f"pay_success_{payment['_id']}",
        )
    except Exception:  # the confirmation itself is stored; the notice is best effort
        pass


def settle_ai_payment(db, payment, intent, now):
    """Confirm atomically or leave a durable record for authorized reconciliation."""
    def get(key):
        return intent.get(key) if isinstance(intent, dict) else getattr(intent, key, None)

    if not ObjectId.is_valid(payment.get("appointmentId")):
        return None
    appointment_id = ObjectId(payment["appointmentId"])
    payments = db["payments"]
    intent_id = payment["stripePaymentIntentId"]
    appointment = db["appointments"].find_one({"_id": appointment_id, "bookingSource": "ai_agent"})
    if not appointment:
        return None
    valid = (get("id") == intent_id and get("amount_received") == appointment["acceptedAmountMinor"]
             and get("currency") == appointment["bookingCurrency"])
    already = appointment.get("stripePaymentIntentId") == intent_id and appointment.get("paymentStatus") == "PAID"
    if valid and not already:
        updated = db["appointments"].find_one_and_update(
            {"_id": appointment_id, "status": {"$in": ["HOLD", "PENDING"]},
             "$expr": {"$gt": ["$holdExpiresAt", "$$NOW"]}, "paymentStatus": {"$ne": "PAID"},
             "patientUserId": payment["patientUserId"]},
            {"$set": {"status": "CONFIRMED", "paymentStatus": "PAID", "updatedAt": now,
                      "stripePaymentIntentId": intent_id, "confirmedAt": now,
                      "confirmationOutbox": notification_entries(now)}},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            current = db["appointments"].find_one({"_id": appointment_id}) or {}
            already = current.get("stripePaymentIntentId") == intent_id and current.get("paymentStatus") == "PAID"
        else:
            already = True
            _notify_patient_confirmed(db, payment, updated)
    if valid and already:
        payments.update_one({"_id": payment["_id"]}, {"$set": {
            "status": "SUCCEEDED", "paidAt": now, "updatedAt": now, "reconciliationState": "CONFIRMED",
        }})
        return "success"
    payments.update_one({"_id": payment["_id"], "reconciliationState": {"$nin": ["CONFIRMED", "REFUND_PENDING", "REFUNDED", "REFUND_FAILED"]}}, {"$set": {
        "status": "SUCCEEDED", "paidAt": now, "updatedAt": now, "reconciliationState": "REVIEW_REQUIRED",
        "reconciliationReason": "booking_unavailable" if valid else "amount_or_currency_mismatch",
    }})
    return "reconciliation_required"
