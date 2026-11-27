"""Comprehensive automated tests for Phase 5: Admin AI Automation, Verification, Analytics & Payment Operations."""

from datetime import datetime, timedelta, timezone
import time
from unittest.mock import MagicMock, patch
from uuid import uuid4
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import DatabaseManager, ensure_indexes, get_database
from tests.mock_db import MockDatabase
from app.main import app
from app.models.appointment import AppointmentStatus, PaymentStatus as ApptPaymentStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.payment import PaymentStatus
from app.models.refund_request import RefundStatus
from app.models.support_ticket import TicketCategory, TicketPriority, TicketStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.services.doctor_verification_assistant import DoctorVerificationAssistant
from app.services.payment_monitoring_service import PaymentMonitoringService
from app.services.refund_service import RefundService
from app.services.support_ticket_service import SupportTicketService
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def isolated_db():
    """Ensure tests run against a dedicated phase 5 test database."""
    mock_db = MockDatabase("mediconnect_phase5_test")
    DatabaseManager._db = mock_db
    try:
        yield mock_db
    finally:
        DatabaseManager._db = None


@pytest.fixture
def test_env():
    """Seed authenticated admin, patient, and doctor users with test tokens."""
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Admin
    admin_id = str(ObjectId())
    admin_email = f"admin_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "fullName": "System Admin",
        "email": admin_email,
        "role": UserRole.ADMIN.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    admin_token = create_access_token(admin_id, role=UserRole.ADMIN.value)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Patient
    patient_id = str(ObjectId())
    patient_email = f"patient_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(patient_id),
        "fullName": "Kasun Perera",
        "email": patient_email,
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    patient_token = create_access_token(patient_id, role=UserRole.PATIENT.value)
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    # 3. Doctor
    doc_user_id = str(ObjectId())
    doc_email = f"doctor_{ts}@mediconnect.lk"
    db["users"].insert_one({
        "_id": ObjectId(doc_user_id),
        "fullName": "Dr. Nimal Silva",
        "email": doc_email,
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc_token = create_access_token(doc_user_id, role=UserRole.DOCTOR.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Doctor Profile (Pending)
    prof_id = str(ObjectId())
    random_code = uuid4().hex[:6].upper()
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(prof_id),
        "userId": doc_user_id,
        "doctorId": f"DOC-{random_code}",
        "fullName": "Dr. Nimal Silva",
        "specialty": "Cardiology",
        "medicalRegistrationNumber": f"SLMC-{random_code}",
        "qualifications": "MBBS, MD Cardiology",
        "hospitalOrClinic": "National Hospital Colombo",
        "experienceYears": 12,
        "consultationFee": 3500.0,
        "verificationStatus": DoctorVerificationStatus.PENDING.value,
        "verificationDocuments": {
            "identityDocument": {"filename": "nic.pdf", "fileSize": 1024, "contentType": "application/pdf"},
            "medicalRegistrationDocument": {"filename": "slmc.pdf", "fileSize": 2048, "contentType": "application/pdf"},
            "qualificationDocument": {"filename": "mbbs.pdf", "fileSize": 4096, "contentType": "application/pdf"},
        },
        "submittedAt": utc_now(),
    })

    return {
        "db": db,
        "admin_id": admin_id,
        "admin_headers": admin_headers,
        "patient_id": patient_id,
        "patient_headers": patient_headers,
        "doc_user_id": doc_user_id,
        "doc_profile_id": prof_id,
        "doc_headers": doc_headers,
        "ts": ts,
    }


# =============================================================================
# 1. Doctor Verification Assistant & Safeguards Tests
# =============================================================================

def test_doctor_verification_assistant_completeness_and_checks(test_env):
    """Verify completeness calculation, missing doc detection, and manual verification rule."""
    db = test_env["db"]
    prof_id = test_env["doc_profile_id"]

    review = DoctorVerificationAssistant.analyze_application(db, prof_id)
    assert review["completenessScore"] == 100
    assert review["needsManualExternalCheck"] is True
    assert review["recommendedAction"] == "APPROVE"
    assert len(review["missingDocuments"]) == 0

    # Test with incomplete doctor application
    bad_prof_id = str(ObjectId())
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(bad_prof_id),
        "userId": str(ObjectId()),
        "doctorId": f"DOC-BAD-{uuid4().hex[:6]}",
        "fullName": "",
        "medicalRegistrationNumber": f"BAD-{uuid4().hex[:6]}",
        "specialty": "",
        "verificationStatus": DoctorVerificationStatus.PENDING.value,
        "verificationDocuments": {},
    })

    bad_review = DoctorVerificationAssistant.analyze_application(db, bad_prof_id)
    assert bad_review["completenessScore"] < 50
    assert len(bad_review["missingDocuments"]) == 3
    assert bad_review["recommendedAction"] == "REQUEST_INFO"


