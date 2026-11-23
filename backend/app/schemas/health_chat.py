"""Pydantic schemas for AI Symptom Guidance & Doctor Referral Chatbot."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CreateHealthChatSessionRequest(BaseModel):
    """Payload to initiate a new health chat session."""

    language: Optional[str] = Field(default="en", description="'en' or 'si'")
    consentGiven: bool = Field(
        default=True,
        description="Explicit user consent that AI provides informational guidance only.",
    )
    initialMessage: Optional[str] = Field(default=None, max_length=1000)


class SendHealthChatMessageRequest(BaseModel):
    """Payload to send a user message in an active session."""

    message: str = Field(..., min_length=1, max_length=1000, description="Patient message text")
    language: Optional[str] = Field(default=None, description="Optional language override ('en' | 'si')")


class DoctorReferralCardSchema(BaseModel):
    """Doctor profile card returned for routine or prompt care referrals."""

    doctorId: str
    fullName: str
    specialty: str
    qualifications: Optional[str] = None
    hospitalOrClinic: Optional[str] = None
    experienceYears: int = 0
    consultationFee: float
    rating: float = 0.0
    city: Optional[str] = None
    nextAvailableSlot: Optional[str] = None
    matchReason: Optional[str] = None


class HealthChatMessageResponse(BaseModel):
    """Response schema for a single chat turn."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    sender: str
    content: str
    timestamp: datetime
    triageLevel: Optional[str] = None
    isUrgent: bool = False
    emergencyNumber: Optional[str] = None
    disclaimer: Optional[str] = None
    clarifyingQuestions: List[str] = Field(default_factory=list)
    recommendedSpecialty: Optional[str] = None
    doctorReferrals: List[DoctorReferralCardSchema] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class HealthChatSessionResponse(BaseModel):
    """Comprehensive response for health chat session state."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    patientUserId: str
    language: str
    consentGiven: bool
    triageLevel: Optional[str] = None
    recommendedSpecialty: Optional[str] = None
    messages: List[HealthChatMessageResponse] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime
    expiresAt: datetime


class DeleteHealthChatSessionResponse(BaseModel):
    """Response returned upon session deletion."""

    success: bool
    message: str
