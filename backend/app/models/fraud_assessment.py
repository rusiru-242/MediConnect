"""MongoDB document models and index creators for Phase 7: AI Fraud Detection & Risk Scoring."""

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


class FraudRiskLevel(str, Enum):
    """Risk tiers for evaluated entities or accounts."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FraudReviewStatus(str, Enum):
    """Lifecycle states for a fraud risk review."""
    DETECTED = "DETECTED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    INVESTIGATING = "INVESTIGATING"
    DISMISSED = "DISMISSED"
    CONFIRMED = "CONFIRMED"
    RESOLVED = "RESOLVED"


class FraudAssessmentDocument(BaseModel):
    """Document representing a rule-based explainable fraud risk assessment."""
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True, arbitrary_types_allowed=True)

    id: Optional[str] = Field(default=None, alias="_id")
    assessmentId: str = Field(..., description="Unique assessment identifier, e.g. FRAUD-UUID")
    relatedAccountId: Optional[str] = Field(default=None, description="User ID evaluated if applicable")
    relatedEntityReference: str = Field(..., description="Reference ID (e.g. appointment, payment, doctor profile)")
    riskScore: float = Field(..., ge=0.0, le=100.0, description="Deterministic risk score between 0 and 100")
    riskLevel: FraudRiskLevel
    triggeredRules: List[str] = Field(default_factory=list, description="IDs/names of rules triggered")
    supportingEventReferences: List[str] = Field(default_factory=list, description="Supporting transaction or event IDs")
    # A05: per-rule threshold, observed value and minimal evidence rows, so a reviewer can see why a rule fired.
    ruleEvidence: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: str = Field(..., description="Explainable natural language narrative detailing triggers")
    reviewStatus: FraudReviewStatus = Field(default=FraudReviewStatus.AWAITING_REVIEW)
    investigationNotes: List[Dict[str, Any]] = Field(default_factory=list)
    assignedAdminId: Optional[str] = None
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)


def create_fraud_assessments_indexes(db: Database) -> None:
    """Create indexes for fraud assessments collection."""
    collection = db["fraud_risk_assessments"]
    collection.create_index([("assessmentId", ASCENDING)], unique=True, name="idx_fraud_assessments_id")
    collection.create_index([("relatedAccountId", ASCENDING)], sparse=True, name="idx_fraud_assessments_account")
    collection.create_index([("relatedEntityReference", ASCENDING)], name="idx_fraud_assessments_entity")
    collection.create_index([("reviewStatus", ASCENDING), ("riskLevel", ASCENDING)], name="idx_fraud_assessments_status_lvl")
    collection.create_index([("createdAt", DESCENDING)], name="idx_fraud_assessments_created")
    # A05-BUG-002: one open assessment per account, enforced by the database (two concurrent evaluations used to
    # insert two alerts). ``openKey`` is set while the assessment is open and removed when a reviewer closes it.
    collection.create_index([("openKey", ASCENDING)], unique=True, name="idx_fraud_assessments_open_unique",
                            partialFilterExpression={"openKey": {"$exists": True}})