def test_doctor_verification_api_and_audit(test_env):
    """Test AI review endpoint and verify non-admin access is rejected."""
    prof_id = test_env["doc_profile_id"]

    # Admin access succeeds
    resp = client.get(f"/api/admin/workflow/doctor-verification/{prof_id}/ai-review", headers=test_env["admin_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["doctorProfileId"] == prof_id
    assert data["needsManualExternalCheck"] is True

    # Patient access is forbidden (403)
    resp_forbidden = client.get(f"/api/admin/workflow/doctor-verification/{prof_id}/ai-review", headers=test_env["patient_headers"])
    assert resp_forbidden.status_code == 403


# =============================================================================
# 2. Payment Monitoring & Reconciliation Tests
# =============================================================================

def test_payment_reconciliation_detects_unconfirmed_appointment(test_env):
    """Reconciliation must detect succeeded payment where appointment is stuck in HOLD/PENDING."""
    db = test_env["db"]
    appt_id = str(ObjectId())
    pay_id = str(ObjectId())

    # Create unconfirmed appointment
    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "patientUserId": test_env["patient_id"],
        "doctorUserId": test_env["doc_user_id"],
        "appointmentDate": "2026-12-01",
        "startTime": "10:00",
        "status": AppointmentStatus.HOLD.value,
        "paymentStatus": ApptPaymentStatus.PENDING.value,
        "createdAt": utc_now(),
    })

    # Create succeeded payment referencing this unconfirmed appointment
    pi_id = f"pi_test_reconcile_{uuid4().hex[:8]}"
    db["payments"].insert_one({
        "_id": ObjectId(pay_id),
        "appointmentId": appt_id,
        "patientUserId": test_env["patient_id"],
        "paymentIntentId": pi_id,
        "stripePaymentIntentId": pi_id,
        "amount": 3500.0,
        "currency": "LKR",
        "status": PaymentStatus.SUCCEEDED.value,
        "createdAt": utc_now(),
    })

    report = PaymentMonitoringService.run_reconciliation_checks(db)
    assert report["discrepanciesCount"] >= 1
    unconf = [d for d in report["discrepancies"] if d["type"] == "UNCONFIRMED_PAID_APPOINTMENT"]
    assert len(unconf) >= 1
    assert unconf[0]["appointmentId"] == appt_id


