"""Appointment service: booking, listing, status management with strict validation."""

from datetime import datetime as _dt, timedelta, timezone
import math
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.appointment import (
    AppointmentDocument,
    AppointmentStatus,
    get_appointment_collection,
    utc_now,
)
from app.models.doctor_availability import get_doctor_availability_collection
from app.models.doctor_profile import DoctorVerificationStatus, get_doctor_profile_collection
from app.models.user import AccountStatus, UserRole
from app.schemas.appointment import (
    AppointmentListResponse,
    AppointmentResponse,
    CancelAppointmentRequest,
    CreateAppointmentRequest,
    CreateAppointmentResponse,
    UpdateAppointmentStatusRequest,
)
from app.schemas.user import UserResponseSchema

# Sri Lanka Standard Time (Asia/Colombo = UTC+05:30)
SL_TIMEZONE = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# VALID STATE TRANSITIONS
# ---------------------------------------------------------------------------
_ALLOWED_TRANSITIONS: Dict[str, set] = {
    AppointmentStatus.PENDING.value: {
        AppointmentStatus.CONFIRMED.value,
        AppointmentStatus.CANCELLED.value,
    },
    AppointmentStatus.CONFIRMED.value: {
        AppointmentStatus.COMPLETED.value,
        AppointmentStatus.CANCELLED.value,
    },
    AppointmentStatus.COMPLETED.value: set(),   # terminal
    AppointmentStatus.CANCELLED.value: set(),   # terminal
}


def _build_appointment_response(
    doc: Dict[str, Any],
    doctor_id: Optional[str] = None,
    patient_name: Optional[str] = None,
    patient_email: Optional[str] = None,
    doctor_name: Optional[str] = None,
    specialty: Optional[str] = None,
    hospital_or_clinic: Optional[str] = None,
) -> AppointmentResponse:
    """Build an AppointmentResponse from a raw MongoDB document with optional enriched fields."""
    return AppointmentResponse(
        id=str(doc["_id"]),
        patientUserId=str(doc["patientUserId"]),
        doctorUserId=str(doc["doctorUserId"]),
        doctorProfileId=str(doc["doctorProfileId"]),
        availabilityId=str(doc["availabilityId"]),
        appointmentDate=doc["appointmentDate"],
        startTime=doc["startTime"],
        endTime=doc["endTime"],
        status=doc["status"],
        patientNote=doc.get("patientNote"),
        cancelledBy=doc.get("cancelledBy"),
        cancellationReason=doc.get("cancellationReason"),
        createdAt=doc["createdAt"],
        updatedAt=doc["updatedAt"],
        doctorId=doctor_id or doc.get("doctorId"),
        patientName=patient_name,
        patientEmail=patient_email,
        doctorName=doctor_name,
        specialty=specialty,
        hospitalOrClinic=hospital_or_clinic,
    )


