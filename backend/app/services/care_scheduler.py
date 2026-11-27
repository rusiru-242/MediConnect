"""Durable patient care occurrences with source revalidation and private delivery."""
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import os
from zoneinfo import ZoneInfo

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
import requests

from app.config.settings import settings
from app.models.notification import NotificationType
from app.services.booking_notifications import normalize_phone, phone_fingerprint, twilio_config, sms_status
from app.services.email_service import EmailService, outcome_of
from app.services.notification_service import NotificationService

COLOMBO = ZoneInfo("Asia/Colombo")
CHANNELS = ("inApp", "push", "email", "sms")


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def medication_revision(item, instructions=None):
    return hashlib.sha256(json.dumps([item, instructions], sort_keys=True, default=str).encode()).hexdigest()


def create_indexes(db):
    def _safe_index(coll, keys, **kwargs):
        try:
            coll.create_index(keys, **kwargs)
        except Exception:
            pass

    events = db["care_reminder_events"]
    _safe_index(events, [("state", 1), ("nextAttemptAt", 1)])
    _safe_index(events, [("patientUserId", 1), ("scheduledAt", 1)])
    _safe_index(events, [("doctorUserId", 1), ("sourceId", 1), ("scheduledAt", -1)])
    _safe_index(db["patient_health_measurements"], [("patientUserId", 1), ("recordedAt", -1)])
    _safe_index(db["medication_reminders"], [("approvalKey", 1)], unique=True, sparse=True)
    _safe_index(db["medication_reminders"], [("status", 1), ("enabled", 1), ("endDate", 1)])
    _safe_index(db["appointments"], [("status", 1), ("appointmentDate", 1)])
    _safe_index(db["care_plans"], [("status", 1), ("followUpDate", 1)])
    _safe_index(db["care_plans"], [("status", 1), ("tasks.dueAt", 1)])
    _safe_index(db["care_tracking_schedules"], [("patientUserId", 1), ("enabled", 1)])


def local_at(day, clock, zone=COLOMBO):
    return datetime.combine(day, time.fromisoformat(clock), zone).astimezone(timezone.utc)


def approved_medication(db, source):
    if not source.get("approvedBy") or not ObjectId.is_valid(source.get("prescriptionDbId")):
        return None
    rx = db["prescriptions"].find_one({
        "_id": ObjectId(source["prescriptionDbId"]), "patientUserId": source["patientUserId"],
        "doctorUserId": source["approvedBy"], "status": {"$in": ["ISSUED", "DISPENSED", "AMENDED"]},
    })
    if not rx:
        return None
    items = rx.get("medicationItems", [])
    index = source.get("prescriptionMedicationIndex", -1)
    if not 0 <= index < len(items):
        return None
    item = items[index]
    return item if medication_revision(item, rx.get("instructions")) == source.get("prescriptionRevision") else None


def event(source, collection, kind, at, due, *, task=None, suffix="", expires=None):
    version = source.get("scheduleVersion", source.get("appointmentVersion", 1)) if collection != "care_plans" else (
        task.get("taskId") if task else source.get("followUpDate")
    )
    identifier = hashlib.sha256(f"{collection}:{source['_id']}:{kind}:{at.isoformat()}:{version}:{suffix}".encode()).hexdigest()
    return {
        "_id": identifier, "sourceCollection": collection, "sourceId": str(source["_id"]),
        "patientUserId": source["patientUserId"],
        "doctorUserId": source.get("approvedBy") or source.get("doctorUserId"),
        "kind": kind, "scheduledAt": at, "dueAt": due, "expiresAt": expires or due + timedelta(hours=4),
        "taskId": task.get("taskId") if task else None, "nextAttemptAt": due,
        "state": "pending", "attempts": 0, "action": None, "snoozes": 0, "audit": [],
    }


