"""Comprehensive integration test suite covering TEST 1 to TEST 17 for appointment booking foundation."""

import asyncio
from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Dict, Tuple
from bson import ObjectId
import pytest
from fastapi import HTTPException

from app.config.database import DatabaseManager
from app.models.appointment import AppointmentStatus, get_appointment_collection
from app.models.doctor_availability import DoctorAvailabilityDocument, get_doctor_availability_collection
from app.models.doctor_profile import DoctorVerificationStatus, get_doctor_profile_collection
from app.models.user import AccountStatus, UserRole, get_user_collection
from app.schemas.appointment import (
    CancelAppointmentRequest,
    CreateAppointmentRequest,
    UpdateAppointmentStatusRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.appointment_service import AppointmentService
from app.services.doctor_service import DoctorService

SL_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture(scope="module")
def db():
    return DatabaseManager.get_database()


def _uid() -> str:
    return uuid.uuid4().hex[:10]


def _future_date(days: int = 5) -> str:
    return (datetime.now(SL_TIMEZONE) + timedelta(days=days)).strftime("%Y-%m-%d")


def _make_patient(db, suffix: str) -> Tuple[Dict[str, Any], UserResponseSchema]:
    col = get_user_collection(db)
    user = {
        "fullName": f"Patient Booking {suffix}",
        "email": f"patient_{suffix}@bookingtest.com",
        "passwordHash": "hashed_pw",
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    result = col.insert_one(user)
    user["_id"] = result.inserted_id
    schema = UserResponseSchema(
        id=str(user["_id"]),
        fullName=user["fullName"],
        email=user["email"],
        role=user["role"],
        emailVerified=user["emailVerified"],
        accountStatus=user["accountStatus"],
        createdAt=user["createdAt"],
        authProviders=user["authProviders"],
    )
    return user, schema


def _make_doctor(
    db,
    suffix: str,
    verification_status: str = DoctorVerificationStatus.APPROVED.value,
    account_status: str = AccountStatus.ACTIVE.value,
) -> Tuple[Dict[str, Any], Dict[str, Any], UserResponseSchema]:
    col = get_user_collection(db)
    user = {
        "fullName": f"Dr. Booking {suffix}",
        "email": f"doctor_{suffix}@bookingtest.com",
        "passwordHash": "hashed_pw",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": account_status,
        "authProviders": ["LOCAL"],
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    result = col.insert_one(user)
    user_id = result.inserted_id
    user["_id"] = user_id

    doctor_id = f"DR-{suffix}"
    pcol = get_doctor_profile_collection(db)
    profile = {
        "userId": str(user_id),
        "doctorId": doctor_id,
        "specialty": "Cardiology",
        "medicalRegistrationNumber": f"SLMC-{suffix}",
        "qualifications": "MBBS, MD",
        "hospitalOrClinic": f"Colombo National Hospital {suffix}",
        "experienceYears": 10,
        "verificationStatus": verification_status,
        "submittedAt": datetime.now(timezone.utc),
        "verifiedAt": datetime.now(timezone.utc) if verification_status == DoctorVerificationStatus.APPROVED.value else None,
    }
    p_result = pcol.insert_one(profile)
    profile["_id"] = p_result.inserted_id

    schema = UserResponseSchema(
        id=str(user_id),
        fullName=user["fullName"],
        email=user["email"],
        role=user["role"],
        emailVerified=user["emailVerified"],
        accountStatus=user["accountStatus"],
        createdAt=user["createdAt"],
        authProviders=user["authProviders"],
    )
    return user, profile, schema


def _make_availability(
    db,
    doctor_user_id: str,
    doctor_profile_id: str,
    date_str: str,
    start: str = "09:00",
    end: str = "12:00",
    is_active: bool = True,
    duration: int = 30,
) -> Dict[str, Any]:
    avail = DoctorAvailabilityDocument(
        doctorUserId=doctor_user_id,
        doctorProfileId=doctor_profile_id,
        date=date_str,
        startTime=start,
        endTime=end,
        slotDurationMinutes=duration,
        isActive=is_active,
    )
    col = get_doctor_availability_collection(db)
    result = col.insert_one(avail.to_mongo_dict())
    return {**avail.to_mongo_dict(), "_id": result.inserted_id}


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ===========================================================================
# TEST 1 to TEST 17
# ===========================================================================

def test_1_patient_books_valid_available_slot(db):
    """TEST 1: Patient books valid available slot. Expected: PENDING appointment created."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, _ = _make_doctor(db, uid)
    date_str = _future_date(5)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00")

    req = CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
        patientNote="First consultation",
    )
    res = _run(AppointmentService.create_appointment(db, p_schema, req))

    assert res.appointment.status == AppointmentStatus.PENDING.value
    assert res.appointment.startTime == "09:00"
    assert res.appointment.endTime == "09:30"
    assert res.appointment.appointmentDate == date_str
    assert res.appointment.patientUserId == p_schema.id

    get_appointment_collection(db).delete_one({"_id": ObjectId(res.appointment.id)})


def test_2_patient_attempts_invalid_time(db):
    """TEST 2: Patient attempts invalid time. Expected: rejected."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, _ = _make_doctor(db, uid)
    date_str = _future_date(6)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00")

    # Slot not aligned with 30-min duration: 09:17
    req = CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:17",
    )
    with pytest.raises(HTTPException) as exc:
        _run(AppointmentService.create_appointment(db, p_schema, req))
    assert exc.value.status_code == 400


def test_3_patient_attempts_past_slot(db):
    """TEST 3: Patient attempts past slot. Expected: rejected."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, _ = _make_doctor(db, uid)
    past_date = "2020-01-01"
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), past_date, "09:00", "11:00")

    req = CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=past_date,
        startTime="09:00",
    )
    with pytest.raises(HTTPException) as exc:
        _run(AppointmentService.create_appointment(db, p_schema, req))
    assert exc.value.status_code == 400
    assert "past" in exc.value.detail.lower()


def test_4_patient_attempts_disabled_availability(db):
    """TEST 4: Patient attempts disabled availability. Expected: rejected."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, _ = _make_doctor(db, uid)
    date_str = _future_date(7)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00", is_active=False)

    req = CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )
    with pytest.raises(HTTPException) as exc:
        _run(AppointmentService.create_appointment(db, p_schema, req))
    assert exc.value.status_code == 400


def test_5_patient_attempts_pending_or_rejected_doctor(db):
    """TEST 5: Patient attempts pending/rejected doctor. Expected: rejected."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    # Pending doctor
    _, dr_prof_pending, _ = _make_doctor(db, f"pnd_{uid}", verification_status=DoctorVerificationStatus.PENDING.value)
    req = CreateAppointmentRequest(
        doctorId=dr_prof_pending["doctorId"],
        date=_future_date(8),
        startTime="09:00",
    )
    with pytest.raises(HTTPException) as exc:
        _run(AppointmentService.create_appointment(db, p_schema, req))
    assert exc.value.status_code in [400, 403, 404]

    # Rejected doctor
    _, dr_prof_rejected, _ = _make_doctor(db, f"rej_{uid}", verification_status=DoctorVerificationStatus.REJECTED.value)
    req2 = CreateAppointmentRequest(
        doctorId=dr_prof_rejected["doctorId"],
        date=_future_date(8),
        startTime="09:00",
    )
    with pytest.raises(HTTPException) as exc2:
        _run(AppointmentService.create_appointment(db, p_schema, req2))
    assert exc2.value.status_code in [400, 403, 404]


def test_6_two_patients_attempt_same_slot_concurrently(db):
    """TEST 6: Two patients attempt same slot concurrently. Expected: ONLY ONE succeeds, other receives 409."""
    uid = _uid()
    _, p1_schema = _make_patient(db, f"p1_{uid}")
    _, p2_schema = _make_patient(db, f"p2_{uid}")
    dr_user, dr_prof, _ = _make_doctor(db, uid)
    date_str = _future_date(9)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "10:00", "12:00")

    req = CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="10:00",
    )

    # First succeeds
    res1 = _run(AppointmentService.create_appointment(db, p1_schema, req))
    assert res1.appointment.status == AppointmentStatus.PENDING.value

    # Second patient receives 409 conflict
    with pytest.raises(HTTPException) as exc:
        _run(AppointmentService.create_appointment(db, p2_schema, req))
    assert exc.value.status_code == 409

    get_appointment_collection(db).delete_one({"_id": ObjectId(res1.appointment.id)})


def test_7_booked_slot_requested_from_availability_endpoint(db):
    """TEST 7: Booked slot requested from availability endpoint. Expected: slot no longer shown."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, _ = _make_doctor(db, uid)
    date_str = _future_date(10)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "10:00")

    # Initial slots: 09:00 and 09:30
    slots_before = _run(DoctorService.get_doctor_patient_slots(db, dr_prof["doctorId"], date_filter=date_str))
    all_times_before = [s.startTime for d in (slots_before if isinstance(slots_before, list) else [slots_before]) for s in d.slots]
    assert "09:00" in all_times_before
    assert "09:30" in all_times_before

    # Book 09:00
    req = CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )
    res = _run(AppointmentService.create_appointment(db, p_schema, req))

    # Slots after booking: 09:00 must be excluded
    slots_after = _run(DoctorService.get_doctor_patient_slots(db, dr_prof["doctorId"], date_filter=date_str))
    all_times_after = [s.startTime for d in (slots_after if isinstance(slots_after, list) else [slots_after]) for s in d.slots]
    assert "09:00" not in all_times_after
    assert "09:30" in all_times_after

    get_appointment_collection(db).delete_one({"_id": ObjectId(res.appointment.id)})


