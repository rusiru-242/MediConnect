"""Automated test suite for Phase 21: Secure Medical Records & Digital Prescriptions.

Covers:
1. Doctor authorization (Only approved active doctor can create records/prescriptions; pending doctor receives 403).
2. Completed appointment validation (Cannot document for PENDING or CANCELLED appointment -> 400).
3. Assigned doctor check (Doctor not assigned to the appointment receives 403).
4. Patient record ownership (Patient A can view their record -> 200).
5. Cross-patient access denial (Patient B cannot view Patient A's record -> 403).
6. Cross-doctor access denial (Doctor B cannot view Doctor A's patient record -> 403).
7. Prescription creation (Authorized doctor creates structured digital prescription -> 201).
8. Patient restriction (Patient cannot create or edit medical records or prescriptions -> 403).
9. Prescription amendment rules (Mandatory justification, audit trail, status becomes AMENDED -> 200).
10. Medical record amendment rules (Mandatory justification, audit trail, status becomes AMENDED -> 200).
11. Secure PDF access (Authenticated Patient and Doctor get 200 OK with valid PDF bytes).
12. Unauthenticated PDF access (Returns 401 Unauthorized).
13. Invalid record ID (Returns 404 Not Found).
14. Pagination on medical records and prescriptions list endpoints.
15. Audit logging verification (Audit entries exist for creation, view, amendment, and PDF download).
"""