def occurrences(db, collection, source, start, end):
    if collection == "appointments":
        if source.get("status") != "CONFIRMED":
            return
        at = local_at(datetime.fromisoformat(source["appointmentDate"]).date(), source["startTime"])
        for hours, preference in ((24, "reminder24h"), (2, "reminder2h")):
            due = at - timedelta(hours=hours)
            if start <= due < end:
                yield {**event(source, collection, "appointment", at, due, suffix=str(hours), expires=at),
                       "preference": preference, "legacyMarker": str(hours) + "h"}
    elif collection == "care_plans":
        if source.get("status") not in {"ACTIVE", "OVERDUE"}:
            return
        at = local_at(datetime.fromisoformat(source["followUpDate"]).date(), "09:00")
        for days, marker in ((0, "DUE"), (1, "1D"), (7, "7D")):
            due = at - timedelta(days=days)
            if start <= due < end:
                yield {**event(source, collection, "follow_up", at, due, suffix=marker),
                       "legacyMarker": marker}
        for task in source.get("tasks", []):
            if task.get("isCompleted") or not task.get("dueAt"):
                continue
            at = utc(task["dueAt"])
            due = at - timedelta(minutes=task.get("remindMinutesBefore", 0))
            if start <= due < end:
                yield event(source, collection, task.get("kind", "task"), at, due, task=task,
                            expires=max(at, due) + timedelta(hours=4))
    elif collection == "medication_reminders":
        if source.get("status") != "ACTIVE" or not source.get("enabled") or not approved_medication(db, source):
            return
        zone = ZoneInfo(source["patientTimezone"])
        day = start.astimezone(zone).date()
        while day <= end.astimezone(zone).date():
            for clock in source["scheduledTimes"]:
                at = local_at(day, clock, zone)
                if (start <= at < end and utc(source["startDate"]) <= at < utc(source["endDate"])):
                    yield event(source, collection, "medication", at, at)
            day += timedelta(days=1)
    elif collection == "care_tracking_schedules":
        if not source.get("enabled"):
            return
        day = start.astimezone(COLOMBO).date()
        while day <= end.astimezone(COLOMBO).date():
            at = local_at(day, source["clock"])
            if start <= at < end and at >= utc(source["createdAt"]):
                yield event(source, collection, "measurement", at, at)
            day += timedelta(days=1)


def rows(db, start, end, patient_id=None):
    scope = {"patientUserId": patient_id} if patient_id is not None else {}
    first = start.astimezone(COLOMBO).date().isoformat()
    last = (end + timedelta(days=1)).astimezone(COLOMBO).date().isoformat()
    followup_last = (end + timedelta(days=7)).astimezone(COLOMBO).date().isoformat()
    sources = {
        "appointments": {"status": "CONFIRMED", "appointmentDate": {"$gte": first, "$lte": last}},
        "care_plans": {"status": {"$in": ["ACTIVE", "OVERDUE"]}, "$or": [
            {"followUpDate": {"$gte": first, "$lte": followup_last}},
            {"tasks.dueAt": {"$gte": start, "$lte": end + timedelta(days=1)}},
        ]},
        "medication_reminders": {"status": "ACTIVE", "enabled": True, "approvedBy": {"$exists": True},
                                 "startDate": {"$lt": end}, "endDate": {"$gt": start}},
        "care_tracking_schedules": {"enabled": True, "createdAt": {"$lt": end}},
    }
    for collection, query in sources.items():
        for source in db[collection].find({**scope, **query}):
            try:
                yield from occurrences(db, collection, source, start, end)
            except (ValueError, TypeError, KeyError):
                # An obsolete or incomplete clinical record cannot produce a reminder.
                continue


def materialize(db, row):
    try:
        db["care_reminder_events"].update_one({"_id": row["_id"]}, {"$setOnInsert": row}, upsert=True)
    except DuplicateKeyError:
        pass


def current_source(db, row):
    collection = row["sourceCollection"]
    identifier = row["sourceId"] if collection == "care_tracking_schedules" else ObjectId(row["sourceId"])
    source = db[collection].find_one({"_id": identifier, "patientUserId": row["patientUserId"]})
    if not source:
        return None
    due = utc(row["dueAt"])
    try:
        return source if any(candidate["_id"] == row["_id"] for candidate in
                             occurrences(db, collection, source, due, due + timedelta(seconds=1))) else None
    except (ValueError, TypeError, KeyError):
        return None


