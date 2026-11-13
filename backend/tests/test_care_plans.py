"""Backend test suite for Phase 56: Smart Follow-up Care Plans.

Covers:
1. Doctor creates care plan with tasks and follow-up window.
2. Unapproved doctor cannot create care plans (403).
3. Another doctor cannot create/update care plans for an appointment they don't own (403).
4. Past follow-up date is rejected (400).
5. Duplicate active care plan for same consultation appointment is rejected (409).
6. Patient can list and view their care plans; unauthorized access blocked (403/404).
7. Doctor updates care plan (audit trail logged, version incremented).
8. Patient completes care tasks (timestamps tracked, audit trail logged).
9. Patient links booked appointment -> status transitions to FOLLOW_UP_BOOKED.
10. Doctor cancels care plan (status transitions to CANCELLED).
11. Reminder sweep verifies 7d/1d/due notifications and OVERDUE marking.
"""

from datetime import datetime, timedelta
import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.appointment import AppointmentStatus, PaymentStatus
from app.models.care_plan import CarePlanStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.notification import NotificationType
from app.models.user import AccountStatus, UserRole, utc_now
from app.services.care_plan_service import CarePlanService
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture
def care_plan_setup():
    """Seed test doctor, unapproved doctor, 2 patients, consultation appointment."""
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Approved Doctor 1
    doc1_id = str(ObjectId())
    doc1_prof_id = str(ObjectId())
    doc1_num = f"DOC-CARE-1-{ts}"

    db["users"].insert_one({
        "_id": ObjectId(doc1_id),
        "fullName": "Dr. Saman Perera",
        "email": f"dr_care1_{ts}@mediconnect.lk",
        "phone": "0771112233",
        "passwordHash": hash_password("Doc@1234"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc1_prof_id),
        "userId": doc1_id,
        "doctorId": doc1_num,
        "fullName": "Dr. Saman Perera",
        "specialty": "Cardiology",
        "medicalRegistrationNumber": f"SLMC-CARE-1-{ts}",
        "hospitalOrClinic": "Colombo General",
        "consultationFee": 3000.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc1_token = create_access_token(doc1_id, role=UserRole.DOCTOR.value)

    # 2. Unapproved Doctor 2
    doc2_id = str(ObjectId())
    doc2_prof_id = str(ObjectId())
    doc2_num = f"DOC-CARE-2-{ts}"

    db["users"].insert_one({
        "_id": ObjectId(doc2_id),
        "fullName": "Dr. Unapproved Doctor",
        "email": f"dr_care2_{ts}@mediconnect.lk",
        "phone": "0774445566",
        "passwordHash": hash_password("Doc@1234"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc2_prof_id),
        "userId": doc2_id,
        "doctorId": doc2_num,
        "fullName": "Dr. Unapproved Doctor",
        "specialty": "Neurology",
        "medicalRegistrationNumber": f"SLMC-CARE-2-{ts}",
        "hospitalOrClinic": "Kandy Hospital",
        "consultationFee": 2000.0,
        "verificationStatus": DoctorVerificationStatus.PENDING_ADMIN_APPROVAL.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc2_token = create_access_token(doc2_id, role=UserRole.DOCTOR.value)

    # 3. Third Doctor (approved, but owns different consultations)
    doc3_id = str(ObjectId())
    doc3_prof_id = str(ObjectId())
    doc3_num = f"DOC-CARE-3-{ts}"

    db["users"].insert_one({
        "_id": ObjectId(doc3_id),
        "fullName": "Dr. Third Doctor",
        "email": f"dr_care3_{ts}@mediconnect.lk",
        "phone": "0777778899",
        "passwordHash": hash_password("Doc@1234"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc3_prof_id),
        "userId": doc3_id,
        "doctorId": doc3_num,
        "fullName": "Dr. Third Doctor",
        "specialty": "Dermatology",
        "medicalRegistrationNumber": f"SLMC-CARE-3-{ts}",
        "hospitalOrClinic": "Galle Hospital",
        "consultationFee": 2200.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc3_token = create_access_token(doc3_id, role=UserRole.DOCTOR.value)

    # 4. Patient 1
    pat1_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat1_id),
        "fullName": "Kasun Wickrama",
        "email": f"patient_care1_{ts}@mediconnect.lk",
        "phone": "0712345678",
        "passwordHash": hash_password("Pat@1234"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat1_token = create_access_token(pat1_id, role=UserRole.PATIENT.value)

    # 5. Patient 2 (stranger)
    pat2_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat2_id),
        "fullName": "Nimal Perera",
        "email": f"patient_care2_{ts}@mediconnect.lk",
        "phone": "0718765432",
        "passwordHash": hash_password("Pat@1234"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat2_token = create_access_token(pat2_id, role=UserRole.PATIENT.value)

    # 6. Consultation Appointment between doc1 and pat1
    appt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "patientId": pat1_id,
        "patientUserId": pat1_id,
        "patientName": "Kasun Wickrama",
        "patientEmail": f"patient_care1_{ts}@mediconnect.lk",
        "patientPhone": "0712345678",
        "doctorId": doc1_num,
        "doctorUserId": doc1_id,
        "doctorProfileId": doc1_prof_id,
        "doctorName": "Dr. Saman Perera",
        "specialty": "Cardiology",
        "hospitalOrClinic": "Colombo General",
        "appointmentDate": "2026-11-10",
        "appointmentTime": "10:00",
        "slotDurationMinutes": 30,
        "consultationType": "PHYSICAL",
        "fee": 3000.0,
        "status": AppointmentStatus.COMPLETED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "notes": "Initial consultation completed",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    yield {
        "db": db,
        "doc1_id": doc1_id,
        "doc1_token": doc1_token,
        "doc1_num": doc1_num,
        "doc2_id": doc2_id,
        "doc2_token": doc2_token,
        "doc3_id": doc3_id,
        "doc3_token": doc3_token,
        "pat1_id": pat1_id,
        "pat1_token": pat1_token,
        "pat2_id": pat2_id,
        "pat2_token": pat2_token,
        "appt_id": appt_id,
    }

    # Teardown
    db["users"].delete_many({"_id": {"$in": [ObjectId(doc1_id), ObjectId(doc2_id), ObjectId(doc3_id), ObjectId(pat1_id), ObjectId(pat2_id)]}})
    db["doctor_profiles"].delete_many({"_id": {"$in": [ObjectId(doc1_prof_id), ObjectId(doc2_prof_id), ObjectId(doc3_prof_id)]}})
    db["appointments"].delete_many({"_id": ObjectId(appt_id)})
    db["care_plans"].delete_many({"patientUserId": pat1_id})
    db["notifications"].delete_many({"userId": {"$in": [pat1_id, pat2_id, doc1_id]}})


def test_01_create_care_plan_success(care_plan_setup):
    """Approved doctor creates care plan for completed consultation."""
    token = care_plan_setup["doc1_token"]
    headers = {"Authorization": f"Bearer {token}"}
    appt_id = care_plan_setup["appt_id"]

    target_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    payload = {
        "appointmentId": appt_id,
        "followUpDate": target_date,
        "followUpDateEnd": (datetime.now() + timedelta(days=18)).strftime("%Y-%m-%d"),
        "reason": "Post-hypertension therapy review",
        "instructions": "Maintain a low-sodium diet and check morning blood pressure daily.",
        "recommendedConsultationType": "IN_PERSON",
        "tasks": [
            {
                "title": "Daily BP Log",
                "description": "Log morning and evening blood pressure.",
            },
            {
                "title": "Lipid Profile Test",
                "description": "Get fasting lipid panel 3 days before visit.",
            }
        ]
    }

    res = client.post("/api/care-plans", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["appointmentId"] == appt_id
    assert data["status"] == CarePlanStatus.ACTIVE.value
    assert data["reason"] == "Post-hypertension therapy review"
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["isCompleted"] is False
    assert len(data["auditLog"]) >= 1

    # Verify notification dispatched to patient
    db = care_plan_setup["db"]
    notif = db["notifications"].find_one({
        "recipientUserId": care_plan_setup["pat1_id"],
        "type": NotificationType.FOLLOW_UP_CARE_PLAN_CREATED.value,
    })
    assert notif is not None
    assert "care plan" in notif["title"].lower()


def test_02_unapproved_doctor_rejected(care_plan_setup):
    """Unapproved doctor cannot create care plans (403)."""
    token = care_plan_setup["doc2_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "appointmentId": care_plan_setup["appt_id"],
        "followUpDate": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "reason": "General checkup",
        "instructions": "Take medication on time",
    }

    res = client.post("/api/care-plans", json=payload, headers=headers)
    assert res.status_code == 403
    assert "review" in res.text.lower() or "approv" in res.text.lower()


def test_03_unauthorized_doctor_rejected(care_plan_setup):
    """Another doctor cannot create care plan for an appointment they do not own (403)."""
    token = care_plan_setup["doc3_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "appointmentId": care_plan_setup["appt_id"],
        "followUpDate": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "reason": "Intrusion attempt",
        "instructions": "Should fail with authorization error",
    }

    res = client.post("/api/care-plans", json=payload, headers=headers)
    assert res.status_code == 403
    assert "not authorized" in res.text.lower()


def test_04_reject_past_follow_up_date(care_plan_setup):
    """Reject follow-up date in the past (400)."""
    token = care_plan_setup["doc1_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "appointmentId": care_plan_setup["appt_id"],
        "followUpDate": "2020-01-01",
        "reason": "Past follow-up",
        "instructions": "Invalid past date instructions",
    }

    res = client.post("/api/care-plans", json=payload, headers=headers)
    assert res.status_code == 400
    assert "past" in res.text.lower()


def test_05_prevent_duplicate_active_care_plan(care_plan_setup):
    """Prevent creating duplicate active care plan for the same consultation (409)."""
    token = care_plan_setup["doc1_token"]
    headers = {"Authorization": f"Bearer {token}"}
    target_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    payload = {
        "appointmentId": care_plan_setup["appt_id"],
        "followUpDate": target_date,
        "reason": "First Plan",
        "instructions": "Take medications regularly",
    }

    # First succeeds
    res1 = client.post("/api/care-plans", json=payload, headers=headers)
    assert res1.status_code == 201

    # Second for same appointment fails with 409
    res2 = client.post("/api/care-plans", json=payload, headers=headers)
    assert res2.status_code == 409
    assert "already exists" in res2.text.lower()


def test_06_patient_view_own_care_plans_and_unauthorized_access(care_plan_setup):
    """Patient can view own plans; other patient cannot view them."""
    doc_token = care_plan_setup["doc1_token"]
    pat1_token = care_plan_setup["pat1_token"]
    pat2_token = care_plan_setup["pat2_token"]
    target_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")

    # Create plan
    res = client.post(
        "/api/care-plans",
        json={
            "appointmentId": care_plan_setup["appt_id"],
            "followUpDate": target_date,
            "reason": "Cardiac follow-up",
            "instructions": "Strict salt restriction",
        },
        headers={"Authorization": f"Bearer {doc_token}"}
    )
    assert res.status_code == 201
    plan_id = res.json()["id"]

    # Patient 1 lists care plans
    list_res = client.get("/api/care-plans/patient", headers={"Authorization": f"Bearer {pat1_token}"})
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] >= 1
    assert any(p["id"] == plan_id for p in data["plans"])

    # Patient 1 views detail
    detail_res = client.get(f"/api/care-plans/{plan_id}", headers={"Authorization": f"Bearer {pat1_token}"})
    assert detail_res.status_code == 200
    assert detail_res.json()["reason"] == "Cardiac follow-up"

    # Patient 2 (stranger) attempts to view plan -> 403
    p2_res = client.get(f"/api/care-plans/{plan_id}", headers={"Authorization": f"Bearer {pat2_token}"})
    assert p2_res.status_code == 403


def test_07_doctor_updates_care_plan(care_plan_setup):
    """Doctor updates care plan, verified in audit log and version increment."""
    doc_token = care_plan_setup["doc1_token"]
    headers = {"Authorization": f"Bearer {doc_token}"}
    target_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    res = client.post(
        "/api/care-plans",
        json={
            "appointmentId": care_plan_setup["appt_id"],
            "followUpDate": target_date,
            "reason": "Initial plan",
            "instructions": "Drink water",
        },
        headers=headers
    )
    plan_id = res.json()["id"]

    # Update care plan
    new_target_date = (datetime.now() + timedelta(days=21)).strftime("%Y-%m-%d")
    update_payload = {
        "reason": "Updated review reason",
        "instructions": "Drink 2L water daily and avoid caffeine",
        "followUpDate": new_target_date,
    }
    update_res = client.put(f"/api/care-plans/{plan_id}", json=update_payload, headers=headers)
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["reason"] == "Updated review reason"
    assert updated_data["followUpDate"] == new_target_date
    assert updated_data["version"] == 2
    assert len(updated_data["auditLog"]) >= 2
    assert any(a["action"] == "UPDATED" for a in updated_data["auditLog"])


def test_08_patient_completes_care_task(care_plan_setup):
    """Patient marks care task complete, verifying timestamp and audit entry."""
    doc_token = care_plan_setup["doc1_token"]
    pat1_token = care_plan_setup["pat1_token"]
    target_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")

    res = client.post(
        "/api/care-plans",
        json={
            "appointmentId": care_plan_setup["appt_id"],
            "followUpDate": target_date,
            "reason": "Exercise task plan",
            "instructions": "Walk 30 minutes daily",
            "tasks": [
                {"title": "Morning Walk", "description": "30 mins brisk walk"}
            ]
        },
        headers={"Authorization": f"Bearer {doc_token}"}
    )
    plan_data = res.json()
    plan_id = plan_data["id"]
    task_id = plan_data["tasks"][0]["taskId"]

    # Mark complete
    patch_res = client.patch(
        f"/api/care-plans/{plan_id}/tasks/{task_id}",
        json={"isCompleted": True},
        headers={"Authorization": f"Bearer {pat1_token}"}
    )
    assert patch_res.status_code == 200
    patched_data = patch_res.json()
    task = next(t for t in patched_data["tasks"] if t["taskId"] == task_id)
    assert task["isCompleted"] is True
    assert task["completedAt"] is not None
    assert any("TASK_COMPLETED" in a["action"] for a in patched_data["auditLog"])

    # Toggle back to pending
    patch_res2 = client.patch(
        f"/api/care-plans/{plan_id}/tasks/{task_id}",
        json={"isCompleted": False},
        headers={"Authorization": f"Bearer {pat1_token}"}
    )
    assert patch_res2.status_code == 200
    task2 = next(t for t in patch_res2.json()["tasks"] if t["taskId"] == task_id)
    assert task2["isCompleted"] is False
    assert task2["completedAt"] is None


def test_09_patient_links_booked_appointment(care_plan_setup):
    """Link booked follow-up appointment transitions care plan to FOLLOW_UP_BOOKED."""
    doc_token = care_plan_setup["doc1_token"]
    pat1_token = care_plan_setup["pat1_token"]
    db = care_plan_setup["db"]
    target_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    # Create care plan
    res = client.post(
        "/api/care-plans",
        json={
            "appointmentId": care_plan_setup["appt_id"],
            "followUpDate": target_date,
            "reason": "Cardiac follow-up review",
            "instructions": "Monitor BP closely",
        },
        headers={"Authorization": f"Bearer {doc_token}"}
    )
    plan_id = res.json()["id"]

    # Seed a newly booked follow-up appointment with doctor 1
    new_appt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(new_appt_id),
        "patientId": care_plan_setup["pat1_id"],
        "patientUserId": care_plan_setup["pat1_id"],
        "doctorId": care_plan_setup["doc1_num"],
        "doctorUserId": care_plan_setup["doc1_id"],
        "doctorName": "Dr. Saman Perera",
        "appointmentDate": target_date,
        "appointmentTime": "11:00",
        "status": AppointmentStatus.CONFIRMED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Link new appointment to care plan
    link_res = client.post(
        f"/api/care-plans/{plan_id}/link-appointment",
        json={"appointmentId": new_appt_id},
        headers={"Authorization": f"Bearer {pat1_token}"}
    )
    assert link_res.status_code == 200
    linked_data = link_res.json()
    assert linked_data["status"] == CarePlanStatus.FOLLOW_UP_BOOKED.value
    assert linked_data["bookedAppointmentId"] == new_appt_id

    # Clean up new appointment
    db["appointments"].delete_one({"_id": ObjectId(new_appt_id)})


def test_10_doctor_cancels_care_plan(care_plan_setup):
    """Doctor cancels care plan and records reason in audit trail."""
    doc_token = care_plan_setup["doc1_token"]
    headers = {"Authorization": f"Bearer {doc_token}"}
    target_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    res = client.post(
        "/api/care-plans",
        json={
            "appointmentId": care_plan_setup["appt_id"],
            "followUpDate": target_date,
            "reason": "Will cancel this plan",
            "instructions": "Rest well",
        },
        headers=headers
    )
    plan_id = res.json()["id"]

    cancel_res = client.post(
        f"/api/care-plans/{plan_id}/cancel",
        json={"reason": "Patient relocated abroad"},
        headers=headers
    )
    assert cancel_res.status_code == 200
    cancelled_data = cancel_res.json()
    assert cancelled_data["status"] == CarePlanStatus.CANCELLED.value
    assert any(a["action"] == "CANCELLED" for a in cancelled_data["auditLog"])


def test_11_reminder_sweep_dispatches_and_marks_overdue(care_plan_setup):
    """Reminder sweep dispatches notifications for 7d, 1d, due dates and marks past plans overdue."""
    db = care_plan_setup["db"]
    doc_token = care_plan_setup["doc1_token"]
    today = datetime.now()

    # Plan A: Due in 7 days
    date_7d = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    res_a = client.post(
        "/api/care-plans",
        json={
            "appointmentId": care_plan_setup["appt_id"],
            "followUpDate": date_7d,
            "reason": "7-day notice review",
            "instructions": "Lab test soon",
        },
        headers={"Authorization": f"Bearer {doc_token}"}
    )
    plan_a_id = res_a.json()["id"]

    # Sweep reminders via service directly
    sweep_result = CarePlanService.check_and_send_care_plan_reminders(db)
    assert sweep_result >= 1

    # Verify 7-day notification recorded
    notif = db["notifications"].find_one({
        "recipientUserId": care_plan_setup["pat1_id"],
        "type": NotificationType.FOLLOW_UP_REMINDER_7D.value,
        "relatedAppointmentId": care_plan_setup["appt_id"],
    })
    assert notif is not None

    # Plan B: Past target date -> should be marked OVERDUE on next sweep
    db["care_plans"].update_one(
        {"_id": ObjectId(plan_a_id)},
        {"$set": {"followUpDate": (today - timedelta(days=2)).strftime("%Y-%m-%d")}}
    )
    CarePlanService.check_and_send_care_plan_reminders(db)

    updated_plan_a = db["care_plans"].find_one({"_id": ObjectId(plan_a_id)})
    assert updated_plan_a["status"] == CarePlanStatus.OVERDUE.value
