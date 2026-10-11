"""Notification endpoints for in-app alerts and FCM device registration."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user
from app.schemas.notification import (
    NotificationActionResponse,
    NotificationListResponse,
    RegisterDeviceTokenRequest,
    RemoveDeviceTokenRequest,
    UnreadCountResponse,
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


@router.patch(
    "/{id}/read",
    response_model=NotificationActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read",
    description="Marks a specific notification as read. Enforces user ownership.",
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
