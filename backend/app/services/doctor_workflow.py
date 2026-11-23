"""Doctor workflow reads and appointment-embedded queue transitions."""
from datetime import datetime, timedelta
from statistics import median

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

from app.models.appointment import utc_now
from app.services.consultation_service import ConsultationService
from app.services.doctor_service import SL_TIMEZONE, get_sl_today_str

VISIBLE = ["CONFIRMED", "COMPLETED", "CANCELLED"]
TRANSITIONS = {
    "scheduled": ["checked_in", "no_show"],
    "checked_in": ["waiting", "in_consultation", "no_show"],
    "waiting": ["in_consultation", "no_show"],
    "in_consultation": ["completed"],
}


def owned_appointment(db, user, identifier):
    ConsultationService._verify_approved_doctor(db, user)
    row = db.appointments.find_one({
        "_id": ObjectId(identifier), "doctorUserId": str(user.id), "status": {"$in": VISIBLE},
    }) if ObjectId.is_valid(identifier) else None
    if not row:
        raise HTTPException(404, "Appointment unavailable.")
    return row


def queue_data(row):
    queue = row.get("clinicQueue") or {}
    if queue.get("date") != row["appointmentDate"] or queue.get("appointmentVersion") != row.get("appointmentVersion", 1):
        return {}
    return queue


def queue_status(row, session=None):
    if row["status"] in {"CANCELLED", "COMPLETED"}:
        return row["status"].lower()
    if session and session.get("status") == "IN_PROGRESS":
        return "in_consultation"
    return queue_data(row).get("status", "scheduled")


def appointment_view(row, names, sessions):
    identifier = str(row["_id"])
    queue = queue_data(row)
    return {
        "id": identifier, "patientName": names.get(row["patientUserId"]), "date": row["appointmentDate"],
        "time": row["startTime"], "status": row["status"], "queueStatus": queue_status(row, sessions.get(identifier)),
        "queueVersion": queue.get("version", 0), "checkedInAt": queue.get("checkedInAt"),
        "position": queue.get("position"), "location": row.get("consultationLocation"),
    }


def schedule(db, user, start, end):
    ConsultationService._verify_approved_doctor(db, user)
    if not 0 <= (end - start).days <= 30:
        raise HTTPException(422, "Select a date range of up to 31 days.")
    rows = list(db.appointments.find({
        "doctorUserId": str(user.id), "appointmentDate": {"$gte": start.isoformat(), "$lte": end.isoformat()},
        "status": {"$in": VISIBLE},
    }, {"patientUserId": 1, "appointmentDate": 1, "startTime": 1, "status": 1,
        "clinicQueue": 1, "appointmentVersion": 1, "consultationLocation": 1}).sort([
            ("appointmentDate", 1), ("startTime", 1), ("_id", 1)]))
    ids = {ObjectId(row["patientUserId"]) for row in rows if ObjectId.is_valid(row.get("patientUserId"))}
    names = {str(row["_id"]): row.get("fullName") for row in db.users.find({"_id": {"$in": list(ids)}}, {"fullName": 1})}
    sessions = {row["appointmentId"]: row for row in db.consultation_sessions.find({
        "appointmentId": {"$in": [str(row["_id"]) for row in rows]}, "doctorUserId": str(user.id),
    }, {"appointmentId": 1, "status": 1})}
    return [appointment_view(row, names, sessions) for row in rows]


def patient_queue(db, user, day):
    rows = schedule(db, user, day, day)
    waiting = sorted(
        (row for row in rows if row["queueStatus"] in {"waiting", "checked_in"}),
        key=lambda row: (row["position"] if row["position"] is not None else 1001,
                         str(row["checkedInAt"] or ""), row["time"], row["id"]),
    )
    durations = measured_durations(db, user, day - timedelta(days=30), day)
    active = [row for row in rows if row["queueStatus"] == "in_consultation"]
    for index, row in enumerate(waiting):
        row["queueOrder"] = index + 1
        if len(durations) >= 5:
            row["estimatedWaitMinutes"] = round(median(durations) * (len(active) + index))
    return {"appointments": rows, "nextPatient": waiting[0] if waiting else None}


def measured_durations(db, user, start, end):
    lower = datetime.combine(start, datetime.min.time(), SL_TIMEZONE)
    upper = datetime.combine(end + timedelta(days=1), datetime.min.time(), SL_TIMEZONE)
    rows = db.consultation_sessions.find({
        "doctorUserId": str(user.id), "status": "COMPLETED",
        "completedAt": {"$gte": lower, "$lt": upper}, "startedAt": {"$type": "date"},
    }, {"startedAt": 1, "completedAt": 1, "appointmentId": 1})
    durations = {}
    for row in rows:
        minutes = (row["completedAt"] - row["startedAt"]).total_seconds() / 60
        if 0 < minutes <= 480:
            durations[row["appointmentId"]] = minutes
    for row in db.appointments.find({
        "doctorUserId": str(user.id), "status": "COMPLETED",
        "clinicQueue.completedAt": {"$gte": lower, "$lt": upper},
        "clinicQueue.startedAt": {"$type": "date"},
    }, {"clinicQueue": 1, "appointmentVersion": 1, "appointmentDate": 1}):
        queue = queue_data(row)
        if queue and str(row["_id"]) not in durations:
            minutes = (queue["completedAt"] - queue["startedAt"]).total_seconds() / 60
            if 0 < minutes <= 480:
                durations[str(row["_id"])] = minutes
    return list(durations.values())


