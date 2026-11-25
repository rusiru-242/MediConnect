"""Fraud Detection Service: Rule-based explainable risk scoring, deduplication, and admin review workflow."""

from app.utils.mongo_documents import document_for_insert
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pymongo.database import Database

from app.config.database import get_database
from app.models.fraud_assessment import (
    FraudAssessmentDocument,
    FraudRiskLevel,
    FraudReviewStatus,
    utc_now,
)
from app.models.security_event import SecurityEventCategory, SecuritySeverity
from app.services.security_event_service import SecurityEventService


class FraudDetectionService:
    """Evaluates transactional signals and manages explainable fraud risk assessments."""

    RULES_DEFINITION = {
        "MULTIPLE_FAILED_PAYMENTS": {
            "weight": 35.0,
            "description": "3 or more failed payment attempts detected within 24 hours.",
        },
        "DUPLICATE_PAYMENT_REFERENCES": {
            "weight": 40.0,
            "description": "Same payment reference/instrument used across distinct accounts.",
        },
        "EXCESSIVE_BOOKING_RATE": {
            "weight": 30.0,
            "description": "More than 5 appointment reservations initiated within 1 hour.",
        },
        "RAPID_CANCELLATION_PATTERN": {
            "weight": 25.0,
            "description": "More than 3 appointment cancellations within 24 hours.",
        },
        "EXCESSIVE_REFUND_REQUESTS": {
            "weight": 30.0,
            "description": "More than 2 refund requests submitted within 7 days.",
        },
        "SLOT_HOARDING_ATTEMPT": {
            "weight": 20.0,
            "description": "Repeated booking attempts against already reserved slots.",
            # Declared but not evaluated: booking conflicts are rejected by a unique index and are not recorded
            # per account, so there is no evidence source for this rule (P04-N12).
            "implemented": False,
        },
        "UNAUTHORIZED_ACCESS_BURST": {
            "weight": 35.0,
            "description": "5 or more authorization failures within a 15-minute window.",
        },
    }

    @classmethod
    def _compute_risk_level(cls, score: float) -> FraudRiskLevel:
        if score >= 75.0:
            return FraudRiskLevel.CRITICAL
        elif score >= 50.0:
            return FraudRiskLevel.HIGH
        elif score >= 25.0:
            return FraudRiskLevel.MEDIUM
        return FraudRiskLevel.LOW

    @classmethod
    def evaluate_account_risk(
        cls,
        account_id: str,
        entity_ref: Optional[str] = None,
        db: Optional[Database] = None,
    ) -> Optional[FraudAssessmentDocument]:
        """Evaluate real behavioral signals against deterministic risk rules."""
        if db is None:
            db = get_database()

        now = utc_now()
        day_ago = now - timedelta(hours=24)
        hour_ago = now - timedelta(hours=1)
        fifteen_mins_ago = now - timedelta(minutes=15)
        week_ago = now - timedelta(days=7)

        triggered_rules: List[str] = []
        supporting_events: List[str] = []
        calculated_score: float = 0.0

        # 1. Rule: MULTIPLE_FAILED_PAYMENTS
        # Payment statuses are upper case; the former lower-case "failed" never matched, so this rule could never
        # fire (P04-N12).
        failed_payments = list(db["payments"].find({
            "patientUserId": account_id,
            "status": "FAILED",
            "createdAt": {"$gte": day_ago},
        }))
        if len(failed_payments) >= 3:
            triggered_rules.append("MULTIPLE_FAILED_PAYMENTS")
            calculated_score += cls.RULES_DEFINITION["MULTIPLE_FAILED_PAYMENTS"]["weight"]
            supporting_events.extend([str(p.get("stripePaymentIntentId") or p.get("paymentIntentId") or p.get("_id")) for p in failed_payments[:5]])

        # 1b. Rule: DUPLICATE_PAYMENT_REFERENCES - this account's PaymentIntent is also recorded for another account.
        own_intents = [p["stripePaymentIntentId"] for p in db["payments"].find(
            {"patientUserId": account_id, "stripePaymentIntentId": {"$nin": [None, ""]}}, {"stripePaymentIntentId": 1})]
        shared = list(db["payments"].find({"stripePaymentIntentId": {"$in": own_intents},
                                           "patientUserId": {"$ne": account_id}}, {"stripePaymentIntentId": 1})) if own_intents else []
        if shared:
            triggered_rules.append("DUPLICATE_PAYMENT_REFERENCES")
            calculated_score += cls.RULES_DEFINITION["DUPLICATE_PAYMENT_REFERENCES"]["weight"]
            supporting_events.extend(sorted({str(x["stripePaymentIntentId"]) for x in shared})[:5])

        # 2. Rule: EXCESSIVE_BOOKING_RATE
        recent_bookings = list(db["appointments"].find({
            "patientUserId": account_id,
            "createdAt": {"$gte": hour_ago},
        }))
        if len(recent_bookings) > 5:
            triggered_rules.append("EXCESSIVE_BOOKING_RATE")
            calculated_score += cls.RULES_DEFINITION["EXCESSIVE_BOOKING_RATE"]["weight"]
            supporting_events.extend([str(b.get("_id")) for b in recent_bookings[:5]])

        # 3. Rule: RAPID_CANCELLATION_PATTERN
        cancellations = list(db["appointments"].find({
            "patientUserId": account_id,
            "status": "CANCELLED",
            "updatedAt": {"$gte": day_ago},
        }))
        if len(cancellations) > 3:
            triggered_rules.append("RAPID_CANCELLATION_PATTERN")
            calculated_score += cls.RULES_DEFINITION["RAPID_CANCELLATION_PATTERN"]["weight"]
            supporting_events.extend([str(c.get("_id")) for c in cancellations[:5]])

        # 4. Rule: EXCESSIVE_REFUND_REQUESTS
        refunds = list(db["refund_requests"].find({
            "patientUserId": account_id,
            "createdAt": {"$gte": week_ago},
        }))
        if len(refunds) > 2:
            triggered_rules.append("EXCESSIVE_REFUND_REQUESTS")
            calculated_score += cls.RULES_DEFINITION["EXCESSIVE_REFUND_REQUESTS"]["weight"]
            supporting_events.extend([str(r.get("refundId") or r.get("_id")) for r in refunds[:5]])

        # 5. Rule: UNAUTHORIZED_ACCESS_BURST
        # Events typed in by an administrator (POST /security/events) are not evidence about the account.
        auth_failures = list(db["security_events"].find({
            "actorId": account_id,
            "category": {"$in": ["AUTH_FAILURE", "UNAUTHORIZED_ACCESS"]},
            "timestamp": {"$gte": fifteen_mins_ago},
            "metadata.source": {"$ne": "manual_admin_entry"},
        }))
        if len(auth_failures) >= 5:
            triggered_rules.append("UNAUTHORIZED_ACCESS_BURST")
            calculated_score += cls.RULES_DEFINITION["UNAUTHORIZED_ACCESS_BURST"]["weight"]
            supporting_events.extend([str(af.get("eventId")) for af in auth_failures[:5]])

        # Cap score at 100.0
        calculated_score = min(calculated_score, 100.0)

        # Do not create an assessment if risk is negligible (< 25.0)
        if calculated_score < 25.0 or not triggered_rules:
            return None

        risk_level = cls._compute_risk_level(calculated_score)
        target_entity = entity_ref or f"ACCOUNT-{account_id}"

        # Deduplication: check if an active assessment already exists
        existing = db["fraud_risk_assessments"].find_one({
            "relatedAccountId": account_id,
            "reviewStatus": {"$in": [FraudReviewStatus.DETECTED.value, FraudReviewStatus.AWAITING_REVIEW.value, FraudReviewStatus.INVESTIGATING.value]},
        })

        if existing:
            # Update existing assessment score and triggers without creating duplicate alert
            db["fraud_risk_assessments"].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "riskScore": calculated_score,
                        "riskLevel": risk_level.value,
                        "triggeredRules": triggered_rules,
                        "supportingEventReferences": supporting_events,
                        "updatedAt": now,
                    }
                },
            )
            existing["_id"] = str(existing["_id"])
            existing["riskScore"] = calculated_score
            existing["riskLevel"] = risk_level.value
            return FraudAssessmentDocument(**existing)

        # Explanation: the score is the sum of fixed rule weights, not a probability, and a signal is not proof.
        explanation = (
            f"Rule weight total {calculated_score:.1f}/100 ({risk_level.value}). "
            f"Triggered {len(triggered_rules)} deterministic rule(s): {', '.join(triggered_rules)}. "
            f"Supported by {len(supporting_events)} event reference(s). These are signals for human review, "
            f"not a finding of fraud; no account action is taken automatically."
        )

        assessment = FraudAssessmentDocument(
            assessmentId=f"FRAUD-{uuid4().hex[:10].upper()}",
            relatedAccountId=account_id,
            relatedEntityReference=target_entity,
            riskScore=calculated_score,
            riskLevel=risk_level,
            triggeredRules=triggered_rules,
            supportingEventReferences=supporting_events,
            explanation=explanation,
            reviewStatus=FraudReviewStatus.AWAITING_REVIEW,
            createdAt=now,
            updatedAt=now,
        )

        db["fraud_risk_assessments"].insert_one(document_for_insert(assessment))  # never "_id": None (P04-N20)

        # Log security audit event for high/critical fraud scores
        if risk_level in (FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL):
            SecurityEventService.record_security_event(
                category=SecurityEventCategory.SUSPICIOUS_PAYMENT,
                severity=SecuritySeverity.HIGH if risk_level == FraudRiskLevel.HIGH else SecuritySeverity.CRITICAL,
                description=f"High fraud risk detected for account {account_id}: score {calculated_score:.1f}",
                actor_id=account_id,
                metadata={"assessmentId": assessment.assessmentId, "rules": triggered_rules},
                db=db,
            )

        return assessment

    @classmethod
    def review_assessment(
        cls,
        assessment_id: str,
        decision: str,
        admin_id: str,
        notes: str,
        action_required: Optional[str] = None,
        db: Optional[Database] = None,
    ) -> Optional[FraudAssessmentDocument]:
        """Admin review of flagged fraud assessment."""
        if db is None:
            db = get_database()

        assessment = db["fraud_risk_assessments"].find_one({"assessmentId": assessment_id})
        if not assessment:
            return None

        status_map = {
            "dismiss": FraudReviewStatus.DISMISSED.value,
            "confirm": FraudReviewStatus.CONFIRMED.value,
            "investigate": FraudReviewStatus.INVESTIGATING.value,
            "resolve": FraudReviewStatus.RESOLVED.value,
        }
        # An unknown decision was silently recorded as "investigating" (P04-N12).
        new_status = status_map.get((decision or "").strip().lower())
        if new_status is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="decision must be dismiss, confirm, investigate or resolve.")

        investigation_entry = {
            "adminId": admin_id,
            "decision": decision,
            "notes": notes,
            "actionRequired": action_required,
            "timestamp": utc_now(),
        }

        db["fraud_risk_assessments"].update_one(
            {"assessmentId": assessment_id},
            {
                "$set": {
                    "reviewStatus": new_status,
                    "assignedAdminId": admin_id,
                    "updatedAt": utc_now(),
                },
                "$push": {"investigationNotes": investigation_entry},
            },
        )

        from app.services.admin_audit_service import AdminAuditService
        AdminAuditService.log_action(
            db=db, actor_id=admin_id, actor_role="ADMIN", action_type="FRAUD_REVIEW_DECISION",
            target_id=assessment_id, target_type="fraud_assessment", previous_state=assessment.get("reviewStatus"),
            new_state=new_status, reason=notes,
            metadata={"relatedAccountId": assessment.get("relatedAccountId"), "accountActionTaken": False},
        )
        updated = db["fraud_risk_assessments"].find_one({"assessmentId": assessment_id})
        updated["_id"] = str(updated["_id"])
        return FraudAssessmentDocument(**updated)

    @classmethod
    def list_assessments(
        cls,
        status: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
        db: Optional[Database] = None,
    ) -> Dict[str, Any]:
        """Query fraud assessments with filters."""
        if db is None:
            db = get_database()

        query: Dict[str, Any] = {}
        if status:
            query["reviewStatus"] = status
        if risk_level:
            query["riskLevel"] = risk_level

        total = db["fraud_risk_assessments"].count_documents(query)
        cursor = db["fraud_risk_assessments"].find(query).sort("createdAt", -1).skip(skip).limit(limit)

        items = []
        for doc in cursor:
            doc["_id"] = str(doc.get("_id"))
            items.append(FraudAssessmentDocument(**doc))

        return {"items": items, "total": total}
