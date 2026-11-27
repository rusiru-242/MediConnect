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
import logging
import re


from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.doctor_profile import DoctorVerificationStatus
from app.models.prescription import (
    CURRENT_PRESCRIPTION_STATUSES,
    MedicationItem,
    PrescriptionDocument,
    PrescriptionStatus,
    claim_submission,
    get_prescription_collection,
    release_submission,
    submission_key,
)
from app.models.prescription_renewal import (
    PrescriptionRenewalDocument,
    RenewalStatus,
    get_prescription_renewal_collection,
    renewal_pending_key,
    utc_now,
)
from app.models.user import UserRole
from app.schemas.clinical_workflow import (
    CreatePrescriptionDraftRequest,
    CreatePrescriptionRenewalRequest,
    DraftItemFinding,
    PrescriptionAssistantReviewResponse,
    PrescriptionDraftReviewRequest,
    PrescriptionDraftReviewResponse,
    PrescriptionRenewalListResponse,
    PrescriptionRenewalResponse,
    ReviewPrescriptionRenewalRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.clinical_safety_service import ClinicalSafetyService

logger = logging.getLogger(__name__)

SAFETY_GUIDANCE = (
    "PRESCRIPTION SAFETY GUIDANCE: Always confirm patient dosage, renal function, "
    "and contraindications before signing. MediConnect assistant highlights known records but "
    "does not replace formal clinical pharmacovigilance."
)
# A number followed by a unit, e.g. "500 mg", "250mg/5ml", "2%", "100 mcg/dose", "40 IU".
STRENGTH_UNIT = re.compile(r"\d\s*(?:mg|mcg|µg|ug|g|kg|ml|l|%|iu|units?|mmol|meq|mg/ml|puffs?|drops?)\b|\d\s*%",
                           re.I)


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
            allergyWarnings=safety_eval["allergyWarnings"],
            missingFieldsWarnings=missing_fields,
            safetyGuidance=SAFETY_GUIDANCE,
        )

    @classmethod
    def review_draft_items(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        req: PrescriptionDraftReviewRequest,
    ) -> PrescriptionDraftReviewResponse:
        """Structural check of clinician-entered items before signing (A04, deterministic).

        Reports missing required fields, repeated medicines, and frequency/duration/strength text the app cannot
        read for reminders. Nothing is added, completed, stored or signed: the draft is returned exactly as entered
        and stays unapproved. These are structural checks, not clinical dose or interaction checks.
        """
        from app.services.medication_reminder_service import prescribed_doses_per_day, prescribed_duration_days
        cls._assert_approved_doctor(db, doctor_user)
        ClinicalSafetyService.verify_doctor_patient_care_relationship(db, str(doctor_user.id), req.patientUserId)
        labels = {"medicationName": "medicine name", "strength": "strength", "dose": "dose",
                  "frequency": "frequency", "duration": "duration", "quantity": "quantity"}
        findings: List[DraftItemFinding] = []
        seen: Dict[str, str] = {}
        repeated: List[str] = []
        for index, item in enumerate(req.medicationItems):
            missing = [label for field, label in labels.items() if not getattr(item, field)]
            notes: List[str] = []
            if item.strength and not STRENGTH_UNIT.search(item.strength):
                notes.append(f"Strength '{item.strength}' has no unit the app recognises (for example mg, mcg, g, "
                             "ml, %, IU or units). Check it is complete.")
            if item.frequency and prescribed_doses_per_day(item.frequency) is None:
                notes.append(f"Frequency '{item.frequency}' does not state a fixed number of doses per day, so "
                             "medicine reminders cannot be scheduled from it. This is allowed (for example 'as "
                             "needed') but the patient will need clear instructions.")
            if item.duration and prescribed_duration_days(item.duration) is None:
                notes.append(f"Duration '{item.duration}' is not stated in days or weeks, so reminders cannot "
                             "be limited to the course automatically.")
            key = " ".join(item.medicationName.split()).casefold()
            if key and key in seen:
                repeated.append(item.medicationName)
            elif key:
                seen[key] = item.medicationName
            findings.append(DraftItemFinding(index=index, medicationName=item.medicationName,
                                             missingFields=missing, notes=notes))
        names = [item.medicationName for item in req.medicationItems if item.medicationName]
        safety_eval = ClinicalSafetyService.check_prescription_safety(db, req.patientUserId, names)
        missing_text = [f"Item {f.index + 1} ({f.medicationName or 'unnamed'}): missing " + ", ".join(f.missingFields)
                        for f in findings if f.missingFields]
        return PrescriptionDraftReviewResponse(
            patientUserId=req.patientUserId,
            documentedAllergies=safety_eval["documentedAllergies"],
            activeMedications=safety_eval["activeMedications"],
            potentialDuplicates=safety_eval["potentialDuplicates"],
            allergyWarnings=safety_eval["allergyWarnings"],
            missingFieldsWarnings=missing_text,
            safetyGuidance=SAFETY_GUIDANCE,
            readyToSign=not missing_text and not repeated,
            items=findings,
            repeatedMedicines=repeated,
            draft=req.medicationItems,
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

        appointment = cls._validated_visit(db, doc_user_id, req.patientUserId, req.appointmentId)
        item_dicts = [item.model_dump(by_alias=True, exclude_none=True) for item in med_items]  # as stored
        cls._reject_duplicate(db, doc_user_id, req.patientUserId, req.appointmentId, item_dicts)
        claim = submission_key(doc_user_id, req.patientUserId, req.appointmentId, item_dicts)
        if not claim_submission(db, claim):  # A04-BUG-003: a simultaneous identical submission
            raise HTTPException(status_code=409, detail="An identical prescription was just submitted.")
        try:
            return cls._store_signed(db, doctor_user, profile, req, appointment, med_items)
        except Exception:
            release_submission(db, claim)
            raise

    @classmethod
    def _store_signed(cls, db, doctor_user, profile, req, appointment, med_items) -> Dict[str, Any]:
        doc_user_id = str(doctor_user.id)
        record = db["medical_records"].find_one({"appointmentId": req.appointmentId}, {"_id": 1}) if appointment else None

        now = utc_now()
        prescription_id = f"RX-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        presc_doc = PrescriptionDocument(
            prescriptionId=prescription_id,
            # Real references only (P03-N07): a generated ObjectId used to be stored here, pointing at nothing.
            medicalRecordId=str(record["_id"]) if record else None,
            appointmentId=req.appointmentId if appointment else None,
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
        # No reminder schedule is created here (P03-N06). Reminder times are approved explicitly by the doctor
        # (PUT /care-automation/prescriptions/{id}/schedule) or set by the patient against the prescribed frequency.

        # A02-BUG-021: a prescription issued from the clinical workflow did not tell the patient it was available
        # (only the older consultation path did). Generic text: no medicine names on the lock screen or in the list.
        try:
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService
            NotificationService.create_notification(
                db=db, recipient_user_id=str(req.patientUserId), type=NotificationType.PRESCRIPTION_ISSUED,
                title="New prescription available",
                body="Your doctor issued a prescription. Open Medical Records in MediConnect to view it.",
                related_appointment_id=str(req.appointmentId) if getattr(req, "appointmentId", None) else None,
                idempotency_key=f"prescription_issued_{rx_db_id}", send_push=True,
            )
        except Exception as exc:  # the prescription itself is already issued
            logger.warning("Prescription notification failed (%s)", type(exc).__name__)

        return {
            "id": rx_db_id,
            "prescriptionId": prescription_id,
            "patientUserId": req.patientUserId,
            "doctorUserId": doc_user_id,
            "status": PrescriptionStatus.ISSUED.value,
            "medicationCount": len(med_items),
            "issuedAt": now,
            "reminderSchedule": "not_created",
        }

    @classmethod
    def _validated_visit(cls, db: Database, doctor_id: str, patient_id: str, appointment_id: Optional[str]):
        """A prescription may cite only this doctor's own confirmed or completed visit with this patient."""
        if not appointment_id:
            return None
        appt = db["appointments"].find_one({"_id": ObjectId(appointment_id)}) if ObjectId.is_valid(appointment_id) else None
        if (not appt or str(appt.get("doctorUserId")) != doctor_id or str(appt.get("patientUserId")) != patient_id
                or appt.get("status") not in {"CONFIRMED", "COMPLETED"}):
            raise HTTPException(status_code=400, detail="The appointment is not a confirmed visit of yours with this patient.")
        return appt

    @classmethod
    def _reject_duplicate(cls, db: Database, doctor_id: str, patient_id: str, appointment_id: Optional[str],
                          item_dicts: List[Dict[str, Any]]) -> None:
        """An identical prescription submitted again within 10 minutes is a repeated tap, not a new order."""
        recent = db["prescriptions"].find_one({
            "doctorUserId": doctor_id, "patientUserId": patient_id, "appointmentId": appointment_id,
            "status": {"$in": [PrescriptionStatus.ISSUED.value, PrescriptionStatus.AMENDED.value]},
            "createdAt": {"$gte": utc_now() - timedelta(minutes=10)},
            "medicationItems": item_dicts,
        }, {"prescriptionId": 1})
        if recent:
            raise HTTPException(status_code=409, detail=f"An identical prescription ({recent['prescriptionId']}) was just issued.")

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

        # A04-BUG-005: a cancelled prescription cannot be renewed, and only a medicine that is on the prescription
        # can be. A request naming any other medicine used to be stored (with empty details) and sent to the doctor.
        if rx.get("status") not in CURRENT_PRESCRIPTION_STATUSES:
            raise HTTPException(status_code=409, detail="This prescription is no longer current and cannot be renewed. "
                                                        "Ask your doctor for a new prescription.")
        wanted = " ".join(req.medicationName.split()).casefold()
        med_details = next((item for item in rx.get("medicationItems", [])
                            if " ".join(str(item.get("medicationName", "")).split()).casefold() == wanted), None)
        if med_details is None:
            raise HTTPException(status_code=422, detail="That medicine is not on this prescription. Choose a medicine "
                                                        "your doctor prescribed on it.")
        medication_name = med_details["medicationName"]  # the prescribed spelling, not the typed one

        # Existing pending renewal for this medication (case-insensitive, A04-BUG-006)
        renewal_coll = get_prescription_renewal_collection(db)
        pending_statuses = [RenewalStatus.REQUESTED.value, RenewalStatus.AWAITING_REVIEW.value]
        existing_pending = renewal_coll.find_one({
            "patientUserId": patient_id,
            "originalPrescriptionId": rx["prescriptionId"],
            "medicationName": {"$regex": f"^{re.escape(medication_name)}$", "$options": "i"},
            "status": {"$in": pending_statuses},
        })
        if existing_pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A renewal request for '{medication_name}' is already pending clinician review.",
            )

        now = utc_now()
        renewal_id = f"REN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        renewal_doc = PrescriptionRenewalDocument(
            renewalId=renewal_id,
            patientUserId=patient_id,
            originalPrescriptionId=rx["prescriptionId"],
            medicationName=medication_name,
            medicationDetails=med_details,
            doctorUserId=rx["doctorUserId"],
            doctorProfileId=rx.get("doctorProfileId"),
            status=RenewalStatus.REQUESTED.value,
            patientReason=req.patientReason.strip() if req.patientReason else None,
            requestedAt=now,
            createdAt=now,
            updatedAt=now,
        )

        row = renewal_doc.model_dump(by_alias=True, exclude_none=True)
        row["pendingKey"] = renewal_pending_key(patient_id, rx["prescriptionId"], medication_name)
        try:
            inserted = renewal_coll.insert_one(row)
        except DuplicateKeyError:  # a simultaneous identical request (unique pendingKey)
            raise HTTPException(status_code=409, detail=f"A renewal request for '{medication_name}' is already "
                                                        "pending clinician review.")
        try:  # Phase 02: the prescribing doctor is told a review is waiting (no medicine name in the push text)
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService
            NotificationService.create_notification(
                db=db, recipient_user_id=str(rx["doctorUserId"]), type=NotificationType.SYSTEM,
                title="Prescription renewal request",
                body="A patient has requested a prescription renewal. Open the renewal queue to review it.",
                idempotency_key=f"renewal_requested_{renewal_id}",
            )
        except Exception as notif_err:
            logger.warning("Renewal request notification failed (%s).", type(notif_err).__name__)

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
            # Only the prescribing doctor decides a renewal (Phase 02); there is no reassignment workflow.
            raise HTTPException(status_code=403, detail="Only the prescribing doctor can review this renewal.")

        if doc["status"] not in {RenewalStatus.REQUESTED.value, RenewalStatus.AWAITING_REVIEW.value}:
            raise HTTPException(status_code=400, detail=f"Renewal request is already finalized with status '{doc['status']}'.")
        if req.decision not in {"approve", "reject", "needs_consultation"}:
            raise HTTPException(status_code=400, detail="Invalid renewal review decision.")

        # Atomic claim: concurrent reviews cannot both issue a prescription.
        now = utc_now()
        lock = uuid.uuid4().hex
        claimed = coll.update_one(
            {"_id": doc["_id"], "status": {"$in": [RenewalStatus.REQUESTED.value, RenewalStatus.AWAITING_REVIEW.value]},
             "$or": [{"reviewLock": {"$exists": False}}, {"reviewLockAt": {"$lt": now - timedelta(minutes=2)}}]},
            {"$set": {"reviewLock": lock, "reviewLockAt": now}},
        )
        if not claimed.matched_count:
            raise HTTPException(status_code=409, detail="This renewal is already being reviewed.")
        resulting_rx_id = None

        if req.decision == "approve":
            new_status = RenewalStatus.APPROVED.value
            # Generate new authorized prescription for the renewed medication
            try:
                resulting_rx_id = cls._issue_renewal_prescription(db, doctor_user, profile, doc, req.adjustedDuration)
            except HTTPException:
                # Nothing was issued: release the claim so the doctor can choose another decision.
                coll.update_one({"_id": doc["_id"], "reviewLock": lock}, {"$unset": {"reviewLock": "", "reviewLockAt": ""}})
                raise
        elif req.decision == "reject":
            new_status = RenewalStatus.REJECTED.value
        elif req.decision == "needs_consultation":
            new_status = RenewalStatus.NEEDS_CONSULTATION.value
        else:
            raise HTTPException(status_code=400, detail="Invalid renewal review decision.")

        coll.update_one(
            {"_id": doc["_id"], "reviewLock": lock},
            {
                "$unset": {"reviewLock": "", "reviewLockAt": "", "pendingKey": ""},
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
        try:  # the patient learns the decision; the reason is shown in the app, not in the push text
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService
            NotificationService.create_notification(
                db=db, recipient_user_id=str(doc["patientUserId"]), type=NotificationType.SYSTEM,
                title="Prescription renewal update",
                body={"approved": "Your prescription renewal was approved by your doctor.",
                      "rejected": "Your doctor did not approve the renewal. Open MediConnect for the explanation.",
                      }.get(new_status, "Your doctor asked for a consultation before renewing. Open MediConnect for details."),
                idempotency_key=f"renewal_decided_{doc['_id']}",
            )
        except Exception as notif_err:
            logger.warning("Renewal decision notification failed (%s).", type(notif_err).__name__)
        return cls._to_renewal_response(
            PrescriptionRenewalDocument.model_validate(updated),
            str(updated["_id"]),
            None,
            doctor_user.fullName,
        )

    # -----------------------------------------------------------------------
    # Helper: Issue the renewed prescription
    # -----------------------------------------------------------------------
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
        med_details = renewal_doc.get("medicationDetails") or {}
        # Renew exactly what was prescribed (P03-N08): no "Standard" strength, "1 dose", "Once daily" or
        # "30 days" defaults. Incomplete source details mean a new prescription is needed instead.
        required = ("strength", "dose", "frequency", "duration", "quantity")
        missing = [field for field in required if not str(med_details.get(field) or "").strip()]
        if duration_override:
            missing = [field for field in missing if field != "duration"]
        if missing:
            raise HTTPException(status_code=409, detail="The original prescription is missing " + ", ".join(missing)
                                + ". Issue a new prescription instead of renewing it.")
        original = db["prescriptions"].find_one({"prescriptionId": renewal_doc.get("originalPrescriptionId"),
                                                 "patientUserId": renewal_doc["patientUserId"]}) or {}

        item = MedicationItem(
            medicationName=renewal_doc["medicationName"],
            strength=med_details["strength"],
            dose=med_details["dose"],
            route=med_details.get("route") or "Oral",
            frequency=med_details["frequency"],
            duration=duration_override or med_details["duration"],
            quantity=med_details["quantity"],
            additionalInstructions=med_details.get("additionalInstructions"),
        )

        doc = PrescriptionDocument(
            prescriptionId=rx_id,
            # The renewal belongs to the original consultation, not to a generated id (P03-N07).
            medicalRecordId=original.get("medicalRecordId"),
            appointmentId=original.get("appointmentId"),
            patientUserId=renewal_doc["patientUserId"],
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(profile["_id"]),
            issuedAt=now,
            status=PrescriptionStatus.ISSUED.value,
            medicationItems=[item],
            instructions=f"Renewal of {renewal_doc.get('originalPrescriptionId')} approved by the prescribing doctor.",
            auditLog=[{"action": "RENEWAL_APPROVED", "userId": str(doctor_user.id), "timestamp": now,
                       "renewalId": renewal_doc.get("renewalId")}],
            createdAt=now,
            updatedAt=now,
        )

        coll = get_prescription_collection(db)
        inserted = coll.insert_one(doc.model_dump(by_alias=True, exclude_none=True))
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