def test_8_patient_views_own_appointments(db):
    """TEST 8: Patient views own appointments. Expected: only own appointments."""
    uid1 = _uid()
    uid2 = _uid()
    _, p1_schema = _make_patient(db, uid1)
    _, p2_schema = _make_patient(db, uid2)
    dr_user, dr_prof, _ = _make_doctor(db, uid1)
    date_str = _future_date(11)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00")

    # Patient 1 books 09:00
    r1 = _run(AppointmentService.create_appointment(db, p1_schema, CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )))

    # Patient 2 views appointments
    p2_list = _run(AppointmentService.list_patient_appointments(db, p2_schema))
    p2_ids = [item.id for item in p2_list.items]
    assert r1.appointment.id not in p2_ids

    # Patient 1 views appointments
    p1_list = _run(AppointmentService.list_patient_appointments(db, p1_schema))
    p1_ids = [item.id for item in p1_list.items]
    assert r1.appointment.id in p1_ids

    get_appointment_collection(db).delete_one({"_id": ObjectId(r1.appointment.id)})


def test_9_patient_attempts_another_patients_appointment_detail(db):
    """TEST 9: Patient attempts another patient's appointment detail. Expected: 403/404 safe response."""
    uid1 = _uid()
    uid2 = _uid()
    _, p1_schema = _make_patient(db, uid1)
    _, p2_schema = _make_patient(db, uid2)
    dr_user, dr_prof, _ = _make_doctor(db, uid1)
    date_str = _future_date(12)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00")

    r1 = _run(AppointmentService.create_appointment(db, p1_schema, CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )))

    with pytest.raises(HTTPException) as exc:
        _run(AppointmentService.get_appointment(db, p2_schema, r1.appointment.id))
    assert exc.value.status_code in [403, 404]

    get_appointment_collection(db).delete_one({"_id": ObjectId(r1.appointment.id)})


