"""Integration and unit tests for Health & Wellness Content Management and Admin Analytics (Phase 24)."""

from datetime import datetime, timezone
import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.appointment import AppointmentStatus, PaymentStatus as ApptPaymentStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.health_content import ContentStatus
from app.models.payment import PaymentStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_users():
    """Create synthetic admin and patient users for testing."""
    db = get_database()
    ts = int(time.time() * 1000)

    admin_id = str(ObjectId())
    admin_email = f"admin_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "fullName": "Test Administrator",
        "email": admin_email,
        "phone": "0771000001",
        "passwordHash": hash_password("AdminPass@123"),
        "role": UserRole.ADMIN.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    admin_token = create_access_token(admin_id, role=UserRole.ADMIN.value)

    patient_id = str(ObjectId())
    patient_email = f"patient_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(patient_id),
        "fullName": "Test Patient",
        "email": patient_email,
        "phone": "0772000002",
        "passwordHash": hash_password("PatientPass@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    patient_token = create_access_token(patient_id, role=UserRole.PATIENT.value)

    patient2_id = str(ObjectId())
    patient2_email = f"patient2_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(patient2_id),
        "fullName": "Second Patient",
        "email": patient2_email,
        "phone": "0773000003",
        "passwordHash": hash_password("PatientPass2@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    patient2_token = create_access_token(patient2_id, role=UserRole.PATIENT.value)

    return {
        "admin": {"id": admin_id, "token": admin_token, "headers": {"Authorization": f"Bearer {admin_token}"}},
        "patient": {"id": patient_id, "token": patient_token, "headers": {"Authorization": f"Bearer {patient_token}"}},
        "patient2": {"id": patient2_id, "token": patient2_token, "headers": {"Authorization": f"Bearer {patient2_token}"}},
    }


def test_admin_content_creation_and_lifecycle(setup_users):
    """Test full lifecycle: create draft, unauthorized protection, update, publish, feed visibility, archive."""
    admin_headers = setup_users["admin"]["headers"]
    patient_headers = setup_users["patient"]["headers"]

    # 1. Non-admin cannot create content
    unauth_resp = client.post(
        "/api/admin/content",
        headers=patient_headers,
        json={
            "title": "Unauthorized Article",
            "summary": "This should be blocked by role authorization.",
            "body": "Detailed content that should fail to create.",
            "category": "Exercise",
        },
    )
    assert unauth_resp.status_code == 403

    # 2. Anonymous cannot create content
    anon_resp = client.post(
        "/api/admin/content",
        json={
            "title": "Anonymous Article",
            "summary": "This should be blocked without auth.",
            "body": "Detailed content that should fail to create.",
            "category": "Exercise",
        },
    )
    assert anon_resp.status_code == 401

    # 3. Admin creates draft article
    create_payload = {
        "title": "Hydration Habits for Better Focus",
        "summary": "A guide on maintaining optimal fluid balance throughout busy work days.",
        "body": "Drinking sufficient water supports cognitive focus, kidney filtering, and metabolic balance. Carry a water bottle and take periodic sips.",
        "category": "Nutrition",
        "tags": ["water", "energy", "focus"],
        "status": "DRAFT",
    }
    create_resp = client.post("/api/admin/content", headers=admin_headers, json=create_payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["title"] == create_payload["title"]
    assert created_data["status"] == "DRAFT"
    assert created_data["contentId"].startswith("CNT-")
    content_id = created_data["contentId"]

    # 4. Draft is NOT visible in public patient feed
    feed_resp = client.get("/api/content?category=Nutrition")
    assert feed_resp.status_code == 200
    feed_items = feed_resp.json()["items"]
    assert not any(it["contentId"] == content_id for it in feed_items)

    # 5. Admin updates article
    update_payload = {
        "title": "Hydration Habits for Peak Mental Focus",
        "summary": "Updated summary about hydration, cognitive focus, and electrolyte balance.",
    }
    update_resp = client.patch(f"/api/admin/content/{content_id}", headers=admin_headers, json=update_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == update_payload["title"]

    # 6. Admin publishes article
    pub_resp = client.post(f"/api/admin/content/{content_id}/publish", headers=admin_headers)
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "PUBLISHED"
    assert pub_resp.json()["publishedAt"] is not None

    # 7. Now article IS visible in patient feed
    feed_resp2 = client.get(f"/api/content?category=Nutrition&search={content_id}")
    assert feed_resp2.status_code == 200
    assert any(it["contentId"] == content_id for it in feed_resp2.json()["items"])

    # 8. Detail retrieval
    detail_resp = client.get(f"/api/content/{content_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["contentId"] == content_id
    assert detail_resp.json()["readingTimeMinutes"] >= 1

    # 9. Admin archives article
    arch_resp = client.post(f"/api/admin/content/{content_id}/archive", headers=admin_headers)
    assert arch_resp.status_code == 200
    assert arch_resp.json()["status"] == "ARCHIVED"

    # 10. Archived article is removed from patient feed
    detail_arch_resp = client.get(f"/api/content/{content_id}")
    assert detail_arch_resp.status_code == 404


def test_category_validation_and_listing(setup_users):
    """Test category enumeration and invalid category validation."""
    admin_headers = setup_users["admin"]["headers"]

    # Invalid category rejected with 422
    bad_cat_resp = client.post(
        "/api/admin/content",
        headers=admin_headers,
        json={
            "title": "Bad Category Test Article",
            "summary": "Testing invalid health category rejection.",
            "body": "Valid body text that exceeds twenty characters minimum.",
            "category": "InvalidNonExistentCategory",
        },
    )
    assert bad_cat_resp.status_code == 422

    # Category list endpoint
    cats_resp = client.get("/api/content/categories")
    assert cats_resp.status_code == 200
    cats = cats_resp.json()
    assert isinstance(cats, list)
    cat_names = [c["category"] for c in cats]
    assert "Healthy Food" in cat_names
    assert "Exercise" in cat_names
    assert "Mental Wellness" in cat_names


def test_bookmark_actions_and_isolation(setup_users):
    """Test bookmarking, unbookmarking, list bookmarks, and user isolation."""
    admin_headers = setup_users["admin"]["headers"]
    patient1_headers = setup_users["patient"]["headers"]
    patient2_headers = setup_users["patient2"]["headers"]

    # 1. Admin creates and publishes an article
    create_resp = client.post(
        "/api/admin/content",
        headers=admin_headers,
        json={
            "title": "Everyday Heart Health Tips",
            "summary": "Simple actionable habits that protect cardiovascular health every day.",
            "body": "Incorporate 30 minutes of walking, replace saturated fats with olive oil, and monitor your blood pressure.",
            "category": "Preventive Healthcare",
            "status": "PUBLISHED",
        },
    )
    assert create_resp.status_code == 201
    content_id = create_resp.json()["contentId"]

    # 2. Patient 1 bookmarks the article
    bm_resp1 = client.post(f"/api/content/bookmarks/{content_id}", headers=patient1_headers)
    assert bm_resp1.status_code == 200
    assert bm_resp1.json()["isBookmarked"] is True

    # 3. Patient 1 verifies bookmark in feed and detail
    bms_list1 = client.get("/api/content/bookmarks", headers=patient1_headers)
    assert bms_list1.status_code == 200
    assert any(it["contentId"] == content_id for it in bms_list1.json()["items"])

    detail1 = client.get(f"/api/content/{content_id}", headers=patient1_headers)
    assert detail1.status_code == 200
    assert detail1.json()["isBookmarked"] is True

    # 4. Patient 2 does NOT have this bookmarked (isolation)
    bms_list2 = client.get("/api/content/bookmarks", headers=patient2_headers)
    assert bms_list2.status_code == 200
    assert not any(it["contentId"] == content_id for it in bms_list2.json()["items"])

    detail2 = client.get(f"/api/content/{content_id}", headers=patient2_headers)
    assert detail2.status_code == 200
    assert detail2.json()["isBookmarked"] is False

    # 5. Patient 1 toggles bookmark off
    toggle_off = client.post(f"/api/content/bookmarks/{content_id}", headers=patient1_headers)
    assert toggle_off.status_code == 200
    assert toggle_off.json()["isBookmarked"] is False

    # 6. Patient 1 bookmark list is now empty of this article
    bms_list1_after = client.get("/api/content/bookmarks", headers=patient1_headers)
    assert bms_list1_after.status_code == 200
    assert not any(it["contentId"] == content_id for it in bms_list1_after.json()["items"])


def test_admin_analytics_authorization(setup_users):
    """Ensure non-admins and anonymous users cannot view analytics."""
    patient_headers = setup_users["patient"]["headers"]

    endpoints = [
        "/api/admin/analytics/overview",
        "/api/admin/analytics/appointments",
        "/api/admin/analytics/payments",
        "/api/admin/analytics/doctors",
        "/api/admin/analytics/content",
    ]

    for ep in endpoints:
        # Patient forbidden
        resp_patient = client.get(ep, headers=patient_headers)
        assert resp_patient.status_code == 403, f"Endpoint {ep} should be 403 for patient"

        # Anonymous unauthorized
        resp_anon = client.get(ep)
        assert resp_anon.status_code == 401, f"Endpoint {ep} should be 401 for anonymous"


def test_admin_analytics_metrics_and_revenue_accounting(setup_users):
    """Verify overview, appointment stats, doctor specialties, and earned revenue calculation."""
    db = get_database()
    admin_headers = setup_users["admin"]["headers"]
    ts = int(time.time() * 1000)

    # Insert synthetic doctor profile
    doc_id = str(ObjectId())
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc_id),
        "userId": str(ObjectId()),
        "doctorId": f"DOC-{ts}",
        "specialty": "Cardiology",
        "medicalRegistrationNumber": f"SLMC-{ts}",
        "qualifications": "MBBS, MD",
        "hospitalOrClinic": "National Hospital",
        "experienceYears": 12,
        "consultationFee": 3500.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Insert synthetic appointments
    appt1_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt1_id),
        "patientUserId": setup_users["patient"]["id"],
        "doctorUserId": str(ObjectId()),
        "doctorProfileId": doc_id,
        "availabilityId": str(ObjectId()),
        "appointmentDate": "2026-10-18",
        "startTime": "10:00",
        "endTime": "10:30",
        "status": AppointmentStatus.COMPLETED.value,
        "paymentStatus": ApptPaymentStatus.PAID.value,
        "consultationFee": 3500.0,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    appt2_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt2_id),
        "patientUserId": setup_users["patient"]["id"],
        "doctorUserId": str(ObjectId()),
        "doctorProfileId": doc_id,
        "availabilityId": str(ObjectId()),
        "appointmentDate": "2026-10-18",
        "startTime": "11:00",
        "endTime": "11:30",
        "status": AppointmentStatus.CANCELLED.value,
        "paymentStatus": ApptPaymentStatus.REFUNDED.value,
        "consultationFee": 3500.0,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Insert synthetic payments:
    # 1 succeeded live/test payment of 3500 LKR
    # 1 refunded payment of 1000 LKR
    # 1 failed payment of 2000 LKR (must NOT be counted in revenue)
    db["payments"].insert_one({
        "_id": ObjectId(),
        "appointmentId": appt1_id,
        "patientUserId": setup_users["patient"]["id"],
        "doctorUserId": str(ObjectId()),
        "stripePaymentIntentId": f"pi_test_{ts}_1",
        "amount": 3500.0,
        "currency": "lkr",
        "status": PaymentStatus.SUCCEEDED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
        "paidAt": utc_now(),
    })

    db["payments"].insert_one({
        "_id": ObjectId(),
        "appointmentId": appt2_id,
        "patientUserId": setup_users["patient"]["id"],
        "doctorUserId": str(ObjectId()),
        "stripePaymentIntentId": f"pi_test_{ts}_2",
        "amount": 1000.0,
        "currency": "lkr",
        "status": PaymentStatus.REFUNDED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    db["payments"].insert_one({
        "_id": ObjectId(),
        "appointmentId": str(ObjectId()),
        "patientUserId": setup_users["patient"]["id"],
        "doctorUserId": str(ObjectId()),
        "stripePaymentIntentId": f"pi_test_{ts}_3",
        "amount": 2000.0,
        "currency": "lkr",
        "status": PaymentStatus.FAILED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 1. Test Overview endpoint
    overview_resp = client.get("/api/admin/analytics/overview", headers=admin_headers)
    assert overview_resp.status_code == 200
    ov = overview_resp.json()
    assert ov["totalPatients"] >= 1
    assert ov["totalVerifiedDoctors"] >= 1
    assert ov["completedAppointments"] >= 1
    assert ov["cancelledAppointments"] >= 1
    assert ov["successfulPaymentsCount"] >= 1

    # Check revenue totals by currency
    lkr_rev = next((r for r in ov["totalRevenueByCurrency"] if r["currency"] == "lkr"), None)
    assert lkr_rev is not None
    assert lkr_rev["grossAmount"] >= 3500.0
    assert lkr_rev["refundedAmount"] >= 1000.0
    assert lkr_rev["netAmount"] >= 2500.0

    # 2. Test Appointments analytics endpoint
    appts_resp = client.get("/api/admin/analytics/appointments", headers=admin_headers)
    assert appts_resp.status_code == 200
    appts_data = appts_resp.json()
    assert appts_data["totalAppointments"] >= 2
    assert "COMPLETED" in appts_data["statusBreakdown"]
    assert "CANCELLED" in appts_data["statusBreakdown"]
    assert appts_data["completionRate"] >= 0.0

    # 3. Test Payments analytics endpoint
    pay_resp = client.get("/api/admin/analytics/payments", headers=admin_headers)
    assert pay_resp.status_code == 200
    pay_data = pay_resp.json()
    assert pay_data["successfulPaymentsCount"] >= 1
    assert pay_data["failedPaymentsCount"] >= 1
    assert pay_data["refundedPaymentsCount"] >= 1
    assert pay_data["testPaymentsCount"] >= 1
    assert len(pay_data["recentTransactions"]) >= 1

    # 4. Test Doctors analytics endpoint
    docs_resp = client.get("/api/admin/analytics/doctors", headers=admin_headers)
    assert docs_resp.status_code == 200
    docs_data = docs_resp.json()
    assert docs_data["approvedDoctors"] >= 1
    assert any(s["specialty"] == "Cardiology" for s in docs_data["specialtyDistribution"])

    # 5. Test Content analytics endpoint
    content_resp = client.get("/api/admin/analytics/content", headers=admin_headers)
    assert content_resp.status_code == 200
    content_data = content_resp.json()
    assert content_data["totalArticles"] >= 1
    assert len(content_data["categoryDistribution"]) == 7


def test_analytics_date_filtering_validation(setup_users):
    """Test date filter validation and range checking."""
    admin_headers = setup_users["admin"]["headers"]

    # Invalid date format
    bad_format = client.get("/api/admin/analytics/overview?startDate=2026/10/18", headers=admin_headers)
    assert bad_format.status_code == 400
    assert "Invalid startDate format" in bad_format.json()["detail"]

    # End date before start date
    inverted_range = client.get(
        "/api/admin/analytics/overview?startDate=2026-12-31&endDate=2026-01-01",
        headers=admin_headers,
    )
    assert inverted_range.status_code == 400
    assert "startDate cannot be after endDate" in inverted_range.json()["detail"]

    # Valid date range
    valid_range = client.get(
        "/api/admin/analytics/overview?startDate=2026-01-01&endDate=2026-12-31",
        headers=admin_headers,
    )
    assert valid_range.status_code == 200
    assert valid_range.json()["startDate"] == "2026-01-01"
    assert valid_range.json()["endDate"] == "2026-12-31"
