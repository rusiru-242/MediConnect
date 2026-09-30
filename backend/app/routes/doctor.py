from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_doctor
from app.schemas.doctor import DoctorApplicationStatusResponse
from app.schemas.user import UserResponseSchema
from app.services.doctor_service import DoctorService

doctor_router = APIRouter(prefix="/doctors", tags=["Doctors"])


@doctor_router.get(
    "/me/application-status",
    response_model=DoctorApplicationStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get doctor application status",
    description="Returns verification status and submission details for the authenticated doctor. Does not expose internal documents.",
)
def get_application_status(
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> DoctorApplicationStatusResponse:
    """Fetch current doctor's application status."""
    return DoctorService.get_application_status(current_user.id, db)
