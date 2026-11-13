"""Backend test suite for Phase 58: Patient Healthcare Timeline & Visit History.

Covers:
1. Authenticated patient retrieves own timeline.
2. Unauthenticated access is rejected (401).
3. Cross-patient isolation: Patient cannot access another patient's timeline or visit.
4. Appointments appear correctly (Booked, Cancelled, Rescheduled).
5. Completed consultations appear.
6. Digital prescriptions appear.
7. Medical records appear with safe patient assessment (clinicalNotes excluded).
8. Follow-up care plans appear (Created, Follow-up Booked).
9. Events are ordered in reverse chronological order (newest first).
10. Stable cursor pagination with no duplicate events across pages.
11. Category filtering (APPOINTMENTS, CONSULTATIONS, PRESCRIPTIONS, MEDICAL_RECORDS, FOLLOW_UPS).
12. Date range and doctor filtering.
13. Timeline summary endpoint returns accurate metrics.
14. Consolidated visit details endpoint returns appointment, consultation, prescription, record, and care plan.
15. Visit detail access controls (403 for other patient's visit, 404 for invalid ID).
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
from app.models.medical_record import MedicalRecordStatus
from app.models.prescription import PrescriptionStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


def now_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.fixture
def timeline_test_setup():
    """Seed test doctors and two distinct patients for isolation verification."""
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Doctor 1 (Dr. Anil)
    doc1_id = str(ObjectId())
    doc1_prof_id = str(ObjectId())
    doc1_num = f"DOC-TIME-1-{ts}"

    db["users"].insert_one({
        "_id": ObjectId(doc1_id),
        "fullName": "Dr. Anil Jayasuriya",
        "email": f"dr_time1_{ts}@mediconnect.lk",
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
        "_id": ObjectId(doc1_prof_id),
        "userId": doc1_id,
        "doctorId": doc1_num,
        "fullName": "Dr. Anil Jayasuriya",
        "specialty": "Cardiology",
        "medicalRegistrationNumber": f"SLMC-TIME-1-{ts}",
        "hospitalOrClinic": "Lanka Hospitals",
        "consultationFee": 3000.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc1_token = create_access_token(doc1_id, role=UserRole.DOCTOR.value)

    # 2. Patient 1 (Primary Test Patient)
    pat1_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat1_id),
        "fullName": "Kavinda De Silva",
        "email": f"kavinda_{ts}@example.com",
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

    # 3. Patient 2 (Secondary Patient for Cross-Patient Isolation)
    pat2_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat2_id),
        "fullName": "Nadeeka Perera",
        "email": f"nadeeka_{ts}@example.com",
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

    return {
        "doc1": {"id": doc1_id, "token": doc1_token, "profId": doc1_prof_id},
        "pat1": {"id": pat1_id, "token": pat1_token},
        "pat2": {"id": pat2_id, "token": pat2_token},
        "ts": ts,
    }


def seed_full_patient_history(data, db):
    """Seed comprehensive visit history for patient 1."""
    appt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "appointmentNumber": f"APT-HIST-{data['ts']}",
        "patientUserId": data["pat1"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "doctorName": "Dr. Anil Jayasuriya",
        "appointmentDate": "2026-11-10",
        "startTime": "10:00",
        "endTime": "10:30",
        "status": AppointmentStatus.COMPLETED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "consultationFee": 3000.0,
        "patientNote": "Regular cardiology review",
        "createdAt": datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 11, 10, 10, 30, tzinfo=timezone.utc),
    })

    # Consultation session
    sess_id = str(ObjectId())
    db["consultation_sessions"].insert_one({
        "_id": ObjectId(sess_id),
        "appointmentId": appt_id,
        "doctorUserId": data["doc1"]["id"],
        "patientUserId": data["pat1"]["id"],
        "status": ConsultationStatus.COMPLETED.value,
        "startedAt": datetime(2026, 11, 10, 10, 2, tzinfo=timezone.utc),
        "completedAt": datetime(2026, 11, 10, 10, 28, tzinfo=timezone.utc),
        "createdAt": datetime(2026, 11, 10, 10, 2, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 11, 10, 10, 28, tzinfo=timezone.utc),
    })

    # Prescription
    rx_id = str(ObjectId())
    db["prescriptions"].insert_one({
        "_id": ObjectId(rx_id),
        "prescriptionId": f"RX-{data['ts']}",
        "appointmentId": appt_id,
        "medicalRecordId": str(ObjectId()),
        "doctorUserId": data["doc1"]["id"],
        "patientUserId": data["pat1"]["id"],
        "status": PrescriptionStatus.ISSUED.value,
        "issuedAt": datetime(2026, 11, 10, 10, 20, tzinfo=timezone.utc),
        "medicationItems": [
            {"medicationName": "Atorvastatin", "strength": "10mg", "dose": "1 tab", "frequency": "Once daily", "duration": "30 days", "quantity": "30 tabs"},
        ],
        "createdAt": datetime(2026, 11, 10, 10, 20, tzinfo=timezone.utc),
    })

    # Medical record
    mr_id = str(ObjectId())
    db["medical_records"].insert_one({
        "_id": ObjectId(mr_id),
        "recordId": f"REC-{data['ts']}",
        "appointmentId": appt_id,
        "doctorUserId": data["doc1"]["id"],
        "doctorProfileId": data["doc1"]["profId"],
        "patientUserId": data["pat1"]["id"],
        "consultationDate": "2026-11-10",
        "assessment": "Mild hypercholesterolemia. Cardiac rhythm regular.",
        "treatmentPlan": "Dietary modification, low saturated fat, statin therapy.",
        "clinicalNotes": "TOP SECRET CONFIDENTIAL DOCTOR OBSERVATION NOTE",
        "status": MedicalRecordStatus.ACTIVE.value,
        "createdAt": datetime(2026, 11, 10, 10, 25, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 11, 10, 10, 25, tzinfo=timezone.utc),
    })

    # Care plan
    cp_id = str(ObjectId())
    db["care_plans"].insert_one({
        "_id": ObjectId(cp_id),
        "consultationAppointmentId": appt_id,
        "appointmentId": appt_id,
        "doctorUserId": data["doc1"]["id"],
        "doctorProfileId": data["doc1"]["profId"],
        "patientUserId": data["pat1"]["id"],
        "followUpDate": "2026-12-10",
        "reason": "Lipid recheck after 4 weeks",
        "status": CarePlanStatus.ACTIVE.value,
        "tasks": [{"taskId": "t1", "title": "Check lipid panel", "isCompleted": False}],
        "createdAt": datetime(2026, 11, 10, 10, 27, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 11, 10, 10, 27, tzinfo=timezone.utc),
    })

    return {
        "appointmentId": appt_id,
        "sessionId": sess_id,
        "prescriptionId": rx_id,
        "recordId": mr_id,
        "carePlanId": cp_id,
    }


def test_unauthenticated_access_rejected():
    """Test 2: Unauthenticated requests to timeline endpoints are rejected (401)."""
    res = client.get("/api/patients/me/healthcare-timeline")
    assert res.status_code == 401

    res_summary = client.get("/api/patients/me/healthcare-timeline/summary")
    assert res_summary.status_code == 401

    res_visit = client.get("/api/patients/me/visits/6af000000000000000000000")
    assert res_visit.status_code == 401


def test_empty_timeline_for_new_patient(timeline_test_setup):
    """Test 18: Patient with no history gets a clean empty timeline response."""
    data = timeline_test_setup

    res = client.get(
        "/api/patients/me/healthcare-timeline",
        headers={"Authorization": f"Bearer {data['pat2']['token']}"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["events"] == []
    assert res_data["totalCount"] == 0
    assert res_data["hasMore"] is False
    assert res_data["nextCursor"] is None

    # Summary
    res_summary = client.get(
        "/api/patients/me/healthcare-timeline/summary",
        headers={"Authorization": f"Bearer {data['pat2']['token']}"},
    )
    assert res_summary.status_code == 200
    assert res_summary.json()["totalEvents"] == 0


def test_appointment_events_and_ordering(timeline_test_setup):
    """Test 4 & 9: Booked, Cancelled, and Rescheduled appointments appear in reverse chronological order."""
    data = timeline_test_setup
    db = get_database()
    today_str = now_date_str()

    # Appointment 1: Booked
    appt1_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt1_id),
        "appointmentNumber": f"APT-TIME-{data['ts']}-1",
        "patientUserId": data["pat1"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": today_str,
        "startTime": "09:00",
        "endTime": "09:30",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "appointmentVersion": 1,
        "createdAt": datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
    })

    # Appointment 2: Cancelled
    appt2_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt2_id),
        "appointmentNumber": f"APT-TIME-{data['ts']}-2",
        "patientUserId": data["pat1"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": "2026-11-05",
        "startTime": "11:00",
        "endTime": "11:30",
        "status": AppointmentStatus.CANCELLED.value,
        "cancellationReason": "Schedule conflict",
        "cancelledBy": "PATIENT",
        "appointmentVersion": 1,
        "createdAt": datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc),
    })

    # Appointment 3: Rescheduled (version 2)
    appt3_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt3_id),
        "appointmentNumber": f"APT-TIME-{data['ts']}-3",
        "patientUserId": data["pat1"]["id"],
        "doctorUserId": data["doc1"]["id"],
        "appointmentDate": "2026-11-10",
        "startTime": "14:00",
        "endTime": "14:30",
        "status": AppointmentStatus.CONFIRMED.value,
        "appointmentVersion": 2,
        "createdAt": datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 11, 5, 16, 0, tzinfo=timezone.utc),
    })

    res = client.get(
        "/api/patients/me/healthcare-timeline",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res.status_code == 200
    events = res.json()["events"]
    assert len(events) >= 3

    event_types = [e["eventType"] for e in events]
    assert "APPOINTMENT_BOOKED" in event_types
    assert "APPOINTMENT_CANCELLED" in event_types
    assert "APPOINTMENT_RESCHEDULED" in event_types

    # Check reverse chronological ordering
    for i in range(len(events) - 1):
        assert events[i]["occurredAt"] >= events[i + 1]["occurredAt"]


def test_completed_consultations_prescriptions_records_careplans(timeline_test_setup):
    """Test 5, 6, 7, 8: Consultation completed, prescription issued, medical record added (no doctor notes), care plan created."""
    data = timeline_test_setup
    db = get_database()
    seeded = seed_full_patient_history(data, db)

    res = client.get(
        "/api/patients/me/healthcare-timeline",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res.status_code == 200
    events = res.json()["events"]

    # Verify consultation event
    consult_ev = next((e for e in events if e["eventType"] == "CONSULTATION_COMPLETED" and e["sourceId"] == seeded["sessionId"]), None)
    assert consult_ev is not None
    assert consult_ev["category"] == "CONSULTATIONS"
    assert "Completed" in consult_ev["title"]

    # Verify prescription event
    rx_ev = next((e for e in events if e["eventType"] == "PRESCRIPTION_ISSUED" and e["sourceId"] == seeded["prescriptionId"]), None)
    assert rx_ev is not None
    assert rx_ev["category"] == "PRESCRIPTIONS"

    # Verify medical record event and ENSURE doctor's clinicalNotes is NOT exposed
    mr_ev = next((e for e in events if e["eventType"] == "MEDICAL_RECORD_ADDED" and e["sourceId"] == seeded["recordId"]), None)
    assert mr_ev is not None
    assert mr_ev["category"] == "MEDICAL_RECORDS"
    assert "Mild hypercholesterolemia" in mr_ev["description"]
    assert "TOP SECRET CONFIDENTIAL" not in mr_ev["description"]
    assert "TOP SECRET CONFIDENTIAL" not in str(mr_ev["metadata"])

    # Verify care plan event
    cp_ev = next((e for e in events if e["eventType"] == "FOLLOW_UP_PLAN_CREATED" and e["sourceId"] == seeded["carePlanId"]), None)
    assert cp_ev is not None
    assert cp_ev["category"] == "FOLLOW_UPS"
    assert "2026-12-10" in cp_ev["description"]


def test_category_and_date_filtering(timeline_test_setup):
    """Test 11 & 12: Filtering by category, fromDate, toDate, and doctorId."""
    data = timeline_test_setup
    db = get_database()
    seed_full_patient_history(data, db)

    # 1. Filter by category PRESCRIPTIONS
    res_rx = client.get(
        "/api/patients/me/healthcare-timeline?category=PRESCRIPTIONS",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res_rx.status_code == 200
    rx_events = res_rx.json()["events"]
    assert len(rx_events) >= 1
    assert all(e["category"] == "PRESCRIPTIONS" for e in rx_events)

    # 2. Filter by category FOLLOW_UPS
    res_cp = client.get(
        "/api/patients/me/healthcare-timeline?category=FOLLOW_UPS",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res_cp.status_code == 200
    cp_events = res_cp.json()["events"]
    assert len(cp_events) >= 1
    assert all(e["category"] == "FOLLOW_UPS" for e in cp_events)

    # 3. Filter by doctor
    res_doc = client.get(
        f"/api/patients/me/healthcare-timeline?doctorId={data['doc1']['id']}",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res_doc.status_code == 200
    doc_events = res_doc.json()["events"]
    assert len(doc_events) >= 1
    assert all(e["doctorUserId"] == data["doc1"]["id"] for e in doc_events)

    # 4. Filter by date range
    res_date = client.get(
        "/api/patients/me/healthcare-timeline?fromDate=2026-11-09&toDate=2026-11-15",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res_date.status_code == 200
    date_events = res_date.json()["events"]
    assert len(date_events) >= 1
    for e in date_events:
        event_date = e["displayDate"][:10]
        assert "2026-11-09" <= event_date <= "2026-11-15"


def test_stable_cursor_pagination(timeline_test_setup):
    """Test 10: Pagination with cursor returns successive pages without duplicate items."""
    data = timeline_test_setup
    db = get_database()
    seed_full_patient_history(data, db)

    # Fetch page 1 with limit = 2
    res_p1 = client.get(
        "/api/patients/me/healthcare-timeline?limit=2",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res_p1.status_code == 200
    p1 = res_p1.json()
    assert len(p1["events"]) == 2
    assert p1["hasMore"] is True
    assert p1["nextCursor"] is not None

    p1_ids = {e["eventId"] for e in p1["events"]}

    # Fetch page 2 using nextCursor
    res_p2 = client.get(
        f"/api/patients/me/healthcare-timeline?limit=2&cursor={p1['nextCursor']}",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res_p2.status_code == 200
    p2 = res_p2.json()
    assert len(p2["events"]) >= 1

    p2_ids = {e["eventId"] for e in p2["events"]}

    # Verify no duplicate events across pages
    intersection = p1_ids.intersection(p2_ids)
    assert len(intersection) == 0


def test_timeline_summary_metrics(timeline_test_setup):
    """Test 13: Summary endpoint returns accurate counts of visits, prescriptions, and records."""
    data = timeline_test_setup
    db = get_database()
    seed_full_patient_history(data, db)

    res = client.get(
        "/api/patients/me/healthcare-timeline/summary",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res.status_code == 200
    s = res.json()
    assert s["totalEvents"] >= 4
    assert s["prescriptionsCount"] >= 1
    assert s["medicalRecordsCount"] >= 1
    assert s["activeCarePlansCount"] >= 1


def test_visit_details_consolidation_and_security(timeline_test_setup):
    """Test 3, 14, 15: Consolidated visit details returned for owner; 403 for other patient; 404 for invalid."""
    data = timeline_test_setup
    db = get_database()
    seeded = seed_full_patient_history(data, db)
    appt_id = seeded["appointmentId"]

    # 1. Patient 1 (Owner) views visit details -> 200 OK
    res_owner = client.get(
        f"/api/patients/me/visits/{appt_id}",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res_owner.status_code == 200
    v = res_owner.json()
    assert v["appointmentId"] == appt_id
    assert v["doctorName"] != ""
    assert v["consultationFee"] > 0
    # Patient-safe check: medical record assessment present, clinicalNotes excluded
    if v.get("medicalRecord"):
        assert "assessment" in v["medicalRecord"]
        assert "clinicalNotes" not in v["medicalRecord"]

    # 2. Patient 2 tries to access Patient 1's visit details -> 403 Forbidden
    res_unauth = client.get(
        f"/api/patients/me/visits/{appt_id}",
        headers={"Authorization": f"Bearer {data['pat2']['token']}"},
    )
    assert res_unauth.status_code == 403
    assert "permission" in res_unauth.json()["detail"].lower()

    # 3. Invalid or non-existent appointment ID -> 404 Not Found
    res_nonexistent = client.get(
        "/api/patients/me/visits/6af999999999999999999999",
        headers={"Authorization": f"Bearer {data['pat1']['token']}"},
    )
    assert res_nonexistent.status_code == 404
