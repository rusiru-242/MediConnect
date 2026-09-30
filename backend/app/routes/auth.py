from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from app.config.database import get_database
from app.schemas.auth import PatientRegisterRequest, PatientRegisterResponse
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
