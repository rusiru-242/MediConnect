"""Prescription Workflow & Renewal Service (Phase 6).

Implements:
1. Doctor Prescription Assistant (checks allergies, duplicates, missing fields).
2. Prescription Signing & sync to Phase 3 medication reminders.
3. Patient Prescription Renewal Workflow:
   REQUESTED -> AWAITING_REVIEW -> (APPROVED | REJECTED | NEEDS_CONSULTATION)
4. Enforces: Only human authorized doctors can sign or approve prescriptions.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.doctor_profile import DoctorVerificationStatus
from app.models.prescription import (
    MedicationItem,
    PrescriptionDocument,
    PrescriptionStatus,
    get_prescription_collection,
)
from app.models.prescription_renewal import (
    PrescriptionRenewalDocument,
    RenewalStatus,
    get_prescription_renewal_collection,
    utc_now,
)
from app.models.user import UserRole
from app.schemas.clinical_workflow import (
    CreatePrescriptionDraftRequest,
    CreatePrescriptionRenewalRequest,
    PrescriptionAssistantReviewResponse,
    PrescriptionRenewalListResponse,
    PrescriptionRenewalResponse,
    ReviewPrescriptionRenewalRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.clinical_safety_service import ClinicalSafetyService


class PrescriptionWorkflowService:
    """Core service for prescription documentation assistance and the prescription renewal lifecycle."""

    @classmethod
    def _assert_approved_doctor(cls, db: Database, user: UserResponseSchema) -> Dict[str, Any]:
        """Verify user is an active, verified doctor with SLMC credentials."""
        if user.role != UserRole.DOCTOR.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only healthcare practitioners are permitted to prescribe or review renewals.",
            )
        profile = db["doctor_profiles"].find_one({"userId": str(user.id)})
        if not profile:
            raise HTTPException(status_code=403, detail="Doctor profile not found.")
        if profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=403,
                detail="Doctor accreditation is pending approval. Only verified doctors can sign prescriptions.",
            )
        return profile

    # -----------------------------------------------------------------------
    # Doctor Prescription Assistant Review
    # -----------------------------------------------------------------------
    @classmethod
    def review_prescription_draft(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        patient_user_id: str,
        medication_names: List[str],
    ) -> PrescriptionAssistantReviewResponse:
        """Analyze proposed medications against documented allergies and active prescriptions."""
        cls._assert_approved_doctor(db, doctor_user)
        ClinicalSafetyService.verify_doctor_patient_care_relationship(db, str(doctor_user.id), patient_user_id)

        safety_eval = ClinicalSafetyService.check_prescription_safety(db, patient_user_id, medication_names)

        missing_fields: List[str] = []
        for name in medication_names:
            if not name or len(name.strip()) < 2:
                missing_fields.append("Medication name must be specified.")

        return PrescriptionAssistantReviewResponse(
            patientUserId=patient_user_id,
            documentedAllergies=safety_eval["documentedAllergies"],
            activeMedications=safety_eval["activeMedications"],
            potentialDuplicates=safety_eval["potentialDuplicates"],
            missingFieldsWarnings=missing_fields,
            safetyGuidance=(
                "PRESCRIPTION SAFETY GUIDANCE: Always confirm patient dosage, renal function, "
                "and contraindications before signing. MediConnect assistant highlights known records but "
                "does not replace formal clinical pharmacovigilance."
            ),
        )

    # -----------------------------------------------------------------------
    # Doctor Sign & Issue Prescription
    # -----------------------------------------------------------------------
    @classmethod
    def sign_prescription(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        req: CreatePrescriptionDraftRequest,
    ) -> Dict[str, Any]:
        """Authorize, sign, and issue a digital prescription, syncing to medication reminders."""
        profile = cls._assert_approved_doctor(db, doctor_user)
        doc_user_id = str(doctor_user.id)
        ClinicalSafetyService.verify_doctor_patient_care_relationship(db, doc_user_id, req.patientUserId)

        # Validate items
        if not req.medicationItems:
            raise HTTPException(status_code=400, detail="At least one medication item must be prescribed.")

        med_items: List[MedicationItem] = []
        for item in req.medicationItems:
            med_items.append(
                MedicationItem(
                    medicationName=item.medicationName.strip(),
                    strength=item.strength.strip(),
                    dose=item.dose.strip(),
                    route=item.route.strip(),
                    frequency=item.frequency.strip(),
                    duration=item.duration.strip(),
                    quantity=item.quantity.strip(),
                    additionalInstructions=item.additionalInstructions.strip() if item.additionalInstructions else None,
                )
            )

        now = utc_now()
        prescription_id = f"RX-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        presc_doc = PrescriptionDocument(
            prescriptionId=prescription_id,
            medicalRecordId=str(ObjectId()),  # Linked medical record reference
            appointmentId=req.appointmentId or str(ObjectId()),
            patientUserId=req.patientUserId,
            doctorUserId=doc_user_id,
            doctorProfileId=str(profile["_id"]),
            issuedAt=now,
            status=PrescriptionStatus.ISSUED.value,
            medicationItems=med_items,
            instructions=req.instructions.strip() if req.instructions else None,
            auditLog=[{"action": "SIGNED", "userId": doc_user_id, "timestamp": now}],
            createdAt=now,
            updatedAt=now,
        )

        coll = get_prescription_collection(db)
        inserted = coll.insert_one(presc_doc.model_dump(by_alias=True, exclude_none=True))
        rx_db_id = str(inserted.inserted_id)

        # Synchronize to Phase 3 medication_reminders collection
        cls._sync_to_medication_reminders(db, rx_db_id, presc_doc, doc_user_id)

        return {
            "id": rx_db_id,
            "prescriptionId": prescription_id,
            "patientUserId": req.patientUserId,
            "doctorUserId": doc_user_id,
            "status": PrescriptionStatus.ISSUED.value,
            "medicationCount": len(med_items),
            "issuedAt": now,
        }

    # -----------------------------------------------------------------------
    # Prescription Renewal Lifecycle
    # -----------------------------------------------------------------------
    @classmethod
    def request_prescription_renewal(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        req: CreatePrescriptionRenewalRequest,
    ) -> PrescriptionRenewalResponse:
        """Patient initiates a renewal request for an existing prescription."""
        patient_id = str(patient_user.id)

        # 1. Verify existing prescription ownership
        presc_coll = get_prescription_collection(db)
        query = {
            "patientUserId": patient_id,
            "$or": [
                {"prescriptionId": req.originalPrescriptionId},
                {"_id": ObjectId(req.originalPrescriptionId)} if ObjectId.is_valid(req.originalPrescriptionId) else {"prescriptionId": req.originalPrescriptionId},
            ],
        }
        rx = presc_coll.find_one(query)
        if not rx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original prescription not found in your patient record.",
            )

        # Check existing pending renewal for this medication
        renewal_coll = get_prescription_renewal_collection(db)
        existing_pending = renewal_coll.find_one({
            "patientUserId": patient_id,
            "originalPrescriptionId": rx["prescriptionId"],
            "medicationName": req.medicationName.strip(),
            "status": {"$in": [RenewalStatus.REQUESTED.value, RenewalStatus.AWAITING_REVIEW.value]},
        })
        if existing_pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A renewal request for '{req.medicationName}' is already pending clinician review.",
            )

        # Extract item details from prescription
        med_details = {}
        for item in rx.get("medicationItems", []):
            if item.get("medicationName", "").lower() == req.medicationName.strip().lower():
                med_details = item
                break

        now = utc_now()
        renewal_id = f"REN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        renewal_doc = PrescriptionRenewalDocument(
            renewalId=renewal_id,
            patientUserId=patient_id,
            originalPrescriptionId=rx["prescriptionId"],
            medicationName=req.medicationName.strip(),
            medicationDetails=med_details,
            doctorUserId=rx["doctorUserId"],
            doctorProfileId=rx.get("doctorProfileId"),
            status=RenewalStatus.REQUESTED.value,
            patientReason=req.patientReason.strip() if req.patientReason else None,
            requestedAt=now,
            createdAt=now,
            updatedAt=now,
        )

        inserted = renewal_coll.insert_one(renewal_doc.model_dump(by_alias=True, exclude_none=True))

        return cls._to_renewal_response(renewal_doc, str(inserted.inserted_id), patient_user.fullName)

    @classmethod
    def list_renewal_requests(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        status_filter: Optional[str] = None,
    ) -> PrescriptionRenewalListResponse:
        """List renewal requests for patient or doctor."""
        user_id_str = str(current_user.id)
        coll = get_prescription_renewal_collection(db)

        if current_user.role == UserRole.DOCTOR.value:
            cls._assert_approved_doctor(db, current_user)
            query: Dict[str, Any] = {"doctorUserId": user_id_str}
        else:
            query = {"patientUserId": user_id_str}

        if status_filter and status_filter != "ALL":
            query["status"] = status_filter

        cursor = coll.find(query).sort("requestedAt", -1).limit(50)
        renewals: List[PrescriptionRenewalResponse] = []
        for doc in cursor:
            pat = db["users"].find_one({"_id": ObjectId(doc["patientUserId"])}) if ObjectId.is_valid(doc["patientUserId"]) else {}
            doc_user = db["users"].find_one({"_id": ObjectId(doc["doctorUserId"])}) if ObjectId.is_valid(doc["doctorUserId"]) else {}
            pat_name = pat.get("fullName", "Patient")
            doc_name = f"Dr. {doc_user.get('fullName', 'Doctor')}"
            renewals.append(
                cls._to_renewal_response(
                    PrescriptionRenewalDocument.model_validate(doc),
                    str(doc["_id"]),
                    pat_name,
                    doc_name,
                )
            )

        return PrescriptionRenewalListResponse(renewals=renewals, total=len(renewals))

    @classmethod
    def review_renewal_request(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        renewal_id: str,
        req: ReviewPrescriptionRenewalRequest,
    ) -> PrescriptionRenewalResponse:
        """Doctor reviews and authorizes, rejects, or requests consultation for a prescription renewal."""
        profile = cls._assert_approved_doctor(db, doctor_user)
        doc_user_id = str(doctor_user.id)
        coll = get_prescription_renewal_collection(db)

        query = {"$or": [{"_id": ObjectId(renewal_id)}, {"renewalId": renewal_id}]} if ObjectId.is_valid(renewal_id) else {"renewalId": renewal_id}
        doc = coll.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Prescription renewal request not found.")

        if doc["doctorUserId"] != doc_user_id:
            # Check care relationship if reassigned
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, doc_user_id, doc["patientUserId"])

        if doc["status"] not in {RenewalStatus.REQUESTED.value, RenewalStatus.AWAITING_REVIEW.value}:
            raise HTTPException(status_code=400, detail=f"Renewal request is already finalized with status '{doc['status']}'.")

        now = utc_now()
        resulting_rx_id = None

        if req.decision == "approve":
            new_status = RenewalStatus.APPROVED.value
            # Generate new authorized prescription for the renewed medication
            resulting_rx_id = cls._issue_renewal_prescription(db, doctor_user, profile, doc, req.adjustedDuration)
        elif req.decision == "reject":
            new_status = RenewalStatus.REJECTED.value
        elif req.decision == "needs_consultation":
            new_status = RenewalStatus.NEEDS_CONSULTATION.value
        else:
            raise HTTPException(status_code=400, detail="Invalid renewal review decision.")

        coll.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "status": new_status,
                    "doctorDecisionReason": req.reason.strip(),
                    "consultationDetails": req.consultationDetails.strip() if req.consultationDetails else None,
                    "resultingPrescriptionId": resulting_rx_id,
                    "reviewedAt": now,
                    "reviewedByDoctorId": doc_user_id,
                    "reviewedByDoctorName": doctor_user.fullName,
                    "updatedAt": now,
                }
            },
        )

        updated = coll.find_one({"_id": doc["_id"]})
        return cls._to_renewal_response(
            PrescriptionRenewalDocument.model_validate(updated),
            str(updated["_id"]),
            None,
            doctor_user.fullName,
        )

    # -----------------------------------------------------------------------
    # Helper: Sync to Medication Reminders
    # -----------------------------------------------------------------------
    @classmethod
    def _sync_to_medication_reminders(
        cls,
        db: Database,
        rx_db_id: str,
        presc_doc: PrescriptionDocument,
        doctor_id: str,
    ) -> None:
        """Create or update Phase 3 medication reminder entries for prescribed drugs."""
        now = utc_now()
        for idx, item in enumerate(presc_doc.medicationItems):
            approval_key = f"{rx_db_id}:{idx}"
            db["medication_reminders"].update_one(
                {"approvalKey": approval_key},
                {
                    "$set": {
                        "patientUserId": presc_doc.patientUserId,
                        "prescriptionDbId": rx_db_id,
                        "prescriptionId": presc_doc.prescriptionId,
                        "prescriptionMedicationIndex": idx,
                        "medicationName": item.medicationName,
                        "strength": item.strength,
                        "dose": item.dose,
                        "route": item.route,
                        "frequency": item.frequency,
                        "duration": item.duration,
                        "scheduledTimes": ["08:00", "20:00"],
                        "patientTimezone": "Asia/Colombo",
                        "startDate": now,
                        "endDate": now + timedelta(days=14),
                        "approvedBy": doctor_id,
                        "status": "ACTIVE",
                        "enabled": True,
                        "updatedAt": now,
                    },
                    "$setOnInsert": {
                        "reminderId": f"REM-{uuid.uuid4().hex[:6].upper()}",
                        "createdAt": now,
                    },
                },
                upsert=True,
            )

    @classmethod
    def _issue_renewal_prescription(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        profile: Dict[str, Any],
        renewal_doc: Dict[str, Any],
        duration_override: Optional[str] = None,
    ) -> str:
        """Issue a fresh signed prescription upon doctor renewal approval."""
        now = utc_now()
        rx_id = f"RX-REN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        med_details = renewal_doc.get("medicationDetails", {})
        duration = duration_override or med_details.get("duration", "30 days")

        item = MedicationItem(
            medicationName=renewal_doc["medicationName"],
            strength=med_details.get("strength", "Standard"),
            dose=med_details.get("dose", "1 dose"),
            route=med_details.get("route", "Oral"),
            frequency=med_details.get("frequency", "Once daily"),
            duration=duration,
            quantity=med_details.get("quantity", "1 refill"),
            additionalInstructions="Prescription renewed by clinician.",
        )

        doc = PrescriptionDocument(
            prescriptionId=rx_id,
            medicalRecordId=str(ObjectId()),
            appointmentId=str(ObjectId()),
            patientUserId=renewal_doc["patientUserId"],
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(profile["_id"]),
            issuedAt=now,
            status=PrescriptionStatus.ISSUED.value,
            medicationItems=[item],
            instructions=f"Prescription renewal approved: {renewal_doc.get('patientReason') or 'Standard refill'}",
            auditLog=[{"action": "RENEWAL_APPROVED", "userId": str(doctor_user.id), "timestamp": now}],
            createdAt=now,
            updatedAt=now,
        )

        coll = get_prescription_collection(db)
        inserted = coll.insert_one(doc.model_dump(by_alias=True, exclude_none=True))
        cls._sync_to_medication_reminders(db, str(inserted.inserted_id), doc, str(doctor_user.id))
        return rx_id

    @classmethod
    def _to_renewal_response(
        cls,
        doc: PrescriptionRenewalDocument,
        obj_id: str,
        patient_name: Optional[str] = None,
        doctor_name: Optional[str] = None,
    ) -> PrescriptionRenewalResponse:
        return PrescriptionRenewalResponse(
            id=obj_id,
            renewalId=doc.renewalId,
            patientUserId=doc.patientUserId,
            patientName=patient_name,
            originalPrescriptionId=doc.originalPrescriptionId,
            medicationName=doc.medicationName,
            medicationDetails=doc.medicationDetails,
            doctorUserId=doc.doctorUserId,
            doctorName=doctor_name or doc.reviewedByDoctorName,
            status=doc.status,
            patientReason=doc.patientReason,
            doctorDecisionReason=doc.doctorDecisionReason,
            consultationDetails=doc.consultationDetails,
            resultingPrescriptionId=doc.resultingPrescriptionId,
            requestedAt=doc.requestedAt,
            reviewedAt=doc.reviewedAt,
            createdAt=doc.createdAt,
            updatedAt=doc.updatedAt,
        )
