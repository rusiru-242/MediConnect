"""Appointment schemas for request validation and API responses."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateAppointmentRequest(BaseModel):
    """Request payload for a patient booking an appointment."""

    doctorId: str = Field(..., description="Doctor's doctorId or profile _id")
    availabilityId: Optional[str] = Field(default=None, description="The availability window _id")
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date YYYY-MM-DD")
    appointmentDate: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date YYYY-MM-DD")
    startTime: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Slot start time HH:MM")
    patientNote: Optional[str] = Field(default=None, max_length=500, description="Optional note for doctor")

    @model_validator(mode="after")
    def resolve_date(self) -> "CreateAppointmentRequest":
        target_date = self.date or self.appointmentDate
        if not target_date:
            raise ValueError("Either 'date' or 'appointmentDate' must be provided.")
        self.date = target_date
        self.appointmentDate = target_date
        return self


class AppointmentResponse(BaseModel):
    """Full appointment data returned to patient or doctor."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    patientUserId: str
    doctorUserId: str
    doctorProfileId: str
    availabilityId: str
    appointmentDate: str
    startTime: str
    endTime: str
    status: str
    patientNote: Optional[str] = None
    cancelledBy: Optional[str] = None
    cancellationReason: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime

    # Enriched fields for patient and doctor display
    doctorId: Optional[str] = None
    patientName: Optional[str] = None
    patientEmail: Optional[str] = None
    doctorName: Optional[str] = None
    specialty: Optional[str] = None
    hospitalOrClinic: Optional[str] = None


class CreateAppointmentResponse(BaseModel):
    """Response returned upon successful appointment creation."""

    message: str = "Appointment request created successfully."
    appointment: AppointmentResponse

    def __getattr__(self, item: str):
        try:
            return super().__getattr__(item)
        except AttributeError:
            if "appointment" in self.__dict__ and hasattr(self.appointment, item):
                return getattr(self.appointment, item)
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")


class CancelAppointmentRequest(BaseModel):
    """Request payload to cancel an appointment."""

    reason: Optional[str] = Field(default=None, max_length=500, description="Optional cancellation reason")


class UpdateAppointmentStatusRequest(BaseModel):
    """Request payload for doctor/admin to update appointment status."""

    status: str = Field(..., description="New status: CONFIRMED | COMPLETED | CANCELLED")
    reason: Optional[str] = Field(default=None, max_length=500, description="Optional reason (for CANCELLED)")


class AppointmentListResponse(BaseModel):
    """Paginated list of appointments."""

    model_config = ConfigDict(populate_by_name=True)

    items: List[AppointmentResponse]
    page: int
    limit: int
    total: int
    totalPages: int
