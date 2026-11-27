"""Agent Completion A03: booking payments, Stripe webhooks and refund integrity (Agent 01).

Runs against the isolated local MongoDB test database. Stripe network calls are replaced with test doubles here;
webhook signatures are computed exactly as Stripe computes them and verified by the real stripe library.
Real Stripe test-mode runs and Stripe CLI deliveries are in docs/uat/agent-completion/a03 (live scripts).
IDs: A03-BUG-nnn (see A03_BUG_FIX_REPORT.md).
"""
import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch
import uuid

from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
import stripe

from app.main import app
from app.models.appointment import utc_now
from app.services import stripe_webhook_service as hooks
from app.services.appointment_service import AppointmentService
from app.services.refund_service import RefundService
from tests.test_payment import _make_future_availability, _make_test_doctor, _make_test_patient, client, db  # noqa: F401
from tests.test_phase02_booking_payment import (
    _admin, _auth, _cancelled_with_request, _hold, _pay_confirmed, _payment, _schema,
)
from tests.test_phase05_stripe_webhooks import _event, _post, _signed

quiet_client = TestClient(app, raise_server_exceptions=False)


def _intent(payment, status, amount_minor=None, **extra):
    obj = MagicMock()
    obj.id = payment["stripePaymentIntentId"]
    obj.status = status
    obj.amount = amount_minor if amount_minor is not None else int(round(payment["amount"] * 100))
    obj.amount_received = obj.amount if status == "succeeded" else 0
    obj.currency = payment["currency"]
    obj.livemode = False
    obj.client_secret = f"{obj.id}_secret_a03"
    obj.last_payment_error = extra.get("last_payment_error")
    return obj


def _fresh_hold(db, suffix, days=6, start="09:00"):
    patient, doctor = _make_test_patient(db, suffix), _make_test_doctor(db, suffix + "Doc")
    appt = _hold(db, patient, doctor, _make_future_availability(db, doctor, days), start)
    payment = _payment(db, appt.id, patient, doctor, amount=doctor["consultationFee"])
    return patient, doctor, appt, payment


# =============================================================================================== webhooks
def test_a03_bug001_inflight_redelivery_is_not_acknowledged_as_processed(db):
    """A redelivery while the first delivery is still processing must not get a 2xx (Stripe would stop retrying)."""
    patient, doctor, appt, payment = _fresh_hold(db, "A03W1")
    event = _event("payment_intent.succeeded", {"id": payment["stripePaymentIntentId"], "object": "payment_intent",
                                                "amount_received": int(payment["amount"] * 100),
                                                "currency": "lkr", "livemode": False})
    db[hooks.EVENTS].insert_one({"_id": event["id"], "type": event["type"], "status": "processing",
                                 "receivedAt": utc_now(), "attempts": 1})
    res = _post(event)
    assert res.status_code == 409, res.text
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] != "CONFIRMED"


def test_a03_bug001_event_whose_processing_crashed_is_processed_on_the_next_delivery(db):
    patient, doctor, appt, payment = _fresh_hold(db, "A03W2")
    event = _event("payment_intent.succeeded", {"id": payment["stripePaymentIntentId"], "object": "payment_intent",
                                                "amount_received": int(payment["amount"] * 100),
                                                "currency": "lkr", "livemode": False})
    from app.services.payment_service import PaymentService
    real = PaymentService._dispatch_event
    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database write interrupted")
        return await real(*args, **kwargs)

    body, headers = _signed(event)
    with patch.object(PaymentService, "_dispatch_event", side_effect=flaky):
        first = quiet_client.post("/api/payments/webhook", content=body, headers=headers)
        assert first.status_code == 500                       # Stripe will redeliver
        second = quiet_client.post("/api/payments/webhook", content=body, headers=headers)
    assert second.status_code == 200 and second.json()["status"] == "success", second.text
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] == "CONFIRMED"
    logged = db[hooks.EVENTS].find_one({"_id": event["id"]})
    assert logged["status"] == "processed" and logged["attempts"] == 2
    assert _post(event).json()["status"] == "already_processed"   # a later redelivery is a duplicate


