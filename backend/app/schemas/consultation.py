"""Pydantic schemas for Doctor Daily Schedule and Consultation Management (Phase 57)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConsultationSessionResponse(BaseModel):
    """Public representation of an active or completed consultation session."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    appointmentId: str
    doctorUserId: str
    doctorProfileId: str
    patientUserId: str
    status: str = Field(..., description="NOT_STARTED | IN_PROGRESS | COMPLETED")
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    startedBy: Optional[str] = None
    completedBy: Optional[str] = None
    notes: Optional[str] = None
    version: int = 1
    createdAt: datetime
    updatedAt: datetime


class DailyScheduleStats(BaseModel):
    """Daily appointment and consultation metrics for the doctor dashboard."""

    model_config = ConfigDict(populate_by_name=True)

    date: str
    timezone: str = "Asia/Colombo"
    totalScheduled: int = 0
    upcoming: int = 0
    waiting: int = 0
    inProgress: int = 0
    completed: int = 0
    cancelled: int = 0


class ScheduleAppointmentItem(BaseModel):
    """An appointment in the doctor's daily schedule enriched with consultation state."""

    model_config = ConfigDict(populate_by_name=True)

    appointmentId: str
    appointmentDate: str
    startTime: str
    endTime: str
    bookingStatus: str = Field(..., description="PENDING | CONFIRMED | COMPLETED | CANCELLED")
    consultationStatus: str = Field(default="NOT_STARTED", description="NOT_STARTED | IN_PROGRESS | COMPLETED")
    consultationFee: float = 2500.0

    patientUserId: str
    patientName: str
    patientEmail: Optional[str] = None
    patientPhone: Optional[str] = None
    patientNote: Optional[str] = None

    consultationSessionId: Optional[str] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None

    # Clinical linkage indicators
    hasPrescription: bool = False
    hasMedicalRecord: bool = False
    hasCarePlan: bool = False

    prescriptionId: Optional[str] = None
    medicalRecordId: Optional[str] = None
    carePlanId: Optional[str] = None


class DoctorDailyScheduleResponse(BaseModel):
    """Comprehensive daily schedule payload for doctor."""

    model_config = ConfigDict(populate_by_name=True)

    date: str
    timezone: str
    stats: DailyScheduleStats
    nextPatient: Optional[ScheduleAppointmentItem] = None
    appointments: List[ScheduleAppointmentItem] = []


class StartConsultationRequest(BaseModel):
    """Optional payload when initiating a consultation."""

    notes: Optional[str] = Field(None, max_length=1000, description="Optional opening notes")


class CompleteConsultationRequest(BaseModel):
    """Optional payload when concluding a consultation."""

    notes: Optional[str] = Field(None, max_length=2000, description="Optional conclusion notes")


class ConsultationDetailResponse(BaseModel):
    """Full view for consultation management screen."""

    model_config = ConfigDict(populate_by_name=True)

    appointment: ScheduleAppointmentItem
    session: Optional[ConsultationSessionResponse] = None
    medicalRecord: Optional[Dict[str, Any]] = None
    prescription: Optional[Dict[str, Any]] = None
    carePlan: Optional[Dict[str, Any]] = None