def test_payment_reconciliation_endpoint(test_env):
    """Test API endpoint for reconciliation check."""
    resp = client.post("/api/admin/workflow/reconciliation/run", headers=test_env["admin_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "discrepancies" in data
    assert "totalChecked" in data


# =============================================================================
# 3. Customer Support Ticketing & AI Drafting Tests
# =============================================================================

def test_customer_support_ticket_workflow_and_ai_draft(test_env):
    """Test ticket creation, AI classification & drafting, emergency escalation, and admin reply."""
    # 1. Patient creates support ticket
    req_body = {
        "subject": "Booking issue on appointment slot",
        "description": "I had a deduction on my card but the booking shows pending.",
        "category": "payment_issue",
        "priority": "high",
    }
    create_resp = client.post("/api/admin/workflow/tickets", json=req_body, headers=test_env["patient_headers"])
    assert create_resp.status_code == 201
    ticket = create_resp.json()
    t_id = ticket["ticketId"]
    assert ticket["status"] == "open"
    # A05 changed expectation (A05-BUG-005): the internal draft is for administrators only, never the requester.
    assert ticket["aiDraft"] is None
    admin_view = client.get(f"/api/admin/workflow/tickets/{t_id}", headers=test_env["admin_headers"]).json()
    assert admin_view["aiDraft"] is not None
    assert "draftResponse" in admin_view["aiDraft"]

    # 2. Patient can view own ticket, but another patient cannot
    get_resp = client.get(f"/api/admin/workflow/tickets/{t_id}", headers=test_env["patient_headers"])
    assert get_resp.status_code == 200

    # 3. Admin generates/refreshes AI draft
    draft_resp = client.post(f"/api/admin/workflow/tickets/{t_id}/ai-draft", headers=test_env["admin_headers"])
    assert draft_resp.status_code == 200
    assert "draftResponse" in draft_resp.json()

    # 4. Admin sends authorized reply and resolves ticket
    reply_resp = client.post(
        f"/api/admin/workflow/tickets/{t_id}/reply",
        json={"message": "We have reviewed your transaction and confirmed the booking.", "resolve": True},
        headers=test_env["admin_headers"],
    )
    assert reply_resp.status_code == 200
    assert reply_resp.json()["status"] == "resolved"


def test_emergency_ticket_ai_draft_escalation(test_env):
    """Emergency keywords in tickets must trigger 1990 ambulance escalation in AI draft."""
    req_body = {
        "subject": "Severe health issue",
        "description": "Patient is having severe chest pain and shortness of breath.",
    }
    create_resp = client.post("/api/admin/workflow/tickets", json=req_body, headers=test_env["patient_headers"])
    assert create_resp.status_code == 201
    ticket = create_resp.json()
    # A05 changed expectation (A05-BUG-005): the requester gets the emergency notice; the draft is admin-only.
    assert ticket["aiDraft"] is None and "1990" in ticket["safetyNotice"]
    draft = client.get(f"/api/admin/workflow/tickets/{ticket['ticketId']}",
                       headers=test_env["admin_headers"]).json()["aiDraft"]
    assert draft["suggestedPriority"] == TicketPriority.URGENT.value
    assert any("POTENTIAL_MEDICAL_EMERGENCY" in f for f in draft.get("flags", []))
    assert "1990" in draft["draftResponse"]


# =============================================================================
# 4. Refund Review & Policy Eligibility Tests
# =============================================================================

def test_refund_policy_rules_and_admin_approval(test_env):
    """Test deterministic refund rules (24h full refund vs completed dispute) and admin approval."""
    db = test_env["db"]

    # 1. Appointment > 24 hours in the future
    future_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    appt_id = str(ObjectId())
    pay_id = str(ObjectId())

    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "patientUserId": test_env["patient_id"],
        "doctorUserId": test_env["doc_user_id"],
        "appointmentDate": future_date,
        "startTime": "14:00",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": ApptPaymentStatus.PAID.value,
        "createdAt": utc_now(),
    })
    ref_pi_id = f"pi_test_refund_{uuid4().hex[:8]}"
    db["payments"].insert_one({
        "_id": ObjectId(pay_id),
        "appointmentId": appt_id,
        "patientUserId": test_env["patient_id"],
        "paymentIntentId": ref_pi_id,
        "stripePaymentIntentId": ref_pi_id,
        "amount": 4000.0,
        "currency": "LKR",
        "status": PaymentStatus.SUCCEEDED.value,
        "createdAt": utc_now(),
    })

    # Policy evaluation should guarantee 100% refund
    policy = RefundService.calculate_refund_eligibility(db, appt_id, pay_id)
    assert policy.eligible is True
    assert policy.eligibleAmount == 4000.0
    assert policy.penaltyAmount == 0.0

    # Phase 02: a refund belongs to a cancelled booking; the patient cancels first.
    db["appointments"].update_one({"_id": ObjectId(appt_id)}, {"$set": {"status": AppointmentStatus.CANCELLED.value,
                                                                       "cancelledBy": "PATIENT"}})

    # Patient creates refund request
    ref_req = client.post(
        "/api/admin/workflow/refunds",
        json={"appointmentId": appt_id, "reason": "Travel plans changed"},
        headers=test_env["patient_headers"],
    )
    assert ref_req.status_code == 201
    refund_data = ref_req.json()
    r_id = refund_data["refundId"]
    assert refund_data["status"] == "requested"

    # Admin approves refund
    with patch("stripe.Refund.create") as mock_stripe:
        mock_stripe.return_value = MagicMock(id=f"re_test_{test_env['ts']}", status="succeeded")
        appr_resp = client.post(
            f"/api/admin/workflow/refunds/{r_id}/approve",
            json={"notes": "Approved based on >24h notice policy"},
            headers=test_env["admin_headers"],
        )
        assert appr_resp.status_code == 200
        assert appr_resp.json()["status"] == "succeeded"

    # Duplicate refund attempt must be rejected
    dup_resp = client.post(
        "/api/admin/workflow/refunds",
        json={"appointmentId": appt_id, "reason": "Another request"},
        headers=test_env["patient_headers"],
    )
    assert dup_resp.status_code == 400


