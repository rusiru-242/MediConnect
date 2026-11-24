"""MongoDB document models and index creators for Phase 7: Security Events & Audit Telemetry."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone."""
    return datetime.now(timezone.utc)


class SecurityEventCategory(str, Enum):
    """Categorization for security audit events."""
    AUTH_FAILURE = "AUTH_FAILURE"
    BRUTE_FORCE = "BRUTE_FORCE"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    UNAUTHORIZED_TOOL_CALL = "UNAUTHORIZED_TOOL_CALL"
    SUSPICIOUS_PAYMENT = "SUSPICIOUS_PAYMENT"
    DATA_LEAK_PREVENTION = "DATA_LEAK_PREVENTION"
    SYSTEM_ANOMALY = "SYSTEM_ANOMALY"


class SecuritySeverity(str, Enum):
    """Severity levels for security events."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SecurityEventDocument(BaseModel):
    """Document representing a logged security or defensive event."""
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True, arbitrary_types_allowed=True)

    id: Optional[str] = Field(default=None, alias="_id")
    eventId: str = Field(..., description="Unique business identifier, e.g. SEC-UUID")
    category: SecurityEventCategory
    severity: SecuritySeverity
    actorId: Optional[str] = None
    actorRole: Optional[str] = None
    ipAddress: Optional[str] = None
    endpoint: Optional[str] = None
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)


def create_security_events_indexes(db: Database) -> None:
    """Create indexes for security event queries and retention."""
    collection = db["security_events"]
    collection.create_index([("eventId", ASCENDING)], unique=True, name="idx_security_events_event_id")
    collection.create_index([("timestamp", DESCENDING)], name="idx_security_events_timestamp")
    collection.create_index([("category", ASCENDING), ("severity", ASCENDING)], name="idx_security_events_cat_sev")
    collection.create_index([("actorId", ASCENDING)], sparse=True, name="idx_security_events_actor")
