"""Phase 02 regression tests: booking, reservation holds, payment integrity, cancellation, refunds, rescheduling.

All tests run against the isolated local MongoDB test database (real unique indexes and atomic updates).
Stripe network calls are mocked here; real Stripe test-mode runs are in docs/uat/phase-02 (live UAT scripts).
IDs: BUG-055, BUG-058, BUG-059, BUG-060, BUG-061, BUG-063, P-05n..P-05r and P02-Nxx (see the Phase 02 reports).
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import uuid

from bson import ObjectId
from fastapi import HTTPException
import pytest

from app.models.appointment import utc_now
from app.models.user import AccountStatus, UserRole
from app.schemas.appointment import CreateAppointmentRequest, RescheduleAppointmentRequest
from app.schemas.user import UserResponseSchema
from app.services.appointment_service import AppointmentService, SL_TIMEZONE
from app.services.payment_service import settle_legacy_payment
from app.services.refund_service import RefundService
from app.utils.security import create_access_token, hash_password
from tests.test_payment import (
    _make_future_availability, _make_test_doctor, _make_test_patient, client, db,  # noqa: F401  (db fixture)
)


def _schema(user):
    return UserResponseSchema(id=user["id"], fullName=user["fullName"], email=user["email"], role=user["role"],
                              emailVerified=True, accountStatus=AccountStatus.ACTIVE.value,
                              createdAt=user["createdAt"], authProviders=["LOCAL"])


def _auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


def _admin(db):
    oid = ObjectId()
    db["users"].insert_one({"_id": oid, "fullName": "P02 Admin", "email": f"p02admin_{oid}@mediconnect.lk",
                            "passwordHash": hash_password("Secret123!"), "role": UserRole.ADMIN.value,
                            "emailVerified": True, "accountStatus": "ACTIVE", "authProviders": ["LOCAL"],
                            "createdAt": utc_now(), "updatedAt": utc_now()})
    return {"id": str(oid), "token": create_access_token(str(oid), role=UserRole.ADMIN.value)}


def _hold(db, patient, doctor, avail, start="09:00"):
    return asyncio.run(AppointmentService.create_appointment(db, _schema(patient), CreateAppointmentRequest(
        doctorId=doctor["doctorId"], availabilityId=avail["id"], date=avail["date"], startTime=start,
    ))).appointment


def _payment(db, appt_id, patient, doctor, amount=2500.0, status="PENDING", intent=None, currency="lkr"):
    intent = intent or f"pi_p02_{uuid.uuid4().hex[:16]}"
    res = db["payments"].insert_one({
        "appointmentId": appt_id, "patientUserId": patient["id"], "doctorUserId": doctor["id"],
        "stripePaymentIntentId": intent, "amount": amount, "currency": currency, "status": status,
        "createdAt": utc_now(), "updatedAt": utc_now(),
    })
    return db["payments"].find_one({"_id": res.inserted_id})


def _pay_confirmed(db, patient, doctor, avail, start="09:00"):
    appt = _hold(db, patient, doctor, avail, start)
    payment = _payment(db, appt.id, patient, doctor, amount=doctor["consultationFee"])
    intent = {"id": payment["stripePaymentIntentId"], "amount_received": int(doctor["consultationFee"] * 100),
              "currency": "lkr", "livemode": False}
    assert settle_legacy_payment(db, payment, intent, utc_now()) == "success"
    return appt, db["payments"].find_one({"_id": payment["_id"]})


# ---------------------------------------------------------------------------------------------- BUG-060 / 058 / 059
def test_bug060_appointment_detail_returns_200_for_patient_doctor_and_admin(db):
    patient, doctor = _make_test_patient(db, "P02Det"), _make_test_doctor(db, "P02Det", fee=3200.0)
    appt, payment = _pay_confirmed(db, patient, doctor, _make_future_availability(db, doctor, 6))
    for who in (patient, doctor, _admin(db)):
        res = client.get(f"/api/appointments/{appt.id}", headers=_auth(who))
        assert res.status_code == 200, res.text  # was 500 (TypeError) for every requester
        body = res.json()
        assert body["id"] == appt.id and body["bookingReference"] == appt.id
        assert body["consultationFee"] == 3200.0 and body["consultationFeeAtBooking"] == 3200.0
        assert body["paymentStatus"] == "PAID" and body["amountPaid"] == 3200.0 and body["paidAt"]
        assert body["visitType"] == "IN_PERSON" and body["currency"] == "lkr"
    other = _make_test_patient(db, "P02DetOther")
    assert client.get(f"/api/appointments/{appt.id}", headers=_auth(other)).status_code == 403
    assert client.get(f"/api/appointments/{ObjectId()}", headers=_auth(patient)).status_code == 404


def test_bug058_fee_is_historical_and_unpaid_shows_no_amount_paid(db):
    patient, doctor = _make_test_patient(db, "P02Hist"), _make_test_doctor(db, "P02Hist", fee=2000.0)
    avail = _make_future_availability(db, doctor, 6)
    appt, _ = _pay_confirmed(db, patient, doctor, avail)
    db["doctor_profiles"].update_one({"_id": ObjectId(doctor["profileId"])}, {"$set": {"consultationFee": 9999.0}})
    body = client.get(f"/api/appointments/{appt.id}", headers=_auth(doctor)).json()
    assert body["consultationFee"] == 2000.0 and body["amountPaid"] == 2000.0  # not the new profile fee
    unpaid = _hold(db, _make_test_patient(db, "P02Hist2"), doctor, avail, "10:00")
    body = client.get(f"/api/appointments/{unpaid.id}", headers=_auth(doctor)).json()
    assert body["amountPaid"] is None and body["paymentStatus"] == "UNPAID"
    listed = client.get("/api/appointments/me", headers=_auth(patient)).json()["items"]
    assert listed[0]["amountPaid"] == 2000.0 and listed[0]["bookingReference"] == appt.id


def test_appointment_without_fee_is_not_given_a_default_amount(db):
    patient, doctor = _make_test_patient(db, "P02NoFee"), _make_test_doctor(db, "P02NoFee")
    oid = ObjectId()
    db["appointments"].insert_one({"_id": oid, "patientUserId": patient["id"], "doctorUserId": doctor["id"],
                                   "doctorProfileId": doctor["profileId"], "appointmentDate": "2030-01-02",
                                   "startTime": "09:00", "endTime": "09:30", "status": "CANCELLED",
                                   "createdAt": utc_now(), "updatedAt": utc_now()})
    body = client.get(f"/api/appointments/{oid}", headers=_auth(patient)).json()
    assert body["consultationFee"] is None and body["amountPaid"] is None


# ---------------------------------------------------------------------------------------------- BUG-061 / 055
def _conversation(patient):
    res = client.post("/api/ai/conversations", json={}, headers=_auth(patient))
    assert res.status_code == 201, res.text
    return res.json().get("data", res.json())["id"]


def _say(patient, cid, text):
    res = client.post(f"/api/ai/conversations/{cid}/messages", json={"message": text, "requestId": uuid.uuid4().hex[:20]},
                      headers=_auth(patient))
    assert res.status_code == 200, res.text
    return res.json().get("data", res.json())


def _spoken(date_str):
    day = datetime.fromisoformat(date_str)
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def test_bug061_taken_time_offers_same_doctor_same_date_alternatives(db):
    patient, other = _make_test_patient(db, "P02Alt"), _make_test_patient(db, "P02AltBlock")
    doctor = _make_test_doctor(db, "P02AltDoc")
    rival = _make_test_doctor(db, "P02AltRival")
    avail = _make_future_availability(db, doctor, 7)
    _make_future_availability(db, rival, 7)  # the rival is free at 10:00 and must not be swapped in
    _hold(db, other, doctor, avail, "10:00")
    cid = _conversation(patient)
    res = client.post(f"/api/ai/booking/sessions/{cid}/select-doctor", json={"doctorId": doctor["doctorId"]},
                      headers=_auth(patient))
    assert res.status_code == 200
    session = _say(patient, cid, f"Book {_spoken(avail['date'])} at 10:00")
    meta = session["messages"][-1]["metadata"]
    assert meta["type"] == "slot_unavailable_alternatives"
    assert meta["doctorId"] == doctor["doctorId"] and meta["requestedDate"] == avail["date"]
    assert session["selectedDoctor"]["doctorId"] == doctor["doctorId"]
    assert session["bookingSummary"] is None
    times = [slot["startTime"] for slot in session["candidateSlots"]]
    assert times[:2] == ["09:30", "10:30"] and "10:00" not in times
    assert {slot["date"] for slot in session["candidateSlots"]} == {avail["date"]}
    assert "not available at 10:00" in session["messages"][-1]["content"]


def test_bug061_wrong_date_fixed_free_time_becomes_proposal_on_requested_date(db):
    patient, doctor = _make_test_patient(db, "P02Date"), _make_test_doctor(db, "P02DateDoc")
    _make_future_availability(db, doctor, 3)  # an earlier date with 10:00 open (was wrongly chosen before)
    later = _make_future_availability(db, doctor, 8)
    cid = _conversation(patient)
    client.post(f"/api/ai/booking/sessions/{cid}/select-doctor", json={"doctorId": doctor["doctorId"]},
                headers=_auth(patient))
    session = _say(patient, cid, f"Book {_spoken(later['date'])} at 10:00")
    summary = session["bookingSummary"]
    assert summary["appointmentDate"] == later["date"] and summary["startTime"] == "10:00"
    assert summary["proposalId"] and summary["selectionReason"] == "Selected by you."


def test_bug061_no_openings_on_date_offers_next_date_for_same_doctor(db):
    patient, doctor = _make_test_patient(db, "P02Next"), _make_test_doctor(db, "P02NextDoc")
    nxt = _make_future_availability(db, doctor, 9)
    empty_day = (datetime.fromisoformat(nxt["date"]) - timedelta(days=1)).date().isoformat()
    cid = _conversation(patient)
    client.post(f"/api/ai/booking/sessions/{cid}/select-doctor", json={"doctorId": doctor["doctorId"]},
                headers=_auth(patient))
    session = _say(patient, cid, f"Book {_spoken(empty_day)} at 10:00")
    meta = session["messages"][-1]["metadata"]
    assert meta["type"] == "slot_unavailable_alternatives" and meta["alternativeDate"] == nxt["date"]
    assert session["candidateSlots"][0]["startTime"] == "10:00"
    assert session["selectedDoctor"]["doctorId"] == doctor["doctorId"]


def test_bug055_manual_slot_is_not_called_closest(db):
    patient, doctor = _make_test_patient(db, "P02Man"), _make_test_doctor(db, "P02ManDoc")
    avail = _make_future_availability(db, doctor, 7)
    cid = _conversation(patient)
    client.post(f"/api/ai/booking/sessions/{cid}/select-doctor", json={"doctorId": doctor["doctorId"]},
                headers=_auth(patient))
    db["booking_sessions"].update_one({"_id": ObjectId(cid)}, {"$set": {"preferences.requestedTime": "10:30"}})
    day = client.get(f"/api/doctors/{doctor['doctorId']}/availability?date={avail['date']}", headers=_auth(patient)).json()
    pick = next(slot for slot in day["slots"] if slot["startTime"] == "11:00")
    res = client.post(f"/api/ai/booking/sessions/{cid}/select-slot",
                      json={"availabilityId": pick["availabilityId"], "date": avail["date"], "startTime": "11:00",
                            "prepareProposal": True}, headers=_auth(patient))
    assert res.status_code == 200, res.text
    assert res.json()["bookingSummary"]["selectionReason"] == "Selected by you."


# ---------------------------------------------------------------------------------------------- BUG-063 hold release
def test_bug063_release_hold_cancels_intent_and_frees_slot(db):
    patient, doctor = _make_test_patient(db, "P02Rel"), _make_test_doctor(db, "P02RelDoc")
    avail = _make_future_availability(db, doctor, 6)
    appt = _hold(db, patient, doctor, avail)
    payment = _payment(db, appt.id, patient, doctor)
    with patch("stripe.PaymentIntent.retrieve", return_value=MagicMock(status="requires_payment_method")), \
            patch("stripe.PaymentIntent.cancel", return_value=MagicMock(status="canceled")) as cancel:
        res = client.post(f"/api/appointments/{appt.id}/release-hold", json={}, headers=_auth(patient))
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCELLED" and cancel.call_count == 1
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "CANCELLED"
    day = client.get(f"/api/doctors/{doctor['doctorId']}/availability?date={avail['date']}", headers=_auth(patient)).json()
    assert "09:00" in [slot["startTime"] for slot in day["slots"]]
    event = db["appointment_events"].find_one({"appointmentId": appt.id, "event": "HOLD_RELEASED"})
    assert event and event["actorRole"] == "PATIENT"
    again = client.post(f"/api/appointments/{appt.id}/release-hold", json={}, headers=_auth(patient))
    assert again.status_code == 200 and again.json()["status"] == "CANCELLED"  # idempotent


def test_bug063_release_loses_race_to_succeeded_payment(db):
    patient, doctor = _make_test_patient(db, "P02Race"), _make_test_doctor(db, "P02RaceDoc")
    appt = _hold(db, patient, doctor, _make_future_availability(db, doctor, 6))
    payment = _payment(db, appt.id, patient, doctor)
    paid = {"id": payment["stripePaymentIntentId"], "status": "succeeded", "amount_received": 250000,
            "currency": "lkr", "livemode": False}
    with patch("stripe.PaymentIntent.retrieve", return_value=MagicMock(**paid)), \
            patch("stripe.PaymentIntent.cancel") as cancel:
        res = client.post(f"/api/appointments/{appt.id}/release-hold", json={}, headers=_auth(patient))
    assert res.status_code == 409 and cancel.call_count == 0
    stored = db["appointments"].find_one({"_id": ObjectId(appt.id)})
    assert stored["status"] == "CONFIRMED" and stored["paymentStatus"] == "PAID"


def test_bug063_processing_payment_and_paid_appointment_are_not_released(db):
    patient, doctor = _make_test_patient(db, "P02Proc"), _make_test_doctor(db, "P02ProcDoc")
    avail = _make_future_availability(db, doctor, 6)
    appt = _hold(db, patient, doctor, avail)
    _payment(db, appt.id, patient, doctor)
    with patch("stripe.PaymentIntent.retrieve", return_value=MagicMock(status="processing")):
        assert client.post(f"/api/appointments/{appt.id}/release-hold", json={}, headers=_auth(patient)).status_code == 409
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] == "PENDING"
    confirmed, _ = _pay_confirmed(db, _make_test_patient(db, "P02Proc2"), doctor, avail, "10:00")
    owner = db["appointments"].find_one({"_id": ObjectId(confirmed.id)})["patientUserId"]
    owner_user = db["users"].find_one({"_id": ObjectId(owner)})
    token = create_access_token(owner, role="PATIENT")
    assert client.post(f"/api/appointments/{confirmed.id}/release-hold", json={},
                       headers={"Authorization": f"Bearer {token}"}).status_code == 409
    assert owner_user is not None
    intruder = _make_test_patient(db, "P02ProcIntruder")
    assert client.post(f"/api/appointments/{appt.id}/release-hold", json={}, headers=_auth(intruder)).status_code == 403


def test_bug063_ai_session_cancel_releases_hold_without_payment(db):
    patient, doctor = _make_test_patient(db, "P02Sess"), _make_test_doctor(db, "P02SessDoc")
    appt = _hold(db, patient, doctor, _make_future_availability(db, doctor, 6))
    cid = _conversation(patient)
    db["booking_sessions"].update_one({"_id": ObjectId(cid)}, {"$set": {"appointmentId": appt.id, "state": "AWAITING_PAYMENT",
                                                                     "holdExpiresAt": utc_now() + timedelta(minutes=9)}})
    res = client.post(f"/api/ai/booking/sessions/{cid}/cancel", headers=_auth(patient))
    assert res.status_code == 200, res.text
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] == "CANCELLED"
    assert "No payment was taken" in res.json()["messages"][-1]["content"]


# ---------------------------------------------------------------------------------------------- expiry sweep
def test_expired_holds_released_once_by_concurrent_sweeps(db):
    patient, doctor = _make_test_patient(db, "P02Exp"), _make_test_doctor(db, "P02ExpDoc")
    avail = _make_future_availability(db, doctor, 6)
    ids = [_hold(db, patient, doctor, avail, start).id for start in ("09:00", "09:30", "10:00")]
    paid, _ = _pay_confirmed(db, _make_test_patient(db, "P02ExpPaid"), doctor, avail, "10:30")
    db["appointments"].update_many({"_id": {"$in": [ObjectId(i) for i in ids + [paid.id]]}},
                                   {"$set": {"holdExpiresAt": utc_now() - timedelta(minutes=1)}})
    with ThreadPoolExecutor(max_workers=4) as pool:
        released = sum(pool.map(lambda _: AppointmentService.release_expired_holds(db), range(4)))
    assert released >= 3
    for i in ids:
        doc = db["appointments"].find_one({"_id": ObjectId(i)})
        assert doc["status"] == "CANCELLED" and doc["cancelledBy"] == "SYSTEM"
        assert db["appointment_events"].count_documents({"appointmentId": i, "event": "HOLD_EXPIRED"}) == 1
    assert db["appointments"].find_one({"_id": ObjectId(paid.id)})["status"] == "CONFIRMED"


# ---------------------------------------------------------------------------------------------- P-05n concurrency
def test_p05n_concurrent_reservations_one_winner_repeated(db):
    doctor = _make_test_doctor(db, "P02Conc")
    avail = _make_future_availability(db, doctor, 6)
    for round_index, start in enumerate(("09:00", "09:30", "10:00", "10:30", "11:00")):
        patients = [_make_test_patient(db, f"P02Conc{round_index}_{i}") for i in range(8)]

        def attempt(p):
            try:
                _hold(db, p, doctor, avail, start)
                return "ok"
            except HTTPException as exc:
                return exc.status_code

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(attempt, patients))
        assert outcomes.count("ok") == 1, outcomes
        assert all(code == 409 for code in outcomes if code != "ok")
        active = db["appointments"].count_documents({"doctorUserId": doctor["id"], "appointmentDate": avail["date"],
                                                     "startTime": start, "status": {"$in": ["HOLD", "PENDING", "CONFIRMED"]}})
        assert active == 1


# ---------------------------------------------------------------------------------------------- Stripe settlement
@pytest.mark.parametrize("change,reason", [
    ({"amount_received": 100}, "amount_currency_or_mode_mismatch"),
    ({"currency": "usd"}, "amount_currency_or_mode_mismatch"),
    ({"livemode": True}, "amount_currency_or_mode_mismatch"),
], ids=["amount", "currency", "livemode"])
def test_payment_mismatch_never_confirms(db, change, reason):
    patient, doctor = _make_test_patient(db, "P02Mis"), _make_test_doctor(db, "P02MisDoc")
    appt = _hold(db, patient, doctor, _make_future_availability(db, doctor, 6))
    payment = _payment(db, appt.id, patient, doctor)
    intent = {"id": payment["stripePaymentIntentId"], "amount_received": 250000, "currency": "lkr", "livemode": False,
              **change}
    assert settle_legacy_payment(db, payment, intent, utc_now()) == "reconciliation_required"
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] == "PENDING"
    stored = db["payments"].find_one({"_id": payment["_id"]})
    assert stored["reconciliationState"] == "REVIEW_REQUIRED" and stored["reconciliationReason"] == reason


def test_payment_for_released_or_expired_hold_is_not_resurrected(db):
    patient, doctor = _make_test_patient(db, "P02Res"), _make_test_doctor(db, "P02ResDoc")
    avail = _make_future_availability(db, doctor, 6)
    released = _hold(db, patient, doctor, avail)
    db["appointments"].update_one({"_id": ObjectId(released.id)}, {"$set": {"status": "CANCELLED"}})
    expired = _hold(db, patient, doctor, avail, "09:30")
    db["appointments"].update_one({"_id": ObjectId(expired.id)}, {"$set": {"holdExpiresAt": utc_now() - timedelta(seconds=1)}})
    for appt in (released, expired):
        payment = _payment(db, appt.id, patient, doctor)
        intent = {"id": payment["stripePaymentIntentId"], "amount_received": 250000, "currency": "lkr"}
        assert settle_legacy_payment(db, payment, intent, utc_now()) == "reconciliation_required"
        assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["paymentStatus"] != "PAID"
        assert db["payments"].find_one({"_id": payment["_id"]})["reconciliationReason"] == "booking_unavailable"


def test_payment_ownership_mismatch_is_not_applied(db):
    patient, doctor = _make_test_patient(db, "P02Own"), _make_test_doctor(db, "P02OwnDoc")
    appt = _hold(db, patient, doctor, _make_future_availability(db, doctor, 6))
    stranger = _make_test_patient(db, "P02OwnStranger")
    payment = _payment(db, appt.id, stranger, doctor)
    intent = {"id": payment["stripePaymentIntentId"], "amount_received": 250000, "currency": "lkr"}
    assert settle_legacy_payment(db, payment, intent, utc_now()) == "reconciliation_required"
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] == "PENDING"


def test_out_of_order_failed_after_success_keeps_paid(db):
    from app.config.settings import settings
    patient, doctor = _make_test_patient(db, "P02Ooo"), _make_test_doctor(db, "P02OooDoc")
    appt, payment = _pay_confirmed(db, patient, doctor, _make_future_availability(db, doctor, 6))
    event = {"id": "evt_p02", "type": "payment_intent.payment_failed", "livemode": False,
             "data": {"object": {"id": payment["stripePaymentIntentId"], "last_payment_error": {"message": "late"}}}}
    with patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_p02"), \
            patch("stripe.Webhook.construct_event", return_value=event):
        assert client.post("/api/payments/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=x"}).status_code == 200
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "SUCCEEDED"
    stored = db["appointments"].find_one({"_id": ObjectId(appt.id)})
    assert stored["status"] == "CONFIRMED" and stored["paymentStatus"] == "PAID"


def test_livemode_event_is_ignored_on_test_key(db):
    from app.config.settings import settings
    event = {"id": "evt_live", "type": "payment_intent.succeeded", "livemode": True,
             "data": {"object": {"id": "pi_live_x", "amount_received": 1, "currency": "lkr"}}}
    with patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_p02"), \
            patch("stripe.Webhook.construct_event", return_value=event):
        res = client.post("/api/payments/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=x"})
    assert res.status_code == 200 and res.json() == {"status": "ignored", "reason": "livemode_mismatch"}


def test_intent_amount_uses_fee_stored_at_reservation(db):
    patient, doctor = _make_test_patient(db, "P02Fee"), _make_test_doctor(db, "P02FeeDoc", fee=2600.0)
    appt = _hold(db, patient, doctor, _make_future_availability(db, doctor, 6))
    db["doctor_profiles"].update_one({"_id": ObjectId(doctor["profileId"])}, {"$set": {"consultationFee": 1.0}})
    with patch("stripe.PaymentIntent.create", return_value=MagicMock(id=f"pi_fee_{uuid.uuid4().hex[:10]}",
                                                                  client_secret="cs_x")) as create:
        res = client.post("/api/payments/create-intent", json={"appointmentId": appt.id, "amount": 1},
                          headers=_auth(patient))
    assert res.status_code == 201, res.text
    assert create.call_args.kwargs["amount"] == 260000 and res.json()["amount"] == 260000


def test_doctor_cannot_confirm_unpaid_appointment(db):
    patient, doctor = _make_test_patient(db, "P02Unp"), _make_test_doctor(db, "P02UnpDoc")
    appt = _hold(db, patient, doctor, _make_future_availability(db, doctor, 6))
    res = client.put(f"/api/appointments/{appt.id}/status", json={"status": "CONFIRMED"}, headers=_auth(doctor))
    assert res.status_code == 409
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["status"] == "PENDING"


# ---------------------------------------------------------------------------------------------- P-05o / P-05p
def test_p05o_paid_cancellation_preview_then_cancel_opens_one_refund_request(db):
    patient, doctor = _make_test_patient(db, "P02Can"), _make_test_doctor(db, "P02CanDoc")
    appt, payment = _pay_confirmed(db, patient, doctor, _make_future_availability(db, doctor, 6))
    preview = client.get(f"/api/appointments/{appt.id}/cancellation-preview", headers=_auth(patient)).json()
    assert preview["isPaid"] and preview["requiresAdminApproval"]
    assert preview["refund"]["eligibleAmount"] == 2500.0 and preview["refund"]["penaltyAmount"] == 0.0
    res = client.post(f"/api/appointments/{appt.id}/cancel", json={"reason": "Travel"}, headers=_auth(patient))
    assert res.status_code == 200 and res.json()["status"] == "CANCELLED"
    assert res.json()["refundStatus"] == "requested"
    assert db["refund_requests"].count_documents({"appointmentId": appt.id}) == 1
    assert client.post(f"/api/appointments/{appt.id}/cancel", json={}, headers=_auth(patient)).status_code == 400
    assert db["refund_requests"].count_documents({"appointmentId": appt.id}) == 1
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "SUCCEEDED"  # no money moved yet


def test_p05p_refund_request_requires_cancelled_booking(db):
    patient, doctor = _make_test_patient(db, "P02RfC"), _make_test_doctor(db, "P02RfCDoc")
    appt, _ = _pay_confirmed(db, patient, doctor, _make_future_availability(db, doctor, 6))
    with pytest.raises(HTTPException) as exc:
        RefundService.create_refund_request(db, patient["id"], appt.id, "keep and refund")
    assert exc.value.status_code == 409


def _cancelled_with_request(db, suffix):
    patient, doctor = _make_test_patient(db, suffix), _make_test_doctor(db, suffix + "Doc")
    appt, payment = _pay_confirmed(db, patient, doctor, _make_future_availability(db, doctor, 6))
    asyncio.run(AppointmentService.cancel_patient_appointment(db, _schema(patient), appt.id, "test"))
    refund = db["refund_requests"].find_one({"appointmentId": appt.id})
    return appt, payment, refund


def test_p05p_refund_limits_and_honest_stripe_states(db):
    from app.config.settings import settings
    admin = _admin(db)
    _, payment, refund = _cancelled_with_request(db, "P02RfL")
    with pytest.raises(HTTPException) as exc:
        RefundService.approve_refund(db, admin["id"], refund["refundId"], approved_amount=2500.01)
    assert exc.value.status_code == 400
    with patch.object(settings, "STRIPE_SECRET_KEY", None), pytest.raises(HTTPException) as exc:
        RefundService.approve_refund(db, admin["id"], refund["refundId"])
    assert exc.value.status_code == 503
    assert db["refund_requests"].find_one({"_id": refund["_id"]})["stripeRefundId"] is None  # no fabricated refund
    with patch("stripe.Refund.create", return_value=MagicMock(id="re_p02_pending", status="pending")):
        result = RefundService.approve_refund(db, admin["id"], refund["refundId"])
    assert result["status"] == "processing"
    assert db["payments"].find_one({"_id": payment["_id"]})["status"] == "SUCCEEDED"


def test_p05p_partial_refund_and_concurrent_approval_single_stripe_call(db):
    admin = _admin(db)
    appt, payment, refund = _cancelled_with_request(db, "P02RfP")
    calls = []

    def stripe_refund(**kwargs):
        calls.append(kwargs)
        return MagicMock(id="re_p02_ok", status="succeeded")

    with patch("stripe.Refund.create", side_effect=stripe_refund):
        def approve(_):
            try:
                return RefundService.approve_refund(db, admin["id"], refund["refundId"], approved_amount=1000.0)["status"]
            except HTTPException as exc:
                return exc.status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(approve, range(4)))
    assert outcomes.count("succeeded") == 1 and len(calls) == 1 and calls[0]["amount"] == 100000
    stored = db["payments"].find_one({"_id": payment["_id"]})
    assert stored["status"] == "SUCCEEDED" and stored["refundedAmount"] == 1000.0  # partial: not marked REFUNDED
    assert db["appointments"].find_one({"_id": ObjectId(appt.id)})["paymentStatus"] == "PAID"
    with pytest.raises(HTTPException):
        RefundService.create_refund_request(db, stored["patientUserId"], appt.id, "again")  # already settled request


# ---------------------------------------------------------------------------------------------- P-05q reschedule
def test_p05q_reschedule_requires_real_slot_and_keeps_booking_on_failure(db):
    patient, doctor = _make_test_patient(db, "P02Rs"), _make_test_doctor(db, "P02RsDoc")
    avail = _make_future_availability(db, doctor, 6)
    appt, payment = _pay_confirmed(db, patient, doctor, avail)
    blocker = _pay_confirmed(db, _make_test_patient(db, "P02RsOther"), doctor, avail, "11:00")[0]
    p = _schema(patient)
    for bad_time in ("03:00", "11:00", "09:10"):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(AppointmentService.reschedule_appointment(db, p, appt.id, RescheduleAppointmentRequest(
                newDate=avail["date"], newStartTime=bad_time)))
        assert exc.value.status_code == 409
    unchanged = db["appointments"].find_one({"_id": ObjectId(appt.id)})
    assert unchanged["startTime"] == "09:00" and unchanged["status"] == "CONFIRMED"
    moved = asyncio.run(AppointmentService.reschedule_appointment(db, p, appt.id, RescheduleAppointmentRequest(
        newDate=avail["date"], newStartTime="10:30")))
    assert moved.startTime == "10:30" and moved.endTime == "11:00" and moved.appointmentVersion == 2
    stored = db["appointments"].find_one({"_id": ObjectId(appt.id)})
    assert stored["paymentStatus"] == "PAID" and stored["rescheduleHistory"][0]["fromStartTime"] == "09:00"
    assert db["payments"].count_documents({"appointmentId": appt.id}) == 1  # no second charge
    assert db["appointment_events"].count_documents({"appointmentId": appt.id, "event": "APPOINTMENT_RESCHEDULED"}) == 1
    assert blocker


def test_p02n06_booking_action_in_draft_chat_is_not_reused_as_new_chat(db):
    patient, doctor = _make_test_patient(db, "P02Draft"), _make_test_doctor(db, "P02DraftDoc")
    _make_future_availability(db, doctor, 6)
    cid = _conversation(patient)
    client.post(f"/api/ai/booking/sessions/{cid}/select-doctor", json={"doctorId": doctor["doctorId"]}, headers=_auth(patient))
    assert db["booking_sessions"].find_one({"_id": ObjectId(cid)})["draft"] is False
    assert _conversation(patient) != cid  # "New Chat" starts clean instead of reopening the booking