def private_message(kind):
    return {
        "medication": "It’s time for your scheduled medication. Open MediConnect for details.",
        "appointment": "You have an upcoming appointment. Open MediConnect for details.",
        "follow_up": "You have a follow-up reminder. Open MediConnect for details.",
        "test": "You have an upcoming care task. Open MediConnect for details.",
    }.get(kind, "You have a care reminder. Open MediConnect for details.")


def deliver(db, row, channel):
    patient_id = row["patientUserId"]
    user = db["users"].find_one({"_id": ObjectId(patient_id)}, {
        "email": 1, "emailVerified": 1, "phone": 1, "notificationPreferences": 1,
    }) or {}
    prefs = user.get("notificationPreferences") or {}
    preference = row.get("preference")
    default = prefs.get("reminder1h", True) if preference == "reminder2h" else True
    if prefs.get(preference, default) is False or prefs.get("careReminders", True) is False:
        return "skipped", None
    title, body = "MediConnect reminder", private_message(row["kind"])
    if channel == "inApp":
        notice = NotificationService.create_notification(
            db, patient_id, NotificationType.CARE_REMINDER, title, body,
            idempotency_key=f"care_{row['_id']}_{row['snoozes']}", send_push=False,
            related_care_event_id=row["_id"],
        )
        return ("stored", None) if notice is not None else ("retry", None)
    if channel == "push":
        if prefs.get("pushNotifications") is False:
            return "skipped", None
        result = NotificationService._send_fcm_push(
            db, patient_id, title, body, {"type": "CARE_REMINDER", "careEventId": row["_id"]},
        )
        # A02-BUG-004: Firebase not configured is "disabled", not a delivery outcome.
        return {"unavailable": "disabled"}.get(result, result or "uncertain"), None
    if row["kind"] == "medication":
        return "skipped", None
    if channel == "email":
        if not prefs.get("careEmail") or not user.get("emailVerified") or not user.get("email"):
            return "skipped", None
        if not (settings.SMTP_HOST or "").strip():
            return "disabled", None
        # A02-BUG-003: "accepted" = accepted by the SMTP server; a failure before transmission is retried.
        outcome = outcome_of(EmailService._send_email(user["email"], title, body, body))
        return {"accepted": "accepted", "retry": "retry", "rejected": "failed",
                "disabled": "disabled"}.get(outcome.status, "uncertain"), None
    phone = normalize_phone(user.get("phone"))
    if not prefs.get("careSms") or not phone or prefs.get("careSmsPhoneHash") != phone_fingerprint(phone):
        return "skipped", None
    account, token, service = twilio_config()
    if not all((account, token, service)):
        return "disabled", None
    response = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{account}/Messages.json",
        auth=(account, token), timeout=10,
        data={"MessagingServiceSid": service, "To": phone, "Body": f"MediConnect: {body}"},
    )
    if response.status_code == 429:
        return "retry", None
    if response.status_code >= 500:
        return "uncertain", None
    if not response.ok:
        return "failed", None
    message = response.json()
    return (sms_status(message.get("status")), message["sid"]) if message.get("sid") else ("uncertain", None)


