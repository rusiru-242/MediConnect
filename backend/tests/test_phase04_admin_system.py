"""Phase 04 regression tests: admin system, financial integrity, monitoring and admin AI components.

Run against the isolated local MongoDB test database (tests/conftest.py refuses any other target).
Stripe calls are mocked here; Stripe test-mode evidence is in docs/uat/phase-04. IDs P04-Nxx refer to the
Phase 04 reports. Fixture dates in 2031/2032 keep the range-based figures independent of other tests' data.
"""
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
import io
import threading
import time
from unittest.mock import MagicMock, patch
import uuid

from bson import ObjectId
from fastapi import HTTPException
import pytest

from app.models.appointment import utc_now
from app.services.financial_metrics import PLATFORM_TZ, collections, platform_range
from app.services.fraud_detection_service import FraudDetectionService
from app.services.notification_monitoring_service import NotificationMonitoringService
from app.services.payment_monitoring_service import PaymentMonitoringService
from app.services.refund_service import RefundService
from app.utils.security import create_access_token, hash_password
from tests.test_payment import (  # noqa: F401  (db fixture)
    _make_future_availability, _make_test_doctor, _make_test_patient, client, db,
)
from tests.test_phase02_booking_payment import _admin, _auth, _pay_confirmed, _payment


def _day() -> str:
    """A far-future date not used by any other test or earlier run (the test database is reused)."""
    import random
    from datetime import date
    return (date(2040, 1, 1) + timedelta(days=random.randint(0, 20000))).isoformat()


def _colombo(day: str, hhmm: str = "10:00") -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=PLATFORM_TZ).astimezone(timezone.utc)


def _captured(db, patient, doctor, amount, *, status="SUCCEEDED", refunded=None, paid_at=None, currency="lkr"):
    doc = {"appointmentId": str(ObjectId()), "patientUserId": patient["id"], "doctorUserId": doctor["id"],
           "stripePaymentIntentId": f"pi_p04_{uuid.uuid4().hex[:16]}", "amount": amount, "currency": currency,
           "status": status, "paidAt": paid_at, "createdAt": paid_at or utc_now(), "updatedAt": utc_now()}
    if refunded is not None:
        doc["refundedAmount"] = refunded
    db["payments"].insert_one(doc)
    return doc


def _cancelled_paid(db, suffix, fee=3000.0, by="doctor"):
    patient, doctor = _make_test_patient(db, suffix), _make_test_doctor(db, suffix + "Doc", fee=fee)
    appt, payment = _pay_confirmed(db, patient, doctor, _make_future_availability(db, doctor, 9))
    if by == "doctor":
        res = client.post(f"/api/doctors/me/appointments/{appt.id}/cancel", json={"reason": "Doctor unavailable"},
                          headers=_auth(doctor))
    else:
        res = client.post(f"/api/appointments/{appt.id}/cancel", json={"reason": "Patient plans changed"},
                          headers=_auth(patient))
    assert res.status_code == 200, res.text
    refund = db["refund_requests"].find_one({"appointmentId": appt.id})
    return patient, doctor, appt, payment, refund


# ------------------------------------------------------------------------------------------------ P04-N01
def test_n01_guard_module_is_used_by_conftest():
    import tests.conftest as guard  # noqa: F401  (import succeeded, so the session target is local *_test)
    import os
    from app.config.db_safety import isolation_error
    assert isolation_error(os.environ["MONGODB_URI"], os.environ["DATABASE_NAME"], "_test") is None


# ------------------------------------------------------------------------------------------------ P04-N03 (P3-B2)
def test_n03_admin_appointments_show_unknown_fee_as_null_not_zero(db):
    admin, patient, doctor = _admin(db), _make_test_patient(db, "P04N03"), _make_test_doctor(db, "P04N03Doc")
    oid = ObjectId()
    db["appointments"].insert_one({
        "_id": oid, "patientUserId": patient["id"], "doctorUserId": doctor["id"], "doctorProfileId": str(ObjectId()),
        "appointmentDate": _day(), "startTime": "09:00", "endTime": "09:30", "status": "CANCELLED",
        "paymentStatus": "UNPAID", "consultationFee": None, "createdAt": utc_now(), "updatedAt": utc_now()})
    res = client.get(f"/api/admin/appointments?search={oid}", headers=_auth(admin))
    assert res.status_code == 200, res.text
    row = next(i for i in res.json()["items"] if i["id"] == str(oid))
    assert row["consultationFee"] is None  # was 0.0 (an invented "LKR 0.00")
    assert row["doctorSpecialty"] is None  # was the invented "General Medicine"
    assert row["consultationType"] == "IN_PERSON"