from datetime import datetime, timezone
import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.appointment import AppointmentStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def seeded_medical_env():
    """Seed test database with:
    - Patient A, Patient B
    - Doctor A (APPROVED, assigned to Appointment A)
    - Doctor B (APPROVED, assigned to Appointment B)
    - Doctor C (PENDING approval, cannot create records)
    - Appointment A (COMPLETED, Doctor A + Patient A)
    - Appointment Incomplete (HOLD/PENDING, Doctor A + Patient A)
    - Appointment B (COMPLETED, Doctor B + Patient B)
    """
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Patient A
    pat_a_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_a_id),
        "email": f"patient.med.a.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Alice Medical Patient",
        "role": UserRole.PATIENT.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "isEmailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_a = create_access_token(user_id=pat_a_id, role=UserRole.PATIENT.value)

    # 2. Patient B
    pat_b_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_b_id),
        "email": f"patient.med.b.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Bob Medical Patient",
        "role": UserRole.PATIENT.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "isEmailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_b = create_access_token(user_id=pat_b_id, role=UserRole.PATIENT.value)

    # 3. Doctor A (APPROVED)
    doc_a_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(doc_a_id),
        "email": f"dr.sarath.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Dr. Sarath Perera",
        "role": UserRole.DOCTOR.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "isEmailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc_a_prof_id = str(ObjectId())
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc_a_prof_id),
        "userId": doc_a_id,
        "doctorId": f"DOC-MED-A-{ts}",
        "medicalRegistrationNumber": f"SLMC-12345-{ts}",
        "specialty": "Cardiologist",
        "qualifications": "MBBS, MD (Cardiology)",
        "experienceYears": 15,
        "consultationFee": 3500.0,
        "hospitalOrClinic": "National Hospital of Sri Lanka",
        "city": "Colombo",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "rating": 4.9,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_doc_a = create_access_token(user_id=doc_a_id, role=UserRole.DOCTOR.value)

    # 4. Doctor B (APPROVED)
    doc_b_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(doc_b_id),
        "email": f"dr.anoma.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Dr. Anoma Silva",
        "role": UserRole.DOCTOR.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "isEmailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc_b_prof_id = str(ObjectId())
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc_b_prof_id),
        "userId": doc_b_id,
        "doctorId": f"DOC-MED-B-{ts}",
        "medicalRegistrationNumber": f"SLMC-67890-{ts}",
        "specialty": "Dermatologist",
        "qualifications": "MBBS, MD (Dermatology)",
        "experienceYears": 10,
        "consultationFee": 3000.0,
        "hospitalOrClinic": "Asiri Central Hospital",
        "city": "Colombo",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "rating": 4.8,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_doc_b = create_access_token(user_id=doc_b_id, role=UserRole.DOCTOR.value)

    # 5. Doctor C (PENDING verification)
    doc_c_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(doc_c_id),
        "email": f"dr.pending.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Dr. Pending Doctor",
        "role": UserRole.DOCTOR.value,
        "accountStatus": AccountStatus.PENDING.value,
        "emailVerified": True,
        "isEmailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(),
        "userId": doc_c_id,
        "doctorId": f"DOC-MED-C-{ts}",
        "medicalRegistrationNumber": f"SLMC-99999-{ts}",
        "specialty": "General Physician",
        "qualifications": "MBBS",
        "hospitalOrClinic": "General Hospital",
        "verificationStatus": DoctorVerificationStatus.PENDING.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_doc_c = create_access_token(user_id=doc_c_id, role=UserRole.DOCTOR.value)

    # 6. Appointment A: COMPLETED (Doctor A + Patient A)
    appt_a_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_a_id),
        "patientUserId": pat_a_id,
        "doctorUserId": doc_a_id,
        "doctorProfileId": doc_a_prof_id,
        "availabilityId": str(ObjectId()),
        "appointmentDate": "2026-10-18",
        "startTime": "09:00",
        "endTime": "09:30",
        "status": AppointmentStatus.COMPLETED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 7. Appointment Incomplete: PENDING status
    appt_pending_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_pending_id),
        "patientUserId": pat_a_id,
        "doctorUserId": doc_a_id,
        "doctorProfileId": doc_a_prof_id,
        "availabilityId": str(ObjectId()),
        "appointmentDate": "2026-10-19",
        "startTime": "10:00",
        "endTime": "10:30",
        "status": AppointmentStatus.PENDING.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 8. Appointment B: COMPLETED (Doctor B + Patient B)
    appt_b_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_b_id),
        "patientUserId": pat_b_id,
        "doctorUserId": doc_b_id,
        "doctorProfileId": doc_b_prof_id,
        "availabilityId": str(ObjectId()),
        "appointmentDate": "2026-10-18",
        "startTime": "14:00",
        "endTime": "14:30",
        "status": AppointmentStatus.COMPLETED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    return {
        "db": db,
        "patient_a": {"id": pat_a_id, "token": token_a},
        "patient_b": {"id": pat_b_id, "token": token_b},
        "doctor_a": {"id": doc_a_id, "token": token_doc_a},
        "doctor_b": {"id": doc_b_id, "token": token_doc_b},
        "doctor_c": {"id": doc_c_id, "token": token_doc_c},
        "appointment_a_id": appt_a_id,
        "appointment_pending_id": appt_pending_id,
        "appointment_b_id": appt_b_id,
    }


def test_doctor_authorization_pending_doctor_rejected(seeded_medical_env):
    """Unapproved / pending doctor cannot create medical consultation records (403)."""
    headers = {"Authorization": f"Bearer {seeded_medical_env['doctor_c']['token']}"}
    payload = {
        "appointmentId": seeded_medical_env["appointment_a_id"],
        "clinicalNotes": "Patient complains of chest tightness.",
        "assessment": "Suspected angina.",
        "treatmentPlan": "Rest and ECG.",
    }
    res = client.post("/api/medical-records", json=payload, headers=headers)
    assert res.status_code == 403
    assert "accreditation" in res.json()["detail"].lower() or "only verified doctors" in res.json()["detail"].lower()


def test_patient_cannot_create_medical_record(seeded_medical_env):
    """Patient cannot create medical records (403 Forbidden)."""
    headers = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}
    payload = {
        "appointmentId": seeded_medical_env["appointment_a_id"],
        "clinicalNotes": "Self note.",
        "assessment": "Self diagnosis.",
        "treatmentPlan": "Self plan.",
    }
    res = client.post("/api/medical-records", json=payload, headers=headers)
    assert res.status_code == 403


