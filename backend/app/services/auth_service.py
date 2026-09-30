from datetime import datetime, timezone
import logging
from typing import Any, Dict
from fastapi import HTTPException, status
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.models.user import AccountStatus, UserRole
from app.schemas.auth import PatientRegisterRequest, PatientRegisterResponse
from app.utils.security import hash_password

logger = logging.getLogger(__name__)


class AuthService:
    """Service handling authentication business logic."""

    @staticmethod
    def register_patient(patient_data: PatientRegisterRequest, db: Database) -> PatientRegisterResponse:
        """Register a new patient account."""
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

        # Build document with enforced defaults (client cannot override)
        patient_document = {
            "fullName": patient_data.fullName,
            "email": normalized_email,
            "phone": patient_data.phone,
            "passwordHash": password_hash,
            "role": UserRole.PATIENT.value,
            "emailVerified": False,
            "accountStatus": AccountStatus.PENDING.value,
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

        user_response = {
            "id": str(insert_result.inserted_id),
            "fullName": patient_document["fullName"],
            "email": patient_document["email"],
            "phone": patient_document["phone"],
            "role": patient_document["role"],
            "emailVerified": patient_document["emailVerified"],
            "accountStatus": patient_document["accountStatus"],
            "createdAt": patient_document["createdAt"],
        }

        return PatientRegisterResponse(
            message="Patient registered successfully.",
            user=user_response,
        )