def test_a03_bug003_failed_event_delivered_after_success_sends_no_failure_notice(db):
    patient, doctor = _make_test_patient(db, "A03W3"), _make_test_doctor(db, "A03W3Doc")
    appt, payment = _pay_confirmed(db, patient, doctor, _make_future_availability(db, doctor, 6))
    res = _post(_event("payment_intent.payment_failed", {
        "id": payment["stripePaymentIntentId"], "object": "payment_intent",
        "last_payment_error": {"message": "Your card was declined."}}))
    assert res.status_code == 200 and res.json()["status"] == "ignored_out_of_order"
    assert db["notifications"].count_documents({"recipientUserId": patient["id"], "type": "PAYMENT_FAILED"}) == 0
    stored = db["appointments"].find_one({"_id": ObjectId(appt.id)})
    assert stored["status"] == "CONFIRMED" and stored["paymentStatus"] == "PAID"


def test_a03_bug002_real_failed_event_is_recorded_once(db):
    patient, doctor, appt, payment = _fresh_hold(db, "A03W4")
    failed = _event("payment_intent.payment_failed", {
        "id": payment["stripePaymentIntentId"], "object": "payment_intent",
        "last_payment_error": {"message": "Your card was declined."}})
    assert _post(failed).json()["status"] == "failed_recorded"
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "FAILED"
    assert db["notifications"].count_documents({"recipientUserId": patient["id"], "type": "PAYMENT_FAILED"}) == 1


# =============================================================================================== status refresh
def test_a03_bug004_status_refresh_after_recorded_decline_confirms_a_later_success(db):
    """Decline recorded (webhook), patient pays with another card in the same sheet, the success webhook is lost."""
    patient, doctor, appt, payment = _fresh_hold(db, "A03S1")
    db["payments"].update_one({"_id": payment["_id"]}, {"$set": {"status": "FAILED", "failureReason": "declined"}})
    with patch("stripe.PaymentIntent.retrieve", return_value=_intent(payment, "succeeded")):
        res = client.get(f"/api/payments/{payment['_id']}/status", headers=_auth(patient))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["paymentStatus"] == "SUCCEEDED" and body["appointmentStatus"] == "CONFIRMED", body


def test_a03_bug004_status_refresh_never_overwrites_a_payment_settled_meanwhile(db):
    patient, doctor, appt, payment = _fresh_hold(db, "A03S2")
    declined = _intent(payment, "requires_payment_method", last_payment_error=MagicMock(message="declined"))

    def retrieve_while_webhook_settles(_intent_id, *a, **k):
        from app.services.payment_service import settle_legacy_payment
        settle_legacy_payment(db, db["payments"].find_one({"_id": payment["_id"]}),
                              {"id": payment["stripePaymentIntentId"], "amount_received": int(payment["amount"] * 100),
                               "currency": "lkr", "livemode": False}, utc_now())
        return declined   # the status call read Stripe a moment before the retry succeeded

    with patch("stripe.PaymentIntent.retrieve", side_effect=retrieve_while_webhook_settles):
        res = client.get(f"/api/payments/{payment['_id']}/status", headers=_auth(patient))
    assert res.status_code == 200
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "SUCCEEDED"
    assert res.json()["paymentStatus"] == "SUCCEEDED"


def test_a03_repeated_status_refresh_settles_once(db):
    patient, doctor, appt, payment = _fresh_hold(db, "A03S3")
    with patch("stripe.PaymentIntent.retrieve", return_value=_intent(payment, "succeeded")):
        for _ in range(4):
            assert client.get(f"/api/payments/{payment['_id']}/status", headers=_auth(patient)).status_code == 200
    assert db["notifications"].count_documents({"recipientUserId": patient["id"], "type": "PAYMENT_SUCCESS"}) == 1
    assert db["appointment_events"].count_documents({"appointmentId": appt.id, "event": "PAYMENT_CONFIRMED"}) == 1


# =============================================================================================== expired holds
def test_a03_bug005_expired_hold_sweep_makes_its_payment_intent_unpayable(db):
    patient, doctor, appt, payment = _fresh_hold(db, "A03H1")
    db["appointments"].update_one({"_id": ObjectId(appt.id)}, {"$set": {"holdExpiresAt": utc_now() - timedelta(seconds=5)}})
    cancelled = []

    def cancel(intent_id, **kwargs):
        cancelled.append(intent_id)
        return _intent(payment, "canceled")

    with patch("stripe.PaymentIntent.retrieve", return_value=_intent(payment, "requires_payment_method")), \
            patch("stripe.PaymentIntent.cancel", side_effect=cancel):
        assert AppointmentService.release_expired_holds(db) >= 1
        for _ in range(50):   # the shared test database holds other tests' released reservations too
            if not AppointmentService.stop_intents_of_released_holds(db)["checked"]:
                break
        assert AppointmentService.stop_intents_of_released_holds(db)["checked"] == 0   # nothing left to do
    assert cancelled.count(payment["stripePaymentIntentId"]) == 1
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "CANCELLED"
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] == "CANCELLED"


