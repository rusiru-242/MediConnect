from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
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
    consultationFee: float = 2500.0
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
    consultationFee: float = 2500.0
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
    consultationFee: float = 2500.0
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


# ---------------------------------------------------------------------------
# Phase 54: Weekly Schedule, Leave & Blocked Time Schemas
# ---------------------------------------------------------------------------

class WorkingSessionSchema(BaseModel):
    """A working consultation window within a day."""

    startTime: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Start time in HH:MM format")
    endTime: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="End time in HH:MM format")


class WeekdayScheduleSchema(BaseModel):
    """Schedule configuration for a weekday."""

    day: str = Field(..., description="monday, tuesday, wednesday, thursday, friday, saturday, sunday")
    isEnabled: bool = Field(default=True, description="Whether available on this day")
    sessions: List[WorkingSessionSchema] = Field(default_factory=list, description="Working sessions")

    @model_validator(mode="before")
    @classmethod
    def normalize_day_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "day" not in data and "weekday" in data:
                data["day"] = data["weekday"]
        return data


class UpdateWeeklyScheduleRequest(BaseModel):
    """Request payload to configure weekly recurring schedule."""

    timezone: Optional[str] = Field(default="Asia/Colombo", description="Doctor IANA time zone")
    slotDurationMinutes: Optional[int] = Field(default=30, ge=10, le=120, description="Slot duration in minutes")
    weekdays: List[WeekdayScheduleSchema] = Field(..., description="List of 7 weekday configurations")


class DoctorWeeklyScheduleResponse(BaseModel):
    """Response representing doctor weekly recurring schedule."""

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    doctorUserId: str
    doctorProfileId: str
    timezone: str = "Asia/Colombo"
    slotDurationMinutes: int = 30
    weekdays: List[WeekdayScheduleSchema] = Field(default_factory=list)
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class CreateLeaveRequest(BaseModel):
    """Request payload to apply for or schedule leave."""

    leaveType: str = Field(default="PERSONAL", description="PERSONAL | MEDICAL | VACATION | PUBLIC_HOLIDAY | OTHER")
    startDate: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Start date YYYY-MM-DD")
    endDate: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="End date YYYY-MM-DD")
    startTime: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$", description="Start time HH:MM for partial-day")
    endTime: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$", description="End time HH:MM for partial-day")
    reason: Optional[str] = Field(default=None, max_length=500, description="Optional private reason")
    resolveConflicts: bool = Field(default=False, description="Whether to auto-cancel conflicting appointments")


class DoctorLeaveResponse(BaseModel):
    """Response representing a doctor leave record."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    doctorUserId: str
    doctorProfileId: str
    leaveType: str
    startDate: str
    endDate: str
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    reason: Optional[str] = None
    status: str = "ACTIVE"
    createdAt: datetime
    updatedAt: datetime


class ConflictingAppointmentSummary(BaseModel):
    """Summary of appointment conflicting with scheduled leave."""

    appointmentId: str
    patientName: str
    appointmentDate: str
    startTime: str
    endTime: str
    status: str


class LeaveConflictResponse(BaseModel):
    """Response when leave conflicts with existing appointments."""

    detail: str
    conflictCount: int
    conflicts: List[ConflictingAppointmentSummary]


class CreateBlockedTimeRequest(BaseModel):
    """Request payload to block a specific date and time range."""

    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format")
    startTime: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Start time HH:MM")
    endTime: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="End time HH:MM")
    reason: Optional[str] = Field(default=None, max_length=200, description="Optional reason")


class DoctorBlockedTimeResponse(BaseModel):
    """Response representing blocked time interval."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    doctorUserId: str
    doctorProfileId: str
    date: str
    startTime: str
    endTime: str
    reason: Optional[str] = None
    createdAt: datetime


class CalendarDayAppointment(BaseModel):
    """Summary of appointment on a specific calendar day."""

    appointmentId: str
    patientName: str
    startTime: str
    endTime: str
    status: str


class CalendarDayOverview(BaseModel):
    """Summary for a single calendar day in doctor calendar."""

    date: str
    weekday: str
    status: str = Field(description="AVAILABLE | UNAVAILABLE | LEAVE | BLOCKED")
    availableSlotsCount: int = 0
    bookedAppointmentsCount: int = 0
    leave: Optional[DoctorLeaveResponse] = None
    blockedTimes: List[DoctorBlockedTimeResponse] = Field(default_factory=list)
    appointments: List[CalendarDayAppointment] = Field(default_factory=list)
    slots: List[TimeSlot] = Field(default_factory=list)


class DoctorCalendarOverviewResponse(BaseModel):
    """Overview of calendar for a given month or date range."""

    month: str
    days: List[CalendarDayOverview]

