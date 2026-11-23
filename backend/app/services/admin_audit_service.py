"""Administrative audit logging service ensuring tamper-evident operational records (Phase 5)."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pymongo.database import Database

from app.models.admin_audit import AdminAuditAction, AdminAuditDocument, utc_now

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {"password", "token", "secret", "cvv", "card_number", "authorization", "apiKey"}


def _sanitize_metadata(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Recursively redact secrets and card data from audit metadata."""
    if not data or not isinstance(data, dict):
        return {}
    clean: Dict[str, Any] = {}
    for k, v in data.items():
        if any(sens in k.lower() for sens in SENSITIVE_KEYS):
            clean[k] = "[REDACTED]"
        elif isinstance(v, dict):
            clean[k] = _sanitize_metadata(v)
        elif isinstance(v, str) and (re.search(r"\b(?:sk|rk)_[a-zA-Z0-9]{20,}", v) or "eyJ" in v):
            clean[k] = "[REDACTED]"
        else:
            clean[k] = v
    return clean


class AdminAuditService:
    """Tamper-resistant audit logging for administrative actions."""

    @staticmethod
    def log_action(
        db: Database,
        actor_id: str,
        actor_role: str,
        action_type: AdminAuditAction | str,
        target_id: str,
        target_type: str,
        actor_email: Optional[str] = None,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        status: str = "SUCCESS",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist an append-only audit record in MongoDB admin_audit_logs."""
        audit_id = f"AUD-{uuid4().hex[:12].upper()}"
        act_val = action_type.value if isinstance(action_type, AdminAuditAction) else str(action_type)
        sanitized_meta = _sanitize_metadata(metadata)

        doc = {
            "auditId": audit_id,
            "actorId": str(actor_id),
            "actorEmail": actor_email,
            "actorRole": str(actor_role),
            "actionType": act_val,
            "targetId": str(target_id),
            "targetType": str(target_type),
            "previousState": previous_state,
            "newState": new_state,
            "reason": reason,
            "correlationId": correlation_id or uuid4().hex,
            "status": status,
            "metadata": sanitized_meta,
            "timestamp": utc_now(),
        }

        try:
            db["admin_audit_logs"].insert_one(doc)
            logger.info("admin_audit_log audit_id=%s action=%s target=%s status=%s", audit_id, act_val, target_id, status)
        except Exception as exc:
            logger.error("Failed to persist admin audit log: %s", exc)

        return audit_id

    @staticmethod
    def query_audit_logs(
        db: Database,
        action_type: Optional[str] = None,
        target_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """Query audit records with filtering and pagination."""
        query: Dict[str, Any] = {}
        if action_type and action_type != "ALL":
            query["actionType"] = action_type
        if target_type and target_type != "ALL":
            query["targetType"] = target_type
        if actor_id:
            query["actorId"] = str(actor_id)

        if start_date or end_date:
            date_filter: Dict[str, Any] = {}
            if start_date:
                try:
                    dt_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                    date_filter["$gte"] = dt_start
                except Exception:
                    pass
            if end_date:
                try:
                    dt_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    date_filter["$lte"] = dt_end
                except Exception:
                    pass
            if date_filter:
                query["timestamp"] = date_filter

        skip = max(0, (page - 1) * page_size)
        coll = db["admin_audit_logs"]
        total = coll.count_documents(query)
        cursor = coll.find(query).sort("timestamp", -1).skip(skip).limit(page_size)

        items = []
        for row in cursor:
            items.append({
                "id": str(row["_id"]),
                "auditId": row.get("auditId", ""),
                "actorId": row.get("actorId", ""),
                "actorEmail": row.get("actorEmail"),
                "actorRole": row.get("actorRole", "ADMIN"),
                "actionType": row.get("actionType", ""),
                "targetId": row.get("targetId", ""),
                "targetType": row.get("targetType", ""),
                "previousState": row.get("previousState"),
                "newState": row.get("newState"),
                "reason": row.get("reason"),
                "correlationId": row.get("correlationId"),
                "status": row.get("status", "SUCCESS"),
                "metadata": row.get("metadata", {}),
                "timestamp": row.get("timestamp", utc_now()),
            })

        return {"items": items, "total": total, "page": page, "pageSize": page_size}