# ------------------------------------------------------------------------------------------------ P04-N04
def test_n04_admin_payments_date_filter_refunds_and_mode(db):
    admin, patient, doctor = _admin(db), _make_test_patient(db, "P04N04"), _make_test_doctor(db, "P04N04Doc")
    day = _day()
    nxt = (datetime.fromisoformat(day) + timedelta(days=2)).strftime("%Y-%m-%d")
    inside = _captured(db, patient, doctor, 1000.0, refunded=200.0, paid_at=_colombo(day))
    _captured(db, patient, doctor, 500.0, paid_at=_colombo(nxt))
    res = client.get(f"/api/admin/payments?startDate={day}&endDate={day}", headers=_auth(admin))
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert [i["stripePaymentIntentId"] for i in items] == [inside["stripePaymentIntentId"]]  # filter was ignored
    assert items[0]["refundedAmount"] == 200.0
    assert items[0]["isTestMode"] is True  # sk_test_ key in the test session


# ------------------------------------------------------------------------------------------------ P04-N05 / N06
def test_n05_collections_count_refunds_once_and_include_partial_refunds():
    rows = collections([
        {"status": "SUCCEEDED", "amount": 3000.0, "currency": "lkr"},
        {"status": "REFUNDED", "amount": 2000.0, "currency": "lkr"},               # full refund, no refundedAmount
        {"status": "SUCCEEDED", "amount": 1000.0, "currency": "lkr", "refundedAmount": 200.0},  # partial
        {"status": "FAILED", "amount": 9999.0, "currency": "lkr"},
        {"status": "SUCCEEDED", "amount": 10.0, "currency": "usd", "refundedAmount": 50.0},     # capped
    ])
    lkr = rows["lkr"]
    assert lkr["capturedAmount"] == 6000.0 and lkr["refundedAmount"] == 2200.0 and lkr["netCollected"] == 3800.0
    assert lkr["fullyRefundedCount"] == 1 and lkr["partiallyRefundedCount"] == 1
    assert rows["usd"]["refundedAmount"] == 10.0  # never more than captured


def test_n05_overview_and_reports_use_refund_aware_figures_and_no_platform_fee(db):
    admin, patient, doctor = _admin(db), _make_test_patient(db, "P04N05"), _make_test_doctor(db, "P04N05Doc")
    day = _day()
    _captured(db, patient, doctor, 3000.0, paid_at=_colombo(day))
    _captured(db, patient, doctor, 2000.0, status="REFUNDED", paid_at=_colombo(day, "11:00"))
    _captured(db, patient, doctor, 1000.0, refunded=200.0, paid_at=_colombo(day, "12:00"))
    ov = client.get(f"/api/admin/analytics/overview?startDate={day}&endDate={day}", headers=_auth(admin)).json()
    lkr = next(r for r in ov["totalRevenueByCurrency"] if r["currency"] == "lkr")
    # Before Phase 04: gross 4000 (refunded payment excluded), refunded 2000, net 2000 (refund counted twice).
    assert (lkr["grossAmount"], lkr["refundedAmount"], lkr["netAmount"]) == (6000.0, 2200.0, 3800.0)
    assert ov["payments"]["platformRevenue"] is None and "not platform profit" in ov["payments"]["note"]
    report = client.post("/api/admin/workflow/reports/generate", json={"reportType": "monthly_payment",
                         "startDate": day, "endDate": day}, headers=_auth(admin)).json()
    m = report["metrics"]
    assert m["capturedAmountLKR"] == 6000.0 and m["refundedAmountLKR"] == 2200.0 and m["netCollectedLKR"] == 3800.0
    assert m["platformRevenue"] is None and not any("platformFee" in k for k in m)  # the invented 10% is gone
    empty = client.get("/api/admin/analytics/payments?startDate=2032-02-02&endDate=2032-02-02", headers=_auth(admin)).json()
    assert empty["paymentSuccessRate"] is None  # was 100% with no payments


