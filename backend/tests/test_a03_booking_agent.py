"""Agent Completion A03: AI booking conversation memory and read-only appointment management (Agent 01).

Deterministic provider (no live AI). Doctors are synthetic cardiologists in Batticaloa, a city no other test uses.
A03-BUG-010 (selected doctor kept), 011 (other times on the same date), 012 (cancel/reschedule an existing
appointment is never done by the chat), 013 (Romanized Sinhala time words). A03-A12: no chat turn creates a hold.
"""
from datetime import datetime, timedelta
import time
from unittest.mock import patch

from bson import ObjectId
import pytest

from app.agents.ai_provider import DeterministicNLPProvider
from app.agents.booking_agent import manage_existing_request, other_time_request
from app.agents.nlp_parser import extract_time_range
from app.models.appointment import utc_now
from app.models.doctor_availability import DoctorAvailabilityDocument
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.review import get_review_collection
from app.models.user import AccountStatus, UserRole
from app.routes.ai_booking import _RATE_LIMIT_BUCKET
from app.services.appointment_service import SL_TIMEZONE
from app.utils.security import create_access_token
from tests.test_payment import client, db  # noqa: F401


@pytest.fixture(autouse=True)
def deterministic_provider():
    _RATE_LIMIT_BUCKET.clear()
    with patch("app.agents.booking_agent.get_ai_provider", return_value=DeterministicNLPProvider()):
        yield


@pytest.fixture(scope="module")
def env(db):
    ts = int(time.time() * 1000)
    created_users, created_profiles = [], []

    def doctor(name, fee, years, ratings):
        uid, pid = ObjectId(), ObjectId()
        db["users"].insert_one({"_id": uid, "fullName": name, "email": f"a03_{uid}@mediconnect.lk", "passwordHash": "x",
                                "role": UserRole.DOCTOR.value, "emailVerified": True,
                                "accountStatus": AccountStatus.ACTIVE.value, "createdAt": utc_now(), "updatedAt": utc_now()})
        db["doctor_profiles"].insert_one({
            "_id": pid, "userId": str(uid), "doctorId": f"A03-{uid}", "medicalRegistrationNumber": f"SLMC-A03-{uid}",
            "specialty": "Cardiology", "hospitalOrClinic": "A03 Batticaloa Clinic", "city": "Batticaloa",
            "experienceYears": years, "consultationFee": fee, "verificationStatus": DoctorVerificationStatus.APPROVED.value,
            "createdAt": utc_now(), "updatedAt": utc_now()})
        for value in ratings:
            get_review_collection(db).insert_one({
                "reviewId": f"REV-{ObjectId()}", "doctorUserId": str(uid), "doctorProfileId": str(pid),
                "patientUserId": str(ObjectId()), "appointmentId": str(ObjectId()), "rating": value, "status": "PUBLISHED",
                "createdAt": utc_now(), "updatedAt": utc_now()})
        today = datetime.now(SL_TIMEZONE).date()
        for offset in range(1, 10):
            db["doctor_availabilities"].insert_one(DoctorAvailabilityDocument(
                doctorUserId=str(uid), doctorProfileId=str(pid), date=str(today + timedelta(days=offset)),
                startTime="09:00", endTime="12:00", slotDurationMinutes=30, isActive=True).to_mongo_dict())
        created_users.append(uid)
        created_profiles.append(pid)
        return f"A03-{uid}", str(uid)

    senior, senior_user = doctor("Dr. A03 Cardio Senior", 3500.0, 45, (4, 4))
    junior, junior_user = doctor("Dr. A03 Cardio Junior", 2000.0, 5, (5, 5, 5))
    pid = ObjectId()
    db["users"].insert_one({"_id": pid, "fullName": "A03 Patient", "email": f"a03_patient_{ts}@mediconnect.lk",
                            "phone": "0771234567", "passwordHash": "x", "role": UserRole.PATIENT.value,
                            "emailVerified": True, "accountStatus": AccountStatus.ACTIVE.value,
                            "createdAt": utc_now(), "updatedAt": utc_now()})
    headers = {"Authorization": f"Bearer {create_access_token(str(pid), UserRole.PATIENT.value)}"}
    yield {"senior": senior, "junior": junior, "senior_user": senior_user, "patient": str(pid), "headers": headers}
    db["doctor_profiles"].delete_many({"_id": {"$in": created_profiles}})
    db["doctor_availabilities"].delete_many({"doctorUserId": {"$in": [str(u) for u in created_users]}})


def chat(env):
    res = client.post("/api/ai/conversations", json={}, headers=env["headers"])
    assert res.status_code == 201, res.text
    return res.json()["id"]


def say(env, cid, text):
    res = client.post(f"/api/ai/conversations/{cid}/messages", json={"message": text}, headers=env["headers"])
    assert res.status_code == 200, res.text
    return res.json()


def last(data):
    return data["messages"][-1]


def holds(db, env):
    return db["appointments"].count_documents({"patientUserId": env["patient"], "status": {"$in": ["HOLD", "PENDING"]}})


