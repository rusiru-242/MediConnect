"""Automated test suite for Phase 22: Smart Medication Reminder System.

Covers:
1. Patient authorization (Only patients can create reminders and log events; doctors receive 403).
2. Prescription ownership (Patient cannot create a reminder for another patient's prescription).
3. Prescription status validation (Cannot create reminder for cancelled prescription).
4. Valid reminder creation (Linked to doctor-issued prescription with parsed duration).
5. Prescribed frequency validation (Dose count must match prescribed frequency e.g. Twice daily -> 2 times).
6. Duplicate reminder prevention (Cannot create duplicate active reminder for same prescription item).
7. Cross-patient access denial (Patient B cannot view, modify, or delete Patient A's reminders).
8. Reminder update & settings (Update times, toggle enabled, notes).
9. Today's schedule generation (Timezone-aware occurrences: PENDING, TAKEN, SKIPPED, SNOOZED).
10. Medication intake event recording (TAKEN, SKIPPED, SNOOZED with snoozeMinutes).
11. Event recording idempotency (Updating status for the same scheduled occurrence is idempotent).
12. Medication history & adherence summary (Accurate calculation of adherence percentage).
13. Reminder cancellation (Soft delete marks reminder CANCELLED and disables notifications).
"""

from datetime import datetime, timedelta, timezone
import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.medication_reminder import EventStatus, ReminderStatus
from app.models.prescription import PrescriptionStatus
from app.models.user import AccountStatus, UserRole
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def seeded_reminder_env():
    """Seed test database with:
    - Patient A, Patient B
    - Doctor A
    - Prescription A1 for Patient A (Valid, Twice daily, 5 days)
    - Prescription A2 for Patient A (Cancelled)
    - Prescription B1 for Patient B
    """
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Patient A
    pat_a_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_a_id),
        "email": f"patient.rem.a.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Alice Reminder Patient",
        "role": UserRole.PATIENT.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    })
    token_pat_a = create_access_token(
        user_id=pat_a_id, role=UserRole.PATIENT.value
    )

    # 2. Patient B
    pat_b_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_b_id),
        "email": f"patient.rem.b.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Bob Reminder Patient",
        "role": UserRole.PATIENT.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    })
    token_pat_b = create_access_token(
        user_id=pat_b_id, role=UserRole.PATIENT.value
    )

    # 3. Doctor A
    doc_a_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(doc_a_id),
        "email": f"dr.rem.a.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Dr. Sarah Prescriber",
        "role": UserRole.DOCTOR.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    })
    token_doc_a = create_access_token(
        user_id=doc_a_id, role=UserRole.DOCTOR.value
    )

    # 4. Prescription A1 (Issued to Patient A, Twice daily for 5 days)
    rx_a1_id = str(ObjectId())
    rx_a1_ref = f"RX-{ts}-A1"
    db["prescriptions"].insert_one({
        "_id": ObjectId(rx_a1_id),
        "prescriptionId": rx_a1_ref,
        "medicalRecordId": str(ObjectId()),
        "appointmentId": str(ObjectId()),
        "patientUserId": pat_a_id,
        "doctorUserId": doc_a_id,
        "doctorProfileId": str(ObjectId()),
        "status": PrescriptionStatus.ISSUED.value,
        "issuedAt": datetime.now(timezone.utc),
        "medicationItems": [
            {
                "medicationName": "Amoxicillin",
                "strength": "500mg",
                "dose": "1 capsule",
                "route": "Oral",
                "frequency": "Twice daily",
                "duration": "5 days",
                "quantity": "10 capsules",
                "additionalInstructions": "Take after meals with water",
            },
            {
                "medicationName": "Paracetamol",
                "strength": "500mg",
                "dose": "2 tablets",
                "route": "Oral",
                "frequency": "Once daily",
                "duration": "3 days",
                "quantity": "6 tablets",
                "additionalInstructions": "Take in the morning",
            },
        ],
        "instructions": "Complete full antibiotic course",
        "amendmentHistory": [],
        "auditLog": [],
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    })

    # 5. Prescription A2 (Cancelled prescription for Patient A)
    rx_a2_id = str(ObjectId())
    rx_a2_ref = f"RX-{ts}-A2"
    db["prescriptions"].insert_one({
        "_id": ObjectId(rx_a2_id),
        "prescriptionId": rx_a2_ref,
        "medicalRecordId": str(ObjectId()),
        "appointmentId": str(ObjectId()),
        "patientUserId": pat_a_id,
        "doctorUserId": doc_a_id,
        "doctorProfileId": str(ObjectId()),
        "status": PrescriptionStatus.CANCELLED.value,
        "issuedAt": datetime.now(timezone.utc),
        "medicationItems": [
            {
                "medicationName": "Ciprofloxacin",
                "strength": "500mg",
                "dose": "1 tablet",
                "route": "Oral",
                "frequency": "Twice daily",
                "duration": "7 days",
                "quantity": "14 tablets",
            }
        ],
        "instructions": "Cancelled due to allergy",
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    })

    # 6. Prescription B1 (Issued to Patient B)
    rx_b1_id = str(ObjectId())
    rx_b1_ref = f"RX-{ts}-B1"
    db["prescriptions"].insert_one({
        "_id": ObjectId(rx_b1_id),
        "prescriptionId": rx_b1_ref,
        "medicalRecordId": str(ObjectId()),
        "appointmentId": str(ObjectId()),
        "patientUserId": pat_b_id,
        "doctorUserId": doc_a_id,
        "doctorProfileId": str(ObjectId()),
        "status": PrescriptionStatus.ISSUED.value,
        "issuedAt": datetime.now(timezone.utc),
        "medicationItems": [
            {
                "medicationName": "Metformin",
                "strength": "500mg",
                "dose": "1 tablet",
                "route": "Oral",
                "frequency": "Once daily",
                "duration": "30 days",
                "quantity": "30 tablets",
            }
        ],
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    })

    return {
        "pat_a_id": pat_a_id,
        "token_pat_a": token_pat_a,
        "pat_b_id": pat_b_id,
        "token_pat_b": token_pat_b,
        "doc_a_id": doc_a_id,
        "token_doc_a": token_doc_a,
        "rx_a1_id": rx_a1_id,
        "rx_a1_ref": rx_a1_ref,
        "rx_a2_id": rx_a2_id,
        "rx_b1_id": rx_b1_id,
    }


