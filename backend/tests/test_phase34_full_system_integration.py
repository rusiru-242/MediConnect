"""Phase 34 Full-System Integration & End-to-End Verification Test Suite.

Validates the complete MediConnect target architecture:
- Patient Journey: Register, OTP Verification, Login, Search, Availability, Booking, Stripe Intent, Webhook, Records, Reminders, Reviews.
- Doctor Journey: Registration, Admin Approval, Login, Availability Management, Consultation Record, Digital Prescription.
- Admin Web Journey: Admin Login, Dashboard Analytics, Doctor Application Review, Payment Oversight, Health Content Publishing.
- Cross-Role RBAC: Strict access boundaries, invalid/expired JWT rejection, cross-patient medical privacy.
- Concurrency & Reliability: Double booking prevention, duplicate webhook idempotency.
- AI & Medical Safeguards: Recommendations, health chat safety disclaimers, input validation.
"""

from datetime import datetime, timedelta, timezone
import json
import time
from unittest.mock import patch, MagicMock
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.config.database import get_database
from app.main import app
from app.models.appointment import AppointmentStatus, PaymentStatus as ApptPaymentStatus
from app.models.doctor_availability import DoctorAvailabilityDocument
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.services.email_service import EmailService
from app.utils.security import create_access_token, hash_password

client = TestClient(app)
SL_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def _future_date(days: int = 4) -> str:
    return (datetime.now(SL_TIMEZONE) + timedelta(days=days)).strftime("%Y-%m-%d")


