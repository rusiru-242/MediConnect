"""MongoDB document model and indexes for AI Conversational Booking sessions."""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class BookingAgentState(str, Enum):
    """Explicit lifecycle states for the AI Booking Assistant agent."""

    COLLECTING_PREFERENCES = "COLLECTING_PREFERENCES"
    SEARCHING_DOCTORS = "SEARCHING_DOCTORS"
    AWAITING_DOCTOR_SELECTION = "AWAITING_DOCTOR_SELECTION"
    AWAITING_SLOT_SELECTION = "AWAITING_SLOT_SELECTION"
    AWAITING_BOOKING_CONFIRMATION = "AWAITING_BOOKING_CONFIRMATION"
    BOOKING_HOLD_CREATED = "BOOKING_HOLD_CREATED"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAYMENT_PENDING_VERIFICATION = "PAYMENT_PENDING_VERIFICATION"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    BOOKING_FAILED = "BOOKING_FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# Valid state transitions enforced by backend business logic
ALLOWED_STATE_TRANSITIONS: Dict[str, set] = {
    BookingAgentState.COLLECTING_PREFERENCES.value: {
        BookingAgentState.COLLECTING_PREFERENCES.value,
        BookingAgentState.SEARCHING_DOCTORS.value,
        BookingAgentState.AWAITING_DOCTOR_SELECTION.value,
        BookingAgentState.CANCELLED.value,
        BookingAgentState.EXPIRED.value,
    },
    BookingAgentState.SEARCHING_DOCTORS.value: {
        BookingAgentState.COLLECTING_PREFERENCES.value,
        BookingAgentState.SEARCHING_DOCTORS.value,
        BookingAgentState.AWAITING_DOCTOR_SELECTION.value,
        BookingAgentState.CANCELLED.value,
        BookingAgentState.EXPIRED.value,
    },
    BookingAgentState.AWAITING_DOCTOR_SELECTION.value: {
        BookingAgentState.COLLECTING_PREFERENCES.value,
        BookingAgentState.SEARCHING_DOCTORS.value,
        BookingAgentState.AWAITING_DOCTOR_SELECTION.value,
        BookingAgentState.AWAITING_SLOT_SELECTION.value,
        BookingAgentState.CANCELLED.value,
        BookingAgentState.EXPIRED.value,
    },
    BookingAgentState.AWAITING_SLOT_SELECTION.value: {
        BookingAgentState.COLLECTING_PREFERENCES.value,
        BookingAgentState.AWAITING_DOCTOR_SELECTION.value,
        BookingAgentState.AWAITING_SLOT_SELECTION.value,
        BookingAgentState.AWAITING_BOOKING_CONFIRMATION.value,
        BookingAgentState.CANCELLED.value,
        BookingAgentState.EXPIRED.value,
    },
    BookingAgentState.AWAITING_BOOKING_CONFIRMATION.value: {
        BookingAgentState.AWAITING_SLOT_SELECTION.value,
        BookingAgentState.BOOKING_HOLD_CREATED.value,
        BookingAgentState.AWAITING_PAYMENT.value,
        BookingAgentState.BOOKING_FAILED.value,
        BookingAgentState.CANCELLED.value,
        BookingAgentState.EXPIRED.value,
    },
    BookingAgentState.BOOKING_HOLD_CREATED.value: {
        BookingAgentState.AWAITING_PAYMENT.value,
        BookingAgentState.PAYMENT_PENDING_VERIFICATION.value,
        BookingAgentState.BOOKING_CONFIRMED.value,
        BookingAgentState.BOOKING_FAILED.value,
        BookingAgentState.CANCELLED.value,
        BookingAgentState.EXPIRED.value,
    },
    BookingAgentState.AWAITING_PAYMENT.value: {
        BookingAgentState.PAYMENT_PENDING_VERIFICATION.value,
        BookingAgentState.BOOKING_CONFIRMED.value,
        BookingAgentState.BOOKING_FAILED.value,
        BookingAgentState.CANCELLED.value,
        BookingAgentState.EXPIRED.value,
    },
    BookingAgentState.PAYMENT_PENDING_VERIFICATION.value: {
        BookingAgentState.BOOKING_CONFIRMED.value,
        BookingAgentState.AWAITING_PAYMENT.value,
        BookingAgentState.BOOKING_FAILED.value,
        BookingAgentState.CANCELLED.value,
        BookingAgentState.EXPIRED.value,
    },
    BookingAgentState.BOOKING_CONFIRMED.value: set(),  # Terminal state
    BookingAgentState.BOOKING_FAILED.value: {
        BookingAgentState.COLLECTING_PREFERENCES.value,
        BookingAgentState.SEARCHING_DOCTORS.value,
        BookingAgentState.AWAITING_DOCTOR_SELECTION.value,
        BookingAgentState.AWAITING_SLOT_SELECTION.value,
        BookingAgentState.CANCELLED.value,
        BookingAgentState.EXPIRED.value,
    },
    BookingAgentState.CANCELLED.value: set(),  # Terminal state
    BookingAgentState.EXPIRED.value: set(),    # Terminal state
}


