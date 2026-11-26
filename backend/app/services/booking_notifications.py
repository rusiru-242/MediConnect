"""Durable appointment confirmations. Provider calls run outside the booking transaction."""
import hashlib
from datetime import timedelta
from html import escape
import os
import re

from pymongo import ReturnDocument
import requests

from app.config.settings import settings
from app.models.appointment import utc_now
from app.models.notification import NotificationType
from app.services.email_service import EmailService, outcome_of
from app.services.notification_service import NotificationService


def normalize_phone(value):
    value = re.sub(r"[ ()-]", "", value or "")
    if re.fullmatch(r"07\d{8}", value):
        value = "+94" + value[1:]
    return value if re.fullmatch(r"\+947\d{8}", value) else None


def phone_fingerprint(value):
    phone = normalize_phone(value)
    return hashlib.sha256(phone.encode()).hexdigest() if phone else None


def twilio_config():
    return tuple(os.getenv(name, "").strip() for name in (
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_MESSAGING_SERVICE_SID",
    ))


def send_confirmation(db, appointment, channel):
    from bson import ObjectId

    recipient_id = appointment["doctorUserId"] if channel == "doctor" else appointment["patientUserId"]
    if not ObjectId.is_valid(recipient_id):
        return {"status": "skipped", "reason": "invalid_recipient"}
    user = db["users"].find_one({"_id": ObjectId(recipient_id)}) or {}
    preferences = user.get("notificationPreferences") or {}
    if preferences.get("appointmentConfirmation") is False or preferences.get(f"{channel}Notifications") is False:
        return {"status": "skipped", "reason": "preference_disabled"}
    reference = str(appointment["_id"])
    doctor = appointment.get("bookingDoctorName") or "your doctor"
    when = f"{appointment['appointmentDate']} at {appointment['startTime']} (Asia/Colombo)"
    if channel == "doctor":
        notification = NotificationService.create_notification(
            db=db, recipient_user_id=recipient_id, type=NotificationType.APPOINTMENT_CONFIRMED,
            title="Appointment Confirmed", body=f"A patient confirmed an appointment for {when}.",
            related_appointment_id=reference, idempotency_key=f"ai_confirmed_{reference}",
            send_push=False,
        )
        if notification is None:
            return {"status": "pending", "reason": "in_app_write_failed"}
        return {"status": "delivered"}
    if channel == "email":
        if not user.get("emailVerified") or not user.get("email"):
            return {"status": "skipped", "reason": "verified_email_required"}
        if not (settings.SMTP_HOST or "").strip():
            # A02-BUG-004: a provider that is not configured is "disabled", not a delivery failure.
            return {"status": "disabled", "reason": "provider_not_configured"}
        message = (
            f"Hello {user.get('fullName') or 'patient'},\n\n"
            f"Your MediConnect appointment with {doctor} is confirmed.\n"
            f"Specialty: {appointment.get('bookingSpecialty') or 'See doctor profile'}\n"
            f"Time: {when}\nClinic: {appointment.get('hospitalOrClinic') or 'See appointment details'}\n"
            f"Payment: {'Paid' if appointment['paymentStatus'] == 'PAID' else 'No payment required'}\n"
            f"Booking reference: {reference}\n\nManage your appointment in My Appointments."
        )
        outcome = outcome_of(EmailService._send_email(
            user["email"], "MediConnect Appointment Confirmation", message,
            "<h1>MediConnect</h1><p>" + escape(message).replace("\n", "<br>") + "</p>",
        ))
        # "sent" = accepted by the SMTP server (not proof of mailbox delivery). A02-BUG-003: a connection failure
        # before transmission is retried; a refusal is permanent; only a break during transmission is "uncertain".
        return {
            "accepted": {"status": "sent"},
            "retry": {"status": "pending", "reason": outcome.reason},
            "rejected": {"status": "failed", "reason": outcome.reason},
            "disabled": {"status": "disabled", "reason": "provider_not_configured"},
        }.get(outcome.status, {"status": "uncertain", "reason": outcome.reason or "smtp_not_acknowledged"})

    phone = normalize_phone(user.get("phone"))
    if not phone or not appointment.get("smsConsent") or (
        appointment.get("smsDestinationHash") != phone_fingerprint(phone)
    ):
        return {"status": "skipped", "reason": "authorized_mobile_required"}
    account, token, service = twilio_config()
    if not all((account, token, service)):
        return {"status": "disabled", "reason": "provider_not_configured"}
    response = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{account}/Messages.json",
        auth=(account, token), timeout=10,
        data={"MessagingServiceSid": service, "To": phone,
              "Body": f"MediConnect: Your appointment with {doctor} is confirmed for {when}. Booking Ref: {reference}."},
    )
    if response.status_code == 429:
        return {"status": "pending", "reason": "rate_limited"}
    if response.status_code >= 500:
        return {"status": "uncertain", "reason": "gateway_response_unknown"}
    if not response.ok:
        return {"status": "failed", "reason": "gateway_rejected"}
    body = response.json()
    if not body.get("sid"):
        return {"status": "uncertain", "reason": "missing_provider_reference"}
    return {"status": sms_status(body.get("status")), "providerId": body["sid"]}