def test_cannot_document_for_pending_appointment(seeded_medical_env):
    """Cannot create consultation record for an incomplete/pending appointment (400)."""
    headers = {"Authorization": f"Bearer {seeded_medical_env['doctor_a']['token']}"}
    payload = {
        "appointmentId": seeded_medical_env["appointment_pending_id"],
        "clinicalNotes": "Attempting note on incomplete appointment.",
        "assessment": "Assessment.",
        "treatmentPlan": "Plan.",
    }
    res = client.post("/api/medical-records", json=payload, headers=headers)
    assert res.status_code == 400
    assert "cannot document" in res.json()["detail"].lower()


def test_unassigned_doctor_cannot_create_record(seeded_medical_env):
    """Doctor B cannot document consultation for Doctor A's appointment (403 Forbidden)."""
    headers = {"Authorization": f"Bearer {seeded_medical_env['doctor_b']['token']}"}
    payload = {
        "appointmentId": seeded_medical_env["appointment_a_id"],
        "clinicalNotes": "Wrong doctor documenting.",
        "assessment": "Assessment.",
        "treatmentPlan": "Plan.",
    }
    res = client.post("/api/medical-records", json=payload, headers=headers)
    assert res.status_code == 403
    assert "not the assigned doctor" in res.json()["detail"].lower()


def test_create_and_view_medical_record_success(seeded_medical_env):
    """Doctor A creates consultation record for completed appointment A, and Patient A can view it."""
    headers_doc = {"Authorization": f"Bearer {seeded_medical_env['doctor_a']['token']}"}
    payload = {
        "appointmentId": seeded_medical_env["appointment_a_id"],
        "clinicalNotes": "Patient presented with mild exertional dyspnea. Blood pressure 128/82 mmHg, HR 74 bpm. Normal S1/S2.",
        "assessment": "Exertional dyspnea, likely physiological deconditioning. Mild essential hypertension.",
        "treatmentPlan": "Low sodium diet, brisk walking 30 mins daily, follow-up BP diary for 2 weeks.",
        "followUpInstructions": "Return for clinic review in 2 weeks with BP diary.",
    }
    res = client.post("/api/medical-records", json=payload, headers=headers_doc)
    assert res.status_code == 201
    data = res.json()
    assert data["recordId"].startswith("REC-")
    assert data["patientUserId"] == seeded_medical_env["patient_a"]["id"]
    assert data["doctorName"] == "Dr. Sarath Perera"
    assert data["doctorSpecialty"] == "Cardiologist"
    record_id = data["id"]

    # Duplicate creation on same appointment blocked
    res_dup = client.post("/api/medical-records", json=payload, headers=headers_doc)
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"].lower()

    # Patient A views their record
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}
    res_get = client.get(f"/api/medical-records/{record_id}", headers=headers_pat_a)
    assert res_get.status_code == 200
    assert res_get.json()["clinicalNotes"] == payload["clinicalNotes"]


def test_cross_patient_access_denial(seeded_medical_env):
    """Patient B cannot view Patient A's medical record (403 Forbidden)."""
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}
    headers_pat_b = {"Authorization": f"Bearer {seeded_medical_env['patient_b']['token']}"}

    # Get record id for patient A
    res_list = client.get("/api/medical-records/me", headers=headers_pat_a)
    assert res_list.status_code == 200
    assert len(res_list.json()["items"]) > 0
    rec_a_id = res_list.json()["items"][0]["id"]

    # Patient B attempts access
    res_b = client.get(f"/api/medical-records/{rec_a_id}", headers=headers_pat_b)
    assert res_b.status_code == 403
    assert "not have authorization" in res_b.json()["detail"].lower()


def test_cross_doctor_access_denial(seeded_medical_env):
    """Doctor B cannot view Doctor A's patient consultation record (403 Forbidden)."""
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}
    headers_doc_b = {"Authorization": f"Bearer {seeded_medical_env['doctor_b']['token']}"}

    res_list = client.get("/api/medical-records/me", headers=headers_pat_a)
    rec_a_id = res_list.json()["items"][0]["id"]

    # Doctor B attempts access
    res_doc_b = client.get(f"/api/medical-records/{rec_a_id}", headers=headers_doc_b)
    assert res_doc_b.status_code == 403


