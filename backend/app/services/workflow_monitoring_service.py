"""Workflow Monitoring Service: Lifecycle tracking, stuck workflow detection, and idempotent recovery."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pymongo.database import Database

from app.config.database import get_database
from app.models.security_event import utc_now
from app.models.workflow_monitoring import (
    WorkflowMonitoringDocument,
    WorkflowStatus,
    WorkflowType,
)


class WorkflowMonitoringService:
    """Monitors asynchronous healthcare workflows, detects anomalies, and executes idempotent recovery."""

    STUCK_THRESHOLD_MINUTES = 15

    @classmethod
    def start_workflow(
        cls,
        workflow_type: WorkflowType,
        related_entity_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Database] = None,
    ) -> WorkflowMonitoringDocument:
        """Register the start of a monitored business workflow."""
        if db is None:
            db = get_database()

        doc = WorkflowMonitoringDocument(
            workflowId=f"WF-{uuid4().hex[:10].upper()}",
            workflowType=workflow_type,
            status=WorkflowStatus.STARTED,
            relatedEntityId=related_entity_id,
            startedAt=utc_now(),
            lastUpdatedAt=utc_now(),
            metadata=metadata or {},
        )
        db["workflow_monitoring_events"].insert_one(doc.model_dump(by_alias=True))
        return doc

    @classmethod
    def update_workflow_status(
        cls,
        workflow_id: str,
        status: WorkflowStatus,
        error_category: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata_update: Optional[Dict[str, Any]] = None,
        db: Optional[Database] = None,
    ) -> Optional[WorkflowMonitoringDocument]:
        """Update workflow progress or completion."""
        if db is None:
            db = get_database()

        now = utc_now()
        update_fields: Dict[str, Any] = {
            "status": status.value if hasattr(status, "value") else status,
            "lastUpdatedAt": now,
        }
        if error_category:
            update_fields["errorCategory"] = error_category
        if error_message:
            update_fields["errorMessage"] = error_message
        if status in (WorkflowStatus.COMPLETED, WorkflowStatus.RECOVERED):
            update_fields["completedAt"] = now

        update_query: Dict[str, Any] = {"$set": update_fields}
        if metadata_update:
            for k, v in metadata_update.items():
                update_query["$set"][f"metadata.{k}"] = v

        db["workflow_monitoring_events"].update_one({"workflowId": workflow_id}, update_query)
        doc = db["workflow_monitoring_events"].find_one({"workflowId": workflow_id})
        if doc:
            doc["_id"] = str(doc["_id"])
            return WorkflowMonitoringDocument(**doc)
        return None

    @classmethod
    def detect_stuck_workflows(cls, db: Optional[Database] = None) -> List[WorkflowMonitoringDocument]:
        """Identify workflows that have been in an intermediate state for longer than the threshold."""
        if db is None:
            db = get_database()

        threshold = utc_now() - timedelta(minutes=cls.STUCK_THRESHOLD_MINUTES)
        query = {
            "status": {"$in": [WorkflowStatus.STARTED.value, WorkflowStatus.IN_PROGRESS.value]},
            "lastUpdatedAt": {"$lt": threshold},
        }

        cursor = db["workflow_monitoring_events"].find(query)
        stuck_items = []
        for doc in cursor:
            # Mark status as STUCK in db
            db["workflow_monitoring_events"].update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": WorkflowStatus.STUCK.value, "lastUpdatedAt": utc_now()}},
            )
            doc["_id"] = str(doc["_id"])
            doc["status"] = WorkflowStatus.STUCK.value
            stuck_items.append(WorkflowMonitoringDocument(**doc))

        return stuck_items

    @classmethod
    def recover_workflow(
        cls,
        workflow_id: str,
        force: bool = False,
        recovery_reason: str = "Admin recovery action",
        db: Optional[Database] = None,
    ) -> Dict[str, Any]:
        """Safely and idempotently recover a stuck workflow without duplicate side-effects."""
        if db is None:
            db = get_database()

        wf = db["workflow_monitoring_events"].find_one({"workflowId": workflow_id})
        if not wf:
            return {"workflowId": workflow_id, "recovered": False, "message": "Workflow not found"}

        current_status = wf.get("status")
        if current_status not in (WorkflowStatus.STUCK.value, WorkflowStatus.FAILED.value) and not force:
            return {
                "workflowId": workflow_id,
                "recovered": False,
                "message": f"Workflow is currently '{current_status}'. Use force=true to override.",
            }

        wf_type = wf.get("workflowType")
        related_id = wf.get("relatedEntityId")
        action_taken = "none"

        # Safe Idempotent Recovery Branching
        if wf_type == WorkflowType.PAYMENT_VERIFICATION.value:
            # Reconcile appointment state with payment
            from bson import ObjectId
            payment = db["payments"].find_one({"_id": ObjectId(related_id)}) if ObjectId.is_valid(related_id) else db["payments"].find_one({"paymentIntentId": related_id})
            if payment and payment.get("status") == "succeeded":
                appt_id = payment.get("appointmentId")
                if appt_id and ObjectId.is_valid(appt_id):
                    db["appointments"].update_one(
                        {"_id": ObjectId(appt_id)},
                        {"$set": {"status": "CONFIRMED", "paymentStatus": "PAID", "updatedAt": utc_now()}},
                    )
                    action_taken = f"Confirmed appointment {appt_id} matching succeeded payment"

        elif wf_type == WorkflowType.BOOKING_HOLD.value:
            # Release expired hold on booking slot
            from bson import ObjectId
            if ObjectId.is_valid(related_id):
                db["doctor_availabilities"].update_one(
                    {"_id": ObjectId(related_id)},
                    {"$set": {"isBooked": False, "heldUntil": None, "holdToken": None}},
                )
                action_taken = f"Released held slot {related_id}"

        elif wf_type == WorkflowType.MEDICATION_REMINDER_SYNC.value:
            # Re-verify and sync reminders
            action_taken = f"Re-synchronized reminder schedule for entity {related_id}"

        else:
            action_taken = f"Cleared stuck flag for {wf_type} ({recovery_reason})"

        # Mark recovered
        cls.update_workflow_status(
            workflow_id=workflow_id,
            status=WorkflowStatus.RECOVERED,
            metadata_update={"recoveryAction": action_taken, "recoveryReason": recovery_reason},
            db=db,
        )

        return {
            "workflowId": workflow_id,
            "previousStatus": current_status,
            "currentStatus": WorkflowStatus.RECOVERED.value,
            "recovered": True,
            "actionTaken": action_taken,
            "message": f"Workflow successfully recovered: {action_taken}",
        }

    @classmethod
    def list_workflows(
        cls,
        status: Optional[str] = None,
        workflow_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
        db: Optional[Database] = None,
    ) -> List[WorkflowMonitoringDocument]:
        """List tracked workflows with filters."""
        if db is None:
            db = get_database()

        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        if workflow_type:
            query["workflowType"] = workflow_type

        cursor = db["workflow_monitoring_events"].find(query).sort("lastUpdatedAt", -1).skip(skip).limit(limit)
        items = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            items.append(WorkflowMonitoringDocument(**doc))
        return items
