"""Notification Monitoring Service: Telemetry, bounded retries, dead-letter handling, and device cleanup."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pymongo.database import Database

from app.config.database import get_database
from app.models.security_event import utc_now


class NotificationMonitoringService:
    """Manages notification outbox reliability, retry scheduling, and dead-letter queue operations."""

    MAX_RETRIES = 3

    @classmethod
    def get_notification_metrics(cls, db: Optional[Database] = None) -> Dict[str, Any]:
        """Aggregate notification telemetry across all delivery channels."""
        if db is None:
            db = get_database()

        channels = ["email", "sms", "push", "in_app"]
        metrics_by_channel = []
        total_backlog = 0
        total_delivered = 0
        total_failed = 0

        for ch in channels:
            # Query outbox states
            if ch in ("email", "sms"):
                path = f"confirmationOutbox.{ch}"
                pending = db["appointments"].count_documents({f"{path}.status": "pending"})
                delivered = db["appointments"].count_documents({f"{path}.status": "delivered"})
                failed = db["appointments"].count_documents({f"{path}.status": "failed"})
                retry_scheduled = db["appointments"].count_documents({f"{path}.status": "retry_scheduled"})
            else:
                pending = db["notifications"].count_documents({"isRead": False})
                delivered = db["notifications"].count_documents({})
                failed = 0
                retry_scheduled = 0

            dead_lettered = db["notification_dead_letters"].count_documents({"channel": ch})

            total_channel = pending + delivered + failed + retry_scheduled + dead_lettered
            total_backlog += (pending + retry_scheduled)
            total_delivered += delivered
            total_failed += (failed + dead_lettered)

            metrics_by_channel.append({
                "channel": ch,
                "pending": pending,
                "processing": 0,
                "delivered": delivered,
                "failed": failed,
                "retryScheduled": retry_scheduled,
                "deadLettered": dead_lettered,
                "total": total_channel,
            })

        dead_letters_count = db["notification_dead_letters"].count_documents({"status": "unresolved"})
        denom = (total_delivered + total_failed)
        failure_rate = (total_failed / denom * 100.0) if denom > 0 else 0.0

        return {
            "timestamp": utc_now(),
            "byChannel": metrics_by_channel,
            "totalBacklog": total_backlog,
            "failureRatePercent": round(failure_rate, 2),
            "deadLetterQueueCount": dead_letters_count,
        }

    @classmethod
    def process_notification_retries(cls, db: Optional[Database] = None) -> Dict[str, Any]:
        """Safely process pending notification retries with bounded exponential backoff and context validation."""
        if db is None:
            db = get_database()

        retried_count = 0
        dead_lettered_count = 0
        cancelled_count = 0
        now = utc_now()

        # Find appointments with failed/retry_scheduled confirmationOutbox
        for channel in ("email", "sms"):
            path = f"confirmationOutbox.{channel}"
            cursor = db["appointments"].find({
                f"{path}.status": {"$in": ["failed", "retry_scheduled"]},
            })

            for appt in cursor:
                appt_id = str(appt["_id"])
                outbox_entry = appt.get("confirmationOutbox", {}).get(channel, {})
                attempts = outbox_entry.get("attempts", 0)

                # Context Revalidation: Check if appointment was cancelled
                if appt.get("status") == "CANCELLED":
                    db["appointments"].update_one(
                        {"_id": appt["_id"]},
                        {"$set": {f"{path}.status": "cancelled", f"{path}.cancellationReason": "appointment_cancelled_before_retry"}},
                    )
                    cancelled_count += 1
                    continue

                # Dead-letter threshold exceeded
                if attempts >= cls.MAX_RETRIES:
                    dead_letter_doc = {
                        "deadLetterId": f"DL-{uuid4().hex[:10].upper()}",
                        "appointmentId": appt_id,
                        "recipientUserId": appt.get("patientUserId"),
                        "channel": channel,
                        "reason": outbox_entry.get("error") or "Max retry attempts exceeded",
                        "retryCount": attempts,
                        "status": "unresolved",
                        "createdAt": now,
                    }
                    db["notification_dead_letters"].insert_one(dead_letter_doc)
                    db["appointments"].update_one(
                        {"_id": appt["_id"]},
                        {"$set": {f"{path}.status": "dead_lettered"}},
                    )
                    dead_lettered_count += 1
                else:
                    # Schedule next retry with exponential backoff (1m, 5m, 15m)
                    backoff_minutes = [1, 5, 15][min(attempts, 2)]
                    next_retry_at = now + timedelta(minutes=backoff_minutes)

                    db["appointments"].update_one(
                        {"_id": appt["_id"]},
                        {
                            "$set": {
                                f"{path}.status": "retry_scheduled",
                                f"{path}.nextRetryAt": next_retry_at,
                            },
                            "$inc": {f"{path}.attempts": 1},
                        },
                    )
                    retried_count += 1

        return {
            "retriedCount": retried_count,
            "deadLetteredCount": dead_lettered_count,
            "cancelledObsoleteCount": cancelled_count,
        }

    @classmethod
    def list_dead_letters(cls, limit: int = 50, skip: int = 0, db: Optional[Database] = None) -> List[Dict[str, Any]]:
        """Retrieve items in the dead-letter queue."""
        if db is None:
            db = get_database()

        cursor = db["notification_dead_letters"].find({}).sort("createdAt", -1).skip(skip).limit(limit)
        items = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            items.append(doc)
        return items

    @classmethod
    def manual_retry_dead_letter(
        cls,
        dead_letter_id: str,
        admin_id: str,
        db: Optional[Database] = None,
    ) -> bool:
        """Allow authorized administrator to manually requeue a dead-lettered notification."""
        if db is None:
            db = get_database()

        dead_letter = db["notification_dead_letters"].find_one({"deadLetterId": dead_letter_id})
        if not dead_letter:
            return False

        appt_id = dead_letter.get("appointmentId")
        channel = dead_letter.get("channel")

        if appt_id and channel:
            from bson import ObjectId
            db["appointments"].update_one(
                {"_id": ObjectId(appt_id)},
                {
                    "$set": {
                        f"confirmationOutbox.{channel}.status": "retry_scheduled",
                        f"confirmationOutbox.{channel}.attempts": 0,
                        f"confirmationOutbox.{channel}.requeuedBy": admin_id,
                    }
                },
            )

        db["notification_dead_letters"].update_one(
            {"deadLetterId": dead_letter_id},
            {
                "$set": {
                    "status": "requeued",
                    "resolvedBy": admin_id,
                    "resolvedAt": utc_now(),
                }
            },
        )
        return True

    @classmethod
    def cleanup_invalid_device_tokens(cls, tokens: List[str], db: Optional[Database] = None) -> int:
        """Remove invalid or expired FCM registration tokens from patient profiles."""
        if db is None:
            db = get_database()

        if not tokens:
            return 0

        res = db["device_tokens"].delete_many({"token": {"$in": tokens}})
        return res.deleted_count
