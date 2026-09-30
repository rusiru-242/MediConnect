from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
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
)
from app.schemas.user import UserResponseSchema
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


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in user",
    description="Authenticates user credentials and issues an access token and refresh token.",
)
def login(
    payload: LoginRequest,
    db: Database = Depends(get_database),
) -> LoginResponse:
    """Handle user login and session initialization."""
    return AuthService.login(payload, db)


@router.get(
    "/me",
    response_model=UserResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the profile of the currently authenticated user based on JWT access token.",
)
def get_me(
    current_user: UserResponseSchema = Depends(get_current_user),
) -> UserResponseSchema:
    """Return authenticated user profile."""
    return current_user


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Rotates refresh token and returns a new access token and refresh token pair.",
)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Database = Depends(get_database),
) -> RefreshTokenResponse:
    """Handle refresh token rotation."""
    return AuthService.refresh_token(payload, db)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Log out user",
    description="Revokes the active refresh token session.",
)
def logout(
    payload: LogoutRequest,
    db: Database = Depends(get_database),
) -> LogoutResponse:
    """Handle user logout and session invalidation."""
    return AuthService.logout(payload, db)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset code",
    description="Sends a 6-digit password reset OTP to the email address if an account exists.",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Database = Depends(get_database),
) -> ForgotPasswordResponse:
    """Handle password reset request."""
    return AuthService.forgot_password(payload, db)


@router.post(
    "/verify-reset-otp",
    response_model=VerifyResetOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify password reset OTP",
    description="Verifies the 6-digit OTP and issues a short-lived reset token for setting a new password.",
)
def verify_reset_otp(
    payload: VerifyResetOtpRequest,
    db: Database = Depends(get_database),
) -> VerifyResetOtpResponse:
    """Handle verification of password reset OTP."""
    return AuthService.verify_reset_otp(payload, db)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="Resets the user's password using a valid reset token and invalidates all active sessions.",
)
def reset_password(
    payload: ResetPasswordRequest,
    db: Database = Depends(get_database),
) -> ResetPasswordResponse:
    """Handle setting a new password."""
    return AuthService.reset_password(payload, db)
