"""Notification endpoints for in-app alerts and FCM device registration."""

from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, require_admin
from app.schemas.notification import (
    NotificationActionResponse,
    NotificationListResponse,
    NotificationPreferencesSchema,
    RegisterDeviceTokenRequest,
    RemoveDeviceTokenRequest,
    UnreadCountResponse,
    UpdateNotificationPreferencesRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List notifications",
    description="Returns a paginated list of notifications for the authenticated user.",
)
async def list_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> NotificationListResponse:
    """Retrieve notifications for the current authenticated user."""
    return NotificationService.list_notifications(
        db=db,
        user_id=str(current_user.id),
        page=page,
        limit=limit,
        unread_only=unread_only,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get unread notification count",
    description="Returns the total number of unread notifications for the authenticated user.",
)
async def get_unread_count(
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> UnreadCountResponse:
    """Get the unread notification badge count."""
    count = NotificationService.get_unread_count(db=db, user_id=str(current_user.id))
    return UnreadCountResponse(unreadCount=count)


@router.get(
    "/preferences",
    response_model=NotificationPreferencesSchema,
    status_code=status.HTTP_200_OK,
    summary="Get notification preferences",
    description="Returns notification preferences for the authenticated user.",
)
async def get_preferences(
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> NotificationPreferencesSchema:
    """Retrieve notification preferences."""
    return NotificationService.get_preferences(db=db, user_id=str(current_user.id))


@router.put(
    "/preferences",
    response_model=NotificationPreferencesSchema,
    status_code=status.HTTP_200_OK,
    summary="Update notification preferences",
    description="Updates notification preferences for the authenticated user.",
)
async def update_preferences(
    req: UpdateNotificationPreferencesRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> NotificationPreferencesSchema:
    """Update notification preferences."""
    return NotificationService.update_preferences(db=db, user_id=str(current_user.id), req=req)


@router.patch(
    "/{id}/read",
    response_model=NotificationActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read",
    description="Marks a specific notification as read. Enforces user ownership.",
)
@router.put(
    "/{id}/read",
    response_model=NotificationActionResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def mark_as_read(
    id: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> NotificationActionResponse:
    """Mark a notification as read."""
    return NotificationService.mark_as_read(
        db=db,
        notification_id=id,
        user_id=str(current_user.id),
    )


@router.patch(
    "/read-all",
    response_model=NotificationActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Marks all unread notifications for the authenticated user as read.",
)
@router.put(
    "/read-all",
    response_model=NotificationActionResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def mark_all_as_read(
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> NotificationActionResponse:
    """Mark all unread notifications as read."""
    return NotificationService.mark_all_as_read(
        db=db,
        user_id=str(current_user.id),
    )


@router.post(
    "/devices",
    response_model=NotificationActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Register device push token",
    description="Registers or updates the FCM token associated with the authenticated user.",
)
async def register_device(
    req: RegisterDeviceTokenRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> NotificationActionResponse:
    """Register or refresh FCM device token."""
    return NotificationService.register_device_token(
        db=db,
        user_id=str(current_user.id),
        fcm_token=req.fcmToken,
        device_type=req.deviceType,
    )


@router.delete(
    "/devices",
    response_model=NotificationActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove device push token",
    description="Removes the specified FCM token upon logout to stop receiving push notifications.",
)
async def remove_device(
    req: RemoveDeviceTokenRequest,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> NotificationActionResponse:
    """Remove FCM device token on logout."""
    return NotificationService.remove_device_token(
        db=db,
        user_id=str(current_user.id),
        fcm_token=req.fcmToken,
    )

@router.post("/booking-confirmations/{appointment_id}/{channel}/retry")
def retry_booking_confirmation(
    appointment_id: str,
    channel: Literal["email", "sms", "doctor"],
    admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    from bson import ObjectId
    from app.models.appointment import utc_now

    if not ObjectId.is_valid(appointment_id):
        raise HTTPException(404, "Failed confirmation job not found.")
    path = f"confirmationOutbox.{channel}"
    result = db["appointments"].update_one(
        {"_id": ObjectId(appointment_id), "confirmedAt": {"$exists": True}, f"{path}.status": "failed"},
        {"$set": {f"{path}.status": "pending", f"{path}.nextAttemptAt": utc_now(),
                  f"{path}.attempts": 0, f"{path}.retriedBy": str(admin.id)},
         "$unset": {f"{path}.providerId": "", f"{path}.reason": ""}},
    )
    if not result.modified_count:
        raise HTTPException(404, "Failed confirmation job not found.")
    return {"status": "pending"}
