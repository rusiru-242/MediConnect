"""Automated test suite for Phase 23: Doctor Reviews & Ratings System.

Covers:
1. Valid review submission by authenticated patient for completed appointment.
2. Invalid rating rejection (< 1 or > 5 -> 422).
3. Appointment ownership enforcement (Patient B cannot review Patient A's appointment -> 403).
4. Appointment status check (Only COMPLETED appointments can be reviewed -> 400).
5. Duplicate review prevention (Same appointment cannot be reviewed twice -> 409).
6. Unique appointment database constraint verification.
7. Public doctor reviews list with privacy-preserving display name (e.g. "Alice P.").
8. Doctor rating summary aggregation (average rating, star breakdown, 0 reviews handled cleanly).
9. Patient "My Reviews" list.
10. Edit own review (rating and text update -> 200).
11. Cross-patient edit rejection (Patient B cannot edit Patient A's review -> 403).
12. Delete own review (Patient deletes review -> 200).
13. Report review for moderation (marks status as REPORTED).
14. Admin list reported reviews.
15. Admin moderation: hide and restore actions (hiding excludes from public summary).
16. Unauthorized access rejection (401 for unauthenticated, 403 for non-patient write).
"""

from datetime import datetime, timezone
import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest
from pymongo.errors import DuplicateKeyError

from app.config.database import ensure_indexes, get_database
from app.main import app
from app.models.appointment import AppointmentStatus, PaymentStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.review import ReviewStatus, create_review_indexes, get_review_collection
from app.models.user import AccountStatus, UserRole, utc_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def seeded_review_env():
    """Seed test database with:
    - Patient A, Patient B
    - Doctor A, Doctor B (with profiles)
    - Admin
    - Completed Appointment A (Doctor A + Patient A)
    - Incomplete Appointment A (Doctor A + Patient A, status PENDING)
    - Completed Appointment B (Doctor A + Patient B)
    - Completed Appointment C (Doctor B + Patient A)
    """
    db = get_database()
    ensure_indexes(db)
    create_review_indexes(db)
    ts = int(time.time() * 1000)

    # 1. Patient A
    pat_a_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_a_id),
        "email": f"patient.a.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Alice Perera",
        "role": UserRole.PATIENT.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_pat_a = create_access_token(user_id=pat_a_id, role=UserRole.PATIENT.value)

    # 2. Patient B
    pat_b_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_b_id),
        "email": f"patient.b.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Bob Silva",
        "role": UserRole.PATIENT.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_pat_b = create_access_token(user_id=pat_b_id, role=UserRole.PATIENT.value)

    # 3. Doctor A (Approved)
    doc_a_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(doc_a_id),
        "email": f"dr.sarath.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Dr. Sarath Gunawardena",
        "role": UserRole.DOCTOR.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc_a_prof_id = str(ObjectId())
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc_a_prof_id),
        "userId": doc_a_id,
        "doctorId": f"DOC-REV-A-{ts}",
        "medicalRegistrationNumber": f"SLMC-11111-{ts}",
        "specialty": "Cardiologist",
        "qualifications": "MBBS, MD (Cardiology)",
        "experienceYears": 14,
        "consultationFee": 3500.0,
        "hospitalOrClinic": "National Hospital Colombo",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_doc_a = create_access_token(user_id=doc_a_id, role=UserRole.DOCTOR.value)

    # 4. Doctor B (Approved - no initial reviews)
    doc_b_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(doc_b_id),
        "email": f"dr.b.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Dr. Nimal Fernando",
        "role": UserRole.DOCTOR.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc_b_prof_id = str(ObjectId())
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc_b_prof_id),
        "userId": doc_b_id,
        "doctorId": f"DOC-REV-B-{ts}",
        "medicalRegistrationNumber": f"SLMC-22222-{ts}",
        "specialty": "General Physician",
        "qualifications": "MBBS",
        "experienceYears": 5,
        "consultationFee": 2000.0,
        "hospitalOrClinic": "Lanka Hospital",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_doc_b = create_access_token(user_id=doc_b_id, role=UserRole.DOCTOR.value)

    # 5. Admin
    admin_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "email": f"admin.rev.{ts}@example.com",
        "passwordHash": hash_password("ValidPassword123!"),
        "fullName": "Admin User",
        "role": UserRole.ADMIN.value,
        "accountStatus": AccountStatus.ACTIVE.value,
        "emailVerified": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_admin = create_access_token(user_id=admin_id, role=UserRole.ADMIN.value)

    # 6. Appointments
    # Appt 1: Completed, Pat A + Doc A
    appt_completed_a_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_completed_a_id),
        "patientUserId": pat_a_id,
        "doctorUserId": doc_a_id,
        "doctorProfileId": doc_a_prof_id,
        "availabilityId": str(ObjectId()),
        "appointmentDate": "2026-10-15",
        "startTime": "09:00",
        "endTime": "09:30",
        "status": AppointmentStatus.COMPLETED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "consultationFee": 3500.0,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Appt 2: Incomplete (PENDING), Pat A + Doc A
    appt_pending_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_pending_id),
        "patientUserId": pat_a_id,
        "doctorUserId": doc_a_id,
        "doctorProfileId": doc_a_prof_id,
        "availabilityId": str(ObjectId()),
        "appointmentDate": "2026-10-25",
        "startTime": "10:00",
        "endTime": "10:30",
        "status": AppointmentStatus.PENDING.value,
        "paymentStatus": PaymentStatus.UNPAID.value,
        "consultationFee": 3500.0,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # Appt 3: Completed, Pat B + Doc A
    appt_completed_b_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_completed_b_id),
        "patientUserId": pat_b_id,
        "doctorUserId": doc_a_id,
        "doctorProfileId": doc_a_prof_id,
        "availabilityId": str(ObjectId()),
        "appointmentDate": "2026-10-16",
        "startTime": "11:00",
        "endTime": "11:30",
        "status": AppointmentStatus.COMPLETED.value,
        "paymentStatus": PaymentStatus.PAID.value,
        "consultationFee": 3500.0,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    return {
        "db": db,
        "pat_a_id": pat_a_id,
        "token_pat_a": token_pat_a,
        "pat_b_id": pat_b_id,
        "token_pat_b": token_pat_b,
        "doc_a_id": doc_a_id,
        "doc_a_prof_id": doc_a_prof_id,
        "token_doc_a": token_doc_a,
        "doc_b_id": doc_b_id,
        "doc_b_prof_id": doc_b_prof_id,
        "token_doc_b": token_doc_b,
        "admin_id": admin_id,
        "token_admin": token_admin,
        "appt_completed_a_id": appt_completed_a_id,
        "appt_pending_id": appt_pending_id,
        "appt_completed_b_id": appt_completed_b_id,
    }