def run_scheduler(db, now=None):
    now = now or datetime.now(timezone.utc)
    db["care_plans"].update_many(
        {"status": "ACTIVE", "followUpDate": {"$lt": now.astimezone(COLOMBO).date().isoformat()}},
        {"$set": {"status": "OVERDUE", "updatedAt": now}},
    )
    sent = 0
    for row in rows(db, now - timedelta(hours=4), now + timedelta(seconds=1)):
        if row["expiresAt"] > now and row["dueAt"] <= now:
            marker = row.get("legacyMarker")
            if marker:
                source = db[row["sourceCollection"]].find_one({"_id": ObjectId(row["sourceId"])}, {"remindersSent": 1})
                if source and marker in source.get("remindersSent", []):
                    continue
            materialize(db, row)
    events = db["care_reminder_events"]
    recover_interrupted(events, now)
    events.update_many({"state": "pending", "expiresAt": {"$lte": now}},
                       {"$set": {"state": "expired"}})
    for _ in range(30):
        row = events.find_one_and_update(
            {"state": "pending", "nextAttemptAt": {"$lte": now}, "expiresAt": {"$gt": now},
             "action": {"$nin": ["taken", "skipped", "completed"]}},
            # P05-N16: the lease uses the same clock as the expiry check above (the run's `now`, or the wall clock
            # if later). It used the wall clock only, so a run with an injected clock judged live leases expired.
            {"$set": {"state": "sending",
                      "leaseUntil": max(now, datetime.now(timezone.utc)) + timedelta(minutes=3)},
             "$inc": {"attempts": 1}},
            sort=[("nextAttemptAt", 1)], return_document=ReturnDocument.AFTER,
        )
        if not row:
            break
        key = {"_id": row["_id"], "state": "sending", "attempts": row["attempts"]}
        if not current_source(db, row):
            events.update_one(key, {"$set": {"state": "cancelled"}})
            continue
        retry = False
        for channel in CHANNELS:
            if (row.get("channels") or {}).get(channel, {}).get("status") not in {None, "retry"}:
                continue
            # A02-BUG-005: record that this channel is in flight, so a crash is recovered per channel.
            if not events.update_one(key, {"$set": {f"channels.{channel}": {
                    "status": "sending", "providerId": None, "attemptedAt": now}}}).matched_count:
                break
            try:
                outcome, provider = deliver(db, row, channel)
            except requests.ConnectTimeout:
                outcome, provider = "retry", None
            except Exception:
                outcome, provider = "uncertain", None
            if outcome == "retry" and row["attempts"] >= 4:
                outcome = "failed"
            retry |= outcome == "retry"
            sent += int(channel == "inApp" and outcome == "stored")
            ack = events.update_one(key, {"$set": {f"channels.{channel}": {
                "status": outcome, "providerId": provider, "attemptedAt": now,
            }}, "$push": {"deliveryAttempts": {"channel": channel, "status": outcome, "at": now}}})
            if not ack.matched_count:
                break
        events.update_one(key, {"$set": {
            "state": "pending" if retry else "processed",
            "nextAttemptAt": now + timedelta(minutes=2 ** row["attempts"] if retry else 10),
        }})
    poll_sms(db, now)
    return sent


def recover_interrupted(events, now):
    """Recover events whose worker stopped while delivering (lease expired).

    A02-BUG-005: these events used to become "uncertain" as a whole, so a crash before the in-app write meant the
    patient never got the reminder. Now each channel is judged separately: a channel that never started is still
    delivered; the in-app channel is idempotent (unique key) and is re-run; an external channel that was in flight
    stays "uncertain" and is never sent again, because the provider may already have accepted it.
    """
    for row in events.find({"state": "sending", "leaseUntil": {"$lte": now}}).limit(100):
        sets = {}
        for channel, info in (row.get("channels") or {}).items():
            if (info or {}).get("status") == "sending":
                sets[f"channels.{channel}.status"] = None if channel == "inApp" else "uncertain"
        resumable = row.get("attempts", 0) < 4 and utc(row["expiresAt"]) > now
        sets.update(state="pending" if resumable else "uncertain", nextAttemptAt=now)
        events.update_one({"_id": row["_id"], "state": "sending", "leaseUntil": row["leaseUntil"]},
                          {"$set": sets, "$inc": {"recoveries": 1}})


def poll_sms(db, now):
    account, token, _ = twilio_config()
    if not account or not token:
        return
    events = db["care_reminder_events"]
    for _ in range(10):
        row = events.find_one_and_update(
            {"state": "processed", "nextAttemptAt": {"$lte": now},
             "channels.sms.status": {"$in": ["accepted", "sent"]},
             "scheduledAt": {"$gte": now - timedelta(days=7)}},
            {"$set": {"nextAttemptAt": now + timedelta(minutes=30)}},
        )
        if not row:
            return
        sid = row["channels"]["sms"].get("providerId")
        if not isinstance(sid, str) or len(sid) != 34 or not sid.startswith("SM") or not all(c in "0123456789abcdefABCDEF" for c in sid[2:]):
            continue
        try:
            response = requests.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{account}/Messages/{sid}.json",
                auth=(account, token), timeout=10,
            )
            if response.ok:
                events.update_one({"_id": row["_id"], "channels.sms.providerId": sid},
                                  {"$set": {"channels.sms.status": sms_status(response.json().get("status"))}})
        except (requests.RequestException, ValueError):
            continue