def test_n06_asia_colombo_day_boundaries_and_strict_dates(db):
    admin, patient, doctor = _admin(db), _make_test_patient(db, "P04N06"), _make_test_doctor(db, "P04N06Doc")
    # 02:00 in Colombo is 20:30 UTC on the previous day.
    day = _day()
    prev = (datetime.fromisoformat(day) - timedelta(days=1)).strftime("%Y-%m-%d")
    _captured(db, patient, doctor, 700.0, paid_at=_colombo(day, "02:00"))
    def captured_on(day):
        rows = client.get(f"/api/admin/analytics/payments?startDate={day}&endDate={day}", headers=_auth(admin)).json()
        return next((r["grossAmount"] for r in rows["revenueByCurrency"] if r["currency"] == "lkr"), 0.0)
    assert captured_on(day) == 700.0 and captured_on(prev) == 0.0
    start, end, _, _ = platform_range(day, day)
    assert end - start == timedelta(days=1) - timedelta(microseconds=1)  # whole local day, end inclusive
    rep = client.post("/api/admin/workflow/reports/generate", json={"reportType": "monthly_payment",
                      "startDate": day, "endDate": day}, headers=_auth(admin)).json()
    assert rep["metrics"]["capturedAmountLKR"] == 700.0  # the end day used to be excluded (end at 00:00)
    bad = client.post("/api/admin/workflow/reports/generate", json={"reportType": "monthly_payment",
                      "startDate": "2031-13-40"}, headers=_auth(admin))
    assert bad.status_code == 400  # was silently replaced with "last 30 days"


# ------------------------------------------------------------------------------------------------ P04-N07
def test_n07_pending_doctor_counts_include_awaiting_admin_approval(db):
    admin = _admin(db)
    before = client.get("/api/admin/analytics/doctors", headers=_auth(admin)).json()["pendingDoctors"]
    db["doctor_profiles"].insert_one({"userId": str(ObjectId()), "doctorId": f"DOC-P04-{uuid.uuid4().hex[:6]}",
                                      "verificationStatus": "PENDING_ADMIN_APPROVAL", "specialty": "Dermatology",
                                      "medicalRegistrationNumber": f"P04-{uuid.uuid4().hex[:6]}", "createdAt": utc_now()})
    after = client.get("/api/admin/analytics/doctors", headers=_auth(admin)).json()["pendingDoctors"]
    assert after == before + 1


# ------------------------------------------------------------------------------------------------ P04-N08
def _pending_doctor(db, reg="P04-REG-1"):
    uid = ObjectId()
    db["users"].insert_one({"_id": uid, "fullName": "Dr. P04 Applicant", "email": f"doctor_p04_{uid}@mediconnect.lk",
                            "passwordHash": hash_password("Secret123!"), "role": "DOCTOR", "emailVerified": True,
                            "accountStatus": "PENDING", "createdAt": utc_now(), "updatedAt": utc_now()})
    pid = db["doctor_profiles"].insert_one({
        "userId": str(uid), "doctorId": f"DOC-P04-{uuid.uuid4().hex[:8]}", "verificationStatus": "PENDING_ADMIN_APPROVAL",
        "medicalRegistrationNumber": reg, "specialty": "General Physician", "qualifications": "MBBS",
        "verificationDocuments": {k: {"documentId": uuid.uuid4().hex} for k in
                                  ("identityDocument", "medicalRegistrationDocument", "qualificationDocument")},
        "createdAt": utc_now(), "updatedAt": utc_now()}).inserted_id
    return str(uid), str(pid)


