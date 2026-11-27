"""Customer support ticketing service with template drafting and human authorization (Phase 5, A05).

Agent 26 is deterministic: keyword rules classify a ticket and pick a fixed reply template, which an administrator
edits and sends. Nothing is sent automatically, no refund, appointment or account is changed, and no ticket text is
sent to an AI provider. Ticket text is untrusted data: it is stored and shown as plain text and never followed as
an instruction.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.admin_audit import AdminAuditAction
from app.models.support_ticket import SupportMessage, SupportTicketDocument, TicketCategory, TicketPriority, TicketStatus, utc_now
from app.services.admin_audit_service import AdminAuditService

logger = logging.getLogger(__name__)

EMERGENCY_KEYWORDS = [
    "chest pain", "shortness of breath", "unconscious", "heavy bleeding",
    "stroke", "heart attack", "suicide", "can't breathe", "cannot breathe",
    "පපුවේ කැක්කුම", "හුස්ම", "மயக்கம்",
]
CATEGORY_VALUES = {c.value for c in TicketCategory}
CLOSED_STATES = {TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value}
# A repeated identical message from the same sender within this window is the same submission (double tap, retry).
DUPLICATE_MESSAGE_WINDOW = timedelta(minutes=2)
SAFETY_NOTICE = (
    "Your message may describe a medical emergency. MediConnect Support is not an emergency or medical service and "
    "cannot give medical advice. If you or someone with you is in danger, call 1990 (Suwa Seriya ambulance) or go "
    "to the nearest hospital emergency unit now."
)


def _ticket_query(ticket_id: str) -> Dict[str, Any]:
    """TCK-... or an ObjectId; anything else is a 404 rather than a 500 from bson (P04-N18)."""
    tid = (ticket_id or "").strip()
    if tid.startswith("TCK-"):
        return {"ticketId": tid}
    if ObjectId.is_valid(tid):
        return {"_id": ObjectId(tid)}
    raise HTTPException(status_code=404, detail="Support ticket not found.")


def is_emergency_text(text: str) -> bool:
    """Existing support keywords plus the assistant's emergency detector (negation and history aware)."""
    lowered = (text or "").casefold()
    if any(kw in lowered for kw in EMERGENCY_KEYWORDS):
        return True
    try:
        from app.agents.emergency_detector import detect_emergency
        return bool(detect_emergency(text or "").is_emergency)
    except Exception:  # the keyword list above still applies
        return False


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(p.strip().casefold() for p in parts).encode("utf-8")).hexdigest()


def _aware(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def ticket_view(t: Dict[str, Any], is_admin: bool) -> Dict[str, Any]:
    """The ticket as the caller may see it. The internal triage draft (suggested reply, resolution notes, linked
    booking state) is for administrators only (A05-BUG-005); message-level dedupe keys are never returned."""
    messages = [{k: v for k, v in m.items() if k != "dedupeKey"} for m in (t.get("messages") or [])]
    last_role = messages[-1].get("senderRole") if messages else None
    status_value = t.get("status", TicketStatus.OPEN.value)
    awaiting = None
    if status_value not in CLOSED_STATES:
        awaiting = "support" if last_role in {"PATIENT", "DOCTOR"} else "requester"
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
        "status": status_value,
        "priority": t.get("priority", TicketPriority.MEDIUM.value),
        "assignedAdminId": t.get("assignedAdminId") if is_admin else None,
        "relatedEntityId": t.get("relatedEntityId"),
        "messages": messages,
        "aiDraft": t.get("aiDraft") if is_admin else None,
        "safetyNotice": t.get("safetyNotice"),
        "awaitingReplyFrom": awaiting,
        "createdAt": t.get("createdAt", utc_now()),
        "updatedAt": t.get("updatedAt", utc_now()),
        "resolvedAt": t.get("resolvedAt"),
    }


