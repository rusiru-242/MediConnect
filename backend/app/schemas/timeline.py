"""Pydantic schemas for Patient Healthcare Timeline & Visit History (Phase 58)."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TimelineCategory(str, Enum):
    """Event category filters for the healthcare timeline."""

    ALL = "ALL"
    APPOINTMENTS = "APPOINTMENTS"
    CONSULTATIONS = "CONSULTATIONS"
    PRESCRIPTIONS = "PRESCRIPTIONS"
    MEDICAL_RECORDS = "MEDICAL_RECORDS"
    FOLLOW_UPS = "FOLLOW_UPS"


class TimelineEventType(str, Enum):
    """Discrete verified clinical and visit events."""

    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    APPOINTMENT_COMPLETED = "APPOINTMENT_COMPLETED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    APPOINTMENT_RESCHEDULED = "APPOINTMENT_RESCHEDULED"
    CONSULTATION_COMPLETED = "CONSULTATION_COMPLETED"
    PRESCRIPTION_ISSUED = "PRESCRIPTION_ISSUED"
    MEDICAL_RECORD_ADDED = "MEDICAL_RECORD_ADDED"
    FOLLOW_UP_PLAN_CREATED = "FOLLOW_UP_PLAN_CREATED"
    FOLLOW_UP_BOOKED = "FOLLOW_UP_BOOKED"


class TimelineAction(str, Enum):
    """Patient-authorized action targets available from timeline cards."""

    VIEW_APPOINTMENT = "VIEW_APPOINTMENT"
    VIEW_VISIT = "VIEW_VISIT"
    VIEW_PRESCRIPTION = "VIEW_PRESCRIPTION"
    VIEW_MEDICAL_RECORD = "VIEW_MEDICAL_RECORD"
    VIEW_CARE_PLAN = "VIEW_CARE_PLAN"


class TimelineEvent(BaseModel):
    """A normalized, patient-safe timeline event item."""

    model_config = ConfigDict(populate_by_name=True)

    eventId: str = Field(..., description="Stable unique ID e.g. appt_6af..._booked")
    eventType: str = Field(..., description="APPOINTMENT_BOOKED, CONSULTATION_COMPLETED, etc.")
    category: str = Field(..., description="APPOINTMENTS, CONSULTATIONS, PRESCRIPTIONS, etc.")
    occurredAt: datetime = Field(..., description="UTC ISO timestamp of event occurrence")
    displayDate: str = Field(..., description="Human readable date e.g. 2026-11-13")
    displayTime: Optional[str] = Field(None, description="Human readable time e.g. 09:30")
    title: str = Field(..., description="Event title")
    description: str = Field(..., description="Patient-safe description (no confidential doctor notes)")

    doctorUserId: Optional[str] = None
    doctorDisplayName: Optional[str] = None
    doctorSpecialty: Optional[str] = None
    hospitalOrClinic: Optional[str] = None

    sourceType: str = Field(..., description="appointment | consultation | prescription | medical_record | care_plan")
    sourceId: str = Field(..., description="Underlying collection document ID")
    appointmentId: Optional[str] = None
    status: Optional[str] = None
    availableActions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    """Paginated timeline payload for patient view."""

    model_config = ConfigDict(populate_by_name=True)

    events: List[TimelineEvent] = []
    nextCursor: Optional[str] = None
    totalCount: int = 0
    hasMore: bool = False


class TimelineSummaryResponse(BaseModel):
    """High-level metrics summary for the patient healthcare dashboard."""

    model_config = ConfigDict(populate_by_name=True)

    totalEvents: int = 0
    upcomingAppointmentsCount: int = 0
    completedConsultationsCount: int = 0
    prescriptionsCount: int = 0
    medicalRecordsCount: int = 0
    activeCarePlansCount: int = 0


class VisitDetailResponse(BaseModel):
    """Consolidated visit overview integrating appointment, consultation, prescription, record, and follow-up."""

    model_config = ConfigDict(populate_by_name=True)

    appointmentId: str
    appointmentNumber: Optional[str] = None
    appointmentDate: str
    startTime: str
    endTime: str
    bookingStatus: str
    consultationStatus: str
    consultationFee: float = 2500.0

    doctorUserId: str
    doctorName: str
    doctorSpecialty: Optional[str] = None
    doctorHospital: Optional[str] = None

    patientNote: Optional[str] = None
    cancelledBy: Optional[str] = None
    cancellationReason: Optional[str] = None

    consultationSession: Optional[Dict[str, Any]] = None
    prescription: Optional[Dict[str, Any]] = None
    medicalRecord: Optional[Dict[str, Any]] = None
    carePlan: Optional[Dict[str, Any]] = None
    timelineEvents: List[TimelineEvent] = []