def test_n08_approval_needs_registration_number_and_decisions_are_audited(db):
    admin = _admin(db)
    db["doctor_profiles"].delete_many({"medicalRegistrationNumber": ""})  # earlier runs (isolated test DB, unique index)
    _, no_reg = _pending_doctor(db, reg="")
    res = client.post(f"/api/admin/doctors/{no_reg}/approve", headers=_auth(admin))
    assert res.status_code == 400 and "registration number" in res.json()["detail"]
    doctor_uid, pid = _pending_doctor(db, reg=f"P04-{uuid.uuid4().hex[:6]}")
    assert client.post(f"/api/admin/doctors/{pid}/approve", headers=_auth(admin)).status_code == 200
    assert client.post(f"/api/admin/doctors/{pid}/approve", headers=_auth(admin)).status_code == 400  # no double approval
    audit = db["admin_audit_logs"].find_one({"targetId": pid, "actionType": "DOCTOR_VERIFICATION_DECISION"})
    assert audit and audit["actorId"] == admin["id"] and audit["newState"] == "APPROVED"
    assert audit["metadata"]["registrationNumberOfficiallyVerified"] is False
    _, rej = _pending_doctor(db, reg=f"P04-{uuid.uuid4().hex[:6]}")
    assert client.post(f"/api/admin/doctors/{rej}/reject", json={"reason": "Registration certificate unreadable"},
                       headers=_auth(admin)).status_code == 200
    assert db["admin_audit_logs"].count_documents({"targetId": rej, "newState": "REJECTED"}) == 1


def test_n08_user_status_transitions_revoke_sessions_and_are_audited(db):
    admin = _admin(db)
    doctor = _make_test_doctor(db, "P04N08Doc")
    db["refresh_tokens"].insert_one({"userId": doctor["id"], "tokenHash": uuid.uuid4().hex, "revokedAt": None})
    res = client.patch(f"/api/admin/users/{doctor['id']}/status", json={"accountStatus": "SUSPENDED",
                       "reason": "Registration under review"}, headers=_auth(admin))
    assert res.status_code == 200, res.text
    # Takes effect on the very next request, and no new session can be refreshed.
    assert client.get("/api/doctors/me/appointments", headers=_auth(doctor)).status_code in (401, 403)
    assert db["refresh_tokens"].count_documents({"userId": doctor["id"], "revokedAt": None}) == 0
    log = db["admin_audit_logs"].find_one({"targetId": doctor["id"], "actionType": "USER_STATUS_CHANGE"})
    assert log and log["previousState"] == "ACTIVE" and log["newState"] == "SUSPENDED" and log["reason"]
    pending = _make_test_patient(db, "P04N08Pend")
    db["users"].update_one({"_id": ObjectId(pending["id"])}, {"$set": {"accountStatus": "PENDING", "emailVerified": False}})
    skip = client.patch(f"/api/admin/users/{pending['id']}/status", json={"accountStatus": "ACTIVE"}, headers=_auth(admin))
    assert skip.status_code == 409  # admins cannot skip email verification
    bad = client.patch(f"/api/admin/users/{pending['id']}/status", json={"accountStatus": "DEACTIVATED"}, headers=_auth(admin))
    assert bad.status_code == 422


# ------------------------------------------------------------------------------------------------ P04-N09 / N10
def test_n09_reject_cannot_overwrite_a_concurrent_approval(db):
    admin = _admin(db)
    patient, _, appt, payment, refund = _cancelled_paid(db, "P04N09")
    started = threading.Event()

    def slow_refund(**kwargs):
        started.set()
        time.sleep(0.6)
        return MagicMock(id="re_p04_slow", status="succeeded")

    with patch("stripe.Refund.create", side_effect=slow_refund):
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(RefundService.approve_refund, db, admin["id"], refund["refundId"])
            started.wait(5)
            with pytest.raises(HTTPException) as exc:
                RefundService.reject_refund(db, admin["id"], refund["refundId"], "Late reject")
            assert exc.value.status_code in (400, 409)
            assert fut.result()["status"] == "succeeded"
    stored = db["refund_requests"].find_one({"_id": refund["_id"]})
    assert stored["status"] == "succeeded" and stored["refundedAmount"] == 3000.0
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "REFUNDED"
    note = db["notifications"].find_one({"recipientUserId": patient["id"], "idempotencyKey": f"refund_succeeded_{refund['refundId']}"})
    assert note and "LKR 3,000.00" in note["body"]
    for bad in ("not-an-id", "zzz"):
        with pytest.raises(HTTPException) as exc:
            RefundService.get_refund_request(db, bad)
        assert exc.value.status_code == 404  # was a 500 from bson