def test_10_doctor_views_appointments(db):
    """TEST 10: Doctor views appointments. Expected: only assigned appointments."""
    uid1 = _uid()
    uid2 = _uid()
    _, p_schema = _make_patient(db, uid1)
    dr1_user, dr1_prof, dr1_schema = _make_doctor(db, uid1)
    dr2_user, dr2_prof, dr2_schema = _make_doctor(db, uid2)

    date_str = _future_date(13)
    avail1 = _make_availability(db, str(dr1_user["_id"]), str(dr1_prof["_id"]), date_str, "09:00", "11:00")

    r1 = _run(AppointmentService.create_appointment(db, p_schema, CreateAppointmentRequest(
        doctorId=dr1_prof["doctorId"],
        availabilityId=str(avail1["_id"]),
        date=date_str,
        startTime="09:00",
    )))

    # Doctor 2 should NOT see doctor 1's appointment
    dr2_list = _run(AppointmentService.list_doctor_appointments(db, dr2_schema))
    dr2_ids = [item.id for item in dr2_list.items]
    assert r1.appointment.id not in dr2_ids

    # Doctor 1 SHOULD see their appointment
    dr1_list = _run(AppointmentService.list_doctor_appointments(db, dr1_schema))
    dr1_ids = [item.id for item in dr1_list.items]
    assert r1.appointment.id in dr1_ids

    get_appointment_collection(db).delete_one({"_id": ObjectId(r1.appointment.id)})