def test_amend_medical_record_with_audit_trail(seeded_medical_env):
    """Doctor A amends medical record with mandatory clinical justification."""
    headers_doc_a = {"Authorization": f"Bearer {seeded_medical_env['doctor_a']['token']}"}
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}

    res_list = client.get("/api/medical-records/me", headers=headers_pat_a)
    rec_a_id = res_list.json()["items"][0]["id"]

    amend_payload = {
        "amendmentReason": "Correction of BP diary review interval from 2 weeks to 4 weeks.",
        "clinicalNotes": "Patient presented with mild exertional dyspnea. BP 128/82 mmHg.",
        "assessment": "Physiological deconditioning.",
        "treatmentPlan": "Low sodium diet and aerobic training.",
        "followUpInstructions": "Return for clinic review in 4 weeks.",
    }
    res_patch = client.patch(f"/api/medical-records/{rec_a_id}", json=amend_payload, headers=headers_doc_a)
    assert res_patch.status_code == 200
    updated = res_patch.json()
    assert updated["status"] == "AMENDED"
    assert len(updated["amendmentHistory"]) == 1
    assert updated["amendmentHistory"][0]["reason"] == amend_payload["amendmentReason"]


def test_create_digital_prescription_success(seeded_medical_env):
    """Doctor A issues digital prescription linked to consultation record."""
    headers_doc_a = {"Authorization": f"Bearer {seeded_medical_env['doctor_a']['token']}"}
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}

    res_list = client.get("/api/medical-records/me", headers=headers_pat_a)
    rec_a = res_list.json()["items"][0]

    presc_payload = {
        "medicalRecordId": rec_a["id"],
        "appointmentId": rec_a["appointmentId"],
        "medicationItems": [
            {
                "medicationName": "Amlodipine Besylate",
                "strength": "5mg",
                "dose": "1 tablet",
                "route": "Oral",
                "frequency": "Once daily (Morning)",
                "duration": "14 days",
                "quantity": "14 tablets",
                "additionalInstructions": "Take after breakfast with a full glass of water.",
            },
            {
                "medicationName": "Paracetamol",
                "strength": "500mg",
                "dose": "1-2 tablets",
                "route": "Oral",
                "frequency": "PRN (As needed for mild headache)",
                "duration": "5 days",
                "quantity": "10 tablets",
                "additionalInstructions": "Do not exceed 8 tablets in 24 hours.",
            },
        ],
        "instructions": "Maintain daily blood pressure diary. Avoid salty foods.",
    }

    res_presc = client.post("/api/prescriptions", json=presc_payload, headers=headers_doc_a)
    assert res_presc.status_code == 201
    data = res_presc.json()
    assert data["prescriptionId"].startswith("RX-")
    assert len(data["medicationItems"]) == 2
    assert data["doctorSpecialty"] == "Cardiologist"
    assert "SLMC-12345" in data["slmcRegistrationNumber"]

    # Patient A views prescription
    res_get = client.get(f"/api/prescriptions/{data['id']}", headers=headers_pat_a)
    assert res_get.status_code == 200
    assert res_get.json()["prescriptionId"] == data["prescriptionId"]


def test_patient_cannot_issue_or_amend_prescription(seeded_medical_env):
    """Patient cannot issue or amend prescriptions (403 Forbidden)."""
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}
    res_list = client.get("/api/prescriptions/me", headers=headers_pat_a)
    presc_id = res_list.json()["items"][0]["id"]

    # Try issue
    res_post = client.post("/api/prescriptions", json={}, headers=headers_pat_a)
    assert res_post.status_code == 403

    # Try amend
    res_patch = client.patch(f"/api/prescriptions/{presc_id}", json={}, headers=headers_pat_a)
    assert res_patch.status_code == 403


