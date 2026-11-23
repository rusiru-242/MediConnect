"""Pydantic schemas for Conversational AI Booking Assistant."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    requestedTime: Optional[str] = None
    maxFee: Optional[float] = None
    preferredGender: Optional[str] = None
    symptoms: Optional[str] = None
    sortBy: Optional[str] = None
    language: str = "en"
    patientNote: Optional[str] = None


class SlotCardSummary(BaseModel):
    """Available appointment slot presented to patient in conversational UI."""

    availabilityId: str
    date: str
    startTime: str
    endTime: str


class DoctorCardSummary(BaseModel):
    """Doctor card presented to patient in conversational UI."""

    doctorId: str
    doctorProfileId: str
    doctorUserId: str
    fullName: str
    specialty: str
    hospitalOrClinic: Optional[str] = None
    experienceYears: int = 0
    consultationFee: Optional[float] = None
    city: Optional[str] = None
    profileImage: Optional[str] = None
    rating: float = 0.0
    nextAvailableDate: Optional[str] = None
    matchReason: Optional[str] = None
    qualifications: Optional[str] = None
    matchScore: Optional[float] = None
    matchReasons: List[str] = Field(default_factory=list)
    requestedDate: Optional[str] = None
    requestedTime: Optional[str] = None
    availableSlots: List[SlotCardSummary] = Field(default_factory=list)


class MedicineCard(BaseModel):
    """Structured educational pharmacology details for a medication."""

    medicineName: str
    activeIngredient: Optional[str] = None
    commonUses: List[str] = Field(default_factory=list)
    precautions: List[str] = Field(default_factory=list)
    sideEffects: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    consultPharmacistWhen: Optional[Union[str, List[str]]] = None
    isPrescriptionRequired: Optional[bool] = None


class WellnessCard(BaseModel):
    """Structured nutrition, exercise, or lifestyle guidance card."""

    category: str = Field(..., description="'food' | 'exercise' | 'lifestyle'")
    title: str
    summary: str
    tips: List[str] = Field(default_factory=list)
    sriLankanOptions: List[str] = Field(default_factory=list)
    safetyNote: Optional[str] = None


class ImageAnalysisResult(BaseModel):
    """Outcome of vision interpretation of a medicine package or label."""

    detectedText: Optional[str] = None
    identifiedMedicine: Optional[str] = None
    activeIngredient: Optional[str] = None
    confidenceLevel: str = Field(default="moderate", description="'high' | 'moderate' | 'low' | 'unidentified'")
    uncertaintyExplanation: str
    safetyAdvice: str
    requiresClearerPhoto: bool = False


class BookingSummary(BaseModel):
    """Authoritative booking summary presented before explicit confirmation."""

    proposalId: Optional[str] = None
    proposalExpiresAt: Optional[datetime] = None
    timezone: Optional[str] = None
    city: Optional[str] = None
    patientName: Optional[str] = None
    maskedEmail: Optional[str] = None
    maskedPhone: Optional[str] = None
    requestedTime: Optional[str] = None
    selectionReason: Optional[str] = None
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


class AssistantResponse(BaseModel):
    assistant_message: str
    detected_intent: str
    conversation_id: Optional[str] = None
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    doctor_cards: List[DoctorCardSummary] = Field(default_factory=list)
    availability_slots: List[SlotCardSummary] = Field(default_factory=list)
    booking_state: Optional[str] = None
    requires_user_action: bool = False
    error_code: Optional[str] = None


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
    activeIntent: Optional[str] = None
    assistantResponse: Optional[AssistantResponse] = None
    bookingResult: Optional[Dict[str, Any]] = None
    activeMedicineCard: Optional[MedicineCard] = None
    activeWellnessCard: Optional[WellnessCard] = None
    activeImageAnalysis: Optional[ImageAnalysisResult] = None
    createdAt: datetime
    updatedAt: datetime
    expiresAt: Optional[datetime] = None


class CreateSessionRequest(BaseModel):
    """Request payload to initiate or resume an AI booking session."""

    initialMessage: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional initial user request (e.g. 'I need a cardiologist in Colombo')",
    )


class SendMessageRequest(BaseModel):
    """Request payload for sending a user message in an active booking session."""

    message: str = Field(..., min_length=1, max_length=2000, description="User conversational text")
    requestId: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{12,80}$")
    imageUrl: Optional[str] = Field(default=None, description="Optional image URL or uploaded path for label analysis")


class SelectDoctorRequest(BaseModel):
    """Explicit request payload to select a recommended doctor."""

    doctorId: str = Field(..., min_length=1, max_length=100, description="Doctor ID or profile ID of selected doctor")
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            date.fromisoformat(value)
        return value


class SelectSlotRequest(BaseModel):
    prepareProposal: bool = False
    """Explicit request payload to select an appointment slot."""

    availabilityId: str = Field(..., description="Doctor availability record ID")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Appointment date YYYY-MM-DD")
    startTime: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Slot start time HH:MM")
    endTime: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$", description="Slot end time HH:MM")


class ConfirmBookingRequest(BaseModel):
    """Explicit user request payload to confirm the appointment booking hold."""

    proposalId: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{24}$")
    smsConsent: bool = False
    patientNote: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional patient medical notes or symptoms to share with doctor",
    )
