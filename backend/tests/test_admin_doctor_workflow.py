import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.user import AccountStatus, UserDocument, UserRole, utc_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


def _get_valid_pdf_file():
    """Return a mock valid PDF file with magic bytes."""
    return ("test_doc.pdf", b"%PDF-1.4 Mock valid PDF content for doctor registration testing", "application/pdf")


def test_admin_doctor_verification_workflow():
    db = get_database()
    timestamp = int(time.time() * 1000)

    # 1. Setup Admin User
    admin_email = f"admin_{timestamp}@mediconnect.lk"
    admin_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "fullName": "Super Administrator",
        "email": admin_email,
        "phone": "0770001122",
        "passwordHash": hash_password("AdminSecure@123"),
        "role": UserRole.ADMIN.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    admin_token = create_access_token(admin_id, role=UserRole.ADMIN.value)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Setup Patient User
    patient_email = f"patient_{timestamp}@mediconnect.lk"
    patient_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(patient_id),
        "fullName": "Test Patient",
        "email": patient_email,
        "phone": "0771122334",
        "passwordHash": hash_password("PatientSecure@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    patient_token = create_access_token(patient_id, role=UserRole.PATIENT.value)
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    # 3. Register Doctor A (will be verified and approved)
    doc_a_email = f"dr.a_{timestamp}@mediconnect.lk"
    doc_a_files = {
        "identityDocument": _get_valid_pdf_file(),
        "medicalRegistrationDocument": _get_valid_pdf_file(),
        "qualificationDocument": _get_valid_pdf_file(),
    }
    doc_a_data = {
        "fullName": "Dr. Alice Perera",
        "email": doc_a_email,
        "phone": "0771234501",
        "password": "DoctorPassword@123",
        "specialty": "Cardiologist",
        "medicalRegistrationNumber": f"SLMC-A{timestamp % 10000:04d}",
        "qualifications": "MBBS, MD Cardiology",
        "hospitalOrClinic": "Colombo General Hospital",
        "experienceYears": 8,
        "bio": "Cardiologist bio here.",
    }
    reg_a_res = client.post("/api/auth/register-doctor", data=doc_a_data, files=doc_a_files)
    assert reg_a_res.status_code == 201
    user_a = db["users"].find_one({"email": doc_a_email})
    profile_a = db["doctor_profiles"].find_one({"userId": str(user_a["_id"])})
    prof_a_id = str(profile_a["_id"])
    doc_a_id = str(user_a["_id"])

    # Mark Doctor A email as verified (like after entering OTP)
    db["users"].update_one({"_id": user_a["_id"]}, {"$set": {"emailVerified": True}})
    doc_a_token = create_access_token(doc_a_id, role=UserRole.DOCTOR.value)
    doc_a_headers = {"Authorization": f"Bearer {doc_a_token}"}

    # 4. Register Doctor B (email NOT verified)
    doc_b_email = f"dr.b_{timestamp}@mediconnect.lk"
    doc_b_files = {
        "identityDocument": _get_valid_pdf_file(),
        "medicalRegistrationDocument": _get_valid_pdf_file(),
        "qualificationDocument": _get_valid_pdf_file(),
    }
    doc_b_data = {
        "fullName": "Dr. Bob Fernando",
        "email": doc_b_email,
        "phone": "0771234502",
        "password": "DoctorPassword@123",
        "specialty": "Pediatrician",
        "medicalRegistrationNumber": f"SLMC-B{timestamp % 10000:04d}",
        "qualifications": "MBBS, DCH",
        "hospitalOrClinic": "Lady Ridgeway Hospital",
        "experienceYears": 5,
        "bio": "Pediatrician bio here.",
    }
    reg_b_res = client.post("/api/auth/register-doctor", data=doc_b_data, files=doc_b_files)
    assert reg_b_res.status_code == 201
    user_b = db["users"].find_one({"email": doc_b_email})
    profile_b = db["doctor_profiles"].find_one({"userId": str(user_b["_id"])})
    prof_b_id = str(profile_b["_id"])

    # 5. Register Doctor C (will be rejected with reason)
    doc_c_email = f"dr.c_{timestamp}@mediconnect.lk"
    doc_c_files = {
        "identityDocument": _get_valid_pdf_file(),
        "medicalRegistrationDocument": _get_valid_pdf_file(),
        "qualificationDocument": _get_valid_pdf_file(),
    }
    doc_c_data = {
        "fullName": "Dr. Charlie Silva",
        "email": doc_c_email,
        "phone": "0771234503",
        "password": "DoctorPassword@123",
        "specialty": "Dermatologist",
        "medicalRegistrationNumber": f"SLMC-C{timestamp % 10000:04d}",
        "qualifications": "MBBS, MD Dermatology",
        "hospitalOrClinic": "Asiri Hospital",
        "experienceYears": 6,
        "bio": "Dermatology specialist.",
    }
    reg_c_res = client.post("/api/auth/register-doctor", data=doc_c_data, files=doc_c_files)
    assert reg_c_res.status_code == 201
    user_c = db["users"].find_one({"email": doc_c_email})
    profile_c = db["doctor_profiles"].find_one({"userId": str(user_c["_id"])})
    prof_c_id = str(profile_c["_id"])
    doc_c_id = str(user_c["_id"])
    db["users"].update_one({"_id": user_c["_id"]}, {"$set": {"emailVerified": True}})
    doc_c_token = create_access_token(doc_c_id, role=UserRole.DOCTOR.value)
    doc_c_headers = {"Authorization": f"Bearer {doc_c_token}"}

    # ---------------------------------------------------------
    # TEST 1: PATIENT requests admin application list -> 403
    # ---------------------------------------------------------
    res_t1 = client.get("/api/admin/doctors/applications", headers=patient_headers)
    assert res_t1.status_code == 403, f"Expected 403, got {res_t1.status_code}"

    # ---------------------------------------------------------
    # TEST 2: DOCTOR requests admin application list -> 403
    # ---------------------------------------------------------
    res_t2 = client.get("/api/admin/doctors/applications", headers=doc_a_headers)
    assert res_t2.status_code == 403, f"Expected 403, got {res_t2.status_code}"

    # ---------------------------------------------------------
    # TEST 3: ADMIN requests pending applications -> 200
    # ---------------------------------------------------------
    res_t3 = client.get("/api/admin/doctors/applications?status=PENDING", headers=admin_headers)
    assert res_t3.status_code == 200, f"Expected 200, got {res_t3.status_code}"
    pending_list = res_t3.json()
    assert isinstance(pending_list, list)
    found_a = any(item["doctorProfileId"] == prof_a_id for item in pending_list)
    assert found_a, "Doctor A should appear in PENDING applications list"

    # ---------------------------------------------------------
    # TEST 4: Admin opens application details -> safe doctor data returned
    # ---------------------------------------------------------
    res_t4 = client.get(f"/api/admin/doctors/applications/{prof_a_id}", headers=admin_headers)
    assert res_t4.status_code == 200, f"Expected 200, got {res_t4.status_code}"
    detail_a = res_t4.json()
    assert detail_a["fullName"] == "Dr. Alice Perera"
    assert detail_a["specialty"] == "Cardiologist"
    assert detail_a["verificationStatus"] == "PENDING"
    assert len(detail_a["documents"]) == 3
    # Verify no raw internal filesystem path is leaked
    for doc_meta in detail_a["documents"]:
        assert "storagePath" not in doc_meta
        assert "/" not in doc_meta["filename"] and "\\" not in doc_meta["filename"]

    # ---------------------------------------------------------
    # TEST 5: Unauthenticated document request -> 401
    # ---------------------------------------------------------
    res_t5 = client.get(f"/api/admin/doctors/applications/{prof_a_id}/documents/identityDocument")
    assert res_t5.status_code == 401, f"Expected 401, got {res_t5.status_code}"

    # ---------------------------------------------------------
    # TEST 6: Doctor/patient document request -> 403
    # ---------------------------------------------------------
    res_t6_patient = client.get(
        f"/api/admin/doctors/applications/{prof_a_id}/documents/identityDocument",
        headers=patient_headers,
    )
    assert res_t6_patient.status_code == 403
    res_t6_doc = client.get(
        f"/api/admin/doctors/applications/{prof_a_id}/documents/identityDocument",
        headers=doc_a_headers,
    )
    assert res_t6_doc.status_code == 403

    # ---------------------------------------------------------
    # TEST 7: Admin securely retrieves valid document -> 200
    # ---------------------------------------------------------
    res_t7 = client.get(
        f"/api/admin/doctors/applications/{prof_a_id}/documents/identityDocument",
        headers=admin_headers,
    )
    assert res_t7.status_code == 200, f"Expected 200, got {res_t7.status_code}"
    assert res_t7.headers["content-type"] == "application/pdf"
    assert res_t7.content.startswith(b"%PDF-1.4")

    # ---------------------------------------------------------
    # TEST 8: Path traversal / invalid document ID attempt -> safe rejection
    # ---------------------------------------------------------
    res_t8_traversal = client.get(
        f"/api/admin/doctors/applications/{prof_a_id}/documents/..%2F..%2Fetc%2Fpasswd",
        headers=admin_headers,
    )
    assert res_t8_traversal.status_code in (400, 404)
    res_t8_invalid = client.get(
        f"/api/admin/doctors/applications/{prof_a_id}/documents/nonExistentDoc",
        headers=admin_headers,
    )
    assert res_t8_invalid.status_code == 404

    # ---------------------------------------------------------
    # TEST 9: Approve doctor whose email is not verified -> rejected
    # ---------------------------------------------------------
    res_t9 = client.post(f"/api/admin/doctors/{prof_b_id}/approve", headers=admin_headers)
    assert res_t9.status_code == 400
    assert "email is not verified" in res_t9.json()["detail"].lower()

    # ---------------------------------------------------------
    # TEST 10: Approve valid pending verified doctor -> APPROVED, ACTIVE, audit set
    # ---------------------------------------------------------
    res_t10 = client.post(f"/api/admin/doctors/{prof_a_id}/approve", headers=admin_headers)
    assert res_t10.status_code == 200
    assert "approved successfully" in res_t10.json()["message"].lower()

    updated_prof_a = db["doctor_profiles"].find_one({"_id": ObjectId(prof_a_id)})
    assert updated_prof_a["verificationStatus"] == "APPROVED"
    assert updated_prof_a["verifiedBy"] == admin_id
    assert updated_prof_a["verifiedAt"] is not None

    updated_user_a = db["users"].find_one({"_id": ObjectId(doc_a_id)})
    assert updated_user_a["accountStatus"] == AccountStatus.ACTIVE.value

    # ---------------------------------------------------------
    # TEST 11: Doctor refreshes status -> APPROVED
    # ---------------------------------------------------------
    res_t11 = client.get("/api/doctors/me/application-status", headers=doc_a_headers)
    assert res_t11.status_code == 200
    assert res_t11.json()["verificationStatus"] == "APPROVED"

    # ---------------------------------------------------------
    # TEST 12: Reject valid pending application with reason -> REJECTED
    # ---------------------------------------------------------
    reject_reason = "Medical registration certificate could not be authenticated with SLMC."
    res_t12 = client.post(
        f"/api/admin/doctors/{prof_c_id}/reject",
        json={"reason": reject_reason},
        headers=admin_headers,
    )
    assert res_t12.status_code == 200
    assert "rejected" in res_t12.json()["message"].lower()

    updated_prof_c = db["doctor_profiles"].find_one({"_id": ObjectId(prof_c_id)})
    assert updated_prof_c["verificationStatus"] == "REJECTED"
    assert updated_prof_c["rejectionReason"] == reject_reason
    assert updated_prof_c["verifiedBy"] == admin_id

    # Doctor status endpoint for Doctor C
    res_t12_c_status = client.get("/api/doctors/me/application-status", headers=doc_c_headers)
    assert res_t12_c_status.status_code == 200
    assert res_t12_c_status.json()["verificationStatus"] == "REJECTED"
    assert res_t12_c_status.json()["rejectionReason"] == reject_reason

    # ---------------------------------------------------------
    # TEST 13: Reject without reason -> validation error (422)
    # ---------------------------------------------------------
    res_t13 = client.post(
        f"/api/admin/doctors/{prof_b_id}/reject",
        json={"reason": "  "},
        headers=admin_headers,
    )
    assert res_t13.status_code == 422

    # ---------------------------------------------------------
    # TEST 14: Try to reject already approved doctor -> rejected (400)
    # ---------------------------------------------------------
    res_t14 = client.post(
        f"/api/admin/doctors/{prof_a_id}/reject",
        json={"reason": "Should not allow rejecting approved doctor."},
        headers=admin_headers,
    )
    assert res_t14.status_code == 400
    assert "cannot reject" in res_t14.json()["detail"].lower()

    # ---------------------------------------------------------
    # TEST 15: Try to approve already rejected doctor -> rejected (400)
    # ---------------------------------------------------------
    res_t15 = client.post(
        f"/api/admin/doctors/{prof_c_id}/approve",
        headers=admin_headers,
    )
    assert res_t15.status_code == 400
    assert "cannot approve" in res_t15.json()["detail"].lower()
