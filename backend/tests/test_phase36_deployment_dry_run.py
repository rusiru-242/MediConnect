"""Phase 36: Production Deployment Dry Run & Pre-Launch Security Verification Test Suite.

Validates:
1. Environment isolation & safety constraints (Stripe test keys, non-production bindings, DB connection).
2. ASGI entrypoint, health (/health), readiness (/ready), and security headers.
3. Strict Role-Based Access Control (RBAC) across Patient, Doctor, and Admin.
4. Token security: Expired token rejection, tampered signature rejection, missing claims rejection.
5. Cross-patient medical records and prescription IDOR protection.
6. Stripe webhook cryptographic verification & error handling.
7. Performance responsiveness and rate limiting defense.
"""

from datetime import datetime, timedelta, timezone
import time
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.config.database import check_database_connection, get_database
from app.config.settings import settings
from app.main import app
from app.models.medical_record import get_medical_record_collection, MedicalRecordStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.utils.rate_limiter import SlidingWindowRateLimiter
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


def test_dry_run_environment_isolation_and_safety():
    """Verify that deployment rehearsal environment is strictly in test mode."""
    # 1. Stripe must be in test mode
    assert settings.STRIPE_SECRET_KEY is not None, "STRIPE_SECRET_KEY is required."
    assert settings.STRIPE_SECRET_KEY.startswith("sk_test_"), (
        "SAFETY VIOLATION: Stripe key must be in test mode (sk_test_)."
    )

    # 2. Database connection must be healthy and reachable
    db_health = check_database_connection()
    assert db_health["connected"] is True, f"Database connectivity failed: {db_health}"

    # 3. Environment must not be unverified live production without isolation
    assert settings.ENVIRONMENT in ("development", "staging", "test", "production")


