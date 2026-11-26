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

    # Outbox results that will never succeed by retrying (P04-N15): retrying them only inflated the backlog.
    PERMANENT_REASONS = frozenset({"provider_not_configured", "verified_email_required", "authorized_mobile_required",
                                   "preference_disabled", "invalid_recipient", "gateway_rejected"})
    # A02-BUG-004: "delivered" now means delivery evidence only (an in-app record stored for the recipient, or a
    # provider delivery receipt such as Twilio "delivered"). Provider acceptance (SMTP accepted the message, FCM or
    # Twilio accepted the request) is reported separately as "accepted", and a provider that is not configured is
    # "disabled", not "failed" or "skipped".
    _DELIVERED = {"delivered", "stored", "stored_in_app"}
    _ACCEPTED = {"sent", "accepted"}
    _PENDING = {"pending", "retry", "retry_scheduled"}
    _SKIPPED = {"skipped", "cancelled", "no_device", "expired"}
    _DISABLED = {"disabled", "unavailable"}
    _NOT_ATTEMPTED = {"not_requested"}

    @classmethod
    def _bucket(cls, counts: Dict[str, int]) -> Dict[str, int]:
        return {
            "pending": sum(v for k, v in counts.items() if k in cls._PENDING),
            "processing": counts.get("sending", 0),
            "accepted": sum(v for k, v in counts.items() if k in cls._ACCEPTED),
            "delivered": sum(v for k, v in counts.items() if k in cls._DELIVERED),
            "failed": counts.get("failed", 0) + counts.get("dead_lettered", 0),
            "retryScheduled": counts.get("retry_scheduled", 0) + counts.get("retry", 0),
            "skipped": sum(v for k, v in counts.items() if k in cls._SKIPPED),
            "disabled": sum(v for k, v in counts.items() if k in cls._DISABLED),
            "uncertain": counts.get("uncertain", 0),
        }

    @staticmethod
    def _status_counts(db: Database, collection: str, path: str) -> Dict[str, int]:
        coll = db[collection]
        if hasattr(coll, "aggregate"):
            rows = coll.aggregate([
                {"$match": {path: {"$exists": True}}},
                {"$group": {"_id": f"${path}", "n": {"$sum": 1}}},
            ])
            return {str(r["_id"]): int(r["n"]) for r in rows if r["_id"] is not None}
        counts: Dict[str, int] = {}
        for doc in coll.find({}):  # minimal stores without aggregation (unit-test doubles)
            value: Any = doc
            for part in path.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            if value is not None:
                counts[str(value)] = counts.get(str(value), 0) + 1
        return counts

    @classmethod
    def get_notification_metrics(cls, db: Optional[Database] = None) -> Dict[str, Any]:
        """Delivery state per channel from the records the workers actually write (P04-N15).

        Sources: the booking-confirmation outbox on appointments (email, SMS, doctor in-app), the care reminder
        events written by the care scheduler (in-app, push, email, SMS) and the stored in-app notifications.
        Before Phase 04, "push" and "in_app" both reported every stored notification as delivered (push was
        counted as delivered with FCM not configured), email "delivered" never matched the outbox value "sent", and
        care reminders were not counted at all.
        """
        if db is None:
            db = get_database()
        from app.services.platform_monitoring_service import PlatformMonitoringService
        providers = {row["name"].split(" ")[0].lower(): row["status"]
                     for row in PlatformMonitoringService.check_notification_channels()}

        sources = {
            "email": [("appointments", "confirmationOutbox.email.status"), ("care_reminder_events", "channels.email.status")],
            "sms": [("appointments", "confirmationOutbox.sms.status"), ("care_reminder_events", "channels.sms.status")],
            "push": [("care_reminder_events", "channels.push.status"), ("notifications", "channels.push.status")],
            "in_app": [("appointments", "confirmationOutbox.doctor.status"), ("care_reminder_events", "channels.inApp.status")],
        }
        metrics_by_channel = []
        total_backlog = total_delivered = total_failed = 0
        notes: List[str] = []
        for ch, paths in sources.items():
            counts: Dict[str, int] = {}
            for coll, path in paths:
                for k, v in cls._status_counts(db, coll, path).items():
                    if k not in cls._NOT_ATTEMPTED:
                        counts[k] = counts.get(k, 0) + v
            dead_lettered = db["notification_dead_letters"].count_documents({"channel": ch, "status": "unresolved"})
            b = cls._bucket(counts)
            provider = "in_app_store" if ch == "in_app" else providers.get(ch, "unknown")
            total = sum(counts.values())
            total_backlog += b["pending"]
            total_delivered += b["delivered"] + b["accepted"]
            total_failed += b["failed"] + dead_lettered
            if provider == "not_configured" and (b["failed"] or b["skipped"] or b["disabled"]):
                notes.append(f"{ch}: provider not configured; {b['disabled']} disabled, {b['failed']} failed and "
                             f"{b['skipped']} skipped. Nothing was sent on this channel.")
            metrics_by_channel.append({"channel": ch, **b, "deadLettered": dead_lettered, "total": total,
                                       "providerStatus": provider, "statusCounts": counts})

        denom = total_delivered + total_failed
        event_states = cls._status_counts(db, "care_reminder_events", "state")
        return {
            "timestamp": utc_now(),
            "byChannel": metrics_by_channel,
            "totalBacklog": total_backlog,
            "failureRatePercent": round(total_failed / denom * 100.0, 2) if denom else None,
            "deadLetterQueueCount": db["notification_dead_letters"].count_documents({"status": "unresolved"}),
            "careReminderEvents": event_states,
            "inAppStored": db["notifications"].count_documents({}),
            "inAppUnread": db["notifications"].count_documents({"isRead": False}),
            "notes": notes,
        }

    @classmethod
    def process_notification_retries(cls, db: Optional[Database] = None) -> Dict[str, Any]:
        """Re-queue transient booking-confirmation failures for the outbox worker (P04-N15).

        - A failure whose reason is permanent (for example provider_not_configured) is not retried.
        - An "uncertain" result is never retried automatically: the message may already have been sent.
        - A retry is handed back as "pending" with nextAttemptAt=now, which is the state the outbox worker
          processes. The former "retry_scheduled" state was not processed by any worker.
        - After MAX_RETRIES attempts the item goes to the dead-letter queue for a human.
        """
        if db is None:
            db = get_database()

        retried_count = 0
        dead_lettered_count = 0
        cancelled_count = 0
        not_retryable = 0
        now = utc_now()

        for channel in ("email", "sms"):
            path = f"confirmationOutbox.{channel}"
            cursor = db["appointments"].find({
                f"{path}.status": {"$in": ["failed", "retry_scheduled"]},
            })

            for appt in cursor:
                appt_id = str(appt["_id"])
                outbox_entry = appt.get("confirmationOutbox", {}).get(channel, {})
                attempts = outbox_entry.get("attempts", 0)
                current = outbox_entry.get("status")

                # Context revalidation: a cancelled appointment's confirmation is obsolete.
                if appt.get("status") == "CANCELLED":
                    db["appointments"].update_one(
                        {"_id": appt["_id"], f"{path}.status": current},
                        {"$set": {f"{path}.status": "cancelled", f"{path}.cancellationReason": "appointment_cancelled_before_retry"}},
                    )
                    cancelled_count += 1
                    continue

                if current == "failed" and outbox_entry.get("reason") in cls.PERMANENT_REASONS:
                    not_retryable += 1
                    continue

                if attempts >= cls.MAX_RETRIES:
                    moved = db["appointments"].update_one(
                        {"_id": appt["_id"], f"{path}.status": current},
                        {"$set": {f"{path}.status": "dead_lettered"}},
                    )
                    if moved.modified_count:
                        db["notification_dead_letters"].insert_one({
                            "deadLetterId": f"DL-{uuid4().hex[:10].upper()}",
                            "appointmentId": appt_id,
                            "recipientUserId": appt.get("patientUserId"),
                            "channel": channel,
                            "reason": outbox_entry.get("reason") or outbox_entry.get("error") or "Max retry attempts exceeded",
                            "retryCount": attempts,
                            "status": "unresolved",
                            "createdAt": now,
                        })
                        dead_lettered_count += 1
                else:
                    requeued = db["appointments"].update_one(
                        {"_id": appt["_id"], f"{path}.status": current},
                        {"$set": {f"{path}.status": "pending", f"{path}.nextAttemptAt": now,
                                  f"{path}.requeuedAt": now}},
                    )
                    retried_count += requeued.modified_count

        return {
            "retriedCount": retried_count,
            "deadLetteredCount": dead_lettered_count,
            "cancelledObsoleteCount": cancelled_count,
            "notRetryableCount": not_retryable,
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

        if dead_letter.get("status") != "unresolved":
            return True  # already requeued: repeated clicks do not queue the message twice
        if appt_id and channel:
            from bson import ObjectId
            if ObjectId.is_valid(str(appt_id)):
                db["appointments"].update_one(
                    {"_id": ObjectId(appt_id), f"confirmationOutbox.{channel}.status": "dead_lettered"},
                    {
                        "$set": {
                            # "pending" is the state the outbox worker processes (was "retry_scheduled").
                            f"confirmationOutbox.{channel}.status": "pending",
                            f"confirmationOutbox.{channel}.nextAttemptAt": utc_now(),
                            f"confirmationOutbox.{channel}.attempts": 0,
                            f"confirmationOutbox.{channel}.requeuedBy": admin_id,
                        }
                    },
                )

        db["notification_dead_letters"].update_one(
            {"deadLetterId": dead_letter_id, "status": "unresolved"},
            {
                "$set": {
                    "status": "requeued",
                    "resolvedBy": admin_id,
                    "resolvedAt": utc_now(),
                }
            },
        )
        from app.services.admin_audit_service import AdminAuditService
        AdminAuditService.log_action(db=db, actor_id=admin_id, actor_role="ADMIN", action_type="NOTIFICATION_REQUEUE",
                                     target_id=dead_letter_id, target_type="notification_dead_letter",
                                     previous_state="unresolved", new_state="requeued",
                                     metadata={"channel": channel, "appointmentId": appt_id})
        return True

    @classmethod
    def cleanup_invalid_device_tokens(cls, tokens: List[str], db: Optional[Database] = None) -> int:
        """Remove invalid or expired FCM registration tokens from patient profiles."""
        if db is None:
            db = get_database()

        if not tokens:
            return 0

        # A02-BUG-010: the stored field is "fcmToken"; the query on "token" never removed anything.
        from app.models.notification import get_device_token_collection
        res = get_device_token_collection(db).delete_many({"fcmToken": {"$in": list(tokens)}})
        return res.deleted_count
