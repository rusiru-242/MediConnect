"""Schemas for AI Doctor Recommendation Agent requests and responses."""

from typing import List, Optional
from pydantic import BaseModel, Field


class DoctorRecommendationRequest(BaseModel):
    """Input payload for AI doctor discovery request."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural-language patient request in English or Sinhala",
        examples=["I have a persistent chest pain and need a cardiologist in Colombo tomorrow under 3500 LKR"],
    )
    specialty: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional explicit specialty filter overriding/supplementing query",
    )
    city: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional explicit city/area filter overriding/supplementing query",
    )
    date: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Optional explicit date filter in YYYY-MM-DD format",
    )
    timeRange: Optional[str] = Field(
        default=None,
        max_length=30,
        description="Optional explicit time range: 'morning', 'afternoon', 'evening'",
    )
    maxFee: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Optional maximum consultation fee filter in LKR",
    )
    consultationType: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Optional consultation type (e.g. in-person, clinic)",
    )


class InterpretedPreferences(BaseModel):
    """Structured preferences extracted from natural-language request and explicit filters."""

    specialty: Optional[str] = None
    city: Optional[str] = None
    date: Optional[str] = None
    timeRange: Optional[str] = None
    maxFee: Optional[float] = None
    consultationType: Optional[str] = None
    languageDetected: Optional[str] = "en"


class RecommendedSlotItem(BaseModel):
    """Individual available appointment slot for a recommended doctor."""

    date: str
    startTime: str
    endTime: str
    availabilityId: Optional[str] = None


class DoctorRecommendationItem(BaseModel):
    """Ranked recommended doctor item with transparent match reasons and verified slots."""

    doctorId: str
    fullName: str
    specialty: str
    hospitalOrClinic: str
    experienceYears: int
    consultationFee: float
    bio: Optional[str] = None
    profileImage: Optional[str] = None
    score: float = Field(..., ge=0.0, le=100.0, description="Deterministically calculated match score 0-100")
    matchReasons: List[str] = Field(default_factory=list, description="Explanations for why this doctor matches")
    availableSlots: List[RecommendedSlotItem] = Field(
        default_factory=list,
        description="Real available slots for immediate appointment booking",
    )


class DoctorRecommendationResponse(BaseModel):
    """Full response returned by the AI recommendation endpoint."""

    interpretedPreferences: InterpretedPreferences
    recommendations: List[DoctorRecommendationItem]
    totalMatches: int
    isUrgent: bool = Field(
        default=False,
        description="True if patient query indicates potentially urgent or emergency medical condition",
    )
    safetyGuidance: Optional[str] = Field(
        default=None,
        description="Safety advice and emergency guidance when urgent symptoms are identified",
    )
    disclaimer: str = Field(
        default=(
            "MediConnect Doctor Discovery Assistant is an informational matching tool, not a diagnostic or "
            "prescribing system. No doctor-patient relationship is created by this recommendation. In the event "
            "of a medical emergency, please call 1990 immediately or visit the nearest emergency facility."
        ),
        description="Standard medical disclaimer",
    )
    clarificationQuestion: Optional[str] = Field(
        default=None,
        description="Clarification prompt when user query lacks sufficient criteria for specific matching",
    )
    aiProviderUsed: str = Field(
        default="deterministic_fallback",
        description="AI or rule-based parser used ('gemini', 'openai', or 'deterministic_fallback')",
    )
