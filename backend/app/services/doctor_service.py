import logging
from typing import Any, Dict
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.doctor_profile import get_doctor_profile_collection
from app.schemas.doctor import DoctorApplicationStatusResponse

logger = logging.getLogger(__name__)


class DoctorService:
    """Business logic for Doctor application and profile management."""

    @staticmethod
    def get_application_status(user_id: str, db: Database) -> DoctorApplicationStatusResponse:
        """Fetch application status for an authenticated doctor."""
        collection = get_doctor_profile_collection(db)

        profile = collection.find_one({"userId": str(user_id)})
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found for this account.",
            )

        return DoctorApplicationStatusResponse(
            doctorId=str(profile.get("doctorId", "")),
            specialty=str(profile.get("specialty", "")),
            verificationStatus=str(profile.get("verificationStatus", "PENDING")),
            submittedAt=profile.get("submittedAt"),
            rejectionReason=profile.get("rejectionReason"),
        )