class AppointmentService:
    """Business logic for appointment booking, listing, and status management."""

    # -------------------------------------------------------------------------
    # PATIENT: Create appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def create_appointment(
        db: Database,
        patient_user: UserResponseSchema,
        req: CreateAppointmentRequest,
    ) -> CreateAppointmentResponse:
        """Book a time slot for a patient.

        Security rules:
        - Patient must have ACTIVE account with verified email.
        - Doctor must be APPROVED and ACTIVE.
        - Slot must exist in the availability window and not be in the past.
        - Backend derives and validates endTime; never trusts client-supplied endTime.
        - Database-level unique index prevents race-condition double-bookings.
        """
        # 1. Role check
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can book appointments.",
            )

        if patient_user.accountStatus != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only active accounts can book appointments.",
            )

        # 2. Resolve doctor via doctorId string (from discovery)
        clean_doctor_id = req.doctorId.strip()
        profile_query: Dict[str, Any] = {}
        if ObjectId.is_valid(clean_doctor_id):
            profile_query = {
                "$or": [
                    {"doctorId": clean_doctor_id},
                    {"_id": ObjectId(clean_doctor_id)},
                ]
            }
        else:
            profile_query = {"doctorId": clean_doctor_id}

        doctor_profile = db["doctor_profiles"].find_one(profile_query)
        if not doctor_profile or doctor_profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found or is not currently accepting appointments.",
            )

        doctor_user_id_raw = doctor_profile.get("userId")
        doctor_user_obj_query = (
            {"$or": [{"_id": ObjectId(doctor_user_id_raw)}, {"_id": doctor_user_id_raw}]}
            if ObjectId.is_valid(str(doctor_user_id_raw))
            else {"_id": doctor_user_id_raw}
        )
        doctor_user_doc = db["users"].find_one(doctor_user_obj_query)
        if (
            not doctor_user_doc
            or doctor_user_doc.get("role") != UserRole.DOCTOR.value
            or doctor_user_doc.get("accountStatus") != AccountStatus.ACTIVE.value
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found or is not currently accepting appointments.",
            )

        doctor_user_id = str(doctor_user_doc["_id"])
        doctor_profile_id = str(doctor_profile["_id"])
        target_date = req.appointmentDate or req.date

        # 3. Resolve and validate the availability window
        avail_doc = None
        if req.availabilityId and req.availabilityId.strip():
            avail_id_raw = req.availabilityId.strip()
            if not ObjectId.is_valid(avail_id_raw):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid availabilityId format.",
                )
            avail_doc = db["doctor_availabilities"].find_one({"_id": ObjectId(avail_id_raw)})
        else:
            # Lookup active availability window for this doctor matching date
            avail_doc = db["doctor_availabilities"].find_one({
                "doctorUserId": doctor_user_id,
                "date": target_date,
                "isActive": True,
                "startTime": {"$lte": req.startTime},
                "endTime": {"$gt": req.startTime},
            })

        if not avail_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability window not found for this schedule.",
            )

        # Security: availability must belong to the resolved doctor
        if str(avail_doc.get("doctorUserId")) != doctor_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Availability does not belong to this doctor.",
            )

        if not avail_doc.get("isActive", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This availability window is no longer active.",
            )

        if avail_doc.get("date") != target_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment date does not match the availability window date.",
            )

        # 4. Backend derives valid slots for the window and validates requested startTime
        slot_duration = int(avail_doc.get("slotDurationMinutes", 30))
        window_start = avail_doc["startTime"]  # "HH:MM"
        window_end = avail_doc["endTime"]      # "HH:MM"

        req_start_h, req_start_m = _parse_hhmm(req.startTime)
        req_start_total = req_start_h * 60 + req_start_m

        # Compute derived endTime
        derived_end_total = req_start_total + slot_duration
        derived_end_str = f"{derived_end_total // 60:02d}:{derived_end_total % 60:02d}"

        # Validate slot falls exactly within window boundaries and aligns with slotDuration
        win_start_h, win_start_m = _parse_hhmm(window_start)
        win_end_h, win_end_m = _parse_hhmm(window_end)
        win_start_total = win_start_h * 60 + win_start_m
        win_end_total = win_end_h * 60 + win_end_m

        slot_valid = (
            req_start_total >= win_start_total
            and derived_end_total <= win_end_total
            and (req_start_total - win_start_total) % slot_duration == 0
        )
        if not slot_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Selected time slot ({req.startTime} - {derived_end_str}) is not a valid slot in this availability window.",
            )

        # 5. Ensure slot is not in the past (Sri Lanka local time)
        sl_now = _dt.now(SL_TIMEZONE)
        try:
            slot_dt_naive = _dt.strptime(f"{target_date} {req.startTime}", "%Y-%m-%d %H:%M")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date or time format.")

        slot_dt = slot_dt_naive.replace(tzinfo=SL_TIMEZONE)
        if slot_dt <= sl_now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book an appointment in the past.",
            )

        # 6. Check if slot is already occupied by any active appointment (PENDING, CONFIRMED, COMPLETED)
        existing_booking = db["appointments"].find_one({
            "doctorUserId": doctor_user_id,
            "appointmentDate": target_date,
            "startTime": req.startTime,
            "status": {"$in": [
                AppointmentStatus.PENDING.value,
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.COMPLETED.value,
            ]},
        })
        if existing_booking:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This time slot is no longer available.",
            )

        # 7. Insert appointment - database unique index guards concurrent race conditions
        now = utc_now()
        avail_id_str = str(avail_doc["_id"])
        appt_doc = AppointmentDocument(
            patientUserId=str(patient_user.id),
            doctorUserId=doctor_user_id,
            doctorProfileId=doctor_profile_id,
            availabilityId=avail_id_str,
            appointmentDate=target_date,
            startTime=req.startTime,
            endTime=derived_end_str,
            status=AppointmentStatus.PENDING,
            patientNote=req.patientNote,
            createdAt=now,
            updatedAt=now,
        )

        try:
            result = get_appointment_collection(db).insert_one(appt_doc.to_mongo_dict())
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This time slot is no longer available.",
            )

        appt_response = _build_appointment_response(
            {**appt_doc.to_mongo_dict(), "_id": result.inserted_id},
            doctor_id=str(doctor_profile.get("doctorId", "")),
            doctor_name=doctor_user_doc.get("fullName"),
            specialty=doctor_profile.get("specialty"),
            hospital_or_clinic=doctor_profile.get("hospitalOrClinic"),
            patient_name=patient_user.fullName,
            patient_email=patient_user.email,
        )

        return CreateAppointmentResponse(
            message="Appointment request created successfully.",
            appointment=appt_response,
        )

    # -------------------------------------------------------------------------
    # PATIENT: List own appointments
    # -------------------------------------------------------------------------
    @staticmethod
    async def list_patient_appointments(
        db: Database,
        patient_user: UserResponseSchema,
        page: int = 1,
        limit: int = 20,
        status_filter: Optional[str] = None,
    ) -> AppointmentListResponse:
        """Return paginated appointment history for the authenticated patient."""
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can access this.")

        page = max(1, page)
        limit = max(1, min(50, limit))
        skip = (page - 1) * limit

        query: Dict[str, Any] = {"patientUserId": str(patient_user.id)}
        if status_filter and status_filter.strip():
            clean = status_filter.strip().upper()
            if clean not in AppointmentStatus.__members__:
                raise HTTPException(status_code=400, detail=f"Invalid status filter: {status_filter}.")
            query["status"] = clean

        collection = get_appointment_collection(db)
        total = collection.count_documents(query)
        cursor = (
            collection.find(query)
            .sort([("appointmentDate", DESCENDING), ("startTime", DESCENDING)])
            .skip(skip)
            .limit(limit)
        )

        items = []
        for doc in cursor:
            dr_user = db["users"].find_one({"_id": ObjectId(doc["doctorUserId"])}) if ObjectId.is_valid(doc.get("doctorUserId", "")) else None
            dr_profile = db["doctor_profiles"].find_one({"_id": ObjectId(doc["doctorProfileId"])}) if ObjectId.is_valid(doc.get("doctorProfileId", "")) else None
            items.append(_build_appointment_response(
                doc,
                doctor_id=dr_profile.get("doctorId") if dr_profile else None,
                doctor_name=dr_user.get("fullName") if dr_user else None,
                specialty=dr_profile.get("specialty") if dr_profile else None,
                hospital_or_clinic=dr_profile.get("hospitalOrClinic") if dr_profile else None,
                patient_name=patient_user.fullName,
                patient_email=patient_user.email,
            ))

        return AppointmentListResponse(
            items=items,
            page=page,
            limit=limit,
            total=total,
            totalPages=math.ceil(total / limit) if total > 0 else 0,
        )

    # -------------------------------------------------------------------------
    # PATIENT: Cancel own appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def cancel_patient_appointment(
        db: Database,
        patient_user: UserResponseSchema,
        appointment_id: str,
        reason: Optional[Any] = None,
    ) -> AppointmentResponse:
        """Allow patient to cancel their own appointment (only PENDING or CONFIRMED)."""
        if hasattr(reason, "reason"):
            reason = reason.reason

        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can cancel appointments.")

        appt = _get_appointment_or_404(db, appointment_id)

        # Ownership check
        if str(appt["patientUserId"]) != str(patient_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to cancel this appointment.",
            )

        current_status = appt["status"]
        if "CANCELLED" not in _ALLOWED_TRANSITIONS.get(current_status, set()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel an appointment with status: {current_status}.",
            )

        now = utc_now()
        get_appointment_collection(db).update_one(
            {"_id": ObjectId(appointment_id)},
            {
                "$set": {
                    "status": AppointmentStatus.CANCELLED.value,
                    "cancelledBy": "PATIENT",
                    "cancellationReason": reason,
                    "updatedAt": now,
                }
            },
        )

        updated = _get_appointment_or_404(db, appointment_id)
        dr_user = db["users"].find_one({"_id": ObjectId(updated["doctorUserId"])}) if ObjectId.is_valid(updated.get("doctorUserId", "")) else None
        dr_profile = db["doctor_profiles"].find_one({"_id": ObjectId(updated["doctorProfileId"])}) if ObjectId.is_valid(updated.get("doctorProfileId", "")) else None
        return _build_appointment_response(
            updated,
            doctor_id=dr_profile.get("doctorId") if dr_profile else None,
            doctor_name=dr_user.get("fullName") if dr_user else None,
            specialty=dr_profile.get("specialty") if dr_profile else None,
            hospital_or_clinic=dr_profile.get("hospitalOrClinic") if dr_profile else None,
            patient_name=patient_user.fullName,
            patient_email=patient_user.email,
        )

    # -------------------------------------------------------------------------
    # DOCTOR: List assigned appointments
    # -------------------------------------------------------------------------
    @staticmethod
    async def list_doctor_appointments(
        db: Database,
        doctor_user: UserResponseSchema,
        page: int = 1,
        limit: int = 20,
        date_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> AppointmentListResponse:
        """Return paginated appointment list for the authenticated doctor."""
        _assert_doctor_approved_and_active(db, doctor_user)

        page = max(1, page)
        limit = max(1, min(50, limit))
        skip = (page - 1) * limit

        query: Dict[str, Any] = {"doctorUserId": str(doctor_user.id)}

        if date_filter and date_filter.strip():
            query["appointmentDate"] = date_filter.strip()

        if status_filter and status_filter.strip():
            clean = status_filter.strip().upper()
            if clean not in AppointmentStatus.__members__:
                raise HTTPException(status_code=400, detail=f"Invalid status filter: {status_filter}.")
            query["status"] = clean

        collection = get_appointment_collection(db)
        total = collection.count_documents(query)
        cursor = (
            collection.find(query)
            .sort([("appointmentDate", ASCENDING), ("startTime", ASCENDING)])
            .skip(skip)
            .limit(limit)
        )

        items = []
        for doc in cursor:
            pt_user = db["users"].find_one({"_id": ObjectId(doc["patientUserId"])}) if ObjectId.is_valid(doc.get("patientUserId", "")) else None
            dr_profile = db["doctor_profiles"].find_one({"_id": ObjectId(doc["doctorProfileId"])}) if ObjectId.is_valid(doc.get("doctorProfileId", "")) else None
            items.append(_build_appointment_response(
                doc,
                doctor_id=dr_profile.get("doctorId") if dr_profile else None,
                patient_name=pt_user.get("fullName") if pt_user else None,
                patient_email=pt_user.get("email") if pt_user else None,
                doctor_name=doctor_user.fullName,
            ))

        return AppointmentListResponse(
            items=items,
            page=page,
            limit=limit,
            total=total,
            totalPages=math.ceil(total / limit) if total > 0 else 0,
        )

    # -------------------------------------------------------------------------
    # DOCTOR: Confirm appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def confirm_doctor_appointment(
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
    ) -> AppointmentResponse:
        """Allow doctor to confirm a PENDING appointment."""
        _assert_doctor_approved_and_active(db, doctor_user)

        appt = _get_appointment_or_404(db, appointment_id)

        # Ownership check
        if str(appt["doctorUserId"]) != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this appointment.",
            )

        current_status = appt["status"]
        if current_status != AppointmentStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm an appointment with status: {current_status}.",
            )

        now = utc_now()
        get_appointment_collection(db).update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": {"status": AppointmentStatus.CONFIRMED.value, "updatedAt": now}},
        )

        updated = _get_appointment_or_404(db, appointment_id)
        pt_user = db["users"].find_one({"_id": ObjectId(updated["patientUserId"])}) if ObjectId.is_valid(updated.get("patientUserId", "")) else None
        return _build_appointment_response(
            updated,
            patient_name=pt_user.get("fullName") if pt_user else None,
            patient_email=pt_user.get("email") if pt_user else None,
            doctor_name=doctor_user.fullName,
        )

    # -------------------------------------------------------------------------
    # DOCTOR: Complete appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def complete_doctor_appointment(
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
    ) -> AppointmentResponse:
        """Allow doctor to complete a CONFIRMED appointment at or after scheduled time."""
        _assert_doctor_approved_and_active(db, doctor_user)

        appt = _get_appointment_or_404(db, appointment_id)

        # Ownership check
        if str(appt["doctorUserId"]) != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this appointment.",
            )

        current_status = appt["status"]
        if current_status != AppointmentStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete an appointment with status: {current_status}.",
            )

        # Validation: Consultation time must have been reached or passed
        sl_now = _dt.now(SL_TIMEZONE)
        slot_dt = _dt.strptime(f"{appt['appointmentDate']} {appt['startTime']}", "%Y-%m-%d %H:%M").replace(tzinfo=SL_TIMEZONE)
        if slot_dt > sl_now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot mark an appointment as completed before its scheduled consultation time.",
            )

        now = utc_now()
        get_appointment_collection(db).update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": {"status": AppointmentStatus.COMPLETED.value, "updatedAt": now}},
        )

        updated = _get_appointment_or_404(db, appointment_id)
        pt_user = db["users"].find_one({"_id": ObjectId(updated["patientUserId"])}) if ObjectId.is_valid(updated.get("patientUserId", "")) else None
        return _build_appointment_response(
            updated,
            patient_name=pt_user.get("fullName") if pt_user else None,
            patient_email=pt_user.get("email") if pt_user else None,
            doctor_name=doctor_user.fullName,
        )

    # -------------------------------------------------------------------------
    # DOCTOR: Cancel appointment
    # -------------------------------------------------------------------------
    @staticmethod
    async def cancel_doctor_appointment(
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
        reason: Optional[Any] = None,
    ) -> AppointmentResponse:
        """Allow doctor to cancel an appointment."""
        if hasattr(reason, "reason"):
            reason = reason.reason

        _assert_doctor_approved_and_active(db, doctor_user)

        appt = _get_appointment_or_404(db, appointment_id)

        # Ownership check
        if str(appt["doctorUserId"]) != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this appointment.",
            )

        current_status = appt["status"]
        if "CANCELLED" not in _ALLOWED_TRANSITIONS.get(current_status, set()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel an appointment with status: {current_status}.",
            )

        now = utc_now()
        get_appointment_collection(db).update_one(
            {"_id": ObjectId(appointment_id)},
            {
                "$set": {
                    "status": AppointmentStatus.CANCELLED.value,
                    "cancelledBy": "DOCTOR",
                    "cancellationReason": reason,
                    "updatedAt": now,
                }
            },
        )

        updated = _get_appointment_or_404(db, appointment_id)
        pt_user = db["users"].find_one({"_id": ObjectId(updated["patientUserId"])}) if ObjectId.is_valid(updated.get("patientUserId", "")) else None
        return _build_appointment_response(
            updated,
            patient_name=pt_user.get("fullName") if pt_user else None,
            patient_email=pt_user.get("email") if pt_user else None,
            doctor_name=doctor_user.fullName,
        )

    # -------------------------------------------------------------------------
    # DOCTOR: Update appointment status (generic dispatcher)
    # -------------------------------------------------------------------------
    @staticmethod
    async def update_appointment_status(
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
        req: UpdateAppointmentStatusRequest,
    ) -> AppointmentResponse:
        """Generic doctor appointment status updater."""
        target_status = req.status.upper()
        if target_status == AppointmentStatus.CONFIRMED.value:
            return await AppointmentService.confirm_doctor_appointment(db, doctor_user, appointment_id)
        elif target_status == AppointmentStatus.COMPLETED.value:
            return await AppointmentService.complete_doctor_appointment(db, doctor_user, appointment_id)
        elif target_status == AppointmentStatus.CANCELLED.value:
            return await AppointmentService.cancel_doctor_appointment(db, doctor_user, appointment_id, reason=req.reason)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target status: {req.status}",
            )

    # -------------------------------------------------------------------------
    # SHARED: Get single appointment (with ownership guard)
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_appointment(
        db: Database,
        requester: UserResponseSchema,
        appointment_id: str,
    ) -> AppointmentResponse:
        """Fetch a single appointment; requester must be the patient, doctor, or admin."""
        appt = _get_appointment_or_404(db, appointment_id)

        is_patient = requester.role == UserRole.PATIENT.value and str(appt["patientUserId"]) == str(requester.id)
        is_doctor = requester.role == UserRole.DOCTOR.value and str(appt["doctorUserId"]) == str(requester.id)
        is_admin = requester.role == UserRole.ADMIN.value

        if not (is_patient or is_doctor or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this appointment.",
            )

        pt_user = db["users"].find_one({"_id": ObjectId(appt["patientUserId"])}) if ObjectId.is_valid(appt.get("patientUserId", "")) else None
        dr_user = db["users"].find_one({"_id": ObjectId(appt["doctorUserId"])}) if ObjectId.is_valid(appt.get("doctorUserId", "")) else None
        dr_profile = db["doctor_profiles"].find_one({"_id": ObjectId(appt["doctorProfileId"])}) if ObjectId.is_valid(appt.get("doctorProfileId", "")) else None

        return _build_appointment_response(
            appt,
            doctor_id=dr_profile.get("doctorId") if dr_profile else None,
            patient_name=pt_user.get("fullName") if pt_user else None,
            patient_email=pt_user.get("email") if pt_user else None,
            doctor_name=dr_user.get("fullName") if dr_user else None,
            specialty=dr_profile.get("specialty") if dr_profile else None,
            hospital_or_clinic=dr_profile.get("hospitalOrClinic") if dr_profile else None,
        )


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """Parse HH:MM string into (hours, minutes). Raises 400 on invalid format."""
    parts = time_str.split(":")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Time must be in HH:MM format.")
    try:
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError()
        return h, m
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time values in HH:MM.")


def _get_appointment_or_404(db: Database, appointment_id: str) -> Dict[str, Any]:
    """Fetch appointment document by ID or raise 404."""
    if not ObjectId.is_valid(appointment_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid appointment ID format.")

    appt = get_appointment_collection(db).find_one({"_id": ObjectId(appointment_id)})
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    return appt


def _assert_doctor_approved_and_active(db: Database, doctor_user: UserResponseSchema) -> Dict[str, Any]:
    """Ensure doctor user is DOCTOR, account is ACTIVE, and doctor profile is APPROVED."""
    if doctor_user.role != UserRole.DOCTOR.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can access this.")

    if doctor_user.accountStatus != AccountStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your doctor account is not active or verified.",
        )

    profile = db["doctor_profiles"].find_one({"userId": str(doctor_user.id)})
    if not profile or profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only approved doctors with active accounts can manage appointments.",
        )
    return profile
