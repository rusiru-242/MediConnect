"""Incident Management Service: Lifecycle management, deduplication, and AI investigation assistance."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pymongo.database import Database

from app.config.database import get_database
from app.models.operational_incident import (
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    OperationalIncidentDocument,
    utc_now,
)


class IncidentManagementService:
    """Manages operational incidents from detection through acknowledgment, investigation, and resolution."""

    @classmethod
    def create_incident(
        cls,
        title: str,
        category: IncidentCategory,
        severity: IncidentSeverity,
        description: str,
        affected_service: str,
        supporting_events: Optional[List[str]] = None,
        db: Optional[Database] = None,
    ) -> OperationalIncidentDocument:
        """Create and persist an operational incident, preventing duplicates for active identical issues."""
        if db is None:
            db = get_database()

        # Deduplication: check if active incident exists for same service and category
        cat_val = category.value if hasattr(category, "value") else str(category)
        sev_val = severity.value if hasattr(severity, "value") else str(severity)

        existing = db["operational_incidents"].find_one({
            "affectedService": affected_service,
            "category": cat_val,
            "status": {"$in": [IncidentStatus.OPEN.value, IncidentStatus.ACKNOWLEDGED.value, IncidentStatus.INVESTIGATING.value]},
        })

        if existing:
            # Append supporting events and update description if needed
            existing_events = existing.get("supportingEventReferences") or []
            new_events = list(dict.fromkeys(existing_events + (supporting_events or [])))
            db["operational_incidents"].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "supportingEventReferences": new_events,
                        "severity": sev_val,
                    }
                },
            )
            existing["_id"] = str(existing["_id"])
            existing["severity"] = sev_val
            existing["supportingEventReferences"] = new_events
            return OperationalIncidentDocument(**existing)

        incident = OperationalIncidentDocument(
            incidentId=f"INC-{uuid4().hex[:10].upper()}",
            title=title,
            category=category,
            severity=severity,
            status=IncidentStatus.OPEN,
            description=description,
            affectedService=affected_service,
            supportingEventReferences=supporting_events or [],
            createdAt=utc_now(),
        )

        db["operational_incidents"].insert_one(incident.model_dump(by_alias=True))
        return incident

    @classmethod
    def acknowledge_incident(
        cls,
        incident_id: str,
        admin_id: str,
        db: Optional[Database] = None,
    ) -> Optional[OperationalIncidentDocument]:
        """Mark an incident as acknowledged by an assigned admin."""
        if db is None:
            db = get_database()

        now = utc_now()
        db["operational_incidents"].update_one(
            {"incidentId": incident_id},
            {
                "$set": {
                    "status": IncidentStatus.ACKNOWLEDGED.value,
                    "assignedAdminId": admin_id,
                    "acknowledgedAt": now,
                }
            },
        )
        doc = db["operational_incidents"].find_one({"incidentId": incident_id})
        if doc:
            doc["_id"] = str(doc["_id"])
            return OperationalIncidentDocument(**doc)
        return None

    @classmethod
    def resolve_incident(
        cls,
        incident_id: str,
        admin_id: str,
        resolution_notes: str,
        db: Optional[Database] = None,
    ) -> Optional[OperationalIncidentDocument]:
        """Mark an incident as resolved with justification notes."""
        if db is None:
            db = get_database()

        now = utc_now()
        db["operational_incidents"].update_one(
            {"incidentId": incident_id},
            {
                "$set": {
                    "status": IncidentStatus.RESOLVED.value,
                    "assignedAdminId": admin_id,
                    "resolutionNotes": resolution_notes,
                    "resolvedAt": now,
                }
            },
        )
        doc = db["operational_incidents"].find_one({"incidentId": incident_id})
        if doc:
            doc["_id"] = str(doc["_id"])
            return OperationalIncidentDocument(**doc)
        return None

    @classmethod
    def list_incidents(
        cls,
        status: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
        db: Optional[Database] = None,
    ) -> Dict[str, Any]:
        """List incidents with status, category, and severity filtering."""
        if db is None:
            db = get_database()

        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        if category:
            query["category"] = category
        if severity:
            query["severity"] = severity

        total = db["operational_incidents"].count_documents(query)
        cursor = db["operational_incidents"].find(query).sort("createdAt", -1).skip(skip).limit(limit)

        items = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            items.append(OperationalIncidentDocument(**doc))

        return {"items": items, "total": total}

    @classmethod
    def generate_ai_incident_summary(cls, incident_id: str, db: Optional[Database] = None) -> Dict[str, Any]:
        """Generate a deterministic, structured incident investigation narrative and action plan."""
        if db is None:
            db = get_database()

        doc = db["operational_incidents"].find_one({"incidentId": incident_id})
        if not doc:
            return {"error": "incident_not_found"}

        title = doc.get("title", "")
        cat = doc.get("category", "")
        sev = doc.get("severity", "")
        svc = doc.get("affectedService", "")
        desc = doc.get("description", "")
        events = doc.get("supportingEventReferences", [])

        suggested_steps = [
            f"Inspect recent error logs for service '{svc}'",
            "Verify network reachability and database connection pool health",
            "Check for any related stuck workflows or payment discrepancies",
            "Acknowledge the incident in the Admin Console to notify the engineering team",
        ]

        if cat == "PAYMENT":
            suggested_steps.insert(0, "Cross-reference Stripe dashboard webhooks and verify idempotency keys")
        elif cat == "NOTIFICATION":
            suggested_steps.insert(0, "Check Twilio / SMTP outbound quotas and examine Dead-Letter Queue items")
        elif cat == "AI_PROVIDER":
            suggested_steps.insert(0, "Check AI Provider circuit breaker status and verify bilingual fallback response")

        summary = (
            f"Incident {incident_id} [{sev}] in service '{svc}': {title}. "
            f"Category: {cat}. Details: {desc}. "
            f"Identified {len(events)} supporting correlation events."
        )

        return {
            "incidentId": incident_id,
            "title": title,
            "category": cat,
            "severity": sev,
            "affectedService": svc,
            "summary": summary,
            "suggestedInvestigationSteps": suggested_steps,
        }
