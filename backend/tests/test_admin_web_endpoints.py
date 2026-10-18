"""Tests for Phase 31 Admin Web backend endpoints."""

import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.user import AccountStatus, UserRole, utc_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


def test_admin_web_endpoints_rbac_and_crud():
    db = get_database()
    timestamp = int(time.time() * 1000)

    # 1. Setup Admin User
    admin_email = f"admin_web_{timestamp}@mediconnect.lk"
    admin_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "fullName": "Admin Web Manager",
        "email": admin_email,
        "phone": "0770009988",
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
    patient_email = f"patient_web_{timestamp}@mediconnect.lk"
    patient_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(patient_id),
        "fullName": "Web Patient",
        "email": patient_email,
        "phone": "0771122889",
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

    # 3. RBAC checks on /api/admin/users
    # Anonymous -> 401
    resp_anon = client.get("/api/admin/users")
    assert resp_anon.status_code == 401

    # Patient -> 403 Forbidden
    resp_patient = client.get("/api/admin/users", headers=patient_headers)
    assert resp_patient.status_code == 403

    # Admin -> 200 OK
    resp_admin = client.get("/api/admin/users", headers=admin_headers)
    assert resp_admin.status_code == 200
    data = resp_admin.json()
    assert "items" in data
    assert data["total"] >= 2
    # Verify least privilege: passwordHash must NOT be in returned data
    for item in data["items"]:
        assert "passwordHash" not in item
        assert "password" not in item

    # 4. Search and filter on /api/admin/users
    resp_search = client.get(f"/api/admin/users?search=Web%20Patient", headers=admin_headers)
    assert resp_search.status_code == 200
    search_data = resp_search.json()
    assert any(u["id"] == patient_id for u in search_data["items"])

    resp_filter_role = client.get("/api/admin/users?role=PATIENT", headers=admin_headers)
    assert resp_filter_role.status_code == 200
    role_data = resp_filter_role.json()
    assert all(u["role"] == "PATIENT" for u in role_data["items"])

    # 5. User Status Update
    # Cannot suspend own admin account
    resp_self = client.patch(
        f"/api/admin/users/{admin_id}/status",
        headers=admin_headers,
        json={"accountStatus": "SUSPENDED"},
    )
    assert resp_self.status_code == 400
    assert "own account status" in resp_self.json()["detail"]

    # Can update patient status
    resp_update = client.patch(
        f"/api/admin/users/{patient_id}/status",
        headers=admin_headers,
        json={"accountStatus": "SUSPENDED"},
    )
    assert resp_update.status_code == 200
    updated_user = db["users"].find_one({"_id": ObjectId(patient_id)})
    assert updated_user["accountStatus"] == "SUSPENDED"

    # Restore patient status
    client.patch(
        f"/api/admin/users/{patient_id}/status",
        headers=admin_headers,
        json={"accountStatus": "ACTIVE"},
    )

    # 6. Admin Doctors Directory
    resp_docs = client.get("/api/admin/doctors", headers=admin_headers)
    assert resp_docs.status_code == 200
    assert "items" in resp_docs.json()

    # 7. Admin Appointments
    # Insert test appointment
    appt_id = ObjectId()
    db["appointments"].insert_one({
        "_id": appt_id,
        "patientUserId": patient_id,
        "doctorUserId": admin_id,
        "doctorProfileId": str(ObjectId()),
        "appointmentDate": "2026-10-25",
        "startTime": "09:00",
        "endTime": "09:30",
        "status": "CONFIRMED",
        "paymentStatus": "PAID",
        "consultationFee": 3000.0,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    resp_appts = client.get("/api/admin/appointments", headers=admin_headers)
    assert resp_appts.status_code == 200
    appts_data = resp_appts.json()
    assert appts_data["total"] >= 1
    assert any(a["id"] == str(appt_id) for a in appts_data["items"])

    # 8. Admin Payments
    payment_id = ObjectId()
    db["payments"].insert_one({
        "_id": payment_id,
        "appointmentId": str(appt_id),
        "patientUserId": patient_id,
        "doctorUserId": admin_id,
        "stripePaymentIntentId": "pi_test_1234567890",
        "amount": 3000.0,
        "currency": "lkr",
        "status": "SUCCEEDED",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    resp_payments = client.get("/api/admin/payments", headers=admin_headers)
    assert resp_payments.status_code == 200
    payments_data = resp_payments.json()
    assert payments_data["total"] >= 1
    assert any(p["id"] == str(payment_id) for p in payments_data["items"])
    test_pmt = next(p for p in payments_data["items"] if p["id"] == str(payment_id))
    assert test_pmt["isTestMode"] is True

    # 9. Admin Reviews
    review_id = ObjectId()
    db["reviews"].insert_one({
        "_id": review_id,
        "appointmentId": str(appt_id),
        "patientId": patient_id,
        "doctorId": admin_id,
        "rating": 5,
        "reviewText": "Excellent care and punctuality.",
        "status": "PUBLISHED",
        "isReported": False,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    resp_reviews = client.get("/api/admin/reviews", headers=admin_headers)
    assert resp_reviews.status_code == 200
    reviews_data = resp_reviews.json()
    assert reviews_data["total"] >= 1
    assert any(r["id"] == str(review_id) for r in reviews_data["items"])
