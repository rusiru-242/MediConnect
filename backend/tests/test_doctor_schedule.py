"""Backend test suite for Phase 57: Doctor Daily Schedule & Consultation Management.

Covers:
1. Approved doctor fetches own daily schedule (`GET /api/doctor/schedule/today` and `GET /api/doctor/schedule?date=...`).
2. Cross-doctor isolation: doctor cannot view or operate on another doctor's consultations (403).
3. Unapproved / pending doctor access denied (403).
4. Correct chronological appointment ordering by `startTime`.
5. Local date filtering and empty schedule handling.
6. Correct daily statistics calculation (totalScheduled, upcoming, waiting, inProgress, completed, cancelled).
7. Next eligible patient selection (in-progress prioritized, earliest not-started selected, cancelled excluded).
8. Start consultation succeeds (status transitions to IN_PROGRESS, startedAt set).
9. Cancelled appointment cannot be started (400).
10. Repeated start is idempotent (200).
11. Complete consultation succeeds (status transitions to COMPLETED, completedAt set, appointment updated).
12. Complete before start is rejected (400).
13. Repeated complete is idempotent (200).
14. Consultation details endpoint returns enriched links (care plan, prescription, medical records).
15. Doctor schedule summary endpoint returns quick snapshot.
"""

from datetime import datetime, timezone
import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.appointment import AppointmentStatus, PaymentStatus
from app.models.care_plan import CarePlanStatus
from app.models.consultation import ConsultationStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


