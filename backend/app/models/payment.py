"""MongoDB document model and indexes for payments."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class PaymentDocument(BaseModel):
    """MongoDB document representation for a payment transaction."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    appointmentId: str = Field(..., description="References appointments._id")
    patientUserId: str = Field(..., description="References users._id (patient)")
    doctorUserId: str = Field(..., description="References users._id (doctor)")
    stripePaymentIntentId: str = Field(..., description="Stripe PaymentIntent ID")
    amount: float = Field(..., description="Payment amount in decimal currency (e.g. 2500.0)")
    currency: str = Field(default="lkr", description="ISO currency code in lowercase (e.g. 'lkr')")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)
    paidAt: Optional[datetime] = Field(default=None)
    failureReason: Optional[str] = Field(default=None)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("createdAt", "updatedAt", "paidAt", mode="before")
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


def get_payment_collection(db: Database) -> Collection:
    """Return the MongoDB 'payments' collection."""
    return db["payments"]


def create_payment_indexes(db: Database) -> None:
    """Create indexes on payments collection."""
    collection = get_payment_collection(db)

    # Patient payment history lookup
    collection.create_index(
        [("patientUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_payments_patient_created",
    )

    # Appointment linkage
    collection.create_index(
        [("appointmentId", ASCENDING)],
        name="idx_payments_appointment_id",
    )

    # Unique lookup per Stripe PaymentIntent
    collection.create_index(
        [("stripePaymentIntentId", ASCENDING)],
        unique=True,
        name="idx_payments_stripe_pi_unique",
    )
