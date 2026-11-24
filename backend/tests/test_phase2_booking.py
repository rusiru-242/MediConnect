"""Phase 2 acceptance checks against an isolated MongoDB database and mocked gateways."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.agents.nlp_parser import extract_date
from app.config.database import get_database
from app.main import app
from app.models.appointment import create_appointment_indexes, utc_now
from app.services import booking_notifications
from app.services.ai_booking_proposal import notification_entries, settle_ai_payment
from tests.test_ai_booking_agent import seeded_booking_env


@pytest.fixture(scope="module", autouse=True)
def isolated_test_database():
    from app.config.database import DatabaseManager
    original_db = DatabaseManager._db
    client = DatabaseManager.get_client()
    client.drop_database("mediconnect_phase2_test")
    test_db = client["mediconnect_phase2_test"]
    DatabaseManager._db = test_db
    assert get_database().name.startswith("mediconnect_phase2_test")
    yield test_db
    client.drop_database("mediconnect_phase2_test")
    DatabaseManager._db = original_db


@pytest.fixture
def booking_fixture(seeded_booking_env, monkeypatch):
    from app.agents.ai_provider import DeterministicNLPProvider
    from app.services.notification_service import NotificationService

    db = get_database()
    create_appointment_indexes(db)
    monkeypatch.setattr("app.agents.booking_agent.get_ai_provider", DeterministicNLPProvider)
    monkeypatch.setattr(NotificationService, "create_notification", Mock())
    seed = seeded_booking_env
    profile = ObjectId(seed["doc_profile_id"])
    db["doctor_profiles"].update_one({"_id": profile}, {"$set": {"specialty": "Neurology", "city": "Colombo"}})
    day = extract_date("December 5")
    db["doctor_availabilities"].insert_one({
        "doctorProfileId": str(profile), "doctorUserId": seed["doc_user_id"], "date": day,
        "startTime": "16:00", "endTime": "18:00", "isActive": True, "slotDurationMinutes": 30,
    })
    db["users"].update_one({"_id": ObjectId(seed["pat_a_id"])}, {"$set": {"phone": "0771234567"}})
    return db, seed, day


def headers(seed, who="patient_a"):
    return {"Authorization": f"Bearer {seed['token_' + who]}"}


def propose(client, patient, message="mata Colombo walin neurologist kenek December 5 4pm ta one"):
    chat = client.post("/api/ai/conversations", headers=patient, json={}).json()
    response = client.post(f"/api/ai/conversations/{chat['id']}/messages", headers=patient,
                           json={"message": message, "requestId": str(ObjectId())})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["state"] == "AWAITING_BOOKING_CONFIRMATION"
    assert result["appointmentId"] is None
    return result


def accept(client, patient, session, **extra):
    return client.post(
        f"/api/ai/booking/sessions/{session['id']}/confirm", headers=patient,
        json={"proposalId": session["bookingSummary"]["proposalId"], **extra},
    )


def test_paid_booking_visibility_notifications_and_replay(booking_fixture, monkeypatch):
    db, seed, day = booking_fixture
    client = TestClient(app)
    owner, other = headers(seed), headers(seed, "patient_b")
    session = propose(client, owner)
    proposal = session["bookingSummary"]
    assert (proposal["appointmentDate"], proposal["startTime"], proposal["city"]) == (day, "16:00", "Colombo")
    assert proposal["maskedPhone"] == "***4567"
    assert accept(client, other, session).status_code in {403, 404}
    assert accept(client, owner, session, proposalId=str(ObjectId())).status_code == 409
    response = accept(client, owner, session, smsConsent=True)
    assert response.status_code == 200, response.text
    booking = response.json()
    appointment_id = booking["appointmentId"]
    assert accept(client, owner, session).json()["appointmentId"] == appointment_id
    assert booking["bookingResult"]["status"] == "PENDING"

    stripe_id = "pi_" + str(ObjectId())
    monkeypatch.setattr("stripe.PaymentIntent.create", Mock(return_value=SimpleNamespace(
        id=stripe_id, client_secret="mock_client_secret",
    )))
    intent = client.post("/api/payments/create-intent", headers=owner, json={"appointmentId": appointment_id})
    assert intent.status_code == 201, intent.text
    event = {"type": "payment_intent.succeeded", "data": {"object": {
        "id": stripe_id, "amount_received": int(proposal["totalAmount"] * 100), "currency": proposal["currency"],
    }}}
    monkeypatch.setattr("stripe.Webhook.construct_event", Mock(return_value=event))
    for _ in range(2):
        webhook = client.post("/api/payments/webhook", headers={"Stripe-Signature": "mock"}, json={})
        assert webhook.status_code == 200, webhook.text
    appointment = db["appointments"].find_one({"_id": ObjectId(appointment_id)})
    assert appointment["bookingSource"] == "ai_agent"
    assert appointment["status"] == "CONFIRMED"
    assert appointment["stripePaymentIntentId"] == stripe_id
    assert appointment["doctorUserId"] == seed["doc_user_id"]

    email = Mock(return_value=True)
    sms = Mock(return_value=SimpleNamespace(status_code=201, ok=True, json=lambda: {"sid": "SM" + "a"*32, "status": "accepted"}))
    monkeypatch.setattr(booking_notifications.EmailService, "_send_email", email)
    monkeypatch.setattr(booking_notifications.settings, "SMTP_HOST", "fixture")
    monkeypatch.setattr(booking_notifications, "twilio_config", lambda: ("test", "token", "service"))
    monkeypatch.setattr(booking_notifications.requests, "post", sms)
    monkeypatch.setattr(booking_notifications.requests, "get", Mock())
    booking_notifications.run_confirmation_outbox(db)
    booking_notifications.run_confirmation_outbox(db)
    assert email.call_count == sms.call_count == 1
    restored = client.get(f"/api/ai/booking/sessions/{session['id']}", headers=owner).json()
    assert restored["state"] == "BOOKING_CONFIRMED"
    assert restored["bookingResult"]["notifications"]["email"] == "sent"
    assert restored["bookingResult"]["notifications"]["sms"] == "accepted"
    db["appointments"].update_one(
        {"_id": ObjectId(appointment_id)},
        {"$set": {"confirmationOutbox.sms.nextAttemptAt": utc_now()}},
    )
    monkeypatch.setattr(booking_notifications.requests, "get", Mock(return_value=SimpleNamespace(
        ok=True, json=lambda: {"status": "delivered"},
    )))
    booking_notifications.run_confirmation_outbox(db)
    assert db["appointments"].find_one({"_id": ObjectId(appointment_id)})["confirmationOutbox"]["sms"]["status"] == "delivered"

    doctor_list = client.get("/api/appointments/doctor/list", headers=headers(seed, "doctor"), params={"date": day})
    patient_list = client.get("/api/appointments/me", headers=owner)
    assert doctor_list.status_code == patient_list.status_code == 200
    assert appointment_id in {row["id"] for row in doctor_list.json()["items"]}
    assert appointment_id in {row["id"] for row in patient_list.json()["items"]}


def test_expired_payment_requires_reconciliation_without_confirmation(booking_fixture, monkeypatch):
    db, seed, day = booking_fixture
    appointment_id, payment_id = ObjectId(), ObjectId()
    stripe_id = "pi_" + str(ObjectId())
    now = utc_now()
    db["appointments"].insert_one({
        "_id": appointment_id, "bookingSource": "ai_agent", "acceptedAmountMinor": 120000,
        "bookingCurrency": "lkr", "status": "PENDING", "paymentStatus": "UNPAID",
        "doctorUserId": seed["doc_user_id"], "startTime": "14:00",
        "holdExpiresAt": now - timedelta(seconds=1), "appointmentDate": day,
    })
    payment = {"_id": payment_id, "appointmentId": str(appointment_id), "stripePaymentIntentId": stripe_id,
               "patientUserId": seed["pat_a_id"], "status": "PENDING"}
    db["payments"].insert_one(payment)
    assert settle_ai_payment(db, payment, {"id": stripe_id, "amount_received": 120000, "currency": "lkr"}, now) == "reconciliation_required"
    appointment = db["appointments"].find_one({"_id": appointment_id})
    assert appointment["status"] != "CONFIRMED"
    assert "confirmationOutbox" not in appointment
    assert db["payments"].find_one({"_id": payment_id})["reconciliationState"] == "REVIEW_REQUIRED"
    refund = Mock(return_value=SimpleNamespace(id="re_test", status="succeeded"))
    monkeypatch.setattr("stripe.Refund.create", refund)
    client = TestClient(app)
    url = f"/api/payments/{payment_id}/reconcile-refund"
    assert client.post(url, headers=headers(seed)).status_code == 403
    response = client.post(url, headers=headers(seed, "admin"))
    assert response.status_code == 200
    assert response.json()["reconciliationState"] == "REFUNDED"
    assert refund.call_count == 1


def test_concurrent_acceptances_and_free_booking(booking_fixture):
    db, seed, day = booking_fixture
    client = TestClient(app)
    first, second = headers(seed), headers(seed, "patient_b")
    db["doctor_profiles"].update_one({"_id": ObjectId(seed["doc_profile_id"])}, {"$set": {"consultationFee": 0}})
    message = "Book a neurologist in Colombo on December 5 at 5:30pm"
    sessions = [propose(client, actor, message) for actor in (first, second)]
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda case: accept(TestClient(app), *case), zip((first, second), sessions)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    booking = next(response.json() for response in responses if response.status_code == 200)
    assert booking["state"] == "BOOKING_CONFIRMED"
    assert booking["holdExpiresAt"] is None

def test_alternative_requires_fresh_acceptance_after_price_change_or_expiry(booking_fixture):
    db, seed, _ = booking_fixture
    client = TestClient(app)
    profile = ObjectId(seed["doc_profile_id"])
    db["doctor_profiles"].update_one({"_id": profile}, {"$set": {"consultationFee": 1800}})
    owner = headers(seed)
    session = propose(client, owner, "Book a neurologist in Colombo December 5 at 4:10pm")
    assert session["bookingSummary"]["requestedTime"] == "16:10"
    assert session["bookingSummary"]["startTime"] != "16:10"
    db["doctor_profiles"].update_one({"_id": profile}, {"$set": {"consultationFee": 1900}})
    assert accept(client, owner, session).status_code == 409
    assert not db["appointments"].find_one({"_id": ObjectId(session["bookingSummary"]["proposalId"])})

    next_session = propose(client, owner, "Book a neurologist in Colombo December 5 at 4:10pm")
    db["booking_sessions"].update_one({"_id": ObjectId(next_session["id"])},
                                      {"$set": {"bookingSummary.proposalExpiresAt": utc_now() - timedelta(seconds=1)}})
    assert accept(client, owner, next_session).status_code == 409


def test_notification_failure_does_not_change_booking_and_retries_are_durable(booking_fixture, monkeypatch):
    db, seed, day = booking_fixture
    appointment_id = ObjectId()
    db["appointments"].insert_one({
        "_id": appointment_id, "doctorUserId": seed["doc_user_id"], "patientUserId": seed["pat_a_id"],
        "appointmentDate": day, "startTime": "19:00", "status": "CONFIRMED", "paymentStatus": "PAID",
        "confirmationOutbox": notification_entries(utc_now()), "confirmedAt": utc_now(),
    })
    send = Mock(return_value={"status": "pending", "reason": "rate_limited"})
    monkeypatch.setattr(booking_notifications, "send_confirmation", send)
    monkeypatch.setattr(booking_notifications, "_poll_sms", Mock())
    booking_notifications.run_confirmation_outbox(db)
    booking_notifications.run_confirmation_outbox(db)
    row = db["appointments"].find_one({"_id": appointment_id})
    assert row["status"] == "CONFIRMED"
    assert row["confirmationOutbox"]["sms"]["status"] == "pending"
    assert row["confirmationOutbox"]["sms"]["attempts"] == 1
    assert row["confirmationOutbox"]["sms"]["nextAttemptAt"].timestamp() > utc_now().timestamp()


def test_manually_selected_slot_uses_bound_proposal(booking_fixture):
    db, seed, day = booking_fixture
    client = TestClient(app)
    owner = headers(seed)
    session = client.post("/api/ai/conversations", headers=owner, json={}).json()
    path = f"/api/ai/booking/sessions/{session['id']}"
    doctor = client.post(f"{path}/select-doctor", headers=owner,
                         json={"doctorId": seed["doc_code"], "date": day}).json()
    slot = doctor["candidateSlots"][0]
    selected = client.post(f"{path}/select-slot", headers=owner, json={**slot, "prepareProposal": True})
    assert selected.status_code == 200, selected.text
    assert selected.json()["bookingSummary"]["timezone"] == "Asia/Colombo"
    assert client.post(f"{path}/confirm", headers=owner, json={}).status_code == 409
    assert not db["appointments"].find_one({"_id": ObjectId(selected.json()["bookingSummary"]["proposalId"])})