def test_01_submit_valid_review(seeded_review_env):
    """Authenticated patient can submit a verified review for a completed appointment."""
    env = seeded_review_env
    res = client.post(
        "/api/reviews",
        json={
            "appointmentId": env["appt_completed_a_id"],
            "rating": 5,
            "reviewText": "Dr. Sarath was very thorough and attentive. Highly recommend!",
        },
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["rating"] == 5
    assert data["reviewText"] == "Dr. Sarath was very thorough and attentive. Highly recommend!"
    assert data["doctorUserId"] == env["doc_a_id"]
    assert data["patientDisplayName"] == "Alice P."
    assert data["verifiedAppointment"] is True
    assert data["status"] == "PUBLISHED"
    env["created_review_id"] = data["reviewId"]


def test_02_invalid_rating_rejection(seeded_review_env):
    """Rating must be between 1 and 5; values outside are rejected with 422."""
    env = seeded_review_env
    # Rating 0
    res = client.post(
        "/api/reviews",
        json={"appointmentId": env["appt_completed_b_id"], "rating": 0},
        headers={"Authorization": f"Bearer {env['token_pat_b']}"},
    )
    assert res.status_code == 422

    # Rating 6
    res = client.post(
        "/api/reviews",
        json={"appointmentId": env["appt_completed_b_id"], "rating": 6},
        headers={"Authorization": f"Bearer {env['token_pat_b']}"},
    )
    assert res.status_code == 422


def test_03_appointment_ownership_enforcement(seeded_review_env):
    """Patient B cannot review Patient A's appointment -> 403 Forbidden."""
    env = seeded_review_env
    res = client.post(
        "/api/reviews",
        json={"appointmentId": env["appt_completed_a_id"], "rating": 4},
        headers={"Authorization": f"Bearer {env['token_pat_b']}"},
    )
    assert res.status_code == 403
    assert "own appointments" in res.json()["detail"].lower()


def test_04_incomplete_appointment_rejection(seeded_review_env):
    """Reviews can only be submitted for COMPLETED appointments -> 400 Bad Request."""
    env = seeded_review_env
    res = client.post(
        "/api/reviews",
        json={"appointmentId": env["appt_pending_id"], "rating": 4},
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res.status_code == 400
    assert "completed appointments" in res.json()["detail"].lower()


def test_05_duplicate_review_prevention(seeded_review_env):
    """Same appointment cannot be reviewed multiple times -> 409 Conflict."""
    env = seeded_review_env
    res = client.post(
        "/api/reviews",
        json={"appointmentId": env["appt_completed_a_id"], "rating": 5},
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res.status_code == 409
    assert "already been reviewed" in res.json()["detail"].lower()


def test_06_unique_database_constraint(seeded_review_env):
    """Database unique index on appointmentId strictly blocks duplicate insert."""
    env = seeded_review_env
    coll = get_review_collection(env["db"])
    with pytest.raises(DuplicateKeyError):
        coll.insert_one({
            "reviewId": "REV-TEST-DUP-UNIQUE",
            "appointmentId": env["appt_completed_a_id"],
            "doctorUserId": env["doc_a_id"],
            "doctorProfileId": env["doc_a_prof_id"],
            "patientUserId": env["pat_a_id"],
            "rating": 4,
            "status": "PUBLISHED",
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
        })


def test_07_second_patient_review(seeded_review_env):
    """Patient B submits a 4-star review for Appt B."""
    env = seeded_review_env
    res = client.post(
        "/api/reviews",
        json={
            "appointmentId": env["appt_completed_b_id"],
            "rating": 4,
            "reviewText": "Good consultation, clear explanations.",
        },
        headers={"Authorization": f"Bearer {env['token_pat_b']}"},
    )
    assert res.status_code == 201
    env["b_review_id"] = res.json()["reviewId"]


def test_08_doctor_rating_summary_aggregation(seeded_review_env):
    """Doctor A rating summary calculates exact verified average and star distribution."""
    env = seeded_review_env
    res = client.get(f"/api/doctors/{env['doc_a_id']}/rating-summary")
    assert res.status_code == 200
    data = res.json()
    assert data["totalReviews"] == 2
    # Average of 5 and 4 is 4.5
    assert data["averageRating"] == 4.5
    assert data["hasReviews"] is True
    assert data["ratingDistribution"]["5"] == 1
    assert data["ratingDistribution"]["4"] == 1
    assert data["ratingDistribution"]["1"] == 0


def test_09_doctor_zero_reviews_handled_cleanly(seeded_review_env):
    """Doctor with 0 reviews returns averageRating=None, totalReviews=0, hasReviews=False."""
    env = seeded_review_env
    res = client.get(f"/api/doctors/{env['doc_b_id']}/rating-summary")
    assert res.status_code == 200
    data = res.json()
    assert data["totalReviews"] == 0
    assert data["averageRating"] is None
    assert data["hasReviews"] is False
    assert data["ratingDistribution"] == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}


def test_10_public_doctor_reviews_privacy(seeded_review_env):
    """Public reviews show masked patient names and no private diagnostic data."""
    env = seeded_review_env
    res = client.get(f"/api/doctors/{env['doc_a_id']}/reviews")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    names = [item["patientDisplayName"] for item in data["items"]]
    assert "Alice P." in names
    assert "Bob S." in names
    # Verify no raw email or private identifiers in review items
    for item in data["items"]:
        assert "@" not in item["patientDisplayName"]
        assert "medicalRecord" not in item
        assert "symptoms" not in item


def test_11_patient_my_reviews_screen(seeded_review_env):
    """Patient can retrieve their own authored reviews."""
    env = seeded_review_env
    res = client.get(
        "/api/reviews/me",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["reviewId"] == env["created_review_id"]
    assert item["rating"] == 5
    assert "Sarath" in item["doctorName"]


def test_12_update_own_review(seeded_review_env):
    """Patient can update their own rating and review text."""
    env = seeded_review_env
    res = client.patch(
        f"/api/reviews/{env['created_review_id']}",
        json={
            "rating": 4,
            "reviewText": "Updated: Great consultation overall.",
        },
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["rating"] == 4
    assert data["reviewText"] == "Updated: Great consultation overall."


def test_13_cross_patient_edit_rejected(seeded_review_env):
    """Patient B cannot edit Patient A's review -> 403 Forbidden."""
    env = seeded_review_env
    res = client.patch(
        f"/api/reviews/{env['created_review_id']}",
        json={"rating": 1},
        headers={"Authorization": f"Bearer {env['token_pat_b']}"},
    )
    assert res.status_code == 403
    assert "cannot edit another patient's review" in res.json()["detail"].lower()


def test_14_report_review(seeded_review_env):
    """User can report an inappropriate review."""
    env = seeded_review_env
    res = client.post(
        f"/api/reviews/{env['b_review_id']}/report",
        json={"reason": "Contains false claims or inappropriate language."},
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_15_admin_list_reported_reviews(seeded_review_env):
    """Admin can list reported reviews awaiting moderation."""
    env = seeded_review_env
    res = client.get(
        "/api/admin/reviews/reported",
        headers={"Authorization": f"Bearer {env['token_admin']}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    reported_ids = [r["reviewId"] for r in data]
    assert env["b_review_id"] in reported_ids


def test_16_admin_hide_review_excludes_from_ratings(seeded_review_env):
    """Admin hides review -> It is removed from public summary and listing."""
    env = seeded_review_env
    res = client.patch(
        f"/api/reviews/{env['b_review_id']}/moderate",
        json={"action": "HIDE", "moderationNotes": "Violated review guidelines."},
        headers={"Authorization": f"Bearer {env['token_admin']}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "HIDDEN"

    # Verify public summary now only counts published reviews (1 review remains)
    summary_res = client.get(f"/api/doctors/{env['doc_a_id']}/rating-summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["totalReviews"] == 1
    # Only Patient A's updated review (rating 4)
    assert summary["averageRating"] == 4.0


def test_17_admin_restore_review(seeded_review_env):
    """Admin restores review -> Status returns to PUBLISHED and included in ratings."""
    env = seeded_review_env
    res = client.patch(
        f"/api/reviews/{env['b_review_id']}/moderate",
        json={"action": "RESTORE", "moderationNotes": "Verified legitimate feedback upon review."},
        headers={"Authorization": f"Bearer {env['token_admin']}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "PUBLISHED"

    summary_res = client.get(f"/api/doctors/{env['doc_a_id']}/rating-summary")
    assert summary_res.status_code == 200
    assert summary_res.json()["totalReviews"] == 2


def test_18_delete_review_by_author(seeded_review_env):
    """Patient author can delete their review."""
    env = seeded_review_env
    res = client.delete(
        f"/api/reviews/{env['created_review_id']}",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Check that deleted review no longer exists
    get_res = client.get(
        "/api/reviews/me",
        headers={"Authorization": f"Bearer {env['token_pat_a']}"},
    )
    assert env["created_review_id"] not in [r["reviewId"] for r in get_res.json()["items"]]


def test_19_unauthorized_access(seeded_review_env):
    """Unauthenticated requests return 401; doctors cannot submit patient reviews."""
    env = seeded_review_env
    # Unauthenticated
    res = client.post("/api/reviews", json={"appointmentId": "dummy", "rating": 5})
    assert res.status_code == 401

    # Doctor attempting to create patient review -> 403
    res_doc = client.post(
        "/api/reviews",
        json={"appointmentId": env["appt_completed_b_id"], "rating": 5},
        headers={"Authorization": f"Bearer {env['token_doc_a']}"},
    )
    assert res_doc.status_code == 403
