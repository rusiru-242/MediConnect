"""Integration tests for appointment booking, listing, cancellation, and status management."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pytest

try:
    from app.config.database import DatabaseManager
    from app.models.appointment import AppointmentStatus, get_appointment_collection
    from app.models.doctor_availability import DoctorAvailabilityDocument, get_doctor_availability_collection
    from app.models.doctor_profile import DoctorVerificationStatus, get_doctor_profile_collection
    from app.models.user import AccountStatus, UserRole, get_user_collection
    from app.services.appointment_service import AppointmentService, _parse_hhmm, _ALLOWED_TRANSITIONS
    from app.schemas.appointment import (
        CancelAppointmentRequest,
        CreateAppointmentRequest,
        UpdateAppointmentStatusRequest,
    )
    from app.schemas.user import UserResponseSchema
    from bson import ObjectId
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="Backend dependencies not available")

SL_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db():
    return DatabaseManager.get_database()


def _uid() -> str:
    return uuid.uuid4().hex[:10]


def _make_patient(db, suffix: str) -> Dict[str, Any]:
    col = get_user_collection(db)
    user = {
        "fullName": f"Patient Test {suffix}",
        "email": f"patient_{suffix}@appttest.com",
        "passwordHash": "hashed",
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    result = col.insert_one(user)
    return {**user, "_id": result.inserted_id}


def _make_doctor_pair(db, suffix: str):
    col = get_user_collection(db)
    user = {
        "fullName": f"Doctor Test {suffix}",
        "email": f"doctor_{suffix}@appttest.com",
        "passwordHash": "hashed",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    user_result = col.insert_one(user)
    user_id = user_result.inserted_id

    doctor_id = f"DR-{suffix}"
    pcol = get_doctor_profile_collection(db)
    profile = {
        "userId": str(user_id),
        "doctorId": doctor_id,
        "specialty": "General Medicine",
        "medicalRegistrationNumber": f"MRN-{suffix}",
        "qualifications": "MBBS",
        "hospitalOrClinic": f"Test Clinic {suffix}",
        "experienceYears": 5,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "submittedAt": datetime.now(timezone.utc),
        "verifiedAt": datetime.now(timezone.utc),
    }
    profile_result = pcol.insert_one(profile)
    return ({**user, "_id": user_id}, {**profile, "_id": profile_result.inserted_id})


def _make_availability(db, doctor_user_id: str, doctor_profile_id: str, date_str: str, start: str, end: str) -> Dict:
    avail = DoctorAvailabilityDocument(
        doctorUserId=doctor_user_id,
        doctorProfileId=doctor_profile_id,
        date=date_str,
        startTime=start,
        endTime=end,
        slotDurationMinutes=30,
        isActive=True,
    )
    col = get_doctor_availability_collection(db)
    result = col.insert_one(avail.to_mongo_dict())
    return {**avail.to_mongo_dict(), "_id": result.inserted_id}


def _make_user_schema(user_doc: Dict) -> UserResponseSchema:
    return UserResponseSchema(
        id=str(user_doc["_id"]),
        fullName=user_doc["fullName"],
        email=user_doc["email"],
        role=user_doc["role"],
        emailVerified=user_doc["emailVerified"],
        accountStatus=user_doc["accountStatus"],
        createdAt=user_doc["createdAt"],
        updatedAt=user_doc.get("updatedAt"),
        authProviders=user_doc.get("authProviders", ["LOCAL"]),
    )


def _future_date_str(days: int = 7) -> str:
    sl_now = datetime.now(SL_TIMEZONE)
    future = sl_now + timedelta(days=days)
    return future.strftime("%Y-%m-%d")


def _run(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. Parser & state machine unit tests (no DB)
# ---------------------------------------------------------------------------

class TestParsers:
    def test_parse_hhmm_valid(self):
        assert _parse_hhmm("09:30") == (9, 30)
        assert _parse_hhmm("23:59") == (23, 59)
        assert _parse_hhmm("00:00") == (0, 0)

    def test_parse_hhmm_rejects_bad_hour(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            _parse_hhmm("25:00")
        assert exc.value.status_code == 400

    def test_parse_hhmm_rejects_bad_format(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            _parse_hhmm("0930")  # missing colon
        assert exc.value.status_code == 400


class TestAllowedTransitions:
    def test_pending_can_go_to_confirmed(self):
        assert "CONFIRMED" in _ALLOWED_TRANSITIONS["PENDING"]

    def test_pending_can_be_cancelled(self):
        assert "CANCELLED" in _ALLOWED_TRANSITIONS["PENDING"]

    def test_confirmed_can_complete(self):
        assert "COMPLETED" in _ALLOWED_TRANSITIONS["CONFIRMED"]

    def test_confirmed_can_cancel(self):
        assert "CANCELLED" in _ALLOWED_TRANSITIONS["CONFIRMED"]

    def test_completed_is_terminal(self):
        assert len(_ALLOWED_TRANSITIONS["COMPLETED"]) == 0

    def test_cancelled_is_terminal(self):
        assert len(_ALLOWED_TRANSITIONS["CANCELLED"]) == 0

    def test_pending_cannot_complete_directly(self):
        assert "COMPLETED" not in _ALLOWED_TRANSITIONS["PENDING"]


# ---------------------------------------------------------------------------
# 2. Booking tests
# ---------------------------------------------------------------------------

class TestCreateAppointment:
    def test_successful_booking(self, db):
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(7)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "09:00", "12:00")
        patient_schema = _make_user_schema(patient_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="09:00",
        )
        result = _run(AppointmentService.create_appointment(db, patient_schema, req))

        assert result.status == AppointmentStatus.PENDING.value
        assert result.startTime == "09:00"
        assert result.endTime == "09:30"
        assert result.patientUserId == str(patient_doc["_id"])

        get_appointment_collection(db).delete_one({"_id": ObjectId(result.id)})

    def test_double_booking_raises_409(self, db):
        from fastapi import HTTPException
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(8)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "10:00", "13:00")
        patient_schema = _make_user_schema(patient_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="10:00",
        )
        r1 = _run(AppointmentService.create_appointment(db, patient_schema, req))

        uid2 = _uid()
        p2_doc = _make_patient(db, uid2)
        p2_schema = _make_user_schema(p2_doc)
        with pytest.raises(HTTPException) as exc:
            _run(AppointmentService.create_appointment(db, p2_schema, req))
        assert exc.value.status_code == 409

        get_appointment_collection(db).delete_one({"_id": ObjectId(r1.id)})

    def test_invalid_slot_boundary_raises_400(self, db):
        from fastapi import HTTPException
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(9)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "09:00", "12:00")
        patient_schema = _make_user_schema(patient_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="09:15",  # Not on 30-minute boundary
        )
        with pytest.raises(HTTPException) as exc:
            _run(AppointmentService.create_appointment(db, patient_schema, req))
        assert exc.value.status_code == 400

    def test_doctor_cannot_book_as_patient(self, db):
        from fastapi import HTTPException
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(10)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "09:00", "12:00")
        doctor_schema = _make_user_schema(doctor_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="09:00",
        )
        with pytest.raises(HTTPException) as exc:
            _run(AppointmentService.create_appointment(db, doctor_schema, req))
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# 3. Patient cancellation tests
# ---------------------------------------------------------------------------

class TestPatientCancellation:
    def test_patient_can_cancel_pending(self, db):
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(11)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "14:00", "16:00")
        patient_schema = _make_user_schema(patient_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="14:00",
        )
        appt = _run(AppointmentService.create_appointment(db, patient_schema, req))
        cancel_req = CancelAppointmentRequest(reason="Change of plans")
        result = _run(AppointmentService.cancel_patient_appointment(db, patient_schema, appt.id, cancel_req))

        assert result.status == AppointmentStatus.CANCELLED.value
        assert result.cancelledBy == "PATIENT"
        assert result.cancellationReason == "Change of plans"

    def test_other_patient_cannot_cancel(self, db):
        from fastapi import HTTPException
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(12)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "15:00", "17:00")
        patient_schema = _make_user_schema(patient_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="15:00",
        )
        appt = _run(AppointmentService.create_appointment(db, patient_schema, req))

        uid2 = _uid()
        other_patient = _make_patient(db, uid2)
        other_schema = _make_user_schema(other_patient)
        cancel_req = CancelAppointmentRequest(reason="Unauthorized")
        with pytest.raises(HTTPException) as exc:
            _run(AppointmentService.cancel_patient_appointment(db, other_schema, appt.id, cancel_req))
        assert exc.value.status_code == 403

        get_appointment_collection(db).delete_one({"_id": ObjectId(appt.id)})


# ---------------------------------------------------------------------------
# 4. Doctor status update tests
# ---------------------------------------------------------------------------

class TestDoctorStatusUpdate:
    def test_doctor_confirms_appointment(self, db):
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(13)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "08:00", "10:00")
        patient_schema = _make_user_schema(patient_doc)
        doctor_schema = _make_user_schema(doctor_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="08:00",
        )
        appt = _run(AppointmentService.create_appointment(db, patient_schema, req))
        update_req = UpdateAppointmentStatusRequest(status="CONFIRMED")
        result = _run(AppointmentService.update_appointment_status(db, doctor_schema, appt.id, update_req))

        assert result.status == AppointmentStatus.CONFIRMED.value

        get_appointment_collection(db).delete_one({"_id": ObjectId(result.id)})

    def test_doctor_cannot_skip_pending_to_completed(self, db):
        from fastapi import HTTPException
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(14)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "09:00", "11:00")
        patient_schema = _make_user_schema(patient_doc)
        doctor_schema = _make_user_schema(doctor_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="09:00",
        )
        appt = _run(AppointmentService.create_appointment(db, patient_schema, req))
        update_req = UpdateAppointmentStatusRequest(status="COMPLETED")
        with pytest.raises(HTTPException) as exc:
            _run(AppointmentService.update_appointment_status(db, doctor_schema, appt.id, update_req))
        assert exc.value.status_code == 400

        get_appointment_collection(db).delete_one({"_id": ObjectId(appt.id)})

    def test_other_doctor_cannot_update(self, db):
        from fastapi import HTTPException
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(15)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "10:00", "12:00")
        patient_schema = _make_user_schema(patient_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="10:00",
        )
        appt = _run(AppointmentService.create_appointment(db, patient_schema, req))

        uid2 = _uid()
        other_doc, _ = _make_doctor_pair(db, uid2)
        other_schema = _make_user_schema(other_doc)
        update_req = UpdateAppointmentStatusRequest(status="CONFIRMED")
        with pytest.raises(HTTPException) as exc:
            _run(AppointmentService.update_appointment_status(db, other_schema, appt.id, update_req))
        assert exc.value.status_code == 403

        get_appointment_collection(db).delete_one({"_id": ObjectId(appt.id)})

    def test_full_happy_path_pending_confirmed_completed(self, db):
        uid = _uid()
        patient_doc = _make_patient(db, uid)
        doctor_doc, profile_doc = _make_doctor_pair(db, uid)
        future_date = _future_date_str(16)
        avail_doc = _make_availability(db, str(doctor_doc["_id"]), str(profile_doc["_id"]), future_date, "11:00", "13:00")
        patient_schema = _make_user_schema(patient_doc)
        doctor_schema = _make_user_schema(doctor_doc)

        req = CreateAppointmentRequest(
            doctorId=profile_doc["doctorId"],
            availabilityId=str(avail_doc["_id"]),
            appointmentDate=future_date,
            startTime="11:00",
        )
        appt = _run(AppointmentService.create_appointment(db, patient_schema, req))
        assert appt.status == "PENDING"

        confirmed = _run(AppointmentService.update_appointment_status(
            db, doctor_schema, appt.id, UpdateAppointmentStatusRequest(status="CONFIRMED")
        ))
        assert confirmed.status == "CONFIRMED"

        # Advance slot to past so consultation time is reached for complete validation
        get_appointment_collection(db).update_one(
            {"_id": ObjectId(appt.id)},
            {"$set": {"appointmentDate": "2020-01-01"}}
        )

        completed = _run(AppointmentService.update_appointment_status(
            db, doctor_schema, appt.id, UpdateAppointmentStatusRequest(status="COMPLETED")
        ))
        assert completed.status == "COMPLETED"

        # Completed is terminal - cannot cancel
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            _run(AppointmentService.cancel_patient_appointment(
                db, patient_schema, appt.id, CancelAppointmentRequest(reason="too late")
            ))
        assert exc.value.status_code == 400

        get_appointment_collection(db).delete_one({"_id": ObjectId(appt.id)})
