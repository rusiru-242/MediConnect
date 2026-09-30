import io
import time
from fastapi.testclient import TestClient
import pytest
from app.config.database import get_database
from app.main import app
from app.models.user import UserRole
from app.utils.security import create_access_token

client = TestClient(app)


def _get_valid_pdf_file():
    """Return a mock valid PDF file with magic bytes."""
    return ("test_doc.pdf", b"%PDF-1.4 Mock valid PDF content for doctor registration testing", "application/pdf")


def _get_invalid_doc_file():
    """Return an executable or invalid document type."""
    return ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-msdownload")


def _get_oversized_pdf_file():
    """Return an oversized PDF document (> 5MB)."""
    return ("large.pdf", b"%PDF-1.4 " + (b"0" * (5 * 1024 * 1024 + 1024)), "application/pdf")


def test_doctor_full_workflow():
    db = get_database()
    timestamp = int(time.time() * 1000)
    doctor_email = f"dr.test_{timestamp}@mediconnect.lk"
    med_reg_num = f"SLMC-{timestamp % 1000000:06d}"
    phone = "0771234567"
    password = "DoctorPassword@123"

    # ---------------------------------------------------------
    # TEST 1: Register valid doctor
    # ---------------------------------------------------------
    files = {
        "identityDocument": _get_valid_pdf_file(),
        "medicalRegistrationDocument": _get_valid_pdf_file(),
        "qualificationDocument": _get_valid_pdf_file(),
    }
    data = {
        "fullName": "Dr. Kasun Test",
        "email": doctor_email,
        "phone": phone,
        "password": password,
        "specialty": "Cardiologist",
        "medicalRegistrationNumber": med_reg_num,
        "qualifications": "MBBS (Colombo), MD (Cardiology)",
        "hospitalOrClinic": "National Hospital of Sri Lanka",
        "experienceYears": 10,
        "bio": "Experienced cardiologist with special interest in interventional cardiology.",
    }

    res = client.post("/api/auth/register-doctor", data=data, files=files)
    assert res.status_code == 201, f"Failed: {res.text}"
    body = res.json()
    assert body["message"] == "Doctor application submitted successfully. Please verify your email."
    user_data = body["user"]
    assert user_data["role"] == "DOCTOR"
    assert user_data["emailVerified"] is False
    assert user_data["accountStatus"] == "PENDING"

    profile_data = body["doctorProfile"]
    assert profile_data["verificationStatus"] == "PENDING"
    assert profile_data["specialty"] == "Cardiologist"
    assert profile_data["medicalRegistrationNumber"] == med_reg_num

    # Verify MongoDB state directly
    user_in_db = db["users"].find_one({"email": doctor_email})
    assert user_in_db is not None
    assert user_in_db["role"] == "DOCTOR"
    assert user_in_db["emailVerified"] is False
    assert user_in_db["accountStatus"] == "PENDING"

    profile_in_db = db["doctor_profiles"].find_one({"userId": str(user_in_db["_id"])})
    assert profile_in_db is not None
    assert profile_in_db["verificationStatus"] == "PENDING"
    assert profile_in_db["rejectionReason"] is None
    assert profile_in_db["verifiedAt"] is None

    # ---------------------------------------------------------
    # TEST 2: Duplicate email rejected
    # ---------------------------------------------------------
    dup_email_files = {
        "identityDocument": _get_valid_pdf_file(),
        "medicalRegistrationDocument": _get_valid_pdf_file(),
        "qualificationDocument": _get_valid_pdf_file(),
    }
    dup_data = data.copy()
    dup_data["medicalRegistrationNumber"] = f"SLMC-NEW-{timestamp}"
    res_dup = client.post("/api/auth/register-doctor", data=dup_data, files=dup_email_files)
    assert res_dup.status_code == 409
    assert "email already exists" in res_dup.json()["detail"]

    # ---------------------------------------------------------
    # TEST 3: Duplicate medical registration number rejected
    # ---------------------------------------------------------
    dup_reg_files = {
        "identityDocument": _get_valid_pdf_file(),
        "medicalRegistrationDocument": _get_valid_pdf_file(),
        "qualificationDocument": _get_valid_pdf_file(),
    }
    dup_reg_data = data.copy()
    dup_reg_data["email"] = f"dr.other_{timestamp}@mediconnect.lk"
    dup_reg_data["medicalRegistrationNumber"] = med_reg_num  # Existing registration number
    res_reg_dup = client.post("/api/auth/register-doctor", data=dup_reg_data, files=dup_reg_files)
    assert res_reg_dup.status_code == 409
    assert "medical registration number already exists" in res_reg_dup.json()["detail"]

    # ---------------------------------------------------------
    # TEST 4: Weak password rejected
    # ---------------------------------------------------------
    weak_pwd_files = {
        "identityDocument": _get_valid_pdf_file(),
        "medicalRegistrationDocument": _get_valid_pdf_file(),
        "qualificationDocument": _get_valid_pdf_file(),
    }
    weak_pwd_data = data.copy()
    weak_pwd_data["email"] = f"dr.weak_{timestamp}@mediconnect.lk"
    weak_pwd_data["medicalRegistrationNumber"] = f"SLMC-WEAK-{timestamp}"
    weak_pwd_data["password"] = "weak"
    res_weak = client.post("/api/auth/register-doctor", data=weak_pwd_data, files=weak_pwd_files)
    assert res_weak.status_code == 422

    # ---------------------------------------------------------
    # TEST 5: Invalid document type rejected
    # ---------------------------------------------------------
    invalid_files = {
        "identityDocument": _get_invalid_doc_file(),
        "medicalRegistrationDocument": _get_valid_pdf_file(),
        "qualificationDocument": _get_valid_pdf_file(),
    }
    inv_data = data.copy()
    inv_data["email"] = f"dr.invalid_{timestamp}@mediconnect.lk"
    inv_data["medicalRegistrationNumber"] = f"SLMC-INV-{timestamp}"
    res_inv = client.post("/api/auth/register-doctor", data=inv_data, files=invalid_files)
    assert res_inv.status_code == 400
    assert "Invalid file type" in res_inv.json()["detail"] or "content type" in res_inv.json()["detail"]

    # ---------------------------------------------------------
    # TEST 6: Oversized document rejected
    # ---------------------------------------------------------
    oversized_files = {
        "identityDocument": _get_oversized_pdf_file(),
        "medicalRegistrationDocument": _get_valid_pdf_file(),
        "qualificationDocument": _get_valid_pdf_file(),
    }
    ovr_data = data.copy()
    ovr_data["email"] = f"dr.oversized_{timestamp}@mediconnect.lk"
    ovr_data["medicalRegistrationNumber"] = f"SLMC-OVR-{timestamp}"
    res_ovr = client.post("/api/auth/register-doctor", data=ovr_data, files=oversized_files)
    assert res_ovr.status_code == 400
    assert "exceeds maximum allowed size" in res_ovr.json()["detail"]

    # ---------------------------------------------------------
    # TEST 7: Doctor email verification
    # ---------------------------------------------------------
    # Verify OTP against user
    from app.utils.security import hash_password
    test_otp = "123456"
    db["users"].update_one(
        {"_id": user_in_db["_id"]},
        {"$set": {"emailVerification.otpHash": hash_password(test_otp)}},
    )

    verify_res = client.post(
        "/api/auth/verify-email",
        json={"email": doctor_email, "otp": test_otp},
    )
    assert verify_res.status_code == 200

    # Refresh user from DB
    verified_user_in_db = db["users"].find_one({"_id": user_in_db["_id"]})
    assert verified_user_in_db["emailVerified"] is True
    # TEST 8: Confirm doctor was NOT automatically approved (accountStatus remains PENDING)
    assert verified_user_in_db["accountStatus"] == "PENDING"

    verified_profile_in_db = db["doctor_profiles"].find_one({"userId": str(user_in_db["_id"])})
    assert verified_profile_in_db["verificationStatus"] == "PENDING"
    assert verified_profile_in_db["verifiedAt"] is None

    # ---------------------------------------------------------
    # TEST 9: Pending doctor can log in and view application-status endpoint
    # ---------------------------------------------------------
    login_res = client.post(
        "/api/auth/login",
        json={"email": doctor_email, "password": password},
    )
    assert login_res.status_code == 200, f"Doctor login failed: {login_res.text}"
    doctor_access_token = login_res.json()["accessToken"]

    status_res = client.get(
        "/api/doctors/me/application-status",
        headers={"Authorization": f"Bearer {doctor_access_token}"},
    )
    assert status_res.status_code == 200
    status_body = status_res.json()
    assert status_body["verificationStatus"] == "PENDING"
    assert status_body["specialty"] == "Cardiologist"
    assert status_body["rejectionReason"] is None

    # ---------------------------------------------------------
    # TEST 10: Patient attempts doctor-only endpoint returns 403 Forbidden
    # ---------------------------------------------------------
    from datetime import datetime, timezone
    patient_user = {
        "fullName": "Test Patient User",
        "email": f"patient.test_{timestamp}@mediconnect.lk",
        "phone": "+94771112233",
        "passwordHash": hash_password(password),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": "ACTIVE",
        "authProviders": ["LOCAL"],
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    pat_res = db["users"].insert_one(patient_user)
    patient_token = create_access_token(user_id=str(pat_res.inserted_id), role=UserRole.PATIENT.value)
    patient_attempt = client.get(
        "/api/doctors/me/application-status",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert patient_attempt.status_code == 403
    assert "do not have permission" in patient_attempt.json()["detail"].lower()
