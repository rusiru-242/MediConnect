"""Phase 4 tests with JWT-authenticated synthetic records and no external delivery."""
from concurrent.futures import ThreadPoolExecutor
import os
from datetime import date, timedelta
from unittest.mock import patch

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.notification import create_notification_indexes
from app.services.doctor_communications import run_communications
from app.services.doctor_service import get_sl_today_str
from tests.test_ai_booking_agent import seeded_booking_env

BASE = "/api/doctor/workflow"


@pytest.fixture(scope="module", autouse=True)
def isolated():
    from app.config.database import DatabaseManager
    original_db = DatabaseManager._db
    client = DatabaseManager.get_client()
    # R03-BUG-001: derived from the session database (which conftest guarantees is local and ends in _test),
    # so a fresh DATABASE_NAME gives a fresh module database. CI (mediconnect_test) keeps mediconnect_phase4_test.
    session_db = os.environ["DATABASE_NAME"]
    test_db = client[session_db[: -len("_test")] + "_phase4_test"]
    DatabaseManager._db = test_db
    assert get_database().name.endswith("_phase4_test") and get_database().name.startswith("mediconnect_")
    yield test_db
    DatabaseManager._db = original_db


@pytest.fixture
def clinic(seeded_booking_env):
    db = get_database()
    return db, seeded_booking_env, TestClient(app)


def token(seed, role="doctor"):
    return {"Authorization": f"Bearer {seed[f'token_{role}']}"}


def add_appointment(db, seed, day, status="CONFIRMED", **other):
    return str(db.appointments.insert_one({
        "doctorUserId": seed["doc_user_id"], "doctorProfileId": seed["doc_profile_id"],
        "patientUserId": seed["pat_a_id"], "appointmentDate": day, "startTime": "00:00",
        "endTime": "00:30", "status": status, **other,
    }).inserted_id)


def test_clinic_queue_preparation_and_analytics(clinic):
    db, seed, client = clinic
    day = get_sl_today_str()
    identifier = add_appointment(db, seed, day, patientNote="Reported reason")
    held = add_appointment(db, seed, day, status="HOLD")
    headers = token(seed)
    assert client.get(f"{BASE}/queue", headers=token(seed, "patient_a")).status_code == 403
    assert client.get(f"{BASE}/queue", headers=token(seed, "admin")).status_code == 403
    assert client.get(f"{BASE}/preparation/{held}", headers=headers).status_code == 404
    response = client.get(f"{BASE}/queue", headers=headers).json()
    assert {row["id"] for row in response["appointments"]} == {identifier}
    assert response["nextPatient"] is None

    def action(state, version, key):
        return client.post(f"{BASE}/queue/{identifier}", headers=headers, json={
            "action": state, "version": version, "requestId": key, "confirm": True,
        })

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda key: action("checked_in", 0, key).status_code, ["request-a", "request-b"]))
    assert sorted(statuses) == [200, 409]
    assistant = client.post(f"{BASE}/assistant", headers=headers, json={"message": "ada mage next patient kawda?"})
    assert assistant.json()["result"]["nextPatient"]["id"] == identifier
    assert action("in_consultation", 1, "request-c").status_code == 200

    db.medical_records.insert_one({
        "doctorUserId": seed["doc_user_id"], "patientUserId": seed["pat_a_id"],
        "clinicalNotes": "Clinician-authored fixture", "appointmentId": identifier,
    })
    db.medical_records.insert_one({
        "doctorUserId": str(ObjectId()), "patientUserId": seed["pat_a_id"],
        "clinicalNotes": "Unrelated doctor",
    })
    preparation = client.get(f"{BASE}/preparation/{identifier}", headers=headers).json()
    assert preparation["patientReportedReason"] == "Reported reason"
    assert [row["clinicalNotes"] for row in preparation["sources"]["priorRecords"]] == ["Clinician-authored fixture"]

    proposal = client.post(f"{BASE}/assistant", headers=headers, json={
        "message": "me patient ta weeks 2kin follow-up ekak set karanna", "appointmentId": identifier,
    }).json()
    assert proposal["followUpDate"] == (date.fromisoformat(day) + timedelta(days=14)).isoformat()
    assert db.care_plans.count_documents({"appointmentId": identifier}) == 0
    assert action("completed", 2, "request-d").status_code == 200
    assert action("completed", 2, "request-d").status_code == 200
    assert client.get(f"{BASE}/analytics", headers=headers).json()["completed"] == 1
    with patch("app.services.care_plan_service.NotificationService.create_notification"):
        plan = client.post("/api/care-plans", headers=headers, json={
            "appointmentId": identifier, "followUpDate": proposal["followUpDate"],
            "reason": "Clinician follow-up", "instructions": "Review the visit in two weeks.",
        })
    assert plan.status_code == 201, plan.json()
    assert db.care_plans.find_one({"appointmentId": identifier})["followUpDate"] == proposal["followUpDate"]
    follows = client.post(f"{BASE}/assistant", headers=headers, json={"message": "List my follow-ups"}).json()
    assert follows["result"]["followUps"][0]["appointmentId"] == identifier
    slots = client.post(f"{BASE}/assistant", headers=headers, json={"message": "heta mata free slots monawada?"}).json()
    assert slots["tool"] == "get_my_available_slots"
    assert slots["result"]["timezone"] == "Asia/Colombo"


def test_consented_preview_outbox_and_slot_conflict(clinic):
    db, seed, client = clinic
    day = (date.fromisoformat(get_sl_today_str()) + timedelta(days=1)).isoformat()
    identifier = add_appointment(db, seed, day)
    headers = token(seed)
    db.users.update_one({"_id": ObjectId(seed["pat_a_id"])}, {"$set": {"notificationPreferences.reminder24h": False}})
    path = f"{BASE}/reminders/{day}"
    assert client.get(path, headers=headers).json()["count"] == 0
    db.users.update_one({"_id": ObjectId(seed["pat_a_id"])}, {"$set": {"notificationPreferences.reminder24h": True}})
    draft = client.get(path, headers=headers).json()
    assert draft["count"] == 1
    assert client.post(path, headers=headers, json={"token": draft["token"], "confirm": False}).status_code == 422
    for _ in range(2):
        assert client.post(path, headers=headers, json={"token": draft["token"], "confirm": True}).status_code == 200
    create_notification_indexes(db)
    with patch("app.services.notification_service.NotificationService._send_fcm_push") as push:
        run_communications(db)
        run_communications(db)
        push.assert_not_called()
    assert db.notifications.count_documents({"relatedAppointmentId": identifier}) == 1
    assert client.get(path, headers=headers).json()["statuses"] == {"stored_in_app": 1}
    block = {"date": day, "startTime": "00:10", "endTime": "00:20", "confirm": True}
    assert client.post(f"{BASE}/blocked-time", headers=headers, json=block).status_code == 409
    db.appointments.update_one({"_id": ObjectId(identifier)}, {"$set": {"status": "CANCELLED"}})
    assert client.post(f"{BASE}/blocked-time", headers=headers, json=block).status_code == 201
