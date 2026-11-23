"""Patient Healthcare Timeline & Visit History Service (Phase 58).

Aggregates real clinical, visit, prescription, medical record, and follow-up care plan
data into a patient-safe, reverse-chronological healthcare journey.
"""

import base64
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Set
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.appointment import AppointmentStatus
from app.models.care_plan import CarePlanStatus
from app.models.consultation import ConsultationStatus
from app.schemas.timeline import (
    TimelineAction,
    TimelineCategory,
    TimelineEvent,
    TimelineEventType,
    TimelineResponse,
    TimelineSummaryResponse,
    VisitDetailResponse,
)
from app.schemas.user import UserResponseSchema

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_datetime_utc(val: Any) -> datetime:
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return _utc_now()


def _decode_cursor(cursor: Optional[str]) -> int:
    """Decode offset cursor."""
    if not cursor or not cursor.strip():
        return 0
    try:
        raw = cursor.strip()
        if raw.startswith("offset_"):
            return max(0, int(raw.split("_")[1]))
        # Base64 fallback
        decoded = base64.b64decode(raw.encode()).decode()
        return max(0, int(decoded))
    except Exception:
        return 0


def _encode_cursor(offset: int) -> str:
    """Encode offset to a stable cursor string."""
    return f"offset_{offset}"


