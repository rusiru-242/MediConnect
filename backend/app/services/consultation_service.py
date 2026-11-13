"""Business logic and service layer for Doctor Daily Schedule and Consultation Management (Phase 57)."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ASCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.appointment import AppointmentStatus, get_appointment_collection
from app.models.care_plan import get_care_plan_collection
from app.models.consultation import (
    ConsultationSessionDocument,
    ConsultationStatus,
    get_consultation_collection,
    utc_now,
)
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.medical_record import get_medical_record_collection
from app.models.prescription import get_prescription_collection
from app.models.user import AccountStatus, UserRole
from app.schemas.consultation import (
    ConsultationDetailResponse,
    ConsultationSessionResponse,
    DailyScheduleStats,
    DoctorDailyScheduleResponse,
    ScheduleAppointmentItem,
)
from app.schemas.user import UserResponseSchema

logger = logging.getLogger(__name__)

# Default Sri Lanka timezone
SL_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def _get_doctor_timezone_str(db: Database, doctor_user_id: str) -> str:
    """Retrieve doctor's configured timezone from schedule, or default to Asia/Colombo."""
    sched = db["doctor_weekly_schedules"].find_one({"doctorUserId": str(doctor_user_id)})
    if sched and sched.get("timezone"):
        return sched["timezone"]
    return "Asia/Colombo"


def _get_doctor_local_now(db: Database, doctor_user_id: str) -> datetime:
    """Return current datetime localized to doctor's configured timezone."""
    tz_str = _get_doctor_timezone_str(db, doctor_user_id)
    try:
        return datetime.now(ZoneInfo(tz_str))
    except Exception:
        return datetime.now(SL_TIMEZONE)


def _doc_to_session_response(doc: Dict[str, Any]) -> ConsultationSessionResponse:
    """Convert MongoDB consultation session document to Pydantic schema."""
    session_id = str(doc["_id"]) if "_id" in doc else str(doc.get("id"))
    return ConsultationSessionResponse(
        id=session_id,
        appointmentId=str(doc.get("appointmentId")),
        doctorUserId=str(doc.get("doctorUserId")),
        doctorProfileId=str(doc.get("doctorProfileId")),
        patientUserId=str(doc.get("patientUserId")),
        status=str(doc.get("status", ConsultationStatus.NOT_STARTED.value)),
        startedAt=doc.get("startedAt"),
        completedAt=doc.get("completedAt"),
        startedBy=doc.get("startedBy"),
        completedBy=doc.get("completedBy"),
        notes=doc.get("notes"),
        version=int(doc.get("version", 1)),
        createdAt=doc.get("createdAt", utc_now()),
        updatedAt=doc.get("updatedAt", utc_now()),
    )