def _append_message(db: Database, t: Dict[str, Any], sender_id: str, sender_role: str, sender_name: str,
                    message: str, changes: Dict[str, Any], unset: Optional[Dict[str, Any]] = None,
                    expected_status: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Append one message atomically. Returns the updated ticket, or None when the same sender already sent the
    same text within DUPLICATE_MESSAGE_WINDOW (A05-BUG-008), or the ticket status changed meanwhile."""
    now = utc_now()
    # recentMessageKeys.<sha256(sender, text)> = time last sent; one atomic conditional update on the ticket.
    path = f"recentMessageKeys.{_digest(sender_id, message)}"
    msg = SupportMessage(senderId=str(sender_id), senderRole=sender_role, senderName=sender_name, message=message,
                         sentAt=now).model_dump()
    condition: Dict[str, Any] = {
        "_id": t["_id"],
        "$or": [{path: {"$exists": False}}, {path: {"$lt": now - DUPLICATE_MESSAGE_WINDOW}}],
    }
    if expected_status is not None:
        condition["status"] = {"$in": expected_status}
    update: Dict[str, Any] = {"$push": {"messages": msg}, "$set": {**changes, "updatedAt": now, path: now}}
    if unset:
        update["$unset"] = unset
    return db["support_tickets"].find_one_and_update(condition, update, return_document=ReturnDocument.AFTER)


class SupportTicketService:
    """Manages support ticket workflows, template drafting, and authorized admin replies."""

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
        # A ticket may reference only the requester's own appointment; otherwise the admin draft would show another
        # patient's booking and payment state (P04-N18).
        if related_entity_id and ObjectId.is_valid(str(related_entity_id)):
            appt = db["appointments"].find_one({"_id": ObjectId(related_entity_id)},
                                               {"patientUserId": 1, "doctorUserId": 1})
            if appt and str(user_id) not in {str(appt.get("patientUserId")), str(appt.get("doctorUserId"))}:
                raise HTTPException(status_code=403, detail="You can only link your own appointments to a ticket.")
        if category and category not in CATEGORY_VALUES:
            raise HTTPException(status_code=422, detail="Unknown support category.")
        ticket_id = f"TCK-{uuid4().hex[:8].upper()}"
        now = utc_now()
        chosen_category = category or TicketCategory.GENERAL_SUPPORT.value

        initial_msg = SupportMessage(
            senderId=str(user_id),
            senderRole=user_role,
            senderName=user_name,
            message=description,
            sentAt=now,
        )
        emergency = is_emergency_text(f"{subject} {description}")

        doc = {
            "ticketId": ticket_id,
            "requesterId": str(user_id),
            "requesterRole": user_role,
            "requesterEmail": user_email,
            "requesterName": user_name,
            "category": chosen_category,
            "subject": subject,
            "description": description,
            "status": TicketStatus.OPEN.value,
            # Requesters do not set priority; the triage rules below do (urgent for a possible emergency).
            "priority": TicketPriority.URGENT.value if emergency else TicketPriority.MEDIUM.value,
            "assignedAdminId": None,
            "relatedEntityId": related_entity_id,
            "messages": [initial_msg.model_dump()],
            "aiDraft": None,
            "safetyNotice": SAFETY_NOTICE if emergency else None,
            "openDedupeKey": _digest(str(user_id), subject, description),
            "createdAt": now,
            "updatedAt": now,
            "resolvedAt": None,
        }

        try:
            doc["_id"] = db["support_tickets"].insert_one(doc).inserted_id
        except DuplicateKeyError:
            existing = db["support_tickets"].find_one({"openDedupeKey": doc["openDedupeKey"]}, {"ticketId": 1})
            raise HTTPException(status_code=409, detail=(
                f"You already have an open ticket with this message ({(existing or {}).get('ticketId', 'see My tickets')}). "
                "Open it to add more details."))

        # Template draft and classification for the administrator (deterministic, see generate_ai_ticket_draft).
        try:
            draft = SupportTicketService.generate_ai_ticket_draft(db, ticket_id)
            # A05-BUG-006: the requester's own category choice was overwritten by the keyword guess. The guess now
            # only fills in "general support"; it is always kept in the draft for the administrator.
            changes = {"aiDraft": draft, "priority": draft["suggestedPriority"]}
            if chosen_category == TicketCategory.GENERAL_SUPPORT.value:
                changes["category"] = draft["suggestedCategory"]
            db["support_tickets"].update_one({"ticketId": ticket_id}, {"$set": changes})
            doc.update(changes)
        except Exception as exc:
            logger.warning("Could not pre-generate the support draft for ticket %s (%s).", ticket_id,
                           type(exc).__name__)

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
        # A05: most recently active first, so a requester's follow-up brings the ticket back to the top.
        cursor = coll.find(query).sort([("updatedAt", -1), ("createdAt", -1)]).skip(skip).limit(page_size)
        items = [ticket_view(t, is_admin) for t in cursor]
        return {"items": items, "total": total, "page": page, "pageSize": page_size}

    @staticmethod
    def get_ticket(db: Database, ticket_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Get ticket detail enforcing ownership or admin privileges."""
        query = _ticket_query(ticket_id)
        t = db["support_tickets"].find_one(query)
        if not t:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        if not is_admin and str(t.get("requesterId")) != str(user_id):
            raise HTTPException(status_code=403, detail="You do not have permission to view this ticket.")

        return ticket_view(t, is_admin)

    @staticmethod
    def add_requester_reply(db: Database, user, ticket_id: str, message: str) -> Dict[str, Any]:
        """A05-BUG-004: the requester's follow-up on their own ticket (there was no way to reply).

        A waiting or resolved ticket returns to "open" so support sees it again; a closed ticket takes no more
        messages. Support is told in the admin queue; the requester gets no notification for their own message.
        """
        t = db["support_tickets"].find_one(_ticket_query(ticket_id))
        if not t:
            raise HTTPException(status_code=404, detail="Support ticket not found.")
        if str(t.get("requesterId")) != str(user.id):
            raise HTTPException(status_code=403, detail="You do not have permission to reply to this ticket.")
        if t.get("status") == TicketStatus.CLOSED.value:
            raise HTTPException(status_code=409, detail="This ticket is closed. Please create a new ticket.")
        changes: Dict[str, Any] = {"status": TicketStatus.OPEN.value, "resolvedAt": None}
        if is_emergency_text(message):
            changes.update(safetyNotice=SAFETY_NOTICE, priority=TicketPriority.URGENT.value)
        allowed = [s.value for s in TicketStatus if s != TicketStatus.CLOSED]
        updated = _append_message(db, t, str(user.id), user.role, getattr(user, "fullName", "") or "", message,
                                  changes, expected_status=allowed)
        if updated is None:
            current = db["support_tickets"].find_one({"_id": t["_id"]}) or t
            if current.get("status") == TicketStatus.CLOSED.value:
                raise HTTPException(status_code=409, detail="This ticket is closed. Please create a new ticket.")
            # Same text sent again within the window: keep the one message, return the ticket unchanged.
            view = ticket_view(current, False)
            view["duplicate"] = True
            return view
        view = ticket_view(updated, False)
        if changes.get("safetyNotice"):
            view["safetyNotice"] = SAFETY_NOTICE
        return view

    @staticmethod
    def generate_ai_ticket_draft(db: Database, ticket_id: str) -> Dict[str, Any]:
        """Perform AI classification and draft professional response with clinical safeguards."""
        query = _ticket_query(ticket_id)
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
            if appt and str(t.get("requesterId")) in {str(appt.get("patientUserId")), str(appt.get("doctorUserId"))}:
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
                f"Our administrative team has received your inquiry and will review it under the existing MediConnect cancellation policy. "
                f"This message does not approve or decline a refund. Refund requests are decided by the MediConnect team, "
                f"and you get an in-app notification when yours is decided.\n\n"
                f"If you have additional booking details or bank receipts to attach, please reply directly to this message.\n\n"
                f"Warm regards,\nMediConnect Support Team"
            )
            suggested_resolution = "Review payment logs in Refund Management tab and confirm eligibility."
        else:
            draft_reply = (
                f"Dear {requester_name},\n\n"
                f"Thank you for contacting MediConnect Support regarding \"{t.get('subject')}\".\n\n"
                f"We have received your message, and a member of the support team will review it. "
                f"Please let us know if you require any urgent assistance in the meantime.\n\n"
                f"Warm regards,\nMediConnect Support Team"
            )
            suggested_resolution = "Standard support workflow: investigate issue and respond within SLA."

        if context_notes:
            suggested_resolution = f"{suggested_resolution} Context: {'; '.join(context_notes)}."
        return {
            "ticketId": t.get("ticketId"),
            "suggestedCategory": suggested_category,
            "suggestedPriority": suggested_priority,
            "issueSummary": f"{t.get('subject')}: {(t.get('description') or '')[:120]}...",
            "draftType": "template",  # fixed wording chosen by keyword rules, not generated by an LLM
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
        query = _ticket_query(ticket_id)
        t = db["support_tickets"].find_one(query)
        if not t:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        now = utc_now()
        # Default after a reply: waiting for the requester (the previous default "in progress" hid that support had
        # answered).
        target_status = TicketStatus.RESOLVED.value if resolve else (new_status or TicketStatus.WAITING_FOR_USER.value)
        closing = target_status in CLOSED_STATES
        changes = {"status": target_status, "assignedAdminId": str(admin_user_id),
                   "resolvedAt": now if closing else None}
        updated = _append_message(db, t, str(admin_user_id), "ADMIN", admin_name, message, changes,
                                  unset={"openDedupeKey": ""} if closing else None)
        if updated is None:
            # A05-BUG-008: a double click or retry sent the same reply twice and notified the patient twice.
            return {"message": "This reply was already sent.", "ticketId": t["ticketId"],
                    "status": t.get("status"), "duplicate": True}
        sent = updated["messages"][-1]

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
            metadata={"messageId": sent.get("messageId"), "draftType": (t.get("aiDraft") or {}).get("draftType")},
        )

        # Tell the requester there is a reply (in-app only; no email or SMS is sent) (P04-N18). The notification
        # carries the ticket reference so it opens the ticket (A05-BUG-009); one notification per message.
        try:
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService
            NotificationService.create_notification(
                db=db, recipient_user_id=str(t["requesterId"]), type=NotificationType.SYSTEM,
                title="Support ticket update",
                body=f"MediConnect Support replied to your ticket {t['ticketId']}. Status: {target_status.replace('_', ' ')}.",
                idempotency_key=f"ticket_reply_{t['ticketId']}_{sent.get('messageId')}",
                related_ticket_id=t["ticketId"], send_push=False,
            )
        except Exception as exc:
            logger.warning("Support reply notification was not stored (%s).", type(exc).__name__)

        return {
            "message": "Reply sent successfully.",
            "ticketId": t["ticketId"],
            "status": target_status,
        }

    @staticmethod
    def update_status(db: Database, admin_user_id: str, ticket_id: str, new_status: str) -> Dict[str, Any]:
        """A05: change a ticket's status without a message (e.g. close a resolved ticket)."""
        t = db["support_tickets"].find_one(_ticket_query(ticket_id))
        if not t:
            raise HTTPException(status_code=404, detail="Support ticket not found.")
        now = utc_now()
        closing = new_status in CLOSED_STATES
        update: Dict[str, Any] = {"$set": {"status": new_status, "updatedAt": now, "assignedAdminId": str(admin_user_id),
                                           "resolvedAt": now if closing else None}}
        if closing:
            update["$unset"] = {"openDedupeKey": ""}
        db["support_tickets"].update_one({"_id": t["_id"]}, update)
        AdminAuditService.log_action(
            db=db, actor_id=admin_user_id, actor_role="ADMIN",
            action_type=AdminAuditAction.SUPPORT_TICKET_RESOLVED if closing else AdminAuditAction.SUPPORT_RESPONSE_SENT,
            target_id=t["ticketId"], target_type="support_ticket", previous_state=t.get("status"),
            new_state=new_status, reason="Status changed without a message",
        )
        return {"message": "Ticket status updated.", "ticketId": t["ticketId"], "status": new_status}
