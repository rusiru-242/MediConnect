"""Phase 3 integration tests use isolated MongoDB records and mocked channels."""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.services import care_scheduler as scheduler
from tests.test_ai_booking_agent import seeded_booking_env


@pytest.fixture(scope="module", autouse=True)
def isolated_database():
    assert get_database().name.startswith("mediconnect_phase3_test")


@pytest.fixture
def fixture(seeded_booking_env, monkeypatch):
    db = get_database()
    scheduler.create_indexes(db)
    push = Mock(return_value="accepted")
    monkeypatch.setattr(scheduler.NotificationService, "_send_fcm_push", push)
    monkeypatch.setattr(scheduler.EmailService, "_send_email", Mock(side_effect=AssertionError("unexpected SMTP")))
    monkeypatch.setattr(scheduler, "twilio_config", lambda: ("", "", ""))
    return db, seeded_booking_env, TestClient(app), push


def header(seed, role="patient_a"):
    return {"Authorization": f"Bearer {seed['token_' + role]}"}


def test_medication_approval_delivery_explicit_actions_and_prescription_change(fixture):
    db, seed, client, push = fixture
    now = datetime.now(timezone.utc)
    local = (now - timedelta(minutes=5)).astimezone(scheduler.COLOMBO)
    item = {"medicationName": "Fixture Medicine", "strength": "Fixture strength",
            "dose": "Clinician dose", "frequency": "Once daily", "duration": "1 day", "route": "Oral"}
    rx = db["prescriptions"].insert_one({
        "prescriptionId": f"RX-{ObjectId()}", "patientUserId": seed["pat_a_id"],
        "doctorUserId": seed["doc_user_id"], "status": "ISSUED", "medicationItems": [item],
    }).inserted_id
    path = f"/api/care-automation/prescriptions/{rx}"
    date = local.date().isoformat()
    request = {"medicationIndex": 0, "times": [local.strftime("%H:%M")],
               "startDate": date, "endDate": date, "confirm": True}
    assert client.put(f"{path}/schedule", headers=header(seed), json=request).status_code == 403
    assert client.put(f"{path}/schedule", headers=header(seed, "doctor"),
                      json={**request, "times": ["08:00", "20:00"]}).status_code == 422
    approved = client.put(f"{path}/schedule", headers=header(seed, "doctor"), json=request)
    assert approved.status_code == 200, approved.text
    repeat = client.put(f"{path}/schedule", headers=header(seed, "doctor"), json=request)
    assert repeat.json()["scheduleId"] == approved.json()["scheduleId"]

    scheduler.run_scheduler(db, now)
    scheduler.run_scheduler(db, now + timedelta(seconds=30))
    rows = list(db["care_reminder_events"].find({"sourceId": approved.json()["scheduleId"]}))
    assert len(rows) == 1
    row = rows[0]
    assert row["channels"]["inApp"]["status"] == "stored"
    assert row["channels"]["push"]["status"] == "accepted"
    assert row["channels"]["sms"]["status"] == "skipped"
    assert push.call_count == 1
    assert "Fixture Medicine" not in str(push.call_args)
    assert "Clinician dose" not in str(push.call_args)
    notice = db["notifications"].find_one({"relatedCareEventId": row["_id"]})
    assert notice and "Fixture Medicine" not in notice["body"]

    detail = f"/api/care-automation/events/{row['_id']}"
    assert client.get(detail, headers=header(seed, "patient_b")).status_code == 404
    response = client.get(detail, headers=header(seed))
    assert response.status_code == 200
    assert "Clinician dose" in response.json()["instructions"]
    for action in ("snooze", "taken", "reset", "skipped"):
        payload = {"action": action, "requestId": str(ObjectId())}
        response = client.post(f"{detail}/actions", headers=header(seed), json=payload)
        assert response.status_code == 200, response.text
        assert client.post(f"{detail}/actions", headers=header(seed), json=payload).status_code == 200
    assert len(db["care_reminder_events"].find_one({"_id": row["_id"]})["audit"]) == 4
    audit = client.get(f"{path}/activity", headers=header(seed, "doctor")).json()
    assert audit[0]["source"] == "patient_reported"

    db["prescriptions"].update_one({"_id": rx}, {"$set": {"medicationItems.0.dose": "Amended dose"}})
    assert client.get(detail, headers=header(seed)).status_code == 410
    assert client.delete(f"{path}/schedule/0", headers=header(seed, "doctor")).status_code == 200


def appointment_fields(seed, when, state="CONFIRMED"):
    local = when.astimezone(scheduler.COLOMBO)
    return {"patientUserId": seed["pat_a_id"], "doctorUserId": seed["doc_user_id"],
            "doctorProfileId": seed["doc_profile_id"], "appointmentDate": local.date().isoformat(),
            "startTime": local.strftime("%H:%M"), "status": state, "appointmentVersion": 1}


