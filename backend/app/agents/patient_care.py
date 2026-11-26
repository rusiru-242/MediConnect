"""Private care intents run locally against authorized records."""
from datetime import datetime, timedelta
import re

from bson import ObjectId
from app.agents.orchestrator import AIOrchestrator
from app.services.care_scheduler import COLOMBO


async def respond_to_care(db, user, provider, session, text, category=None):
    """``category`` is set by the shared intent router (Phase 05) for paraphrases the patterns below miss."""
    query = text.casefold()
    forced_category = category
    action = re.search(r"\b(?:mama beheth biwwa|mark.*taken|snooze|skip.*reminder|medicine reminder.*one)\b", query)
    category = next((kind for kind, pattern in (
        ("medication", r"beheth|බෙහෙත්|மருந்து|medication schedule|medicine.*(?:time|due|take)"),
        ("test", r"blood test|urine test|scheduled test|රුධිර පරීක්ෂණ|இரத்தப் பரிசோதனை"),
        ("follow_up", r"follow[ -]up.*(?:due|when|task)|my follow[ -]up|පසු විපරම"),
        ("appointment", r"next appointment|upcoming appointment|heta mata appointment|ඊළඟ හමුව"),
        ("all", r"my care tasks|today.?s tasks|care plan|karanna thiyena dewal|අද.*කාර්ය"),
        ("readings", r"my.*readings|my measurements|my health tracking"),
    ) if re.search(pattern, query)), None)
    if forced_category:
        category, action = forced_category, None
    if category is None and re.fullmatch(r"(?:and )?(?:tomorrow|heta|හෙට|நாளை)[?!. ]*", query):
        category = session.get("careCategory")
    if action:
        message = (
            "Open My Care Plan and choose the exact medication occurrence to record or correct an action. "
            "A clinician must approve the exact times before medication reminders are activated."
        )
    elif category == "notification_action":
        # A02: the assistant never changes notification state; the user does it in the app.
        message = ("I can't change your notifications from the chat. Open Notifications and use Mark as read or "
                   "Mark all as read.")
    elif category == "notifications":
        output = await AIOrchestrator(db, user, provider).execute(
            "get_my_notifications", {"unread_only": True}, {"get_my_notifications"})
        if output.get("error"):
            message = "Your notifications are temporarily unavailable. Open Notifications in the app."
        elif not output.get("unreadCount"):
            message = "You have no unread notifications."
        else:
            lines = [f"{datetime.fromisoformat(item['createdAt']).astimezone(COLOMBO):%d %b %H:%M} · {item['title']}"
                     for item in output["items"] if item.get("createdAt")]
            message = (f"You have {output['unreadCount']} unread notification"
                       f"{'s' if output['unreadCount'] != 1 else ''}.\n" + "\n".join(lines)
                       + "\nOpen Notifications to read them.")
    elif category == "missed":
        # Past medication occurrences with no recorded action, from the clinician-approved schedule only.
        today = datetime.now(COLOMBO).date()
        yesterday = bool(re.search(r"\byesterday\b|\biye\b|ඊයේ", query))
        start = today - timedelta(days=1) if yesterday else today - timedelta(days=6)
        output = await AIOrchestrator(db, user, provider).execute(
            "get_my_care_agenda",
            {"day": start.isoformat(), "days": 1 if yesterday else 7, "kind": "medication", "unrecorded_only": True},
            {"get_my_care_agenda"})
        items = output.get("items", [])
        if output.get("error"):
            message = "Your care records are temporarily unavailable. Try My Care Plan."
        elif not items:
            message = ("No scheduled medicine doses without a recorded action "
                       f"{'yesterday' if yesterday else 'in the last 7 days'}.")
        else:
            lines = [f"{datetime.fromisoformat(item['scheduledAt']).astimezone(COLOMBO):%d %b %H:%M} · {item['title']}"
                     for item in items[:10]]
            message = ("Scheduled doses with no action recorded:\n" + "\n".join(lines)
                       + "\nIf you took a dose but did not record it, open My Care Plan to record it. "
                         "For what to do about a missed dose, ask your pharmacist or the doctor who prescribed it.")
    elif category:
        day = datetime.now(COLOMBO).date()
        tomorrow = bool(re.search(r"\b(?:tomorrow|heta)\b|හෙට|நாளை", query))
        day += timedelta(days=int(tomorrow))
        # A02-BUG-013: "this week" read only today, and "next appointment" listed one that had already started.
        upcoming = bool(re.search(r"\b(?:next|upcoming|coming)\b", query))
        week = bool(re.search(r"\bthis week\b|\bweek\b|sathiye|සතියේ", query))
        days = 7 if (upcoming or week) and category in {"appointment", "test"} and not tomorrow else 1
        tool = "get_my_health_tracking_summary" if category == "readings" else "get_my_care_agenda"
        arguments = {} if category == "readings" else {"day": day.isoformat(), "days": days, "kind": category,
                                                        "upcoming_only": upcoming and not tomorrow}
        output = await AIOrchestrator(db, user, provider).execute(tool, arguments, {tool})
        items = output.get("items", [])
        if output.get("error"):
            message = "Your care records are temporarily unavailable. Try My Care Plan."
        elif not items:
            message = "There are no saved readings." if category == "readings" else (
                "There are no matching scheduled records in the next seven days." if days == 7
                else f"There are no matching scheduled records for {day.isoformat()}."
            )
        elif category == "readings":
            message = "\n".join(
                f"{item['metric'].replace('_', ' ')} · {item['value']}"
                f"{'/' + str(item['secondary']) if item.get('secondary') is not None else ''} {item['unit']}"
                for item in items[:5]
            ) + "\nThese are patient-reported readings."
        else:
            lines = []
            for item in items[:10]:
                at = datetime.fromisoformat(item["scheduledAt"]).astimezone(COLOMBO)
                line = f"{at:%d %b %H:%M} · {item['title']}"
                if item.get("instructions"):
                    line += f" · {item['instructions']}"
                if item.get("action"):
                    line += f" ({item['action']}, patient-reported)"
                lines.append(line)
            message = "\n".join(lines) + "\nTimes are in Asia/Colombo. Open My Care Plan for details."
        session["careCategory"] = category
    else:
        return None
    now = datetime.now(COLOMBO).astimezone()
    session.setdefault("messages", []).extend([
        {"id": str(ObjectId()), "sender": "user", "content": text, "timestamp": now},
        {"id": str(ObjectId()), "sender": "assistant", "content": message, "timestamp": now,
         "metadata": {"type": "care_agenda"}},
    ])
    session["activeIntent"] = "PATIENT_CARE"
    return session
