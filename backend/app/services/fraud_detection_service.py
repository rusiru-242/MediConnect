"""Fraud Detection Service: Rule-based explainable risk scoring, deduplication, and admin review workflow."""

from app.utils.mongo_documents import document_for_insert
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

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
            # A05: evaluated from the account's own unpaid reservations (expired, released before payment, or still
            # held). Weight 25 so the rule alone reaches the MEDIUM review tier; it was 20 and declared only (P04-N12).
            "weight": 25.0,
            "description": "Several distinct appointment slots reserved and left unpaid within the observation window.",
        },
        "UNAUTHORIZED_ACCESS_BURST": {
            "weight": 35.0,
            "description": "5 or more authorization failures within a 15-minute window.",
        },
    }

    OPEN_STATUSES = (FraudReviewStatus.DETECTED.value, FraudReviewStatus.AWAITING_REVIEW.value,
                     FraudReviewStatus.INVESTIGATING.value)
    CLOSED_STATUSES = (FraudReviewStatus.DISMISSED.value, FraudReviewStatus.CONFIRMED.value,
                       FraudReviewStatus.RESOLVED.value)

    @classmethod
    def _compute_risk_level(cls, score: float) -> FraudRiskLevel:
        if score >= 75.0:
            return FraudRiskLevel.CRITICAL
        elif score >= 50.0:
            return FraudRiskLevel.HIGH
        elif score >= 25.0:
            return FraudRiskLevel.MEDIUM
        return FraudRiskLevel.LOW

    @staticmethod
    def _aware(value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @classmethod
    def slot_hoarding_evidence(cls, db: Database, account_id: str, since: datetime) -> Dict[str, Any]:
        """A05 (Agent 25): unpaid reservations of distinct slots that the account held without paying.

        Counted: holds that expired unpaid (released by the system), holds the patient released before paying, and
        holds still open and unpaid. Not counted: paid or confirmed bookings, free bookings, and cancellations by a
        doctor or administrator. Repeated attempts on the *same* slot (a payment retry after a card failure or a
        network error) count once, because the rule counts distinct slots.
        """
        rows = []
        cursor = db["appointments"].find(
            {"patientUserId": account_id, "createdAt": {"$gte": since},
             "paymentStatus": {"$nin": ["PAID", "NOT_REQUIRED", "REFUNDED", "PARTIALLY_REFUNDED"]},
             "confirmedAt": None},
            {"doctorUserId": 1, "appointmentDate": 1, "startTime": 1, "status": 1, "cancelledBy": 1,
             "cancellationReason": 1, "holdReleasedAt": 1, "createdAt": 1}).sort("createdAt", 1).limit(500)
        for appt in cursor:
            status_value = appt.get("status")
            if status_value in {"HOLD", "PENDING"}:
                outcome = "held_unpaid"
            elif status_value == "CANCELLED" and appt.get("holdReleasedAt"):
                outcome = "released_before_payment"
            elif (status_value == "CANCELLED" and appt.get("cancelledBy") == "SYSTEM"
                  and appt.get("cancellationReason") == "Booking hold expired"):
                outcome = "expired_unpaid"
            else:
                continue
            rows.append({"appointmentId": str(appt["_id"]), "doctorUserId": str(appt.get("doctorUserId") or ""),
                         "slot": f"{appt.get('appointmentDate')} {appt.get('startTime')} (Asia/Colombo)",
                         "outcome": outcome, "reservedAt": cls._aware(appt.get("createdAt"))})
        slots = {(r["doctorUserId"], r["slot"]) for r in rows}
        return {"rows": rows, "distinctSlots": len(slots)}

    @classmethod
    def evaluate_account_risk(
        cls,
        account_id: str,
        entity_ref: Optional[str] = None,
        db: Optional[Database] = None,
        now: Optional[datetime] = None,
    ) -> Optional[FraudAssessmentDocument]:
        """Evaluate real behavioral signals against deterministic risk rules."""
        if db is None:
            db = get_database()
        from app.config.settings import settings

        now = now or utc_now()
        # A05-BUG-003: after a reviewer closed an assessment, the same evidence raised a new alert on the next
        # evaluation. Only activity after the latest closing decision counts towards a new signal.
        last_closed = next(iter(db["fraud_risk_assessments"].find(
            {"relatedAccountId": account_id, "reviewStatus": {"$in": list(cls.CLOSED_STATUSES)}}
        ).sort("updatedAt", -1).limit(1)), None)
        reviewed_until = cls._aware(last_closed.get("updatedAt")) if last_closed else None

        def since(delta: timedelta) -> datetime:
            start = now - delta
            return max(start, reviewed_until) if reviewed_until else start

        day_ago = since(timedelta(hours=24))
        hour_ago = since(timedelta(hours=1))
        fifteen_mins_ago = since(timedelta(minutes=15))
        week_ago = since(timedelta(days=7))

        triggered_rules: List[str] = []
        supporting_events: List[str] = []
        rule_evidence: List[Dict[str, Any]] = []
        score = {"value": 0.0}

        def trigger(rule: str, threshold: str, observed: Any, references: List[str], items=None) -> None:
            triggered_rules.append(rule)
            score["value"] += cls.RULES_DEFINITION[rule]["weight"]
            supporting_events.extend(references[:5])
            entry = {"rule": rule, "description": cls.RULES_DEFINITION[rule]["description"],
                     "threshold": threshold, "observed": observed, "references": references[:10]}
            if items is not None:
                entry["items"] = items[:20]
            rule_evidence.append(entry)

        # 1. Rule: MULTIPLE_FAILED_PAYMENTS
        # Payment statuses are upper case; the former lower-case "failed" never matched, so this rule could never
        # fire (P04-N12).
        failed_payments = list(db["payments"].find({
            "patientUserId": account_id,
            "status": "FAILED",
            "createdAt": {"$gte": day_ago},
        }))
        if len(failed_payments) >= 3:
            trigger("MULTIPLE_FAILED_PAYMENTS", "3 or more in 24 hours", len(failed_payments),
                    [str(p.get("stripePaymentIntentId") or p.get("paymentIntentId") or p.get("_id"))
                     for p in failed_payments])

        # 1b. Rule: DUPLICATE_PAYMENT_REFERENCES - this account's PaymentIntent is also recorded for another account.
        intent_query: Dict[str, Any] = {"patientUserId": account_id, "stripePaymentIntentId": {"$nin": [None, ""]}}
        if reviewed_until:
            intent_query["createdAt"] = {"$gte": reviewed_until}
        own_intents = [p["stripePaymentIntentId"] for p in db["payments"].find(intent_query, {"stripePaymentIntentId": 1})]
        shared = list(db["payments"].find({"stripePaymentIntentId": {"$in": own_intents},
                                           "patientUserId": {"$ne": account_id}}, {"stripePaymentIntentId": 1})) if own_intents else []
        if shared:
            refs = sorted({str(x["stripePaymentIntentId"]) for x in shared})
            trigger("DUPLICATE_PAYMENT_REFERENCES", "any payment reference shared with another account", len(refs), refs)

        # 2. Rule: EXCESSIVE_BOOKING_RATE
        recent_bookings = list(db["appointments"].find({
            "patientUserId": account_id,
            "createdAt": {"$gte": hour_ago},
        }, {"_id": 1}))
        if len(recent_bookings) > 5:
            trigger("EXCESSIVE_BOOKING_RATE", "more than 5 in 1 hour", len(recent_bookings),
                    [str(b.get("_id")) for b in recent_bookings])

        # 3. Rule: RAPID_CANCELLATION_PATTERN
        # A05-BUG-010: released or expired unpaid holds were counted as cancellations, so a patient who retried a
        # failed card payment a few times on one slot raised this signal. Only the patient's own cancellations of
        # bookings count here; unpaid holds are assessed by SLOT_HOARDING_ATTEMPT (distinct slots).
        cancellations = list(db["appointments"].find({
            "patientUserId": account_id,
            "status": "CANCELLED",
            "cancelledBy": "PATIENT",
            "holdReleasedAt": None,
            "updatedAt": {"$gte": day_ago},
        }, {"_id": 1}))
        if len(cancellations) > 3:
            trigger("RAPID_CANCELLATION_PATTERN", "more than 3 in 24 hours", len(cancellations),
                    [str(c.get("_id")) for c in cancellations])

        # 4. Rule: EXCESSIVE_REFUND_REQUESTS
        refunds = list(db["refund_requests"].find({
            "patientUserId": account_id,
            "createdAt": {"$gte": week_ago},
        }))
        if len(refunds) > 2:
            trigger("EXCESSIVE_REFUND_REQUESTS", "more than 2 in 7 days", len(refunds),
                    [str(r.get("refundId") or r.get("_id")) for r in refunds])

        # 4b. Rule: SLOT_HOARDING_ATTEMPT (A05).
        window_hours = max(1, int(settings.FRAUD_SLOT_HOARDING_WINDOW_HOURS))
        min_slots = max(2, int(settings.FRAUD_SLOT_HOARDING_MIN_SLOTS))
        hoarding = cls.slot_hoarding_evidence(db, account_id, since(timedelta(hours=window_hours)))
        if hoarding["distinctSlots"] >= min_slots:
            trigger("SLOT_HOARDING_ATTEMPT",
                    f"{min_slots} or more distinct slots held unpaid within {window_hours} hours (provisional)",
                    hoarding["distinctSlots"], [r["appointmentId"] for r in hoarding["rows"]], items=hoarding["rows"])

        # 5. Rule: UNAUTHORIZED_ACCESS_BURST
        # Events typed in by an administrator (POST /security/events) are not evidence about the account.
        auth_failures = list(db["security_events"].find({
            "actorId": account_id,
            "category": {"$in": ["AUTH_FAILURE", "UNAUTHORIZED_ACCESS"]},
            "timestamp": {"$gte": fifteen_mins_ago},
            "metadata.source": {"$ne": "manual_admin_entry"},
        }))
        if len(auth_failures) >= 5:
            trigger("UNAUTHORIZED_ACCESS_BURST", "5 or more in 15 minutes", len(auth_failures),
                    [str(af.get("eventId")) for af in auth_failures])

        # Cap score at 100.0
        calculated_score = min(score["value"], 100.0)

        # Do not create an assessment if risk is negligible (< 25.0)
        if calculated_score < 25.0 or not triggered_rules:
            return None

        risk_level = cls._compute_risk_level(calculated_score)
        target_entity = entity_ref or f"ACCOUNT-{account_id}"

        # Explanation: the score is the sum of fixed rule weights, not a probability, and a signal is not proof.
        explanation = (
            f"Rule weight total {calculated_score:.1f}/100 ({risk_level.value}). "
            f"Triggered {len(triggered_rules)} deterministic rule(s): {', '.join(triggered_rules)}. "
            f"Supported by {len(supporting_events)} event reference(s). These are signals for human review, "
            f"not a finding of fraud; no account action is taken automatically."
        )
        refresh = {"riskScore": calculated_score, "riskLevel": risk_level.value, "triggeredRules": triggered_rules,
                   "supportingEventReferences": supporting_events, "ruleEvidence": rule_evidence,
                   "explanation": explanation, "updatedAt": now}

        def refresh_open() -> Optional[FraudAssessmentDocument]:
            # Re-evaluation refreshes the open assessment instead of creating a duplicate alert (P04-N22).
            existing = db["fraud_risk_assessments"].find_one_and_update(
                {"relatedAccountId": account_id, "reviewStatus": {"$in": list(cls.OPEN_STATUSES)}},
                {"$set": refresh}, sort=[("createdAt", 1)], return_document=ReturnDocument.AFTER)
            if not existing:
                return None
            existing["_id"] = str(existing["_id"])
            return FraudAssessmentDocument(**existing)

        refreshed = refresh_open()
        if refreshed:
            return refreshed

        assessment = FraudAssessmentDocument(
            assessmentId=f"FRAUD-{uuid4().hex[:10].upper()}",
            relatedAccountId=account_id,
            relatedEntityReference=target_entity,
            riskScore=calculated_score,
            riskLevel=risk_level,
            triggeredRules=triggered_rules,
            supportingEventReferences=supporting_events,
            ruleEvidence=rule_evidence,
            explanation=explanation,
            reviewStatus=FraudReviewStatus.AWAITING_REVIEW,
            createdAt=now,
            updatedAt=now,
        )

        try:
            # never "_id": None (P04-N20); openKey makes a concurrent second insert fail (A05-BUG-002)
            db["fraud_risk_assessments"].insert_one({**document_for_insert(assessment), "openKey": account_id})
        except DuplicateKeyError:
            return refresh_open()

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

    _last_sweep_at: Optional[datetime] = None

    @classmethod
    def run_detection_sweep(cls, db: Database, now: Optional[datetime] = None, *, force: bool = False,
                            limit: int = 200) -> Dict[str, int]:
        """A05-BUG-001: evaluate recently active accounts from the background worker.

        Before A05 the rules ran only when an administrator called the evaluate endpoint with an account id, so no
        signal appeared unless the account was already suspected. The sweep reads only stored records, takes no
        account, booking or payment action, and is safe to repeat: concurrent or repeated runs refresh the one open
        assessment per account (unique ``openKey``). It is stateless, so a backend restart only makes it run again.
        """
        from app.config.settings import settings
        now = now or utc_now()
        interval = int(settings.FRAUD_SWEEP_INTERVAL_SECONDS)
        if not force:
            if interval <= 0:
                return {"skipped": 1}
            if cls._last_sweep_at and (now - cls._last_sweep_at).total_seconds() < interval:
                return {"skipped": 1}
        cls._last_sweep_at = now
        window = timedelta(hours=max(24, int(settings.FRAUD_SLOT_HOARDING_WINDOW_HOURS)))
        accounts = set(db["appointments"].distinct("patientUserId", {"createdAt": {"$gte": now - window}}))
        accounts |= set(db["appointments"].distinct("patientUserId", {"updatedAt": {"$gte": now - window},
                                                                      "status": "CANCELLED"}))
        accounts |= set(db["payments"].distinct("patientUserId", {"createdAt": {"$gte": now - window}}))
        accounts |= set(db["refund_requests"].distinct("patientUserId",
                                                       {"createdAt": {"$gte": now - timedelta(days=7)}}))
        accounts |= set(db["security_events"].distinct("actorId", {
            "category": {"$in": ["AUTH_FAILURE", "UNAUTHORIZED_ACCESS"]},
            "timestamp": {"$gte": now - timedelta(minutes=15)}}))
        stats = {"evaluated": 0, "flagged": 0}
        for account_id in sorted(str(a) for a in accounts if a)[:limit]:
            stats["evaluated"] += 1
            if cls.evaluate_account_risk(account_id, db=db, now=now):
                stats["flagged"] += 1
        return stats

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

        update: Dict[str, Any] = {
            "$set": {
                "reviewStatus": new_status,
                "assignedAdminId": admin_id,
                "updatedAt": utc_now(),
            },
            "$push": {"investigationNotes": investigation_entry},
        }
        if new_status in cls.CLOSED_STATUSES:
            # A closed assessment no longer blocks a new one for later activity (A05-BUG-002/003).
            update["$unset"] = {"openKey": ""}
        elif assessment.get("reviewStatus") in cls.CLOSED_STATUSES:
            # Reopening a closed assessment makes it the account's open one again.
            update["$set"]["openKey"] = assessment.get("relatedAccountId") or assessment_id
        try:
            db["fraud_risk_assessments"].update_one({"assessmentId": assessment_id}, update)
        except DuplicateKeyError:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="This account already has an open assessment. "
                                                        "Review that one instead of reopening this.")

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
