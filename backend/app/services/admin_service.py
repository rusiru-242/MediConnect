"""Admin service for managing doctor applications, verification, and documents."""

import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.doctor_profile import DoctorVerificationStatus, utc_now
from app.models.user import AccountStatus, UserRole
from app.schemas.admin import (
    AdminActionResponse,
    AdminAppointmentItem,
    AdminAppointmentListResponse,
    AdminDoctorApplicationDetail,
    AdminDoctorApplicationSummary,
    AdminDoctorDocumentMetadata,
    AdminDoctorListItem,
    AdminDoctorListResponse,
    AdminPaymentItem,
    AdminPaymentListResponse,
    AdminReviewItem,
    AdminReviewListResponse,
    AdminUserItem,
    AdminUserListResponse,
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

    # -------------------------------------------------------------------------
    # User Administration
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_users(
        db: Database,
        role: Optional[str] = None,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminUserListResponse:
        """Paginated list of users with privacy-conscious least-privilege projection."""
        query: Dict[str, Any] = {}

        if role and role.strip().upper() != "ALL":
            query["role"] = role.strip().upper()

        if status_filter and status_filter.strip().upper() != "ALL":
            query["accountStatus"] = status_filter.strip().upper()

        if search and search.strip():
            esc = re.escape(search.strip())
            query["$or"] = [
                {"fullName": {"$regex": esc, "$options": "i"}},
                {"email": {"$regex": esc, "$options": "i"}},
            ]

        total = db["users"].count_documents(query)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        skip = (page - 1) * page_size

        # Least-privilege projection: Never include password hashes, tokens, or private medical data
        projection = {
            "_id": 1,
            "email": 1,
            "fullName": 1,
            "phone": 1,
            "role": 1,
            "accountStatus": 1,
            "emailVerified": 1,
            "createdAt": 1,
            "updatedAt": 1,
            "lastLoginAt": 1,
        }

        cursor = db["users"].find(query, projection).sort("createdAt", -1).skip(skip).limit(page_size)

        items: List[AdminUserItem] = []
        for u in cursor:
            c_at = u.get("createdAt")
            if isinstance(c_at, datetime) and c_at.tzinfo is None:
                c_at = c_at.replace(tzinfo=timezone.utc)
            elif not isinstance(c_at, datetime):
                c_at = utc_now()

            u_at = u.get("updatedAt")
            if isinstance(u_at, datetime) and u_at.tzinfo is None:
                u_at = u_at.replace(tzinfo=timezone.utc)

            ll_at = u.get("lastLoginAt")
            if isinstance(ll_at, datetime) and ll_at.tzinfo is None:
                ll_at = ll_at.replace(tzinfo=timezone.utc)

            items.append(
                AdminUserItem(
                    id=str(u["_id"]),
                    email=u.get("email", ""),
                    fullName=u.get("fullName", "User"),
                    phone=u.get("phone"),
                    role=u.get("role", UserRole.PATIENT.value),
                    accountStatus=u.get("accountStatus", AccountStatus.ACTIVE.value),
                    emailVerified=bool(u.get("emailVerified", False)),
                    createdAt=c_at,
                    updatedAt=u_at,
                    lastLoginAt=ll_at,
                )
            )

        return AdminUserListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
        )

    @staticmethod
    async def update_user_status(
        db: Database,
        user_id: str,
        new_status: str,
        admin_user_id: str,
    ) -> AdminActionResponse:
        """Modify user account status (ACTIVE, SUSPENDED, DEACTIVATED). Prevents self-modification."""
        if str(user_id) == str(admin_user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators cannot modify their own account status.",
            )

        clean_status = (new_status or "").strip().upper()
        valid_statuses = {s.value for s in AccountStatus}
        if clean_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid account status '{new_status}'. Allowed: {', '.join(sorted(valid_statuses))}",
            )

        u_oid = AdminService._parse_object_id(user_id, "User")
        user = db["users"].find_one({"_id": u_oid})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found.",
            )

        now = utc_now()
        db["users"].update_one(
            {"_id": u_oid},
            {"$set": {"accountStatus": clean_status, "updatedAt": now}},
        )

        return AdminActionResponse(message=f"User account status updated to {clean_status}.")

    # -------------------------------------------------------------------------
    # Doctor Directory Administration
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_doctors(
        db: Database,
        specialty: Optional[str] = None,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminDoctorListResponse:
        """Paginated directory of doctors with account and verification status."""
        query: Dict[str, Any] = {}

        if specialty and specialty.strip().upper() != "ALL":
            query["specialty"] = {"$regex": re.escape(specialty.strip()), "$options": "i"}

        if status_filter and status_filter.strip().upper() != "ALL":
            query["verificationStatus"] = status_filter.strip().upper()

        profiles = list(db["doctor_profiles"].find(query).sort("submittedAt", -1))
        if not profiles:
            return AdminDoctorListResponse(items=[], total=0, page=page, pageSize=page_size, totalPages=1)

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

        # Average rating lookup by doctor userId
        rating_pipeline = [
            {"$match": {"status": "PUBLISHED"}},
            {
                "$group": {
                    "_id": "$doctorId",
                    "avgRating": {"$avg": "$rating"},
                    "count": {"$sum": 1},
                }
            },
        ]
        review_aggregates = {
            str(r["_id"]): r for r in db["reviews"].aggregate(rating_pipeline)
        }

        all_items: List[AdminDoctorListItem] = []
        for p in profiles:
            uid_str = str(p.get("userId", ""))
            user = users_by_id.get(uid_str, {})
            name = user.get("fullName", "Unknown Doctor")
            email = user.get("email", "")

            # Apply search filter across name, email, specialty, hospital
            if search and search.strip():
                term = search.strip().lower()
                combined = f"{name} {email} {p.get('specialty', '')} {p.get('hospitalOrClinic', '')}".lower()
                if term not in combined:
                    continue

            sub_at = p.get("submittedAt")
            if isinstance(sub_at, datetime) and sub_at.tzinfo is None:
                sub_at = sub_at.replace(tzinfo=timezone.utc)
            elif not isinstance(sub_at, datetime):
                sub_at = utc_now()

            ver_at = p.get("verifiedAt")
            if isinstance(ver_at, datetime) and ver_at.tzinfo is None:
                ver_at = ver_at.replace(tzinfo=timezone.utc)

            review_info = review_aggregates.get(uid_str, {})
            avg_r = round(review_info["avgRating"], 1) if "avgRating" in review_info else None
            cnt_r = review_info.get("count", 0)

            all_items.append(
                AdminDoctorListItem(
                    doctorProfileId=str(p["_id"]),
                    userId=uid_str,
                    fullName=name,
                    email=email,
                    phone=user.get("phone"),
                    specialty=p.get("specialty", ""),
                    medicalRegistrationNumber=p.get("medicalRegistrationNumber", ""),
                    hospitalOrClinic=p.get("hospitalOrClinic", ""),
                    experienceYears=int(p.get("experienceYears", 0)),
                    verificationStatus=p.get("verificationStatus", DoctorVerificationStatus.PENDING.value),
                    accountStatus=user.get("accountStatus", AccountStatus.ACTIVE.value),
                    submittedAt=sub_at,
                    verifiedAt=ver_at,
                    averageRating=avg_r,
                    totalReviews=cnt_r,
                )
            )

        total = len(all_items)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        skip = (page - 1) * page_size
        paginated_items = all_items[skip : skip + page_size]

        return AdminDoctorListResponse(
            items=paginated_items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
        )

    # -------------------------------------------------------------------------
    # Appointment Management
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_appointments(
        db: Database,
        status_filter: Optional[str] = None,
        payment_status: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminAppointmentListResponse:
        """Paginated list of patient appointments with doctor and patient details."""
        query: Dict[str, Any] = {}

        if status_filter and status_filter.strip().upper() != "ALL":
            query["status"] = status_filter.strip().upper()

        if payment_status and payment_status.strip().upper() != "ALL":
            query["paymentStatus"] = payment_status.strip().upper()

        if start_date and end_date:
            query["appointmentDate"] = {"$gte": start_date, "$lte": end_date}
        elif start_date:
            query["appointmentDate"] = {"$gte": start_date}
        elif end_date:
            query["appointmentDate"] = {"$lte": end_date}

        cursor = db["appointments"].find(query).sort("createdAt", -1)
        raw_appointments = list(cursor)

        if not raw_appointments:
            return AdminAppointmentListResponse(items=[], total=0, page=page, pageSize=page_size, totalPages=1)

        # Bulk user lookup
        user_ids_set = set()
        for a in raw_appointments:
            pid = a.get("patientUserId")
            did = a.get("doctorUserId")
            if pid:
                user_ids_set.add(ObjectId(pid) if ObjectId.is_valid(pid) else pid)
            if did:
                user_ids_set.add(ObjectId(did) if ObjectId.is_valid(did) else did)

        users_cursor = db["users"].find({"_id": {"$in": list(user_ids_set)}})
        users_by_id = {str(u["_id"]): u for u in users_cursor}

        # Bulk doctor profile lookup for specialty
        doc_prof_ids = [
            ObjectId(a["doctorProfileId"])
            for a in raw_appointments
            if a.get("doctorProfileId") and ObjectId.is_valid(a.get("doctorProfileId"))
        ]
        profs_cursor = db["doctor_profiles"].find({"_id": {"$in": doc_prof_ids}})
        profs_by_id = {str(p["_id"]): p for p in profs_cursor}

        items: List[AdminAppointmentItem] = []
        for a in raw_appointments:
            pid_str = str(a.get("patientUserId", ""))
            did_str = str(a.get("doctorUserId", ""))
            dprof_id_str = str(a.get("doctorProfileId", ""))

            patient = users_by_id.get(pid_str, {})
            doctor = users_by_id.get(did_str, {})
            profile = profs_by_id.get(dprof_id_str, {})

            p_name = patient.get("fullName", "Patient")
            p_email = patient.get("email", "")
            d_name = doctor.get("fullName", "Doctor")
            d_spec = profile.get("specialty", "General Medicine")

            if search and search.strip():
                term = search.strip().lower()
                combined = f"{p_name} {p_email} {d_name} {d_spec} {a.get('appointmentDate', '')}".lower()
                if term not in combined:
                    continue

            c_at = a.get("createdAt")
            if isinstance(c_at, datetime) and c_at.tzinfo is None:
                c_at = c_at.replace(tzinfo=timezone.utc)
            elif not isinstance(c_at, datetime):
                c_at = utc_now()

            items.append(
                AdminAppointmentItem(
                    id=str(a["_id"]),
                    patientUserId=pid_str,
                    patientName=p_name,
                    patientEmail=p_email,
                    doctorUserId=did_str,
                    doctorName=d_name,
                    doctorSpecialty=d_spec,
                    appointmentDate=a.get("appointmentDate", ""),
                    startTime=a.get("startTime", ""),
                    endTime=a.get("endTime", ""),
                    status=a.get("status", "PENDING"),
                    paymentStatus=a.get("paymentStatus", "UNPAID"),
                    consultationFee=float(a.get("consultationFee") or 0.0),
                    patientNote=a.get("patientNote"),
                    cancellationReason=a.get("cancellationReason"),
                    cancelledBy=a.get("cancelledBy"),
                    createdAt=c_at,
                )
            )

        total = len(items)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        skip = (page - 1) * page_size
        paginated_items = items[skip : skip + page_size]

        return AdminAppointmentListResponse(
            items=paginated_items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
        )

    # -------------------------------------------------------------------------
    # Payment Oversight
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_payments(
        db: Database,
        status_filter: Optional[str] = None,
        currency: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminPaymentListResponse:
        """Paginated list of payments with patient and doctor details."""
        query: Dict[str, Any] = {}

        if status_filter and status_filter.strip().upper() != "ALL":
            query["status"] = status_filter.strip().upper()

        if currency and currency.strip().upper() != "ALL":
            query["currency"] = currency.strip().lower()

        raw_payments = list(db["payments"].find(query).sort("createdAt", -1))
        if not raw_payments:
            return AdminPaymentListResponse(items=[], total=0, page=page, pageSize=page_size, totalPages=1)

        user_ids_set = set()
        for p in raw_payments:
            pid = p.get("patientUserId")
            did = p.get("doctorUserId")
            if pid:
                user_ids_set.add(ObjectId(pid) if ObjectId.is_valid(pid) else pid)
            if did:
                user_ids_set.add(ObjectId(did) if ObjectId.is_valid(did) else did)

        users_cursor = db["users"].find({"_id": {"$in": list(user_ids_set)}})
        users_by_id = {str(u["_id"]): u for u in users_cursor}

        items: List[AdminPaymentItem] = []
        for p in raw_payments:
            pid_str = str(p.get("patientUserId", ""))
            did_str = str(p.get("doctorUserId", ""))

            patient = users_by_id.get(pid_str, {})
            doctor = users_by_id.get(did_str, {})

            c_at = p.get("createdAt")
            if isinstance(c_at, datetime) and c_at.tzinfo is None:
                c_at = c_at.replace(tzinfo=timezone.utc)
            elif not isinstance(c_at, datetime):
                c_at = utc_now()

            p_at = p.get("paidAt")
            if isinstance(p_at, datetime) and p_at.tzinfo is None:
                p_at = p_at.replace(tzinfo=timezone.utc)

            intent_id = p.get("stripePaymentIntentId", "")
            is_test = "test" in intent_id.lower() or intent_id.startswith("mock_") or True

            items.append(
                AdminPaymentItem(
                    id=str(p["_id"]),
                    appointmentId=str(p.get("appointmentId", "")),
                    patientUserId=pid_str,
                    patientName=patient.get("fullName", "Patient"),
                    doctorUserId=did_str,
                    doctorName=doctor.get("fullName", "Doctor"),
                    stripePaymentIntentId=intent_id,
                    amount=float(p.get("amount") or 0.0),
                    currency=(p.get("currency") or "lkr").upper(),
                    status=p.get("status", "PENDING"),
                    isTestMode=is_test,
                    failureReason=p.get("failureReason"),
                    paidAt=p_at,
                    createdAt=c_at,
                )
            )

        total = len(items)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        skip = (page - 1) * page_size
        paginated_items = items[skip : skip + page_size]

        return AdminPaymentListResponse(
            items=paginated_items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
        )

    # -------------------------------------------------------------------------
    # Review Management
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_reviews(
        db: Database,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminReviewListResponse:
        """Paginated list of doctor reviews with moderation flags."""
        query: Dict[str, Any] = {}

        if status_filter:
            clean = status_filter.strip().upper()
            if clean == "REPORTED":
                query["$or"] = [{"isReported": True}, {"status": "REPORTED"}]
            elif clean in ("PUBLISHED", "HIDDEN"):
                query["status"] = clean

        raw_reviews = list(db["reviews"].find(query).sort("createdAt", -1))
        if not raw_reviews:
            return AdminReviewListResponse(items=[], total=0, page=page, pageSize=page_size, totalPages=1)

        user_ids_set = set()
        for r in raw_reviews:
            pid = r.get("patientId")
            did = r.get("doctorId")
            if pid:
                user_ids_set.add(ObjectId(pid) if ObjectId.is_valid(pid) else pid)
            if did:
                user_ids_set.add(ObjectId(did) if ObjectId.is_valid(did) else did)

        users_cursor = db["users"].find({"_id": {"$in": list(user_ids_set)}})
        users_by_id = {str(u["_id"]): u for u in users_cursor}

        items: List[AdminReviewItem] = []
        for r in raw_reviews:
            pid_str = str(r.get("patientId", ""))
            did_str = str(r.get("doctorId", ""))

            patient = users_by_id.get(pid_str, {})
            doctor = users_by_id.get(did_str, {})

            c_at = r.get("createdAt")
            if isinstance(c_at, datetime) and c_at.tzinfo is None:
                c_at = c_at.replace(tzinfo=timezone.utc)
            elif not isinstance(c_at, datetime):
                c_at = utc_now()

            items.append(
                AdminReviewItem(
                    id=str(r["_id"]),
                    appointmentId=str(r.get("appointmentId", "")),
                    doctorId=did_str,
                    doctorName=doctor.get("fullName", "Doctor"),
                    patientId=pid_str,
                    patientName=patient.get("fullName", "Patient"),
                    rating=int(r.get("rating", 5)),
                    reviewText=r.get("reviewText"),
                    status=r.get("status", "PUBLISHED"),
                    isReported=bool(r.get("isReported", False)),
                    reportReason=r.get("reportReason"),
                    moderationNotes=r.get("moderationNotes"),
                    createdAt=c_at,
                )
            )

        total = len(items)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        skip = (page - 1) * page_size
        paginated_items = items[skip : skip + page_size]

        return AdminReviewListResponse(
            items=paginated_items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
        )
