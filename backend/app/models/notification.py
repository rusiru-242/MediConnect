"""MongoDB document models and indexes for notifications and FCM device tokens."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class NotificationType(str, Enum):
    """Supported notification types in MediConnect."""

    BOOKING_CREATED = "BOOKING_CREATED"
    APPOINTMENT_CONFIRMED = "APPOINTMENT_CONFIRMED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    APPOINTMENT_COMPLETED = "APPOINTMENT_COMPLETED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    APPOINTMENT_REMINDER_24H = "APPOINTMENT_REMINDER_24H"
    APPOINTMENT_REMINDER_1H = "APPOINTMENT_REMINDER_1H"
    CONSULTATION_RECORD_AVAILABLE = "CONSULTATION_RECORD_AVAILABLE"
    PRESCRIPTION_ISSUED = "PRESCRIPTION_ISSUED"
    SYSTEM = "SYSTEM"


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class NotificationDocument(BaseModel):
    """MongoDB document representation for an in-app notification."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    recipientUserId: str = Field(..., description="References users._id of recipient")
    type: NotificationType = Field(default=NotificationType.SYSTEM)
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=1000)
    relatedAppointmentId: Optional[str] = Field(default=None, description="Optional references appointments._id")
    relatedPaymentId: Optional[str] = Field(default=None, description="Optional references payments._id")
    isRead: bool = Field(default=False)
    readAt: Optional[datetime] = Field(default=None)
    createdAt: datetime = Field(default_factory=utc_now)
    idempotencyKey: Optional[str] = Field(default=None, description="Unique key to prevent duplicate notifications")

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("createdAt", "readAt", mode="before")
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


class DeviceTokenDocument(BaseModel):
    """MongoDB document for FCM device token registration."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    userId: str = Field(..., description="References users._id")
    fcmToken: str = Field(..., min_length=1, description="Firebase device push token")
    deviceType: str = Field(default="android", description="android | ios | web | other")
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Serialize model for MongoDB insertion/update."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if "_id" in data and isinstance(data["_id"], str) and ObjectId.is_valid(data["_id"]):
            data["_id"] = ObjectId(data["_id"])
        return data


def get_notification_collection(db: Database) -> Collection:
    """Return the MongoDB 'notifications' collection."""
    return db["notifications"]


def get_device_token_collection(db: Database) -> Collection:
    """Return the MongoDB 'device_tokens' collection."""
    return db["device_tokens"]


def create_notification_indexes(db: Database) -> None:
    """Create indexes on notifications and device_tokens collections."""
    notif_col = get_notification_collection(db)
    device_col = get_device_token_collection(db)

    # 1. Notifications: Recipient feed ordered by creation desc
    notif_col.create_index(
        [("recipientUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_notifications_recipient_created",
    )

    # 2. Notifications: Recipient unread filter
    notif_col.create_index(
        [("recipientUserId", ASCENDING), ("isRead", ASCENDING)],
        name="idx_notifications_recipient_unread",
    )

    # 3. Notifications: Unique idempotency key (sparse/partial) to avoid duplicates
    notif_col.create_index(
        [("idempotencyKey", ASCENDING)],
        unique=True,
        partialFilterExpression={"idempotencyKey": {"$exists": True, "$type": "string"}},
        name="idx_notifications_idempotency_unique",
    )

    # 4. Device Tokens: Unique per user and FCM token
    device_col.create_index(
        [("userId", ASCENDING), ("fcmToken", ASCENDING)],
        unique=True,
        name="idx_device_tokens_user_fcm_unique",
    )

    # 5. Device Tokens: Global FCM token lookup (e.g. for stale token cleanup across users)
    device_col.create_index(
        [("fcmToken", ASCENDING)],
        name="idx_device_tokens_token",
    )

    # 6. Device Tokens: User lookup
    device_col.create_index(
        [("userId", ASCENDING)],
        name="idx_device_tokens_user",
    )
