"""Customer support ticketing service with AI-assisted drafting and human authorization (Phase 5)."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.admin_audit import AdminAuditAction
from app.models.support_ticket import SupportMessage, SupportTicketDocument, TicketCategory, TicketPriority, TicketStatus, utc_now
from app.services.admin_audit_service import AdminAuditService

logger = logging.getLogger(__name__)

EMERGENCY_KEYWORDS = [
    "chest pain", "shortness of breath", "unconscious", "heavy bleeding",
    "stroke", "heart attack", "suicide", "can't breathe", "cannot breathe",
    "පපුවේ කැක්කුම", "හුස්ම", "மயக்கம்",
]


class SupportTicketService:
    """Manages support ticket workflows, AI drafting, and authorized admin replies."""

    @staticmethod
    def create_ticket(
        db: Database,
        user_id: str,
        user_role: str,
        user_email: str,
        user_name: str,
        subject: str,
        description: str,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        related_entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new customer support ticket."""
        ticket_id = f"TCK-{uuid4().hex[:8].upper()}"
        now = utc_now()

        # Classify priority & category if not provided
        cat_val = category or TicketCategory.GENERAL_SUPPORT.value
        prio_val = priority or TicketPriority.MEDIUM.value

        initial_msg = SupportMessage(
            senderId=str(user_id),
            senderRole=user_role,
            senderName=user_name,
            message=description,
            sentAt=now,
        )

        doc = {
            "ticketId": ticket_id,
            "requesterId": str(user_id),
            "requesterRole": user_role,
            "requesterEmail": user_email,
            "requesterName": user_name,
            "category": cat_val,
            "subject": subject,
            "description": description,
            "status": TicketStatus.OPEN.value,
            "priority": prio_val,
            "assignedAdminId": None,
            "relatedEntityId": related_entity_id,
            "messages": [initial_msg.model_dump()],
            "aiDraft": None,
            "createdAt": now,
            "updatedAt": now,
            "resolvedAt": None,
        }

        db["support_tickets"].insert_one(doc)

        # Generate immediate AI draft and classification
        try:
            draft = SupportTicketService.generate_ai_ticket_draft(db, ticket_id)
            db["support_tickets"].update_one(
                {"ticketId": ticket_id},
                {"$set": {"aiDraft": draft, "category": draft["suggestedCategory"], "priority": draft["suggestedPriority"]}}
            )
            doc["aiDraft"] = draft
            doc["category"] = draft["suggestedCategory"]
            doc["priority"] = draft["suggestedPriority"]
        except Exception as exc:
            logger.warning("Could not pre-generate AI draft for ticket %s: %s", ticket_id, exc)

        return doc

    @staticmethod
    def list_tickets(
        db: Database,
        user_id: Optional[str] = None,
        is_admin: bool = False,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List tickets with role-based access filtering."""
        query: Dict[str, Any] = {}

        if not is_admin:
            if not user_id:
                raise HTTPException(status_code=403, detail="User authentication required.")
            query["requesterId"] = str(user_id)

        if status_filter and status_filter != "ALL":
            query["status"] = status_filter.lower()

        if category and category != "ALL":
            query["category"] = category.lower()

        if priority and priority != "ALL":
            query["priority"] = priority.lower()

        coll = db["support_tickets"]
        total = coll.count_documents(query)
        skip = max(0, (page - 1) * page_size)
        cursor = coll.find(query).sort("createdAt", -1).skip(skip).limit(page_size)

        items = []
        for t in cursor:
            items.append({
                "id": str(t["_id"]),
                "ticketId": t.get("ticketId", ""),
                "requesterId": t.get("requesterId", ""),
                "requesterRole": t.get("requesterRole", "PATIENT"),
                "requesterEmail": t.get("requesterEmail", ""),
                "requesterName": t.get("requesterName", ""),
                "category": t.get("category", TicketCategory.GENERAL_SUPPORT.value),
                "subject": t.get("subject", ""),
                "description": t.get("description", ""),
                "status": t.get("status", TicketStatus.OPEN.value),
                "priority": t.get("priority", TicketPriority.MEDIUM.value),
                "assignedAdminId": t.get("assignedAdminId"),
                "relatedEntityId": t.get("relatedEntityId"),
                "messages": t.get("messages", []),
                "aiDraft": t.get("aiDraft"),
                "createdAt": t.get("createdAt", utc_now()),
                "updatedAt": t.get("updatedAt", utc_now()),
                "resolvedAt": t.get("resolvedAt"),
            })

        return {"items": items, "total": total, "page": page, "pageSize": page_size}

    @staticmethod
    def get_ticket(db: Database, ticket_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Get ticket detail enforcing ownership or admin privileges."""
        query = {"ticketId": ticket_id} if ticket_id.startswith("TCK-") else {"_id": ObjectId(ticket_id)}
        t = db["support_tickets"].find_one(query)
        if not t:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        if not is_admin and str(t.get("requesterId")) != str(user_id):
            raise HTTPException(status_code=403, detail="You do not have permission to view this ticket.")

        return {
            "id": str(t["_id"]),
            "ticketId": t.get("ticketId", ""),
            "requesterId": t.get("requesterId", ""),
            "requesterRole": t.get("requesterRole", "PATIENT"),
            "requesterEmail": t.get("requesterEmail", ""),
            "requesterName": t.get("requesterName", ""),
            "category": t.get("category", TicketCategory.GENERAL_SUPPORT.value),
            "subject": t.get("subject", ""),
            "description": t.get("description", ""),
            "status": t.get("status", TicketStatus.OPEN.value),
            "priority": t.get("priority", TicketPriority.MEDIUM.value),
            "assignedAdminId": t.get("assignedAdminId"),
            "relatedEntityId": t.get("relatedEntityId"),
            "messages": t.get("messages", []),
            "aiDraft": t.get("aiDraft"),
            "createdAt": t.get("createdAt", utc_now()),
            "updatedAt": t.get("updatedAt", utc_now()),
            "resolvedAt": t.get("resolvedAt"),
        }

    @staticmethod
    def generate_ai_ticket_draft(db: Database, ticket_id: str) -> Dict[str, Any]:
        """Perform AI classification and draft professional response with clinical safeguards."""
        query = {"ticketId": ticket_id} if ticket_id.startswith("TCK-") else {"_id": ObjectId(ticket_id)}
        t = db["support_tickets"].find_one(query)
        if not t:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        text_to_analyze = f"{t.get('subject', '')} {t.get('description', '')}".casefold()

        # 1. Emergency symptom detection
        flags = []
        is_emergency = any(kw in text_to_analyze for kw in EMERGENCY_KEYWORDS)
        if is_emergency:
            flags.append("POTENTIAL_MEDICAL_EMERGENCY: Advise immediate emergency care (1990 Suwa Seriya / nearest ER).")

        # 2. Category classification
        if any(w in text_to_analyze for w in ["refund", "money back", "cancelled", "chargeback"]):
            suggested_category = TicketCategory.REFUND_REQUEST.value
        elif any(w in text_to_analyze for w in ["payment", "stripe", "receipt", "deducted", "card", "lkr"]):
            suggested_category = TicketCategory.PAYMENT_ISSUE.value
        elif any(w in text_to_analyze for w in ["appointment", "booking", "reschedule", "doctor visit", "time slot"]):
            suggested_category = TicketCategory.APPOINTMENT_ISSUE.value
        elif any(w in text_to_analyze for w in ["verification", "slmc", "doctor profile", "approval"]):
            suggested_category = TicketCategory.DOCTOR_VERIFICATION.value
        elif any(w in text_to_analyze for w in ["login", "password", "otp", "email verify", "account"]):
            suggested_category = TicketCategory.ACCOUNT_ACCESS.value
        elif any(w in text_to_analyze for w in ["sms", "push notification", "reminder", "bell"]):
            suggested_category = TicketCategory.NOTIFICATION_ISSUE.value
        else:
            suggested_category = TicketCategory.GENERAL_SUPPORT.value

        # 3. Priority determination
        if is_emergency:
            suggested_priority = TicketPriority.URGENT.value
        elif suggested_category in [TicketCategory.REFUND_REQUEST.value, TicketCategory.PAYMENT_ISSUE.value]:
            suggested_priority = TicketPriority.HIGH.value
        elif suggested_category == TicketCategory.DOCTOR_VERIFICATION.value:
            suggested_priority = TicketPriority.MEDIUM.value
        else:
            suggested_priority = TicketPriority.LOW.value

        # 4. Context retrieval
        related_id = t.get("relatedEntityId")
        context_notes = []
        if related_id and ObjectId.is_valid(related_id):
            appt = db["appointments"].find_one({"_id": ObjectId(related_id)})
            if appt:
                context_notes.append(f"Linked appointment status: {appt.get('status')}, Payment: {appt.get('paymentStatus')}")

        # 5. Draft response formulation
        requester_name = t.get("requesterName") or "Valued Patient/User"
        if is_emergency:
            draft_reply = (
                f"Dear {requester_name},\n\n"
                f"We noticed that your message mentions severe symptoms. If you or someone with you is experiencing a medical emergency, "
                f"please call 1990 (Suwa Seriya Ambulance Service in Sri Lanka) immediately or proceed to the nearest hospital Emergency Room.\n\n"
                f"MediConnect customer support cannot provide emergency medical diagnoses. For administrative assistance regarding your account, "
                f"our team is on standby.\n\nWarm regards,\nMediConnect Support Team"
            )
            suggested_resolution = "Escalate to emergency services advisory; follow up after confirmation of patient safety."
        elif suggested_category == TicketCategory.REFUND_REQUEST.value:
            draft_reply = (
                f"Dear {requester_name},\n\n"
                f"Thank you for reaching out regarding your refund request for ticket #{t.get('ticketId')}.\n\n"
                f"Our administrative team has received your inquiry and is reviewing the transaction in accordance with the MediConnect cancellation policy. "
                f"You will receive an automated notification as soon as the review is complete.\n\n"
                f"If you have additional booking details or bank receipts to attach, please reply directly to this message.\n\n"
                f"Warm regards,\nMediConnect Support Team"
            )
            suggested_resolution = "Review payment logs in Refund Management tab and confirm eligibility."
        else:
            draft_reply = (
                f"Dear {requester_name},\n\n"
                f"Thank you for contacting MediConnect Support regarding \"{t.get('subject')}\".\n\n"
                f"We are actively investigating the issue and will provide an update shortly. "
                f"Please let us know if you require any urgent assistance in the meantime.\n\n"
                f"Warm regards,\nMediConnect Support Team"
            )
            suggested_resolution = "Standard support workflow: investigate issue and respond within SLA."

        return {
            "ticketId": t.get("ticketId"),
            "suggestedCategory": suggested_category,
            "suggestedPriority": suggested_priority,
            "issueSummary": f"{t.get('subject')}: {t.get('description')[:120]}...",
            "suggestedResolution": suggested_resolution,
            "draftResponse": draft_reply,
            "flags": flags,
        }

    @staticmethod
    def send_admin_reply(
        db: Database,
        admin_user_id: str,
        admin_name: str,
        ticket_id: str,
        message: str,
        new_status: Optional[str] = None,
        resolve: bool = False,
    ) -> Dict[str, Any]:
        """Admin authorizes sending a reply message and optionally updates ticket status."""
        query = {"ticketId": ticket_id} if ticket_id.startswith("TCK-") else {"_id": ObjectId(ticket_id)}
        t = db["support_tickets"].find_one(query)
        if not t:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        now = utc_now()
        msg_obj = SupportMessage(
            senderId=str(admin_user_id),
            senderRole="ADMIN",
            senderName=admin_name,
            message=message,
            sentAt=now,
        )

        target_status = TicketStatus.RESOLVED.value if resolve else (new_status or TicketStatus.IN_PROGRESS.value)
        resolved_at = now if target_status in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value] else None

        db["support_tickets"].update_one(
            {"_id": t["_id"]},
            {
                "$push": {"messages": msg_obj.model_dump()},
                "$set": {
                    "status": target_status,
                    "assignedAdminId": str(admin_user_id),
                    "updatedAt": now,
                    "resolvedAt": resolved_at,
                }
            }
        )

        AdminAuditService.log_action(
            db=db,
            actor_id=admin_user_id,
            actor_role="ADMIN",
            action_type=AdminAuditAction.SUPPORT_TICKET_RESOLVED if resolve else AdminAuditAction.SUPPORT_RESPONSE_SENT,
            target_id=t["ticketId"],
            target_type="support_ticket",
            previous_state=t.get("status"),
            new_state=target_status,
            reason=f"Admin reply: {message[:100]}...",
        )

        return {
            "message": "Reply sent successfully.",
            "ticketId": t["ticketId"],
            "status": target_status,
        }
