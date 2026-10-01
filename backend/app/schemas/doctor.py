from datetime import datetime
from typing import List, Optional
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


# Patient Doctor Discovery Schemas

class DoctorListItem(BaseModel):
    """Safe summary of an approved doctor for patient search/listing."""

    model_config = ConfigDict(populate_by_name=True)

    doctorId: str
    fullName: str
    specialty: str
    hospitalOrClinic: str
    experienceYears: int
    bio: Optional[str] = None
    profileImage: Optional[str] = None
    verificationStatus: str = "APPROVED"


class DoctorListResponse(BaseModel):
    """Paginated list of approved doctors."""

    model_config = ConfigDict(populate_by_name=True)

    items: List[DoctorListItem]
    page: int
    limit: int
    total: int
    totalPages: int


class DoctorDetailResponse(BaseModel):
    """Detailed public profile for an approved doctor."""

    model_config = ConfigDict(populate_by_name=True)

    doctorId: str
    fullName: str
    specialty: str
    qualifications: str
    hospitalOrClinic: str
    experienceYears: int
    bio: Optional[str] = None
    profileImage: Optional[str] = None
    verificationStatus: str = "APPROVED"


# Doctor Availability Management Schemas

class CreateAvailabilityRequest(BaseModel):
    """Request payload to define a new availability window."""

    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format")
    startTime: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Start time in HH:MM format (24-hour)")
    endTime: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="End time in HH:MM format (24-hour)")
    slotDurationMinutes: int = Field(default=30, description="Duration in minutes (15, 20, 30, 45, 60)")


class UpdateAvailabilityRequest(BaseModel):
    """Request payload to update an existing availability window."""

    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    startTime: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    endTime: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    slotDurationMinutes: Optional[int] = None
    isActive: Optional[bool] = None


class DoctorAvailabilityResponse(BaseModel):
    """Response representing an availability window."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    doctorUserId: str
    doctorProfileId: str
    date: str
    startTime: str
    endTime: str
    slotDurationMinutes: int
    isActive: bool
    createdAt: datetime
    updatedAt: datetime


class TimeSlot(BaseModel):
    """Generated time slot for patient booking."""

    startTime: str
    endTime: str
    availabilityId: Optional[str] = None


class DayAvailabilitySlots(BaseModel):
    """Available slots on a specific date."""

    date: str
    slots: List[TimeSlot]


class DoctorSlotsResponse(BaseModel):
    """Generated patient-visible slots grouped by date."""

    doctorId: str
    availabilities: List[DayAvailabilitySlots]