def test_a03_bug005_stripe_outage_keeps_release_and_retries_the_intent_later(db):
    patient, doctor, appt, payment = _fresh_hold(db, "A03H2")
    db["appointments"].update_one({"_id": ObjectId(appt.id)}, {"$set": {"holdExpiresAt": utc_now() - timedelta(seconds=5)}})
    with patch("stripe.PaymentIntent.retrieve", side_effect=stripe.error.APIConnectionError("down")):
        AppointmentService.release_expired_holds(db)
        AppointmentService.stop_intents_of_released_holds(db)
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] == "CANCELLED"   # expiry never waits
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "PENDING"
    with patch("stripe.PaymentIntent.retrieve", return_value=_intent(payment, "requires_payment_method")), \
            patch("stripe.PaymentIntent.cancel", return_value=_intent(payment, "canceled")):
        AppointmentService.stop_intents_of_released_holds(db)
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "CANCELLED"


def test_a03_bug005_intent_that_succeeded_after_expiry_goes_to_review_not_confirmation(db):
    patient, doctor, appt, payment = _fresh_hold(db, "A03H3")
    db["appointments"].update_one({"_id": ObjectId(appt.id)}, {"$set": {"holdExpiresAt": utc_now() - timedelta(seconds=5)}})
    with patch("stripe.PaymentIntent.retrieve", return_value=_intent(payment, "succeeded")):
        AppointmentService.release_expired_holds(db)
        AppointmentService.stop_intents_of_released_holds(db)
    stored = db["payments"].find_one({"_id": payment["_id"]})
    assert stored["status"] == "SUCCEEDED" and stored["reconciliationState"] == "REVIEW_REQUIRED"
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] == "CANCELLED"


# =============================================================================================== refunds
def _uncertain_refund(db, suffix):
    admin = _admin(db)
    appt, payment, refund = _cancelled_with_request(db, suffix)
    seen = []

    def create(**kwargs):
        seen.append(kwargs)
        raise stripe.error.APIConnectionError("connection reset after the request was sent")

    with patch("stripe.Refund.create", side_effect=create), pytest.raises(HTTPException) as exc:
        RefundService.approve_refund(db, admin["id"], refund["refundId"])
    return admin, appt, payment, refund, seen, exc.value


def _sync_until_settled(db, refund, **doubles):
    """The shared test database can hold other processing refunds; sweep until this one has left processing."""
    for _ in range(20):
        hooks.sync_pending_refunds(db, **doubles)
        if db["refund_requests"].find_one({"_id": refund["_id"]})["status"] != "processing":
            return


def test_a03_bug007_refund_network_error_is_uncertain_not_failed(db):
    admin, appt, payment, refund, seen, exc = _uncertain_refund(db, "A03R1")
    assert exc.status_code == 502
    assert seen[0]["metadata"]["refundId"] == refund["refundId"]           # findable at Stripe later
    stored = db["refund_requests"].find_one({"_id": refund["_id"]})
    assert stored["status"] == "processing" and stored["stripeOutcome"] == "uncertain", stored


def test_a03_bug007_webhook_for_uncertain_refund_is_matched_by_metadata(db):
    admin, appt, payment, refund, seen, exc = _uncertain_refund(db, "A03R2")
    obj = {"id": f"re_a03_{uuid.uuid4().hex[:12]}", "object": "refund", "status": "succeeded",
           "amount": int(round(refund["policyEligibility"]["eligibleAmount"] * 100)), "currency": "lkr",
           "payment_intent": payment["stripePaymentIntentId"], "metadata": {"refundId": refund["refundId"]}}
    assert _post(_event("refund.created", obj)).json()["status"] == "refund_succeeded"
    stored = db["refund_requests"].find_one({"_id": refund["_id"]})
    assert stored["status"] == "succeeded" and stored["stripeRefundId"] == obj["id"]


