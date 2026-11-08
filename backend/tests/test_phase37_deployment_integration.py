"""Phase 37: Staging Deployment Integration Verification & Admin Login Test Suite.

Validates:
1. Backend health probe (/health and /api/health) without credential leakage.
2. Backend readiness probe (/ready and /api/ready).
3. CORS configuration for Vercel staging domains (*.vercel.app) and preflight handling.
4. Admin authentication via /api/auth/login, JWT claims, and role assignment.
5. Invalid credentials rejection (wrong password, unknown user) with generic 401 error.
6. Account status verification (unverified email, suspended accounts blocked).
7. Role-Based Access Control (RBAC) on administrative endpoints (/api/admin/*).
8. Protected dashboard and analytics access with Admin tokens.
9. Session logout and refresh token invalidation via /api/auth/logout.
"""

import time
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.config.database import check_database_connection, get_database
from app.main import app
from app.models.user import AccountStatus, UserRole, utc_now
from app.utils.security import create_access_token, decode_access_token, hash_password

client = TestClient(app)


def test_health_check_endpoints():
    """Verify both /health and /api/health return healthy status without exposing secrets."""
    for path in ["/health", "/api/health"]:
        resp = client.get(path)
        assert resp.status_code == 200, f"Failed at path {path}"
        data = resp.json()
        assert data["api"] == "healthy"
        assert "database" in data
        assert data["database"]["connected"] is True
        # Verify no credentials leaked
        assert "password" not in resp.text.lower()
        assert "mongodb+srv" not in resp.text.lower()
        assert "secret" not in resp.text.lower()


def test_readiness_check_endpoints():
    """Verify /ready and /api/ready return ready status."""
    for path in ["/ready", "/api/ready"]:
        resp = client.get(path)
        assert resp.status_code == 200, f"Failed at path {path}"
        data = resp.json()
        assert data["status"] == "ready"


def test_cors_vercel_staging_origin():
    """Verify CORS preflight and responses accept actual Vercel staging domains."""
    vercel_origins = [
        "https://mediconnect-admin.vercel.app",
        "https://mediconnect-admin-staging.vercel.app",
        "https://mediconnect-admin-git-phase37.vercel.app",
        "https://preview-123.vercel.app",
    ]

    for origin in vercel_origins:
        # Preflight OPTIONS request
        resp_opt = client.options(
            "/api/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization",
            },
        )
        assert resp_opt.status_code == 200, f"Preflight failed for {origin}"
        assert resp_opt.headers.get("access-control-allow-origin") == origin
        assert resp_opt.headers.get("access-control-allow-credentials") == "true"

        # Actual GET request
        resp_get = client.get("/api/health", headers={"Origin": origin})
        assert resp_get.status_code == 200
        assert resp_get.headers.get("access-control-allow-origin") == origin

    # Reject unauthorized origin
    resp_bad = client.options(
        "/api/auth/login",
        headers={
            "Origin": "https://malicious-phishing-site.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp_bad.status_code == 400


def test_admin_login_and_token_handling():
    """Verify admin login returns JWT with ADMIN role and valid claims."""
    db = get_database()
    ts = int(time.time() * 1000)
    admin_email = f"stg_admin_{ts}@mediconnect.lk"
    password = "AdminSecurePassword@2026"
    admin_id = str(ObjectId())

    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "fullName": "Staging Administrator",
        "email": admin_email,
        "phone": "0771234567",
        "passwordHash": hash_password(password),
        "role": UserRole.ADMIN.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 1. Successful login
    resp = client.post(
        "/api/auth/login",
        json={"email": admin_email, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "accessToken" in data
    assert "refreshToken" in data
    assert data["tokenType"] == "bearer"
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["email"] == admin_email
    assert data["user"]["accountStatus"] == "ACTIVE"
    assert "passwordHash" not in data["user"]

    # 2. Verify decoded JWT payload
    token_claims = decode_access_token(data["accessToken"])
    assert token_claims["sub"] == admin_id
    assert token_claims["role"] == "ADMIN"

    # 3. Access current user profile via /api/auth/me
    resp_me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['accessToken']}"},
    )
    assert resp_me.status_code == 200
    me_data = resp_me.json()
    assert me_data["id"] == admin_id
    assert me_data["role"] == "ADMIN"


def test_login_invalid_credentials_handling():
    """Verify login handles invalid password and non-existent email safely."""
    # Unknown user
    resp_unknown = client.post(
        "/api/auth/login",
        json={"email": "nonexistent_user@mediconnect.lk", "password": "WrongPassword@123"},
    )
    assert resp_unknown.status_code == 401
    assert "invalid email or password" in resp_unknown.json()["detail"].lower()

    # Wrong password for existing user
    db = get_database()
    ts = int(time.time() * 1000)
    email = f"user_wrong_pw_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(),
        "fullName": "Test User",
        "email": email,
        "passwordHash": hash_password("CorrectPassword@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
    })

    resp_wrong_pw = client.post(
        "/api/auth/login",
        json={"email": email, "password": "BadPassword@999"},
    )
    assert resp_wrong_pw.status_code == 401
    assert "invalid email or password" in resp_wrong_pw.json()["detail"].lower()


def test_login_unverified_and_suspended_rejection():
    """Verify login strictly rejects unverified emails and suspended accounts."""
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Unverified user
    unverified_email = f"unverified_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(),
        "fullName": "Unverified User",
        "email": unverified_email,
        "passwordHash": hash_password("ValidPassword@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": False,
        "accountStatus": AccountStatus.PENDING.value,
        "createdAt": utc_now(),
    })
    resp_unverified = client.post(
        "/api/auth/login",
        json={"email": unverified_email, "password": "ValidPassword@123"},
    )
    assert resp_unverified.status_code == 403
    assert "verification is required" in resp_unverified.json()["detail"].lower()

    # 2. Suspended user
    suspended_email = f"suspended_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(),
        "fullName": "Suspended Admin",
        "email": suspended_email,
        "passwordHash": hash_password("ValidPassword@123"),
        "role": UserRole.ADMIN.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.SUSPENDED.value,
        "createdAt": utc_now(),
    })
    resp_suspended = client.post(
        "/api/auth/login",
        json={"email": suspended_email, "password": "ValidPassword@123"},
    )
    assert resp_suspended.status_code == 403
    assert "suspended" in resp_suspended.json()["detail"].lower()


