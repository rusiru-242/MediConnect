"""Append-only audit trail for appointment and payment lifecycle transitions (Phase 02).

Each event stores identifiers, the actor role and the state change only: no clinical notes, contact
details or payment secrets. Recording never breaks the business operation that triggered it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import ASCENDING
from pymongo.database import Database

logger = logging.getLogger(__name__)
COLLECTION = "appointment_events"


def create_appointment_event_indexes(db: Database) -> None:
    db[COLLECTION].create_index([("appointmentId", ASCENDING), ("createdAt", ASCENDING)],
                                name="idx_appt_events_appointment_created")
    db[COLLECTION].create_index([("idempotencyKey", ASCENDING)], unique=True, sparse=True,
                                name="idx_appt_events_idempotency")


def record_appointment_event(
    db: Database,
    appointment_id: str,
    event: str,
    *,
    actor_role: str,
    actor_id: Optional[str] = None,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> None:
    document = {
        "appointmentId": str(appointment_id), "event": event, "actorRole": actor_role,
        "actorId": str(actor_id) if actor_id else None, "fromStatus": from_status, "toStatus": to_status,
        "details": details or {}, "createdAt": datetime.now(timezone.utc),
    }
    if idempotency_key:
        document["idempotencyKey"] = idempotency_key
    try:
        db[COLLECTION].insert_one(document)
    except Exception as exc:  # duplicate idempotency key or storage error: the operation itself already succeeded
        if type(exc).__name__ != "DuplicateKeyError":
            logger.warning("Appointment event %s was not recorded (%s).", event, type(exc).__name__)
