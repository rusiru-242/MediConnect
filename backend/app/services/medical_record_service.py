"""Service layer for Medical Records, Digital Prescriptions, and Audit Governance (Phase 21)."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import DESCENDING
from pymongo.database import Database

from app.models.appointment import AppointmentStatus, utc_now
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.medical_record import (
    MedicalRecordDocument,
    MedicalRecordStatus,
    get_medical_record_collection,
)
from app.models.notification import NotificationType
from app.models.prescription import (
    MedicationItem,
    PrescriptionDocument,
    PrescriptionStatus,
    claim_submission,
    get_prescription_collection,
    release_submission,
    submission_key,
)
from app.models.user import AccountStatus, UserRole
from app.schemas.medical_record import (
    AmendMedicalRecordRequest,
    CreateMedicalRecordRequest,
    MedicalRecordListResponse,
    MedicalRecordResponseSchema,
)
from app.schemas.prescription import (
    AmendPrescriptionRequest,
    CreatePrescriptionRequest,
    PrescriptionListResponse,
    PrescriptionResponseSchema,
)
from app.schemas.user import UserResponseSchema
from app.services.notification_service import NotificationService
from app.services.pdf_service import PrescriptionPdfService

logger = logging.getLogger(__name__)


class MedicalRecordService:
    """Manages consultation records, prescriptions, role validations, and audit trails."""

    # -----------------------------------------------------------------------
    # Helper: Verify Approved & Active Doctor
    # -----------------------------------------------------------------------
    @classmethod
    def _verify_approved_doctor(cls, db: Database, doctor_user: UserResponseSchema) -> Dict[str, Any]:
        """Ensure current user is an active, verified doctor with approved SLMC credentials."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only healthcare practitioners can perform clinical documentation.",
            )

        # Check doctor profile approval
        query = {"userId": str(doctor_user.id)}
        profile = db["doctor_profiles"].find_one(query)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctor profile not found. Cannot issue clinical documentation.",
            )

        if profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctor accreditation is not approved. Only verified doctors can document records.",
            )

        return profile

    # -----------------------------------------------------------------------
    # Helper: Fetch Doctor & Patient Enrichment Data
    # -----------------------------------------------------------------------
    @classmethod
    def _enrich_metadata(cls, db: Database, doc_user_id: str, pat_user_id: str) -> Dict[str, Any]:
        """Retrieve user and profile metadata for responses without sensitive leakages."""
        doc_query = {"$or": [{"_id": ObjectId(doc_user_id)}, {"_id": doc_user_id}]} if ObjectId.is_valid(doc_user_id) else {"_id": doc_user_id}
        pat_query = {"$or": [{"_id": ObjectId(pat_user_id)}, {"_id": pat_user_id}]} if ObjectId.is_valid(pat_user_id) else {"_id": pat_user_id}

        doc_user = db["users"].find_one(doc_query) or {}
        pat_user = db["users"].find_one(pat_query) or {}
        doc_prof = db["doctor_profiles"].find_one({"userId": doc_user_id}) or {}

        doc_name = doc_user.get("fullName", "Doctor")
        if not doc_name.startswith("Dr."):
            doc_name = f"Dr. {doc_name}"

        return {
            "doctorName": doc_name,
            "doctorSpecialty": doc_prof.get("specialty", "General Medicine"),
            "slmcRegistrationNumber": doc_prof.get("medicalRegistrationNumber"),
            "hospitalOrClinic": doc_prof.get("hospitalOrClinic"),
            "patientName": pat_user.get("fullName", "Patient"),
            "doctor_user": doc_user,
            "doctor_profile": doc_prof,
            "patient_user": pat_user,
        }

    # =======================================================================
    # 1. MEDICAL CONSULTATION RECORDS
    # =======================================================================

    @classmethod
    async def create_medical_record(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        req: CreateMedicalRecordRequest,
    ) -> MedicalRecordResponseSchema:
        """Create a clinical consultation record for a completed appointment."""
        doc_prof = cls._verify_approved_doctor(db, doctor_user)

        # Validate appointment
        appt_query = {"$or": [{"_id": ObjectId(req.appointmentId)}, {"_id": req.appointmentId}]} if ObjectId.is_valid(req.appointmentId) else {"_id": req.appointmentId}
        appointment = db["appointments"].find_one(appt_query)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced appointment not found.",
            )

        # Doctor assignment check
        if appointment.get("doctorUserId") != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not the assigned doctor for this appointment.",
            )

        # Check status: must be COMPLETED (or CONFIRMED, which we transition to COMPLETED)
        appt_status = appointment.get("status")
        if appt_status not in [AppointmentStatus.COMPLETED.value, AppointmentStatus.CONFIRMED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot document consultation for appointment in {appt_status} status. Appointment must be confirmed or completed.",
            )

        # Uniqueness check first: a rejected duplicate must not change the appointment (P03-N12).
        rec_coll = get_medical_record_collection(db)
        existing = rec_coll.find_one({"appointmentId": req.appointmentId})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A medical consultation record already exists for this appointment.",
            )

        # Documenting a CONFIRMED visit completes it, but only once the visit has started (the same rule as
        # "Mark completed"); a future visit cannot be completed by writing its record early (P03-N12).
        if appt_status == AppointmentStatus.CONFIRMED.value:
            starts = datetime.strptime(f"{appointment['appointmentDate']} {appointment['startTime']}", "%Y-%m-%d %H:%M"
                                       ).replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
            if starts > datetime.now(timezone.utc):
                raise HTTPException(status_code=409, detail="The consultation record can be written once the visit has started.")
            moved = db["appointments"].update_one({"_id": appointment["_id"], "status": AppointmentStatus.CONFIRMED.value},
                                                  {"$set": {"status": AppointmentStatus.COMPLETED.value, "updatedAt": utc_now()}})
            if moved.modified_count:
                from app.services.appointment_events import record_appointment_event
                record_appointment_event(db, str(appointment["_id"]), "APPOINTMENT_COMPLETED", actor_role="DOCTOR",
                                         actor_id=str(doctor_user.id), from_status="CONFIRMED", to_status="COMPLETED",
                                         details={"via": "consultation_record"},
                                         idempotency_key=f"completed_{appointment['_id']}")

        # Generate unique record ID
        date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_suffix = uuid.uuid4().hex[:6].upper()
        record_id = f"REC-{date_prefix}-{rand_suffix}"

        now = utc_now()
        patient_user_id = str(appointment.get("patientUserId"))
        consult_date = appointment.get("appointmentDate", now.strftime("%Y-%m-%d"))

        record_doc = {
            "recordId": record_id,
            "patientUserId": patient_user_id,
            "doctorUserId": str(doctor_user.id),
            "doctorProfileId": str(doc_prof.get("_id", "")),
            "appointmentId": req.appointmentId,
            "consultationDate": consult_date,
            "clinicalNotes": req.clinicalNotes.strip(),
            "assessment": req.assessment.strip(),
            "treatmentPlan": req.treatmentPlan.strip(),
            "followUpInstructions": req.followUpInstructions.strip() if req.followUpInstructions else None,
            "status": MedicalRecordStatus.ACTIVE.value,
            "amendmentHistory": [],
            "auditLog": [
                {
                    "action": "CREATED",
                    "userId": str(doctor_user.id),
                    "role": doctor_user.role,
                    "timestamp": now,
                }
            ],
            "createdAt": now,
            "updatedAt": now,
        }

        result = rec_coll.insert_one(record_doc)
        record_doc["_id"] = str(result.inserted_id)

        # Patient notification
        try:
            # A04-BUG-012: this called NotificationService.create_and_send_notification, which does not exist, so the
            # patient was never told (the AttributeError was logged and swallowed). Generic text on the lock screen.
            NotificationService.create_notification(
                db=db,
                recipient_user_id=patient_user_id,
                type=NotificationType.CONSULTATION_RECORD_AVAILABLE,
                title="Consultation Summary Available",
                body="Your consultation summary is now available in Medical Records in MediConnect.",
                related_appointment_id=str(req.appointmentId),
                idempotency_key=f"consultation_record_{record_id}",
            )
        except Exception as exc:
            logger.warning("Could not dispatch patient consultation record notification: %s", exc)

        meta = cls._enrich_metadata(db, str(doctor_user.id), patient_user_id)
        return MedicalRecordResponseSchema(
            id=str(result.inserted_id),
            recordId=record_id,
            patientUserId=patient_user_id,
            patientName=meta["patientName"],
            doctorUserId=str(doctor_user.id),
            doctorName=meta["doctorName"],
            doctorSpecialty=meta["doctorSpecialty"],
            slmcRegistrationNumber=meta["slmcRegistrationNumber"],
            hospitalOrClinic=meta["hospitalOrClinic"],
            appointmentId=req.appointmentId,
            consultationDate=consult_date,
            clinicalNotes=record_doc["clinicalNotes"],
            assessment=record_doc["assessment"],
            treatmentPlan=record_doc["treatmentPlan"],
            followUpInstructions=record_doc["followUpInstructions"],
            status=record_doc["status"],
            prescription=None,
            amendmentHistory=record_doc["amendmentHistory"],
            createdAt=now,
            updatedAt=now,
        )

    @classmethod
    async def get_medical_record(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        record_id: str,
    ) -> MedicalRecordResponseSchema:
        """Fetch a specific medical consultation record with ownership verification."""
        rec_coll = get_medical_record_collection(db)
        query = {"$or": [{"_id": ObjectId(record_id)}, {"recordId": record_id}]} if ObjectId.is_valid(record_id) else {"recordId": record_id}
        record = rec_coll.find_one(query)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medical consultation record not found.",
            )

        # Ownership authorization: Patient must be patientUserId OR Doctor must be doctorUserId
        user_id_str = str(current_user.id)
        if record.get("patientUserId") != user_id_str and record.get("doctorUserId") != user_id_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have authorization to view this medical record.",
            )

        # Audit log entry for viewing
        now = utc_now()
        rec_coll.update_one(
            {"_id": record["_id"]},
            {"$push": {"auditLog": {"action": "VIEWED", "userId": user_id_str, "role": current_user.role, "timestamp": now}}},
        )

        # Check for associated prescription
        presc_coll = get_prescription_collection(db)
        presc_doc = presc_coll.find_one({"medicalRecordId": str(record["_id"])}) or presc_coll.find_one({"medicalRecordId": record["recordId"]})

        meta = cls._enrich_metadata(db, record["doctorUserId"], record["patientUserId"])
        presc_schema = None
        if presc_doc:
            presc_schema = PrescriptionResponseSchema(
                id=str(presc_doc["_id"]),
                prescriptionId=presc_doc["prescriptionId"],
                medicalRecordId=str(record["_id"]),
                appointmentId=presc_doc.get("appointmentId"),
                patientUserId=presc_doc["patientUserId"],
                patientName=meta["patientName"],
                doctorUserId=presc_doc["doctorUserId"],
                doctorName=meta["doctorName"],
                doctorSpecialty=meta["doctorSpecialty"],
                slmcRegistrationNumber=meta["slmcRegistrationNumber"],
                hospitalOrClinic=meta["hospitalOrClinic"],
                issuedAt=presc_doc["issuedAt"],
                status=presc_doc["status"],
                medicationItems=presc_doc["medicationItems"],
                instructions=presc_doc.get("instructions"),
                amendmentHistory=presc_doc.get("amendmentHistory", []),
                createdAt=presc_doc["createdAt"],
                updatedAt=presc_doc["updatedAt"],
            )

        return MedicalRecordResponseSchema(
            id=str(record["_id"]),
            recordId=record["recordId"],
            patientUserId=record["patientUserId"],
            patientName=meta["patientName"],
            doctorUserId=record["doctorUserId"],
            doctorName=meta["doctorName"],
            doctorSpecialty=meta["doctorSpecialty"],
            slmcRegistrationNumber=meta["slmcRegistrationNumber"],
            hospitalOrClinic=meta["hospitalOrClinic"],
            appointmentId=record["appointmentId"],
            consultationDate=record["consultationDate"],
            clinicalNotes=record["clinicalNotes"],
            assessment=record["assessment"],
            treatmentPlan=record["treatmentPlan"],
            followUpInstructions=record.get("followUpInstructions"),
            status=record["status"],
            prescription=presc_schema,
            amendmentHistory=record.get("amendmentHistory", []),
            createdAt=record["createdAt"],
            updatedAt=record["updatedAt"],
        )

    @classmethod
    async def amend_medical_record(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        record_id: str,
        req: AmendMedicalRecordRequest,
    ) -> MedicalRecordResponseSchema:
        """Safely amend a clinical record with mandatory clinical justification and audit trail."""
        cls._verify_approved_doctor(db, doctor_user)

        rec_coll = get_medical_record_collection(db)
        query = {"$or": [{"_id": ObjectId(record_id)}, {"recordId": record_id}]} if ObjectId.is_valid(record_id) else {"recordId": record_id}
        record = rec_coll.find_one(query)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medical consultation record not found.",
            )

        if record.get("doctorUserId") != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the prescribing/authoring doctor may amend this clinical record.",
            )

        now = utc_now()
        amendment_entry = {
            "amendedAt": now,
            "amendedBy": str(doctor_user.id),
            "reason": req.amendmentReason.strip(),
            "previousNotes": record["clinicalNotes"],
            "previousAssessment": record["assessment"],
            "previousTreatmentPlan": record["treatmentPlan"],
            "previousFollowUp": record.get("followUpInstructions"),
        }

        audit_entry = {
            "action": "AMENDED",
            "userId": str(doctor_user.id),
            "role": doctor_user.role,
            "reason": req.amendmentReason.strip(),
            "timestamp": now,
        }

        updated_notes = req.clinicalNotes.strip()
        updated_assessment = req.assessment.strip()
        updated_plan = req.treatmentPlan.strip()
        updated_follow_up = req.followUpInstructions.strip() if req.followUpInstructions else None

        rec_coll.update_one(
            {"_id": record["_id"]},
            {
                "$set": {
                    "clinicalNotes": updated_notes,
                    "assessment": updated_assessment,
                    "treatmentPlan": updated_plan,
                    "followUpInstructions": updated_follow_up,
                    "status": MedicalRecordStatus.AMENDED.value,
                    "updatedAt": now,
                },
                "$push": {
                    "amendmentHistory": amendment_entry,
                    "auditLog": audit_entry,
                },
            },
        )

        return await cls.get_medical_record(db, doctor_user, str(record["_id"]))

    @classmethod
    async def list_patient_records(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        page: int = 1,
        page_size: int = 20,
    ) -> MedicalRecordListResponse:
        """List all consultation records for the authenticated patient with pagination."""
        rec_coll = get_medical_record_collection(db)
        filter_query = {"patientUserId": str(patient_user.id)}

        total = rec_coll.count_documents(filter_query)
        skip = (page - 1) * page_size
        cursor = rec_coll.find(filter_query).sort("createdAt", DESCENDING).skip(skip).limit(page_size)

        items = []
        for doc in cursor:
            meta = cls._enrich_metadata(db, doc["doctorUserId"], doc["patientUserId"])
            items.append(
                MedicalRecordResponseSchema(
                    id=str(doc["_id"]),
                    recordId=doc["recordId"],
                    patientUserId=doc["patientUserId"],
                    patientName=meta["patientName"],
                    doctorUserId=doc["doctorUserId"],
                    doctorName=meta["doctorName"],
                    doctorSpecialty=meta["doctorSpecialty"],
                    slmcRegistrationNumber=meta["slmcRegistrationNumber"],
                    hospitalOrClinic=meta["hospitalOrClinic"],
                    appointmentId=doc.get("appointmentId"),
                    consultationDate=doc["consultationDate"],
                    clinicalNotes=doc["clinicalNotes"],
                    assessment=doc["assessment"],
                    treatmentPlan=doc["treatmentPlan"],
                    followUpInstructions=doc.get("followUpInstructions"),
                    status=doc["status"],
                    amendmentHistory=doc.get("amendmentHistory", []),
                    createdAt=doc["createdAt"],
                    updatedAt=doc["updatedAt"],
                )
            )

        return MedicalRecordListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
        )

    @classmethod
    async def list_doctor_records(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> MedicalRecordListResponse:
        """List consultation records authored by the authenticated doctor."""
        rec_coll = get_medical_record_collection(db)
        filter_query: Dict[str, Any] = {"doctorUserId": str(doctor_user.id)}

        if appointment_id:
            filter_query["appointmentId"] = appointment_id
        if patient_id:
            filter_query["patientUserId"] = patient_id

        total = rec_coll.count_documents(filter_query)
        skip = (page - 1) * page_size
        cursor = rec_coll.find(filter_query).sort("createdAt", DESCENDING).skip(skip).limit(page_size)

        items = []
        for doc in cursor:
            meta = cls._enrich_metadata(db, doc["doctorUserId"], doc["patientUserId"])
            items.append(
                MedicalRecordResponseSchema(
                    id=str(doc["_id"]),
                    recordId=doc["recordId"],
                    patientUserId=doc["patientUserId"],
                    patientName=meta["patientName"],
                    doctorUserId=doc["doctorUserId"],
                    doctorName=meta["doctorName"],
                    doctorSpecialty=meta["doctorSpecialty"],
                    slmcRegistrationNumber=meta["slmcRegistrationNumber"],
                    hospitalOrClinic=meta["hospitalOrClinic"],
                    appointmentId=doc.get("appointmentId"),
                    consultationDate=doc["consultationDate"],
                    clinicalNotes=doc["clinicalNotes"],
                    assessment=doc["assessment"],
                    treatmentPlan=doc["treatmentPlan"],
                    followUpInstructions=doc.get("followUpInstructions"),
                    status=doc["status"],
                    amendmentHistory=doc.get("amendmentHistory", []),
                    createdAt=doc["createdAt"],
                    updatedAt=doc["updatedAt"],
                )
            )

        return MedicalRecordListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
        )

    # =======================================================================
    # 2. DIGITAL PRESCRIPTION OPERATIONS
    # =======================================================================

    @classmethod
    async def create_prescription(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        req: CreatePrescriptionRequest,
    ) -> PrescriptionResponseSchema:
        """Issue a verified digital prescription linked to a consultation record."""
        doc_prof = cls._verify_approved_doctor(db, doctor_user)

        # Validate consultation medical record
        rec_coll = get_medical_record_collection(db)
        rec_query = {"$or": [{"_id": ObjectId(req.medicalRecordId)}, {"recordId": req.medicalRecordId}]} if ObjectId.is_valid(req.medicalRecordId) else {"recordId": req.medicalRecordId}
        record = rec_coll.find_one(rec_query)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced medical consultation record not found.",
            )

        if record.get("doctorUserId") != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to issue prescriptions for another doctor's consultation record.",
            )
        if str(record.get("appointmentId")) != str(req.appointmentId):
            # The prescription belongs to the consultation it was written in (P03-N07).
            raise HTTPException(status_code=400, detail="The appointment does not match this consultation record.")

        med_items_dicts = [item.model_dump() for item in req.medicationItems]
        duplicate = get_prescription_collection(db).find_one({
            "medicalRecordId": str(record["_id"]), "doctorUserId": str(doctor_user.id),
            "status": {"$in": [PrescriptionStatus.ISSUED.value, PrescriptionStatus.AMENDED.value]},
            "medicationItems": med_items_dicts,
        }, {"prescriptionId": 1})
        if duplicate:
            # A repeated submission of the same prescription (double tap, retry) must not issue it twice (P03-N13).
            raise HTTPException(status_code=409, detail=f"This prescription was already issued ({duplicate['prescriptionId']}).")
        # A04-BUG-003: the read above cannot see a simultaneous identical submission; the claim can.
        claim = submission_key(str(doctor_user.id), record["patientUserId"], str(record["_id"]), med_items_dicts)
        if not claim_submission(db, claim):
            raise HTTPException(status_code=409, detail="This prescription was just submitted.")
        try:
            return await cls._store_prescription(db, doctor_user, doc_prof, req, record, med_items_dicts)
        except Exception:
            release_submission(db, claim)
            raise

    @classmethod
    async def _store_prescription(cls, db, doctor_user, doc_prof, req, record, med_items_dicts):
        # Generate prescription ID
        date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_suffix = uuid.uuid4().hex[:6].upper()
        presc_id = f"RX-{date_prefix}-{rand_suffix}"

        now = utc_now()
        patient_user_id = record["patientUserId"]

        presc_doc = {
            "prescriptionId": presc_id,
            "medicalRecordId": str(record["_id"]),
            "appointmentId": str(record.get("appointmentId")),
            "patientUserId": patient_user_id,
            "doctorUserId": str(doctor_user.id),
            "doctorProfileId": str(doc_prof.get("_id", "")),
            "issuedAt": now,
            "status": PrescriptionStatus.ISSUED.value,
            "medicationItems": med_items_dicts,
            "instructions": req.instructions.strip() if req.instructions else None,
            "amendmentHistory": [],
            "auditLog": [
                {
                    "action": "ISSUED",
                    "userId": str(doctor_user.id),
                    "role": doctor_user.role,
                    "timestamp": now,
                }
            ],
            "createdAt": now,
            "updatedAt": now,
        }

        presc_coll = get_prescription_collection(db)
        result = presc_coll.insert_one(presc_doc)
        presc_doc["_id"] = str(result.inserted_id)

        # Patient notification
        try:
            # A04-BUG-012: same missing method as above; the same generic wording as the clinical-workflow path.
            NotificationService.create_notification(
                db=db,
                recipient_user_id=patient_user_id,
                type=NotificationType.PRESCRIPTION_ISSUED,
                title="New prescription available",
                body="Your doctor issued a prescription. Open Medical Records in MediConnect to view it.",
                related_appointment_id=str(record.get("appointmentId")) if record.get("appointmentId") else None,
                idempotency_key=f"prescription_issued_{result.inserted_id}",
            )
        except Exception as exc:
            logger.warning("Could not dispatch patient digital prescription notification: %s", exc)

        meta = cls._enrich_metadata(db, str(doctor_user.id), patient_user_id)
        return PrescriptionResponseSchema(
            id=str(result.inserted_id),
            prescriptionId=presc_id,
            medicalRecordId=str(record["_id"]),
            appointmentId=req.appointmentId,
            patientUserId=patient_user_id,
            patientName=meta["patientName"],
            doctorUserId=str(doctor_user.id),
            doctorName=meta["doctorName"],
            doctorSpecialty=meta["doctorSpecialty"],
            slmcRegistrationNumber=meta["slmcRegistrationNumber"],
            hospitalOrClinic=meta["hospitalOrClinic"],
            issuedAt=now,
            status=presc_doc["status"],
            medicationItems=req.medicationItems,
            instructions=presc_doc["instructions"],
            amendmentHistory=presc_doc["amendmentHistory"],
            createdAt=now,
            updatedAt=now,
        )

    @classmethod
    async def get_prescription(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        prescription_id: str,
    ) -> PrescriptionResponseSchema:
        """Fetch a specific digital prescription with authorization checks and access logging."""
        presc_coll = get_prescription_collection(db)
        query = {"$or": [{"_id": ObjectId(prescription_id)}, {"prescriptionId": prescription_id}]} if ObjectId.is_valid(prescription_id) else {"prescriptionId": prescription_id}
        doc = presc_coll.find_one(query)

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Digital prescription not found.",
            )

        user_id_str = str(current_user.id)
        if doc.get("patientUserId") != user_id_str and doc.get("doctorUserId") != user_id_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have authorization to view this prescription.",
            )

        now = utc_now()
        presc_coll.update_one(
            {"_id": doc["_id"]},
            {"$push": {"auditLog": {"action": "VIEWED", "userId": user_id_str, "role": current_user.role, "timestamp": now}}},
        )

        meta = cls._enrich_metadata(db, doc["doctorUserId"], doc["patientUserId"])
        return PrescriptionResponseSchema(
            id=str(doc["_id"]),
            prescriptionId=doc["prescriptionId"],
            medicalRecordId=doc.get("medicalRecordId"),
            appointmentId=doc.get("appointmentId"),
            patientUserId=doc["patientUserId"],
            patientName=meta["patientName"],
            doctorUserId=doc["doctorUserId"],
            doctorName=meta["doctorName"],
            doctorSpecialty=meta["doctorSpecialty"],
            slmcRegistrationNumber=meta["slmcRegistrationNumber"],
            hospitalOrClinic=meta["hospitalOrClinic"],
            issuedAt=doc["issuedAt"],
            status=doc["status"],
            medicationItems=doc["medicationItems"],
            instructions=doc.get("instructions"),
            amendmentHistory=doc.get("amendmentHistory", []),
            createdAt=doc["createdAt"],
            updatedAt=doc["updatedAt"],
        )

    @classmethod
    async def amend_prescription(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        prescription_id: str,
        req: AmendPrescriptionRequest,
    ) -> PrescriptionResponseSchema:
        """Controlled correction/amendment of an issued prescription with audit trail."""
        cls._verify_approved_doctor(db, doctor_user)

        presc_coll = get_prescription_collection(db)
        query = {"$or": [{"_id": ObjectId(prescription_id)}, {"prescriptionId": prescription_id}]} if ObjectId.is_valid(prescription_id) else {"prescriptionId": prescription_id}
        doc = presc_coll.find_one(query)

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Digital prescription not found.",
            )

        if doc.get("doctorUserId") != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the issuing doctor may amend this prescription.",
            )
        if doc.get("status") == PrescriptionStatus.CANCELLED.value:
            raise HTTPException(status_code=409, detail="A cancelled prescription cannot be amended. Issue a new one.")

        now = utc_now()
        amend_entry = {
            "amendedAt": now,
            "amendedBy": str(doctor_user.id),
            "reason": req.amendmentReason.strip(),
            "previousMedicationItems": doc["medicationItems"],
            "previousInstructions": doc.get("instructions"),
        }

        audit_entry = {
            "action": "AMENDED",
            "userId": str(doctor_user.id),
            "role": doctor_user.role,
            "reason": req.amendmentReason.strip(),
            "timestamp": now,
        }

        new_items = [item.model_dump() for item in req.medicationItems]
        new_instructions = req.instructions.strip() if req.instructions else None

        presc_coll.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "medicationItems": new_items,
                    "instructions": new_instructions,
                    "status": PrescriptionStatus.AMENDED.value,
                    "updatedAt": now,
                },
                "$push": {
                    "amendmentHistory": amend_entry,
                    "auditLog": audit_entry,
                },
            },
        )
        cls._retire_outdated_patient_reminders(db, doc, new_items, now)

        return await cls.get_prescription(db, doctor_user, str(doc["_id"]))

    @classmethod
    def _retire_outdated_patient_reminders(cls, db: Database, doc: Dict[str, Any], new_items: List[Dict[str, Any]],
                                           now: datetime) -> None:
        """A04-BUG-008: reminders the patient set from the old instructions stop when those instructions change.

        A patient-created reminder copies the medicine, dose and frequency at creation and kept firing after an
        amendment (doctor-approved schedules already stop: the scheduler compares the prescription revision). A
        reminder whose item changed or disappeared is cancelled, and the patient is told to set it again from the
        updated prescription. Nothing is rescheduled automatically.
        """
        fields = ("medicationName", "strength", "dose", "route", "frequency", "duration", "additionalInstructions")
        old_items = doc.get("medicationItems") or []
        changed = [index for index, old in enumerate(old_items)
                   if index >= len(new_items) or any(old.get(k) != new_items[index].get(k) for k in fields)]
        if not changed:
            return
        result = db["medication_reminders"].update_many(
            {"prescriptionDbId": str(doc["_id"]), "prescriptionMedicationIndex": {"$in": changed},
             "approvedBy": {"$exists": False}, "status": "ACTIVE"},
            {"$set": {"status": "CANCELLED", "enabled": False, "updatedAt": now,
                      "cancelReason": "prescription_amended"}},
        )
        try:
            NotificationService.create_notification(
                db=db, recipient_user_id=str(doc["patientUserId"]), type=NotificationType.PRESCRIPTION_ISSUED,
                title="Prescription updated",
                body=("Your doctor updated a prescription. Open Medical Records to see the new instructions."
                      + (" Reminders set from the old instructions were stopped; set them again from the updated "
                         "prescription." if result.modified_count else "")),
                idempotency_key=f"prescription_amended_{doc['_id']}_{now.isoformat()}", send_push=True,
            )
        except Exception as exc:
            logger.warning("Prescription amendment notification failed (%s)", type(exc).__name__)

    @classmethod
    async def list_patient_prescriptions(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        page: int = 1,
        page_size: int = 20,
    ) -> PrescriptionListResponse:
        """List all digital prescriptions issued to the patient."""
        presc_coll = get_prescription_collection(db)
        filter_query = {"patientUserId": str(patient_user.id)}

        total = presc_coll.count_documents(filter_query)
        skip = (page - 1) * page_size
        cursor = presc_coll.find(filter_query).sort("issuedAt", DESCENDING).skip(skip).limit(page_size)

        items = []
        for doc in cursor:
            meta = cls._enrich_metadata(db, doc["doctorUserId"], doc["patientUserId"])
            items.append(
                PrescriptionResponseSchema(
                    id=str(doc["_id"]),
                    prescriptionId=doc["prescriptionId"],
                    medicalRecordId=doc.get("medicalRecordId"),
                    appointmentId=doc.get("appointmentId"),
                    patientUserId=doc["patientUserId"],
                    patientName=meta["patientName"],
                    doctorUserId=doc["doctorUserId"],
                    doctorName=meta["doctorName"],
                    doctorSpecialty=meta["doctorSpecialty"],
                    slmcRegistrationNumber=meta["slmcRegistrationNumber"],
                    hospitalOrClinic=meta["hospitalOrClinic"],
                    issuedAt=doc["issuedAt"],
                    status=doc["status"],
                    medicationItems=doc["medicationItems"],
                    instructions=doc.get("instructions"),
                    amendmentHistory=doc.get("amendmentHistory", []),
                    createdAt=doc["createdAt"],
                    updatedAt=doc["updatedAt"],
                )
            )

        return PrescriptionListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
        )

    @classmethod
    async def list_doctor_prescriptions(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        appointment_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PrescriptionListResponse:
        """List digital prescriptions issued by the doctor."""
        presc_coll = get_prescription_collection(db)
        filter_query: Dict[str, Any] = {"doctorUserId": str(doctor_user.id)}

        if appointment_id:
            filter_query["appointmentId"] = appointment_id
        if patient_id:
            filter_query["patientUserId"] = patient_id

        total = presc_coll.count_documents(filter_query)
        skip = (page - 1) * page_size
        cursor = presc_coll.find(filter_query).sort("issuedAt", DESCENDING).skip(skip).limit(page_size)

        items = []
        for doc in cursor:
            meta = cls._enrich_metadata(db, doc["doctorUserId"], doc["patientUserId"])
            items.append(
                PrescriptionResponseSchema(
                    id=str(doc["_id"]),
                    prescriptionId=doc["prescriptionId"],
                    medicalRecordId=doc.get("medicalRecordId"),
                    appointmentId=doc.get("appointmentId"),
                    patientUserId=doc["patientUserId"],
                    patientName=meta["patientName"],
                    doctorUserId=doc["doctorUserId"],
                    doctorName=meta["doctorName"],
                    doctorSpecialty=meta["doctorSpecialty"],
                    slmcRegistrationNumber=meta["slmcRegistrationNumber"],
                    hospitalOrClinic=meta["hospitalOrClinic"],
                    issuedAt=doc["issuedAt"],
                    status=doc["status"],
                    medicationItems=doc["medicationItems"],
                    instructions=doc.get("instructions"),
                    amendmentHistory=doc.get("amendmentHistory", []),
                    createdAt=doc["createdAt"],
                    updatedAt=doc["updatedAt"],
                )
            )

        return PrescriptionListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
        )

    # =======================================================================
    # 3. SECURE PRESCRIPTION PDF GENERATION
    # =======================================================================

    @classmethod
    async def generate_prescription_pdf(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        prescription_id: str,
    ) -> bytes:
        """Authenticate user, verify record authorization, and stream verified PDF document bytes."""
        presc_coll = get_prescription_collection(db)
        query = {"$or": [{"_id": ObjectId(prescription_id)}, {"prescriptionId": prescription_id}]} if ObjectId.is_valid(prescription_id) else {"prescriptionId": prescription_id}
        presc = presc_coll.find_one(query)

        if not presc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Digital prescription not found.",
            )

        user_id_str = str(current_user.id)
        if presc.get("patientUserId") != user_id_str and presc.get("doctorUserId") != user_id_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have authorization to download this prescription.",
            )

        # Log PDF download event in audit trail
        now = utc_now()
        presc_coll.update_one(
            {"_id": presc["_id"]},
            {"$push": {"auditLog": {"action": "PDF_DOWNLOADED", "userId": user_id_str, "role": current_user.role, "timestamp": now}}},
        )

        meta = cls._enrich_metadata(db, presc["doctorUserId"], presc["patientUserId"])
        rec_coll = get_medical_record_collection(db)
        record_ref = presc.get("medicalRecordId")
        medical_record = (rec_coll.find_one({"_id": ObjectId(record_ref)}) if ObjectId.is_valid(record_ref or "")
                          else rec_coll.find_one({"recordId": record_ref}) if record_ref else None)

        return PrescriptionPdfService.generate_prescription_pdf(
            prescription=presc,
            doctor=meta["doctor_user"],
            doctor_profile=meta["doctor_profile"],
            patient=meta["patient_user"],
            medical_record=medical_record,
        )