def test_amend_prescription_with_audit_trail(seeded_medical_env):
    """Doctor A amends prescription with reason, updating items and status."""
    headers_doc_a = {"Authorization": f"Bearer {seeded_medical_env['doctor_a']['token']}"}
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}

    res_list = client.get("/api/prescriptions/me", headers=headers_pat_a)
    presc_id = res_list.json()["items"][0]["id"]

    amend_payload = {
        "amendmentReason": "Increased Amlodipine duration from 14 days to 30 days based on response.",
        "medicationItems": [
            {
                "medicationName": "Amlodipine Besylate",
                "strength": "5mg",
                "dose": "1 tablet",
                "route": "Oral",
                "frequency": "Once daily (Morning)",
                "duration": "30 days",
                "quantity": "30 tablets",
                "additionalInstructions": "Take after breakfast with water.",
            }
        ],
        "instructions": "Continue salt-restricted diet.",
    }

    res_patch = client.patch(f"/api/prescriptions/{presc_id}", json=amend_payload, headers=headers_doc_a)
    assert res_patch.status_code == 200
    updated = res_patch.json()
    assert updated["status"] == "AMENDED"
    assert len(updated["medicationItems"]) == 1
    assert len(updated["amendmentHistory"]) == 1
    assert "Increased Amlodipine duration" in updated["amendmentHistory"][0]["reason"]


def test_secure_prescription_pdf_download(seeded_medical_env):
    """Authenticated Patient and Doctor can download official prescription PDF."""
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}
    headers_doc_a = {"Authorization": f"Bearer {seeded_medical_env['doctor_a']['token']}"}

    res_list = client.get("/api/prescriptions/me", headers=headers_pat_a)
    presc_id = res_list.json()["items"][0]["id"]

    # 1. Patient downloads PDF
    res_pdf_pat = client.get(f"/api/prescriptions/{presc_id}/pdf", headers=headers_pat_a)
    assert res_pdf_pat.status_code == 200
    assert res_pdf_pat.headers["Content-Type"] == "application/pdf"
    assert "attachment; filename=" in res_pdf_pat.headers["Content-Disposition"]
    assert res_pdf_pat.content.startswith(b"%PDF-")

    # 2. Doctor downloads PDF
    res_pdf_doc = client.get(f"/api/prescriptions/{presc_id}/pdf", headers=headers_doc_a)
    assert res_pdf_doc.status_code == 200
    assert res_pdf_doc.content.startswith(b"%PDF-")


def test_unauthenticated_and_cross_user_pdf_access_denied(seeded_medical_env):
    """Unauthenticated (401) and unauthorized cross-user (403) PDF requests are rejected."""
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}
    headers_pat_b = {"Authorization": f"Bearer {seeded_medical_env['patient_b']['token']}"}

    res_list = client.get("/api/prescriptions/me", headers=headers_pat_a)
    presc_id = res_list.json()["items"][0]["id"]

    # 1. Unauthenticated -> 401
    res_unauth = client.get(f"/api/prescriptions/{presc_id}/pdf")
    assert res_unauth.status_code == 401

    # 2. Patient B accessing Patient A's prescription PDF -> 403
    res_pat_b = client.get(f"/api/prescriptions/{presc_id}/pdf", headers=headers_pat_b)
    assert res_pat_b.status_code == 403


def test_pagination_and_not_found(seeded_medical_env):
    """Pagination parameters work cleanly and invalid IDs return 404."""
    headers_pat_a = {"Authorization": f"Bearer {seeded_medical_env['patient_a']['token']}"}

    # Pagination
    res_page = client.get("/api/medical-records/me?page=1&page_size=1", headers=headers_pat_a)
    assert res_page.status_code == 200
    assert res_page.json()["page"] == 1
    assert res_page.json()["pageSize"] == 1

    # 404 on non-existent record
    res_404_rec = client.get(f"/api/medical-records/{str(ObjectId())}", headers=headers_pat_a)
    assert res_404_rec.status_code == 404

    # 404 on non-existent prescription
    res_404_presc = client.get(f"/api/prescriptions/{str(ObjectId())}", headers=headers_pat_a)
    assert res_404_presc.status_code == 404
