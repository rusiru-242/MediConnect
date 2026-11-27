"""Agent 26 — patient-facing customer support replies in the assistant chat (A05).

Deterministic. The reply is built from the requester's own tickets, read through the role-checked
``get_my_support_tickets`` tool, plus fixed navigation guidance. The assistant never creates or sends a support
message, never approves a refund, changes an appointment or resets a password, and gives no medical advice:
emergencies are handled earlier in the chat by the emergency detector, before this module is reached.
"""
from app.agents.orchestrator import AIOrchestrator

SUPPORT_HOW_TO = (
    "To contact MediConnect Support, open Profile and choose Help & Support, then Create ticket. Pick a category, "
    "write a subject and your message, and send it. A member of the support team replies there, and you get an "
    "in-app notification when they do."
)
SUPPORT_LIMITS = (
    "Support can explain how the app works and look into account, booking and payment problems. It cannot give "
    "medical advice; for health questions ask your doctor or use the health assistant."
)
SUPPORT_ACTION_REFUSAL = (
    "I can't approve a refund, change or cancel an appointment, reset a password or unlock an account from this "
    "chat, and support replies don't do that either. Refunds: open the appointment in My Appointments; a refund is "
    "decided by the MediConnect team under the cancellation policy. Password: use Forgot Password on the sign-in "
    "screen. For anything else, create a support ticket from Profile → Help & Support."
)
STATUS_LABELS = {"open": "open", "in_progress": "in progress", "waiting_for_user": "waiting for your reply",
                 "resolved": "resolved", "closed": "closed"}


def ticket_line(t):
    return (f"{t.get('ticketId')} · {t.get('subject')} · {STATUS_LABELS.get(t.get('status'), t.get('status'))}"
            + (" · support replied" if t.get("awaitingReplyFrom") == "requester" else ""))


async def patient_reply(db, user, intent):
    """Return (text, metadata) for a support intent, or None when the intent is not a support intent."""
    if intent == "support_action_request":
        return SUPPORT_ACTION_REFUSAL, {"type": "support_action_refused", "changed": False}
    if intent != "support_request":
        return None
    if user is None:
        return SUPPORT_HOW_TO, {"type": "support_guidance", "signedIn": False}
    result = await AIOrchestrator(db, user, None).execute("get_my_support_tickets", {}, {"get_my_support_tickets"})
    if "error" in result:
        return (f"I could not read your support tickets just now. {SUPPORT_HOW_TO}",
                {"type": "support_tickets_unavailable"})
    rows = result.get("items", [])
    if rows:
        lines = "\n".join(f"  {ticket_line(t)}" for t in rows[:5])
        text = f"Your support tickets (most recent first):\n{lines}\n\n{SUPPORT_HOW_TO}\n\n{SUPPORT_LIMITS}"
    else:
        text = f"You have no support tickets yet.\n\n{SUPPORT_HOW_TO}\n\n{SUPPORT_LIMITS}"
    return text, {"type": "support_guidance", "source": "support_tickets",
                  "ticketIds": [t.get("ticketId") for t in rows[:5]]}
