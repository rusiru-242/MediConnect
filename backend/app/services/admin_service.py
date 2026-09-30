"""Admin service for managing doctor applications, verification, and documents."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.doctor_profile import DoctorVerificationStatus, utc_now
from app.models.user import AccountStatus, UserRole
from app.schemas.admin import (
    AdminActionResponse,
    AdminDoctorApplicationDetail,
    AdminDoctorApplicationSummary,
    AdminDoctorDocumentMetadata,
)
from app.services.document_storage_service import document_storage


DOCUMENT_TITLES = {
    "identityDocument": "Identity Document",
    "medicalRegistrationDocument": "Medical Registration Document",
    "qualificationDocument": "Qualification Document",
}


class AdminService:
    """Service encapsulating administrator operations for doctor verification."""

    @staticmethod
    def _parse_object_id(id_str: str, entity_name: str = "Record") -> ObjectId:
        """Safely parse ObjectId or raise 400 Bad Request."""
        if not ObjectId.is_valid(id_str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {entity_name} ID format.",
            )
        return ObjectId(id_str)

    @staticmethod
    async def list_doctor_applications(
        db: Database,
        status_filter: Optional[str] = "PENDING",
    ) -> List[AdminDoctorApplicationSummary]:
        """List doctor applications with optional status filtering (default: PENDING)."""
        query = {}
        if status_filter and status_filter.upper() != "ALL":
            clean_status = status_filter.strip().upper()
            if clean_status in {s.value for s in DoctorVerificationStatus}:
                query["verificationStatus"] = clean_status
            else:
                query["verificationStatus"] = DoctorVerificationStatus.PENDING.value
        elif not status_filter:
            query["verificationStatus"] = DoctorVerificationStatus.PENDING.value

        profiles = list(db["doctor_profiles"].find(query).sort("submittedAt", -1))
        if not profiles:
            return []

        # Collect userIds for efficient bulk lookup
        user_ids = []
        for p in profiles:
            uid = p.get("userId")
            if uid:
                if ObjectId.is_valid(uid):
                    user_ids.append(ObjectId(uid))
                else:
                    user_ids.append(uid)

        users_cursor = db["users"].find({"_id": {"$in": user_ids}})
        users_by_id = {str(u["_id"]): u for u in users_cursor}

        results: List[AdminDoctorApplicationSummary] = []
        for p in profiles:
            uid_str = str(p.get("userId", ""))
            user = users_by_id.get(uid_str, {})

            # Ensure UTC submittedAt
            sub_at = p.get("submittedAt")
            if isinstance(sub_at, datetime) and sub_at.tzinfo is None:
                sub_at = sub_at.replace(tzinfo=timezone.utc)
            elif not isinstance(sub_at, datetime):
                sub_at = utc_now()

            results.append(
                AdminDoctorApplicationSummary(
                    doctorProfileId=str(p["_id"]),
                    userId=uid_str,
                    fullName=user.get("fullName", "Unknown Doctor"),
                    email=user.get("email", ""),
                    phone=user.get("phone"),
                    specialty=p.get("specialty", ""),
                    medicalRegistrationNumber=p.get("medicalRegistrationNumber", ""),
                    hospitalOrClinic=p.get("hospitalOrClinic", ""),
                    experienceYears=int(p.get("experienceYears", 0)),
                    verificationStatus=p.get("verificationStatus", DoctorVerificationStatus.PENDING.value),
                    submittedAt=sub_at,
                )
            )

        return results

    @staticmethod
    async def get_doctor_application_detail(
        db: Database,
        doctor_profile_id: str,
    ) -> AdminDoctorApplicationDetail:
        """Fetch complete doctor application detail with safe document metadata."""
        prof_oid = AdminService._parse_object_id(doctor_profile_id, "Doctor Profile")
        profile = db["doctor_profiles"].find_one({"_id": prof_oid})
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor application not found.",
            )

        user_id_val = profile.get("userId")
        user_query = {}
        if ObjectId.is_valid(user_id_val):
            user_query = {"$or": [{"_id": ObjectId(user_id_val)}, {"_id": user_id_val}]}
        else:
            user_query = {"_id": user_id_val}

        user = db["users"].find_one(user_query)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated user account not found.",
            )

        # Prepare safe document metadata
        raw_docs = profile.get("verificationDocuments", {})
        documents_meta: List[AdminDoctorDocumentMetadata] = []

        for key, doc in raw_docs.items():
            if isinstance(doc, dict):
                title = DOCUMENT_TITLES.get(key, key.replace("Document", " Document").title())
                filename = doc.get("originalFilename") or doc.get("filename") or f"{key}.pdf"
                mime_type = doc.get("contentType") or "application/octet-stream"
                size_bytes = int(doc.get("fileSize") or 0)

                up_at = profile.get("submittedAt")
                if isinstance(up_at, datetime) and up_at.tzinfo is None:
                    up_at = up_at.replace(tzinfo=timezone.utc)

                documents_meta.append(
                    AdminDoctorDocumentMetadata(
                        documentKey=key,
                        title=title,
                        filename=filename,
                        mimeType=mime_type,
                        sizeBytes=size_bytes,
                        uploadedAt=up_at,
                    )
                )

        sub_at = profile.get("submittedAt")
        if isinstance(sub_at, datetime) and sub_at.tzinfo is None:
            sub_at = sub_at.replace(tzinfo=timezone.utc)
        elif not isinstance(sub_at, datetime):
            sub_at = utc_now()

        ver_at = profile.get("verifiedAt")
        if isinstance(ver_at, datetime) and ver_at.tzinfo is None:
            ver_at = ver_at.replace(tzinfo=timezone.utc)

        return AdminDoctorApplicationDetail(
            doctorProfileId=str(profile["_id"]),
            userId=str(user["_id"]),
            fullName=user.get("fullName", ""),
            email=user.get("email", ""),
            phone=user.get("phone"),
            specialty=profile.get("specialty", ""),
            medicalRegistrationNumber=profile.get("medicalRegistrationNumber", ""),
            qualifications=profile.get("qualifications", ""),
            hospitalOrClinic=profile.get("hospitalOrClinic", ""),
            experienceYears=int(profile.get("experienceYears", 0)),
            bio=profile.get("bio"),
            verificationStatus=profile.get("verificationStatus", DoctorVerificationStatus.PENDING.value),
            rejectionReason=profile.get("rejectionReason"),
            submittedAt=sub_at,
            verifiedAt=ver_at,
            verifiedBy=profile.get("verifiedBy"),
            documents=documents_meta,
        )

    @staticmethod
    async def get_doctor_verification_document(
        db: Database,
        doctor_profile_id: str,
        document_id: str,
    ) -> Tuple[Path, str, str]:
        """Locate and validate a doctor's verification document, returning (Path, filename, mime_type).

        Validates against path traversal and does not expose internal filesystem paths.
        """
        prof_oid = AdminService._parse_object_id(doctor_profile_id, "Doctor Profile")
        profile = db["doctor_profiles"].find_one({"_id": prof_oid})
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor application not found.",
            )

        raw_docs = profile.get("verificationDocuments", {})

        # Support document_id as direct key (e.g. 'identityDocument') or matching documentType
        doc_entry = raw_docs.get(document_id)
        if not doc_entry:
            for k, v in raw_docs.items():
                if k.lower() == document_id.lower() or v.get("documentType", "").lower() == document_id.lower():
                    doc_entry = v
                    break

        if not doc_entry or not isinstance(doc_entry, dict) or not doc_entry.get("storagePath"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requested verification document not found.",
            )

        relative_path = doc_entry["storagePath"]

        try:
            resolved_path = document_storage.get_document_path(relative_path)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid document path format.",
            )

        if not resolved_path.exists() or not resolved_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification document file is missing from storage.",
            )

        filename = doc_entry.get("originalFilename") or resolved_path.name
        mime_type = doc_entry.get("contentType") or "application/octet-stream"

        return resolved_path, filename, mime_type

    @staticmethod
    async def approve_doctor_application(
        db: Database,
        doctor_profile_id: str,
        admin_user_id: str,
    ) -> AdminActionResponse:
        """Approve a PENDING doctor application, activating their account and updating audit fields."""
        prof_oid = AdminService._parse_object_id(doctor_profile_id, "Doctor Profile")
        profile = db["doctor_profiles"].find_one({"_id": prof_oid})
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor application not found.",
            )

        current_status = profile.get("verificationStatus")

        # Concurrency / Double Action Protection: Only PENDING applications can be approved
        if current_status != DoctorVerificationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve application with status '{current_status}'. Only PENDING applications can be approved.",
            )

        user_id_val = profile.get("userId")
        user_query = {}
        if ObjectId.is_valid(user_id_val):
            user_query = {"$or": [{"_id": ObjectId(user_id_val)}, {"_id": user_id_val}]}
        else:
            user_query = {"_id": user_id_val}

        user = db["users"].find_one(user_query)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated doctor user not found.",
            )

        if user.get("role") != UserRole.DOCTOR.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account does not have DOCTOR role.",
            )

        if not user.get("emailVerified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve doctor whose email is not verified.",
            )

        # Validate professional documents exist
        docs = profile.get("verificationDocuments", {})
        required_keys = {"identityDocument", "medicalRegistrationDocument", "qualificationDocument"}
        if not required_keys.issubset(docs.keys()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve application missing required verification documents.",
            )

        now = utc_now()

        # Atomic status update with status condition for concurrency protection
        update_result = db["doctor_profiles"].update_one(
            {
                "_id": prof_oid,
                "verificationStatus": DoctorVerificationStatus.PENDING.value,
            },
            {
                "$set": {
                    "verificationStatus": DoctorVerificationStatus.APPROVED.value,
                    "verifiedAt": now,
                    "verifiedBy": str(admin_user_id),
                    "rejectionReason": None,
                    "previousStatus": DoctorVerificationStatus.PENDING.value,
                    "updatedAt": now,
                }
            },
        )

        if update_result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application status was modified by another administrator.",
            )

        # Update User account status to ACTIVE
        db["users"].update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "accountStatus": AccountStatus.ACTIVE.value,
                    "updatedAt": now,
                }
            },
        )

        return AdminActionResponse(message="Doctor application approved successfully.")

    @staticmethod
    async def reject_doctor_application(
        db: Database,
        doctor_profile_id: str,
        admin_user_id: str,
        reason: str,
    ) -> AdminActionResponse:
        """Reject a PENDING doctor application with a required reason, keeping doctor restricted."""
        clean_reason = (reason or "").strip()
        if not clean_reason or len(clean_reason) < 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A valid reason for rejection is required (minimum 3 characters).",
            )

        prof_oid = AdminService._parse_object_id(doctor_profile_id, "Doctor Profile")
        profile = db["doctor_profiles"].find_one({"_id": prof_oid})
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor application not found.",
            )

        current_status = profile.get("verificationStatus")

        # Concurrency / Double Action Protection: Only PENDING applications can be rejected
        if current_status != DoctorVerificationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject application with status '{current_status}'. Only PENDING applications can be rejected.",
            )

        now = utc_now()

        update_result = db["doctor_profiles"].update_one(
            {
                "_id": prof_oid,
                "verificationStatus": DoctorVerificationStatus.PENDING.value,
            },
            {
                "$set": {
                    "verificationStatus": DoctorVerificationStatus.REJECTED.value,
                    "rejectionReason": clean_reason,
                    "verifiedAt": now,
                    "verifiedBy": str(admin_user_id),
                    "previousStatus": DoctorVerificationStatus.PENDING.value,
                    "updatedAt": now,
                }
            },
        )

        if update_result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application status was modified by another administrator.",
            )

        # Doctor user account remains PENDING (restricted, not active)

        return AdminActionResponse(message="Doctor application rejected.")