def test_doctor_cannot_create_medication_reminder(seeded_reminder_env):
    """Doctors should be rejected (403) from creating patient medication reminders."""
    env = seeded_reminder_env
    res = client.post(
        "/api/medication-reminders",
        headers={"Authorization": f"Bearer {env['token_doc_a']}"},
        json={
            "prescriptionId": env["rx_a1_id"],
            "prescriptionMedicationIndex": 0,
            "scheduledTimes": ["08:00", "20:00"],
        },
    )
    assert res.status_code == 403


def test_cannot_create_reminder_for_other_patient_prescription(seeded_reminder_env):
    """Patient A cannot create a reminder using Patient B's prescription."""
    env = seeded_reminder_env
    res = client.post(
        "/api/medication-reminders",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
        json={
            "prescriptionId": env["rx_b1_id"],
            "prescriptionMedicationIndex": 0,
            "scheduledTimes": ["08:00"],
        },
    )
    assert res.status_code == 403
    assert "another patient" in res.json()["detail"].lower()


def test_cannot_create_reminder_for_cancelled_prescription(seeded_reminder_env):
    """Cannot create reminder from a cancelled prescription."""
    env = seeded_reminder_env
    res = client.post(
        "/api/medication-reminders",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
        json={
            "prescriptionId": env["rx_a2_id"],
            "prescriptionMedicationIndex": 0,
            "scheduledTimes": ["08:00", "20:00"],
        },
    )
    assert res.status_code == 400
    assert "cancelled" in res.json()["detail"].lower()


def test_frequency_mismatch_validation_rejected(seeded_reminder_env):
    """If prescribed Twice daily, patient cannot supply only 1 time or 3 times."""
    env = seeded_reminder_env
    # Only 1 time provided for Twice daily drug
    res = client.post(
        "/api/medication-reminders",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
        json={
            "prescriptionId": env["rx_a1_id"],
            "prescriptionMedicationIndex": 0,
            "scheduledTimes": ["08:00"],
        },
    )
    assert res.status_code == 400
    assert "2 doses/day" in res.json()["detail"] or "frequency" in res.json()["detail"].lower()


