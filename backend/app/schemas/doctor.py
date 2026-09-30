from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.user import UserResponseSchema


class DoctorProfileResponseSchema(BaseModel):
    """Safe public representation of a doctor profile."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    userId: str
    doctorId: str
    specialty: str
    medicalRegistrationNumber: str
    qualifications: str
    hospitalOrClinic: str
    experienceYears: int
    bio: Optional[str] = None
    verificationStatus: str
    rejectionReason: Optional[str] = None
    submittedAt: datetime
    verifiedAt: Optional[datetime] = None


class DoctorRegisterResponse(BaseModel):
    """Response returned upon successful doctor registration."""

    message: str = "Doctor application submitted successfully. Please verify your email."
    user: UserResponseSchema
    doctorProfile: DoctorProfileResponseSchema


class DoctorApplicationStatusResponse(BaseModel):
    """Safe application status returned to pending/verified doctors."""

    doctorId: str
    specialty: str
    verificationStatus: str
    submittedAt: datetime
    rejectionReason: Optional[str] = None
