"""Pydantic schemas for Conversational AI Booking Assistant."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ChatMessageSchema(BaseModel):
    """Chat message schema for response payloads."""

    id: str
    sender: str = Field(..., description="'user' | 'assistant' | 'system'")
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class BookingPreferencesSchema(BaseModel):
    """Accumulated structured preferences for doctor appointment booking."""

    specialty: Optional[str] = None
    city: Optional[str] = None
    date: Optional[str] = None
    timeRange: Optional[str] = None
    maxFee: Optional[float] = None
    language: str = "en"
    patientNote: Optional[str] = None


class DoctorCardSummary(BaseModel):
    """Doctor card presented to patient in conversational UI."""

    doctorId: str
    doctorProfileId: str
    doctorUserId: str
    fullName: str
    specialty: str
    hospitalOrClinic: Optional[str] = None
    experienceYears: int = 0
    consultationFee: float
    rating: float = 0.0
    nextAvailableDate: Optional[str] = None
    matchReason: Optional[str] = None


class SlotCardSummary(BaseModel):
    """Available appointment slot presented to patient in conversational UI."""

    availabilityId: str
    date: str
    startTime: str
    endTime: str


class BookingSummary(BaseModel):
    """Authoritative booking summary presented before explicit confirmation."""

    doctorName: str
    specialty: str
    hospitalOrClinic: Optional[str] = None
    appointmentDate: str
    startTime: str
    endTime: str
    consultationFee: float
    serviceFee: float = 0.0
    totalAmount: float
    currency: str = "lkr"


class BookingSessionResponse(BaseModel):
    """Comprehensive response object for a booking session."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    patientUserId: str
    state: str
    preferences: BookingPreferencesSchema
    selectedDoctor: Optional[DoctorCardSummary] = None
    selectedSlot: Optional[SlotCardSummary] = None
    bookingSummary: Optional[BookingSummary] = None
    candidateDoctors: List[DoctorCardSummary] = Field(default_factory=list)
    candidateSlots: List[SlotCardSummary] = Field(default_factory=list)
    appointmentId: Optional[str] = None
    paymentId: Optional[str] = None
    holdExpiresAt: Optional[datetime] = None
    messages: List[ChatMessageSchema] = Field(default_factory=list)
    isUrgent: bool = False
    urgencyReason: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    expiresAt: datetime


class CreateSessionRequest(BaseModel):
    """Request payload to initiate or resume an AI booking session."""

    initialMessage: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional initial user request (e.g. 'I need a cardiologist in Colombo')",
    )


class SendMessageRequest(BaseModel):
    """Request payload for sending a user message in an active booking session."""

    message: str = Field(..., min_length=1, max_length=1000, description="User conversational text")


class SelectDoctorRequest(BaseModel):
    """Explicit request payload to select a recommended doctor."""

    doctorId: str = Field(..., description="Doctor ID or profile ID of selected doctor")


class SelectSlotRequest(BaseModel):
    """Explicit request payload to select an appointment slot."""

    availabilityId: str = Field(..., description="Doctor availability record ID")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Appointment date YYYY-MM-DD")
    startTime: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Slot start time HH:MM")
    endTime: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$", description="Slot end time HH:MM")


class ConfirmBookingRequest(BaseModel):
    """Explicit user request payload to confirm the appointment booking hold."""

    patientNote: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional patient medical notes or symptoms to share with doctor",
    )