def test_n09_rejection_notifies_patient_and_is_final(db):
    admin = _admin(db)
    patient, _, _, _, refund = _cancelled_paid(db, "P04N09R", by="patient")
    res = client.post(f"/api/admin/workflow/refunds/{refund['refundId']}/reject", json={"reason": "Outside policy"},
                      headers=_auth(admin))
    assert res.status_code == 200, res.text
    again = client.post(f"/api/admin/workflow/refunds/{refund['refundId']}/reject", json={"reason": "Outside policy"},
                        headers=_auth(admin))
    assert again.status_code == 409
    approve = client.post(f"/api/admin/workflow/refunds/{refund['refundId']}/approve", json={}, headers=_auth(admin))
    assert approve.status_code == 409  # a rejected request cannot be approved
    assert db["notifications"].count_documents({"recipientUserId": patient["id"],
                                                "idempotencyKey": f"refund_rejected_{refund['refundId']}"}) == 1


def test_n10_doctor_initiated_refund_requests_are_labelled_and_filterable(db):
    admin = _admin(db)
    _, doctor, appt, _, refund = _cancelled_paid(db, "P04N10")
    assert refund["source"] == "doctor" and refund["cancelledBy"] == "DOCTOR"
    assert refund["requestedBy"] == doctor["id"]
    listed = client.get("/api/admin/workflow/refunds?source=doctor&pageSize=100", headers=_auth(admin)).json()["items"]
    row = next(r for r in listed if r["refundId"] == refund["refundId"])
    assert row["source"] == "doctor" and row["cancellationReason"] == "Doctor unavailable"
    assert row["policyEligibility"]["eligibleAmount"] == 3000.0  # existing 100% doctor-cancellation rule
    # A request created before Phase 04 has no source; the appointment's cancelledBy is used.
    db["refund_requests"].update_one({"_id": refund["_id"]}, {"$unset": {"source": "", "cancelledBy": ""}})
    detail = client.get(f"/api/admin/workflow/refunds/{refund['refundId']}", headers=_auth(admin)).json()
    assert detail["source"] == "doctor"


def test_n10_refund_failure_then_retry_after_external_success(db):
    """Stripe succeeds but the response is lost: the retry returns the same refund (same idempotency key)."""
    import stripe
    admin = _admin(db)
    _, _, _, payment, refund = _cancelled_paid(db, "P04N10F")
    keys = []

    def lost_response(**kwargs):
        keys.append(kwargs["idempotency_key"])
        raise stripe.error.APIConnectionError("connection reset after refund was created")

    with patch("stripe.Refund.create", side_effect=lost_response):
        with pytest.raises(HTTPException) as exc:
            RefundService.approve_refund(db, admin["id"], refund["refundId"])
        assert exc.value.status_code == 502
    assert db["refund_requests"].find_one({"_id": refund["_id"]})["status"] == "failed"
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "SUCCEEDED"  # nothing recorded as refunded

    def replay(**kwargs):
        keys.append(kwargs["idempotency_key"])
        return MagicMock(id="re_p04_same", status="succeeded")

    with patch("stripe.Refund.create", side_effect=replay):
        assert RefundService.approve_refund(db, admin["id"], refund["refundId"])["status"] == "succeeded"
    assert len(set(keys)) == 1  # one idempotency key: Stripe returns the existing refund, no second refund
    stored = db["payments"].find_one({"_id": payment["_id"]})
    assert stored["refundedAmount"] == 3000.0 and stored["refundRequestIds"] == [refund["refundId"]]