def change_queue(db, user, identifier, req):
    row = owned_appointment(db, user, identifier)
    queue = queue_data(row)
    if any(entry["requestId"] == req.requestId for entry in row.get("clinicQueueAudit", [])):
        return {"status": queue_status(row), "version": queue.get("version", 0)}
    if row["appointmentDate"] != get_sl_today_str() or row["status"] != "CONFIRMED":
        raise HTTPException(409, "Queue actions require a confirmed appointment scheduled for today.")
    session = db.consultation_sessions.find_one({"appointmentId": identifier, "doctorUserId": str(user.id)})
    current = queue_status(row, session)
    allowed = req.action in TRANSITIONS.get(current, [])
    if req.action == "reorder":
        allowed = current in {"checked_in", "waiting"} and req.position is not None
    if not allowed or req.version != queue.get("version", 0):
        raise HTTPException(409, "Queue state changed. Refresh and try again.")
    now = utc_now()
    if req.action == "no_show":
        slot = datetime.fromisoformat(f"{row['appointmentDate']}T{row['startTime']}").replace(tzinfo=SL_TIMEZONE)
        if slot > now:
            raise HTTPException(409, "No-show can be recorded after the appointment starts.")
    next_status = current if req.action == "reorder" else req.action
    updated = {**queue, "status": next_status, "version": req.version + 1,
               "date": row["appointmentDate"], "appointmentVersion": row.get("appointmentVersion", 1)}
    if req.action == "checked_in":
        updated["checkedInAt"] = now
    if req.action == "reorder":
        updated["position"] = req.position
    changes = {"clinicQueue": updated}
    if next_status == "completed":
        changes.update(status="COMPLETED", updatedAt=now)
    for field, state in (("startedAt", "in_consultation"), ("completedAt", "completed")):
        if req.action == state:
            updated[field] = now
    result = db.appointments.find_one_and_update({
        "_id": row["_id"], "doctorUserId": str(user.id), "status": "CONFIRMED",
        "appointmentDate": row["appointmentDate"],
        "appointmentVersion": row.get("appointmentVersion", {"$exists": False}),
        "clinicQueue": row.get("clinicQueue", {"$exists": False}),
        "clinicQueueAudit.requestId": {"$ne": req.requestId},
    }, {"$set": changes, "$push": {"clinicQueueAudit": {"$each": [{
        "at": now, "action": req.action, "doctorUserId": str(user.id), "requestId": req.requestId,
    }], "$slice": -100}}}, return_document=ReturnDocument.AFTER)
    if not result:
        raise HTTPException(409, "Queue state changed. Refresh and try again.")
    return {"status": queue_status(result), "version": updated["version"]}


def analytics(db, user, start, end):
    rows = schedule(db, user, start, end)
    durations = measured_durations(db, user, start, end)
    return {"from": start.isoformat(), "to": end.isoformat(), "total": len(rows),
            "completed": sum(r["status"] == "COMPLETED" for r in rows),
            "cancelled": sum(r["status"] == "CANCELLED" for r in rows),
            "noShow": sum(r["queueStatus"] == "no_show" for r in rows),
            "waiting": sum(r["queueStatus"] in {"checked_in", "waiting"} for r in rows),
            "averageMeasuredMinutes": round(sum(durations) / len(durations), 1) if durations else None,
            "measuredConsultations": len(durations)}


def preparation(db, user, identifier):
    appt = owned_appointment(db, user, identifier)
    if appt["status"] == "CANCELLED":
        raise HTTPException(404, "Appointment unavailable.")
    patient_id = appt["patientUserId"]
    patient = db.users.find_one({"_id": ObjectId(patient_id)}, {"fullName": 1}) if ObjectId.is_valid(patient_id) else None
    scope = {"patientUserId": patient_id, "doctorUserId": str(user.id)}
    sources = {}
    for label, collection, fields in (
        ("priorRecords", "medical_records", ("recordId", "chiefComplaint", "assessment", "clinicalNotes", "allergies")),
        ("prescriptions", "prescriptions", ("prescriptionId", "medications", "status")),
        ("followUps", "care_plans", ("carePlanId", "followUpDate", "instructions", "status")),
    ):
        sources[label] = []
        for row in db[collection].find(scope, {field: 1 for field in (*fields, "createdAt", "appointmentId")}).sort("createdAt", -1).limit(5):
            row["reference"] = str(row.pop("_id"))
            sources[label].append(row)
    return {"label": "Assistant-generated preparation draft. Verify against source records.",
            "appointment": appointment_view(appt, {patient_id: (patient or {}).get("fullName")}, {}),
            "patientReportedReason": appt.get("patientNote"), "sources": sources,
            "summary": (f"Found {len(sources['priorRecords'])} clinician records, "
                        f"{len(sources['prescriptions'])} prescription records and {len(sources['followUps'])} follow-up plans. "
                        "Current medication use, allergies and test results require source verification.")}


def follow_ups(db, user):
    ConsultationService._verify_approved_doctor(db, user)
    rows = db.care_plans.find({"doctorUserId": str(user.id)}, {
        "appointmentId": 1, "followUpDate": 1, "status": 1,
    }).sort("followUpDate", -1).limit(30)
    return [{"id": str(row.pop("_id")), **row} for row in rows]
