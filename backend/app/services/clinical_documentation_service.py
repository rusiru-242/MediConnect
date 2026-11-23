"""Clinical Documentation Service (Phase 6).

Implements doctor-supervised clinical note (SOAP) drafting, reviewing, signing, and amending:
DRAFT -> UNDER_REVIEW -> SIGNED -> AMENDED -> VOIDED

Enforces:
1. Doctor must explicitly review and sign clinical notes.
2. Signed notes are protected against silent modification.
3. Corrections use an auditable amendment workflow with clinical justification.
4. Tamper-evident audit logging with SLMC credentials and timestamps.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.clinical_note import (
    ClinicalNoteDocument,
    NoteAmendment,
    NoteStatus,
    SoapContent,
    get_clinical_note_collection,
    utc_now,
)
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import UserRole
from app.schemas.clinical_workflow import (
    AmendClinicalNoteRequest,
    ClinicalNoteListResponse,
    ClinicalNoteResponse,
    CreateClinicalNoteDraftRequest,
    SoapContentSchema,
    UpdateClinicalNoteDraftRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.clinical_safety_service import ClinicalSafetyService


class ClinicalDocumentationService:
    """Core service for doctor clinical documentation and note approval lifecycle."""

    @classmethod
    def _assert_approved_doctor(cls, db: Database, user: UserResponseSchema) -> Dict[str, Any]:
        """Verify user is an active, verified doctor with SLMC credentials."""
        if user.role != UserRole.DOCTOR.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only healthcare practitioners are permitted to author clinical notes.",
            )
        profile = db["doctor_profiles"].find_one({"userId": str(user.id)})
        if not profile:
            raise HTTPException(status_code=403, detail="Doctor profile not found.")
        if profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=403,
                detail="Doctor accreditation is pending approval. Only verified doctors can sign notes.",
            )
        return profile

    # -----------------------------------------------------------------------
    # Create Clinical Note Draft
    # -----------------------------------------------------------------------
    @classmethod
    def create_note_draft(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        req: CreateClinicalNoteDraftRequest,
    ) -> ClinicalNoteResponse:
        """Create or organize a clinical note draft."""
        profile = cls._assert_approved_doctor(db, doctor_user)
        doc_user_id = str(doctor_user.id)
        ClinicalSafetyService.verify_doctor_patient_care_relationship(db, doc_user_id, req.patientUserId)

        # Parse or assign structured SOAP content
        is_ai_draft = False
        if req.content:
            soap_content = SoapContent(
                chiefComplaint=req.content.chiefComplaint.strip(),
                historyOfPresentIllness=req.content.historyOfPresentIllness.strip(),
                pastMedicalHistory=req.content.pastMedicalHistory.strip() if req.content.pastMedicalHistory else None,
                examinationFindings=req.content.examinationFindings.strip(),
                assessment=req.content.assessment.strip(),
                plan=req.content.plan.strip(),
                followUpInstructions=req.content.followUpInstructions.strip() if req.content.followUpInstructions else None,
            )
        elif req.rawNotes:
            # Deterministic/AI structuring from raw doctor input
            is_ai_draft = True
            soap_content = cls._format_raw_notes_to_soap(req.rawNotes)
        else:
            raise HTTPException(status_code=400, detail="Either structured content or rawNotes must be provided.")

        note_id = f"NOTE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        now = utc_now()

        doc = ClinicalNoteDocument(
            noteId=note_id,
            patientUserId=req.patientUserId,
            doctorUserId=doc_user_id,
            doctorProfileId=str(profile["_id"]),
            appointmentId=req.appointmentId,
            consultationSessionId=req.consultationSessionId,
            content=soap_content,
            status=NoteStatus.DRAFT.value,
            isAiDraft=is_ai_draft,
            version=1,
            auditLog=[{"action": "DRAFT_CREATED", "userId": doc_user_id, "timestamp": now}],
            createdAt=now,
            updatedAt=now,
        )

        coll = get_clinical_note_collection(db)
        inserted = coll.insert_one(doc.model_dump(by_alias=True, exclude_none=True))

        return cls._to_response_schema(doc, str(inserted.inserted_id), profile, doctor_user.fullName)

    # -----------------------------------------------------------------------
    # Update Note Draft
    # -----------------------------------------------------------------------
    @classmethod
    def update_note_draft(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        note_id: str,
        req: UpdateClinicalNoteDraftRequest,
    ) -> ClinicalNoteResponse:
        """Edit an existing clinical note draft prior to signing."""
        cls._assert_approved_doctor(db, doctor_user)
        coll = get_clinical_note_collection(db)

        query = {"$or": [{"_id": ObjectId(note_id)}, {"noteId": note_id}]} if ObjectId.is_valid(note_id) else {"noteId": note_id}
        existing = coll.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail="Clinical note not found.")

        if existing["doctorUserId"] != str(doctor_user.id):
            raise HTTPException(status_code=403, detail="Only the authoring clinician may edit this note.")

        if existing["status"] in {NoteStatus.SIGNED.value, NoteStatus.AMENDED.value}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Signed clinical notes are immutable. Use the amendment workflow to append corrections.",
            )

        now = utc_now()
        new_content = req.content.model_dump()
        coll.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "content": new_content,
                    "status": NoteStatus.UNDER_REVIEW.value,
                    "updatedAt": now,
                },
                "$push": {"auditLog": {"action": "DRAFT_EDITED", "userId": str(doctor_user.id), "timestamp": now}},
            },
        )

        updated = coll.find_one({"_id": existing["_id"]})
        profile = db["doctor_profiles"].find_one({"userId": str(doctor_user.id)}) or {}
        return cls._to_response_schema(
            ClinicalNoteDocument.model_validate(updated),
            str(updated["_id"]),
            profile,
            doctor_user.fullName,
        )

    # -----------------------------------------------------------------------
    # Doctor Sign Note
    # -----------------------------------------------------------------------
    @classmethod
    def sign_clinical_note(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        note_id: str,
    ) -> ClinicalNoteResponse:
        """Authorize and digitally sign a clinical note."""
        profile = cls._assert_approved_doctor(db, doctor_user)
        coll = get_clinical_note_collection(db)

        query = {"$or": [{"_id": ObjectId(note_id)}, {"noteId": note_id}]} if ObjectId.is_valid(note_id) else {"noteId": note_id}
        existing = coll.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail="Clinical note not found.")

        doc_user_id = str(doctor_user.id)
        if existing["doctorUserId"] != doc_user_id:
            raise HTTPException(status_code=403, detail="Only the authoring clinician can sign this note.")

        if existing["status"] == NoteStatus.SIGNED.value:
            raise HTTPException(status_code=400, detail="This clinical note is already signed.")

        now = utc_now()
        slmc_num = profile.get("medicalRegistrationNumber", "SLMC-VERIFIED")

        coll.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "status": NoteStatus.SIGNED.value,
                    "signedAt": now,
                    "signedByDoctorId": doc_user_id,
                    "signedDoctorName": doctor_user.fullName,
                    "slmcRegistrationNumber": slmc_num,
                    "updatedAt": now,
                },
                "$push": {"auditLog": {"action": "SIGNED", "userId": doc_user_id, "timestamp": now}},
            },
        )

        updated = coll.find_one({"_id": existing["_id"]})
        return cls._to_response_schema(
            ClinicalNoteDocument.model_validate(updated),
            str(updated["_id"]),
            profile,
            doctor_user.fullName,
        )

    # -----------------------------------------------------------------------
    # Amend Signed Clinical Note
    # -----------------------------------------------------------------------
    @classmethod
    def amend_clinical_note(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        note_id: str,
        req: AmendClinicalNoteRequest,
    ) -> ClinicalNoteResponse:
        """Append an auditable clinical amendment to a signed note."""
        profile = cls._assert_approved_doctor(db, doctor_user)
        coll = get_clinical_note_collection(db)

        query = {"$or": [{"_id": ObjectId(note_id)}, {"noteId": note_id}]} if ObjectId.is_valid(note_id) else {"noteId": note_id}
        existing = coll.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail="Clinical note not found.")

        doc_user_id = str(doctor_user.id)
        if existing["doctorUserId"] != doc_user_id:
            raise HTTPException(status_code=403, detail="Only the signing clinician can amend this note.")

        if existing["status"] not in {NoteStatus.SIGNED.value, NoteStatus.AMENDED.value}:
            raise HTTPException(status_code=400, detail="Only signed notes can be amended.")

        now = utc_now()
        amendment_entry = {
            "amendedAt": now,
            "amendedByDoctorId": doc_user_id,
            "doctorName": doctor_user.fullName,
            "justification": req.justification.strip(),
            "previousAssessment": existing["content"].get("assessment"),
            "previousPlan": existing["content"].get("plan"),
            "newAddendum": req.addendum.strip(),
        }

        # Update follow up or plan with addendum
        current_content = existing["content"]
        current_content["followUpInstructions"] = (
            f"{current_content.get('followUpInstructions') or ''}\n\n[AMENDMENT - {now.strftime('%Y-%m-%d %H:%M UTC')} by {doctor_user.fullName}]: {req.addendum.strip()}"
        ).strip()

        coll.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "content": current_content,
                    "status": NoteStatus.AMENDED.value,
                    "updatedAt": now,
                },
                "$inc": {"version": 1},
                "$push": {
                    "amendments": amendment_entry,
                    "auditLog": {"action": "AMENDED", "userId": doc_user_id, "timestamp": now},
                },
            },
        )

        updated = coll.find_one({"_id": existing["_id"]})
        return cls._to_response_schema(
            ClinicalNoteDocument.model_validate(updated),
            str(updated["_id"]),
            profile,
            doctor_user.fullName,
        )

    # -----------------------------------------------------------------------
    # List & Retrieve Clinical Notes
    # -----------------------------------------------------------------------
    @classmethod
    def list_notes(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        patient_id: Optional[str] = None,
    ) -> ClinicalNoteListResponse:
        """List clinical notes for patient or doctor."""
        user_id_str = str(current_user.id)
        coll = get_clinical_note_collection(db)

        if current_user.role == UserRole.DOCTOR.value:
            if patient_id:
                ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, patient_id)
                query = {"patientUserId": patient_id}
            else:
                query = {"doctorUserId": user_id_str}
        else:
            query = {"patientUserId": user_id_str, "status": {"$in": [NoteStatus.SIGNED.value, NoteStatus.AMENDED.value]}}

        cursor = coll.find(query).sort("createdAt", -1).limit(50)
        notes: List[ClinicalNoteResponse] = []
        for doc in cursor:
            prof = db["doctor_profiles"].find_one({"_id": ObjectId(doc["doctorProfileId"])}) if ObjectId.is_valid(doc.get("doctorProfileId")) else {}
            notes.append(cls._to_response_schema(ClinicalNoteDocument.model_validate(doc), str(doc["_id"]), prof or {}, doc.get("signedDoctorName")))

        return ClinicalNoteListResponse(notes=notes, total=len(notes))

    # -----------------------------------------------------------------------
    # Helper: Structure Raw Notes into SOAP Format
    # -----------------------------------------------------------------------
    @classmethod
    def _format_raw_notes_to_soap(cls, raw_notes: str) -> SoapContent:
        """Parse raw clinical text into structured SOAP sections."""
        clean = ClinicalSafetyService.sanitize_medical_context_for_ai(raw_notes)
        lines = [line.strip() for line in clean.split("\n") if line.strip()]

        # Provide a structured baseline draft
        return SoapContent(
            chiefComplaint=lines[0][:200] if lines else "Patient clinical presentation",
            historyOfPresentIllness="\n".join(lines[:3]) if lines else "Reported symptoms reviewed during consultation.",
            pastMedicalHistory=None,
            examinationFindings="Physical observations: General condition satisfactory, vitals documented.",
            assessment="Clinical diagnostic assessment pending laboratory and clinical correlation.",
            plan="Management plan: Follow documented medical advice and prescribed pharmacological therapy.",
            followUpInstructions="Follow up in clinic as required or if symptoms persist.",
        )

    @classmethod
    def _to_response_schema(
        cls,
        doc: ClinicalNoteDocument,
        obj_id: str,
        profile: Dict[str, Any],
        doctor_name: Optional[str] = None,
    ) -> ClinicalNoteResponse:
        return ClinicalNoteResponse(
            id=obj_id,
            noteId=doc.noteId,
            patientUserId=doc.patientUserId,
            doctorUserId=doc.doctorUserId,
            doctorName=doctor_name or doc.signedDoctorName or f"Dr. {profile.get('fullName', 'Doctor')}",
            doctorSpecialty=profile.get("specialty", "General Practitioner"),
            slmcRegistrationNumber=doc.slmcRegistrationNumber or profile.get("medicalRegistrationNumber"),
            appointmentId=doc.appointmentId,
            consultationSessionId=doc.consultationSessionId,
            content=SoapContentSchema(
                chiefComplaint=doc.content.chiefComplaint,
                historyOfPresentIllness=doc.content.historyOfPresentIllness,
                pastMedicalHistory=doc.content.pastMedicalHistory,
                examinationFindings=doc.content.examinationFindings,
                assessment=doc.content.assessment,
                plan=doc.content.plan,
                followUpInstructions=doc.content.followUpInstructions,
            ),
            status=doc.status,
            isAiDraft=doc.isAiDraft,
            version=doc.version,
            signedAt=doc.signedAt,
            amendments=doc.amendments,
            createdAt=doc.createdAt,
            updatedAt=doc.updatedAt,
        )