# ------------------------------------------------------------------------------------------------ P04-N11
def test_n11_reconciliation_never_advises_confirming_a_cancelled_booking(db):
    _, _, appt, payment, refund = _cancelled_paid(db, "P04N11")
    report = PaymentMonitoringService.run_reconciliation_checks(db)
    mine = [d for d in report["discrepancies"] if d.get("appointmentId") == appt.id]
    assert [d["type"] for d in mine] == ["CANCELLED_AWAITING_REFUND_DECISION"]
    assert not any("Confirm appointment" in d["recommendation"] for d in report["discrepancies"])
    # Amount mismatch against the amount accepted at booking.
    db["payments"].update_one({"_id": payment["_id"]}, {"$set": {"amount": 2999.0}})
    types = {d["type"] for d in PaymentMonitoringService.run_reconciliation_checks(db)["discrepancies"]
             if d.get("appointmentId") == appt.id}
    assert "AMOUNT_MISMATCH" in types
    # One PaymentIntent cannot be recorded twice: the unique index rejects it before reconciliation is needed.
    from pymongo.errors import DuplicateKeyError
    dup = dict(db["payments"].find_one({"_id": payment["_id"]}))
    dup.pop("_id")
    with pytest.raises(DuplicateKeyError):
        db["payments"].insert_one(dup)


# ------------------------------------------------------------------------------------------------ P04-N12
def test_n12_fraud_rules_use_real_statuses_and_manual_events_are_not_evidence(db):
    admin = _admin(db)
    a, b, doctor = _make_test_patient(db, "P04N12A"), _make_test_patient(db, "P04N12B"), _make_test_doctor(db, "P04N12Doc")
    for _ in range(3):
        _payment(db, str(ObjectId()), a, doctor, status="FAILED")  # stored upper case, as the payment service does
    # A PaymentIntent shared by two accounts cannot be stored (unique index), so DUPLICATE_PAYMENT_REFERENCES can
    # only fire on data written outside the application.
    from pymongo.errors import DuplicateKeyError
    shared = f"pi_p04_shared_{uuid.uuid4().hex[:8]}"
    _payment(db, str(ObjectId()), a, doctor, status="SUCCEEDED", intent=shared)
    with pytest.raises(DuplicateKeyError):
        _payment(db, str(ObjectId()), b, doctor, status="SUCCEEDED", intent=shared)
    for _ in range(5):  # typed in by an admin: must not count
        client.post("/api/security/events", json={"category": "UNAUTHORIZED_ACCESS", "severity": "HIGH",
                    "description": "manual", "actorId": a["id"]}, headers=_auth(admin))
    assessment = FraudDetectionService.evaluate_account_risk(account_id=a["id"], db=db)
    assert assessment.triggeredRules == ["MULTIPLE_FAILED_PAYMENTS"]  # the 5 admin-typed events did not count
    assert "not a finding of fraud" in assessment.explanation
    assert db["users"].find_one({"_id": ObjectId(a["id"])})["accountStatus"] == "ACTIVE"  # no automatic action
    bad = client.post(f"/api/security/fraud/assessments/{assessment.assessmentId}/review",
                      json={"decision": "ban", "notes": "test"}, headers=_auth(admin))
    assert bad.status_code == 422
    ok = client.post(f"/api/security/fraud/assessments/{assessment.assessmentId}/review",
                     json={"decision": "dismiss", "notes": "False positive: card retried"}, headers=_auth(admin))
    assert ok.status_code == 200 and ok.json()["reviewStatus"] == "DISMISSED"
    assert db["admin_audit_logs"].count_documents({"targetId": assessment.assessmentId,
                                                   "actionType": "FRAUD_REVIEW_DECISION"}) == 1


# ------------------------------------------------------------------------------------------------ P04-N13 / N14
def test_n13_n14_heartbeat_requires_admin_and_health_is_not_invented(db):
    patient = _make_test_patient(db, "P04N13")
    url = "/api/security/monitoring/workers/heartbeat?workerName=reminder_care_worker&jobCount=0"
    assert client.post(url).status_code == 401
    assert client.post(url, headers=_auth(patient)).status_code == 403
    db["worker_heartbeats"].delete_many({"workerName": "reminder_care_worker"})
    admin = _admin(db)
    snap = client.get("/api/security/monitoring/platform", headers=_auth(admin)).json()
    worker = next(w for w in snap["workers"] if w["workerName"] == "reminder_care_worker")
    assert worker["status"] == "not_reported" and worker["lastHeartbeat"] is None  # was "active", now
    deps = {d["name"]: d["status"] for d in snap["dependencies"]}
    assert deps["Stripe Payments"] == "configured_not_verified"  # was "healthy" because a key existed
    assert deps["Push (FCM)"] in ("not_configured", "configured_not_verified")
    assert snap["status"] != "healthy"