# =============================================================================
# 5. Operational Reports & CSV Export Tests
# =============================================================================

def test_admin_reports_generation_and_csv_export(test_env):
    """Test generating operational reports and safe CSV export."""
    # Generate daily appointment report
    rep_resp = client.post(
        "/api/admin/workflow/reports/generate",
        json={"reportType": "daily_appointment"},
        headers=test_env["admin_headers"],
    )
    assert rep_resp.status_code == 200
    report = rep_resp.json()
    assert report["reportType"] == "daily_appointment"
    assert "metrics" in report
    assert "aiSummary" in report

    # Export report as CSV
    csv_resp = client.post(
        "/api/admin/workflow/reports/export-csv",
        json={"reportType": "monthly_payment"},
        headers=test_env["admin_headers"],
    )
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    csv_text = csv_resp.text
    assert "MediConnect Operational Report" in csv_text
    assert "Metric,Value" in csv_text


# =============================================================================
# 6. Admin AI Assistant Natural Language Queries Tests
# =============================================================================

def test_admin_ai_assistant_queries(test_env):
    """Test English and Romanized Sinhala queries routed to bounded tools."""
    # 1. Doctor verification backlog in Romanized Sinhala
    resp1 = client.post(
        "/api/admin/workflow/assistant",
        json={"message": "pending doctors keeyak innawada?"},
        headers=test_env["admin_headers"],
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["toolCalled"] == "get_pending_doctor_verifications"
    assert "doctor verification application(s) pending" in data1["reply"]

    # 2. Bookings count in Romanized Sinhala
    resp2 = client.post(
        "/api/admin/workflow/assistant",
        json={"message": "me month eke bookings keeyak thiyenawada?"},
        headers=test_env["admin_headers"],
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["toolCalled"] == "get_admin_dashboard_metrics"
    assert "appointment booking(s)" in data2["reply"]

    # 3. Reconciliation check
    resp3 = client.post(
        "/api/admin/workflow/assistant",
        json={"message": "failed payments tika check karanna"},
        headers=test_env["admin_headers"],
    )
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["toolCalled"] == "get_payment_reconciliation_issues"

    # 4. Refund requests
    resp4 = client.post(
        "/api/admin/workflow/assistant",
        json={"message": "refund requests monawada?"},
        headers=test_env["admin_headers"],
    )
    assert resp4.status_code == 200
    data4 = resp4.json()
    assert data4["toolCalled"] == "get_admin_report_data"


# =============================================================================
# 7. Administrative Audit Log Querying Tests
# =============================================================================

def test_admin_audit_logs_endpoint(test_env):
    """Test retrieving immutable audit logs with admin authorization."""
    resp = client.get("/api/admin/workflow/audit-logs", headers=test_env["admin_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1  # Prior test actions (refund approval, ticket resolution) logged