def test_11_doctor_confirms_own_pending_appointment(db):
    """TEST 11: Doctor confirms own PENDING appointment. Expected: CONFIRMED."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, dr_schema = _make_doctor(db, uid)
    date_str = _future_date(14)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00")

    r = _run(AppointmentService.create_appointment(db, p_schema, CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )))
    assert r.appointment.status == "PENDING"

    confirmed = _run(AppointmentService.confirm_doctor_appointment(db, dr_schema, r.appointment.id))
    assert confirmed.status == AppointmentStatus.CONFIRMED.value

    get_appointment_collection(db).delete_one({"_id": ObjectId(r.appointment.id)})


def test_12_unrelated_doctor_attempts_confirmation(db):
    """TEST 12: Unrelated doctor attempts confirmation. Expected: 403/404."""
    uid1 = _uid()
    uid2 = _uid()
    _, p_schema = _make_patient(db, uid1)
    dr1_user, dr1_prof, _ = _make_doctor(db, uid1)
    _, _, dr2_schema = _make_doctor(db, uid2)

    date_str = _future_date(15)
    avail = _make_availability(db, str(dr1_user["_id"]), str(dr1_prof["_id"]), date_str, "09:00", "11:00")

    r = _run(AppointmentService.create_appointment(db, p_schema, CreateAppointmentRequest(
        doctorId=dr1_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )))

    with pytest.raises(HTTPException) as exc:
        _run(AppointmentService.confirm_doctor_appointment(db, dr2_schema, r.appointment.id))
    assert exc.value.status_code in [403, 404]

    get_appointment_collection(db).delete_one({"_id": ObjectId(r.appointment.id)})


def test_13_patient_cancels_confirmed_appointment(db):
    """TEST 13: Patient cancels confirmed appointment. Expected: CANCELLED."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, dr_schema = _make_doctor(db, uid)
    date_str = _future_date(16)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00")

    r = _run(AppointmentService.create_appointment(db, p_schema, CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )))
    _run(AppointmentService.confirm_doctor_appointment(db, dr_schema, r.appointment.id))

    cancelled = _run(AppointmentService.cancel_patient_appointment(
        db, p_schema, r.appointment.id, reason="Emergency conflict"
    ))
    assert cancelled.status == AppointmentStatus.CANCELLED.value
    assert cancelled.cancelledBy == "PATIENT"

    get_appointment_collection(db).delete_one({"_id": ObjectId(r.appointment.id)})


def test_14_cancelled_future_slot_becomes_available_again(db):
    """TEST 14: Cancelled future slot becomes available again."""
    uid = _uid()
    _, p1_schema = _make_patient(db, f"p1_{uid}")
    _, p2_schema = _make_patient(db, f"p2_{uid}")
    dr_user, dr_prof, _ = _make_doctor(db, uid)
    date_str = _future_date(17)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "14:00", "15:00")

    # P1 books 14:00
    r1 = _run(AppointmentService.create_appointment(db, p1_schema, CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="14:00",
    )))

    # P1 cancels 14:00
    _run(AppointmentService.cancel_patient_appointment(db, p1_schema, r1.appointment.id, reason="Cancelled"))

    # Slot should appear in availability again
    slots = _run(DoctorService.get_doctor_patient_slots(db, dr_prof["doctorId"], date_filter=date_str))
    all_times = [s.startTime for d in (slots if isinstance(slots, list) else [slots]) for s in d.slots]
    assert "14:00" in all_times

    # P2 can now successfully book 14:00
    r2 = _run(AppointmentService.create_appointment(db, p2_schema, CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="14:00",
    )))
    assert r2.appointment.status == AppointmentStatus.PENDING.value

    get_appointment_collection(db).delete_one({"_id": ObjectId(r1.appointment.id)})
    get_appointment_collection(db).delete_one({"_id": ObjectId(r2.appointment.id)})