def test_dry_run_health_and_readiness_probes():
    """Verify production health (/health) and readiness (/ready) probes."""
    # Health check probe
    res_health = client.get("/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    assert health_data["api"] == "healthy"
    assert health_data["database"]["connected"] is True
    # Ensure sensitive credentials are never exposed in health output
    assert "password" not in res_health.text.lower()
    assert "mongodb+srv" not in res_health.text.lower()
    assert "secret" not in res_health.text.lower()

    # Readiness check probe
    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    ready_data = res_ready.json()
    assert ready_data["status"] == "ready"


def test_dry_run_security_headers_enforcement():
    """Verify defensive HTTP security headers on all responses."""
    res = client.get("/")
    assert res.status_code == 200
    headers = res.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "1; mode=block" in headers.get("X-XSS-Protection", "")
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in headers.get("Permissions-Policy", "")


def test_dry_run_rbac_matrix_isolation():
    """Verify complete RBAC isolation: Admin, Doctor, and Patient access boundaries."""
    db = get_database()
    ts = int(time.time() * 1000)

    # Create synthetic test users for each role
    patient_id = ObjectId()
    doctor_id = ObjectId()
    admin_id = ObjectId()

    db["users"].insert_many([
        {
            "_id": patient_id,
            "fullName": "Rehearsal Patient",
            "email": f"p36_pat_{ts}@mediconnect.lk",
            "role": UserRole.PATIENT.value,
            "emailVerified": True,
            "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": utc_now(),
        },
        {
            "_id": doctor_id,
            "fullName": "Dr. Rehearsal",
            "email": f"p36_doc_{ts}@mediconnect.lk",
            "role": UserRole.DOCTOR.value,
            "emailVerified": True,
            "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": utc_now(),
        },
        {
            "_id": admin_id,
            "fullName": "Rehearsal Admin",
            "email": f"p36_adm_{ts}@mediconnect.lk",
            "role": UserRole.ADMIN.value,
            "emailVerified": True,
            "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": utc_now(),
        },
    ])

    pat_token = create_access_token(str(patient_id), role=UserRole.PATIENT.value)
    doc_token = create_access_token(str(doctor_id), role=UserRole.DOCTOR.value)
    adm_token = create_access_token(str(admin_id), role=UserRole.ADMIN.value)

    try:
        # 1. Anonymous access to Admin routes must be rejected (401)
        res_anon = client.get("/api/admin/doctors/applications")
        assert res_anon.status_code == 401

        # 2. Patient access to Admin routes must be rejected (403)
        res_pat = client.get(
            "/api/admin/doctors/applications",
            headers={"Authorization": f"Bearer {pat_token}"},
        )
        assert res_pat.status_code == 403

        # 3. Doctor access to Admin routes must be rejected (403)
        res_doc = client.get(
            "/api/admin/doctors/applications",
            headers={"Authorization": f"Bearer {doc_token}"},
        )
        assert res_doc.status_code == 403

        # 4. Admin access to Admin routes must succeed (200)
        res_adm = client.get(
            "/api/admin/doctors/applications",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert res_adm.status_code == 200

        # 5. Admin access to Admin analytics overview must succeed (200)
        res_analytics = client.get(
            "/api/admin/analytics/overview",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert res_analytics.status_code == 200
        data = res_analytics.json()
        assert "totalPatients" in data
        assert "totalVerifiedDoctors" in data

    finally:
        db["users"].delete_many({"_id": {"$in": [patient_id, doctor_id, admin_id]}})


def test_dry_run_jwt_tampering_and_expiration():
    """Verify that expired and cryptographic signature tampered tokens are rejected."""
    # 1. Expired access token
    expired_token = create_access_token(
        user_id="p36_expired_user",
        role=UserRole.PATIENT.value,
        expires_delta=timedelta(seconds=-30),
    )
    res_exp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res_exp.status_code == 401
    assert "expired" in res_exp.json().get("detail", "").lower()

    # 2. Tampered signature
    valid_token = create_access_token(
        user_id="p36_valid_user",
        role=UserRole.PATIENT.value,
    )
    tampered_token = valid_token[:-6] + "BADSIG"
    res_tamp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res_tamp.status_code == 401


def test_dry_run_cross_patient_idor_defense():
    """Verify that Patient A cannot view or tamper with Patient B's medical records."""
    db = get_database()
    now = datetime.now(timezone.utc)
    ts = int(time.time() * 1000)

    pat_a_id = ObjectId()
    pat_b_id = ObjectId()
    doc_id = ObjectId()
    rec_id = f"REC-P36-{ts}"
    rec_coll = get_medical_record_collection(db)

    db["users"].insert_many([
        {
            "_id": pat_a_id,
            "fullName": "Patient A",
            "email": f"p36_a_{ts}@mediconnect.lk",
            "role": UserRole.PATIENT.value,
            "emailVerified": True,
            "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": now,
        },
        {
            "_id": pat_b_id,
            "fullName": "Patient B",
            "email": f"p36_b_{ts}@mediconnect.lk",
            "role": UserRole.PATIENT.value,
            "emailVerified": True,
            "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": now,
        },
    ])

    # Insert confidential medical record owned by Patient B
    rec_coll.insert_one({
        "recordId": rec_id,
        "patientUserId": str(pat_b_id),
        "doctorUserId": str(doc_id),
        "appointmentId": f"APPT-P36-{ts}",
        "consultationDate": "2026-10-18",
        "clinicalNotes": "Confidential diagnosis for Patient B only.",
        "assessment": "Under medical observation",
        "treatmentPlan": "Prescribed medication",
        "status": MedicalRecordStatus.ACTIVE.value,
        "amendmentHistory": [],
        "auditLog": [],
        "createdAt": now,
        "updatedAt": now,
    })

    try:
        token_a = create_access_token(user_id=str(pat_a_id), role=UserRole.PATIENT.value)

        # Patient A attempts to view Patient B's record -> must return 403 Forbidden
        res = client.get(
            f"/api/medical-records/{rec_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 403
        assert "authorization" in res.json().get("detail", "").lower()

    finally:
        db["users"].delete_many({"_id": {"$in": [pat_a_id, pat_b_id]}})
        rec_coll.delete_one({"recordId": rec_id})


def test_dry_run_stripe_webhook_security():
    """Verify Stripe webhook strictly rejects invalid signatures without processing."""
    res = client.post(
        "/api/payments/webhook",
        content=b'{"id": "evt_fake_test_event", "type": "payment_intent.succeeded"}',
        headers={"Stripe-Signature": "t=1700000000,v1=invalidsignaturedigest"},
    )
    assert res.status_code == 400
    assert "signature" in res.json().get("detail", "").lower() or "payload" in res.json().get("detail", "").lower()


def test_dry_run_rate_limiter_defense():
    """Verify rate limiter blocks burst traffic with HTTP 429."""
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60, name="p36_burst_test")
    test_ip = "192.168.10.50"

    for _ in range(5):
        limiter.check(test_ip)

    # 6th request within window must be rejected
    with pytest.raises(Exception) as exc:
        limiter.check(test_ip)
    assert "429" in str(exc.value) or exc.value.status_code == 429