def test_a03_bug007_sync_finds_uncertain_refund_without_creating_another(db):
    admin, appt, payment, refund, seen, exc = _uncertain_refund(db, "A03R3")
    db["refund_requests"].update_one({"_id": refund["_id"]}, {"$set": {"updatedAt": utc_now() - timedelta(minutes=10)}})
    amount = int(round(refund["policyEligibility"]["eligibleAmount"] * 100))
    found = {"id": "re_a03_found", "object": "refund", "status": "succeeded", "amount": amount, "currency": "lkr",
             "payment_intent": payment["stripePaymentIntentId"], "metadata": {"refundId": refund["refundId"]}}
    other = {**found, "id": "re_a03_other", "metadata": {"refundId": "REF-SOMEONEELSE"}}
    with patch("stripe.Refund.create") as create:
        mine = payment["stripePaymentIntentId"]
        _sync_until_settled(db, refund, retrieve=MagicMock(), list_refunds=lambda pi: [other, found] if pi == mine else [])
        assert not create.called
    stored = db["refund_requests"].find_one({"_id": refund["_id"]})
    assert stored["status"] == "succeeded" and stored["stripeRefundId"] == "re_a03_found"
    assert db["payments"].find_one({"_id": payment["_id"]})["refundRequestIds"].count(refund["refundId"]) == 1


def test_a03_bug007_approval_retry_while_uncertain_never_sends_a_second_refund(db):
    admin, appt, payment, refund, seen, exc = _uncertain_refund(db, "A03R4")
    with patch("stripe.Refund.create") as create, pytest.raises(HTTPException) as again:
        RefundService.approve_refund(db, admin["id"], refund["refundId"])
    assert again.value.status_code == 409 and not create.called


def test_a03_bug007_definite_stripe_rejection_is_failed_and_retryable(db):
    admin = _admin(db)
    appt, payment, refund = _cancelled_with_request(db, "A03R5")
    with patch("stripe.Refund.create", side_effect=stripe.error.InvalidRequestError("charge disputed", "charge")), \
            pytest.raises(HTTPException):
        RefundService.approve_refund(db, admin["id"], refund["refundId"])
    assert db["refund_requests"].find_one({"_id": refund["_id"]})["status"] == "failed"


def test_a03_bug007_sync_marks_a_refund_stripe_never_created_as_failed_for_re_approval(db):
    admin, appt, payment, refund, seen, exc = _uncertain_refund(db, "A03R6")
    db["refund_requests"].update_one({"_id": refund["_id"]}, {"$set": {"updatedAt": utc_now() - timedelta(minutes=10)}})
    _sync_until_settled(db, refund, retrieve=MagicMock(), list_refunds=lambda pi: [])
    stored = db["refund_requests"].find_one({"_id": refund["_id"]})
    assert stored["status"] == "failed" and stored["stripeOutcome"] == "not_created"
    with patch("app.services.stripe_webhook_service._list_refunds_for_intent", return_value=[]), \
            patch("stripe.Refund.create", return_value=MagicMock(id="re_a03_second", status="succeeded")) as create:
        assert RefundService.approve_refund(db, admin["id"], refund["refundId"])["status"] == "succeeded"
    assert create.call_count == 1


def test_a03_bug007_stale_retry_adopts_the_refund_stripe_already_has(db):
    admin, appt, payment, refund, seen, exc = _uncertain_refund(db, "A03R7")
    db["refund_requests"].update_one({"_id": refund["_id"]}, {"$set": {"updatedAt": utc_now() - timedelta(minutes=10)}})
    found = stripe.Refund.construct_from({"id": "re_a03_adopted", "object": "refund", "status": "succeeded",
                                          "metadata": {"refundId": refund["refundId"]}}, "sk_test_unused")
    with patch("app.services.stripe_webhook_service._list_refunds_for_intent", return_value=[found]), \
            patch("stripe.Refund.create") as create:
        assert RefundService.approve_refund(db, admin["id"], refund["refundId"])["status"] == "succeeded"
    assert not create.called
    assert db["payments"].find_one({"_id": payment["_id"]})["refundRequestIds"].count(refund["refundId"]) == 1


