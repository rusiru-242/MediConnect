from datetime import datetime, timezone
import time
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient
from pymongo.database import Database

from app.config.database import check_database_connection, ensure_indexes, get_database
from app.config.settings import settings
from app.main import app
from app.models.user import UserRole
from app.utils.rate_limiter import SlidingWindowRateLimiter, auth_login_limiter
from app.utils.security import create_access_token

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