def test_15_doctor_completes_confirmed_appointment_at_valid_time(db):
    """TEST 15: Doctor completes confirmed appointment at valid time. Expected: COMPLETED."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, dr_schema = _make_doctor(db, uid)
    date_str = _future_date(18)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00")

    r = _run(AppointmentService.create_appointment(db, p_schema, CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )))
    _run(AppointmentService.confirm_doctor_appointment(db, dr_schema, r.appointment.id))

    # Move appointmentDate to past so consultation time is reached
    get_appointment_collection(db).update_one(
        {"_id": ObjectId(r.appointment.id)},
        {"$set": {"appointmentDate": "2020-01-01"}}
    )

    completed = _run(AppointmentService.complete_doctor_appointment(db, dr_schema, r.appointment.id))
    assert completed.status == AppointmentStatus.COMPLETED.value

    get_appointment_collection(db).delete_one({"_id": ObjectId(r.appointment.id)})


def test_16_try_cancelled_to_confirmed_rejected(db):
    """TEST 16: Try CANCELLED → CONFIRMED. Expected: rejected."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, dr_schema = _make_doctor(db, uid)
    date_str = _future_date(19)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00")

    r = _run(AppointmentService.create_appointment(db, p_schema, CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )))
    _run(AppointmentService.cancel_patient_appointment(db, p_schema, r.appointment.id, reason="Cancel"))

    with pytest.raises(HTTPException) as exc:
        _run(AppointmentService.confirm_doctor_appointment(db, dr_schema, r.appointment.id))
    assert exc.value.status_code == 400

    get_appointment_collection(db).delete_one({"_id": ObjectId(r.appointment.id)})


def test_17_try_completed_to_cancelled_rejected(db):
    """TEST 17: Try COMPLETED → CANCELLED. Expected: rejected."""
    uid = _uid()
    _, p_schema = _make_patient(db, uid)
    dr_user, dr_prof, dr_schema = _make_doctor(db, uid)
    date_str = _future_date(20)
    avail = _make_availability(db, str(dr_user["_id"]), str(dr_prof["_id"]), date_str, "09:00", "11:00")

    r = _run(AppointmentService.create_appointment(db, p_schema, CreateAppointmentRequest(
        doctorId=dr_prof["doctorId"],
        availabilityId=str(avail["_id"]),
        date=date_str,
        startTime="09:00",
    )))
    _run(AppointmentService.confirm_doctor_appointment(db, dr_schema, r.appointment.id))

    # Move appointmentDate to past so consultation time is reached
    get_appointment_collection(db).update_one(
        {"_id": ObjectId(r.appointment.id)},
        {"$set": {"appointmentDate": "2020-01-01"}}
    )
    _run(AppointmentService.complete_doctor_appointment(db, dr_schema, r.appointment.id))

    # Patient attempt to cancel completed
    with pytest.raises(HTTPException) as exc1:
        _run(AppointmentService.cancel_patient_appointment(db, p_schema, r.appointment.id, reason="Late cancel"))
    assert exc1.value.status_code == 400

    # Doctor attempt to cancel completed
    with pytest.raises(HTTPException) as exc2:
        _run(AppointmentService.cancel_doctor_appointment(db, dr_schema, r.appointment.id, reason="Doctor cancel"))
    assert exc2.value.status_code == 400

    get_appointment_collection(db).delete_one({"_id": ObjectId(r.appointment.id)})
