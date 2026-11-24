"""MongoDB document models and index creators for Phase 7: Operational Incident Management."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone."""
    return datetime.now(timezone.utc)


class IncidentCategory(str, Enum):
    """Categories of operational incidents."""
    SECURITY = "SECURITY"
    PAYMENT = "PAYMENT"
    NOTIFICATION = "NOTIFICATION"
    DATABASE = "DATABASE"
    AI_PROVIDER = "AI_PROVIDER"
    SCHEDULER = "SCHEDULER"
    BOOKING = "BOOKING"
    API_AVAILABILITY = "API_AVAILABILITY"


class IncidentSeverity(str, Enum):
    """Severity ratings for incidents."""
    INFORMATIONAL = "INFORMATIONAL"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    """Operational lifecycle statuses for an incident."""
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"


class OperationalIncidentDocument(BaseModel):
    """Document representing an operational platform incident."""
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True, arbitrary_types_allowed=True)

    id: Optional[str] = Field(default=None, alias="_id")
    incidentId: str = Field(..., description="Unique incident identifier, e.g. INC-UUID")
    title: str = Field(..., min_length=1, max_length=200)
    category: IncidentCategory
    severity: IncidentSeverity
    status: IncidentStatus = Field(default=IncidentStatus.OPEN)
    description: str
    affectedService: str
    supportingEventReferences: List[str] = Field(default_factory=list)
    assignedAdminId: Optional[str] = None
    resolutionNotes: Optional[str] = None
    createdAt: datetime = Field(default_factory=utc_now)
    acknowledgedAt: Optional[datetime] = None
    resolvedAt: Optional[datetime] = None


def create_operational_incidents_indexes(db: Database) -> None:
    """Create indexes for operational incidents collection."""
    collection = db["operational_incidents"]
    collection.create_index([("incidentId", ASCENDING)], unique=True, name="idx_operational_incidents_id")
    collection.create_index([("category", ASCENDING), ("status", ASCENDING)], name="idx_operational_incidents_cat_status")
    collection.create_index([("severity", ASCENDING), ("status", ASCENDING)], name="idx_operational_incidents_sev_status")
    collection.create_index([("createdAt", DESCENDING)], name="idx_operational_incidents_created")