class ChatMessageDocument(BaseModel):
    """Individual message in conversation history."""

    id: str = Field(default_factory=lambda: str(ObjectId()))
    sender: str = Field(..., description="'user' | 'assistant' | 'system'")
    content: str
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: Optional[Dict[str, Any]] = None


class BookingSessionDocument(BaseModel):
    """MongoDB document representation for a conversational AI Booking session."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    patientUserId: str = Field(..., description="References users._id (patient)")
    state: BookingAgentState = Field(default=BookingAgentState.COLLECTING_PREFERENCES)

    # Structured booking preferences accumulated across turns
    preferences: Dict[str, Any] = Field(
        default_factory=lambda: {
            "specialty": None,
            "city": None,
            "date": None,
            "timeRange": None,
            "maxFee": None,
            "language": "en",
            "patientNote": None,
        }
    )

    # Active selections
    selectedDoctor: Optional[Dict[str, Any]] = None
    selectedSlot: Optional[Dict[str, Any]] = None
    bookingSummary: Optional[Dict[str, Any]] = None

    # Cached candidates for quick user selection
    candidateDoctors: List[Dict[str, Any]] = Field(default_factory=list)
    candidateSlots: List[Dict[str, Any]] = Field(default_factory=list)

    # Associated appointment and payment records
    appointmentId: Optional[str] = None
    paymentId: Optional[str] = None
    holdExpiresAt: Optional[datetime] = None

    # Conversational transcript
    messages: List[ChatMessageDocument] = Field(default_factory=list)

    # Emergency and safety flags
    isUrgent: bool = Field(default=False)
    urgencyReason: Optional[str] = None

    # Timestamps (UTC)
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)
    expiresAt: datetime = Field(default_factory=lambda: utc_now() + timedelta(minutes=30))

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("createdAt", "updatedAt", "expiresAt", "holdExpiresAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Serialize model for MongoDB insertion/update."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if "_id" in data and isinstance(data["_id"], str) and ObjectId.is_valid(data["_id"]):
            data["_id"] = ObjectId(data["_id"])
        return data


def get_booking_session_collection(db: Database) -> Collection:
    """Return the MongoDB 'booking_sessions' collection."""
    return db["booking_sessions"]


def create_booking_session_indexes(db: Database) -> None:
    """Create indexes on booking_sessions collection."""
    collection = get_booking_session_collection(db)
    collection.create_index(
        [("patientUserId", ASCENDING), ("state", ASCENDING)],
        name="idx_booking_sess_patient_state",
    )
    collection.create_index(
        [("patientUserId", ASCENDING), ("updatedAt", DESCENDING)],
        name="idx_booking_sess_patient_updated",
    )
    collection.create_index(
        [("expiresAt", ASCENDING)],
        expireAfterSeconds=0,
        name="idx_booking_sess_ttl",
    )