def sms_status(value):
    if value in {"failed", "undelivered", "canceled"}:
        return "failed"
    if value in {"sent", "delivered"}:
        return value
    return "accepted"


def run_confirmation_outbox(db):
    collection = db["appointments"]
    for channel in ("email", "sms", "doctor"):
        path = f"confirmationOutbox.{channel}"
        now = utc_now()
        collection.update_many(
            {f"{path}.status": "sending", f"{path}.leaseUntil": {"$lte": now}},
            {"$set": {f"{path}.status": "uncertain", f"{path}.reason": "worker_interrupted"}},
        )
        for _ in range(10):
            now = utc_now()
            row = collection.find_one_and_update(
                {"confirmedAt": {"$exists": True}, "status": "CONFIRMED", f"{path}.status": "pending",
                 f"{path}.nextAttemptAt": {"$lte": now}},
                {"$set": {f"{path}.status": "sending", f"{path}.leaseUntil": now + timedelta(minutes=2)},
                 "$inc": {f"{path}.attempts": 1}},
                return_document=ReturnDocument.AFTER,
            )
            if not row:
                break
            attempt = row["confirmationOutbox"][channel]["attempts"]
            try:
                result = send_confirmation(db, row, channel)
            except requests.ConnectTimeout:
                result = {"status": "pending", "reason": "connection_timeout"}
            except Exception:
                result = {"status": "uncertain", "reason": "provider_result_unknown"}
            if result["status"] == "pending" and attempt >= 5:
                result["status"] = "failed"
            result["nextAttemptAt"] = now + timedelta(minutes=2 ** min(attempt, 5))
            collection.update_one(
                {"_id": row["_id"], f"{path}.status": "sending", f"{path}.attempts": attempt},
                {"$set": {f"{path}.{key}": value for key, value in result.items()}},
            )
    _poll_sms(db)


def _poll_sms(db):
    account, token, _ = twilio_config()
    if not account or not token:
        return
    collection = db["appointments"]
    path = "confirmationOutbox.sms"
    now = utc_now()
    for _ in range(10):
        row = collection.find_one_and_update(
            {f"{path}.status": {"$in": ["accepted", "sent"]}, f"{path}.providerId": {"$exists": True},
             f"{path}.nextAttemptAt": {"$lte": now}},
            {"$set": {f"{path}.nextAttemptAt": now + timedelta(minutes=10)}},
        )
        if not row:
            break
        sid = row["confirmationOutbox"]["sms"]["providerId"]
        if not re.fullmatch(r"SM[a-fA-F0-9]{32}", sid):
            continue
        try:
            response = requests.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{account}/Messages/{sid}.json",
                auth=(account, token), timeout=10,
            )
            if response.ok:
                collection.update_one(
                    {"_id": row["_id"], f"{path}.providerId": sid, f"{path}.status": {"$in": ["accepted", "sent"]}},
                    {"$set": {f"{path}.status": sms_status(response.json().get("status"))}},
                )
        except (requests.RequestException, ValueError):
            continue