# ------------------------------------------------------------------------------- A03-BUG-006 status vocabulary
def _pending_real_refund(db, suffix):
    """A refund approved through the real service while Stripe reports it pending (asynchronous refund)."""
    admin = _admin(db)
    appt, payment, refund = _cancelled_with_request(db, suffix)
    re_id = f"re_a03_{uuid.uuid4().hex[:12]}"
    with patch("stripe.Refund.create", return_value=MagicMock(id=re_id, status="pending")):
        assert RefundService.approve_refund(db, admin["id"], refund["refundId"])["status"] == "processing"
    request = db["refund_requests"].find_one({"_id": refund["_id"]})
    return admin, appt, db["payments"].find_one({"_id": payment["_id"]}), request, re_id


def test_a03_bug006_webhook_completes_a_real_pending_refund_in_the_service_vocabulary(db):
    admin, appt, payment, request, re_id = _pending_real_refund(db, "A03V1")
    amount = int(round(request["approvedAmount"] * 100))
    obj = {"id": re_id, "object": "refund", "status": "succeeded", "amount": amount, "currency": payment["currency"],
           "payment_intent": payment["stripePaymentIntentId"]}
    assert _post(_event("refund.updated", obj)).json()["status"] == "refund_succeeded"
    stored = db["refund_requests"].find_one({"_id": request["_id"]})
    assert stored["status"] == "succeeded"
    listed = RefundService.list_refund_requests(db, status_filter="succeeded", page_size=200)["items"]
    assert any(item["refundId"] == request["refundId"] for item in listed)        # visible to the admin filter
    with pytest.raises(HTTPException):                                            # and blocks a second request
        RefundService.create_refund_request(db, payment["patientUserId"], appt.id, "again")
    assert _post(_event("refund.updated", {**obj, "status": "pending"})).json()["status"] == "ignored_out_of_order"


def test_a03_bug006_polling_fallback_finds_a_real_pending_refund(db):
    admin, appt, payment, request, re_id = _pending_real_refund(db, "A03V2")
    db["refund_requests"].update_one({"_id": request["_id"]}, {"$set": {"updatedAt": utc_now() - timedelta(minutes=10)}})
    amount = int(round(request["approvedAmount"] * 100))
    retrieve = MagicMock(return_value={"id": re_id, "status": "failed", "amount": amount, "currency": "lkr",
                                       "payment_intent": payment["stripePaymentIntentId"],
                                       "failure_reason": "expired_or_canceled_card"})
    hooks.sync_pending_refunds(db, retrieve=retrieve, list_refunds=lambda pi: [])
    retrieve.assert_any_call(re_id)
    assert db["refund_requests"].find_one({"_id": request["_id"]})["status"] == "failed"


# ------------------------------------------------------------------------------- A03-BUG-009 review visibility
def test_a03_bug009_refund_failed_after_success_is_visible_to_admins(db):
    admin, appt, payment, request, re_id = _pending_real_refund(db, "A03V3")
    amount = int(round(request["approvedAmount"] * 100))
    obj = {"id": re_id, "object": "refund", "amount": amount, "currency": payment["currency"],
           "payment_intent": payment["stripePaymentIntentId"]}
    assert _post(_event("refund.updated", {**obj, "status": "succeeded"})).json()["status"] == "refund_succeeded"
    assert _post(_event("refund.failed", {**obj, "status": "failed"})).json()["status"] == "flagged_for_review"
    detail = client.get(f"/api/admin/workflow/refunds/{request['refundId']}", headers=_auth(admin))
    assert detail.status_code == 200 and detail.json()["requiresReview"] is True
    assert detail.json()["stripeRefundStatus"] == "failed"
    report = client.post("/api/admin/workflow/reconciliation/run", headers=_auth(admin))
    assert report.status_code == 200, report.text
    found = report.json()["discrepancies"]
    mine = [d for d in found if d.get("refundId") == request["refundId"]]
    assert [d["type"] for d in mine] == ["REFUND_FAILED_AFTER_SUCCESS"]


def test_a03_bug009_uncertain_refund_is_listed_as_being_checked(db):
    admin, appt, payment, refund, seen, exc = _uncertain_refund(db, "A03V4")
    from app.services.payment_monitoring_service import PaymentMonitoringService
    mine = [d for d in PaymentMonitoringService.run_reconciliation_checks(db)["discrepancies"]
            if d.get("refundId") == refund["refundId"]]
    assert [d["type"] for d in mine] == ["REFUND_OUTCOME_UNCERTAIN"]
    listed = RefundService.list_refund_requests(db, status_filter="processing", page_size=500)["items"]
    assert next(i for i in listed if i["refundId"] == refund["refundId"])["stripeOutcome"] == "uncertain"