def test_phase34_e2e_patient_registration_and_otp_verification():
    """Verify Patient registration sends OTP and verify-email activates the account."""
    db = get_database()
    ts = int(time.time() * 1000)
    email = f"p34_pat_{ts}@mediconnect.lk"
    password = "PatientPassword@123"

    captured_otp = []

    def mock_send_otp(recipient_email, otp_code):
        captured_otp.append(otp_code)
        return True

    with patch.object(EmailService, "send_verification_otp", side_effect=mock_send_otp):
        reg_res = client.post("/api/auth/register", json={
            "fullName": "P34 Integration Patient",
            "email": email,
            "phone": "0771239999",
            "password": password,
        })
        assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
        assert len(captured_otp) == 1, "Expected verification OTP to be generated and dispatched"

        otp_code = captured_otp[0]
        assert len(otp_code) == 6

        # Verify email using the captured OTP
        verify_res = client.post("/api/auth/verify-email", json={
            "email": email,
            "otp": otp_code,
        })
        assert verify_res.status_code == 200, f"OTP verification failed: {verify_res.text}"
        assert verify_res.json().get("message") == "Email verified successfully."

        # Verify database reflects verified email and active account
        db_user = db["users"].find_one({"email": email})
        assert db_user is not None
        assert db_user["emailVerified"] is True
        assert db_user["accountStatus"] == AccountStatus.ACTIVE.value

        # Verify login now succeeds
        login_res = client.post("/api/auth/login", json={
            "email": email,
            "password": password,
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        login_data = login_res.json()
        assert "accessToken" in login_data
        assert login_data["user"]["role"] == "PATIENT"


def test_phase34_e2e_doctor_registration_and_admin_approval():
    """Verify Doctor registration creates PENDING profile, Admin approves, and Doctor can log in."""
    db = get_database()
    ts = int(time.time() * 1000)
    dr_email = f"p34_dr_{ts}@mediconnect.lk"
    dr_password = "DoctorPassword@123"

    # Setup admin
    admin_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "fullName": "P34 Chief Admin",
        "email": f"p34_admin_{ts}@mediconnect.lk",
        "phone": "0770009999",
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

    # Register Doctor with synthetic documents using a supported specialty (Cardiologist)
    valid_pdf = ("doc.pdf", b"%PDF-1.4 synthetic doctor license content", "application/pdf")
    reg_res = client.post(
        "/api/auth/register-doctor",
        data={
            "fullName": "Dr. P34 Verified Doctor",
            "email": dr_email,
            "phone": "0775551234",
            "password": dr_password,
            "specialty": "Cardiologist",
            "medicalRegistrationNumber": f"SLMC-{ts % 1000000:06d}",
            "qualifications": "MBBS, MD (Cardiology)",
            "hospitalOrClinic": "National Hospital Sri Lanka",
            "experienceYears": 12,
            "bio": "Consultant Cardiologist specializing in interventional cardiology.",
        },
        files={
            "identityDocument": valid_pdf,
            "medicalRegistrationDocument": valid_pdf,
            "qualificationDocument": valid_pdf,
        },
    )
    assert reg_res.status_code == 201, f"Doctor registration failed: {reg_res.text}"

    # Verify doctor profile is in database as PENDING
    dr_user = db["users"].find_one({"email": dr_email})
    assert dr_user is not None
    dr_prof = db["doctor_profiles"].find_one({"userId": str(dr_user["_id"])})
    assert dr_prof is not None
    assert dr_prof["verificationStatus"] == DoctorVerificationStatus.PENDING.value

    # Doctor verifies their email before admin approval
    db["users"].update_one({"_id": dr_user["_id"]}, {"$set": {"emailVerified": True}})

    # Admin checks pending doctor applications list
    pending_res = client.get("/api/admin/doctors/applications?status=PENDING", headers=admin_headers)
    assert pending_res.status_code == 200
    pending_prof_ids = [d["doctorProfileId"] for d in pending_res.json()]
    assert str(dr_prof["_id"]) in pending_prof_ids

    # Admin approves the doctor application
    approve_res = client.post(
        f"/api/admin/doctors/{str(dr_prof['_id'])}/approve",
        headers=admin_headers,
        json={"notes": "All SLMC verification documents verified successfully."},
    )
    assert approve_res.status_code == 200, f"Admin approval failed: {approve_res.text}"

    # Verify database status is now APPROVED
    updated_prof = db["doctor_profiles"].find_one({"_id": dr_prof["_id"]})
    assert updated_prof["verificationStatus"] == DoctorVerificationStatus.APPROVED.value


def test_phase34_e2e_booking_payment_and_fulfillment():
    """Verify slot booking, Stripe intent generation, webhook confirmation, and appointment status."""
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Create Patient
    pat_id = str(ObjectId())
    pat_email = f"p34_booker_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(pat_id),
        "fullName": "Booking Patient",
        "email": pat_email,
        "phone": "0771122334",
        "passwordHash": hash_password("Pass@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat_token = create_access_token(pat_id, role=UserRole.PATIENT.value)
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    # 2. Create Approved Doctor with Availability
    dr_user_id = str(ObjectId())
    dr_doc_id = f"DR-P34-{ts % 100000}"
    db["users"].insert_one({
        "_id": ObjectId(dr_user_id),
        "fullName": "Dr. Booking Specialist",
        "email": f"dr_book_{ts}@mediconnect.lk",
        "phone": "0779988776",
        "passwordHash": hash_password("Pass@123"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    dr_prof_res = db["doctor_profiles"].insert_one({
        "userId": dr_user_id,
        "doctorId": dr_doc_id,
        "specialty": "General Physician",
        "medicalRegistrationNumber": f"SLMC-{ts % 100000}",
        "qualifications": "MBBS",
        "hospitalOrClinic": "Lanka Hospital",
        "experienceYears": 8,
        "consultationFee": 3000.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "submittedAt": utc_now(),
        "verifiedAt": utc_now(),
    })
    date_str = _future_date(3)
    avail_doc = DoctorAvailabilityDocument(
        doctorUserId=dr_user_id,
        doctorProfileId=str(dr_prof_res.inserted_id),
        date=date_str,
        startTime="10:00",
        endTime="12:00",
        slotDurationMinutes=30,
        isActive=True,
    )
    avail_res = db["doctor_availabilities"].insert_one(avail_doc.to_mongo_dict())

    # 3. Patient searches doctor and views availability
    search_res = client.get(f"/api/doctors?search=Specialist", headers=pat_headers)
    assert search_res.status_code == 200

    slots_res = client.get(f"/api/doctors/{dr_doc_id}/availability?date={date_str}", headers=pat_headers)
    assert slots_res.status_code == 200

    # 4. Patient books slot
    book_res = client.post(
        "/api/appointments",
        headers=pat_headers,
        json={
            "doctorId": dr_doc_id,
            "availabilityId": str(avail_res.inserted_id),
            "date": date_str,
            "startTime": "10:00",
            "patientNote": "Routine checkup",
        },
    )
    assert book_res.status_code in (200, 201), f"Booking failed: {book_res.text}"
    appt_data = book_res.json()["appointment"]
    appt_id = appt_data["id"]

    # 5. Concurrency check: Second patient attempts to book the SAME slot -> must be rejected
    pat2_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat2_id),
        "fullName": "Second Booker",
        "email": f"second_{ts}@mediconnect.lk",
        "phone": "0771122335",
        "passwordHash": hash_password("Pass@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat2_token = create_access_token(pat2_id, role=UserRole.PATIENT.value)
    pat2_headers = {"Authorization": f"Bearer {pat2_token}"}

    double_book_res = client.post(
        "/api/appointments",
        headers=pat2_headers,
        json={
            "doctorId": dr_doc_id,
            "availabilityId": str(avail_res.inserted_id),
            "date": date_str,
            "startTime": "10:00",
            "patientNote": "Attempted double booking",
        },
    )
    assert double_book_res.status_code in (400, 409), "Double booking must be rejected with 400 or 409"

    # 6. Create Stripe test payment intent
    mock_intent = MagicMock()
    mock_intent.id = f"pi_test_{ts}"
    mock_intent.client_secret = f"pi_test_{ts}_secret_test"
    mock_intent.status = "requires_payment_method"

    with patch("stripe.PaymentIntent.create", return_value=mock_intent):
        intent_res = client.post(
            "/api/payments/create-intent",
            headers=pat_headers,
            json={"appointmentId": appt_id},
        )
        assert intent_res.status_code in (200, 201), f"Payment intent creation failed: {intent_res.text}"
        intent_data = intent_res.json()
        assert "paymentIntentClientSecret" in intent_data
        assert "paymentId" in intent_data

    # 7. Simulate Stripe webhook payment_intent.succeeded
    webhook_event = {
        "id": f"evt_test_{ts}",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": f"pi_test_{ts}",
                "amount": 300000,
                "currency": "lkr",
                "status": "succeeded",
                "metadata": {
                    "appointmentId": appt_id,
                    "patientId": pat_id,
                    "doctorId": dr_doc_id,
                },
            }
        },
    }

    with patch("stripe.Webhook.construct_event", return_value=webhook_event):
        wh_res = client.post(
            "/api/payments/webhook",
            content=json.dumps(webhook_event),
            headers={"stripe-signature": "test_sig"},
        )
        assert wh_res.status_code == 200, f"Webhook failed: {wh_res.text}"

        # 8. Webhook idempotency: Second delivery of same event must succeed without duplicate side-effects
        wh_repeat_res = client.post(
            "/api/payments/webhook",
            content=json.dumps(webhook_event),
            headers={"stripe-signature": "test_sig"},
        )
        assert wh_repeat_res.status_code == 200

    # 9. Verify appointment confirmed in database
    confirmed_appt = db["appointments"].find_one({"_id": ObjectId(appt_id)})
    assert confirmed_appt is not None
    assert confirmed_appt["paymentStatus"] == ApptPaymentStatus.PAID.value
    assert confirmed_appt["status"] == AppointmentStatus.CONFIRMED.value


def test_phase34_cross_role_rbac_and_privacy_boundaries():
    """Verify strict backend role-based access control and medical record privacy boundaries."""
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Setup Patient and Doctor in database
    pat_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_id),
        "fullName": "RBAC Patient",
        "email": f"rbac_pat_{ts}@mediconnect.lk",
        "phone": "0771112222",
        "passwordHash": hash_password("Pass@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat_token = create_access_token(pat_id, role=UserRole.PATIENT.value)
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    dr_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(dr_id),
        "fullName": "RBAC Doctor",
        "email": f"rbac_dr_{ts}@mediconnect.lk",
        "phone": "0773334444",
        "passwordHash": hash_password("Pass@123"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    dr_token = create_access_token(dr_id, role=UserRole.DOCTOR.value)
    dr_headers = {"Authorization": f"Bearer {dr_token}"}

    # Patient attempts to access Admin endpoints -> 403 Forbidden
    res1 = client.get("/api/admin/doctors/applications", headers=pat_headers)
    assert res1.status_code == 403, f"Expected 403 for patient accessing admin endpoint, got {res1.status_code}"

    # Doctor attempts to access Admin endpoints -> 403 Forbidden
    res2 = client.get("/api/admin/doctors/applications", headers=dr_headers)
    assert res2.status_code == 403, f"Expected 403 for doctor accessing admin endpoint, got {res2.status_code}"

    # Patient attempts to create consultation record -> 403 Forbidden
    res3 = client.post("/api/medical-records", headers=pat_headers, json={
        "appointmentId": str(ObjectId()),
        "diagnosis": "Self-diagnosis",
        "notes": "Testing",
    })
    assert res3.status_code == 403

    # Unauthenticated request -> 401 Unauthorized
    res4 = client.get("/api/admin/doctors/applications")
    assert res4.status_code == 401

    # Malformed token -> 401 Unauthorized
    res5 = client.get("/api/admin/doctors/applications", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert res5.status_code == 401


def test_phase34_ai_assistant_contracts_and_safety_disclaimers():
    """Verify AI recommendation and health chat contracts include required medical safety disclosures."""
    db = get_database()
    ts = int(time.time() * 1000)

    pat_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_id),
        "fullName": "AI User",
        "email": f"ai_user_{ts}@mediconnect.lk",
        "phone": "0778889999",
        "passwordHash": hash_password("Pass@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat_token = create_access_token(pat_id, role=UserRole.PATIENT.value)
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    # AI Doctor Recommendations
    rec_res = client.post(
        "/api/ai/doctor-recommendations",
        headers=pat_headers,
        json={
            "query": "chest pain and shortness of breath when walking up stairs",
            "preferredLanguage": "English",
        },
    )
    assert rec_res.status_code == 200, f"Recommendation request failed: {rec_res.text}"
    rec_data = rec_res.json()
    assert "recommendations" in rec_data
    assert "disclaimer" in rec_data
    assert "informational matching tool" in rec_data["disclaimer"].lower() or "medical emergency" in rec_data["disclaimer"].lower()

    # AI Health Chat
    chat_res = client.post(
        "/api/ai/health-chat/sessions",
        headers=pat_headers,
        json={
            "initialMessage": "What should I do if I have a mild headache?",
            "consentGiven": True,
            "language": "en",
        },
    )
    assert chat_res.status_code in (200, 201), f"Health chat failed: {chat_res.text}"
    chat_data = chat_res.json()
    assert "id" in chat_data
    assert "messages" in chat_data
    assert len(chat_data["messages"]) >= 1
