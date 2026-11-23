"""Backend test suite for Phase 54: Doctor Availability & Leave Calendar.

Tests:
1. Get and update weekly recurring schedule (valid weekdays, sessions, duration, timezone).
2. Validation: Reject overlapping sessions or invalid times in weekly schedule.
3. Apply for leave, list leaves, cancel active leave.
4. Conflict detection: creating leave overlapping active appointment returns 409 conflict;
   resolveConflicts=True cancels conflicting appointment and notifies patient.
5. Create, list, and delete doctor blocked time windows.
6. Slot generation: get_doctor_patient_slots generates slots from weekly schedule,
   excludes active leaves, excludes blocked times, excludes booked appointments.
7. Doctor calendar overview endpoint returns calendar days and stats.
"""

import asyncio
from datetime import datetime, timedelta
import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.appointment import AppointmentStatus, PaymentStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.services.doctor_service import SL_TIMEZONE, get_sl_now, DoctorService
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture
def test_setup():
    """Seed test doctor, patient, and doctor profile."""
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Doctor
    doc_id = str(ObjectId())
    doc_prof_id = str(ObjectId())
    doc_num = f"DOC-TEST-CAL-{ts}"

    db["users"].insert_one({
        "_id": ObjectId(doc_id),
        "fullName": "Dr. Nishantha Silva",
        "email": f"dr_silva_{ts}@mediconnect.lk",
        "phone": "0771234567",
        "passwordHash": hash_password("Doc@1234"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc_prof_id),
        "userId": doc_id,
        "doctorId": doc_num,
        "fullName": "Dr. Nishantha Silva",
        "specialty": "Cardiology",
        "medicalRegistrationNumber": f"SLMC-CAL-{ts}",
        "hospitalOrClinic": "National Hospital Colombo",
        "consultationFee": 2500.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc_token = create_access_token(doc_id, role=UserRole.DOCTOR.value)

    # 2. Patient
    pat_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_id),
        "fullName": "Anura Kumara",
        "email": f"patient_cal_{ts}@mediconnect.lk",
        "phone": "0779988776",
        "passwordHash": hash_password("Pat@1234"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat_token = create_access_token(pat_id, role=UserRole.PATIENT.value)

    yield {
        "db": db,
        "doc_id": doc_id,
        "doc_prof_id": doc_prof_id,
        "doc_num": doc_num,
        "doc_token": doc_token,
        "pat_id": pat_id,
        "pat_token": pat_token,
    }

    # Teardown
    db["users"].delete_one({"_id": ObjectId(doc_id)})
    db["users"].delete_one({"_id": ObjectId(pat_id)})
    db["doctor_profiles"].delete_one({"_id": ObjectId(doc_prof_id)})
    db["doctor_weekly_schedules"].delete_many({"doctorUserId": doc_id})
    db["doctor_leaves"].delete_many({"doctorUserId": doc_id})
    db["doctor_blocked_times"].delete_many({"doctorUserId": doc_id})
    db["appointments"].delete_many({"doctorId": doc_num})


def test_01_weekly_schedule_get_and_update(test_setup):
    """Test getting default weekly schedule and updating with multi-session days."""
    token = test_setup["doc_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get default schedule
    res = client.get("/api/doctors/me/weekly-schedule", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["timezone"] == "Asia/Colombo"
    assert data["slotDurationMinutes"] == 30
    assert len(data["weekdays"]) == 7

    # 2. Update with custom sessions (e.g. Monday morning and afternoon)
    payload = {
        "timezone": "Asia/Colombo",
        "slotDurationMinutes": 20,
        "weekdays": [
            {
                "weekday": "monday",
                "isEnabled": True,
                "sessions": [
                    {"startTime": "09:00", "endTime": "12:00"},
                    {"startTime": "14:00", "endTime": "17:00"},
                ],
            },
            {
                "weekday": "tuesday",
                "isEnabled": True,
                "sessions": [{"startTime": "10:00", "endTime": "13:00"}],
            },
            {"weekday": "wednesday", "isEnabled": False, "sessions": []},
            {"weekday": "thursday", "isEnabled": False, "sessions": []},
            {"weekday": "friday", "isEnabled": False, "sessions": []},
            {"weekday": "saturday", "isEnabled": False, "sessions": []},
            {"weekday": "sunday", "isEnabled": False, "sessions": []},
        ],
    }
    put_res = client.put("/api/doctors/me/weekly-schedule", json=payload, headers=headers)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["slotDurationMinutes"] == 20
    mon = next(w for w in updated["weekdays"] if w["day"] == "monday")
    assert mon["isEnabled"] is True
    assert len(mon["sessions"]) == 2


def test_02_weekly_schedule_validation_rejects_overlapping_sessions(test_setup):
    """Validation test: reject overlapping sessions within the same day."""
    token = test_setup["doc_token"]
    headers = {"Authorization": f"Bearer {token}"}

    overlapping_payload = {
        "timezone": "Asia/Colombo",
        "slotDurationMinutes": 30,
        "weekdays": [
            {
                "weekday": "monday",
                "isEnabled": True,
                "sessions": [
                    {"startTime": "09:00", "endTime": "12:00"},
                    {"startTime": "11:30", "endTime": "14:00"},  # overlaps with 09:00-12:00!
                ],
            }
        ],
    }
    res = client.put("/api/doctors/me/weekly-schedule", json=overlapping_payload, headers=headers)
    assert res.status_code == 400
    assert "overlap" in res.json()["detail"].lower()


def test_03_doctor_leave_crud(test_setup):
    """Test scheduling a leave, listing active leaves, and cancelling a leave."""
    token = test_setup["doc_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Apply for leave
    leave_payload = {
        "leaveType": "VACATION",
        "startDate": "2026-12-24",
        "endDate": "2026-12-26",
        "reason": "Christmas Holiday with Family",
        "resolveConflicts": False,
    }
    create_res = client.post("/api/doctors/me/leave", json=leave_payload, headers=headers)
    assert create_res.status_code == 201
    leave_data = create_res.json()
    leave_id = leave_data["id"]
    assert leave_data["status"] == "ACTIVE"
    assert leave_data["startDate"] == "2026-12-24"

    # List leaves
    list_res = client.get("/api/doctors/me/leave?status=ACTIVE", headers=headers)
    assert list_res.status_code == 200
    leaves = list_res.json()
    assert any(l["id"] == leave_id for l in leaves)

    # Cancel leave
    del_res = client.delete(f"/api/doctors/me/leave/{leave_id}", headers=headers)
    assert del_res.status_code == 200

    # Verify cancelled
    list_res_after = client.get("/api/doctors/me/leave?status=ACTIVE", headers=headers)
    assert not any(l["id"] == leave_id for l in list_res_after.json())


def test_04_doctor_leave_conflict_detection_and_resolution(test_setup):
    """Test leave conflict detection with confirmed appointment and cancellation with notification."""
    db = test_setup["db"]
    doc_token = test_setup["doc_token"]
    doc_num = test_setup["doc_num"]
    pat_id = test_setup["pat_id"]
    headers = {"Authorization": f"Bearer {doc_token}"}

    conflict_date = "2026-11-25"

    # Seed an existing confirmed appointment on that date
    apt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(apt_id),
        "doctorUserId": test_setup["doc_id"],
        "doctorProfileId": test_setup["doc_prof_id"],
        "doctorId": doc_num,
        "patientUserId": pat_id,
        "patientId": pat_id,
        "appointmentDate": conflict_date,
        "startTime": "10:00",
        "endTime": "10:30",
        "slotDurationMinutes": 30,
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "consultationType": "IN_PERSON",
        "totalAmount": 2500.0,
        "patientNotes": "Regular checkup",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 1. Attempt creating leave without resolveConflicts -> Expect 409 Conflict
    leave_req = {
        "leaveType": "MEDICAL",
        "startDate": conflict_date,
        "endDate": conflict_date,
        "reason": "Emergency surgery training",
        "resolveConflicts": False,
    }
    conflict_res = client.post("/api/doctors/me/leave", json=leave_req, headers=headers)
    assert conflict_res.status_code == 409
    assert "conflicts with" in conflict_res.json()["detail"].lower()

    # 2. Retry with resolveConflicts=True -> Leave created and appointment cancelled
    leave_req["resolveConflicts"] = True
    resolved_res = client.post("/api/doctors/me/leave", json=leave_req, headers=headers)
    assert resolved_res.status_code == 201
    assert resolved_res.json()["status"] == "ACTIVE"

    # Check appointment status in DB
    updated_apt = db["appointments"].find_one({"_id": ObjectId(apt_id)})
    assert updated_apt["status"] == AppointmentStatus.CANCELLED.value

    # Check patient was sent cancellation notification
    notif = db["notifications"].find_one({"recipientUserId": pat_id})
    assert notif is not None
    assert "cancelled" in notif["title"].lower() or "cancelled" in notif["body"].lower()


def test_05_doctor_blocked_time_crud(test_setup):
    """Test blocking a specific time range and deleting it."""
    token = test_setup["doc_token"]
    headers = {"Authorization": f"Bearer {token}"}

    block_payload = {
        "date": "2026-11-28",
        "startTime": "14:00",
        "endTime": "16:00",
        "reason": "Hospital committee meeting",
    }
    post_res = client.post("/api/doctors/me/blocked-time", json=block_payload, headers=headers)
    assert post_res.status_code == 201
    block_id = post_res.json()["id"]

    # List
    list_res = client.get("/api/doctors/me/blocked-time", headers=headers)
    assert list_res.status_code == 200
    assert any(b["id"] == block_id for b in list_res.json())

    # Delete
    del_res = client.delete(f"/api/doctors/me/blocked-time/{block_id}", headers=headers)
    assert del_res.status_code == 200

    list_after = client.get("/api/doctors/me/blocked-time", headers=headers)
    assert not any(b["id"] == block_id for b in list_after.json())


def test_06_slots_respect_weekly_schedule_leave_and_blocked_time(test_setup):
    """Test get_doctor_patient_slots:

    - Slots generated based on weekly schedule sessions.
    - Day with leave returns 0 available slots.
    - Partial blocked time removes overlapping slots.
    """
    db = test_setup["db"]
    doc_token = test_setup["doc_token"]
    doc_num = test_setup["doc_num"]
    headers = {"Authorization": f"Bearer {doc_token}"}

    # Find a future date that is a Monday (e.g. 2026-11-16 or next Monday)
    today = get_sl_now().date()
    days_ahead = (0 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_monday = today + timedelta(days=days_ahead)
    mon_str = target_monday.strftime("%Y-%m-%d")

    # Set weekly schedule: Monday 09:00 - 11:00 with 30 min duration (slots: 09:00, 09:30, 10:00, 10:30)
    client.put(
        "/api/doctors/me/weekly-schedule",
        json={
            "timezone": "Asia/Colombo",
            "slotDurationMinutes": 30,
            "weekdays": [
                {
                    "weekday": "monday",
                    "isEnabled": True,
                    "sessions": [{"startTime": "09:00", "endTime": "11:00"}],
                }
            ],
        },
        headers=headers,
    )

    # 1. Fetch slots without leaves/blocks -> 4 slots
    slots_res = asyncio.run(DoctorService.get_doctor_patient_slots(db, doc_num, mon_str))
    slots = slots_res.slots if hasattr(slots_res, "slots") else slots_res
    assert len(slots) == 4
    times = [s["startTime"] if isinstance(s, dict) else s.startTime for s in slots]
    assert times == ["09:00", "09:30", "10:00", "10:30"]

    # 2. Block 09:30 - 10:30 -> slots 09:30 and 10:00 should be removed!
    client.post(
        "/api/doctors/me/blocked-time",
        json={"date": mon_str, "startTime": "09:30", "endTime": "10:30", "reason": "Ward rounds"},
        headers=headers,
    )
    slots_after_block_res = asyncio.run(DoctorService.get_doctor_patient_slots(db, doc_num, mon_str))
    slots_after_block = slots_after_block_res.slots if hasattr(slots_after_block_res, "slots") else slots_after_block_res
    times_after_block = [s["startTime"] if isinstance(s, dict) else s.startTime for s in slots_after_block]
    assert times_after_block == ["09:00", "10:30"]

    # 3. Add full-day leave on that Monday -> 0 slots returned!
    client.post(
        "/api/doctors/me/leave",
        json={"leaveType": "PERSONAL", "startDate": mon_str, "endDate": mon_str, "reason": "Family event"},
        headers=headers,
    )
    slots_after_leave_res = asyncio.run(DoctorService.get_doctor_patient_slots(db, doc_num, mon_str))
    slots_after_leave = slots_after_leave_res.slots if hasattr(slots_after_leave_res, "slots") else slots_after_leave_res
    assert len(slots_after_leave) == 0


def test_07_calendar_overview_endpoint(test_setup):
    """Test GET /api/doctors/me/calendar-overview returns day-by-day status and metrics."""
    doc_token = test_setup["doc_token"]
    headers = {"Authorization": f"Bearer {doc_token}"}

    # Month overview for current month
    now = get_sl_now()
    month_str = now.strftime("%Y-%m")
    res = client.get(f"/api/doctors/me/calendar-overview?month={month_str}", headers=headers)
    assert res.status_code == 200
    overview = res.json()
    assert overview["month"] == month_str
    assert "days" in overview
    assert len(overview["days"]) >= 28