def test_protected_dashboard_rbac_access():
    """Verify protected admin dashboard and user management enforce ADMIN role."""
    db = get_database()
    ts = int(time.time() * 1000)

    # Patient user
    patient_id = str(ObjectId())
    patient_token = create_access_token(patient_id, role=UserRole.PATIENT.value)

    # Admin user
    admin_id = str(ObjectId())
    admin_token = create_access_token(admin_id, role=UserRole.ADMIN.value)

    db["users"].insert_many([
        {
            "_id": ObjectId(patient_id),
            "fullName": "Regular Patient",
            "email": f"rbac_patient_{ts}@mediconnect.lk",
            "role": UserRole.PATIENT.value,
            "emailVerified": True,
            "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": utc_now(),
        },
        {
            "_id": ObjectId(admin_id),
            "fullName": "RBAC Admin",
            "email": f"rbac_admin_{ts}@mediconnect.lk",
            "role": UserRole.ADMIN.value,
            "emailVerified": True,
            "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": utc_now(),
        },
    ])

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    # 1. Anonymous access -> 401
    assert client.get("/api/admin/users").status_code == 401
    assert client.get("/api/admin/analytics/overview").status_code == 401

    # 2. Patient access -> 403 Forbidden
    assert client.get("/api/admin/users", headers=patient_headers).status_code == 403
    assert client.get("/api/admin/analytics/overview", headers=patient_headers).status_code == 403

    # 3. Admin access -> 200 OK
    resp_users = client.get("/api/admin/users", headers=admin_headers)
    assert resp_users.status_code == 200
    assert "items" in resp_users.json()

    resp_overview = client.get("/api/admin/analytics/overview", headers=admin_headers)
    assert resp_overview.status_code == 200
    assert "totalPatients" in resp_overview.json()


def test_logout_and_session_invalidation():
    """Verify logout revokes the refresh token and subsequent refresh fails."""
    db = get_database()
    ts = int(time.time() * 1000)
    email = f"logout_user_{ts}@mediconnect.lk"
    password = "LogoutPassword@123"

    db["users"].insert_one({
        "_id": ObjectId(),
        "fullName": "Logout User",
        "email": email,
        "passwordHash": hash_password(password),
        "role": UserRole.ADMIN.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
    })

    login_resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refreshToken"]

    # Logout
    logout_resp = client.post(
        "/api/auth/logout",
        json={"refreshToken": refresh_token},
    )
    assert logout_resp.status_code == 200
    assert "logged out" in logout_resp.json()["message"].lower()

    # Attempt to use revoked refresh token -> 401
    refresh_attempt = client.post(
        "/api/auth/refresh",
        json={"refreshToken": refresh_token},
    )
    assert refresh_attempt.status_code == 401

