"""Notification service: in-app notifications, FCM push messaging, and scheduled reminders."""

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.config.settings import settings
from app.models.appointment import AppointmentStatus, utc_now
from app.models.notification import (
    DeviceTokenDocument,
    NotificationDocument,
    NotificationType,
    get_device_token_collection,
    get_notification_collection,
)
from app.schemas.notification import (
    NotificationActionResponse,
    NotificationListResponse,
    NotificationResponse,
)

logger = logging.getLogger(__name__)

# Sri Lanka Standard Time (Asia/Colombo = UTC+05:30)
SL_TIMEZONE = timezone(timedelta(hours=5, minutes=30))

# Firebase Admin SDK globals
_firebase_app = None
_firebase_initialized = False


def _init_firebase() -> bool:
    """Initialize Firebase Admin SDK once if credentials exist."""
    global _firebase_app, _firebase_initialized
    if _firebase_initialized:
        return _firebase_app is not None

    _firebase_initialized = True
    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check existing default app
        if firebase_admin._apps:
            _firebase_app = firebase_admin.get_app()
            logger.info("Using already-initialized Firebase app.")
            return True

        cred = None
        # 1. Path to service account file
        if settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
            logger.info("Initializing Firebase Admin SDK with credentials file: %s", settings.FIREBASE_CREDENTIALS_PATH)
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        # 2. Raw JSON string from environment variable
        elif settings.FIREBASE_SERVICE_ACCOUNT_JSON and settings.FIREBASE_SERVICE_ACCOUNT_JSON.strip():
            logger.info("Initializing Firebase Admin SDK with inline service account JSON.")
            cert_data = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
            cred = credentials.Certificate(cert_data)

        if cred:
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized successfully.")
            return True
        else:
            logger.info(
                "No Firebase credentials configured (FIREBASE_CREDENTIALS_PATH or "
                "FIREBASE_SERVICE_ACCOUNT_JSON). Push notifications will be recorded in-app only."
            )
            return False
    except Exception as exc:
        logger.warning("Failed to initialize Firebase Admin SDK: %s", exc)
        _firebase_app = None
        return False


def _doc_to_response(doc: Dict[str, Any]) -> NotificationResponse:
    """Format raw notification MongoDB document into NotificationResponse schema."""
    created_at = doc.get("createdAt")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    read_at = doc.get("readAt")
    if isinstance(read_at, datetime) and read_at.tzinfo is None:
        read_at = read_at.replace(tzinfo=timezone.utc)

    return NotificationResponse(
        id=str(doc["_id"]),
        recipientUserId=str(doc["recipientUserId"]),
        type=doc.get("type", NotificationType.SYSTEM.value),
        title=doc.get("title", ""),
        body=doc.get("body", ""),
        relatedAppointmentId=str(doc["relatedAppointmentId"]) if doc.get("relatedAppointmentId") else None,
        relatedPaymentId=str(doc["relatedPaymentId"]) if doc.get("relatedPaymentId") else None,
        isRead=bool(doc.get("isRead", False)),
        readAt=read_at,
        createdAt=created_at or utc_now(),
    )


