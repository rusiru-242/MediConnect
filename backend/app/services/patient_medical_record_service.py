"""Patient Medical Record Service (Phase 6).

Implements:
1. Longitudinal medical record storage with 10 record categories.
2. Secure private medical document upload (PDF, JPG, PNG) with integrity hashing and magic-byte checks.
3. Access-controlled document streaming and short-lived authorized download tokens.
4. Tamper-evident audit trails for views and downloads.
5. Source-grounded clinical history summarization with date citations and data disclosure warnings.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pymongo.database import Database

from app.config.settings import settings
from app.models.patient_medical_record import (
    DocumentMetadata,
    PatientMedicalRecordDocument,
    RecordStatus,
    RecordType,
    SourceType,
    get_patient_medical_record_collection,
    utc_now,
)
from app.models.user import UserRole
from app.schemas.clinical_workflow import (
    CreatePatientMedicalRecordRequest,
    DocumentDownloadTokenResponse,
    MedicalRecordSummaryResponse,
    PatientMedicalRecordListResponse,
    PatientMedicalRecordResponse,
)
from app.schemas.user import UserResponseSchema
from app.services.clinical_safety_service import ClinicalSafetyService

# Document configuration
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIMES = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB limit
import logging

logger = logging.getLogger(__name__)

MAGIC_BYTES = {
    "pdf": b"%PDF-",
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
}


def _verify_magic_bytes(prefix: bytes, ext: str) -> bool:
    ext_lower = ext.lower()
    if ext_lower == ".pdf":
        return prefix.startswith(MAGIC_BYTES["pdf"])
    if ext_lower == ".png":
        return prefix.startswith(MAGIC_BYTES["png"])
    if ext_lower in {".jpg", ".jpeg"}:
        return prefix.startswith(MAGIC_BYTES["jpeg"])
    return False


def _get_storage_root() -> Path:
    project_root = Path(__file__).resolve().parent.parent.parent
    storage_dir = project_root / "uploads" / "medical_documents"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


class PatientMedicalRecordService:
    """Core service for managing longitudinal patient medical records and private document storage."""

    # -----------------------------------------------------------------------
    # Document Upload & Private Storage
    # -----------------------------------------------------------------------
    @classmethod
    async def upload_medical_document(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        file: UploadFile,
        title: str,
        record_type: str,
        clinical_date: str,
        description: Optional[str] = None,
        target_patient_id: Optional[str] = None,
    ) -> PatientMedicalRecordResponse:
        """Securely store an uploaded clinical document and create an auditable record."""
        # 0. Validate the request before anything is written (P05-N11: an unknown recordType raised a pydantic
        # ValidationError, a 500, after the file had already been stored, leaving an orphan file).
        allowed_types = {t.value for t in RecordType}
        if record_type not in allowed_types:
            raise HTTPException(status_code=422, detail=f"recordType must be one of: {', '.join(sorted(allowed_types))}.")
        if current_user.role not in (UserRole.PATIENT.value, UserRole.DOCTOR.value):
            raise HTTPException(status_code=403, detail="Only patients and their treating doctors can upload medical documents.")
        # 1. Determine patient identity
        user_id_str = str(current_user.id)
        if current_user.role == UserRole.DOCTOR.value:
            if not target_patient_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Doctor must specify target patient ID for uploaded medical document.",
                )
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, target_patient_id)
            patient_id = target_patient_id
            source_type = SourceType.CLINICIAN_AUTHORED.value
            author_role = "DOCTOR"
        else:
            patient_id = user_id_str
            source_type = SourceType.PATIENT_UPLOADED.value
            author_role = "PATIENT"

        # 2. Validate file attributes
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided.")

        raw_filename = Path(file.filename).name
        extension = Path(raw_filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{extension}'. Allowed formats: PDF, JPG, PNG.",
            )

        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_MIMES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid MIME content type '{content_type}'.",
            )

        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum permissible size of 10 MB (received {len(content) / (1024*1024):.1f} MB).",
            )

        # 3. Magic byte signature check
        if not _verify_magic_bytes(content[:16], extension):
            raise HTTPException(
                status_code=400,
                detail="File header does not match expected format signature.",
            )

        # 4. Integrity hash & randomized secure filename
        file_hash = hashlib.sha256(content).hexdigest()
        random_file_key = f"{uuid.uuid4().hex}{extension}"

        patient_dir = _get_storage_root() / patient_id
        patient_dir.mkdir(parents=True, exist_ok=True)
        dest_path = patient_dir / random_file_key

        relative_file_key = f"{patient_id}/{random_file_key}"
        # Encrypted before the first write (B8). fileHash stays the SHA-256 of the plaintext for integrity checks.
        from app.services.document_crypto import seal_for_storage
        stored_bytes, encryption_meta = seal_for_storage(content, f"medical_documents/{relative_file_key}")
        with open(dest_path, "wb") as f:
            f.write(stored_bytes)

        # 5. Create database record
        record_id = f"MED-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        now = utc_now()

        doc_meta = DocumentMetadata(
            fileKey=relative_file_key,
            fileName=raw_filename,
            fileSize=len(content),
            mimeType=content_type,
            fileHash=file_hash,
            uploadedAt=now,
        )

        record_doc = PatientMedicalRecordDocument(
            recordId=record_id,
            patientUserId=patient_id,
            recordType=record_type,
            sourceType=source_type,
            authorId=user_id_str,
            authorRole=author_role,
            authorName=current_user.fullName,
            title=title.strip(),
            description=description.strip() if description else None,
            clinicalDate=clinical_date,
            clinicalData={"originalFileName": raw_filename},
            documentMetadata=doc_meta,
            status=RecordStatus.ACTIVE.value,
            version=1,
            isAiGenerated=False,
            auditLog=[{"action": "CREATED", "userId": user_id_str, "timestamp": now}],
            createdAt=now,
            updatedAt=now,
        )

        coll = get_patient_medical_record_collection(db)
        inserted = coll.insert_one(record_doc.model_dump(by_alias=True, exclude_none=True))

        return cls._to_response_schema(record_doc, str(inserted.inserted_id))

    # -----------------------------------------------------------------------
    # Create Medical Record (Without File)
    # -----------------------------------------------------------------------
    @classmethod
    def create_medical_record(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        req: CreatePatientMedicalRecordRequest,
    ) -> PatientMedicalRecordResponse:
        """Create a clinical medical record entry (diagnosis, allergy, medical history)."""
        user_id_str = str(current_user.id)
        if current_user.role == UserRole.DOCTOR.value:
            if not req.patientUserId:
                raise HTTPException(status_code=400, detail="Doctor must specify patientUserId.")
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, req.patientUserId)
            patient_id = req.patientUserId
            source_type = SourceType.CLINICIAN_AUTHORED.value
            author_role = "DOCTOR"
        else:
            patient_id = user_id_str
            source_type = SourceType.PATIENT_UPLOADED.value
            author_role = "PATIENT"

        record_id = f"MED-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        now = utc_now()

        record_doc = PatientMedicalRecordDocument(
            recordId=record_id,
            patientUserId=patient_id,
            recordType=req.recordType,
            sourceType=source_type,
            authorId=user_id_str,
            authorRole=author_role,
            authorName=current_user.fullName,
            title=req.title.strip(),
            description=req.description.strip() if req.description else None,
            clinicalDate=req.clinicalDate,
            clinicalData=req.clinicalData,
            status=RecordStatus.ACTIVE.value,
            version=1,
            isAiGenerated=False,
            auditLog=[{"action": "CREATED", "userId": user_id_str, "timestamp": now}],
            createdAt=now,
            updatedAt=now,
        )

        coll = get_patient_medical_record_collection(db)
        inserted = coll.insert_one(record_doc.model_dump(by_alias=True, exclude_none=True))

        return cls._to_response_schema(record_doc, str(inserted.inserted_id))

    # -----------------------------------------------------------------------
    # List & Retrieve Medical Records
    # -----------------------------------------------------------------------
    @classmethod
    def list_medical_records(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        patient_id: Optional[str] = None,
        record_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PatientMedicalRecordListResponse:
        """List patient medical records with access control and pagination."""
        user_id_str = str(current_user.id)
        if current_user.role == UserRole.DOCTOR.value:
            if not patient_id:
                raise HTTPException(status_code=400, detail="Doctor must specify patient_id.")
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, patient_id)
            target_patient = patient_id
        else:
            target_patient = user_id_str

        query: Dict[str, Any] = {"patientUserId": target_patient, "status": {"$ne": "archived"}}
        if record_type:
            query["recordType"] = record_type

        coll = get_patient_medical_record_collection(db)
        total = coll.count_documents(query)
        cursor = (
            coll.find(query)
            .sort([("clinicalDate", -1), ("createdAt", -1)])
            .skip((page - 1) * page_size)
            .limit(page_size)
        )

        records: List[PatientMedicalRecordResponse] = []
        unreadable: List[str] = []
        for doc in cursor:
            # P4-O1 (Phase 05): one malformed historical record used to make the whole list a 500. It is now
            # reported by reference instead, so it is neither hidden nor allowed to block the other records.
            try:
                records.append(cls._to_response_schema(PatientMedicalRecordDocument.model_validate(doc),
                                                       str(doc["_id"])))
            except Exception as exc:
                logger.warning("Medical record %s could not be displayed (%s).", doc.get("_id"), type(exc).__name__)
                unreadable.append(str(doc.get("recordId") or doc.get("_id")))

        return PatientMedicalRecordListResponse(
            records=records,
            unreadableRecords=len(unreadable),
            unreadableRecordRefs=unreadable,
            total=total,
            page=page,
            pageSize=page_size,
        )

    @classmethod
    def get_medical_record(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        record_id: str,
    ) -> PatientMedicalRecordResponse:
        """Fetch a specific medical record with ownership and audit logging."""
        coll = get_patient_medical_record_collection(db)
        query = {"$or": [{"_id": ObjectId(record_id)}, {"recordId": record_id}]} if ObjectId.is_valid(record_id) else {"recordId": record_id}
        doc = coll.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Medical record not found.")

        user_id_str = str(current_user.id)
        # Authorization check
        if current_user.role == UserRole.DOCTOR.value:
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, doc["patientUserId"])
        elif doc["patientUserId"] != user_id_str:
            raise HTTPException(status_code=403, detail="You are not authorized to view this medical record.")

        # Log viewing event
        now = utc_now()
        coll.update_one(
            {"_id": doc["_id"]},
            {"$push": {"auditLog": {"action": "VIEWED", "userId": user_id_str, "timestamp": now}}},
        )

        return cls._to_response_schema(PatientMedicalRecordDocument.model_validate(doc), str(doc["_id"]))

    # -----------------------------------------------------------------------
    # Secure Download Stream
    # -----------------------------------------------------------------------
    @classmethod
    def stream_document_file(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        record_id: str,
    ) -> FileResponse:
        """Stream private document file to authorized user with provenance auditing."""
        coll = get_patient_medical_record_collection(db)
        query = {"$or": [{"_id": ObjectId(record_id)}, {"recordId": record_id}]} if ObjectId.is_valid(record_id) else {"recordId": record_id}
        doc = coll.find_one(query)
        if not doc or not doc.get("documentMetadata"):
            raise HTTPException(status_code=404, detail="Document file not found.")

        user_id_str = str(current_user.id)
        # Authorization check
        if current_user.role == UserRole.DOCTOR.value:
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, doc["patientUserId"])
        elif doc["patientUserId"] != user_id_str:
            raise HTTPException(status_code=403, detail="You are not authorized to download this medical document.")

        meta = doc["documentMetadata"]
        root = _get_storage_root().resolve()
        file_path = (root / meta["fileKey"]).resolve()
        if not str(file_path).startswith(str(root)):
            raise HTTPException(status_code=404, detail="Document file not found.")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Physical document file missing from storage.")
        from app.services.document_crypto import DocumentEncryptionError, open_from_storage
        try:
            content = open_from_storage(file_path.read_bytes(), f"medical_documents/{meta['fileKey']}")
        except DocumentEncryptionError as exc:
            logger.error("Medical document could not be decrypted (%s)", exc)
            raise HTTPException(status_code=500, detail="The document could not be opened (integrity or key check failed).")
        if meta.get("fileHash") and hashlib.sha256(content).hexdigest() != meta["fileHash"]:
            raise HTTPException(status_code=500, detail="The document failed its integrity check.")

        # Log download event
        now = utc_now()
        coll.update_one(
            {"_id": doc["_id"]},
            {"$push": {"auditLog": {"action": "DOWNLOADED", "userId": user_id_str, "timestamp": now}}},
        )

        from urllib.parse import quote
        from fastapi.responses import Response
        return Response(content=content, media_type=meta["mimeType"], headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(meta.get('fileName') or 'document')}",
            "Cache-Control": "no-store",
        })

    # -----------------------------------------------------------------------
    # Source-Grounded Medical Record Summarization
    # -----------------------------------------------------------------------
    @classmethod
    def summarize_patient_history(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        patient_id: Optional[str] = None,
    ) -> MedicalRecordSummaryResponse:
        """Synthesize an authorized, source-grounded longitudinal medical record summary."""
        user_id_str = str(current_user.id)
        if current_user.role == UserRole.DOCTOR.value:
            if not patient_id:
                raise HTTPException(status_code=400, detail="Doctor must specify patient_id.")
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, patient_id)
            target_patient = patient_id
        else:
            target_patient = user_id_str

        # 1. Fetch patient records
        coll = get_patient_medical_record_collection(db)
        records = list(coll.find({"patientUserId": target_patient, "status": "active"}).sort("clinicalDate", 1))

        # 2. Fetch consultation notes
        consultation_notes = list(db["clinical_notes"].find({"patientUserId": target_patient, "status": "signed"}))

        # 3. Fetch active prescriptions
        prescriptions = list(db["prescriptions"].find({"patientUserId": target_patient, "status": {"$in": ["ISSUED", "ACTIVE", "signed"]}}))

        total_records = len(records) + len(consultation_notes) + len(prescriptions)

        diagnoses: List[str] = []
        allergies: List[str] = []
        active_meds: List[str] = []
        findings: List[str] = []
        dates: List[str] = []

        for r in records:
            if r.get("clinicalDate"):
                dates.append(r["clinicalDate"])
            rtype = r.get("recordType")
            if rtype == "diagnosis":
                diagnoses.append(f"{r.get('title')} ({r.get('clinicalDate')})")
            elif rtype == "allergy":
                allergies.append(r.get("title", ""))
            elif rtype in {"laboratory_result", "imaging_report"}:
                findings.append(f"{r.get('title')} on {r.get('clinicalDate')}: {r.get('description', 'Report attached')}")

        for n in consultation_notes:
            content = n.get("content", {})
            created = n.get("createdAt")
            # createdAt is a datetime; slicing it raised TypeError and the summary returned 500 (P03-N14).
            created_text = created.strftime("%Y-%m-%d") if hasattr(created, "strftime") else str(created or "")[:10]
            author = n.get("signedDoctorName") or "the signing clinician"
            findings.append(f"Signed consultation note by {author} ({created_text}): {content.get('assessment', '')}")

        for p in prescriptions:
            for item in p.get("medicationItems", []):
                active_meds.append(f"{item.get('medicationName')} {item.get('strength', '')} ({item.get('frequency', '')})")

        start_date = min(dates) if dates else None
        end_date = max(dates) if dates else None

        # Build grounded summary text
        summary_paragraphs = [
            f"Patient record synthesis based on {total_records} documented healthcare events "
            f"from {start_date or 'N/A'} to {end_date or 'present'}.",
        ]

        if diagnoses:
            summary_paragraphs.append(f"Documented Diagnoses: {', '.join(diagnoses)}.")
        else:
            summary_paragraphs.append("No active clinician-confirmed chronic diagnoses recorded.")

        if allergies:
            summary_paragraphs.append(f"Documented Allergies: {', '.join(allergies)}.")
        else:
            # Absence of a record is not evidence of no allergy (P03-N14).
            summary_paragraphs.append("No allergies are recorded in MediConnect. This does not confirm that the patient "
                                      "has no allergies; ask the patient and check other records.")

        if active_meds:
            summary_paragraphs.append(f"Medicines prescribed on record (confirm current use with the patient): "
                                      f"{', '.join(active_meds)}.")

        summary_text = "\n\n".join(summary_paragraphs)

        missing_notice = None
        if total_records < 3:
            missing_notice = (
                "Notice: Patient record set is limited. Information shown reflects only currently available "
                "institutional documentation and uploaded patient files."
            )

        return MedicalRecordSummaryResponse(
            patientUserId=target_patient,
            recordsAnalyzed=total_records,
            dateRange={"startDate": start_date, "endDate": end_date},
            summary=summary_text,
            diagnoses=diagnoses,
            activeMedications=active_meds,
            documentedAllergies=allergies,
            keyClinicalFindings=findings[:5],
            missingInformationNotice=missing_notice,
            aiDisclaimer=(
                "ASSISTIVE MEDICAL SUMMARY NOTICE: This clinical synthesis is generated for reference only. "
                "It does not replace clinical judgment or official laboratory/imaging reports. "
                "Healthcare professionals must verify raw clinical documentation."
            ),
        )

    @classmethod
    def _to_response_schema(cls, doc: PatientMedicalRecordDocument, obj_id: str) -> PatientMedicalRecordResponse:
        has_file = doc.documentMetadata is not None
        return PatientMedicalRecordResponse(
            id=obj_id,
            recordId=doc.recordId,
            patientUserId=doc.patientUserId,
            recordType=doc.recordType,
            sourceType=doc.sourceType,
            authorId=doc.authorId,
            authorRole=doc.authorRole,
            authorName=doc.authorName,
            title=doc.title,
            description=doc.description,
            clinicalDate=doc.clinicalDate,
            clinicalData=doc.clinicalData,
            hasAttachment=has_file,
            attachmentName=doc.documentMetadata.fileName if has_file else None,
            attachmentSize=doc.documentMetadata.fileSize if has_file else None,
            attachmentMimeType=doc.documentMetadata.mimeType if has_file else None,
            status=doc.status,
            version=doc.version,
            isAiGenerated=doc.isAiGenerated,
            createdAt=doc.createdAt,
            updatedAt=doc.updatedAt,
        )
