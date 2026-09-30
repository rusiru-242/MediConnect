from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from app.config.database import get_database
from app.schemas.auth import (
    PatientRegisterRequest,
    PatientRegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=PatientRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient",
    description="Registers a new patient account with role PATIENT and pending verification status.",
)
def register_patient(
    payload: PatientRegisterRequest,
    db: Database = Depends(get_database),
) -> PatientRegisterResponse:
    """Handle patient registration."""
    return AuthService.register_patient(payload, db)


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description="Verifies a patient account using the 6-digit OTP code sent to their email.",
)
def verify_email(
    payload: VerifyEmailRequest,
    db: Database = Depends(get_database),
) -> VerifyEmailResponse:
    """Handle email verification using OTP."""
    return AuthService.verify_email(payload, db)


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend verification code",
    description="Generates and emails a new 6-digit OTP code with a 60-second cooldown period.",
)
def resend_verification(
    payload: ResendVerificationRequest,
    db: Database = Depends(get_database),
) -> ResendVerificationResponse:
    """Handle resending verification code."""
    return AuthService.resend_verification(payload, db)