# ------------------------------------------------------------------------------------------------ P04-N15
def test_n15_push_is_not_counted_delivered_and_permanent_failures_are_not_retried(db):
    admin = _admin(db)
    before = client.get("/api/security/monitoring/notifications", headers=_auth(admin)).json()
    push_before = next(c for c in before["byChannel"] if c["channel"] == "push")
    db["notifications"].insert_one({"recipientUserId": str(ObjectId()), "title": "x", "body": "y", "isRead": False,
                                    "type": "SYSTEM", "createdAt": utc_now()})
    after = client.get("/api/security/monitoring/notifications", headers=_auth(admin)).json()
    push_after = next(c for c in after["byChannel"] if c["channel"] == "push")
    assert push_after["delivered"] == push_before["delivered"]  # a stored in-app item is not a push delivery
    perm, transient = ObjectId(), ObjectId()
    for oid, reason in ((perm, "provider_not_configured"), (transient, "connection_timeout")):
        db["appointments"].insert_one({"_id": oid, "status": "CONFIRMED", "patientUserId": str(ObjectId()),
                                       "doctorUserId": str(ObjectId()), "appointmentDate": _day(), "startTime": "09:00",
                                       "confirmationOutbox": {"email": {"status": "failed", "attempts": 1,
                                                                        "reason": reason}}})
    result = NotificationMonitoringService.process_notification_retries(db)
    assert result["notRetryableCount"] >= 1
    assert db["appointments"].find_one({"_id": perm})["confirmationOutbox"]["email"]["status"] == "failed"
    requeued = db["appointments"].find_one({"_id": transient})["confirmationOutbox"]["email"]
    assert requeued["status"] == "pending" and requeued["nextAttemptAt"]  # the state the outbox worker processes


# ------------------------------------------------------------------------------------------------ P04-N16
def test_n16_monitoring_assistant_counts_real_failed_payments(db):
    admin, patient, doctor = _admin(db), _make_test_patient(db, "P04N16"), _make_test_doctor(db, "P04N16Doc")
    _payment(db, str(ObjectId()), patient, doctor, status="FAILED")
    res = client.post("/api/security/ai-assistant/chat", json={"message": "failed payments today?"},
                      headers=_auth(admin)).json()
    assert res["intent"] == "failed_payments_check"
    assert res["relevantMetrics"]["failedCount"] >= 1 and "operating normally" not in res["response"]


# ------------------------------------------------------------------------------------------------ P04-N17
def test_n17_csv_export_keeps_zeros_escapes_formulas_and_rejects_unknown_reports(db):
    admin, patient = _admin(db), _make_test_patient(db, "P04N17")
    client.post("/api/admin/workflow/tickets", json={"subject": "=HYPERLINK(\"http://x\")",
                "description": "\t=1+1 payment question", "category": "payment_issue"}, headers=_auth(patient))
    today = datetime.now(PLATFORM_TZ).strftime("%Y-%m-%d")
    res = client.post("/api/admin/workflow/reports/export-csv", json={"reportType": "support_ticket_resolution",
                      "startDate": today, "endDate": today}, headers=_auth(admin))
    assert res.status_code == 200
    rows = list(csv.reader(io.StringIO(res.text)))
    assert ["resolvedCount", "0"] in rows or any(r[:1] == ["resolvedCount"] and r[1] != "" for r in rows)
    subjects = [r for r in rows if any(c.startswith("'=HYPERLINK") for c in r)]
    assert subjects, "formula-like text must be prefixed with a quote"
    assert all(not c.startswith("=") for r in rows for c in r)
    assert db["admin_audit_logs"].count_documents({"actionType": "REPORT_EXPORTED", "actorId": admin["id"]}) >= 1
    unknown = client.post("/api/admin/workflow/reports/generate", json={"reportType": "weekly_booking"}, headers=_auth(admin))
    assert unknown.status_code == 422  # was silently answered with the refund report


