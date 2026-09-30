from datetime import datetime, timedelta, timezone
import logging
import re
import secrets
from typing import Any, Dict, Optional
from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.config.settings import settings
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.specialty import is_valid_specialty
from app.models.user import AccountStatus, UserRole
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleAuthRequest,
    GoogleAuthResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    PatientRegisterRequest,
    PatientRegisterResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
    VerifyResetOtpRequest,
    VerifyResetOtpResponse,
    validate_password_strength,
)
from app.schemas.doctor import DoctorProfileResponseSchema, DoctorRegisterResponse
from app.schemas.user import UserResponseSchema
from app.services.document_storage_service import document_storage
from app.services.email_service import EmailService
from app.services.google_auth_service import GoogleAuthVerifier
from app.utils.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)

logger = logging.getLogger(__name__)

MAX_OTP_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
OTP_EXPIRATION_MINUTES = 10


def _ensure_utc(dt: Any) -> datetime:
    """Ensure datetime object is timezone-aware in UTC."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return dt


class AuthService:
    """Service handling authentication, sessions, email verification, password resets, and Google auth."""

    @staticmethod
    def register_patient(patient_data: PatientRegisterRequest, db: Database) -> PatientRegisterResponse:
        """Register a new patient account and send a 6-digit verification OTP."""
        normalized_email = patient_data.email.strip().lower()

        # Check for existing email in database
        try:
            existing_user = db["users"].find_one({"email": normalized_email})
        except PyMongoError as exc:
            logger.error("Database query failed during duplicate email check: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database error occurred while verifying email availability.",
            )

        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        # Hash password securely
        password_hash = hash_password(patient_data.password)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=OTP_EXPIRATION_MINUTES)

        # Generate cryptographically secure 6-digit OTP and hash it before storage
        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = hash_password(otp)

        # Build document with enforced defaults (client cannot override)
        patient_document = {
            "fullName": patient_data.fullName,
            "email": normalized_email,
            "phone": patient_data.phone,
            "passwordHash": password_hash,
            "role": UserRole.PATIENT.value,
            "emailVerified": False,
            "accountStatus": AccountStatus.PENDING.value,
            "authProviders": ["LOCAL"],
            "profileImage": None,
            "emailVerification": {
                "otpHash": otp_hash,
                "expiresAt": expires_at,
                "attempts": 0,
                "lastSentAt": now,
            },
            "createdAt": now,
            "updatedAt": now,
        }

        try:
            insert_result = db["users"].insert_one(patient_document)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        except PyMongoError as exc:
            logger.error("Failed to insert patient document: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while creating the account.",
            )

        # Send verification email with OTP (does not log or store plain OTP)
        EmailService.send_verification_otp(normalized_email, otp)

        user_response = {
            "id": str(insert_result.inserted_id),
            "fullName": patient_document["fullName"],
            "email": patient_document["email"],
            "phone": patient_document["phone"],
            "role": patient_document["role"],
            "emailVerified": patient_document["emailVerified"],
            "accountStatus": patient_document["accountStatus"],
            "createdAt": patient_document["createdAt"],
            "authProviders": patient_document["authProviders"],
            "profileImage": patient_document["profileImage"],
        }

        return PatientRegisterResponse(
            message="Patient registered successfully.",
            user=user_response,
        )

    @staticmethod
    async def register_doctor(
        full_name: str,
        email: str,
        phone: str,
        password: str,
        specialty: str,
        medical_registration_number: str,
        qualifications: str,
        hospital_or_clinic: str,
        experience_years: int,
        bio: Optional[str],
        identity_document: UploadFile,
        medical_registration_document: UploadFile,
        qualification_document: UploadFile,
        db: Database,
    ) -> DoctorRegisterResponse:
        """Register a new doctor account with verification documents and initiate email OTP."""
        # 1. Validate full name
        clean_name = (full_name or "").strip()
        if len(clean_name) < 2 or len(clean_name) > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Full name must be between 2 and 100 characters.",
            )

        # 2. Validate email
        clean_email = (email or "").strip().lower()
        if not re.fullmatch(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", clean_email):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Please enter a valid email address.",
            )

        # 3. Validate Sri Lankan phone
        raw_phone = re.sub(r"[\s\-()]", "", phone or "")
        normalized_phone = None
        if re.fullmatch(r"07[0-8]\d{7}", raw_phone):
            normalized_phone = f"+94{raw_phone[1:]}"
        elif re.fullmatch(r"\+947[0-8]\d{7}", raw_phone):
            normalized_phone = raw_phone
        elif re.fullmatch(r"947[0-8]\d{7}", raw_phone):
            normalized_phone = f"+{raw_phone}"
        elif re.fullmatch(r"00947[0-8]\d{7}", raw_phone):
            normalized_phone = f"+{raw_phone[2:]}"
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid Sri Lankan mobile number format.",
            )

        # 4. Validate strong password
        try:
            validate_password_strength(password)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            )

        # 5. Validate specialty
        clean_specialty = (specialty or "").strip()
        if not is_valid_specialty(clean_specialty):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid specialty. Please select a supported specialty.",
            )

        # 6. Validate medical registration number
        clean_med_reg = (medical_registration_number or "").strip()
        if not clean_med_reg or len(clean_med_reg) < 2 or len(clean_med_reg) > 50:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Medical registration number is required (2 to 50 characters).",
            )

        # 7. Validate qualifications & hospital
        clean_qualifications = (qualifications or "").strip()
        if not clean_qualifications or len(clean_qualifications) < 2 or len(clean_qualifications) > 200:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Qualifications are required.",
            )

        clean_hospital = (hospital_or_clinic or "").strip()
        if not clean_hospital or len(clean_hospital) < 2 or len(clean_hospital) > 150:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Hospital or clinic name is required.",
            )

        # 8. Experience years
        try:
            exp_int = int(experience_years)
            if exp_int < 0 or exp_int > 70:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Experience years must be between 0 and 70.",
            )

        # 9. Bio
        clean_bio = (bio.strip() if bio else None)
        if clean_bio and len(clean_bio) > 1000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Bio cannot exceed 1000 characters.",
            )

        # 10. Check uniqueness before saving files
        if db["users"].find_one({"email": clean_email}):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        if db["doctor_profiles"].find_one({"medicalRegistrationNumber": clean_med_reg}):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A doctor profile with this medical registration number already exists.",
            )

        # 11. Process and save verification documents
        temp_user_id = str(ObjectId())
        id_doc_meta = await document_storage.save_document(
            identity_document, "identity_document", temp_user_id
        )
        med_doc_meta = await document_storage.save_document(
            medical_registration_document, "medical_registration_document", temp_user_id
        )
        qual_doc_meta = await document_storage.save_document(
            qualification_document, "qualification_document", temp_user_id
        )

        now = datetime.now(timezone.utc)
        password_hash = hash_password(password)
        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = hash_password(otp)
        expires_at = now + timedelta(minutes=OTP_EXPIRATION_MINUTES)

        user_doc = {
            "_id": ObjectId(temp_user_id),
            "fullName": clean_name,
            "email": clean_email,
            "phone": normalized_phone,
            "passwordHash": password_hash,
            "role": UserRole.DOCTOR.value,
            "emailVerified": False,
            "accountStatus": AccountStatus.PENDING.value,
            "authProviders": ["LOCAL"],
            "profileImage": None,
            "emailVerification": {
                "otpHash": otp_hash,
                "expiresAt": expires_at,
                "attempts": 0,
                "lastSentAt": now,
            },
            "createdAt": now,
            "updatedAt": now,
        }

        doctor_id = f"DOC-{secrets.token_hex(4).upper()}"
        doctor_profile_doc = {
            "userId": temp_user_id,
            "doctorId": doctor_id,
            "specialty": clean_specialty,
            "medicalRegistrationNumber": clean_med_reg,
            "qualifications": clean_qualifications,
            "hospitalOrClinic": clean_hospital,
            "experienceYears": exp_int,
            "bio": clean_bio,
            "verificationDocuments": {
                "identityDocument": id_doc_meta,
                "medicalRegistrationDocument": med_doc_meta,
                "qualificationDocument": qual_doc_meta,
            },
            "verificationStatus": DoctorVerificationStatus.PENDING.value,
            "rejectionReason": None,
            "submittedAt": now,
            "verifiedAt": None,
            "createdAt": now,
            "updatedAt": now,
        }

        try:
            db["users"].insert_one(user_doc)
            profile_res = db["doctor_profiles"].insert_one(doctor_profile_doc)
            doctor_profile_doc["_id"] = profile_res.inserted_id
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account or registration number with these details already exists.",
            )
        except PyMongoError as exc:
            logger.error("Database error during doctor registration: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while creating doctor account.",
            )

        EmailService.send_verification_otp(clean_email, otp)

        user_response = UserResponseSchema(
            id=temp_user_id,
            fullName=clean_name,
            email=clean_email,
            phone=normalized_phone,
            role=UserRole.DOCTOR.value,
            emailVerified=False,
            accountStatus=AccountStatus.PENDING.value,
            authProviders=["LOCAL"],
            createdAt=now,
            updatedAt=now,
        )

        profile_response = DoctorProfileResponseSchema(
            id=str(doctor_profile_doc["_id"]),
            userId=temp_user_id,
            doctorId=doctor_id,
            specialty=clean_specialty,
            medicalRegistrationNumber=clean_med_reg,
            qualifications=clean_qualifications,
            hospitalOrClinic=clean_hospital,
            experienceYears=exp_int,
            bio=clean_bio,
            verificationStatus=DoctorVerificationStatus.PENDING.value,
            rejectionReason=None,
            submittedAt=now,
            verifiedAt=None,
        )

        return DoctorRegisterResponse(
            message="Doctor application submitted successfully. Please verify your email.",
            user=user_response,
            doctorProfile=profile_response,
        )

    @staticmethod
    def verify_email(payload: VerifyEmailRequest, db: Database) -> VerifyEmailResponse:
        """Verify patient email using submitted 6-digit OTP."""
        normalized_email = payload.email.strip().lower()

        try:
            user = db["users"].find_one({"email": normalized_email})
        except PyMongoError as exc:
            logger.error("Database query failed during email verification: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database error occurred during verification.",
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification request.",
            )

        if user.get("emailVerified") is True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is already verified.",
            )

        verification = user.get("emailVerification")
        if not verification or "otpHash" not in verification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pending verification code found. Please request a new code.",
            )

        # Check attempt threshold before comparing
        attempts = verification.get("attempts", 0)
        if attempts >= MAX_OTP_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts exceeded. Please request a new code.",
            )

        # Check expiration
        expires_at = _ensure_utc(verification.get("expiresAt"))
        now = datetime.now(timezone.utc)
        if expires_at and now > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired. Please request a new code.",
            )

        # Securely compare submitted OTP against stored hash
        is_valid = verify_password(payload.otp, verification["otpHash"])

        if not is_valid:
            new_attempts = attempts + 1
            try:
                db["users"].update_one(
                    {"_id": user["_id"]},
                    {"$set": {"emailVerification.attempts": new_attempts}},
                )
            except PyMongoError as exc:
                logger.error("Failed to update verification attempts: %s", type(exc).__name__)

            if new_attempts >= MAX_OTP_ATTEMPTS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum verification attempts exceeded. Please request a new code.",
                )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code. Please check and try again.",
            )

        # OTP is valid:
        user_role = user.get("role", UserRole.PATIENT.value)
        # For PATIENT: successful email verification activates the account.
        # For DOCTOR: successful email verification marks emailVerified = True,
        # but accountStatus remains PENDING until administrative review & approval.
        new_account_status = (
            AccountStatus.PENDING.value
            if user_role == UserRole.DOCTOR.value
            else AccountStatus.ACTIVE.value
        )

        try:
            db["users"].update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "emailVerified": True,
                        "accountStatus": new_account_status,
                        "updatedAt": now,
                    },
                    "$unset": {
                        "emailVerification": "",
                    },
                },
            )
        except PyMongoError as exc:
            logger.error("Failed to activate verified user: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating verification status.",
            )

        return VerifyEmailResponse(message="Email verified successfully.")

    @staticmethod
    def resend_verification(payload: ResendVerificationRequest, db: Database) -> ResendVerificationResponse:
        """Resend a new 6-digit OTP with cooldown protection."""
        normalized_email = payload.email.strip().lower()

        try:
            user = db["users"].find_one({"email": normalized_email})
        except PyMongoError as exc:
            logger.error("Database query failed during resend verification: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database error occurred.",
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request. No account found with this email.",
            )

        if user.get("emailVerified") is True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is already verified.",
            )

        verification = user.get("emailVerification")
        now = datetime.now(timezone.utc)

        # Enforce 60-second cooldown
        if verification and "lastSentAt" in verification:
            last_sent = _ensure_utc(verification["lastSentAt"])
            elapsed = (now - last_sent).total_seconds()
            if elapsed < RESEND_COOLDOWN_SECONDS:
                remaining = int(RESEND_COOLDOWN_SECONDS - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {remaining} seconds before requesting a new verification code.",
                )

        # Generate new OTP, hash it, and reset attempts
        new_otp = f"{secrets.randbelow(1_000_000):06d}"
        new_otp_hash = hash_password(new_otp)
        expires_at = now + timedelta(minutes=OTP_EXPIRATION_MINUTES)

        try:
            db["users"].update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "emailVerification": {
                            "otpHash": new_otp_hash,
                            "expiresAt": expires_at,
                            "attempts": 0,
                            "lastSentAt": now,
                        },
                        "updatedAt": now,
                    }
                },
            )
        except PyMongoError as exc:
            logger.error("Failed to update user with new OTP: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate new verification code.",
            )

        EmailService.send_verification_otp(normalized_email, new_otp)

        return ResendVerificationResponse(
            message="Verification code has been resent successfully."
        )

    @staticmethod
    def login(payload: LoginRequest, db: Database) -> LoginResponse:
        """Authenticate user credentials and issue access + refresh tokens."""
        normalized_email = payload.email.strip().lower()

        try:
            user = db["users"].find_one({"email": normalized_email})
        except PyMongoError as exc:
            logger.error("Database query error during login: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database error occurred during login.",
            )

        # Generic credential rejection (does not reveal if email or password was wrong)
        if not user or not user.get("passwordHash"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verify_password(payload.password, user["passwordHash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check email verification status
        if not user.get("emailVerified"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email verification is required before logging in. Please verify your email.",
            )

        # Check account status
        account_status = user.get("accountStatus")
        user_role = user.get("role", UserRole.PATIENT.value)

        if account_status == AccountStatus.SUSPENDED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended. Please contact support.",
            )

        # Allow DOCTOR with verified email and PENDING status for restricted application-status sessions
        is_pending_verified_doctor = (
            user_role == UserRole.DOCTOR.value
            and user.get("emailVerified") is True
            and account_status == AccountStatus.PENDING.value
        )

        if not is_pending_verified_doctor and account_status != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active.",
            )

        user_id_str = str(user["_id"])
        user_role = user.get("role", UserRole.PATIENT.value)

        # Generate JWT access token (60 minutes default)
        access_token = create_access_token(user_id=user_id_str, role=user_role)
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        # Generate opaque refresh token and store only its SHA-256 hash
        raw_refresh_token = generate_refresh_token()
        refresh_hash = hash_token(raw_refresh_token)
        now = datetime.now(timezone.utc)
        refresh_expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        try:
            db["refresh_tokens"].insert_one({
                "userId": user_id_str,
                "tokenHash": refresh_hash,
                "expiresAt": refresh_expires,
                "createdAt": now,
                "revokedAt": None,
            })
        except PyMongoError as exc:
            logger.error("Failed to store refresh token hash: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate authenticated session.",
            )

        safe_user = UserResponseSchema(
            id=user_id_str,
            fullName=user["fullName"],
            email=user["email"],
            phone=user.get("phone"),
            role=user_role,
            emailVerified=user["emailVerified"],
            accountStatus=user["accountStatus"],
            createdAt=user["createdAt"],
            updatedAt=user.get("updatedAt"),
            profileImage=user.get("profileImage"),
            authProviders=user.get("authProviders", ["LOCAL"]),
        )

        return LoginResponse(
            message="Login successful.",
            accessToken=access_token,
            refreshToken=raw_refresh_token,
            tokenType="bearer",
            expiresIn=expires_in,
            user=safe_user,
        )

    @staticmethod
    def refresh_token(payload: RefreshTokenRequest, db: Database) -> RefreshTokenResponse:
        """Rotate a refresh token, revoking the old one and returning a new access + refresh pair."""
        token_hash = hash_token(payload.refreshToken)

        try:
            token_record = db["refresh_tokens"].find_one({"tokenHash": token_hash})
        except PyMongoError as exc:
            logger.error("Database query error during token refresh: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error during token refresh.",
            )

        if not token_record or token_record.get("revokedAt") is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        expires_at = _ensure_utc(token_record.get("expiresAt"))
        now = datetime.now(timezone.utc)
        if expires_at and now > expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = token_record.get("userId")
        user_query = {"$or": [{"_id": ObjectId(user_id)}, {"_id": user_id}]} if ObjectId.is_valid(user_id) else {"_id": user_id}

        try:
            user = db["users"].find_one(user_query)
        except PyMongoError as exc:
            logger.error("Database query error finding user for refresh: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error during token refresh.",
            )

        is_pending_verified_doctor = (
            user.get("role") == UserRole.DOCTOR.value
            and user.get("emailVerified") is True
            and user.get("accountStatus") == AccountStatus.PENDING.value
        )

        if not user or not user.get("emailVerified") or user.get("accountStatus") == AccountStatus.SUSPENDED.value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive or not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not is_pending_verified_doctor and user.get("accountStatus") != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive or not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Invalidate the used refresh token immediately (token rotation)
        try:
            db["refresh_tokens"].update_one(
                {"_id": token_record["_id"]},
                {"$set": {"revokedAt": now}},
            )
        except PyMongoError as exc:
            logger.error("Failed to revoke old refresh token during rotation: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update session state.",
            )

        # Generate fresh access token and new rotated refresh token
        new_access_token = create_access_token(user_id=str(user["_id"]), role=user["role"])
        new_raw_refresh = generate_refresh_token()
        new_refresh_hash = hash_token(new_raw_refresh)
        new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        try:
            db["refresh_tokens"].insert_one({
                "userId": str(user["_id"]),
                "tokenHash": new_refresh_hash,
                "expiresAt": new_expires_at,
                "createdAt": now,
                "revokedAt": None,
            })
        except PyMongoError as exc:
            logger.error("Failed to store new refresh token: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist rotated session.",
            )

        return RefreshTokenResponse(
            message="Token refreshed successfully.",
            accessToken=new_access_token,
            refreshToken=new_raw_refresh,
            tokenType="bearer",
            expiresIn=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    def logout(payload: LogoutRequest, db: Database) -> LogoutResponse:
        """Revoke the submitted refresh token to terminate session."""
        token_hash = hash_token(payload.refreshToken)
        now = datetime.now(timezone.utc)

        try:
            db["refresh_tokens"].update_one(
                {"tokenHash": token_hash, "revokedAt": None},
                {"$set": {"revokedAt": now}},
            )
        except PyMongoError as exc:
            logger.error("Database error during logout: %s", type(exc).__name__)

        return LogoutResponse(message="Logged out successfully.")

    @staticmethod
    def forgot_password(payload: ForgotPasswordRequest, db: Database) -> ForgotPasswordResponse:
        """Process password reset request securely without revealing account existence."""
        normalized_email = payload.email.strip().lower()

        try:
            user = db["users"].find_one({"email": normalized_email})
        except PyMongoError as exc:
            logger.error("Database error during forgot-password lookup: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database error occurred.",
            )

        # If user exists, enforce cooldown and issue a new reset OTP
        if user:
            existing_challenge = db["password_resets"].find_one({
                "email": normalized_email,
                "used": False,
            })

            now = datetime.now(timezone.utc)
            if existing_challenge and "lastSentAt" in existing_challenge:
                last_sent = _ensure_utc(existing_challenge["lastSentAt"])
                elapsed = (now - last_sent).total_seconds()
                if elapsed < RESEND_COOLDOWN_SECONDS:
                    remaining = int(RESEND_COOLDOWN_SECONDS - elapsed)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Please wait {remaining} seconds before requesting a new password reset code.",
                    )

            otp = f"{secrets.randbelow(1_000_000):06d}"
            otp_hash = hash_password(otp)
            expires_at = now + timedelta(minutes=OTP_EXPIRATION_MINUTES)

            # Invalidate any previous challenges for this email
            db["password_resets"].delete_many({"email": normalized_email})

            db["password_resets"].insert_one({
                "userId": str(user["_id"]),
                "email": normalized_email,
                "otpHash": otp_hash,
                "expiresAt": expires_at,
                "attempts": 0,
                "lastSentAt": now,
                "used": False,
                "createdAt": now,
            })

            EmailService.send_password_reset_otp(normalized_email, otp)

        # Generic response returned whether account exists or not
        return ForgotPasswordResponse(
            message="If an account exists for this email, a password reset code has been sent."
        )

    @staticmethod
    def verify_reset_otp(payload: VerifyResetOtpRequest, db: Database) -> VerifyResetOtpResponse:
        """Verify the 6-digit reset OTP and issue a short-lived reset token."""
        normalized_email = payload.email.strip().lower()

        try:
            challenge = db["password_resets"].find_one({
                "email": normalized_email,
                "used": False,
            })
        except PyMongoError as exc:
            logger.error("Database error during reset OTP verification: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database error occurred.",
            )

        if not challenge:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset request.",
            )

        attempts = challenge.get("attempts", 0)
        if attempts >= MAX_OTP_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum reset attempts exceeded. Please request a new password reset code.",
            )

        expires_at = _ensure_utc(challenge.get("expiresAt"))
        now = datetime.now(timezone.utc)
        if expires_at and now > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset code has expired. Please request a new code.",
            )

        is_valid = verify_password(payload.otp, challenge["otpHash"])

        if not is_valid:
            new_attempts = attempts + 1
            try:
                db["password_resets"].update_one(
                    {"_id": challenge["_id"]},
                    {"$set": {"attempts": new_attempts}},
                )
            except PyMongoError as exc:
                logger.error("Failed to update reset attempts: %s", type(exc).__name__)

            if new_attempts >= MAX_OTP_ATTEMPTS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum reset attempts exceeded. Please request a new password reset code.",
                )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset code. Please check and try again.",
            )

        # Generate single-purpose, cryptographically secure reset token
        raw_reset_token = secrets.token_urlsafe(48)
        reset_token_hash = hash_token(raw_reset_token)
        reset_token_expires = now + timedelta(minutes=OTP_EXPIRATION_MINUTES)

        try:
            db["password_resets"].update_one(
                {"_id": challenge["_id"]},
                {
                    "$set": {
                        "resetTokenHash": reset_token_hash,
                        "resetTokenExpiresAt": reset_token_expires,
                        "otpVerified": True,
                    }
                },
            )
        except PyMongoError as exc:
            logger.error("Failed to store reset token: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate reset token.",
            )

        return VerifyResetOtpResponse(
            message="Reset code verified.",
            resetToken=raw_reset_token,
        )

    @staticmethod
    def reset_password(payload: ResetPasswordRequest, db: Database) -> ResetPasswordResponse:
        """Reset user password using verified reset token, then revoke all active user sessions."""
        token_hash = hash_token(payload.resetToken)

        try:
            challenge = db["password_resets"].find_one({
                "resetTokenHash": token_hash,
                "used": False,
            })
        except PyMongoError as exc:
            logger.error("Database error during password reset: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database error occurred.",
            )

        if not challenge:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already used reset token.",
            )

        expires_at = _ensure_utc(challenge.get("resetTokenExpiresAt"))
        now = datetime.now(timezone.utc)
        if expires_at and now > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired. Please request a new password reset code.",
            )

        user_id = challenge.get("userId")
        user_query = {"$or": [{"_id": ObjectId(user_id)}, {"_id": user_id}]} if ObjectId.is_valid(user_id) else {"_id": user_id}

        try:
            user = db["users"].find_one(user_query)
        except PyMongoError as exc:
            logger.error("Database error finding user for reset: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A database error occurred.",
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account not found.",
            )

        # Hash new password
        new_password_hash = hash_password(payload.newPassword)

        try:
            # 1. Update user password
            db["users"].update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "passwordHash": new_password_hash,
                        "updatedAt": now,
                    }
                },
            )

            # 2. Mark reset challenge as used
            db["password_resets"].update_one(
                {"_id": challenge["_id"]},
                {
                    "$set": {
                        "used": True,
                        "usedAt": now,
                    }
                },
            )

            # 3. Invalidate ALL existing refresh tokens/sessions for this user
            db["refresh_tokens"].update_many(
                {"userId": str(user["_id"]), "revokedAt": None},
                {"$set": {"revokedAt": now}},
            )
        except PyMongoError as exc:
            logger.error("Failed to apply password reset changes: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password. Please try again.",
            )

        return ResetPasswordResponse(
            message="Password reset successfully. Please log in again."
        )

    @staticmethod
    def google_authenticate(payload: GoogleAuthRequest, db: Database) -> GoogleAuthResponse:
        """Authenticate or register a patient via independently verified Google OAuth2 ID token."""
        id_info = GoogleAuthVerifier.verify_token(payload.idToken)

        google_sub = str(id_info["sub"])
        email = id_info["email"].strip().lower()
        full_name = id_info.get("name") or "Google User"
        picture = id_info.get("picture")

        # Lookup existing user by googleSub and by email
        user_by_sub = db["users"].find_one({"googleSub": google_sub})
        user_by_email = db["users"].find_one({"email": email})

        # Integrity check: Google sub linked to a different email account
        if user_by_sub and user_by_email and user_by_sub["_id"] != user_by_email["_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This Google account is already linked to another user.",
            )

        existing_user = user_by_email or user_by_sub
        now = datetime.now(timezone.utc)

        if existing_user:
            # Restrict Google authentication to PATIENT accounts only
            if existing_user.get("role") != UserRole.PATIENT.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Google authentication is only permitted for patient accounts.",
                )

            # Prevent suspended users from accessing via Google
            if existing_user.get("accountStatus") == AccountStatus.SUSPENDED.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is suspended. Please contact support.",
                )

            # Securely link Google identity to existing account without overwriting password or role
            update_data: Dict[str, Any] = {
                "updatedAt": now,
                "emailVerified": True,  # Google verified email
                "accountStatus": AccountStatus.ACTIVE.value,
            }
            if not existing_user.get("googleSub"):
                update_data["googleSub"] = google_sub
            if picture and not existing_user.get("profileImage"):
                update_data["profileImage"] = picture

            db["users"].update_one(
                {"_id": existing_user["_id"]},
                {
                    "$set": update_data,
                    "$addToSet": {"authProviders": "GOOGLE"},
                },
            )
            user = db["users"].find_one({"_id": existing_user["_id"]})
        else:
            # Create new PATIENT user (never ADMIN or DOCTOR, no fake password)
            new_user_document = {
                "fullName": full_name,
                "email": email,
                "phone": None,
                "passwordHash": None,
                "role": UserRole.PATIENT.value,
                "emailVerified": True,
                "accountStatus": AccountStatus.ACTIVE.value,
                "authProviders": ["GOOGLE"],
                "googleSub": google_sub,
                "profileImage": picture,
                "createdAt": now,
                "updatedAt": now,
            }
            try:
                insert_result = db["users"].insert_one(new_user_document)
            except DuplicateKeyError:
                user = db["users"].find_one({"email": email})
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="An account with this email already exists.",
                    )
            else:
                user = new_user_document
                user["_id"] = insert_result.inserted_id

        user_id_str = str(user["_id"])
        user_role = user.get("role", UserRole.PATIENT.value)

        # Generate standard MediConnect JWT access token and refresh token pair
        access_token = create_access_token(user_id=user_id_str, role=user_role)
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        raw_refresh_token = generate_refresh_token()
        refresh_hash = hash_token(raw_refresh_token)
        refresh_expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        try:
            db["refresh_tokens"].insert_one({
                "userId": user_id_str,
                "tokenHash": refresh_hash,
                "expiresAt": refresh_expires,
                "createdAt": now,
                "revokedAt": None,
            })
        except PyMongoError as exc:
            logger.error("Failed to store refresh token during Google login: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate authenticated session.",
            )

        safe_user = UserResponseSchema(
            id=user_id_str,
            fullName=user["fullName"],
            email=user["email"],
            phone=user.get("phone"),
            role=user_role,
            emailVerified=user["emailVerified"],
            accountStatus=user["accountStatus"],
            createdAt=user["createdAt"],
            updatedAt=user.get("updatedAt"),
            profileImage=user.get("profileImage"),
            authProviders=user.get("authProviders", ["GOOGLE"]),
        )

        return GoogleAuthResponse(
            message="Google authentication successful.",
            accessToken=access_token,
            refreshToken=raw_refresh_token,
            tokenType="bearer",
            expiresIn=expires_in,
            user=safe_user,
        )
