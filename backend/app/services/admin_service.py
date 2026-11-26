"""Admin service for managing doctor applications, verification, and documents."""

import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.admin_audit import AdminAuditAction
from app.services.admin_audit_service import AdminAuditService
from app.config.settings import settings
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
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType

logger = logging.getLogger(__name__)


DOCUMENT_TITLES = {
    "identityDocument": "Identity Document",
    "medicalRegistrationDocument": "Medical Registration Document",
    "qualificationDocument": "Qualification Document",
}


def _locked_fee(appt: Dict[str, Any]) -> Optional[float]:
    """The fee locked at booking, or None when unknown. Never an invented 0.00 (P04-N03 / P3-B2)."""
    if isinstance(appt.get("acceptedAmountMinor"), int):
        return appt["acceptedAmountMinor"] / 100
    from app.agents.doctor_ranking import coerce_fee
    return coerce_fee(appt.get("consultationFee"))


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
        clean_status = (status_filter or "PENDING").strip().upper()
        query: Dict[str, Any] = {}
        filter_verified_only = False

        if clean_status in ("PENDING", "PENDING_ADMIN_APPROVAL"):
            query["verificationStatus"] = {
                "$in": [
                    DoctorVerificationStatus.PENDING.value,
                    DoctorVerificationStatus.PENDING_ADMIN_APPROVAL.value,
                ]
            }
            filter_verified_only = True
        elif clean_status == "PENDING_EMAIL_VERIFICATION":
            query["verificationStatus"] = DoctorVerificationStatus.PENDING_EMAIL_VERIFICATION.value
        elif clean_status != "ALL":
            if clean_status in {s.value for s in DoctorVerificationStatus}:
                query["verificationStatus"] = clean_status
            else:
                query["verificationStatus"] = DoctorVerificationStatus.PENDING.value
                filter_verified_only = True

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

            email_verified = bool(user.get("emailVerified", False))
            # Pending approvals section only lists email-verified applications
            if filter_verified_only and not email_verified:
                continue

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
                    qualifications=p.get("qualifications", ""),
                    hospitalOrClinic=p.get("hospitalOrClinic", ""),
                    experienceYears=int(p.get("experienceYears", 0)),
                    verificationStatus=p.get("verificationStatus", DoctorVerificationStatus.PENDING.value),
                    emailVerified=email_verified,
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
            emailVerified=bool(user.get("emailVerified", False)),
            emailVerifiedAt=profile.get("emailVerifiedAt"),
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
        if current_status == DoctorVerificationStatus.PENDING_EMAIL_VERIFICATION.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor's email must be verified before the application can be approved.",
            )

        pending_statuses = [
            DoctorVerificationStatus.PENDING.value,
            DoctorVerificationStatus.PENDING_ADMIN_APPROVAL.value,
        ]

        # Concurrency / Double Action Protection: Only pending applications can be approved
        if current_status not in pending_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve application with status '{current_status}'. Only pending applications can be approved.",
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
                detail="Doctor's email must be verified before the application can be approved.",
            )

        # Clinical workflows (note signing, prescriptions) need the doctor's real registration number, so an
        # application without one cannot be approved (P04-N08). It is never generated.
        if not str(profile.get("medicalRegistrationNumber") or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve an application without a medical registration number.",
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
                "verificationStatus": {"$in": pending_statuses},
            },
            {
                "$set": {
                    "verificationStatus": DoctorVerificationStatus.APPROVED.value,
                    "verifiedAt": now,
                    "verifiedBy": str(admin_user_id),
                    "rejectionReason": None,
                    "previousStatus": current_status,
                    "updatedAt": now,
                }
            },
        )

        if update_result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application status was modified by another administrator.",
            )

        # Update User account status to ACTIVE and emailVerified to True
        db["users"].update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "accountStatus": AccountStatus.ACTIVE.value,
                    "emailVerified": True,
                    "updatedAt": now,
                }
            },
        )

        AdminAuditService.log_action(
            db=db, actor_id=str(admin_user_id), actor_role="ADMIN",
            action_type=AdminAuditAction.DOCTOR_VERIFICATION_DECISION, target_id=str(prof_oid),
            target_type="doctor_profile", previous_state=current_status,
            new_state=DoctorVerificationStatus.APPROVED.value, reason="Approved by administrator",
            metadata={"doctorUserId": str(user["_id"]), "decision": "approve",
                      "registrationNumberOfficiallyVerified": False},
        )

        # Dispatch approval email with doctor's personal details and login portal link
        login_url = settings.DOCTOR_PORTAL_URL or "https://mediconnect-admin-staging.vercel.app/login"
        try:
            EmailService.send_doctor_approval_email(
                to_email=user.get("email", ""),
                doctor_name=user.get("fullName", "Doctor"),
                specialty=profile.get("specialty", ""),
                medical_registration_number=profile.get("medicalRegistrationNumber", ""),
                hospital_or_clinic=profile.get("hospitalOrClinic", ""),
                phone=user.get("phone"),
                qualifications=profile.get("qualifications"),
                login_url=login_url,
            )
        except Exception as exc:
            logger.error("Failed to send doctor approval email to %s: %s", user.get("email"), exc)

        # Create in-app approval notification for the doctor
        try:
            NotificationService.create_notification(
                db=db,
                recipient_user_id=str(user["_id"]),
                type=NotificationType.SYSTEM,
                title="Doctor Application Approved",
                body="Your MediConnect doctor application has been approved by an administrator. You can now sign in "
                     "and manage your schedule and appointments.",
            )
        except Exception as exc:
            logger.warning("Failed to create in-app notification for approved doctor: %s", exc)

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
        pending_statuses = [
            DoctorVerificationStatus.PENDING.value,
            DoctorVerificationStatus.PENDING_EMAIL_VERIFICATION.value,
            DoctorVerificationStatus.PENDING_ADMIN_APPROVAL.value,
        ]

        # Concurrency / Double Action Protection: Only pending applications can be rejected
        if current_status not in pending_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject application with status '{current_status}'. Only pending applications can be rejected.",
            )

        now = utc_now()

        update_result = db["doctor_profiles"].update_one(
            {
                "_id": prof_oid,
                "verificationStatus": {"$in": pending_statuses},
            },
            {
                "$set": {
                    "verificationStatus": DoctorVerificationStatus.REJECTED.value,
                    "rejectionReason": clean_reason,
                    "verifiedAt": now,
                    "verifiedBy": str(admin_user_id),
                    "previousStatus": current_status,
                    "updatedAt": now,
                }
            },
        )

        if update_result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application status was modified by another administrator.",
            )

        AdminAuditService.log_action(
            db=db, actor_id=str(admin_user_id), actor_role="ADMIN",
            action_type=AdminAuditAction.DOCTOR_VERIFICATION_DECISION, target_id=str(prof_oid),
            target_type="doctor_profile", previous_state=current_status,
            new_state=DoctorVerificationStatus.REJECTED.value, reason=clean_reason,
            metadata={"doctorUserId": str(profile.get("userId")), "decision": "reject"},
        )

        # Notify doctor via email and in-app notification
        user_id_val = profile.get("userId")
        user_query = {}
        if ObjectId.is_valid(user_id_val):
            user_query = {"$or": [{"_id": ObjectId(user_id_val)}, {"_id": user_id_val}]}
        else:
            user_query = {"_id": user_id_val}

        user = db["users"].find_one(user_query)
        if user:
            try:
                EmailService.send_doctor_rejection_email(
                    to_email=user.get("email", ""),
                    doctor_name=user.get("fullName", "Doctor"),
                    reason=clean_reason,
                )
            except Exception as exc:
                logger.error("Failed to send doctor rejection email to %s: %s", user.get("email"), exc)

            try:
                NotificationService.create_notification(
                    db=db,
                    recipient_user_id=str(user["_id"]),
                    type=NotificationType.SYSTEM,
                    title="Doctor Application Status Update",
                    body="Your doctor registration application was not approved. Please contact administrative support for further information.",
                )
            except Exception as exc:
                logger.warning("Failed to create in-app notification for rejected doctor: %s", exc)

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
        reason: Optional[str] = None,
    ) -> AdminActionResponse:
        """Suspend or reinstate an account. Prevents self-modification; audited."""
        if str(user_id) == str(admin_user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators cannot modify their own account status.",
            )

        clean_status = (new_status or "").strip().upper()
        # Admins suspend and reinstate accounts. PENDING belongs to registration (email verification and doctor
        # review); setting an account ACTIVE from PENDING would skip those checks (P04-N08).
        allowed = {AccountStatus.ACTIVE.value, AccountStatus.SUSPENDED.value}
        if clean_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid account status '{new_status}'. Allowed: ACTIVE, SUSPENDED",
            )

        u_oid = AdminService._parse_object_id(user_id, "User")
        user = db["users"].find_one({"_id": u_oid})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found.",
            )
        previous = user.get("accountStatus")
        if previous == clean_status:
            return AdminActionResponse(message=f"User account status is already {clean_status}.")
        if clean_status == AccountStatus.ACTIVE.value and previous != AccountStatus.SUSPENDED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only a suspended account can be reinstated. Pending accounts must finish registration.",
            )

        now = utc_now()
        changed = db["users"].update_one(
            {"_id": u_oid, "accountStatus": previous},
            {"$set": {"accountStatus": clean_status, "updatedAt": now}},
        )
        if not changed.matched_count:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="The account status changed. Refresh and try again.")
        if clean_status == AccountStatus.SUSPENDED.value:
            # Access tokens already stop working on the next request (the auth middleware reads the account);
            # refresh tokens are revoked as well so no new session can be issued.
            db["refresh_tokens"].update_many({"userId": str(u_oid), "revokedAt": None}, {"$set": {"revokedAt": now}})
            # Phase 05: access tokens issued before suspension stay invalid after a later reinstatement.
            import math
            db["users"].update_one({"_id": u_oid}, {"$set": {
                "tokensValidAfter": datetime.fromtimestamp(math.ceil(now.timestamp()), tz=timezone.utc)}})
        AdminAuditService.log_action(
            db=db, actor_id=str(admin_user_id), actor_role="ADMIN", action_type=AdminAuditAction.USER_STATUS_CHANGE,
            target_id=str(u_oid), target_type="user", previous_state=previous, new_state=clean_status,
            reason=(reason or "").strip() or None, metadata={"role": user.get("role")},
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
        refunds_by_appt: Dict[str, Any] = {}
        for r in db["refund_requests"].find({"appointmentId": {"$in": [str(a["_id"]) for a in raw_appointments]}},
                                            {"appointmentId": 1, "status": 1, "refundId": 1, "createdAt": 1}).sort("createdAt", 1):
            refunds_by_appt[r["appointmentId"]] = r  # latest request wins

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
            d_spec = profile.get("specialty") or None

            if search and search.strip():
                term = search.strip().lower()
                combined = f"{p_name} {p_email} {d_name} {d_spec or ''} {a.get('appointmentDate', '')} {a['_id']}".lower()
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
                    consultationFee=_locked_fee(a),
                    currency=(a.get("bookingCurrency") or "").upper() or None,
                    consultationType="IN_PERSON",
                    refundStatus=(refunds_by_appt.get(str(a["_id"])) or {}).get("status"),
                    refundId=(refunds_by_appt.get(str(a["_id"])) or {}).get("refundId"),
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

        # The date filters were accepted but ignored before Phase 04 (P04-N04). Asia/Colombo days, by paidAt
        # (createdAt for payments that were never paid).
        from app.services.financial_metrics import payment_time_query, platform_range
        start_dt, end_dt, _, _ = platform_range(start_date, end_date)
        query.update(payment_time_query(start_dt, end_dt))

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
        key_is_test = (settings.STRIPE_SECRET_KEY or "").startswith("sk_test_")
        from app.services.financial_metrics import payment_refunded_amount

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

            intent_id = p.get("stripePaymentIntentId") or ""
            # Was "... or True": every payment was reported as test mode. A recorded payment is verified against the
            # configured key and a livemode mismatch is rejected, so the key's mode is the payment's mode; a stored
            # livemode flag, when present, wins.
            is_test = (not p["livemode"]) if isinstance(p.get("livemode"), bool) else key_is_test

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
                    refundedAmount=payment_refunded_amount(p) if p.get("status") in ("SUCCEEDED", "REFUNDED") else 0.0,
                    reconciliationState=p.get("reconciliationState"),
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
