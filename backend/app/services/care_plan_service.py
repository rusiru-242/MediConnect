"""Service layer for Smart Follow-up Care Plans (Phase 56)."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.appointment import AppointmentStatus
from app.models.care_plan import (
    CarePlanAuditEntry,
    CarePlanDocument,
    CarePlanStatus,
    CareTask,
    get_care_plan_collection,
    utc_now,
)
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.notification import NotificationType
from app.models.user import AccountStatus, UserRole
from app.schemas.care_plan import (
    CancelCarePlanRequest,
    CarePlanAuditEntrySchema,
    CarePlanListResponse,
    CarePlanResponse,
    CareTaskSchema,
    CreateCarePlanRequest,
    LinkAppointmentRequest,
    UpdateCarePlanRequest,
    UpdateTaskStatusRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.doctor_service import get_sl_now, get_sl_today_str
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def _doc_to_response(db: Database, doc: Dict[str, Any]) -> CarePlanResponse:
    """Convert MongoDB care plan document to Pydantic CarePlanResponse with enriched metadata."""
    plan_id = str(doc["_id"]) if "_id" in doc else str(doc.get("id"))
    pat_id = str(doc.get("patientUserId"))
    doc_user_id = str(doc.get("doctorUserId"))
    doc_prof_id = str(doc.get("doctorProfileId"))

    # Enrich patient name
    pat_user = db["users"].find_one({"_id": ObjectId(pat_id)}) if ObjectId.is_valid(pat_id) else None
    patient_name = pat_user.get("fullName") if pat_user else "Patient"

    # Enrich doctor profile
    doc_prof = None
    if ObjectId.is_valid(doc_prof_id):
        doc_prof = db["doctor_profiles"].find_one({"_id": ObjectId(doc_prof_id)})
    if not doc_prof and ObjectId.is_valid(doc_user_id):
        doc_prof = db["doctor_profiles"].find_one({"userId": doc_user_id})

    doctor_name = doc_prof.get("fullName") if doc_prof else "Doctor"
    doctor_specialty = doc_prof.get("specialty") if doc_prof else None
    doctor_hospital = doc_prof.get("hospitalOrClinic") if doc_prof else None

    # Enrich consultation date
    appt_id = str(doc.get("appointmentId"))
    consultation_date = None
    if ObjectId.is_valid(appt_id):
        appt = db["appointments"].find_one({"_id": ObjectId(appt_id)})
        if appt:
            consultation_date = appt.get("appointmentDate")

    tasks_out: List[CareTaskSchema] = []
    for t in doc.get("tasks", []):
        tasks_out.append(
            CareTaskSchema(
                taskId=str(t.get("taskId")),
                title=t.get("title", ""),
                description=t.get("description"),
                isCompleted=bool(t.get("isCompleted", False)),
                completedAt=t.get("completedAt"),
            )
        )

    audit_out: List[CarePlanAuditEntrySchema] = []
    for a in doc.get("auditLog", []):
        audit_out.append(
            CarePlanAuditEntrySchema(
                action=a.get("action", ""),
                performedBy=str(a.get("performedBy", "")),
                performedByRole=a.get("performedByRole", "SYSTEM"),
                timestamp=a.get("timestamp", utc_now()),
                note=a.get("note"),
            )
        )

    return CarePlanResponse(
        id=plan_id,
        patientUserId=pat_id,
        patientName=patient_name,
        doctorUserId=doc_user_id,
        doctorProfileId=doc_prof_id,
        doctorName=doctor_name,
        doctorSpecialty=doctor_specialty,
        doctorHospital=doctor_hospital,
        appointmentId=appt_id,
        consultationDate=consultation_date,
        followUpDate=doc.get("followUpDate", ""),
        followUpDateEnd=doc.get("followUpDateEnd"),
        reason=doc.get("reason", ""),
        instructions=doc.get("instructions", ""),
        recommendedConsultationType=doc.get("recommendedConsultationType", "IN_PERSON"),
        tasks=tasks_out,
        linkedPrescriptionIds=[str(p) for p in doc.get("linkedPrescriptionIds", [])],
        linkedMedicalRecordIds=[str(r) for r in doc.get("linkedMedicalRecordIds", [])],
        bookedAppointmentId=str(doc.get("bookedAppointmentId")) if doc.get("bookedAppointmentId") else None,
        status=str(doc.get("status", CarePlanStatus.ACTIVE.value)),
        version=int(doc.get("version", 1)),
        createdBy=str(doc.get("createdBy", "")),
        updatedBy=str(doc.get("updatedBy", "")),
        auditLog=audit_out,
        remindersSent=[str(r) for r in doc.get("remindersSent", [])],
        createdAt=doc.get("createdAt", utc_now()),
        updatedAt=doc.get("updatedAt", utc_now()),
    )


class CarePlanService:
    """Business logic for Smart Follow-up Care Plans."""

    @classmethod
    async def create_care_plan(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        req: CreateCarePlanRequest,
    ) -> CarePlanResponse:
        """Create a new follow-up care plan for an eligible consultation."""
        # 1. Authorization: Authenticated doctor with APPROVED verification status
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only doctors can create follow-up care plans.",
            )

        if doctor_user.accountStatus != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your doctor account is not active.",
            )

        doc_prof = db["doctor_profiles"].find_one({"userId": str(doctor_user.id)})
        if not doc_prof or doc_prof.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only approved doctors can author care plans.",
            )

        # 2. Consultation Appointment Validation
        if not ObjectId.is_valid(req.appointmentId):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid appointment ID format.",
            )

        appt = db["appointments"].find_one({"_id": ObjectId(req.appointmentId)})
        if not appt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation appointment not found.",
            )

        # Check that this doctor is indeed the doctor of the consultation
        is_authorized_doc = (
            str(appt.get("doctorUserId")) == str(doctor_user.id)
            or str(appt.get("doctorProfileId")) == str(doc_prof["_id"])
            or str(appt.get("doctorId")) == str(doc_prof.get("doctorId"))
        )
        if not is_authorized_doc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to create a care plan for this consultation.",
            )

        # Derive patient from consultation
        patient_user_id = str(appt.get("patientUserId") or appt.get("patientId") or "")

        # 3. Date Validation: Follow-up date must be today or future
        today_sl = get_sl_today_str()
        if req.followUpDate < today_sl:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Follow-up date cannot be in the past.",
            )

        if req.followUpDateEnd and req.followUpDateEnd < req.followUpDate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Follow-up date range end cannot be earlier than start date.",
            )

        # 4. Duplicate Active Plan Prevention
        coll = get_care_plan_collection(db)
        existing_active = coll.find_one({
            "appointmentId": str(req.appointmentId),
            "status": {"$in": [CarePlanStatus.ACTIVE.value, CarePlanStatus.FOLLOW_UP_BOOKED.value]},
        })
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active follow-up care plan already exists for this consultation.",
            )

        # 5. Build Tasks and Audit Log
        now = utc_now()
        task_objs = [
            CareTask(
                taskId=str(ObjectId()),
                title=t.title.strip(),
                description=t.description.strip() if t.description else None,
                isCompleted=False,
            )
            for t in req.tasks
        ]

        audit_entry = CarePlanAuditEntry(
            action="CREATED",
            performedBy=str(doctor_user.id),
            performedByRole="DOCTOR",
            timestamp=now,
            note=f"Care plan authored by Dr. {doc_prof.get('fullName', 'Doctor')}",
        )

        plan_doc = CarePlanDocument(
            patientUserId=patient_user_id,
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(doc_prof["_id"]),
            appointmentId=str(req.appointmentId),
            followUpDate=req.followUpDate,
            followUpDateEnd=req.followUpDateEnd,
            reason=req.reason.strip(),
            instructions=req.instructions.strip(),
            recommendedConsultationType=req.recommendedConsultationType or "IN_PERSON",
            tasks=task_objs,
            linkedPrescriptionIds=req.linkedPrescriptionIds or [],
            linkedMedicalRecordIds=req.linkedMedicalRecordIds or [],
            status=CarePlanStatus.ACTIVE,
            version=1,
            createdBy=str(doctor_user.id),
            updatedBy=str(doctor_user.id),
            auditLog=[audit_entry],
            remindersSent=[],
            createdAt=now,
            updatedAt=now,
        )

        inserted_dict = plan_doc.to_mongo_dict()
        res = coll.insert_one(inserted_dict)
        inserted_dict["_id"] = res.inserted_id

        # 6. Dispatch In-App & FCM Notification to Patient
        try:
            NotificationService.create_notification(
                db=db,
                recipient_user_id=patient_user_id,
                type=NotificationType.FOLLOW_UP_CARE_PLAN_CREATED,
                title="New Follow-up Care Plan",
                body="Your doctor has created a follow-up plan. Open MediConnect to view the details.",
                related_appointment_id=str(req.appointmentId),
                idempotency_key=f"care_plan_created_{res.inserted_id}",
                send_push=True,
            )
        except Exception as e:
            logger.warning("Failed to dispatch care plan created notification: %s", e)

        return _doc_to_response(db, inserted_dict)

    @classmethod
    async def get_care_plan(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        plan_id: str,
    ) -> CarePlanResponse:
        """Fetch a single care plan with strict patient/doctor authorization."""
        if not ObjectId.is_valid(plan_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan ID format.")

        coll = get_care_plan_collection(db)
        doc = coll.find_one({"_id": ObjectId(plan_id)})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care plan not found.")

        # Access check
        is_owner_patient = (current_user.role == UserRole.PATIENT.value and str(doc.get("patientUserId")) == str(current_user.id))
        is_owner_doctor = (current_user.role == UserRole.DOCTOR.value and str(doc.get("doctorUserId")) == str(current_user.id))
        is_admin = current_user.role == UserRole.ADMIN.value

        if not (is_owner_patient or is_owner_doctor or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this care plan.",
            )

        return _doc_to_response(db, doc)

    @classmethod
    async def list_doctor_care_plans(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        status_filter: Optional[str] = None,
        appointment_id: Optional[str] = None,
    ) -> CarePlanListResponse:
        """List care plans authored by this doctor."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can view doctor care plans.")

        coll = get_care_plan_collection(db)
        query: Dict[str, Any] = {"doctorUserId": str(doctor_user.id)}
        if status_filter and status_filter.strip():
            query["status"] = status_filter.strip().upper()
        if appointment_id and appointment_id.strip():
            query["appointmentId"] = appointment_id.strip()

        docs = list(coll.find(query).sort([("createdAt", -1)]))
        plans = [_doc_to_response(db, d) for d in docs]
        return CarePlanListResponse(total=len(plans), plans=plans)

    @classmethod
    async def list_patient_care_plans(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        status_filter: Optional[str] = None,
    ) -> CarePlanListResponse:
        """List care plans assigned to this patient."""
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can view patient care plans.")

        coll = get_care_plan_collection(db)
        query: Dict[str, Any] = {"patientUserId": str(patient_user.id)}
        if status_filter and status_filter.strip():
            query["status"] = status_filter.strip().upper()

        docs = list(coll.find(query).sort([("createdAt", -1)]))
        plans = [_doc_to_response(db, d) for d in docs]
        return CarePlanListResponse(total=len(plans), plans=plans)

    @classmethod
    async def update_care_plan(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        plan_id: str,
        req: UpdateCarePlanRequest,
    ) -> CarePlanResponse:
        """Update care plan instructions, follow-up dates, or tasks."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can edit care plans.")

        if not ObjectId.is_valid(plan_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan ID format.")

        coll = get_care_plan_collection(db)
        doc = coll.find_one({"_id": ObjectId(plan_id)})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care plan not found.")

        if str(doc.get("doctorUserId")) != str(doctor_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit care plans you authored.")

        if doc.get("status") in [CarePlanStatus.COMPLETED.value, CarePlanStatus.CANCELLED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit care plan with status '{doc.get('status')}'.",
            )

        now = utc_now()
        today_sl = get_sl_today_str()
        audit_notes = []

        update_fields: Dict[str, Any] = {
            "updatedAt": now,
            "updatedBy": str(doctor_user.id),
        }

        # Date updates
        if req.followUpDate:
            if req.followUpDate < today_sl:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Follow-up date cannot be in the past.")
            update_fields["followUpDate"] = req.followUpDate
            audit_notes.append(f"Follow-up date updated to {req.followUpDate}")
            # Reset reminders so fresh notifications fire for rescheduled date
            update_fields["remindersSent"] = []

        if req.followUpDateEnd is not None:
            effective_start = req.followUpDate or doc.get("followUpDate")
            if req.followUpDateEnd and req.followUpDateEnd < effective_start:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Range end cannot be before start date.")
            update_fields["followUpDateEnd"] = req.followUpDateEnd

        # Clinical instructions & reason (tracked in audit log)
        if req.instructions and req.instructions.strip() != doc.get("instructions"):
            update_fields["instructions"] = req.instructions.strip()
            audit_notes.append("Clinical care instructions revised")

        if req.reason and req.reason.strip() != doc.get("reason"):
            update_fields["reason"] = req.reason.strip()
            audit_notes.append(f"Follow-up reason updated: {req.reason.strip()}")

        if req.recommendedConsultationType:
            update_fields["recommendedConsultationType"] = req.recommendedConsultationType

        # Tasks update
        if req.tasks is not None:
            # Preserve completion status of existing tasks if title matches
            existing_completed = {
                t.get("title", "").strip().lower(): t.get("completedAt")
                for t in doc.get("tasks", [])
                if t.get("isCompleted")
            }
            new_tasks = []
            for t in req.tasks:
                clean_title = t.title.strip()
                was_completed = clean_title.lower() in existing_completed
                new_tasks.append(
                    CareTask(
                        taskId=str(ObjectId()),
                        title=clean_title,
                        description=t.description.strip() if t.description else None,
                        isCompleted=was_completed,
                        completedAt=existing_completed.get(clean_title.lower()),
                    ).model_dump()
                )
            update_fields["tasks"] = new_tasks
            audit_notes.append(f"Updated tasks list ({len(new_tasks)} tasks)")

        if req.linkedPrescriptionIds is not None:
            update_fields["linkedPrescriptionIds"] = req.linkedPrescriptionIds

        if req.linkedMedicalRecordIds is not None:
            update_fields["linkedMedicalRecordIds"] = req.linkedMedicalRecordIds

        # Bump version
        new_version = int(doc.get("version", 1)) + 1
        update_fields["version"] = new_version

        audit_entry = CarePlanAuditEntry(
            action="UPDATED",
            performedBy=str(doctor_user.id),
            performedByRole="DOCTOR",
            timestamp=now,
            note="; ".join(audit_notes) if audit_notes else "Plan details updated",
        ).model_dump()

        coll.update_one(
            {"_id": ObjectId(plan_id)},
            {
                "$set": update_fields,
                "$push": {"auditLog": audit_entry},
            },
        )

        updated_doc = coll.find_one({"_id": ObjectId(plan_id)})
        return _doc_to_response(db, updated_doc)

    @classmethod
    async def cancel_care_plan(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        plan_id: str,
        req: CancelCarePlanRequest,
    ) -> CarePlanResponse:
        """Cancel an active follow-up care plan."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can cancel care plans.")

        if not ObjectId.is_valid(plan_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan ID format.")

        coll = get_care_plan_collection(db)
        doc = coll.find_one({"_id": ObjectId(plan_id)})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care plan not found.")

        if str(doc.get("doctorUserId")) != str(doctor_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only cancel care plans you authored.")

        if doc.get("status") in [CarePlanStatus.COMPLETED.value, CarePlanStatus.CANCELLED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Care plan is already {doc.get('status').lower()}.",
            )

        now = utc_now()
        audit_entry = CarePlanAuditEntry(
            action="CANCELLED",
            performedBy=str(doctor_user.id),
            performedByRole="DOCTOR",
            timestamp=now,
            note=f"Cancelled by doctor: {req.reason.strip()}",
        ).model_dump()

        coll.update_one(
            {"_id": ObjectId(plan_id)},
            {
                "$set": {
                    "status": CarePlanStatus.CANCELLED.value,
                    "updatedAt": now,
                    "updatedBy": str(doctor_user.id),
                },
                "$push": {"auditLog": audit_entry},
            },
        )

        updated_doc = coll.find_one({"_id": ObjectId(plan_id)})
        return _doc_to_response(db, updated_doc)

    @classmethod
    async def update_task_status(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        plan_id: str,
        task_id: str,
        req: UpdateTaskStatusRequest,
    ) -> CarePlanResponse:
        """Patient toggles non-medication care task completion."""
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can update task status.")

        if not ObjectId.is_valid(plan_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan ID format.")

        coll = get_care_plan_collection(db)
        doc = coll.find_one({"_id": ObjectId(plan_id)})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care plan not found.")

        if str(doc.get("patientUserId")) != str(patient_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update tasks in your own care plans.")

        now = utc_now()
        tasks = doc.get("tasks", [])
        matched = False
        task_title = "Task"

        for t in tasks:
            if str(t.get("taskId")) == str(task_id):
                matched = True
                task_title = t.get("title", "Task")
                t["isCompleted"] = req.isCompleted
                t["completedAt"] = now if req.isCompleted else None
                break

        if not matched:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found in care plan.")

        action_name = "TASK_COMPLETED" if req.isCompleted else "TASK_PENDING"
        audit_entry = CarePlanAuditEntry(
            action=action_name,
            performedBy=str(patient_user.id),
            performedByRole="PATIENT",
            timestamp=now,
            note=f"Task '{task_title}' marked as {'completed' if req.isCompleted else 'pending'}",
        ).model_dump()

        coll.update_one(
            {"_id": ObjectId(plan_id)},
            {
                "$set": {"tasks": tasks, "updatedAt": now, "updatedBy": str(patient_user.id)},
                "$push": {"auditLog": audit_entry},
            },
        )

        updated_doc = coll.find_one({"_id": ObjectId(plan_id)})
        return _doc_to_response(db, updated_doc)

    @classmethod
    async def link_booked_appointment(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        plan_id: str,
        req: LinkAppointmentRequest,
    ) -> CarePlanResponse:
        """Connect a newly confirmed follow-up appointment to the care plan."""
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can link follow-up bookings.")

        if not ObjectId.is_valid(plan_id) or not ObjectId.is_valid(req.appointmentId):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format.")

        coll = get_care_plan_collection(db)
        doc = coll.find_one({"_id": ObjectId(plan_id)})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care plan not found.")

        if str(doc.get("patientUserId")) != str(patient_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only link appointments to your own care plans.")

        # Validate appointment
        appt = db["appointments"].find_one({"_id": ObjectId(req.appointmentId)})
        if not appt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up appointment not found.")

        appt_patient_id = str(appt.get("patientUserId") or appt.get("patientId") or "")
        if appt_patient_id != str(patient_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Appointment does not belong to you.")

        # Ensure appointment is with treating doctor
        doc_prof = (
            db["doctor_profiles"].find_one({"_id": ObjectId(doc.get("doctorProfileId"))})
            if ObjectId.is_valid(doc.get("doctorProfileId"))
            else None
        )
        is_same_doctor = (
            str(appt.get("doctorUserId")) == str(doc.get("doctorUserId"))
            or str(appt.get("doctorProfileId")) == str(doc.get("doctorProfileId"))
            or (doc_prof and str(appt.get("doctorId")) == str(doc_prof.get("doctorId")))
            or str(appt.get("doctorId")) == str(doc.get("doctorProfileId"))
        )
        if not is_same_doctor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Follow-up appointment must be booked with the recommended treating doctor.",
            )

        now = utc_now()
        audit_entry = CarePlanAuditEntry(
            action="APPOINTMENT_LINKED",
            performedBy=str(patient_user.id),
            performedByRole="PATIENT",
            timestamp=now,
            note=f"Follow-up appointment {req.appointmentId} ({appt.get('appointmentDate')} {appt.get('startTime')}) booked and linked",
        ).model_dump()

        coll.update_one(
            {"_id": ObjectId(plan_id)},
            {
                "$set": {
                    "bookedAppointmentId": str(req.appointmentId),
                    "status": CarePlanStatus.FOLLOW_UP_BOOKED.value,
                    "updatedAt": now,
                    "updatedBy": str(patient_user.id),
                },
                "$push": {"auditLog": audit_entry},
            },
        )

        updated_doc = coll.find_one({"_id": ObjectId(plan_id)})
        return _doc_to_response(db, updated_doc)

    @classmethod
    def check_and_send_care_plan_reminders(cls, db: Database) -> int:
        """Scan active care plans and dispatch smart follow-up reminders (7d, 1d, and day-of).

        Ensures:
        - Completed or cancelled plans do NOT receive reminders.
        - Privacy: No sensitive clinical diagnoses in notification previews.
        - Idempotency: Reminders already marked in remindersSent are skipped.
        """
        today_date = get_sl_now().date()
        today_str = today_date.strftime("%Y-%m-%d")

        coll = get_care_plan_collection(db)
        query = {
            "status": {"$in": [CarePlanStatus.ACTIVE.value, CarePlanStatus.OVERDUE.value]},
        }

        active_plans = list(coll.find(query))
        sent_count = 0

        for plan in active_plans:
            plan_id = str(plan["_id"])
            follow_up_str = plan.get("followUpDate")
            if not follow_up_str:
                continue

            try:
                target_date = datetime.strptime(follow_up_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            days_diff = (target_date - today_date).days
            reminders_sent = list(plan.get("remindersSent", []))
            patient_id = str(plan.get("patientUserId"))

            # 1. 7-day reminder
            if days_diff == 7 and "7D" not in reminders_sent:
                NotificationService.create_notification(
                    db=db,
                    recipient_user_id=patient_id,
                    type=NotificationType.FOLLOW_UP_REMINDER_7D,
                    title="Follow-up Reminder",
                    body="You have an upcoming recommended follow-up in 7 days. Open MediConnect for details.",
                    related_appointment_id=str(plan.get("appointmentId")),
                    idempotency_key=f"care_plan_7d_{plan_id}_{follow_up_str}",
                    send_push=True,
                )
                coll.update_one({"_id": ObjectId(plan_id)}, {"$addToSet": {"remindersSent": "7D"}})
                sent_count += 1

            # 2. 1-day reminder
            elif days_diff == 1 and "1D" not in reminders_sent:
                NotificationService.create_notification(
                    db=db,
                    recipient_user_id=patient_id,
                    type=NotificationType.FOLLOW_UP_REMINDER_1D,
                    title="Follow-up Reminder",
                    body="You have an upcoming recommended follow-up tomorrow. Open MediConnect for details.",
                    related_appointment_id=str(plan.get("appointmentId")),
                    idempotency_key=f"care_plan_1d_{plan_id}_{follow_up_str}",
                    send_push=True,
                )
                coll.update_one({"_id": ObjectId(plan_id)}, {"$addToSet": {"remindersSent": "1D"}})
                sent_count += 1

            # 3. Day-of reminder
            elif days_diff == 0 and "DUE" not in reminders_sent:
                NotificationService.create_notification(
                    db=db,
                    recipient_user_id=patient_id,
                    type=NotificationType.FOLLOW_UP_REMINDER_DUE,
                    title="Follow-up Reminder",
                    body="You have a recommended follow-up scheduled for today. Open MediConnect for details.",
                    related_appointment_id=str(plan.get("appointmentId")),
                    idempotency_key=f"care_plan_due_{plan_id}_{follow_up_str}",
                    send_push=True,
                )
                coll.update_one({"_id": ObjectId(plan_id)}, {"$addToSet": {"remindersSent": "DUE"}})
                sent_count += 1

            # 4. Overdue marking
            elif days_diff < 0 and plan.get("status") == CarePlanStatus.ACTIVE.value:
                coll.update_one(
                    {"_id": ObjectId(plan_id)},
                    {"$set": {"status": CarePlanStatus.OVERDUE.value, "updatedAt": utc_now()}},
                )

        return sent_count