class ConsultationService:
    """Service handling doctor schedule, next patient determination, and consultation lifecycles."""

    @classmethod
    def _verify_approved_doctor(cls, db: Database, doctor_user: UserResponseSchema) -> Dict[str, Any]:
        """Verify that the user is an active, approved doctor and return profile."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Only doctors can manage daily schedules and consultations.",
            )

        if doctor_user.accountStatus != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your doctor account is not active.",
            )

        doc_prof = db["doctor_profiles"].find_one({"userId": str(doctor_user.id)})
        if not doc_prof:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found.",
            )

        v_status = doc_prof.get("verificationStatus")
        if v_status != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Doctor registration status is {v_status}. Only approved doctors can access this feature.",
            )

        return doc_prof

    @classmethod
    def _verify_appointment_ownership(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        doc_prof: Dict[str, Any],
        appointment_id: str,
    ) -> Dict[str, Any]:
        """Verify appointment exists and belongs to the authenticated doctor."""
        if not ObjectId.is_valid(appointment_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid appointment ID format.",
            )

        appt = db["appointments"].find_one({"_id": ObjectId(appointment_id)})
        if not appt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )

        is_owner = (
            str(appt.get("doctorUserId")) == str(doctor_user.id)
            or str(appt.get("doctorProfileId")) == str(doc_prof["_id"])
            or str(appt.get("doctorId")) == str(doc_prof.get("doctorId"))
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to manage consultations for this appointment.",
            )

        return appt

    @classmethod
    async def get_doctor_daily_schedule(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        date_str: Optional[str] = None,
    ) -> DoctorDailyScheduleResponse:
        """Fetch chronological schedule, stats, and next patient for a given date."""
        doc_prof = cls._verify_approved_doctor(db, doctor_user)
        tz_str = _get_doctor_timezone_str(db, str(doctor_user.id))
        doctor_local_now = _get_doctor_local_now(db, str(doctor_user.id))

        if not date_str or not date_str.strip():
            date_str = doctor_local_now.strftime("%Y-%m-%d")
        else:
            date_str = date_str.strip()
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Expected YYYY-MM-DD.",
                )

        current_time_str = doctor_local_now.strftime("%H:%M")
        is_today = (date_str == doctor_local_now.strftime("%Y-%m-%d"))

        # Query appointments belonging to doctor for this date
        appt_query = {
            "$or": [
                {"doctorUserId": str(doctor_user.id)},
                {"doctorProfileId": str(doc_prof["_id"])},
                {"doctorId": str(doc_prof.get("doctorId"))},
            ],
            "appointmentDate": date_str,
        }
        appts = list(db["appointments"].find(appt_query).sort("startTime", ASCENDING))

        appt_ids = [str(a["_id"]) for a in appts]
        patient_ids = [str(a.get("patientUserId") or a.get("patientId")) for a in appts if (a.get("patientUserId") or a.get("patientId"))]

        # Batch lookup consultation sessions
        sessions_map = {}
        if appt_ids:
            sess_docs = list(db["consultation_sessions"].find({"appointmentId": {"$in": appt_ids}}))
            for s in sess_docs:
                sessions_map[str(s["appointmentId"])] = s

        # Batch lookup clinical records
        rx_map = {}
        mr_map = {}
        cp_map = {}
        if appt_ids:
            for r in db["prescriptions"].find({"appointmentId": {"$in": appt_ids}}):
                rx_map[str(r["appointmentId"])] = str(r["_id"])
            for m in db["medical_records"].find({"appointmentId": {"$in": appt_ids}}):
                mr_map[str(m["appointmentId"])] = str(m["_id"])
            for c in db["care_plans"].find({"appointmentId": {"$in": appt_ids}}):
                cp_map[str(c["appointmentId"])] = str(c["_id"])

        # Batch lookup patient user details
        patient_users_map = {}
        valid_patient_obj_ids = [ObjectId(p) for p in patient_ids if ObjectId.is_valid(p)]
        if valid_patient_obj_ids:
            for u in db["users"].find({"_id": {"$in": valid_patient_obj_ids}}):
                patient_users_map[str(u["_id"])] = u

        # Build schedule items
        schedule_items: List[ScheduleAppointmentItem] = []
        total_count = len(appts)
        cancelled_count = 0
        completed_count = 0
        in_progress_count = 0
        waiting_count = 0
        upcoming_count = 0

        for appt in appts:
            appt_id = str(appt["_id"])
            booking_status = str(appt.get("status", "PENDING")).upper()
            sess = sessions_map.get(appt_id)

            if sess:
                consultation_status = str(sess.get("status", ConsultationStatus.NOT_STARTED.value))
                started_at = sess.get("startedAt")
                completed_at = sess.get("completedAt")
                sess_id = str(sess["_id"])
            else:
                consultation_status = ConsultationStatus.COMPLETED.value if booking_status == "COMPLETED" else ConsultationStatus.NOT_STARTED.value
                started_at = None
                completed_at = None
                sess_id = None

            pat_id = str(appt.get("patientUserId") or appt.get("patientId") or "")
            pat_user = patient_users_map.get(pat_id)

            patient_name = appt.get("patientName") or (pat_user.get("fullName") if pat_user else "Patient")
            patient_email = appt.get("patientEmail") or (pat_user.get("email") if pat_user else None)
            patient_phone = appt.get("patientPhone") or (pat_user.get("phone") if pat_user else None)

            start_t = appt.get("startTime", "00:00")
            end_t = appt.get("endTime", "00:00")

            # Calculate statistics
            if booking_status == "CANCELLED":
                cancelled_count += 1
            elif consultation_status == ConsultationStatus.COMPLETED.value or booking_status == "COMPLETED":
                completed_count += 1
            elif consultation_status == ConsultationStatus.IN_PROGRESS.value:
                in_progress_count += 1
            else:
                # Active scheduled
                upcoming_count += 1
                if is_today and start_t <= current_time_str:
                    waiting_count += 1

            schedule_items.append(
                ScheduleAppointmentItem(
                    appointmentId=appt_id,
                    appointmentDate=str(appt.get("appointmentDate", date_str)),
                    startTime=start_t,
                    endTime=end_t,
                    bookingStatus=booking_status,
                    consultationStatus=consultation_status,
                    consultationFee=float(appt.get("consultationFee", 2500.0)),
                    patientUserId=pat_id,
                    patientName=patient_name,
                    patientEmail=patient_email,
                    patientPhone=patient_phone,
                    patientNote=appt.get("patientNote"),
                    consultationSessionId=sess_id,
                    startedAt=started_at,
                    completedAt=completed_at,
                    hasPrescription=appt_id in rx_map,
                    hasMedicalRecord=appt_id in mr_map,
                    hasCarePlan=appt_id in cp_map,
                    prescriptionId=rx_map.get(appt_id),
                    medicalRecordId=mr_map.get(appt_id),
                    carePlanId=cp_map.get(appt_id),
                )
            )

        # Determine next patient
        next_patient: Optional[ScheduleAppointmentItem] = None
        # 1. First priority: An in-progress consultation
        for item in schedule_items:
            if item.bookingStatus != "CANCELLED" and item.consultationStatus == ConsultationStatus.IN_PROGRESS.value:
                next_patient = item
                break

        # 2. Second priority: Earliest not-started, non-cancelled appointment
        if not next_patient:
            for item in schedule_items:
                if (
                    item.bookingStatus != "CANCELLED"
                    and item.consultationStatus == ConsultationStatus.NOT_STARTED.value
                    and item.bookingStatus in ["CONFIRMED", "PENDING"]
                ):
                    next_patient = item
                    break

        stats = DailyScheduleStats(
            date=date_str,
            timezone=tz_str,
            totalScheduled=total_count,
            upcoming=upcoming_count,
            waiting=waiting_count,
            inProgress=in_progress_count,
            completed=completed_count,
            cancelled=cancelled_count,
        )

        return DoctorDailyScheduleResponse(
            date=date_str,
            timezone=tz_str,
            stats=stats,
            nextPatient=next_patient,
            appointments=schedule_items,
        )

    @classmethod
    async def get_doctor_schedule_summary(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        date_str: Optional[str] = None,
    ) -> DailyScheduleStats:
        """Return daily appointment & consultation metrics for a date."""
        full_schedule = await cls.get_doctor_daily_schedule(db, doctor_user, date_str)
        return full_schedule.stats

    @classmethod
    async def get_consultation_details(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
    ) -> ConsultationDetailResponse:
        """Retrieve full consultation details and clinical linkages for an appointment."""
        doc_prof = cls._verify_approved_doctor(db, doctor_user)
        appt = cls._verify_appointment_ownership(db, doctor_user, doc_prof, appointment_id)

        appt_id = str(appt["_id"])
        sess = db["consultation_sessions"].find_one({"appointmentId": appt_id})
        booking_status = str(appt.get("status", "PENDING")).upper()

        if sess:
            consultation_status = str(sess.get("status", ConsultationStatus.NOT_STARTED.value))
            started_at = sess.get("startedAt")
            completed_at = sess.get("completedAt")
            sess_id = str(sess["_id"])
            session_resp = _doc_to_session_response(sess)
        else:
            consultation_status = ConsultationStatus.COMPLETED.value if booking_status == "COMPLETED" else ConsultationStatus.NOT_STARTED.value
            started_at = None
            completed_at = None
            sess_id = None
            session_resp = None

        pat_id = str(appt.get("patientUserId") or appt.get("patientId") or "")
        pat_user = db["users"].find_one({"_id": ObjectId(pat_id)}) if ObjectId.is_valid(pat_id) else None

        # Fetch clinical links
        rx = db["prescriptions"].find_one({"appointmentId": appt_id})
        mr = db["medical_records"].find_one({"appointmentId": appt_id})
        cp = db["care_plans"].find_one({"$or": [{"consultationAppointmentId": appt_id}, {"appointmentId": appt_id}]})

        rx_dict = {
            "id": str(rx["_id"]),
            "prescriptionId": rx.get("prescriptionId"),
            "medicationsCount": len(rx.get("medications", [])),
        } if rx else None

        mr_dict = {
            "id": str(mr["_id"]),
            "recordId": mr.get("recordId"),
            "assessment": mr.get("assessment"),
        } if mr else None

        cp_dict = {
            "id": str(cp["_id"]),
            "status": cp.get("status"),
            "followUpDate": cp.get("followUpDate"),
            "reason": cp.get("reason"),
        } if cp else None

        item = ScheduleAppointmentItem(
            appointmentId=appt_id,
            appointmentDate=str(appt.get("appointmentDate")),
            startTime=appt.get("startTime", "00:00"),
            endTime=appt.get("endTime", "00:00"),
            bookingStatus=booking_status,
            consultationStatus=consultation_status,
            consultationFee=float(appt.get("consultationFee", 2500.0)),
            patientUserId=pat_id,
            patientName=appt.get("patientName") or (pat_user.get("fullName") if pat_user else "Patient"),
            patientEmail=appt.get("patientEmail") or (pat_user.get("email") if pat_user else None),
            patientPhone=appt.get("patientPhone") or (pat_user.get("phone") if pat_user else None),
            patientNote=appt.get("patientNote"),
            consultationSessionId=sess_id,
            startedAt=started_at,
            completedAt=completed_at,
            hasPrescription=rx is not None,
            hasMedicalRecord=mr is not None,
            hasCarePlan=cp is not None,
            prescriptionId=str(rx["_id"]) if rx else None,
            medicalRecordId=str(mr["_id"]) if mr else None,
            carePlanId=str(cp["_id"]) if cp else None,
        )

        return ConsultationDetailResponse(
            appointment=item,
            session=session_resp,
            medicalRecord=mr_dict,
            prescription=rx_dict,
            carePlan=cp_dict,
        )

    @classmethod
    async def start_consultation(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
        notes: Optional[str] = None,
    ) -> ConsultationSessionResponse:
        """Start a consultation session for an appointment.

        Concurrency & Idempotency:
        - Re-calling while IN_PROGRESS returns the active session (double-tap safe).
        - Attempting to start a CANCELLED appointment raises 400 Bad Request.
        - Attempting to start a COMPLETED consultation raises 400 Bad Request.
        - Database unique index on appointmentId prevents duplicate session records.
        """
        doc_prof = cls._verify_approved_doctor(db, doctor_user)
        appt = cls._verify_appointment_ownership(db, doctor_user, doc_prof, appointment_id)

        appt_id = str(appt["_id"])
        booking_status = str(appt.get("status", "")).upper()

        if booking_status == AppointmentStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot start consultation for a cancelled appointment.",
            )

        coll = get_consultation_collection(db)
        existing = coll.find_one({"appointmentId": appt_id})

        now = utc_now()

        if existing:
            current_status = existing.get("status")
            if current_status == ConsultationStatus.COMPLETED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Consultation has already been completed.",
                )
            if current_status == ConsultationStatus.IN_PROGRESS.value:
                # Idempotent return for active consultation
                return _doc_to_session_response(existing)

            # Transition from NOT_STARTED to IN_PROGRESS
            coll.update_one(
                {"_id": existing["_id"], "status": ConsultationStatus.NOT_STARTED.value},
                {
                    "$set": {
                        "status": ConsultationStatus.IN_PROGRESS.value,
                        "startedAt": now,
                        "startedBy": str(doctor_user.id),
                        "notes": notes if notes else existing.get("notes"),
                        "updatedAt": now,
                    },
                    "$inc": {"version": 1},
                },
            )
            updated = coll.find_one({"_id": existing["_id"]})
            session_result = _doc_to_session_response(updated)
        else:
            # Create new consultation session
            pat_id = str(appt.get("patientUserId") or appt.get("patientId") or "")
            new_session = ConsultationSessionDocument(
                appointmentId=appt_id,
                doctorUserId=str(doctor_user.id),
                doctorProfileId=str(doc_prof["_id"]),
                patientUserId=pat_id,
                status=ConsultationStatus.IN_PROGRESS,
                startedAt=now,
                startedBy=str(doctor_user.id),
                notes=notes,
                version=1,
                createdAt=now,
                updatedAt=now,
            )
            try:
                res = coll.insert_one(new_session.to_mongo_dict())
                doc_dict = new_session.to_mongo_dict()
                doc_dict["_id"] = res.inserted_id
                session_result = _doc_to_session_response(doc_dict)
            except DuplicateKeyError:
                # Concurrency safety: Another worker inserted concurrently
                concurrent_doc = coll.find_one({"appointmentId": appt_id})
                session_result = _doc_to_session_response(concurrent_doc)

        # Synchronize booking status to CONFIRMED if it was PENDING
        if booking_status == AppointmentStatus.PENDING.value:
            db["appointments"].update_one(
                {"_id": ObjectId(appt_id)},
                {"$set": {"status": AppointmentStatus.CONFIRMED.value, "updatedAt": now}},
            )

        return session_result

    @classmethod
    async def complete_consultation(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: str,
        notes: Optional[str] = None,
    ) -> ConsultationSessionResponse:
        """Mark a consultation session as completed.

        Rules:
        - Only assigned approved doctor can complete.
        - Consultation must have been started (IN_PROGRESS).
        - Calling complete on an already COMPLETED session is idempotent.
        - Synchronizes appointment booking status to COMPLETED.
        """
        doc_prof = cls._verify_approved_doctor(db, doctor_user)
        appt = cls._verify_appointment_ownership(db, doctor_user, doc_prof, appointment_id)

        appt_id = str(appt["_id"])
        coll = get_consultation_collection(db)
        existing = coll.find_one({"appointmentId": appt_id})

        if not existing or existing.get("status") == ConsultationStatus.NOT_STARTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consultation has not been started yet. Please start consultation before completing it.",
            )

        if existing.get("status") == ConsultationStatus.COMPLETED.value:
            # Idempotent response
            return _doc_to_session_response(existing)

        now = utc_now()
        coll.update_one(
            {"_id": existing["_id"], "status": ConsultationStatus.IN_PROGRESS.value},
            {
                "$set": {
                    "status": ConsultationStatus.COMPLETED.value,
                    "completedAt": now,
                    "completedBy": str(doctor_user.id),
                    "notes": notes if notes else existing.get("notes"),
                    "updatedAt": now,
                },
                "$inc": {"version": 1},
            },
        )

        updated = coll.find_one({"_id": existing["_id"]})

        # Synchronize appointment status to COMPLETED
        db["appointments"].update_one(
            {"_id": ObjectId(appt_id)},
            {"$set": {"status": AppointmentStatus.COMPLETED.value, "updatedAt": now}},
        )

        return _doc_to_session_response(updated)
