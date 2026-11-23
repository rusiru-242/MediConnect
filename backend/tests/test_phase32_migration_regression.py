"""Phase 32 Regression Tests: Role-Based Authorization & Admin Web Only Migration.

Verifies:
1. Admin Web authentication & JWT token generation remains intact on backend.
2. Patient and Doctor authentication remains intact on backend.
3. Strict backend RBAC denial (403 Forbidden) when Patient or Doctor calls Admin endpoints.
4. Unauthenticated calls to Admin endpoints return 401 Unauthorized.
5. Medical records and verification document privacy boundaries are preserved.
"""

import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.user import AccountStatus, UserRole, utc_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


def test_phase32_auth_compatibility_and_rbac():
    db = get_database()
    timestamp = int(time.time() * 1000)

    # 1. Setup Admin Account
    admin_id = str(ObjectId())
    admin_email = f"phase32_admin_{timestamp}@mediconnect.lk"
    admin_password = "AdminSecretPass@123"
    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "fullName": "Phase 32 Admin",
        "email": admin_email,
        "phone": "0771000001",
        "passwordHash": hash_password(admin_password),
        "role": UserRole.ADMIN.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 2. Setup Patient Account
    patient_id = str(ObjectId())
    patient_email = f"phase32_pat_{timestamp}@mediconnect.lk"
    patient_password = "PatientSecretPass@123"
    db["users"].insert_one({
        "_id": ObjectId(patient_id),
        "fullName": "Phase 32 Patient",
        "email": patient_email,
        "phone": "0771000002",
        "passwordHash": hash_password(patient_password),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 3. Setup Doctor Account
    doctor_id = str(ObjectId())
    doctor_email = f"phase32_doc_{timestamp}@mediconnect.lk"
    doctor_password = "DoctorSecretPass@123"
    db["users"].insert_one({
        "_id": ObjectId(doctor_id),
        "fullName": "Dr. Phase 32 Specialist",
        "email": doctor_email,
        "phone": "0771000003",
        "passwordHash": hash_password(doctor_password),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # TEST A: Admin Login through FastAPI Backend (used by React Web Admin)
    login_admin = client.post("/api/auth/login", json={
        "email": admin_email,
        "password": admin_password,
    })
    assert login_admin.status_code == 200
    admin_data = login_admin.json()
    assert admin_data["user"]["role"] == "ADMIN"
    assert "accessToken" in admin_data
    admin_token = admin_data["accessToken"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # TEST B: Patient Login through FastAPI Backend (used by Flutter Mobile)
    login_pat = client.post("/api/auth/login", json={
        "email": patient_email,
        "password": patient_password,
    })
    assert login_pat.status_code == 200
    pat_data = login_pat.json()
    assert pat_data["user"]["role"] == "PATIENT"
    assert "accessToken" in pat_data
    patient_token = pat_data["accessToken"]
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    # TEST C: Doctor Login through FastAPI Backend (used by Flutter Mobile)
    login_doc = client.post("/api/auth/login", json={
        "email": doctor_email,
        "password": doctor_password,
    })
    assert login_doc.status_code == 200
    doc_data = login_doc.json()
    assert doc_data["user"]["role"] == "DOCTOR"
    assert "accessToken" in doc_data
    doctor_token = doc_data["accessToken"]
    doctor_headers = {"Authorization": f"Bearer {doctor_token}"}

    # TEST D: Backend Role-Based Authorization on Admin Endpoints
    admin_endpoints = [
        "/api/admin/doctors/applications",
        "/api/admin/users",
        "/api/admin/doctors",
        "/api/admin/appointments",
        "/api/admin/payments",
    ]

    for ep in admin_endpoints:
        # 1. Unauthenticated -> 401
        res_anon = client.get(ep)
        assert res_anon.status_code == 401, f"Expected 401 for anonymous access to {ep}"

        # 2. Patient access -> 403 Forbidden
        res_pat = client.get(ep, headers=patient_headers)
        assert res_pat.status_code == 403, f"Expected 403 for patient access to {ep}"

        # 3. Doctor access -> 403 Forbidden
        res_doc = client.get(ep, headers=doctor_headers)
        assert res_doc.status_code == 403, f"Expected 403 for doctor access to {ep}"

        # 4. Admin access -> 200 OK
        res_admin = client.get(ep, headers=admin_headers)
        assert res_admin.status_code == 200, f"Expected 200 for admin access to {ep}"

    # TEST E: Patient Medical Record Privacy
    # Create another patient to test cross-patient isolation
    other_patient_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(other_patient_id),
        "fullName": "Phase 32 Other Patient",
        "email": f"phase32_other_pat_{timestamp}@mediconnect.lk",
        "phone": "0771000004",
        "passwordHash": hash_password(patient_password),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    other_patient_token = create_access_token(other_patient_id, role=UserRole.PATIENT.value)
    other_patient_headers = {"Authorization": f"Bearer {other_patient_token}"}

    # Add medical consultation record for patient 1
    med_rec_id = ObjectId()
    db["medical_records"].insert_one({
        "_id": med_rec_id,
        "recordId": f"REC-REG-{timestamp}",
        "appointmentId": str(ObjectId()),
        "patientUserId": patient_id,
        "doctorUserId": doctor_id,
        "doctorProfileId": str(ObjectId()),
        "doctorName": "Dr. Phase 32 Specialist",
        "doctorSpecialty": "General Medicine",
        "clinicalNotes": "Patient presented with mild seasonal allergy.",
        "assessment": "Allergic rhinitis.",
        "treatmentPlan": "Antihistamines for 5 days.",
        "consultationDate": "2026-10-18",
        "status": "ACTIVE",
        "version": 1,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Patient 1 can access their records via /api/medical-records/me
    res_pat1 = client.get("/api/medical-records/me", headers=patient_headers)
    assert res_pat1.status_code == 200
    pat1_items = res_pat1.json().get("items", [])
    assert any(str(r["id"]) == str(med_rec_id) for r in pat1_items)

    # Patient 2 CANNOT see Patient 1's records
    res_pat2 = client.get("/api/medical-records/me", headers=other_patient_headers)
    assert res_pat2.status_code == 200
    pat2_items = res_pat2.json().get("items", [])
    assert not any(str(r["id"]) == str(med_rec_id) for r in pat2_items)

    # Patient 2 directly accessing Patient 1's record ID receives 403 Forbidden
    res_cross = client.get(f"/api/medical-records/{med_rec_id}", headers=other_patient_headers)
    assert res_cross.status_code == 403

    # Cleanup test documents
    db["users"].delete_many({"_id": {"$in": [ObjectId(admin_id), ObjectId(patient_id), ObjectId(doctor_id), ObjectId(other_patient_id)]}})
    db["medical_records"].delete_one({"_id": med_rec_id})