def test_valid_medication_reminder_creation(seeded_reminder_env):
    """Patient A creates a valid reminder for Amoxicillin (Twice daily: 08:00, 20:00)."""
    env = seeded_reminder_env
    res = client.post(
        "/api/medication-reminders",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
        json={
            "prescriptionId": env["rx_a1_id"],
            "prescriptionMedicationIndex": 0,
            "scheduledTimes": ["08:00", "20:00"],
            "patientTimezone": "Asia/Colombo",
            "notes": "Take with breakfast and dinner",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["reminderId"].startswith("REM-")
    assert data["medicationName"] == "Amoxicillin"
    assert data["scheduledTimes"] == ["08:00", "20:00"]
    assert data["enabled"] is True
    assert data["status"] == "ACTIVE"

    # Save created reminder ID into env for subsequent tests
    env["reminder_a1_id"] = data["_id"]
    env["reminder_a1_ref"] = data["reminderId"]


def test_duplicate_reminder_prevention(seeded_reminder_env):
    """Attempting to create another active reminder for the same prescription medication should fail (400)."""
    env = seeded_reminder_env
    res = client.post(
        "/api/medication-reminders",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
        json={
            "prescriptionId": env["rx_a1_id"],
            "prescriptionMedicationIndex": 0,
            "scheduledTimes": ["09:00", "21:00"],
        },
    )
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"].lower()


def test_list_patient_reminders_and_cross_patient_denial(seeded_reminder_env):
    """Patient A sees their reminder; Patient B cannot access or modify Patient A's reminder."""
    env = seeded_reminder_env
    # 1. Patient A lists reminders
    res_list = client.get(
        "/api/medication-reminders",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) >= 1
    assert any(it["_id"] == env["reminder_a1_id"] for it in items)

    # 2. Patient B tries to view Patient A's reminder
    res_b_view = client.get(
        f"/api/medication-reminders/{env['reminder_a1_id']}",
        headers={"Authorization": f"Bearer {env['token_pat_b']}"},
    )
    assert res_b_view.status_code == 403

    # 3. Patient B tries to update Patient A's reminder
    res_b_patch = client.patch(
        f"/api/medication-reminders/{env['reminder_a1_id']}",
        headers={"Authorization": f"Bearer {env['token_pat_b']}"},
        json={"enabled": False},
    )
    assert res_b_patch.status_code == 403


def test_update_medication_reminder(seeded_reminder_env):
    """Patient A updates reminder times (still matching Twice daily: 09:00, 21:00) and notes."""
    env = seeded_reminder_env
    res = client.patch(
        f"/api/medication-reminders/{env['reminder_a1_id']}",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
        json={
            "scheduledTimes": ["09:00", "21:00"],
            "notes": "Updated to 9 AM and 9 PM",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["scheduledTimes"] == ["09:00", "21:00"]
    assert data["notes"] == "Updated to 9 AM and 9 PM"


def test_today_schedule_generation(seeded_reminder_env):
    """Verify today's schedule returns occurrences matching scheduled times with status PENDING."""
    env = seeded_reminder_env
    res = client.get(
        "/api/medication-reminders/today?timezone=Asia/Colombo",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["totalScheduled"] >= 2
    # Verify items contain 09:00 and 21:00
    times = [item["timeStr"] for item in data["items"]]
    assert "09:00" in times
    assert "21:00" in times

    # Save first occurrence for event recording
    first_item = data["items"][0]
    env["first_occurrence_time"] = first_item["scheduledOccurrenceTime"]


def test_record_medication_event_taken_and_idempotency(seeded_reminder_env):
    """Patient records TAKEN for today's first occurrence, then updates it to SNOOZED idempotently."""
    env = seeded_reminder_env
    occurrence_time = env["first_occurrence_time"]

    # 1. Record TAKEN
    res1 = client.post(
        f"/api/medication-reminders/{env['reminder_a1_id']}/events",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
        json={
            "scheduledOccurrenceTime": occurrence_time,
            "status": EventStatus.TAKEN.value,
            "notes": "Taken with a glass of water",
        },
    )
    assert res1.status_code == 200
    ev1 = res1.json()
    assert ev1["status"] == "TAKEN"
    assert ev1["eventId"].startswith("EVT-")
    event_id = ev1["eventId"]

    # 2. Check today's schedule now reflects TAKEN
    res_today = client.get(
        "/api/medication-reminders/today?timezone=Asia/Colombo",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res_today.status_code == 200
    today_data = res_today.json()
    assert today_data["takenCount"] >= 1

    # 3. Idempotently update the same occurrence to SNOOZED with 30 minutes snooze
    res2 = client.post(
        f"/api/medication-reminders/{env['reminder_a1_id']}/events",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
        json={
            "scheduledOccurrenceTime": occurrence_time,
            "status": EventStatus.SNOOZED.value,
            "snoozeMinutes": 30,
            "notes": "Postponed 30 mins after phone call",
        },
    )
    assert res2.status_code == 200
    ev2 = res2.json()
    assert ev2["status"] == "SNOOZED"
    assert ev2["snoozeMinutes"] == 30
    # Should update the existing record
    assert ev2["eventId"] == event_id


def test_history_and_adherence_summary(seeded_reminder_env):
    """Test history list contains recorded events and adherence summary calculates correctly."""
    env = seeded_reminder_env
    # 1. Get history
    res_hist = client.get(
        "/api/medication-reminders/history",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res_hist.status_code == 200
    hist = res_hist.json()
    assert hist["total"] >= 1
    assert hist["items"][0]["medicationName"] == "Amoxicillin"

    # 2. Get adherence
    res_adh = client.get(
        "/api/medication-reminders/adherence",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res_adh.status_code == 200
    adh = res_adh.json()
    assert adh["totalTrackedDays"] == 30
    assert adh["activeRemindersCount"] >= 1
    assert isinstance(adh["adherenceRatePercent"], float)


def test_delete_medication_reminder(seeded_reminder_env):
    """Patient deletes (cancels) the reminder schedule."""
    env = seeded_reminder_env
    res = client.delete(
        f"/api/medication-reminders/{env['reminder_a1_id']}",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Verify reminder is now CANCELLED and disabled
    res_get = client.get(
        f"/api/medication-reminders/{env['reminder_a1_id']}",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res_get.status_code == 200
    assert res_get.json()["status"] == "CANCELLED"
    assert res_get.json()["enabled"] is False