class PatientTimelineService:
    """Read-only clinical aggregation service powering the patient healthcare timeline."""

    @classmethod
    async def get_patient_timeline(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        category: TimelineCategory = TimelineCategory.ALL,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        doctor_id: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> TimelineResponse:
        """Fetch normalized, patient-safe timeline events in reverse chronological order."""
        patient_user_id = str(patient_user.id)
        limit = max(1, min(limit, 100))
        offset = _decode_cursor(cursor)

        events: List[TimelineEvent] = []
        doctor_user_ids: Set[str] = set()

        # 1. Fetch relevant collections based on requested category
        should_fetch_appts = category in (TimelineCategory.ALL, TimelineCategory.APPOINTMENTS, TimelineCategory.CONSULTATIONS)
        should_fetch_consultations = category in (TimelineCategory.ALL, TimelineCategory.CONSULTATIONS)
        should_fetch_prescriptions = category in (TimelineCategory.ALL, TimelineCategory.PRESCRIPTIONS)
        should_fetch_records = category in (TimelineCategory.ALL, TimelineCategory.MEDICAL_RECORDS)
        should_fetch_care_plans = category in (TimelineCategory.ALL, TimelineCategory.FOLLOW_UPS)

        appts_list: List[Dict[str, Any]] = []
        if should_fetch_appts:
            appt_filter: Dict[str, Any] = {"patientUserId": patient_user_id}
            if doctor_id:
                appt_filter["doctorUserId"] = doctor_id
            appts_list = list(db["appointments"].find(appt_filter).sort("createdAt", -1))
            for a in appts_list:
                if a.get("doctorUserId"):
                    doctor_user_ids.add(str(a["doctorUserId"]))

        sessions_list: List[Dict[str, Any]] = []
        if should_fetch_consultations:
            sess_filter: Dict[str, Any] = {"patientUserId": patient_user_id}
            if doctor_id:
                sess_filter["doctorUserId"] = doctor_id
            sessions_list = list(db["consultation_sessions"].find(sess_filter))
            for s in sessions_list:
                if s.get("doctorUserId"):
                    doctor_user_ids.add(str(s["doctorUserId"]))

        prescriptions_list: List[Dict[str, Any]] = []
        if should_fetch_prescriptions:
            rx_filter: Dict[str, Any] = {"patientUserId": patient_user_id}
            if doctor_id:
                rx_filter["doctorUserId"] = doctor_id
            prescriptions_list = list(db["prescriptions"].find(rx_filter).sort("issuedAt", -1))
            for rx in prescriptions_list:
                if rx.get("doctorUserId"):
                    doctor_user_ids.add(str(rx["doctorUserId"]))

        records_list: List[Dict[str, Any]] = []
        if should_fetch_records:
            mr_filter: Dict[str, Any] = {"patientUserId": patient_user_id}
            if doctor_id:
                mr_filter["doctorUserId"] = doctor_id
            records_list = list(db["medical_records"].find(mr_filter).sort("createdAt", -1))
            for mr in records_list:
                if mr.get("doctorUserId"):
                    doctor_user_ids.add(str(mr["doctorUserId"]))

        care_plans_list: List[Dict[str, Any]] = []
        if should_fetch_care_plans:
            cp_filter: Dict[str, Any] = {"patientUserId": patient_user_id}
            if doctor_id:
                cp_filter["doctorUserId"] = doctor_id
            care_plans_list = list(db["care_plans"].find(cp_filter).sort("createdAt", -1))
            for cp in care_plans_list:
                if cp.get("doctorUserId"):
                    doctor_user_ids.add(str(cp["doctorUserId"]))

        # 2. Batch resolve Doctor Profiles and User information
        doctor_info_map: Dict[str, Dict[str, Optional[str]]] = {}
        if doctor_user_ids:
            doc_obj_ids = [ObjectId(d_id) for d_id in doctor_user_ids if ObjectId.is_valid(d_id)]
            doc_users = {str(u["_id"]): u for u in db["users"].find({"_id": {"$in": doc_obj_ids}})}
            doc_profiles = {str(p["userId"]): p for p in db["doctor_profiles"].find({"userId": {"$in": list(doctor_user_ids)}})}

            for d_id in doctor_user_ids:
                u = doc_users.get(d_id, {})
                p = doc_profiles.get(d_id, {})
                doctor_info_map[d_id] = {
                    "name": p.get("fullName") or u.get("fullName") or f"Dr. Medical Specialist",
                    "specialty": p.get("specialty"),
                    "hospitalOrClinic": p.get("hospitalOrClinic"),
                }

        # 3. Build lookup of sessions by appointmentId
        session_by_appt: Dict[str, Dict[str, Any]] = {}
        for s in sessions_list:
            appt_ref = str(s.get("appointmentId") or "")
            if appt_ref:
                session_by_appt[appt_ref] = s

        # 4. Generate events from Appointments
        if should_fetch_appts:
            for appt in appts_list:
                appt_id = str(appt["_id"])
                d_id = str(appt.get("doctorUserId") or "")
                doc_meta = doctor_info_map.get(d_id, {})
                doc_name = appt.get("doctorName") or doc_meta.get("name") or "Your Doctor"
                doc_specialty = doc_meta.get("specialty")
                hospital = doc_meta.get("hospitalOrClinic")
                appt_date = str(appt.get("appointmentDate", ""))
                start_time = str(appt.get("startTime", ""))
                booking_status = str(appt.get("status", "PENDING")).upper()
                created_at = _ensure_datetime_utc(appt.get("createdAt"))
                updated_at = _ensure_datetime_utc(appt.get("updatedAt") or appt.get("createdAt"))
                version = int(appt.get("appointmentVersion", 1))

                # A. APPOINTMENT_BOOKED
                if category in (TimelineCategory.ALL, TimelineCategory.APPOINTMENTS):
                    events.append(
                        TimelineEvent(
                            eventId=f"appt_{appt_id}_booked",
                            eventType=TimelineEventType.APPOINTMENT_BOOKED.value,
                            category=TimelineCategory.APPOINTMENTS.value,
                            occurredAt=created_at,
                            displayDate=appt_date or created_at.strftime("%Y-%m-%d"),
                            displayTime=start_time,
                            title=f"Appointment Booked with {doc_name}",
                            description=f"Scheduled visit for {appt_date} at {start_time}. Status: {booking_status}.",
                            doctorUserId=d_id,
                            doctorDisplayName=doc_name,
                            doctorSpecialty=doc_specialty,
                            hospitalOrClinic=hospital,
                            sourceType="appointment",
                            sourceId=appt_id,
                            appointmentId=appt_id,
                            status=booking_status,
                            availableActions=[TimelineAction.VIEW_APPOINTMENT.value, TimelineAction.VIEW_VISIT.value],
                            metadata={
                                "appointmentNumber": appt.get("appointmentNumber"),
                                "reasonForVisit": appt.get("patientNote"),
                                "fee": float(appt.get("consultationFee", 2500.0)),
                            },
                        )
                    )

                # B. APPOINTMENT_CANCELLED
                if booking_status == AppointmentStatus.CANCELLED.value and category in (TimelineCategory.ALL, TimelineCategory.APPOINTMENTS):
                    canc_reason = appt.get("cancellationReason")
                    canc_by = appt.get("cancelledBy") or "Patient"
                    reason_desc = f" Reason: {canc_reason}." if canc_reason else ""
                    events.append(
                        TimelineEvent(
                            eventId=f"appt_{appt_id}_cancelled",
                            eventType=TimelineEventType.APPOINTMENT_CANCELLED.value,
                            category=TimelineCategory.APPOINTMENTS.value,
                            occurredAt=updated_at,
                            displayDate=updated_at.strftime("%Y-%m-%d"),
                            displayTime=updated_at.strftime("%H:%M"),
                            title=f"Appointment Cancelled ({doc_name})",
                            description=f"Appointment scheduled for {appt_date} was cancelled by {canc_by}.{reason_desc}",
                            doctorUserId=d_id,
                            doctorDisplayName=doc_name,
                            doctorSpecialty=doc_specialty,
                            hospitalOrClinic=hospital,
                            sourceType="appointment",
                            sourceId=appt_id,
                            appointmentId=appt_id,
                            status="CANCELLED",
                            availableActions=[TimelineAction.VIEW_APPOINTMENT.value, TimelineAction.VIEW_VISIT.value],
                            metadata={
                                "cancelledBy": canc_by,
                                "cancellationReason": canc_reason,
                            },
                        )
                    )

                # C. APPOINTMENT_RESCHEDULED (only when verified history exists)
                if version > 1 and category in (TimelineCategory.ALL, TimelineCategory.APPOINTMENTS):
                    events.append(
                        TimelineEvent(
                            eventId=f"appt_{appt_id}_rescheduled_v{version}",
                            eventType=TimelineEventType.APPOINTMENT_RESCHEDULED.value,
                            category=TimelineCategory.APPOINTMENTS.value,
                            occurredAt=updated_at,
                            displayDate=appt_date,
                            displayTime=start_time,
                            title=f"Appointment Rescheduled ({doc_name})",
                            description=f"Appointment was rescheduled to {appt_date} at {start_time}.",
                            doctorUserId=d_id,
                            doctorDisplayName=doc_name,
                            doctorSpecialty=doc_specialty,
                            hospitalOrClinic=hospital,
                            sourceType="appointment",
                            sourceId=appt_id,
                            appointmentId=appt_id,
                            status=booking_status,
                            availableActions=[TimelineAction.VIEW_APPOINTMENT.value, TimelineAction.VIEW_VISIT.value],
                            metadata={"version": version},
                        )
                    )

                # D. APPOINTMENT_COMPLETED (if no consultation session completed event exists)
                sess = session_by_appt.get(appt_id)
                has_completed_session = sess and sess.get("status") == ConsultationStatus.COMPLETED.value
                if booking_status == AppointmentStatus.COMPLETED.value and not has_completed_session:
                    if category in (TimelineCategory.ALL, TimelineCategory.CONSULTATIONS):
                        events.append(
                            TimelineEvent(
                                eventId=f"appt_{appt_id}_completed",
                                eventType=TimelineEventType.APPOINTMENT_COMPLETED.value,
                                category=TimelineCategory.CONSULTATIONS.value,
                                occurredAt=updated_at,
                                displayDate=appt_date,
                                displayTime=start_time,
                                title=f"Consultation Completed with {doc_name}",
                                description=f"Appointment visit for {appt_date} concluded successfully.",
                                doctorUserId=d_id,
                                doctorDisplayName=doc_name,
                                doctorSpecialty=doc_specialty,
                                hospitalOrClinic=hospital,
                                sourceType="appointment",
                                sourceId=appt_id,
                                appointmentId=appt_id,
                                status="COMPLETED",
                                availableActions=[TimelineAction.VIEW_VISIT.value],
                                metadata={},
                            )
                        )

        # 5. Generate events from Consultation Sessions
        if should_fetch_consultations:
            for sess in sessions_list:
                sess_status = str(sess.get("status", "NOT_STARTED")).upper()
                if sess_status == ConsultationStatus.COMPLETED.value:
                    sess_id = str(sess["_id"])
                    appt_id = str(sess.get("appointmentId") or "")
                    d_id = str(sess.get("doctorUserId") or "")
                    doc_meta = doctor_info_map.get(d_id, {})
                    doc_name = doc_meta.get("name") or "Your Doctor"
                    completed_at = _ensure_datetime_utc(sess.get("completedAt") or sess.get("updatedAt"))

                    events.append(
                        TimelineEvent(
                            eventId=f"sess_{sess_id}_completed",
                            eventType=TimelineEventType.CONSULTATION_COMPLETED.value,
                            category=TimelineCategory.CONSULTATIONS.value,
                            occurredAt=completed_at,
                            displayDate=completed_at.strftime("%Y-%m-%d"),
                            displayTime=completed_at.strftime("%H:%M"),
                            title=f"Doctor Consultation Completed ({doc_name})",
                            description=f"Consultation with {doc_name} was completed.",
                            doctorUserId=d_id,
                            doctorDisplayName=doc_name,
                            doctorSpecialty=doc_meta.get("specialty"),
                            hospitalOrClinic=doc_meta.get("hospitalOrClinic"),
                            sourceType="consultation",
                            sourceId=sess_id,
                            appointmentId=appt_id,
                            status="COMPLETED",
                            availableActions=[TimelineAction.VIEW_VISIT.value],
                            metadata={
                                "durationMinutes": 15,
                            },
                        )
                    )

        # 6. Generate events from Digital Prescriptions
        if should_fetch_prescriptions:
            for rx in prescriptions_list:
                rx_id = str(rx["_id"])
                appt_id = str(rx.get("appointmentId") or "")
                d_id = str(rx.get("doctorUserId") or "")
                doc_meta = doctor_info_map.get(d_id, {})
                doc_name = doc_meta.get("name") or "Your Doctor"
                issued_at = _ensure_datetime_utc(rx.get("issuedAt") or rx.get("createdAt"))
                med_items = rx.get("medicationItems", []) or rx.get("medications", [])
                med_count = len(med_items)
                rx_ref = rx.get("prescriptionId") or f"RX-{rx_id[:8]}"

                events.append(
                    TimelineEvent(
                        eventId=f"rx_{rx_id}_issued",
                        eventType=TimelineEventType.PRESCRIPTION_ISSUED.value,
                        category=TimelineCategory.PRESCRIPTIONS.value,
                        occurredAt=issued_at,
                        displayDate=issued_at.strftime("%Y-%m-%d"),
                        displayTime=issued_at.strftime("%H:%M"),
                        title=f"Digital Prescription Issued ({rx_ref})",
                        description=f"{med_count} medication(s) prescribed by {doc_name}.",
                        doctorUserId=d_id,
                        doctorDisplayName=doc_name,
                        doctorSpecialty=doc_meta.get("specialty"),
                        hospitalOrClinic=doc_meta.get("hospitalOrClinic"),
                        sourceType="prescription",
                        sourceId=rx_id,
                        appointmentId=appt_id,
                        status=str(rx.get("status", "ISSUED")),
                        availableActions=[TimelineAction.VIEW_PRESCRIPTION.value, TimelineAction.VIEW_VISIT.value],
                        metadata={
                            "prescriptionId": rx_ref,
                            "medicationsCount": med_count,
                        },
                    )
                )

        # 7. Generate events from Medical Records (excluding confidential doctor-only clinicalNotes)
        if should_fetch_records:
            for mr in records_list:
                mr_id = str(mr["_id"])
                appt_id = str(mr.get("appointmentId") or "")
                d_id = str(mr.get("doctorUserId") or "")
                doc_meta = doctor_info_map.get(d_id, {})
                doc_name = doc_meta.get("name") or "Your Doctor"
                created_at = _ensure_datetime_utc(mr.get("createdAt"))
                rec_ref = mr.get("recordId") or f"REC-{mr_id[:8]}"
                safe_assessment = str(mr.get("assessment") or "Consultation clinical assessment recorded.")[:160]

                events.append(
                    TimelineEvent(
                        eventId=f"mr_{mr_id}_added",
                        eventType=TimelineEventType.MEDICAL_RECORD_ADDED.value,
                        category=TimelineCategory.MEDICAL_RECORDS.value,
                        occurredAt=created_at,
                        displayDate=str(mr.get("consultationDate") or created_at.strftime("%Y-%m-%d")),
                        displayTime=created_at.strftime("%H:%M"),
                        title=f"Medical Consultation Record ({rec_ref})",
                        description=f"Assessment: {safe_assessment}",
                        doctorUserId=d_id,
                        doctorDisplayName=doc_name,
                        doctorSpecialty=doc_meta.get("specialty"),
                        hospitalOrClinic=doc_meta.get("hospitalOrClinic"),
                        sourceType="medical_record",
                        sourceId=mr_id,
                        appointmentId=appt_id,
                        status=str(mr.get("status", "ACTIVE")),
                        availableActions=[TimelineAction.VIEW_MEDICAL_RECORD.value, TimelineAction.VIEW_VISIT.value],
                        metadata={
                            "recordId": rec_ref,
                        },
                    )
                )

        # 8. Generate events from Follow-up Care Plans (Phase 56)
        if should_fetch_care_plans:
            for cp in care_plans_list:
                cp_id = str(cp["_id"])
                appt_id = str(cp.get("appointmentId") or cp.get("consultationAppointmentId") or "")
                d_id = str(cp.get("doctorUserId") or "")
                doc_meta = doctor_info_map.get(d_id, {})
                doc_name = doc_meta.get("name") or "Your Doctor"
                created_at = _ensure_datetime_utc(cp.get("createdAt"))
                updated_at = _ensure_datetime_utc(cp.get("updatedAt") or cp.get("createdAt"))
                follow_up_date = str(cp.get("followUpDate") or "")
                plan_status = str(cp.get("status", "ACTIVE")).upper()
                reason = cp.get("reason") or "Follow-up review"
                tasks = cp.get("tasks", [])

                # A. FOLLOW_UP_PLAN_CREATED
                events.append(
                    TimelineEvent(
                        eventId=f"cp_{cp_id}_created",
                        eventType=TimelineEventType.FOLLOW_UP_PLAN_CREATED.value,
                        category=TimelineCategory.FOLLOW_UPS.value,
                        occurredAt=created_at,
                        displayDate=created_at.strftime("%Y-%m-%d"),
                        displayTime=created_at.strftime("%H:%M"),
                        title=f"Follow-up Care Plan Created ({doc_name})",
                        description=f"Target follow-up date: {follow_up_date}. Reason: {reason}.",
                        doctorUserId=d_id,
                        doctorDisplayName=doc_name,
                        doctorSpecialty=doc_meta.get("specialty"),
                        hospitalOrClinic=doc_meta.get("hospitalOrClinic"),
                        sourceType="care_plan",
                        sourceId=cp_id,
                        appointmentId=appt_id,
                        status=plan_status,
                        availableActions=[TimelineAction.VIEW_CARE_PLAN.value, TimelineAction.VIEW_VISIT.value],
                        metadata={
                            "followUpDate": follow_up_date,
                            "tasksCount": len(tasks),
                            "recommendedType": cp.get("recommendedConsultationType", "IN_PERSON"),
                        },
                    )
                )

                # B. FOLLOW_UP_BOOKED
                if plan_status == CarePlanStatus.FOLLOW_UP_BOOKED.value or cp.get("bookedAppointmentId") or cp.get("bookedFollowUpAppointmentId"):
                    booked_at = updated_at
                    # Inspect audit log for exact APPOINTMENT_LINKED timestamp if available
                    for entry in cp.get("auditLog", []):
                        if entry.get("action") == "APPOINTMENT_LINKED" and entry.get("timestamp"):
                            booked_at = _ensure_datetime_utc(entry.get("timestamp"))
                            break

                    events.append(
                        TimelineEvent(
                            eventId=f"cp_{cp_id}_booked",
                            eventType=TimelineEventType.FOLLOW_UP_BOOKED.value,
                            category=TimelineCategory.FOLLOW_UPS.value,
                            occurredAt=booked_at,
                            displayDate=booked_at.strftime("%Y-%m-%d"),
                            displayTime=booked_at.strftime("%H:%M"),
                            title="Follow-up Appointment Confirmed",
                            description=f"Confirmed follow-up consultation booked for Care Plan.",
                            doctorUserId=d_id,
                            doctorDisplayName=doc_name,
                            doctorSpecialty=doc_meta.get("specialty"),
                            hospitalOrClinic=doc_meta.get("hospitalOrClinic"),
                            sourceType="care_plan",
                            sourceId=cp_id,
                            appointmentId=appt_id,
                            status="FOLLOW_UP_BOOKED",
                            availableActions=[TimelineAction.VIEW_CARE_PLAN.value, TimelineAction.VIEW_APPOINTMENT.value],
                            metadata={
                                "followUpDate": follow_up_date,
                                "bookedAppointmentId": str(cp.get("bookedAppointmentId") or cp.get("bookedFollowUpAppointmentId") or ""),
                            },
                        )
                    )

        # 9. Deduplicate by eventId
        unique_events: Dict[str, TimelineEvent] = {}
        for ev in events:
            unique_events[ev.eventId] = ev
        all_events = list(unique_events.values())

        # 10. Filter by date range if provided
        if from_date and from_date.strip():
            fd = from_date.strip()
            all_events = [e for e in all_events if e.displayDate >= fd or e.occurredAt.strftime("%Y-%m-%d") >= fd]
        if to_date and to_date.strip():
            td = to_date.strip()
            all_events = [e for e in all_events if e.displayDate <= td or e.occurredAt.strftime("%Y-%m-%d") <= td]

        # 11. Filter by doctor if provided
        if doctor_id and doctor_id.strip():
            doc_target = doctor_id.strip()
            all_events = [e for e in all_events if e.doctorUserId == doc_target]

        # 12. Sort deterministically: reverse chronological order (newest first)
        # Using (occurredAt, eventId) ensures stable ordering across pagination boundaries
        all_events.sort(key=lambda x: (x.occurredAt, x.eventId), reverse=True)

        total_count = len(all_events)
        sliced_events = all_events[offset : offset + limit]
        has_more = (offset + limit) < total_count
        next_cursor = _encode_cursor(offset + limit) if has_more else None

        return TimelineResponse(
            events=sliced_events,
            nextCursor=next_cursor,
            totalCount=total_count,
            hasMore=has_more,
        )

    @classmethod
    async def get_patient_timeline_summary(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
    ) -> TimelineSummaryResponse:
        """Calculate quick KPI metrics for patient healthcare journey."""
        patient_user_id = str(patient_user.id)
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Upcoming appointments
        upcoming_count = db["appointments"].count_documents({
            "patientUserId": patient_user_id,
            "status": {"$in": [AppointmentStatus.CONFIRMED.value, AppointmentStatus.PENDING.value]},
            "appointmentDate": {"$gte": today_str},
        })

        # Completed consultations
        completed_sessions_count = db["consultation_sessions"].count_documents({
            "patientUserId": patient_user_id,
            "status": ConsultationStatus.COMPLETED.value,
        })
        completed_appts_count = db["appointments"].count_documents({
            "patientUserId": patient_user_id,
            "status": AppointmentStatus.COMPLETED.value,
        })
        completed_count = max(completed_sessions_count, completed_appts_count)

        # Prescriptions
        prescriptions_count = db["prescriptions"].count_documents({
            "patientUserId": patient_user_id,
        })

        # Medical Records
        records_count = db["medical_records"].count_documents({
            "patientUserId": patient_user_id,
        })

        # Active Care Plans
        active_care_plans_count = db["care_plans"].count_documents({
            "patientUserId": patient_user_id,
            "status": {"$in": [CarePlanStatus.ACTIVE.value, CarePlanStatus.FOLLOW_UP_BOOKED.value]},
        })

        # Total events estimation
        total_events = (
            db["appointments"].count_documents({"patientUserId": patient_user_id})
            + completed_sessions_count
            + prescriptions_count
            + records_count
            + active_care_plans_count
        )

        return TimelineSummaryResponse(
            totalEvents=total_events,
            upcomingAppointmentsCount=upcoming_count,
            completedConsultationsCount=completed_count,
            prescriptionsCount=prescriptions_count,
            medicalRecordsCount=records_count,
            activeCarePlansCount=active_care_plans_count,
        )

    @classmethod
    async def get_patient_visit_detail(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        appointment_id: str,
    ) -> VisitDetailResponse:
        """Consolidate full patient-authorized visit details for a specific appointment."""
        patient_user_id = str(patient_user.id)

        if not ObjectId.is_valid(appointment_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )

        appt = db["appointments"].find_one({"_id": ObjectId(appointment_id)})
        if not appt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )

        # Ownership authorization check: Patient can only view their own visit details
        if str(appt.get("patientUserId")) != patient_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this visit.",
            )

        d_id = str(appt.get("doctorUserId") or "")
        doc_user = db["users"].find_one({"_id": ObjectId(d_id)}) if ObjectId.is_valid(d_id) else None
        doc_prof = db["doctor_profiles"].find_one({"userId": d_id}) if d_id else None

        doc_name = appt.get("doctorName") or (doc_prof.get("fullName") if doc_prof else None) or (doc_user.get("fullName") if doc_user else "Doctor")
        doc_spec = doc_prof.get("specialty") if doc_prof else None
        doc_hosp = doc_prof.get("hospitalOrClinic") if doc_prof else None

        # Fetch Consultation Session (Phase 57)
        sess = db["consultation_sessions"].find_one({"appointmentId": appointment_id})
        sess_dict = {
            "id": str(sess["_id"]),
            "status": sess.get("status"),
            "startedAt": sess.get("startedAt"),
            "completedAt": sess.get("completedAt"),
        } if sess else None

        # Fetch Digital Prescription (Phase 44)
        rx = db["prescriptions"].find_one({"appointmentId": appointment_id})
        rx_dict = {
            "id": str(rx["_id"]),
            "prescriptionId": rx.get("prescriptionId"),
            "status": rx.get("status"),
            "issuedAt": rx.get("issuedAt"),
            "medicationsCount": len(rx.get("medicationItems", []) or rx.get("medications", [])),
            "instructions": rx.get("instructions"),
        } if rx else None

        # Fetch Medical Record (Phase 47) - Patient-safe: Exclude confidential doctor notes!
        mr = db["medical_records"].find_one({"appointmentId": appointment_id})
        mr_dict = {
            "id": str(mr["_id"]),
            "recordId": mr.get("recordId"),
            "consultationDate": mr.get("consultationDate"),
            "assessment": mr.get("assessment"),
            "treatmentPlan": mr.get("treatmentPlan"),
            "followUpInstructions": mr.get("followUpInstructions"),
            "status": mr.get("status"),
        } if mr else None

        # Fetch Care Plan (Phase 56)
        cp = db["care_plans"].find_one({
            "$or": [{"appointmentId": appointment_id}, {"consultationAppointmentId": appointment_id}]
        })
        cp_dict = {
            "id": str(cp["_id"]),
            "status": cp.get("status"),
            "followUpDate": cp.get("followUpDate"),
            "reason": cp.get("reason"),
            "instructions": cp.get("instructions"),
            "tasksCount": len(cp.get("tasks", [])),
            "recommendedConsultationType": cp.get("recommendedConsultationType"),
        } if cp else None

        # Related timeline events for this appointment
        visit_events_res = await cls.get_patient_timeline(
            db=db,
            patient_user=patient_user,
            category=TimelineCategory.ALL,
            limit=50,
        )
        visit_events = [e for e in visit_events_res.events if e.appointmentId == appointment_id]

        booking_status = str(appt.get("status", "PENDING")).upper()
        consultation_status = (
            str(sess.get("status", "NOT_STARTED")).upper()
            if sess
            else ("COMPLETED" if booking_status == "COMPLETED" else "NOT_STARTED")
        )

        return VisitDetailResponse(
            appointmentId=appointment_id,
            appointmentNumber=appt.get("appointmentNumber"),
            appointmentDate=str(appt.get("appointmentDate", "")),
            startTime=str(appt.get("startTime", "")),
            endTime=str(appt.get("endTime", "")),
            bookingStatus=booking_status,
            consultationStatus=consultation_status,
            consultationFee=float(appt.get("consultationFee", 2500.0)),
            doctorUserId=d_id,
            doctorName=doc_name,
            doctorSpecialty=doc_spec,
            doctorHospital=doc_hosp,
            patientNote=appt.get("patientNote"),
            cancelledBy=appt.get("cancelledBy"),
            cancellationReason=appt.get("cancellationReason"),
            consultationSession=sess_dict,
            prescription=rx_dict,
            medicalRecord=mr_dict,
            carePlan=cp_dict,
            timelineEvents=visit_events,
        )

