"""Pydantic schemas for notifications and FCM device tokens."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    """Notification item returned to the client."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    recipientUserId: str
    type: str
    title: str
    body: str
    relatedAppointmentId: Optional[str] = None
    relatedPaymentId: Optional[str] = None
    isRead: bool = False
    readAt: Optional[datetime] = None
    createdAt: datetime


class NotificationListResponse(BaseModel):
    """Paginated response containing notifications and unread summary."""

    items: List[NotificationResponse]
    total: int
    page: int
    limit: int
    totalPages: int
    unreadCount: int


class UnreadCountResponse(BaseModel):
    """Response containing total unread notifications count."""

    unreadCount: int


class RegisterDeviceTokenRequest(BaseModel):
    """Request payload to register or refresh an FCM device push token."""

    fcmToken: str = Field(..., min_length=1, description="FCM registration token")
    deviceType: Optional[str] = Field(default="android", description="android | ios | web")


class RemoveDeviceTokenRequest(BaseModel):
    """Request payload to remove an FCM device token upon logout."""

    fcmToken: str = Field(..., min_length=1, description="FCM registration token to remove")


class NotificationActionResponse(BaseModel):
    """Generic status response for notification mutations."""

    success: bool = True
    message: str
    modifiedCount: int = 0
