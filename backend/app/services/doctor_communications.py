"""Doctor-approved, consented in-app appointment reminders."""
from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

from app.models.appointment import utc_now
from app.models.notification import NotificationType
from app.services.consultation_service import ConsultationService
from app.services.notification_service import NotificationService
from app.services.doctor_service import SL_TIMEZONE

TITLE = "Appointment reminder"
BODY = "You have an upcoming MediConnect appointment. Open the app to review the details."


def create_indexes(db):
    db.doctor_communication_events.create_index([("status", 1), ("nextAttemptAt", 1)])
    db.doctor_communication_events.create_index([("doctorUserId", 1), ("date", -1)])


def consent(db, patient_id):
    user = db.users.find_one({"_id": ObjectId(patient_id)}, {"notificationPreferences": 1}) if ObjectId.is_valid(patient_id) else None
    return bool(user and (user.get("notificationPreferences") or {}).get("reminder24h") is True)


def preview(db, doctor, day):
    ConsultationService._verify_approved_doctor(db, doctor)
    now = utc_now().astimezone(SL_TIMEZONE)
    timing = {"startTime": {"$gt": now.strftime("%H:%M")}} if day == now.date() else {}
    rows = list(db.appointments.find({
        "doctorUserId": str(doctor.id), "appointmentDate": day.isoformat(), "status": "CONFIRMED", **timing,
    }, {"patientUserId": 1, "appointmentVersion": 1}).sort("_id", 1).limit(51))
    if len(rows) > 50:
        raise HTTPException(422, "This reminder batch exceeds 50 appointments.")
    return [{"id": str(row["_id"]), "version": row.get("appointmentVersion", 1)}
            for row in rows if consent(db, row["patientUserId"])]


def batch_status(db, doctor, day):
    ConsultationService._verify_approved_doctor(db, doctor)
    rows = db.doctor_communication_events.aggregate([
        {"$match": {"doctorUserId": str(doctor.id), "date": day.isoformat()}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ])
    return {row["_id"]: row["count"] for row in rows}


def queue_batch(db, doctor, day, recipients):
    if preview(db, doctor, day) != recipients:
        raise HTTPException(409, "The recipient list changed. Preview the draft again.")
    for entry in recipients:
        identifier = f"appointment-reminder:{entry['id']}:{entry['version']}"
        db.doctor_communication_events.update_one({"_id": identifier}, {"$setOnInsert": {
            "doctorUserId": str(doctor.id), "date": day.isoformat(), "appointmentId": entry["id"],
            "appointmentVersion": entry["version"], "approvedAt": utc_now(), "status": "pending",
            "nextAttemptAt": utc_now(), "attempts": 0,
        }}, upsert=True)
    return batch_status(db, doctor, day)


def run_communications(db):
    coll = db.doctor_communication_events
    for _ in range(25):
        now = utc_now()
        row = coll.find_one_and_update({"$or": [
            {"status": "pending", "nextAttemptAt": {"$lte": now}},
            {"status": "processing", "leaseUntil": {"$lte": now}},
        ]}, {"$set": {"status": "processing", "leaseUntil": now + timedelta(minutes=2)},
             "$inc": {"attempts": 1}}, return_document=ReturnDocument.AFTER)
        if row is None:
            break
        status = "skipped"
        appt = db.appointments.find_one({"_id": ObjectId(row["appointmentId"]), "doctorUserId": row["doctorUserId"],
                                          "appointmentDate": row["date"], "status": "CONFIRMED"})
        if (appt and appt.get("appointmentVersion", 1) == row["appointmentVersion"]
            and datetime.fromisoformat(f"{row['date']}T{appt['startTime']}").replace(tzinfo=SL_TIMEZONE) > now
            and consent(db, appt["patientUserId"])):
            result = NotificationService.create_notification(
                db, appt["patientUserId"], NotificationType.SYSTEM, TITLE, BODY,
                related_appointment_id=row["appointmentId"], idempotency_key=row["_id"], send_push=False,
            )
            status = "stored_in_app" if result else "pending" if row["attempts"] < 5 else "failed"
        coll.update_one({"_id": row["_id"], "status": "processing", "attempts": row["attempts"]}, {
            "$set": {"status": status, "updatedAt": now, "nextAttemptAt": now + timedelta(minutes=2 ** min(row["attempts"], 5))},
        })