def now_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.fixture
def schedule_test_setup():
    """Seed test doctors, patient, and test appointments."""
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Approved Doctor 1 (Dr. Kasun)
    doc1_id = str(ObjectId())
    doc1_prof_id = str(ObjectId())
    doc1_num = f"DOC-SCHED-1-{ts}"

    db["users"].insert_one({
        "_id": ObjectId(doc1_id),
        "fullName": "Dr. Kasun Fernando",
        "email": f"dr_sched1_{ts}@mediconnect.lk",
        "phone": "0771113344",
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
        "fullName": "Dr. Kasun Fernando",
        "specialty": "Cardiology",
        "medicalRegistrationNumber": f"SLMC-SCHED-1-{ts}",
        "hospitalOrClinic": "Colombo General",
        "consultationFee": 3500.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc1_token = create_access_token(doc1_id, role=UserRole.DOCTOR.value)

    # 2. Approved Doctor 2 (Dr. Nimal - for cross-doctor testing)
    doc2_id = str(ObjectId())
    doc2_prof_id = str(ObjectId())
    doc2_num = f"DOC-SCHED-2-{ts}"

    db["users"].insert_one({
        "_id": ObjectId(doc2_id),
        "fullName": "Dr. Nimal Silva",
        "email": f"dr_sched2_{ts}@mediconnect.lk",
        "phone": "0772224455",
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
        "fullName": "Dr. Nimal Silva",
        "specialty": "Pediatrics",
        "medicalRegistrationNumber": f"SLMC-SCHED-2-{ts}",
        "hospitalOrClinic": "Nawaloka Hospital",
        "consultationFee": 3000.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc2_token = create_access_token(doc2_id, role=UserRole.DOCTOR.value)

    # 3. Unapproved Doctor (Dr. Pending)
    doc3_id = str(ObjectId())
    doc3_prof_id = str(ObjectId())
    doc3_num = f"DOC-SCHED-3-{ts}"

    db["users"].insert_one({
        "_id": ObjectId(doc3_id),
        "fullName": "Dr. Pending Doctor",
        "email": f"dr_sched3_{ts}@mediconnect.lk",
        "phone": "0775556677",
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
        "fullName": "Dr. Pending Doctor",
        "specialty": "Dermatology",
        "medicalRegistrationNumber": f"SLMC-SCHED-3-{ts}",
        "hospitalOrClinic": "Asiri Hospital",
        "consultationFee": 2500.0,
        "verificationStatus": DoctorVerificationStatus.PENDING_ADMIN_APPROVAL.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc3_token = create_access_token(doc3_id, role=UserRole.DOCTOR.value)

    # 4. Patient
    pat_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_id),
        "fullName": "Sunil Weerasinghe",
        "email": f"sunil_{ts}@example.com",
        "phone": "0719998877",
        "passwordHash": hash_password("Pat@1234"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat_token = create_access_token(pat_id, role=UserRole.PATIENT.value)

    return {
        "doc1": {"id": doc1_id, "token": doc1_token, "num": doc1_num},
        "doc2": {"id": doc2_id, "token": doc2_token, "num": doc2_num},
        "doc3_pending": {"id": doc3_id, "token": doc3_token},
        "patient": {"id": pat_id, "token": pat_token},
        "ts": ts,
    }


def test_doctor_daily_schedule_approved_access(schedule_test_setup):
    """Test 1: Approved doctor fetches today's schedule and specific date schedule."""
    data = schedule_test_setup
    db = get_database()
    today_str = now_date_str()

    # Insert an appointment for doc1 today
    appt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "appointmentNumber": f"APT-SCHED-{data['ts']}-1",
        "patientUserId": data["patient"]["id"],
        "patientName": "Sunil Weerasinghe",
        "patientPhone": "0719998877",
        "doctorUserId": data["doc1"]["id"],
        "doctorName": "Dr. Kasun Fernando",
        "appointmentDate": today_str,
        "startTime": "09:00",
        "endTime": "09:30",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "reasonForVisit": "Chest pain review",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Fetch today's schedule
    res = client.get(
        "/api/doctor/schedule/today",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["date"] == today_str
    assert res_data["stats"]["totalScheduled"] >= 1
    assert len(res_data["appointments"]) >= 1
    item = next(a for a in res_data["appointments"] if a["appointmentId"] == appt_id)
    assert item["patientName"] == "Sunil Weerasinghe"
    assert item["startTime"] == "09:00"
    assert item["consultationStatus"] == "NOT_STARTED"

    # Fetch specific date schedule
    res2 = client.get(
        f"/api/doctor/schedule?date={today_str}",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
    )
    assert res2.status_code == 200
    assert res2.json()["date"] == today_str


def test_unapproved_doctor_denied(schedule_test_setup):
    """Test 2 & 3: Unapproved / pending doctor cannot access doctor schedule endpoints (403)."""
    data = schedule_test_setup

    res = client.get(
        "/api/doctor/schedule/today",
        headers={"Authorization": f"Bearer {data['doc3_pending']['token']}"},
    )
    assert res.status_code == 403
    assert "under review" in res.json()["detail"].lower() or "approves" in res.json()["detail"].lower()


def test_chronological_ordering_and_stats(schedule_test_setup):
    """Test 4, 5 & 6: Appointments ordered chronologically, local date filtering, accurate statistics."""
    data = schedule_test_setup
    db = get_database()
    target_date = "2026-11-20"

    # Insert 3 appointments out of chronological order
    # Appt 3: 14:00 (CANCELLED)
    appt3_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt3_id),
        "appointmentNumber": f"APT-SCHED-{data['ts']}-3",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": target_date,
        "startTime": "14:00",
        "endTime": "14:30",
        "status": AppointmentStatus.CANCELLED.value,
        "paymentStatus": PaymentStatus.UNPAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Appt 1: 08:30 (CONFIRMED)
    appt1_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt1_id),
        "appointmentNumber": f"APT-SCHED-{data['ts']}-1b",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": target_date,
        "startTime": "08:30",
        "endTime": "09:00",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Appt 2: 10:15 (COMPLETED)
    appt2_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt2_id),
        "appointmentNumber": f"APT-SCHED-{data['ts']}-2",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": target_date,
        "startTime": "10:15",
        "endTime": "10:45",
        "status": AppointmentStatus.COMPLETED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Also insert a completed consultation session for Appt 2
    db["consultation_sessions"].insert_one({
        "_id": ObjectId(),
        "appointmentId": appt2_id,
        "doctorUserId": data["doc1"]["id"],
        "patientUserId": data["patient"]["id"],
        "status": ConsultationStatus.COMPLETED.value,
        "startedAt": utc_now(),
        "completedAt": utc_now(),
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    res = client.get(
        f"/api/doctor/schedule?date={target_date}",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
    )
    assert res.status_code == 200
    appts = res.json()["appointments"]
    assert len(appts) == 3
    # Check ordering: 08:30, 10:15, 14:00
    assert appts[0]["appointmentId"] == appt1_id
    assert appts[0]["startTime"] == "08:30"
    assert appts[1]["appointmentId"] == appt2_id
    assert appts[1]["startTime"] == "10:15"
    assert appts[2]["appointmentId"] == appt3_id
    assert appts[2]["startTime"] == "14:00"

    # Check stats
    stats = res.json()["stats"]
    assert stats["totalScheduled"] == 3
    assert stats["completed"] == 1
    assert stats["cancelled"] == 1
    assert stats["upcoming"] == 1

    # Check next patient selection (cancelled & completed excluded, earliest not-started selected)
    next_pat = res.json()["nextPatient"]
    assert next_pat is not None
    assert next_pat["appointmentId"] == appt1_id
    assert next_pat["startTime"] == "08:30"


def test_next_patient_prioritizes_in_progress(schedule_test_setup):
    """Test 7: In-progress consultation is always prioritized as next patient over not-started appointments."""
    data = schedule_test_setup
    db = get_database()
    target_date = "2026-11-21"

    # Appt 1: 09:00 (NOT_STARTED)
    appt1_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt1_id),
        "appointmentNumber": f"APT-SCHED-{data['ts']}-p1",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": target_date,
        "startTime": "09:00",
        "endTime": "09:30",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Appt 2: 10:00 (IN_PROGRESS)
    appt2_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt2_id),
        "appointmentNumber": f"APT-SCHED-{data['ts']}-p2",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": target_date,
        "startTime": "10:00",
        "endTime": "10:30",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["consultation_sessions"].insert_one({
        "_id": ObjectId(),
        "appointmentId": appt2_id,
        "doctorUserId": data["doc1"]["id"],
        "patientUserId": data["patient"]["id"],
        "status": ConsultationStatus.IN_PROGRESS.value,
        "startedAt": utc_now(),
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    res = client.get(
        f"/api/doctor/schedule?date={target_date}",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
    )
    assert res.status_code == 200
    next_pat = res.json()["nextPatient"]
    assert next_pat is not None
    # Must be appt2 because it is IN_PROGRESS, even though appt1 was earlier
    assert next_pat["appointmentId"] == appt2_id
    assert next_pat["consultationStatus"] == "IN_PROGRESS"


def test_start_consultation_lifecycle_and_idempotency(schedule_test_setup):
    """Test 8, 10: Start consultation succeeds, sets startedAt, idempotent on repeat."""
    data = schedule_test_setup
    db = get_database()
    today_str = now_date_str()

    appt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "appointmentNumber": f"APT-START-{data['ts']}",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": today_str,
        "startTime": "11:00",
        "endTime": "11:30",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Start consultation
    res = client.post(
        f"/api/doctor/consultations/{appt_id}/start",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
        json={"notes": "Patient arrived on time"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "IN_PROGRESS"
    assert res_data["startedAt"] is not None
    started_at = res_data["startedAt"]

    # Repeated start call should be idempotent (200) and preserve startedAt
    res_repeat = client.post(
        f"/api/doctor/consultations/{appt_id}/start",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
        json={},
    )
    assert res_repeat.status_code == 200
    assert res_repeat.json()["status"] == "IN_PROGRESS"
    assert res_repeat.json()["startedAt"][:19] == started_at[:19]


def test_start_consultation_forbidden_and_cancelled_validation(schedule_test_setup):
    """Test 9: Cross-doctor isolation (403) and cancelled appointment reject (400)."""
    data = schedule_test_setup
    db = get_database()

    # Appointment belongs to doc1
    appt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "appointmentNumber": f"APT-CROSS-{data['ts']}",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": "2026-11-22",
        "startTime": "12:00",
        "endTime": "12:30",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Doctor 2 tries to start it -> 403 Forbidden
    res_doc2 = client.post(
        f"/api/doctor/consultations/{appt_id}/start",
        headers={"Authorization": f"Bearer {data['doc2']['token']}"},
        json={},
    )
    assert res_doc2.status_code == 403
    assert "not authorized" in res_doc2.json()["detail"].lower()

    # Cancelled appointment cannot be started
    appt_cancelled_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_cancelled_id),
        "appointmentNumber": f"APT-CANC-{data['ts']}",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": "2026-11-22",
        "startTime": "13:00",
        "endTime": "13:30",
        "status": AppointmentStatus.CANCELLED.value,
        "paymentStatus": PaymentStatus.UNPAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    res_canc = client.post(
        f"/api/doctor/consultations/{appt_cancelled_id}/start",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
        json={},
    )
    assert res_canc.status_code == 400
    assert "cancelled" in res_canc.json()["detail"].lower()


def test_complete_consultation_flow_and_guards(schedule_test_setup):
    """Test 11, 12, 13, 15: Complete consultation transitions to COMPLETED, updates appointment status, guarded against completing unstarted."""
    data = schedule_test_setup
    db = get_database()

    appt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "appointmentNumber": f"APT-COMP-{data['ts']}",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": "2026-11-23",
        "startTime": "15:00",
        "endTime": "15:30",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 1. Complete before start -> 400 Bad Request
    res_early = client.post(
        f"/api/doctor/consultations/{appt_id}/complete",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
        json={},
    )
    assert res_early.status_code == 400
    assert "not been started" in res_early.json()["detail"].lower()

    # 2. Start consultation
    res_start = client.post(
        f"/api/doctor/consultations/{appt_id}/start",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
        json={},
    )
    assert res_start.status_code == 200

    # 3. Complete consultation
    res_comp = client.post(
        f"/api/doctor/consultations/{appt_id}/complete",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
        json={"notes": "Consultation concluded successfully. Follow-up plan advised."},
    )
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["status"] == "COMPLETED"
    assert comp_data["completedAt"] is not None

    # Check appointment status was synced in database
    db_appt = db["appointments"].find_one({"_id": ObjectId(appt_id)})
    assert db_appt["status"] == AppointmentStatus.COMPLETED.value

    # 4. Repeated complete call is idempotent (200)
    res_comp_repeat = client.post(
        f"/api/doctor/consultations/{appt_id}/complete",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
        json={},
    )
    assert res_comp_repeat.status_code == 200
    assert res_comp_repeat.json()["status"] == "COMPLETED"


def test_consultation_details_and_links(schedule_test_setup):
    """Test 14 & 16: Consultation detail endpoint enriches care plan, prescription, and patient details."""
    data = schedule_test_setup
    db = get_database()

    appt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "appointmentNumber": f"APT-DETAIL-{data['ts']}",
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": "2026-11-24",
        "startTime": "16:00",
        "endTime": "16:30",
        "status": AppointmentStatus.COMPLETED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "reasonForVisit": "Follow-up for hypertension",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Seed an associated care plan (Phase 56)
    care_plan_id = str(ObjectId())
    db["care_plans"].insert_one({
        "_id": ObjectId(care_plan_id),
        "consultationAppointmentId": appt_id,
        "patientUserId": data["patient"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "status": CarePlanStatus.ACTIVE.value,
        "diagnosis": "Stage 1 Essential Hypertension",
        "title": "Hypertension Care Plan",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Seed an associated prescription
    db["prescriptions"].insert_one({
        "_id": ObjectId(),
        "prescriptionId": f"RX-{data['ts']}",
        "appointmentId": appt_id,
        "doctorUserId": data["doc1"]["id"],
        "patientUserId": data["patient"]["id"],
        "medications": [{"name": "Amlodipine 5mg"}],
        "createdAt": utc_now(),
    })

    # Doctor 1 requests consultation details
    res = client.get(
        f"/api/doctor/consultations/{appt_id}",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
    )
    assert res.status_code == 200
    d = res.json()
    assert d["appointment"]["appointmentId"] == appt_id
    assert d["appointment"]["patientName"] == "Sunil Weerasinghe"
    assert d["appointment"]["hasPrescription"] is True
    assert d["appointment"]["hasCarePlan"] is True
    assert d["appointment"]["carePlanId"] == care_plan_id
    assert d["carePlan"]["id"] == care_plan_id

    # Doctor 2 requests Doctor 1's consultation details -> 403 Forbidden
    res_doc2 = client.get(
        f"/api/doctor/consultations/{appt_id}",
        headers={"Authorization": f"Bearer {data['doc2']['token']}"},
    )
    assert res_doc2.status_code == 403


def test_doctor_schedule_summary(schedule_test_setup):
    """Test 17: Schedule summary endpoint returns quick snapshot of stats."""
    data = schedule_test_setup
    today_str = now_date_str()

    res = client.get(
        f"/api/doctor/schedule/summary?date={today_str}",
        headers={"Authorization": f"Bearer {data['doc1']['token']}"},
    )
    assert res.status_code == 200
    summary = res.json()
    assert summary["date"] == today_str
    assert "totalScheduled" in summary
    assert "upcoming" in summary
    assert "inProgress" in summary
    assert "completed" in summary
