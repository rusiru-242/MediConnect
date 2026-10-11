"""Integration tests for Phase 16 — Stripe Payment Integration.

Covers tests 1 through 13:
TEST 1: Unauthenticated payment intent request -> 401
TEST 2: Doctor attempts patient payment endpoint -> 403
TEST 3: Patient attempts another patient's appointment -> 403/404
TEST 4: Flutter/request sends manipulated amount -> ignored/backend fee used
TEST 5: Valid booking creates payment intent -> PENDING payment
TEST 6: Two patients attempt same slot -> only one active hold
TEST 7: Expired hold -> slot released
TEST 8: Invalid webhook signature -> 400 rejected
TEST 9: payment_intent.succeeded -> Payment=SUCCEEDED, Appointment.paymentStatus=PAID, Appointment=CONFIRMED
TEST 10: Same success webhook delivered twice -> idempotent, no duplicate effects
TEST 11: payment_intent.payment_failed -> Payment=FAILED, appointment not confirmed
TEST 12: Patient reads own payment status -> allowed (200)
TEST 13: Other patient reads payment -> denied (403)
"""

from datetime import datetime, timedelta, timezone
import json
import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest
import stripe

from app.config.database import DatabaseManager, get_database
from app.main import app
from app.config.settings import settings
from app.models.appointment import (
    AppointmentDocument,
    AppointmentStatus,
    PaymentStatus as AppointmentPaymentStatus,
    utc_now,
)
from app.models.doctor_availability import DoctorAvailabilityDocument
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.payment import PaymentDocument, PaymentStatus, get_payment_collection
from app.models.user import AccountStatus, UserRole
from app.services.appointment_service import AppointmentService, SL_TIMEZONE
from app.schemas.appointment import CreateAppointmentRequest
from app.schemas.user import UserResponseSchema
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def db():
    return DatabaseManager.get_database()


def _uid() -> str:
    return f"{int(time.time() * 1000)}_{ObjectId()}"[:14]


