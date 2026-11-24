"""Doctor availability consistency across doctor calendar, patient profile and AI booking (BUG-005/006).

The doctor calendar, the patient-facing slot list and the AI assistant must all derive slots from the
same generator, so a newly created availability window appears identically everywhere, and a booked
slot disappears everywhere.
"""

import asyncio
from datetime import datetime, timedelta

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.agents.booking_agent import BookingAgent
from app.config.database import get_database
from app.main import app
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.services.doctor_service import get_sl_now
from app.utils.security import create_access_token

client = TestClient(app)


@pytest.fixture(scope="module")
def doctor_env():
    db = get_database()
    doctor_uid, profile_id, patient_uid = ObjectId(), ObjectId(), ObjectId()
    doctor_code = f"CONS-{doctor_uid}"
    for uid, role, name in ((doctor_uid, UserRole.DOCTOR.value, "Dr. Consistency"), (patient_uid, UserRole.PATIENT.value, "Pat Consistency")):
        db["users"].insert_one({
            "_id": uid, "fullName": name, "email": f"{uid}@mediconnect.lk", "passwordHash": "x", "role": role,
            "emailVerified": True, "accountStatus": AccountStatus.ACTIVE.value, "createdAt": utc_now(), "updatedAt": utc_now(),
        })
    db["doctor_profiles"].insert_one({
        "_id": profile_id, "userId": str(doctor_uid), "doctorId": doctor_code, "medicalRegistrationNumber": f"SLMC-{doctor_uid}",
        "specialty": "Neurology", "hospitalOrClinic": "Kandy Care", "city": "Kandy", "experienceYears": 8,
        "consultationFee": 2000.0, "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(), "updatedAt": utc_now(),
    })
    first_of_next_month = (get_sl_now().date().replace(day=1) + timedelta(days=32)).replace(day=1)
    target = first_of_next_month.replace(day=10)
    yield {
        "db": db, "doctor_code": doctor_code, "doctor_uid": str(doctor_uid), "profile_id": str(profile_id),
        "patient_uid": str(patient_uid), "date": target.isoformat(), "month": target.strftime("%Y-%m"),
        "doctor_headers": {"Authorization": f"Bearer {create_access_token(str(doctor_uid), UserRole.DOCTOR.value)}"},
        "patient_headers": {"Authorization": f"Bearer {create_access_token(str(patient_uid), UserRole.PATIENT.value)}"},
    }
    db["doctor_availabilities"].delete_many({"doctorUserId": str(doctor_uid)})
    db["appointments"].delete_many({"doctorUserId": str(doctor_uid)})
    db["doctor_profiles"].delete_one({"_id": profile_id})
    db["users"].delete_many({"_id": {"$in": [doctor_uid, patient_uid]}})


def _calendar_day(env):
    resp = client.get(f"/api/doctors/me/calendar-overview?month={env['month']}", headers=env["doctor_headers"])
    assert resp.status_code == 200, resp.text
    return next(day for day in resp.json()["days"] if day["date"] == env["date"])


def _patient_starts(env):
    resp = client.get(f"/api/doctors/{env['doctor_code']}/availability?date={env['date']}", headers=env["patient_headers"])
    assert resp.status_code == 200, resp.text
    return [slot["startTime"] for slot in resp.json()["slots"]]


def _ai_starts(env):
    slots = asyncio.run(BookingAgent._fetch_available_slots(env["db"], env["doctor_code"], env["date"]))
    return [slot["startTime"] for slot in slots]


def test_bug006_new_window_appears_in_calendar_patient_profile_and_ai(doctor_env):
    resp = client.post("/api/doctors/me/availability", headers=doctor_env["doctor_headers"], json={
        "date": doctor_env["date"], "startTime": "09:00", "endTime": "11:00", "slotDurationMinutes": 30,
    })
    assert resp.status_code in (200, 201), resp.text

    day = _calendar_day(doctor_env)
    expected = ["09:00", "09:30", "10:00", "10:30"]
    assert day["status"] == "AVAILABLE"
    assert [slot["startTime"] for slot in day["slots"]] == expected
    assert _patient_starts(doctor_env) == expected
    assert _ai_starts(doctor_env) == expected


def test_bug006_booked_slot_removed_everywhere(doctor_env):
    doctor_env["db"]["appointments"].insert_one({
        "doctorUserId": doctor_env["doctor_uid"], "doctorProfileId": doctor_env["profile_id"],
        "patientUserId": doctor_env["patient_uid"], "appointmentDate": doctor_env["date"],
        "startTime": "09:30", "endTime": "10:00", "status": "CONFIRMED", "paymentStatus": "PAID",
        "createdAt": utc_now(), "updatedAt": utc_now(),
    })
    expected = ["09:00", "10:00", "10:30"]
    day = _calendar_day(doctor_env)
    assert [slot["startTime"] for slot in day["slots"]] == expected
    assert day["bookedAppointmentsCount"] == 1
    assert day["appointments"][0]["patientName"] == "Pat Consistency"
    assert _patient_starts(doctor_env) == expected
    assert _ai_starts(doctor_env) == expected


@pytest.mark.parametrize("month", ["2026-13", "2026-00", "26-1", "abc"])
def test_bug005_invalid_month_is_a_400_not_a_server_error(doctor_env, month):
    resp = client.get(f"/api/doctors/me/calendar-overview?month={month}", headers=doctor_env["doctor_headers"])
    assert resp.status_code == 400


def test_bug005_month_navigation_past_and_future(doctor_env):
    now = get_sl_now()
    previous = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    far_future = (now.replace(day=1) + timedelta(days=400)).strftime("%Y-%m")
    for month in (previous, far_future):
        resp = client.get(f"/api/doctors/me/calendar-overview?month={month}", headers=doctor_env["doctor_headers"])
        assert resp.status_code == 200, resp.text
        days = resp.json()["days"]
        assert days and all(day["date"].startswith(month) for day in days)
    past_days = client.get(f"/api/doctors/me/calendar-overview?month={previous}", headers=doctor_env["doctor_headers"]).json()["days"]
    assert all(day["availableSlotsCount"] == 0 for day in past_days)


def test_bug005_calendar_uses_batched_slot_generation(doctor_env, monkeypatch):
    from app.services.doctor_service import DoctorService

    calls = []
    original = DoctorService.get_doctor_patient_slots

    async def counting(*args, **kwargs):
        calls.append(kwargs.get("date_list"))
        return await original(*args, **kwargs)

    monkeypatch.setattr(DoctorService, "get_doctor_patient_slots", staticmethod(counting))
    resp = client.get(f"/api/doctors/me/calendar-overview?month={doctor_env['month']}", headers=doctor_env["doctor_headers"])
    assert resp.status_code == 200
    assert len(calls) == 1 and len(calls[0]) >= 28