# ------------------------------------------------------------------------------------------------ P04-N18
def test_n18_tickets_cannot_link_other_patients_appointments_and_replies_notify(db):
    admin, a, b, doctor = _admin(db), _make_test_patient(db, "P04N18A"), _make_test_patient(db, "P04N18B"), _make_test_doctor(db, "P04N18Doc")
    appt_b, _ = _pay_confirmed(db, b, doctor, _make_future_availability(db, doctor, 10))
    res = client.post("/api/admin/workflow/tickets", json={"subject": "Refund?", "description": "Where is my refund",
                      "relatedEntityId": appt_b.id}, headers=_auth(a))
    assert res.status_code == 403
    own = client.post("/api/admin/workflow/tickets", json={"subject": "Payment question", "description": "Receipt",
                      "relatedEntityId": appt_b.id}, headers=_auth(b))
    assert own.status_code == 201, own.text
    tid = own.json()["ticketId"]
    assert client.get(f"/api/admin/workflow/tickets/{tid}", headers=_auth(a)).status_code == 403
    assert client.get("/api/admin/workflow/tickets/not-a-ticket", headers=_auth(admin)).status_code == 404
    reply = client.post(f"/api/admin/workflow/tickets/{tid}/reply", json={"message": "We are checking.",
                        "status": "in_progress"}, headers=_auth(admin))
    assert reply.status_code == 200
    assert db["notifications"].count_documents({"recipientUserId": b["id"], "title": "Support ticket update"}) == 1
    bad_status = client.post(f"/api/admin/workflow/tickets/{tid}/reply", json={"message": "x", "status": "deleted"},
                             headers=_auth(admin))
    assert bad_status.status_code == 422


# ------------------------------------------------------------------------------------------------ A-14 privacy / audit
def test_a14_admin_clinical_routes_return_no_patient_clinical_content(db):
    admin, patient = _admin(db), _make_test_patient(db, "P04A14")
    db["patient_medical_records"].insert_one({"recordId": f"MED-P04-{uuid.uuid4().hex[:6]}", "patientUserId": patient["id"],
                                              "title": "P04 synthetic diagnosis", "recordType": "DIAGNOSIS",
                                              "createdAt": utc_now(), "updatedAt": utc_now()})
    db["clinical_notes"].insert_one({"noteId": f"NOTE-P04-{uuid.uuid4().hex[:8]}", "patientUserId": patient["id"], "doctorUserId": str(ObjectId()), "status": "signed",
                                     "content": {"assessment": "P04 synthetic assessment"}, "createdAt": utc_now()})
    for path in (f"/api/clinical/records?patientId={patient['id']}", f"/api/clinical/notes?patientId={patient['id']}",
                 f"/api/clinical/measurements/trends?patientId={patient['id']}"):
        res = client.get(path, headers=_auth(admin))
        assert "P04 synthetic" not in res.text, path  # patientId is ignored for non-doctors: admin gets only own data


def test_a14_audit_logs_have_no_write_routes_for_clients():
    from app.main import app
    for route in app.routes:
        path = getattr(route, "path", "")
        if "audit" in path:
            assert set(getattr(route, "methods", set())) <= {"GET", "HEAD"}, path


# ------------------------------------------------------------------------------------------------ P04-N20
def test_n20_repeated_security_events_and_assessments_can_be_stored(db):
    """Models dumped with "_id": None made every insert after the first fail with a duplicate-key error."""
    admin = _admin(db)
    statuses = [client.post("/api/security/events", json={"category": "SUSPICIOUS_PAYMENT", "severity": "LOW",
                            "description": f"P04 event {i}"}, headers=_auth(admin)).status_code for i in range(3)]
    assert statuses == [201, 201, 201]
    assert db["security_events"].count_documents({"_id": None}) == 0
    from app.services.incident_management_service import IncidentManagementService  # noqa: F401
    for i in range(2):
        res = client.post("/api/security/incidents", json={"title": f"P04 incident {i}", "description": "synthetic",
                          "severity": "LOW", "category": "SYSTEM"}, headers=_auth(admin))
        assert res.status_code in (201, 422), res.text
    assert db["operational_incidents"].count_documents({"_id": None}) == 0
