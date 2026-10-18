from datetime import datetime, timedelta, timezone
import time
from bson import ObjectId
import jwt
import pytest
from fastapi.testclient import TestClient
from pymongo.database import Database

from app.config.database import check_database_connection, ensure_indexes, get_database
from app.config.settings import settings
from app.main import app
from app.models.appointment import AppointmentStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.medical_record import get_medical_record_collection, MedicalRecordStatus
from app.models.notification import get_device_token_collection
from app.models.prescription import get_prescription_collection, PrescriptionStatus
from app.models.user import AccountStatus, UserRole
from app.services.notification_service import NotificationService
from app.utils.rate_limiter import SlidingWindowRateLimiter, auth_login_limiter
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


def test_mongodb_index_creation_idempotency():
    """Verify that ensure_indexes executes cleanly without OperationFailure or index conflicts."""
    db_status = check_database_connection()
    if not db_status.get("connected"):
        pytest.skip("MongoDB connection not active in test environment.")

    # Call ensure_indexes twice to verify total idempotency
    success_first = ensure_indexes()
    success_second = ensure_indexes()
    assert success_first is True, "First ensure_indexes call failed."
    assert success_second is True, "Second ensure_indexes call failed on existing indexes."


def test_health_check_endpoint_no_secrets_leaked():
    """Verify /health endpoint returns status without exposing sensitive credentials or URIs."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "api" in data
    assert "database" in data
    assert "password" not in res.text.lower()
    assert "secret" not in res.text.lower()
    assert "mongodb+srv" not in res.text.lower()


def test_security_headers_present():
    """Verify defensive security response headers on HTTP endpoints."""
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "1; mode=block" in res.headers.get("X-XSS-Protection", "")
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in res.headers.get("Permissions-Policy", "")


def test_sliding_window_rate_limiter():
    """Verify rate limiter blocks excessive requests with HTTP 429 and resets cleanly."""
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60, name="unit_test")
    test_key = "192.168.1.100"

    # 3 requests should succeed
    limiter.check(test_key)
    limiter.check(test_key)
    limiter.check(test_key)

    # 4th request must raise 429
    with pytest.raises(Exception) as exc_info:
        limiter.check(test_key)
    assert "429" in str(exc_info.value) or exc_info.value.status_code == 429

    # Reset allows new requests
    limiter.reset()
    limiter.check(test_key)


def test_rbac_unauthorized_role_access():
    """Verify non-admin user cannot access admin verification endpoints."""
    db = get_database()
    now = datetime.now(timezone.utc)
    test_user_id = ObjectId()

    # Create active patient in database
    db["users"].insert_one({
        "_id": test_user_id,
        "fullName": "Audit Patient",
        "email": f"audit.patient.{int(time.time())}@mediconnect.lk",
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": "ACTIVE",
        "createdAt": now,
        "updatedAt": now,
    })

    try:
        patient_token = create_access_token(user_id=str(test_user_id), role=UserRole.PATIENT.value)

        # Authenticated patient attempting to access admin route must receive 403 Forbidden
        res = client.get(
            "/api/admin/doctors/applications",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert res.status_code == 403
        assert "permission" in res.json().get("detail", "").lower()
    finally:
        db["users"].delete_one({"_id": test_user_id})

    # Unknown or non-existent user token must receive 401
    ghost_token = create_access_token(user_id=str(ObjectId()), role=UserRole.PATIENT.value)
    res_ghost = client.get(
        "/api/admin/doctors/applications",
        headers={"Authorization": f"Bearer {ghost_token}"},
    )
    assert res_ghost.status_code == 401


def test_tampered_jwt_token_rejection():
    """Verify tampered JWT signature is rejected with 401 Unauthorized."""
    valid_token = create_access_token(user_id="user_abc", role=UserRole.PATIENT.value)
    # Tamper with signature
    tampered_token = valid_token[:-4] + "xxxx"

    res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res.status_code == 401
    assert "credentials" in res.json().get("detail", "").lower()


def test_anonymous_access_denied_to_medical_records():
    """Verify anonymous access to medical records endpoint is blocked with 401."""
    res = client.get("/api/medical-records/me")
    assert res.status_code == 401


def test_anonymous_access_denied_to_prescriptions():
    """Verify anonymous access to prescriptions endpoint is blocked with 401."""
    res = client.get("/api/prescriptions/me")
    assert res.status_code == 401


def test_jwt_expired_token_rejection():
    """Verify that expired JWT access token is rejected with 401 and clear expiration message."""
    expired_token = create_access_token(
        user_id="user_test_exp",
        role=UserRole.PATIENT.value,
        expires_delta=timedelta(seconds=-10),
    )
    res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "expired" in res.json().get("detail", "").lower()


def test_jwt_missing_role_claim_rejection():
    """Verify that JWT token missing the required role claim is strictly rejected with 401."""
    now = datetime.now(timezone.utc)
    raw_payload = {
        "sub": "user_test_norole",
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token_without_role = jwt.encode(raw_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token_without_role}"},
    )
    assert res.status_code == 401


def test_device_token_cross_account_isolation():
    """Verify that registering an FCM token on a shared device deletes prior user associations."""
    db = get_database()
    col = get_device_token_collection(db)
    token = f"fcm_test_token_{int(time.time())}"
    user_a = str(ObjectId())
    user_b = str(ObjectId())

    try:
        # User A registers the token
        res_a = NotificationService.register_device_token(
            db=db, user_id=user_a, fcm_token=token, device_type="android"
        )
        assert res_a.success is True
        assert col.find_one({"userId": user_a, "fcmToken": token}) is not None

        # User B logs in and registers the same physical device token
        res_b = NotificationService.register_device_token(
            db=db, user_id=user_b, fcm_token=token, device_type="android"
        )
        assert res_b.success is True

        # User A's token mapping must be deleted; User B must be the sole owner
        assert col.find_one({"userId": user_a, "fcmToken": token}) is None
        assert col.find_one({"userId": user_b, "fcmToken": token}) is not None
    finally:
        col.delete_many({"fcmToken": token})


def test_cross_patient_medical_record_access_forbidden():
    """Verify that Patient A cannot access Patient B's medical consultation record (IDOR defense)."""
    db = get_database()
    now = datetime.now(timezone.utc)
    patient_a_id = ObjectId()
    patient_b_id = ObjectId()
    doctor_id = ObjectId()
    rec_coll = get_medical_record_collection(db)
    rec_id = f"REC-AUDIT-{int(time.time())}"

    # Insert test users
    for p_id, email, role in [
        (patient_a_id, f"pat_a_{int(time.time())}@audit.lk", UserRole.PATIENT.value),
        (patient_b_id, f"pat_b_{int(time.time())}@audit.lk", UserRole.PATIENT.value),
    ]:
        db["users"].insert_one({
            "_id": p_id,
            "fullName": "Audit Patient",
            "email": email,
            "role": role,
            "emailVerified": True,
            "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": now,
        })

    # Insert medical record for Patient B
    rec_coll.insert_one({
        "recordId": rec_id,
        "patientUserId": str(patient_b_id),
        "doctorUserId": str(doctor_id),
        "appointmentId": "APPT-DUMMY-001",
        "consultationDate": "2026-10-18",
        "clinicalNotes": "Confidential patient B diagnosis.",
        "assessment": "Healthy",
        "treatmentPlan": "Rest",
        "status": MedicalRecordStatus.ACTIVE.value,
        "amendmentHistory": [],
        "auditLog": [],
        "createdAt": now,
        "updatedAt": now,
    })

    try:
        token_a = create_access_token(user_id=str(patient_a_id), role=UserRole.PATIENT.value)
        res = client.get(
            f"/api/medical-records/{rec_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 403
        assert "authorization" in res.json().get("detail", "").lower()
    finally:
        db["users"].delete_many({"_id": {"$in": [patient_a_id, patient_b_id]}})
        rec_coll.delete_one({"recordId": rec_id})


def test_cross_patient_prescription_pdf_forbidden():
    """Verify that Patient A cannot download Patient B's digital prescription PDF."""
    db = get_database()
    now = datetime.now(timezone.utc)
    patient_a_id = ObjectId()
    patient_b_id = ObjectId()
    doctor_id = ObjectId()
    rx_coll = get_prescription_collection(db)
    rx_id = f"RX-AUDIT-{int(time.time())}"

    for p_id, email in [
        (patient_a_id, f"pat_rx_a_{int(time.time())}@audit.lk"),
        (patient_b_id, f"pat_rx_b_{int(time.time())}@audit.lk"),
    ]:
        db["users"].insert_one({
            "_id": p_id,
            "fullName": "Audit Patient",
            "email": email,
            "role": UserRole.PATIENT.value,
            "emailVerified": True,
            "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": now,
        })

    rx_coll.insert_one({
        "prescriptionId": rx_id,
        "medicalRecordId": "REC-DUMMY",
        "appointmentId": "APPT-DUMMY",
        "patientUserId": str(patient_b_id),
        "doctorUserId": str(doctor_id),
        "status": PrescriptionStatus.ISSUED.value,
        "medicationItems": [],
        "issuedAt": now,
        "createdAt": now,
        "updatedAt": now,
    })

    try:
        token_a = create_access_token(user_id=str(patient_a_id), role=UserRole.PATIENT.value)
        res = client.get(
            f"/api/prescriptions/{rx_id}/pdf",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 403
        assert "authorization" in res.json().get("detail", "").lower()
    finally:
        db["users"].delete_many({"_id": {"$in": [patient_a_id, patient_b_id]}})
        rx_coll.delete_one({"prescriptionId": rx_id})


def test_unverified_doctor_cannot_create_availability():
    """Verify that a PENDING or unverified doctor cannot create appointment availability."""
    db = get_database()
    now = datetime.now(timezone.utc)
    doctor_user_id = ObjectId()

    timestamp_val = int(time.time() * 1000)
    db["users"].insert_one({
        "_id": doctor_user_id,
        "fullName": "Pending Doctor",
        "email": f"dr_pending_{timestamp_val}@audit.lk",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.PENDING.value,
        "createdAt": now,
    })
    db["doctor_profiles"].insert_one({
        "userId": str(doctor_user_id),
        "doctorId": f"DOC-{timestamp_val}",
        "specialty": "Cardiology",
        "medicalRegistrationNumber": f"SLMC-AUDIT-{timestamp_val}",
        "verificationStatus": DoctorVerificationStatus.PENDING.value,
        "submittedAt": now,
    })

    try:
        doctor_token = create_access_token(user_id=str(doctor_user_id), role=UserRole.DOCTOR.value)
        payload = {
            "date": "2026-10-25",
            "startTime": "09:00",
            "endTime": "12:00",
            "slotDurationMinutes": 30,
        }
        res = client.post(
            "/api/doctors/me/availability",
            json=payload,
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        assert res.status_code == 403
    finally:
        db["users"].delete_one({"_id": doctor_user_id})
        db["doctor_profiles"].delete_one({"userId": str(doctor_user_id)})


def test_stripe_webhook_invalid_signature_rejection():
    """Verify Stripe webhook endpoint rejects requests with invalid or missing signature."""
    res = client.post(
        "/api/payments/webhook",
        content=b'{"type": "payment_intent.succeeded"}',
        headers={"Stripe-Signature": "t=12345,v1=invalidsignature"},
    )
    assert res.status_code == 400
    assert "signature" in res.json().get("detail", "").lower() or "payload" in res.json().get("detail", "").lower()


def test_non_patient_cannot_access_ai_booking():
    """Verify that a non-patient role (Doctor) cannot access AI Booking Assistant sessions."""
    db = get_database()
    now = datetime.now(timezone.utc)
    doc_id = ObjectId()

    db["users"].insert_one({
        "_id": doc_id,
        "fullName": "Dr. Test AI",
        "email": f"dr_ai_{int(time.time())}@audit.lk",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": now,
    })

    try:
        doctor_token = create_access_token(user_id=str(doc_id), role=UserRole.DOCTOR.value)
        res = client.post(
            "/api/ai/booking/sessions",
            json={"initialMessage": "Book appointment"},
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        assert res.status_code == 403
    finally:
        db["users"].delete_one({"_id": doc_id})


def test_non_admin_cannot_moderate_reviews():
    """Verify that non-admin role (Patient) cannot moderate reviews."""
    db = get_database()
    now = datetime.now(timezone.utc)
    patient_id = ObjectId()

    db["users"].insert_one({
        "_id": patient_id,
        "fullName": "Regular Patient",
        "email": f"pat_mod_{int(time.time())}@audit.lk",
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": now,
    })

    try:
        patient_token = create_access_token(user_id=str(patient_id), role=UserRole.PATIENT.value)
        res = client.patch(
            "/api/reviews/REV-12345/moderate",
            json={"action": "HIDE", "reason": "Violates guidelines"},
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert res.status_code == 403
    finally:
        db["users"].delete_one({"_id": patient_id})


def test_non_admin_cannot_access_analytics():
    """Verify that non-admin role (Patient) cannot access admin analytics overview."""
    db = get_database()
    now = datetime.now(timezone.utc)
    patient_id = ObjectId()

    db["users"].insert_one({
        "_id": patient_id,
        "fullName": "Regular Patient",
        "email": f"pat_analytics_{int(time.time())}@audit.lk",
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": now,
    })

    try:
        patient_token = create_access_token(user_id=str(patient_id), role=UserRole.PATIENT.value)
        res = client.get(
            "/api/admin/analytics/overview",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert res.status_code == 403
    finally:
        db["users"].delete_one({"_id": patient_id})