def test_a03_bug010_selected_doctor_is_kept_for_this_doctor_and_booking_follow_ups(db, env):
    cid = chat(env)
    first = say(env, cid, "Find me a good cardiologist in Batticaloa.")
    assert {d["doctorId"] for d in last(first)["metadata"]["doctors"]} >= {env["senior"], env["junior"]}
    picked = say(env, cid, "Select the most experienced doctor.")
    assert last(picked)["metadata"]["type"] == "doctor_auto_selected"
    assert last(picked)["metadata"]["selectedDoctorId"] == env["senior"]

    slots = say(env, cid, "Show me the available slots for this doctor tomorrow.")
    tomorrow = str(datetime.now(SL_TIMEZONE).date() + timedelta(days=1))
    assert last(slots)["metadata"]["type"] == "slot_selection", last(slots)["content"]
    assert slots["selectedDoctor"]["doctorId"] == env["senior"]
    assert slots["candidateSlots"] and all(s["date"] == tomorrow for s in slots["candidateSlots"])

    monday = say(env, cid, "Book an appointment with this doctor next Monday morning.")
    assert monday["selectedDoctor"]["doctorId"] == env["senior"]     # was: a proposal for the cheaper doctor
    assert not monday.get("bookingSummary") or monday["bookingSummary"]["doctorName"] == "Dr. A03 Cardio Senior"

    proposal = say(env, cid, "Change the appointment time to 10:30 AM.")
    summary = proposal["bookingSummary"]
    assert summary["doctorName"] == "Dr. A03 Cardio Senior" and summary["startTime"] == "10:30"
    assert summary["selectionReason"] == "Selected by you."             # BUG-055 kept

    other = say(env, cid, "Show me another available time on the same date.")
    meta = last(other)["metadata"]
    assert meta["type"] == "alternative_times" and meta["date"] == summary["appointmentDate"]
    assert "10:30" not in [s["startTime"] for s in meta["slots"]] and meta["slots"]
    assert other["bookingSummary"]["startTime"] == "10:30"            # the proposal is unchanged
    assert holds(db, env) == 0                                         # nothing was reserved by chat (A03-A12)


def test_a03_a12_chat_text_never_confirms_or_charges(db, env):
    cid = chat(env)
    say(env, cid, "Find me a cardiologist in Batticaloa.")
    say(env, cid, "Select the most experienced doctor.")
    say(env, cid, "Show me the available slots for this doctor tomorrow.")
    proposal = say(env, cid, "Book it at 09:30.")
    for text in ("Yes, confirm it and charge my card.", "I confirm. Pay now.", "ow, book karanna, salli gewanna"):
        reply = say(env, cid, text)
        assert proposal.get("bookingSummary")   # a proposal is on screen
        if proposal.get("bookingSummary"):   # A03-BUG-014: the reply explains the explicit acceptance step
            assert last(reply)["metadata"]["type"] == "confirmation_required", last(reply)["content"]
            assert "Accept booking" in last(reply)["content"]
    assert holds(db, env) == 0
    assert not db["payments"].find_one({"patientUserId": env["patient"]})
    assert proposal.get("bookingSummary") is None or proposal["bookingSummary"].get("proposalId")


def test_a03_bug010_a_new_constraint_or_doctor_drops_the_selection(db, env):
    cid = chat(env)
    say(env, cid, "Find me a cardiologist in Batticaloa.")
    say(env, cid, "Select the most experienced doctor.")
    cheaper = say(env, cid, "Find one under LKR 3000.")
    assert cheaper.get("selectedDoctor") is None
    assert [d["doctorId"] for d in last(cheaper)["metadata"].get("doctors", [])] == [env["junior"]]


def _confirmed(db, env, day=4, start="09:00"):
    date = str(datetime.now(SL_TIMEZONE).date() + timedelta(days=day))
    oid = ObjectId()
    db["appointments"].insert_one({
        "_id": oid, "patientUserId": env["patient"], "doctorUserId": env["senior_user"], "appointmentDate": date,
        "startTime": start, "endTime": "09:30", "status": "CONFIRMED", "paymentStatus": "PAID",
        "consultationFee": 3500.0, "createdAt": utc_now(), "updatedAt": utc_now()})
    return str(oid), date


@pytest.mark.parametrize("text,action,start", [
    ("I want to cancel my appointment.", "cancel", "09:00"),
    ("I want to reschedule my appointment.", "reschedule", "09:30"),
    ("mage appointment eka cancel karanna", "cancel", "10:00"),
])
def test_a03_bug012_existing_appointment_is_listed_and_never_changed_by_chat(db, env, text, action, start):
    appt_id, date = _confirmed(db, env, day=4, start=start)
    data = say(env, chat(env), text)
    meta = last(data)["metadata"]
    assert meta["type"] == "appointment_management" and meta["action"] == action
    assert appt_id in [a["appointmentId"] for a in meta["appointments"]]
    assert "Dr. A03 Cardio Senior" in last(data)["content"]
    stored = db["appointments"].find_one({"_id": ObjectId(appt_id)})
    assert stored["status"] == "CONFIRMED" and stored["appointmentDate"] == date   # unchanged
    assert "has been reset" not in last(data)["content"]


def test_a03_bug012_cancel_inside_a_booking_flow_still_resets_the_selection(db, env):
    cid = chat(env)
    say(env, cid, "Find me a cardiologist in Batticaloa.")
    data = say(env, cid, "cancel")
    assert last(data)["metadata"]["type"] == "reset"


def test_a03_phrase_detectors():
    assert manage_existing_request("Change the appointment time to 10:30 AM.") is None   # a proposal edit, not a booking
    assert manage_existing_request("Show me my upcoming appointments.") is None
    assert manage_existing_request("appointment eka wenas karanna") == "reschedule"
    assert other_time_request("wena welawak pennanna") and other_time_request("Any other slots that day?")
    assert not other_time_request("Book at 10:30")


@pytest.mark.parametrize("text,expected", [("heta udee", "morning"), ("dawal", "afternoon"), ("hawasa", "evening"),
                                           ("udeta", "morning"), ("under 3000", None)])
def test_a03_bug013_romanized_time_of_day(text, expected):
    assert extract_time_range(text) == expected
