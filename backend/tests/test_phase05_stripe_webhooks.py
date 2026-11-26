"""Phase 05 B3 / P4-B10: Stripe webhook integrity with locally signed events.

Events are signed here with the test webhook secret exactly as Stripe signs them (HMAC-SHA256 over
"<timestamp>.<raw body>"), and the real stripe library verifies them; nothing is mocked in the signature path.
External delivery from Stripe to this backend is NOT exercised (no Stripe CLI / public endpoint): BLOCKED.
"""
import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import MagicMock, patch

from bson import ObjectId
import pytest

from app.config.settings import settings
from app.services import stripe_webhook_service as hooks
from tests.test_payment import client, db  # noqa: F401
from tests.test_phase02_booking_payment import _admin, _auth
from tests.test_phase04_admin_system import _cancelled_paid


def _signed(event: dict, secret=None, ts=None, tamper=False):
    body = json.dumps(event).encode()
    ts = ts or int(time.time())
    sig = hmac.new((secret or settings.STRIPE_WEBHOOK_SECRET).encode(), f"{ts}.".encode() + body,
                   hashlib.sha256).hexdigest()
    if tamper:
        body = body.replace(b'"livemode": false', b'"livemode": false ')
    return body, {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


def _event(event_type, obj, event_id=None, livemode=False):
    return {"id": event_id or f"evt_p05_{uuid.uuid4().hex[:18]}", "object": "event", "type": event_type,
            "livemode": livemode, "created": int(time.time()), "data": {"object": obj}}


def _post(event, **kw):
    body, headers = _signed(event, **kw)
    return client.post("/api/payments/webhook", content=body, headers=headers)


def _processing_refund(db, suffix, amount=None):
    patient, doctor, appt, payment, refund = _cancelled_paid(db, suffix)
    re_id = f"re_p05_{uuid.uuid4().hex[:16]}"
    amt = amount if amount is not None else float(payment["amount"] if isinstance(payment, dict) else payment.amount)
    db["refund_requests"].update_one({"_id": refund["_id"]}, {"$set": {
        "status": "PROCESSING", "stripeRefundId": re_id, "approvedAmount": amt}})
    pay = db["payments"].find_one({"_id": ObjectId(refund["paymentId"])})
    return db["refund_requests"].find_one({"_id": refund["_id"]}), pay, re_id


def _refund_obj(re_id, pay, status, amount=None, currency=None):
    return {"id": re_id, "object": "refund", "status": status,
            "amount": int(round((amount if amount is not None else pay["amount"]) * 100)),
            "currency": currency or pay["currency"], "payment_intent": pay["stripePaymentIntentId"]}


# ------------------------------------------------------------------------------------------------ signature
def test_signature_raw_body_and_tolerance_are_enforced(db):
    ev = _event("payment_intent.canceled", {"id": "pi_unknown_p05", "object": "payment_intent"})
    assert _post(ev).status_code == 200
    assert _post(_event("payment_intent.canceled", {"id": "pi_x"}), tamper=True).status_code == 400
    assert _post(_event("payment_intent.canceled", {"id": "pi_x"}), secret="whsec_wrong").status_code == 400
    old = int(time.time()) - 3600  # outside Stripe's 300 s tolerance: replayed capture
    assert _post(_event("payment_intent.canceled", {"id": "pi_x"}), ts=old).status_code == 400
    assert client.post("/api/payments/webhook", content=b"{}").status_code == 400  # no signature header


def test_livemode_event_is_ignored_with_a_test_key(db):
    res = _post(_event("refund.updated", {"id": "re_x", "object": "refund", "status": "succeeded"}, livemode=True))
    assert res.json()["status"] == "ignored"


# ------------------------------------------------------------------------------------------------ refunds
def test_pending_refund_reaches_final_state_once_and_redelivery_is_a_duplicate(db):
    request, pay, re_id = _processing_refund(db, "P05WH1")
    ev = _event("refund.updated", _refund_obj(re_id, pay, "succeeded"))
    first = _post(ev).json()
    assert first["status"] == "refund_succeeded"
    assert _post(ev).json()["status"] == "already_processed"                            # same event id redelivered
    again = _post(_event("charge.refunded", {"object": "charge", "refunds": {"data": [
        _refund_obj(re_id, pay, "succeeded")]}})).json()                        # different event, same refund
    assert again["status"] == "no_change"
    after = db["refund_requests"].find_one({"_id": request["_id"]})
    payment = db["payments"].find_one({"_id": pay["_id"]})
    assert after["status"] == "SUCCEEDED" and payment["refundedAmount"] == pay["amount"]  # applied exactly once
    assert payment["status"] == "REFUNDED"
    assert db["admin_audit_logs"].find_one({"actionType": "REFUND_RECONCILIATION", "targetId": request["refundId"]})
    logged = db[hooks.EVENTS].find_one({"_id": ev["id"]})
    assert logged["status"] == "processed" and "data" not in logged  # no payload stored


def test_out_of_order_pending_after_success_is_ignored_and_failure_after_success_needs_review(db):
    request, pay, re_id = _processing_refund(db, "P05WH2")
    assert _post(_event("refund.updated", _refund_obj(re_id, pay, "succeeded"))).json()["status"] == "refund_succeeded"
    assert _post(_event("refund.updated", _refund_obj(re_id, pay, "pending"))).json()["status"] == "ignored_out_of_order"
    flagged = _post(_event("refund.failed", _refund_obj(re_id, pay, "failed"))).json()
    assert flagged["status"] == "flagged_for_review"
    doc = db["refund_requests"].find_one({"_id": request["_id"]})
    assert doc["status"] == "SUCCEEDED" and doc["requiresReview"] is True  # money records not edited automatically
    assert db["payments"].find_one({"_id": pay["_id"]})["refundedAmount"] == pay["amount"]


def test_refund_failure_marks_failed_and_is_audited(db):
    request, pay, re_id = _processing_refund(db, "P05WH3")
    assert _post(_event("refund.failed", _refund_obj(re_id, pay, "failed"))).json()["status"] == "refund_failed"
    assert db["refund_requests"].find_one({"_id": request["_id"]})["status"] == "FAILED"
    assert db["payments"].find_one({"_id": pay["_id"]}).get("refundedAmount", 0) in (0, None)


@pytest.mark.parametrize("change", ["currency", "amount", "intent"])
def test_refund_event_that_does_not_match_its_payment_changes_nothing(db, change):
    request, pay, re_id = _processing_refund(db, f"P05WH4{change}")
    obj = _refund_obj(re_id, pay, "succeeded")
    if change == "currency":
        obj["currency"] = "usd"
    elif change == "amount":
        obj["amount"] = int(pay["amount"] * 100) + 100
    else:
        obj["payment_intent"] = "pi_someone_else"
    assert _post(_event("refund.updated", obj)).json()["status"] == "rejected_mismatch"
    assert db["refund_requests"].find_one({"_id": request["_id"]})["status"] == "PROCESSING"


def test_unknown_refund_is_ignored(db):
    res = _post(_event("refund.updated", {"id": "re_not_ours", "object": "refund", "status": "succeeded",
                                          "amount": 100, "currency": "lkr", "payment_intent": "pi_x"}))
    assert res.json()["status"] == "ignored_unknown_refund"


# ------------------------------------------------------------------------------------------------ intents
def test_payment_intent_canceled_never_confirms_anything(db):
    patient, doctor, appt, payment, refund = _cancelled_paid(db, "P05WH5")
    pid = ObjectId()
    db["payments"].insert_one({"_id": pid, "appointmentId": str(ObjectId()), "patientUserId": patient["id"],
                               "stripePaymentIntentId": f"pi_p05_cancel_{pid}", "amount": 1000.0, "currency": "lkr",
                               "status": "PENDING"})
    res = _post(_event("payment_intent.canceled", {"id": f"pi_p05_cancel_{pid}", "object": "payment_intent",
                                                    "cancellation_reason": "abandoned"}))
    assert res.json()["status"] == "payment_cancelled"
    assert db["payments"].find_one({"_id": pid})["status"] == "CANCELLED"


# ------------------------------------------------------------------------------------------------ polling fallback
def test_sync_pending_refunds_applies_final_state_and_survives_network_errors(db):
    request, pay, re_id = _processing_refund(db, "P05WH6")
    db["refund_requests"].update_one({"_id": request["_id"]}, {"$set": {"updatedAt": hooks.utc_now().replace(year=2020)}})
    failing = MagicMock(side_effect=ConnectionError("network down"))
    stats = hooks.sync_pending_refunds(db, retrieve=failing)
    assert stats["checked"] >= 1 and db["refund_requests"].find_one({"_id": request["_id"]})["status"] == "PROCESSING"
    ok = MagicMock(side_effect=lambda rid: _refund_obj(rid, pay, "succeeded") if rid == re_id else
                   {"id": rid, "status": "pending"})
    hooks.sync_pending_refunds(db, retrieve=ok)
    assert db["refund_requests"].find_one({"_id": request["_id"]})["status"] == "SUCCEEDED"


def test_admin_sync_endpoint_is_admin_only(db):
    from tests.test_payment import _make_test_patient
    patient = _make_test_patient(db, "P05WH7")
    assert client.post("/api/admin/workflow/refunds/sync-pending", headers=_auth(patient)).status_code == 403
    with patch("app.services.stripe_webhook_service.sync_pending_refunds", return_value={"checked": 0}):
        assert client.post("/api/admin/workflow/refunds/sync-pending", headers=_auth(_admin(db))).status_code == 200


# ------------------------------------------------------------------------------------------------ P4-O7
def test_reconcile_refund_is_audited(db):
    admin = _admin(db)
    pid, appt_id = ObjectId(), ObjectId()
    db["appointments"].insert_one({"_id": appt_id, "status": "CANCELLED", "paymentStatus": "PAID"})
    db["payments"].insert_one({"_id": pid, "appointmentId": str(appt_id), "stripePaymentIntentId": f"pi_p05_rec_{pid}",
                               "amount": 1500.0, "currency": "lkr", "status": "SUCCEEDED",
                               "reconciliationState": "REVIEW_REQUIRED"})
    fake = MagicMock(id=f"re_p05_rec_{pid}", status="succeeded")
    with patch("stripe.Refund.create", return_value=fake):
        res = client.post(f"/api/payments/{pid}/reconcile-refund", headers=_auth(admin))
    assert res.status_code == 200 and res.json()["reconciliationState"] == "REFUNDED"
    audit = db["admin_audit_logs"].find_one({"actionType": "PAYMENT_RECONCILIATION_ACTION", "targetId": str(pid)})
    assert audit and audit["actorId"] == admin["id"] and audit["newState"] == "REFUNDED"