def _make_test_patient(db, suffix: str) -> Dict[str, Any]:
    uid = _uid()
    oid = ObjectId()
    doc = {
        "_id": oid,
        "fullName": f"Patient {suffix}",
        "email": f"patient_{suffix}_{uid}@mediconnect.lk",
        "phone": "0771234567",
        "passwordHash": hash_password("Secret123!"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    }
    db["users"].insert_one(doc)
    token = create_access_token(str(oid), role=UserRole.PATIENT.value)
    return {**doc, "token": token, "id": str(oid)}


def _make_test_doctor(db, suffix: str, fee: float = 2500.0) -> Dict[str, Any]:
    uid = _uid()
    doc_oid = ObjectId()
    user_doc = {
        "_id": doc_oid,
        "fullName": f"Dr. {suffix}",
        "email": f"doctor_{suffix}_{uid}@mediconnect.lk",
        "phone": "0777654321",
        "passwordHash": hash_password("DoctorSecret123!"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    }
    db["users"].insert_one(user_doc)
    token = create_access_token(str(doc_oid), role=UserRole.DOCTOR.value)

    prof_oid = ObjectId()
    doc_id_str = f"DOC-TEST-{suffix}-{uid}"
    prof_doc = {
        "_id": prof_oid,
        "userId": str(doc_oid),
        "doctorId": doc_id_str,
        "specialty": "Cardiology",
        "medicalRegistrationNumber": f"SLMC-{uid}",
        "hospitalOrClinic": "MediConnect General Hospital",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "consultationFee": fee,
        "experienceYears": 8,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    }
    db["doctor_profiles"].insert_one(prof_doc)

    return {
        "user": user_doc,
        "profile": prof_doc,
        "token": token,
        "id": str(doc_oid),
        "profileId": str(prof_oid),
        "doctorId": doc_id_str,
        "consultationFee": fee,
    }


def _make_future_availability(db, doctor: Dict[str, Any], days_ahead: int = 5) -> Dict[str, Any]:
    sl_future = datetime.now(SL_TIMEZONE) + timedelta(days=days_ahead)
    date_str = sl_future.strftime("%Y-%m-%d")
    avail = DoctorAvailabilityDocument(
        doctorUserId=doctor["id"],
        doctorProfileId=doctor["profileId"],
        date=date_str,
        startTime="09:00",
        endTime="12:00",
        slotDurationMinutes=30,
        isActive=True,
    )
    res = db["doctor_availabilities"].insert_one(avail.to_mongo_dict())
    return {**avail.to_mongo_dict(), "_id": res.inserted_id, "id": str(res.inserted_id)}


def _book_appointment(db, patient: Dict[str, Any], doctor: Dict[str, Any], avail: Dict[str, Any], start_time: str = "09:00") -> Dict[str, Any]:
    patient_schema = UserResponseSchema(
        id=patient["id"],
        fullName=patient["fullName"],
        email=patient["email"],
        role=patient["role"],
        emailVerified=patient["emailVerified"],
        accountStatus=patient["accountStatus"],
        createdAt=patient["createdAt"],
        authProviders=patient["authProviders"],
    )
    req = CreateAppointmentRequest(
        doctorId=doctor["doctorId"],
        availabilityId=avail["id"],
        date=avail["date"],
        startTime=start_time,
    )
    import asyncio
    res = asyncio.get_event_loop().run_until_complete(
        AppointmentService.create_appointment(db, patient_schema, req)
    )
    return res.appointment.model_dump()


# ===========================================================================
# BACKEND TESTS (1 through 13)
# ===========================================================================

class TestStripePaymentBackend:

    # TEST 1: Unauthenticated payment intent request -> 401
    def test_01_unauthenticated_create_intent_returns_401(self):
        resp = client.post("/api/payments/create-intent", json={"appointmentId": str(ObjectId())})
        assert resp.status_code == 401

    # TEST 2: Doctor attempts patient payment endpoint -> 403
    def test_02_doctor_role_forbidden_from_create_intent(self, db):
        doc = _make_test_doctor(db, "RoleCheck")
        resp = client.post(
            "/api/payments/create-intent",
            headers={"Authorization": f"Bearer {doc['token']}"},
            json={"appointmentId": str(ObjectId())},
        )
        assert resp.status_code == 403

    # TEST 3: Patient attempts another patient's appointment -> 403
    def test_03_patient_cannot_pay_another_patients_appointment(self, db):
        patient_a = _make_test_patient(db, "OwnerA")
        patient_b = _make_test_patient(db, "AttackerB")
        doctor = _make_test_doctor(db, "DocCross")
        avail = _make_future_availability(db, doctor, 5)

        appt = _book_appointment(db, patient_a, doctor, avail, "09:00")

        resp = client.post(
            "/api/payments/create-intent",
            headers={"Authorization": f"Bearer {patient_b['token']}"},
            json={"appointmentId": appt["id"]},
        )
        assert resp.status_code == 403
        assert "do not have access" in resp.json()["detail"]

    # TEST 4: Flutter/request sends manipulated amount -> ignored; backend fee used
    def test_04_manipulated_amount_in_request_is_ignored_and_backend_fee_used(self, db):
        patient = _make_test_patient(db, "FeePatient")
        doctor = _make_test_doctor(db, "FeeDoc", fee=3500.0)  # LKR 3,500.00
        avail = _make_future_availability(db, doctor, 6)

        appt = _book_appointment(db, patient, doctor, avail, "09:30")

        # Patient sends manipulated amount: 100 LKR
        manipulated_payload = {
            "appointmentId": appt["id"],
            "amount": 100,  # manipulated amount
        }

        mock_intent = MagicMock()
        mock_intent.id = f"pi_mock_{_uid()}"
        mock_intent.client_secret = f"{mock_intent.id}_secret_xyz"
        mock_intent.status = "requires_payment_method"

        with patch("stripe.PaymentIntent.create", return_value=mock_intent) as mock_create:
            resp = client.post(
                "/api/payments/create-intent",
                headers={"Authorization": f"Bearer {patient['token']}"},
                json=manipulated_payload,
            )
            assert resp.status_code == 201
            data = resp.json()
            # Must be 3500 * 100 = 350000 cents, NOT 100 or 10000
            assert data["amount"] == 350000
            # Verify Stripe was called with backend-calculated 350000 cents
            mock_create.assert_called_once()
            args, kwargs = mock_create.call_args
            assert kwargs["amount"] == 350000

    # TEST 5: Valid booking creates payment intent -> PENDING payment
    def test_05_valid_booking_creates_pending_payment(self, db):
        patient = _make_test_patient(db, "ValidBooking")
        doctor = _make_test_doctor(db, "ValidDoc", fee=2500.0)
        avail = _make_future_availability(db, doctor, 7)

        appt = _book_appointment(db, patient, doctor, avail, "10:00")

        mock_intent = MagicMock()
        mock_intent.id = f"pi_valid_{_uid()}"
        mock_intent.client_secret = f"{mock_intent.id}_secret_abc"
        mock_intent.status = "requires_payment_method"

        with patch("stripe.PaymentIntent.create", return_value=mock_intent):
            resp = client.post(
                "/api/payments/create-intent",
                headers={"Authorization": f"Bearer {patient['token']}"},
                json={"appointmentId": appt["id"]},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["paymentIntentClientSecret"] == mock_intent.client_secret
            payment_id = data["paymentId"]

            # Verify Payment in DB is PENDING
            payment_doc = get_payment_collection(db).find_one({"_id": ObjectId(payment_id)})
            assert payment_doc is not None
            assert payment_doc["status"] == PaymentStatus.PENDING.value
            assert payment_doc["stripePaymentIntentId"] == mock_intent.id

    # TEST 6: Two patients attempt same slot -> only one active hold
    def test_06_double_booking_prevention_only_one_active_hold(self, db):
        patient_1 = _make_test_patient(db, "SlotHolder1")
        patient_2 = _make_test_patient(db, "SlotHolder2")
        doctor = _make_test_doctor(db, "ConflictDoc")
        avail = _make_future_availability(db, doctor, 8)

        # Patient 1 successfully holds slot
        appt1 = _book_appointment(db, patient_1, doctor, avail, "10:30")
        assert appt1["status"] in ["PENDING", "HOLD"]

        # Patient 2 attempts same slot -> must fail with 409
        p2_schema = UserResponseSchema(
            id=patient_2["id"],
            fullName=patient_2["fullName"],
            email=patient_2["email"],
            role=patient_2["role"],
            emailVerified=patient_2["emailVerified"],
            accountStatus=patient_2["accountStatus"],
            createdAt=patient_2["createdAt"],
            authProviders=patient_2["authProviders"],
        )
        req2 = CreateAppointmentRequest(
            doctorId=doctor["doctorId"],
            availabilityId=avail["id"],
            date=avail["date"],
            startTime="10:30",
        )
        import asyncio
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.get_event_loop().run_until_complete(
                AppointmentService.create_appointment(db, p2_schema, req2)
            )
        assert exc.value.status_code == 409

    # TEST 7: Expired hold -> slot released
    def test_07_expired_hold_releases_slot(self, db):
        patient_old = _make_test_patient(db, "OldHold")
        patient_new = _make_test_patient(db, "NewBooking")
        doctor = _make_test_doctor(db, "ExpiryDoc")
        avail = _make_future_availability(db, doctor, 9)

        # Book slot with patient_old
        appt = _book_appointment(db, patient_old, doctor, avail, "11:00")

        # Manually expire patient_old's hold to 15 minutes ago
        past_time = utc_now() - timedelta(minutes=15)
        db["appointments"].update_one(
            {"_id": ObjectId(appt["id"])},
            {"$set": {"holdExpiresAt": past_time}}
        )

        # Patient new attempts the same slot -> slot should be freed and booking succeed!
        appt_new = _book_appointment(db, patient_new, doctor, avail, "11:00")
        assert appt_new is not None
        assert appt_new["patientUserId"] == patient_new["id"]

        # Verify old booking was marked CANCELLED
        old_doc = db["appointments"].find_one({"_id": ObjectId(appt["id"])})
        assert old_doc["status"] == AppointmentStatus.CANCELLED.value
        assert old_doc["cancellationReason"] == "Booking hold expired"

    # TEST 8: Invalid webhook signature -> 400 rejected
    def test_08_invalid_webhook_signature_rejected(self):
        with patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_mock_test_secret_123"):
            with patch(
                "stripe.Webhook.construct_event",
                side_effect=stripe.error.SignatureVerificationError("Signature mismatch", "sig"),
            ):
                resp = client.post(
                    "/api/payments/webhook",
                    content=b'{"id": "evt_test"}',
                    headers={"Stripe-Signature": "t=123,v1=invalidsignature"},
                )
                assert resp.status_code == 400
                assert "signature" in resp.json()["detail"].lower()

    # TEST 9: payment_intent.succeeded webhook -> Payment=SUCCEEDED, Appointment.paymentStatus=PAID, Appointment=CONFIRMED
    def test_09_webhook_payment_intent_succeeded_confirms_appointment(self, db):
        patient = _make_test_patient(db, "SuccessHookPat")
        doctor = _make_test_doctor(db, "SuccessHookDoc")
        avail = _make_future_availability(db, doctor, 10)

        appt = _book_appointment(db, patient, doctor, avail, "11:30")
        pi_id = f"pi_succ_{_uid()}"

        # Insert pending payment record
        now = utc_now()
        pay_doc = PaymentDocument(
            appointmentId=appt["id"],
            patientUserId=patient["id"],
            doctorUserId=doctor["id"],
            stripePaymentIntentId=pi_id,
            amount=doctor["consultationFee"],
            currency="lkr",
            status=PaymentStatus.PENDING,
            createdAt=now,
            updatedAt=now,
        )
        pay_res = get_payment_collection(db).insert_one(pay_doc.to_mongo_dict())

        event_payload = {
            "id": f"evt_{_uid()}",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": pi_id,
                    "amount": int(doctor["consultationFee"] * 100),
                    "currency": "lkr",
                    "status": "succeeded",
                }
            }
        }

        with patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_mock_test_secret_123"):
            with patch("stripe.Webhook.construct_event", return_value=event_payload):
                resp = client.post(
                    "/api/payments/webhook",
                    content=json.dumps(event_payload).encode("utf-8"),
                    headers={"Stripe-Signature": "valid_mock_sig"},
                )
                assert resp.status_code == 200
                assert resp.json()["status"] == "success"

        # Verify DB states
        updated_pay = get_payment_collection(db).find_one({"_id": pay_res.inserted_id})
        assert updated_pay["status"] == PaymentStatus.SUCCEEDED.value
        assert updated_pay["paidAt"] is not None

        updated_appt = db["appointments"].find_one({"_id": ObjectId(appt["id"])})
        assert updated_appt["status"] == AppointmentStatus.CONFIRMED.value
        assert updated_appt["paymentStatus"] == AppointmentPaymentStatus.PAID.value

    # TEST 10: Same success webhook delivered twice -> idempotent
    def test_10_webhook_delivered_twice_is_idempotent(self, db):
        patient = _make_test_patient(db, "IdempotentPat")
        doctor = _make_test_doctor(db, "IdempotentDoc")
        avail = _make_future_availability(db, doctor, 11)

        appt = _book_appointment(db, patient, doctor, avail, "09:00")
        pi_id = f"pi_idem_{_uid()}"

        now = utc_now()
        pay_doc = PaymentDocument(
            appointmentId=appt["id"],
            patientUserId=patient["id"],
            doctorUserId=doctor["id"],
            stripePaymentIntentId=pi_id,
            amount=doctor["consultationFee"],
            currency="lkr",
            status=PaymentStatus.PENDING,
            createdAt=now,
            updatedAt=now,
        )
        pay_res = get_payment_collection(db).insert_one(pay_doc.to_mongo_dict())

        event_payload = {
            "id": f"evt_{_uid()}",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": pi_id, "status": "succeeded"}},
        }

        with patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_mock_test_secret_123"):
            with patch("stripe.Webhook.construct_event", return_value=event_payload):
                # First delivery
                r1 = client.post(
                    "/api/payments/webhook",
                    content=json.dumps(event_payload).encode("utf-8"),
                    headers={"Stripe-Signature": "valid_mock_sig"},
                )
                assert r1.status_code == 200
                assert r1.json()["status"] == "success"

                # Second delivery (duplicate from Stripe)
                r2 = client.post(
                    "/api/payments/webhook",
                    content=json.dumps(event_payload).encode("utf-8"),
                    headers={"Stripe-Signature": "valid_mock_sig"},
                )
                assert r2.status_code == 200
                assert r2.json()["status"] == "already_processed"

        # Verify DB payment is still SUCCEEDED and didn't create duplicate
        payments_count = get_payment_collection(db).count_documents({"stripePaymentIntentId": pi_id})
        assert payments_count == 1

    # TEST 11: payment_intent.payment_failed webhook -> Payment=FAILED, appointment not confirmed
    def test_11_webhook_payment_failed_does_not_confirm(self, db):
        patient = _make_test_patient(db, "FailHookPat")
        doctor = _make_test_doctor(db, "FailHookDoc")
        avail = _make_future_availability(db, doctor, 12)

        appt = _book_appointment(db, patient, doctor, avail, "09:30")
        pi_id = f"pi_fail_{_uid()}"

        now = utc_now()
        pay_doc = PaymentDocument(
            appointmentId=appt["id"],
            patientUserId=patient["id"],
            doctorUserId=doctor["id"],
            stripePaymentIntentId=pi_id,
            amount=doctor["consultationFee"],
            currency="lkr",
            status=PaymentStatus.PENDING,
            createdAt=now,
            updatedAt=now,
        )
        pay_res = get_payment_collection(db).insert_one(pay_doc.to_mongo_dict())

        event_payload = {
            "id": f"evt_{_uid()}",
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": pi_id,
                    "last_payment_error": {"message": "Card was declined"},
                }
            },
        }

        with patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_mock_test_secret_123"):
            with patch("stripe.Webhook.construct_event", return_value=event_payload):
                resp = client.post(
                    "/api/payments/webhook",
                    content=json.dumps(event_payload).encode("utf-8"),
                    headers={"Stripe-Signature": "valid_mock_sig"},
                )
                assert resp.status_code == 200

        updated_pay = get_payment_collection(db).find_one({"_id": pay_res.inserted_id})
        assert updated_pay["status"] == PaymentStatus.FAILED.value
        assert "Card was declined" in updated_pay.get("failureReason", "")

        updated_appt = db["appointments"].find_one({"_id": ObjectId(appt["id"])})
        assert updated_appt["status"] != AppointmentStatus.CONFIRMED.value
        assert updated_appt["paymentStatus"] == AppointmentPaymentStatus.FAILED.value

    # TEST 12: Patient reads own payment status -> allowed (200)
    def test_12_patient_reads_own_payment_status_allowed(self, db):
        patient = _make_test_patient(db, "StatusOwner")
        doctor = _make_test_doctor(db, "StatusDoc")
        now = utc_now()

        pay_doc = PaymentDocument(
            appointmentId=str(ObjectId()),
            patientUserId=patient["id"],
            doctorUserId=doctor["id"],
            stripePaymentIntentId=f"pi_status_{_uid()}",
            amount=2500.0,
            currency="lkr",
            status=PaymentStatus.SUCCEEDED,
            paidAt=now,
            createdAt=now,
            updatedAt=now,
        )
        pay_res = get_payment_collection(db).insert_one(pay_doc.to_mongo_dict())

        resp = client.get(
            f"/api/payments/{pay_res.inserted_id}/status",
            headers={"Authorization": f"Bearer {patient['token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["paymentId"] == str(pay_res.inserted_id)
        assert data["paymentStatus"] == PaymentStatus.SUCCEEDED.value

    # TEST 13: Other patient reads payment -> denied (403)
    def test_13_other_patient_reads_payment_denied(self, db):
        patient_owner = _make_test_patient(db, "PayOwner")
        patient_other = _make_test_patient(db, "PayOther")
        doctor = _make_test_doctor(db, "Doc13")
        now = utc_now()

        pay_doc = PaymentDocument(
            appointmentId=str(ObjectId()),
            patientUserId=patient_owner["id"],
            doctorUserId=doctor["id"],
            stripePaymentIntentId=f"pi_priv_{_uid()}",
            amount=2500.0,
            currency="lkr",
            status=PaymentStatus.SUCCEEDED,
            createdAt=now,
            updatedAt=now,
        )
        pay_res = get_payment_collection(db).insert_one(pay_doc.to_mongo_dict())

        resp = client.get(
            f"/api/payments/{pay_res.inserted_id}/status",
            headers={"Authorization": f"Bearer {patient_other['token']}"},
        )
        assert resp.status_code == 403
        assert "do not have permission" in resp.json()["detail"]

    # TEST 14: Payment intent on expired booking hold -> cancels hold and returns 400
    def test_14_create_intent_on_expired_hold_returns_400(self, db):
        patient = _make_test_patient(db, "ExpiredHoldPat")
        doctor = _make_test_doctor(db, "ExpiredHoldDoc")
        avail = _make_future_availability(db, doctor, 14)

        appt = _book_appointment(db, patient, doctor, avail, "10:00")

        # Manually expire hold
        past_time = utc_now() - timedelta(minutes=15)
        db["appointments"].update_one(
            {"_id": ObjectId(appt["id"])},
            {"$set": {"holdExpiresAt": past_time}},
        )

        resp = client.post(
            "/api/payments/create-intent",
            headers={"Authorization": f"Bearer {patient['token']}"},
            json={"appointmentId": appt["id"]},
        )
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

        # Verify appointment marked CANCELLED
        updated_appt = db["appointments"].find_one({"_id": ObjectId(appt["id"])})
        assert updated_appt["status"] == AppointmentStatus.CANCELLED.value

    # TEST 15: Duplicate create payment intent for same active hold -> reuses existing intent idempotently
    def test_15_duplicate_create_intent_reuses_existing_intent(self, db):
        patient = _make_test_patient(db, "DupIntentPat")
        doctor = _make_test_doctor(db, "DupIntentDoc")
        avail = _make_future_availability(db, doctor, 15)

        appt = _book_appointment(db, patient, doctor, avail, "10:30")

        mock_intent = MagicMock()
        mock_intent.id = f"pi_reuse_{_uid()}"
        mock_intent.client_secret = f"{mock_intent.id}_secret_xyz"
        mock_intent.status = "requires_payment_method"

        with patch("stripe.PaymentIntent.create", return_value=mock_intent) as mock_create:
            with patch("stripe.PaymentIntent.retrieve", return_value=mock_intent) as mock_retrieve:
                # First request creates PaymentIntent
                r1 = client.post(
                    "/api/payments/create-intent",
                    headers={"Authorization": f"Bearer {patient['token']}"},
                    json={"appointmentId": appt["id"]},
                )
                assert r1.status_code == 201
                d1 = r1.json()
                assert mock_create.call_count == 1

                # Second request reuses the existing PaymentIntent without creating another
                r2 = client.post(
                    "/api/payments/create-intent",
                    headers={"Authorization": f"Bearer {patient['token']}"},
                    json={"appointmentId": appt["id"]},
                )
                assert r2.status_code == 201
                d2 = r2.json()

                # Verify same intent and payment ID returned
                assert d2["paymentIntentClientSecret"] == d1["paymentIntentClientSecret"]
                assert d2["paymentId"] == d1["paymentId"]
                # PaymentIntent.create was NOT called again
                assert mock_create.call_count == 1
                assert mock_retrieve.call_count >= 1

    # TEST 16: Payment intent on already paid appointment -> rejected with 400
    def test_16_create_intent_on_already_paid_appointment_returns_400(self, db):
        patient = _make_test_patient(db, "PaidApptPat")
        doctor = _make_test_doctor(db, "PaidApptDoc")
        avail = _make_future_availability(db, doctor, 16)

        appt = _book_appointment(db, patient, doctor, avail, "11:00")
        db["appointments"].update_one(
            {"_id": ObjectId(appt["id"])},
            {"$set": {"status": AppointmentStatus.CONFIRMED.value, "paymentStatus": AppointmentPaymentStatus.PAID.value}},
        )

        resp = client.post(
            "/api/payments/create-intent",
            headers={"Authorization": f"Bearer {patient['token']}"},
            json={"appointmentId": appt["id"]},
        )
        assert resp.status_code == 400
        assert "already been paid" in resp.json()["detail"].lower()

    # TEST 17: Patient payment history GET /api/payments/me -> returns 200 with items and total
    def test_17_patient_reads_payment_history(self, db):
        patient = _make_test_patient(db, "HistPat")
        doctor = _make_test_doctor(db, "HistDoc")
        now = utc_now()

        pay_doc = PaymentDocument(
            appointmentId=str(ObjectId()),
            patientUserId=patient["id"],
            doctorUserId=doctor["id"],
            stripePaymentIntentId=f"pi_hist_{_uid()}",
            amount=2500.0,
            currency="lkr",
            status=PaymentStatus.SUCCEEDED,
            paidAt=now,
            createdAt=now,
            updatedAt=now,
        )
        get_payment_collection(db).insert_one(pay_doc.to_mongo_dict())

        resp = client.get(
            "/api/payments/me",
            headers={"Authorization": f"Bearer {patient['token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert any(item["doctorName"] == doctor["user"]["fullName"] for item in data["items"])

    # TEST 18: Doctor role accessing GET /api/payments/me -> 403 forbidden
    def test_18_doctor_cannot_view_patient_payment_history(self, db):
        doctor = _make_test_doctor(db, "DocNoHist")
        resp = client.get(
            "/api/payments/me",
            headers={"Authorization": f"Bearer {doctor['token']}"},
        )
        assert resp.status_code == 403

