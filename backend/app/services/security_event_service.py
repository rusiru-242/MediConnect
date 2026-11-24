"""Security Event Service: Logs, queries, and audits security events with strict PII sanitization."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pymongo.database import Database

from app.config.database import get_database
from app.models.security_event import (
    SecurityEventCategory,
    SecurityEventDocument,
    SecuritySeverity,
    utc_now,
)


class SecurityEventService:
    """Central service for auditing and querying security telemetry."""

    SENSITIVE_KEYS = {"password", "token", "jwt", "secret", "card_number", "stripe_secret", "cvv"}

    @classmethod
    def sanitize_metadata(cls, data: Any) -> Any:
        """Recursively redact passwords, secrets, and raw tokens from audit metadata."""
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                if any(sk in k.lower() for sk in cls.SENSITIVE_KEYS):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = cls.sanitize_metadata(v)
            return sanitized
        elif isinstance(data, list):
            return [cls.sanitize_metadata(item) for item in data]
        return data

    @classmethod
    def record_security_event(
        cls,
        category: SecurityEventCategory,
        severity: SecuritySeverity,
        description: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Database] = None,
    ) -> SecurityEventDocument:
        """Create and persist an auditable security event."""
        if db is None:
            db = get_database()

        clean_metadata = cls.sanitize_metadata(metadata or {})
        event = SecurityEventDocument(
            eventId=f"SEC-{uuid4().hex[:10].upper()}",
            category=category,
            severity=severity,
            actorId=actor_id,
            actorRole=actor_role,
            ipAddress=ip_address,
            endpoint=endpoint,
            description=description,
            metadata=clean_metadata,
            timestamp=utc_now(),
        )

        db["security_events"].insert_one(event.model_dump(by_alias=True))
        return event

    @classmethod
    def list_security_events(
        cls,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        actor_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
        db: Optional[Database] = None,
    ) -> Dict[str, Any]:
        """Query security events with filters and pagination."""
        if db is None:
            db = get_database()

        query: Dict[str, Any] = {}
        if category:
            query["category"] = category
        if severity:
            query["severity"] = severity
        if actor_id:
            query["actorId"] = actor_id

        total = db["security_events"].count_documents(query)
        cursor = db["security_events"].find(query).sort("timestamp", -1).skip(skip).limit(limit)

        items = []
        for doc in cursor:
            doc["_id"] = str(doc.get("_id"))
            items.append(SecurityEventDocument(**doc))

        return {"items": items, "total": total}

    @classmethod
    def get_security_summary(cls, hours: int = 24, db: Optional[Database] = None) -> Dict[str, Any]:
        """Return counts of security events grouped by severity and category within time window."""
        if db is None:
            db = get_database()

        since = utc_now() - timedelta(hours=hours)
        events = list(db["security_events"].find({"timestamp": {"$gte": since}}))

        by_severity = {sev.value: 0 for sev in SecuritySeverity}
        by_category = {cat.value: 0 for cat in SecurityEventCategory}

        for ev in events:
            sev = ev.get("severity")
            cat = ev.get("category")
            if sev in by_severity:
                by_severity[sev] += 1
            if cat in by_category:
                by_category[cat] += 1

        return {
            "timeWindowHours": hours,
            "totalEvents": len(events),
            "bySeverity": by_severity,
            "byCategory": by_category,
        }
