"""Authenticated patient care agenda, clinician approval, and patient-reported activity."""
from uuid import uuid4
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
import re

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pymongo import ReturnDocument

from app.config.database import get_database
from app.middleware.auth import require_doctor, require_patient
from app.services.appointment_service import _assert_doctor_approved_and_active
from app.services.booking_notifications import phone_fingerprint
from app.services import care_scheduler as scheduler

router = APIRouter(prefix="/care-automation", tags=["Patient care automation"])
Clock = Annotated[str, StringConstraints(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")]
Metric = Literal["blood_pressure", "blood_glucose", "weight", "temperature"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApproveSchedule(Input):
    medicationIndex: int = Field(ge=0)
    times: list[Clock] = Field(min_length=1, max_length=4)
    startDate: date
    endDate: date
    confirm: Literal[True]

    @field_validator("times")
    @classmethod
    def unique_times(cls, times):
        if len(times) != len(set(times)):
            raise ValueError("Enter one distinct time per scheduled dose.")
        return sorted(times)


class CareAction(Input):
    action: Literal["taken", "skipped", "snooze", "completed", "reset"]
    requestId: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{12,80}$")]
    snoozeMinutes: Literal[5, 10, 15, 30] = 15


class Preferences(Input):
    careReminders: bool
    reminder24h: bool
    reminder2h: bool
    careEmail: bool
    careSms: bool


class Reading(Input):
    metric: Metric
    value: float = Field(gt=0, le=1000)
    secondary: float | None = Field(default=None, gt=0, le=250)


class TrackingSchedule(Input):
    metric: Metric
    time: Clock
    enabled: bool = True


def owned_rx(db, doctor, identifier):
    _assert_doctor_approved_and_active(db, doctor)
    query = {"doctorUserId": str(doctor.id)}
    query.update({"_id": ObjectId(identifier)} if ObjectId.is_valid(identifier) else {"prescriptionId": identifier})
    rx = db["prescriptions"].find_one(query)
    if not rx:
        raise HTTPException(404, "Prescription not found.")
    return rx


def validate_approved_dates(req, item):
    frequencies = {
        "once daily": 1, "once a day": 1, "daily": 1, "od": 1,
        "twice daily": 2, "twice a day": 2, "bd": 2, "bid": 2,
        "three times daily": 3, "three times a day": 3, "tds": 3, "tid": 3,
        "four times daily": 4, "four times a day": 4, "qds": 4, "qid": 4,
    }
    count = frequencies.get(str(item.get("frequency", "")).strip().casefold())
    duration = re.fullmatch(r"([1-9][0-9]*)\s*(day|week)s?", str(item.get("duration", "")).strip().casefold())
    if count is None or not duration or not item.get("dose") or not item.get("medicationName"):
        raise HTTPException(422, "Clarify the prescription frequency, duration and dose before approving reminders.")
    days = int(duration[1]) * (7 if duration[2] == "week" else 1)
    if len(req.times) != count or not 1 <= (req.endDate - req.startDate).days + 1 <= min(days, 366):
        raise HTTPException(422, "Reminder times or dates conflict with the prescribed frequency or duration.")
    if req.endDate < datetime.now(scheduler.COLOMBO).date():
        raise HTTPException(422, "The schedule end date has already passed.")


@router.put("/prescriptions/{identifier}/schedule")
def approve_schedule(identifier: str, req: ApproveSchedule, doctor=Depends(require_doctor), db=Depends(get_database)):
    rx = owned_rx(db, doctor, identifier)
    items = rx.get("medicationItems") or []
    if rx.get("status") not in {"ISSUED", "AMENDED", "DISPENSED"} or req.medicationIndex >= len(items):
        raise HTTPException(409, "This medication cannot be scheduled.")
    item = items[req.medicationIndex]
    validate_approved_dates(req, item)
    now = datetime.now(timezone.utc)
    key = f"{rx['_id']}:{req.medicationIndex}"
    revision = scheduler.medication_revision(item, rx.get("instructions"))
    fields = {
        "patientUserId": rx["patientUserId"], "prescriptionDbId": str(rx["_id"]),
        "prescriptionId": rx["prescriptionId"], "prescriptionMedicationIndex": req.medicationIndex,
        **{k: item[k] for k in ("medicationName", "strength", "dose", "route", "frequency", "duration", "additionalInstructions") if k in item},
        "scheduledTimes": req.times, "patientTimezone": "Asia/Colombo",
        "startDate": scheduler.local_at(req.startDate, "00:00"),
        "endDate": scheduler.local_at(req.endDate + timedelta(days=1), "00:00"),
        "approvedBy": str(doctor.id), "prescriptionRevision": revision,
        "status": "ACTIVE", "enabled": True,
    }
    collection = db["medication_reminders"]
    previous = collection.find_one({"approvalKey": key})
    if previous and all(
        (scheduler.utc(previous[k]) if isinstance(previous.get(k), datetime) else previous.get(k)) == v
        for k, v in fields.items()
    ):
        return {"scheduleId": str(previous["_id"]), "status": "ACTIVE"}
    row = collection.find_one_and_update(
        {"approvalKey": key},
        {"$set": {**fields, "approvedAt": now, "updatedAt": now},
         "$setOnInsert": {"reminderId": f"REM-{ObjectId()}", "createdAt": now},
         "$inc": {"scheduleVersion": 1},
         "$push": {"approvalAudit": {"by": str(doctor.id), "at": now, "action": "approved"}}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    return {"scheduleId": str(row["_id"]), "status": row["status"]}


@router.delete("/prescriptions/{identifier}/schedule/{index}")
def discontinue_schedule(identifier: str, index: int, doctor=Depends(require_doctor), db=Depends(get_database)):
    rx = owned_rx(db, doctor, identifier)
    result = db["medication_reminders"].update_one(
        {"approvalKey": f"{rx['_id']}:{index}", "approvedBy": str(doctor.id), "status": "ACTIVE"},
        {"$set": {"enabled": False, "status": "CANCELLED", "updatedAt": datetime.now(timezone.utc)},
         "$push": {"approvalAudit": {"by": str(doctor.id), "at": datetime.now(timezone.utc), "action": "discontinued"}}},
    )
    if not result.matched_count:
        raise HTTPException(404, "Active approved schedule not found.")
    return {"status": "CANCELLED"}


@router.get("/prescriptions/{identifier}/activity")
def clinician_activity(identifier: str, doctor=Depends(require_doctor), db=Depends(get_database)):
    rx = owned_rx(db, doctor, identifier)
    ids = [str(r["_id"]) for r in db["medication_reminders"].find(
        {"prescriptionDbId": str(rx["_id"]), "approvedBy": str(doctor.id)}, {"_id": 1},
    )]
    rows = db["care_reminder_events"].find({
        "sourceCollection": "medication_reminders", "sourceId": {"$in": ids},
        "doctorUserId": str(doctor.id), "patientUserId": rx["patientUserId"], "audit.0": {"$exists": True},
    }).sort("scheduledAt", -1).limit(100)
    return [{"scheduledAt": row["scheduledAt"], "action": row.get("action"), "audit": row["audit"],
             "source": "patient_reported"} for row in rows]


@router.get("/plans/{identifier}/activity")
def plan_activity(identifier: str, doctor=Depends(require_doctor), db=Depends(get_database)):
    _assert_doctor_approved_and_active(db, doctor)
    if not ObjectId.is_valid(identifier):
        raise HTTPException(404, "Care plan not found.")
    plan = db["care_plans"].find_one({"_id": ObjectId(identifier), "doctorUserId": str(doctor.id)})
    if not plan:
        raise HTTPException(404, "Care plan not found.")
    rows = db["care_reminder_events"].find({
        "sourceCollection": "care_plans", "sourceId": identifier, "doctorUserId": str(doctor.id),
        "patientUserId": plan["patientUserId"], "audit.0": {"$exists": True},
    }).sort("scheduledAt", -1).limit(100)
    return [{"scheduledAt": row["scheduledAt"], "kind": row["kind"], "action": row.get("action"),
             "source": "patient_reported"} for row in rows]


def event_details(db, row, source=None):
    source = source or scheduler.current_source(db, row)
    if not source:
        raise HTTPException(410, "This reminder is no longer scheduled.")
    kind = row["kind"]
    result = {"id": row["_id"], "kind": kind, "scheduledAt": row["scheduledAt"],
              "action": row.get("action"), "snoozes": row.get("snoozes", 0),
              "source": "patient_entered" if row["sourceCollection"] == "care_tracking_schedules" else "clinician",
              "title": kind.replace("_", " ").title()}
    if kind == "medication":
        item = scheduler.approved_medication(db, source)
        if not item:
            raise HTTPException(410, "The prescription has changed.")
        result.update(title=item["medicationName"],
                      instructions=" · ".join(filter(None, (item.get("dose"), item.get("route"),
                                                              item.get("frequency"), item.get("additionalInstructions")))),
                      prescriptionId=source["prescriptionId"])
    elif kind == "appointment":
        result.update(appointmentId=row["sourceId"], title="Confirmed appointment")
    elif kind == "follow_up":
        result.update(title="Follow-up", instructions=source.get("instructions"), carePlanId=row["sourceId"])
        profile = source.get("doctorProfileId")
        if ObjectId.is_valid(profile):
            doctor = db["doctor_profiles"].find_one({"_id": ObjectId(profile)}, {"doctorId": 1})
            result["doctorId"] = doctor.get("doctorId") if doctor else None
        author = source.get("doctorUserId")
        if ObjectId.is_valid(author):
            doctor = db["users"].find_one({"_id": ObjectId(author)}, {"fullName": 1})
            result["doctorName"] = doctor.get("fullName") if doctor else None
    elif row.get("taskId"):
        task = next(task for task in source["tasks"] if task["taskId"] == row["taskId"])
        result.update(title=task["title"], instructions=task.get("description"), location=task.get("location"),
                      carePlanId=row["sourceId"])
    elif kind == "measurement":
        result["title"] = source["metric"].replace("_", " ").title()
    return result


def get_agenda(db, patient_id, day, days=1):
    start = scheduler.local_at(day, "00:00")
    end = scheduler.local_at(day + timedelta(days=days), "00:00")
    items, seen = [], set()
    for row in scheduler.rows(db, start - timedelta(hours=24), end, patient_id):
        if not start <= row["scheduledAt"] < end:
            continue
        identity = (row["kind"], row["sourceId"], row["scheduledAt"], row["taskId"])
        if identity in seen:
            continue
        seen.add(identity)
        saved = db["care_reminder_events"].find_one({"_id": row["_id"]}) or row
        try:
            items.append(event_details(db, saved))
        except HTTPException as exc:
            if exc.status_code != 410:
                raise
    return sorted(items, key=lambda item: item["scheduledAt"])


@router.get("/agenda")
def agenda(day: date | None = None, days: int = Query(1, ge=1, le=7),
           patient=Depends(require_patient), db=Depends(get_database)):
    return {"items": get_agenda(db, str(patient.id), day or datetime.now(scheduler.COLOMBO).date(), days)}


def find_event(db, identifier, patient_id):
    row = db["care_reminder_events"].find_one({"_id": identifier, "patientUserId": patient_id})
    if row:
        return row
    now = datetime.now(timezone.utc)
    candidate = next((row for row in scheduler.rows(db, now - timedelta(days=2), now + timedelta(days=8), patient_id)
                      if row["_id"] == identifier), None)
    if not candidate:
        raise HTTPException(404, "Reminder not found.")
    scheduler.materialize(db, candidate)
    return db["care_reminder_events"].find_one({"_id": identifier, "patientUserId": patient_id})


@router.get("/events/{identifier}")
def reminder_detail(identifier: str, patient=Depends(require_patient), db=Depends(get_database)):
    return event_details(db, find_event(db, identifier, str(patient.id)))


@router.post("/events/{identifier}/actions")
def record_action(identifier: str, req: CareAction, patient=Depends(require_patient), db=Depends(get_database)):
    patient_id = str(patient.id)
    row = find_event(db, identifier, patient_id)
    source = scheduler.current_source(db, row)
    if not source:
        raise HTTPException(410, "This reminder is no longer scheduled.")
    if any(entry["requestId"] == req.requestId for entry in row.get("audit", [])):
        return event_details(db, row, source)
    allowed = {"taken", "skipped", "reset", "snooze"} if row["kind"] == "medication" else {"completed", "reset"}
    if row["kind"] == "appointment" or req.action not in allowed:
        raise HTTPException(422, "That action is unavailable for this task.")
    now = datetime.now(timezone.utc)
    if row["kind"] == "medication" and now < scheduler.utc(row["scheduledAt"]):
        raise HTTPException(409, "This medication occurrence is in the future.")
    updates = {"action": None if req.action == "reset" else req.action}
    if req.action == "snooze":
        when = now + timedelta(minutes=req.snoozeMinutes)
        if row.get("snoozes", 0) >= 2 or when >= scheduler.utc(row["expiresAt"]):
            raise HTTPException(409, "This reminder can no longer be snoozed.")
        if row.get("action") in {"taken", "skipped"}:
            raise HTTPException(409, "Correct the previous action before snoozing.")
        updates.update(state="pending", nextAttemptAt=when, channels={}, attempts=0)
    elif req.action == "reset":
        original_due = scheduler.utc(row["dueAt"])
        if original_due > now and not row.get("channels"):
            updates.update(state="pending", nextAttemptAt=original_due)
        else:
            updates["state"] = "processed"
    else:
        updates["state"] = "processed"
    operations = {"$set": updates, "$push": {"audit": {
        "action": req.action, "requestId": req.requestId, "at": now,
    }}, "$inc": {"actionVersion": 1}}
    if req.action == "snooze":
        operations["$inc"]["snoozes"] = 1
    updated = db["care_reminder_events"].find_one_and_update({
        "_id": identifier, "patientUserId": patient_id,
        "actionVersion": row.get("actionVersion", {"$exists": False}),
        "audit.requestId": {"$ne": req.requestId},
    }, operations, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(409, "The task changed. Refresh and retry.")
    return event_details(db, updated, source)


@router.get("/preferences")
def get_preferences(patient=Depends(require_patient), db=Depends(get_database)):
    user = db["users"].find_one({"_id": ObjectId(str(patient.id))}, {"notificationPreferences": 1}) or {}
    prefs = user.get("notificationPreferences") or {}
    return {key: prefs.get(key, prefs.get("reminder1h", True) if key == "reminder2h"
                           else key not in {"careEmail", "careSms"}) for key in Preferences.model_fields}


@router.put("/preferences")
def update_preferences(req: Preferences, patient=Depends(require_patient), db=Depends(get_database)):
    query = {"_id": ObjectId(str(patient.id))}
    user = db["users"].find_one(query, {"phone": 1, "emailVerified": 1}) or {}
    phone_hash = phone_fingerprint(user.get("phone")) if req.careSms else None
    if req.careSms and not phone_hash or req.careEmail and not user.get("emailVerified"):
        raise HTTPException(422, "Add a valid mobile number or verify your email in your account first.")
    db["users"].update_one(query, {"$set": {f"notificationPreferences.{key}": value for key, value in
                                          {**req.model_dump(), "careSmsPhoneHash": phone_hash}.items()}})
    return req


MEASUREMENTS = {
    "blood_pressure": ("mmHg", 300), "blood_glucose": ("mg/dL", 1000),
    "weight": ("kg", 500), "temperature": ("°C", 50),
}


@router.post("/measurements", status_code=201)
def record_measurement(req: Reading, patient=Depends(require_patient), db=Depends(get_database)):
    unit, maximum = MEASUREMENTS[req.metric]
    pressure = req.metric == "blood_pressure"
    if (req.value > maximum or (req.secondary is not None) != pressure
        or pressure and req.secondary >= req.value or req.metric == "temperature" and req.value < 25):
        raise HTTPException(422, "Enter a valid reading in the units shown.")
    # Same alert rules as Health Tracking (/clinical/measurements), so a concerning reading entered from the
    # Care Agenda is not silently stored (P02-N09). Thresholds are existing rules pending clinical review.
    from app.services.clinical_safety_service import ClinicalSafetyService
    alert = ClinicalSafetyService.evaluate_measurement_safety(req.metric, req.value, req.secondary)
    now = datetime.now(timezone.utc)
    # B7 (Phase 05): new Care Agenda readings carry the same identifying fields as Health Tracking readings.
    row = {**req.model_dump(), "patientUserId": str(patient.id), "unit": unit,
           "recordedAt": now, "measuredAt": now, "measurementId": f"MEAS-{now:%Y%m%d}-{uuid4().hex[:6].upper()}",
           "verificationStatus": "unverified", "entryPoint": "care_agenda",
           "source": "patient_reported", "criticalAlert": alert}
    db["patient_health_measurements"].insert_one(row)
    return {"id": str(row["_id"]), "source": row["source"], "unit": unit, "criticalAlert": alert}


@router.get("/measurements")
def list_measurements(patient=Depends(require_patient), db=Depends(get_database)):
    result = db["patient_health_measurements"].find(
        {"patientUserId": str(patient.id)}, {"_id": 0, "patientUserId": 0},
    ).sort("recordedAt", -1).limit(50)
    return {"items": list(result)}


@router.put("/tracking-schedule")
def set_tracking_schedule(req: TrackingSchedule, patient=Depends(require_patient), db=Depends(get_database)):
    identifier = f"{patient.id}:{req.metric}"
    collection = db["care_tracking_schedules"]
    previous = collection.find_one({"_id": identifier})
    if not previous or previous["clock"] != req.time or previous["enabled"] != req.enabled:
        collection.update_one({"_id": identifier}, {"$set": {
            "patientUserId": str(patient.id), "metric": req.metric, "clock": req.time,
            "enabled": req.enabled, "createdAt": datetime.now(timezone.utc),
        }, "$inc": {"scheduleVersion": 1}}, upsert=True)
    return {"enabled": req.enabled, "timezone": "Asia/Colombo"}