def test_appointment_reschedule_cancellation_and_hold(fixture):
    db, seed, _, _ = fixture
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    at = now + timedelta(hours=2)
    first = db["appointments"].insert_one(appointment_fields(seed, at)).inserted_id
    held = db["appointments"].insert_one(appointment_fields(seed, at, "HOLD")).inserted_id
    cancelled = db["appointments"].insert_one(appointment_fields(seed, at, "CANCELLED")).inserted_id
    candidates = list(scheduler.rows(db, now, now + timedelta(seconds=1), seed["pat_a_id"]))
    row = next(item for item in candidates if item["sourceId"] == str(first))
    assert not {str(held), str(cancelled)} & {item["sourceId"] for item in candidates}
    scheduler.materialize(db, row)
    # Reschedule before dispatch; an already persisted job must be invalidated.
    later = at + timedelta(hours=1)
    db["appointments"].update_one({"_id": first}, {"$set": {
        **appointment_fields(seed, later), "appointmentVersion": 2,
    }})
    scheduler.run_scheduler(db, now)
    assert db["care_reminder_events"].find_one({"_id": row["_id"]})["state"] == "cancelled"
    scheduler.run_scheduler(db, now + timedelta(hours=1))
    refreshed = db["care_reminder_events"].find_one({"sourceId": str(first), "state": "processed"})
    assert refreshed is not None and refreshed["_id"] != row["_id"]


def test_clinician_tasks_and_private_romanized_agenda(fixture):
    db, seed, client, _ = fixture
    now = datetime.now(timezone.utc)
    today = now.astimezone(scheduler.COLOMBO).date()
    confirmed = db["appointments"].insert_one(appointment_fields(seed, now, "COMPLETED")).inserted_id
    request = {
        "appointmentId": str(confirmed), "followUpDate": today.isoformat(),
        "reason": "Fixture review", "instructions": "Clinician-approved follow-up instructions.",
        "tasks": [{"title": "Fixture blood test", "kind": "test", "dueAt": now.isoformat(),
                   "location": "Fixture laboratory"}],
    }
    assert client.post("/api/care-plans", headers=header(seed), json=request).status_code == 403
    created = client.post("/api/care-plans", headers=header(seed, "doctor"), json=request)
    assert created.status_code == 201, created.text
    patient = header(seed)
    agenda = client.get("/api/care-automation/agenda", headers=patient).json()["items"]
    test = next(item for item in agenda if item["title"] == "Fixture blood test")
    assert test.get("instructions") is None
    assert any(item["kind"] == "follow_up" for item in agenda)
    completion = client.post(f"/api/care-automation/events/{test['id']}/actions",
                             headers=patient, json={"action": "completed", "requestId": str(ObjectId())})
    assert completion.status_code == 200
    session = client.post("/api/ai/conversations", headers=patient, json={}).json()
    response = client.post(f"/api/ai/conversations/{session['id']}/messages", headers=patient,
                           json={"message": "ada mata karanna thiyena dewal monawada?", "requestId": str(ObjectId())})
    assert response.status_code == 200, response.text
    reply = response.json()["messages"][-1]["content"]
    assert "Fixture blood test" in reply and "patient-reported" in reply
    assert "fast" not in reply.lower()

    different = client.get("/api/care-automation/agenda", headers=header(seed, "patient_b")).json()["items"]
    assert all(item["title"] != "Fixture blood test" for item in different)
    assert client.put(f"/api/care-plans/{created.json()['id']}", headers=header(seed, "doctor"),
                      json={"tasks": []}).status_code == 200
    assert client.get(f"/api/care-automation/events/{test['id']}", headers=patient).status_code == 410


def test_tracking_ownership_and_reminder_preferences(fixture):
    db, seed, client, _ = fixture
    path = "/api/care-automation"
    owner, other = header(seed), header(seed, "patient_b")
    assert client.post(f"{path}/measurements", headers=owner,
                       json={"metric": "blood_pressure", "value": 85, "secondary": 110}).status_code == 422
    assert client.post(f"{path}/measurements", headers=owner,
                       json={"metric": "blood_pressure", "value": 118, "secondary": 76}).status_code == 201
    assert client.get(f"{path}/measurements", headers=owner).json()["items"][0]["source"] == "patient_reported"
    assert client.get(f"{path}/measurements", headers=other).json()["items"] == []
    preferences = client.get(f"{path}/preferences", headers=owner).json()
    assert not preferences["careEmail"] and not preferences["careSms"]
    db["users"].update_one({"_id": ObjectId(seed["pat_a_id"])}, {"$set": {"phone": "not-valid"}})
    assert client.put(f"{path}/preferences", headers=owner, json={**preferences, "careSms": True}).status_code == 422
    assert client.put(f"{path}/tracking-schedule", headers=owner,
                      json={"metric": "weight", "time": "08:00", "enabled": True}).status_code == 200
    assert client.put(f"{path}/tracking-schedule", headers=owner,
                      json={"metric": "weight", "time": "08:00", "enabled": False}).status_code == 200

def test_channel_retry_does_not_resend_accepted_push(fixture, monkeypatch):
    db, seed, _, _ = fixture
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    identifier = db["appointments"].insert_one(appointment_fields(seed, now + timedelta(hours=2))).inserted_id
    row = next(candidate for candidate in scheduler.rows(db, now, now + timedelta(seconds=1), seed["pat_a_id"])
               if candidate["sourceId"] == str(identifier))
    scheduler.materialize(db, row)
    attempts = []

    def send(database, queued, channel):
        if queued["_id"] == row["_id"]:
            attempts.append(channel)
            if channel == "inApp" and attempts.count("inApp") == 1:
                return "retry", None
        return "accepted", None

    monkeypatch.setattr(scheduler, "deliver", send)
    scheduler.run_scheduler(db, now)
    assert db["care_reminder_events"].find_one({"_id": row["_id"]})["state"] == "pending"
    scheduler.run_scheduler(db, now + timedelta(minutes=2))
    assert attempts.count("inApp") == 2
    assert attempts.count("push") == 1
    assert db["care_reminder_events"].find_one({"_id": row["_id"]})["state"] == "processed"