class NotificationService:
    """Core notification management: persistence, push delivery, and appointment reminders."""

    # -------------------------------------------------------------------------
    # 1. FCM Device Token Registration
    # -------------------------------------------------------------------------
    @staticmethod
    def register_device_token(
        db: Database,
        user_id: str,
        fcm_token: str,
        device_type: Optional[str] = "android",
    ) -> NotificationActionResponse:
        """Register or update an FCM token for a user (supports multiple devices)."""
        token = fcm_token.strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FCM token cannot be empty.",
            )

        col = get_device_token_collection(db)
        now = utc_now()

        # Disassociate this physical device token from any other user to prevent cross-account notification leakage
        col.delete_many({"fcmToken": token, "userId": {"$ne": str(user_id)}})

        # Upsert token for this user
        col.update_one(
            {"userId": str(user_id), "fcmToken": token},
            {
                "$set": {
                    "deviceType": (device_type or "android").lower(),
                    "updatedAt": now,
                },
                "$setOnInsert": {
                    "createdAt": now,
                },
            },
            upsert=True,
        )
        return NotificationActionResponse(
            success=True,
            message="Device token registered successfully.",
            modifiedCount=1,
        )

    @staticmethod
    def remove_device_token(
        db: Database,
        user_id: str,
        fcm_token: str,
    ) -> NotificationActionResponse:
        """Remove a device token upon logout."""
        token = fcm_token.strip()
        col = get_device_token_collection(db)
        res = col.delete_one({"userId": str(user_id), "fcmToken": token})
        return NotificationActionResponse(
            success=True,
            message="Device token removed successfully." if res.deleted_count > 0 else "Device token not found.",
            modifiedCount=res.deleted_count,
        )

    @staticmethod
    def clean_stale_token(db: Database, fcm_token: str) -> None:
        """Remove invalid or unregistered device token across all records."""
        try:
            col = get_device_token_collection(db)
            col.delete_many({"fcmToken": fcm_token})
            logger.info("Removed stale FCM token: %s...", fcm_token[:10])
        except Exception as exc:
            logger.warning("Failed to remove stale FCM token: %s", exc)

    # -------------------------------------------------------------------------
    # 2. Push Dispatcher via Firebase Admin SDK
    # -------------------------------------------------------------------------
    @classmethod
    def _send_fcm_push(
        cls,
        db: Database,
        recipient_user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> None:
        """Send push notification to all active devices registered for user."""
        try:
            if not _init_firebase():
                return

            from firebase_admin import messaging

            col = get_device_token_collection(db)
            tokens_cursor = col.find({"userId": str(recipient_user_id)}, {"fcmToken": 1})
            tokens = [doc["fcmToken"] for doc in tokens_cursor if doc.get("fcmToken")]

            if not tokens:
                logger.debug("No registered FCM tokens found for user %s", recipient_user_id)
                return

            # Clean payload: FCM data values must all be strings
            payload_data = {}
            if data:
                for k, v in data.items():
                    if v is not None:
                        payload_data[str(k)] = str(v)

            # Build multicast message
            message = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=payload_data,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        channel_id="mediconnect_general",
                    ),
                ),
            )

            response = messaging.send_each_for_multicast(message)
            logger.info(
                "FCM multicast sent for user %s: %d success, %d failure",
                recipient_user_id,
                response.success_count,
                response.failure_count,
            )

            # Clean up invalid/unregistered tokens
            if response.failure_count > 0:
                for idx, item in enumerate(response.responses):
                    if not item.success and item.exception:
                        err_code = getattr(item.exception, "code", "") or str(item.exception)
                        # Detect unregistered/invalid token
                        if (
                            "registration-token-not-registered" in err_code.lower()
                            or "invalid-argument" in err_code.lower()
                            or "notregistered" in err_code.lower()
                        ):
                            bad_token = tokens[idx]
                            cls.clean_stale_token(db, bad_token)
        except Exception as exc:
            # Critical requirement: Push notification failure must never crash or bubble up
            logger.error("Error dispatching FCM push notification to user %s: %s", recipient_user_id, exc)

    # -------------------------------------------------------------------------
    # 3. Notification Creation (In-App + FCM Push)
    # -------------------------------------------------------------------------
    @classmethod
    def create_notification(
        cls,
        db: Database,
        recipient_user_id: str,
        type: NotificationType,
        title: str,
        body: str,
        related_appointment_id: Optional[str] = None,
        related_payment_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        send_push: bool = True,
    ) -> Optional[NotificationResponse]:
        """Persist an in-app notification in MongoDB and trigger FCM push safely.

        Idempotent: If idempotency_key is provided and already exists, duplicate
        creation and push delivery are skipped cleanly.
        """
        try:
            notif_col = get_notification_collection(db)

            # Idempotency check
            if idempotency_key:
                existing = notif_col.find_one({"idempotencyKey": idempotency_key})
                if existing:
                    logger.debug("Notification with idempotencyKey %s already exists. Skipping duplicate.", idempotency_key)
                    return _doc_to_response(existing)

            now = utc_now()
            doc_data = {
                "recipientUserId": str(recipient_user_id),
                "type": type.value if isinstance(type, NotificationType) else str(type),
                "title": title,
                "body": body,
                "relatedAppointmentId": str(related_appointment_id) if related_appointment_id else None,
                "relatedPaymentId": str(related_payment_id) if related_payment_id else None,
                "isRead": False,
                "readAt": None,
                "createdAt": now,
            }
            if idempotency_key:
                doc_data["idempotencyKey"] = idempotency_key

            try:
                res = notif_col.insert_one(doc_data)
                doc_data["_id"] = res.inserted_id
            except DuplicateKeyError:
                # Concurrent insertion with same idempotency key
                if idempotency_key:
                    existing = notif_col.find_one({"idempotencyKey": idempotency_key})
                    if existing:
                        return _doc_to_response(existing)
                return None

            # Dispatch push notification safely without risking in-app creation
            if send_push:
                try:
                    push_data = {
                        "notificationId": str(doc_data["_id"]),
                        "type": doc_data["type"],
                        "relatedAppointmentId": doc_data.get("relatedAppointmentId") or "",
                        "relatedPaymentId": doc_data.get("relatedPaymentId") or "",
                    }
                    cls._send_fcm_push(
                        db=db,
                        recipient_user_id=str(recipient_user_id),
                        title=title,
                        body=body,
                        data=push_data,
                    )
                except Exception as push_exc:
                    logger.warning("FCM push delivery failed: %s", push_exc)

            return _doc_to_response(doc_data)
        except Exception as exc:
            # Logging failure without breaking the caller
            logger.error("Failed to create notification for user %s: %s", recipient_user_id, exc)
            return None

    # -------------------------------------------------------------------------
    # 4. User Notification Listing & Counts
    # -------------------------------------------------------------------------
    @staticmethod
    def list_notifications(
        db: Database,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False,
    ) -> NotificationListResponse:
        """Fetch paginated notifications owned by the authenticated user."""
        notif_col = get_notification_collection(db)
        query: Dict[str, Any] = {"recipientUserId": str(user_id)}
        if unread_only:
            query["isRead"] = False

        total = notif_col.count_documents(query)
        total_pages = max(1, math.ceil(total / limit)) if total > 0 else 1
        skip = (page - 1) * limit

        cursor = (
            notif_col.find(query)
            .sort("createdAt", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

        items = [_doc_to_response(d) for d in cursor]

        # Calculate unread count for current user
        unread_count = notif_col.count_documents({"recipientUserId": str(user_id), "isRead": False})

        return NotificationListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            totalPages=total_pages,
            unreadCount=unread_count,
        )

    @staticmethod
    def get_unread_count(db: Database, user_id: str) -> int:
        """Return total unread notifications count for a user."""
        notif_col = get_notification_collection(db)
        return notif_col.count_documents({"recipientUserId": str(user_id), "isRead": False})

    # -------------------------------------------------------------------------
    # 5. Mark As Read / Mark All As Read
    # -------------------------------------------------------------------------
    @staticmethod
    def mark_as_read(
        db: Database,
        notification_id: str,
        user_id: str,
    ) -> NotificationActionResponse:
        """Mark a single notification as read, enforcing recipient ownership."""
        if not ObjectId.is_valid(notification_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid notification ID format.",
            )

        notif_col = get_notification_collection(db)
        doc = notif_col.find_one({"_id": ObjectId(notification_id)})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        # Ownership authorization check
        if str(doc.get("recipientUserId")) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this notification.",
            )

        if not doc.get("isRead"):
            notif_col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"isRead": True, "readAt": utc_now()}},
            )

        return NotificationActionResponse(
            success=True,
            message="Notification marked as read.",
            modifiedCount=1,
        )

    @staticmethod
    def mark_all_as_read(
        db: Database,
        user_id: str,
    ) -> NotificationActionResponse:
        """Mark all unread notifications for a user as read."""
        notif_col = get_notification_collection(db)
        now = utc_now()
        res = notif_col.update_many(
            {"recipientUserId": str(user_id), "isRead": False},
            {"$set": {"isRead": True, "readAt": now}},
        )
        return NotificationActionResponse(
            success=True,
            message=f"Marked {res.modified_count} notifications as read.",
            modifiedCount=res.modified_count,
        )

    # -------------------------------------------------------------------------
    # 6. Appointment Reminders (Scheduled Background Job)
    # -------------------------------------------------------------------------
    @classmethod
    def check_and_send_appointment_reminders(cls, db: Database) -> int:
        """Check upcoming CONFIRMED appointments and trigger 24h & 1h reminders.

        Reminders:
        - 24 hours before appointment
        - 1 hour before appointment
        - Skips cancelled appointments
        - Never sends duplicate reminders
        - Timezone aware (Asia/Colombo)
        """
        try:
            now_sl = datetime.now(SL_TIMEZONE)
            today_sl = now_sl.date()
            tomorrow_sl = today_sl + timedelta(days=1)
            day_after_sl = today_sl + timedelta(days=2)

            # Dates to inspect: today, tomorrow, day after tomorrow
            dates_to_inspect = [
                today_sl.strftime("%Y-%m-%d"),
                tomorrow_sl.strftime("%Y-%m-%d"),
                day_after_sl.strftime("%Y-%m-%d"),
            ]

            appt_col = db["appointments"]
            # Find confirmed appointments for these dates
            cursor = appt_col.find({
                "status": AppointmentStatus.CONFIRMED.value,
                "appointmentDate": {"$in": dates_to_inspect},
            })

            reminders_sent_count = 0

            for appt in cursor:
                appt_id_str = str(appt["_id"])
                patient_user_id = str(appt["patientUserId"])
                date_str = appt.get("appointmentDate", "")
                time_str = appt.get("startTime", "")

                try:
                    appt_dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                    appt_dt = appt_dt_naive.replace(tzinfo=SL_TIMEZONE)
                except ValueError:
                    continue

                diff = appt_dt - now_sl
                reminders_sent = appt.get("remindersSent", [])

                # 1. 24-Hour Reminder: window between 1 hour and 24 hours before slot
                if timedelta(hours=1) < diff <= timedelta(hours=24):
                    if "24h" not in reminders_sent:
                        # Atomic lock via $addToSet
                        update_res = appt_col.update_one(
                            {"_id": appt["_id"], "remindersSent": {"$ne": "24h"}},
                            {"$addToSet": {"remindersSent": "24h"}},
                        )
                        if update_res.modified_count > 0:
                            cls.create_notification(
                                db=db,
                                recipient_user_id=patient_user_id,
                                type=NotificationType.APPOINTMENT_REMINDER_24H,
                                title="Upcoming Appointment Tomorrow",
                                body=f"Reminder: You have an appointment tomorrow at {time_str}.",
                                related_appointment_id=appt_id_str,
                                idempotency_key=f"reminder_24h_{appt_id_str}",
                                send_push=True,
                            )
                            reminders_sent_count += 1
                            logger.info("Sent 24h reminder for appointment %s", appt_id_str)

                # 2. 1-Hour Reminder: window between 0 and 1 hour before slot
                elif timedelta(minutes=0) < diff <= timedelta(hours=1):
                    if "1h" not in reminders_sent:
                        update_res = appt_col.update_one(
                            {"_id": appt["_id"], "remindersSent": {"$ne": "1h"}},
                            {"$addToSet": {"remindersSent": "1h"}},
                        )
                        if update_res.modified_count > 0:
                            cls.create_notification(
                                db=db,
                                recipient_user_id=patient_user_id,
                                type=NotificationType.APPOINTMENT_REMINDER_1H,
                                title="Appointment in 1 Hour",
                                body=f"Reminder: Your appointment starts in approximately 1 hour at {time_str}.",
                                related_appointment_id=appt_id_str,
                                idempotency_key=f"reminder_1h_{appt_id_str}",
                                send_push=True,
                            )
                            reminders_sent_count += 1
                            logger.info("Sent 1h reminder for appointment %s", appt_id_str)

            return reminders_sent_count
        except Exception as exc:
            logger.error("Error executing check_and_send_appointment_reminders: %s", exc)
            return 0
