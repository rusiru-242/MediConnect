"""JWT-scoped clinic workflow endpoints. Clinical writes stay in existing care-plan flows."""
from datetime import date, datetime, timedelta
import hashlib
import hmac
import json
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.agents.orchestrator import AIOrchestrator
from app.config.database import get_database
from app.config.settings import settings
from app.middleware.auth import require_doctor
from app.schemas.doctor import CreateBlockedTimeRequest
from app.services import doctor_communications as communications, doctor_workflow as workflow
from app.services.doctor_service import DoctorService, SL_TIMEZONE

router = APIRouter(prefix="/doctor/workflow", tags=["Doctor workflow"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueueAction(Strict):
    action: Literal["checked_in", "waiting", "in_consultation", "completed", "no_show", "reorder"]
    version: int = Field(ge=0)
    requestId: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{8,80}$")]
    confirm: Literal[True]
    position: int | None = Field(None, ge=1, le=1000)


class Chat(Strict):
    message: str = Field(min_length=1, max_length=500)
    appointmentId: str | None = Field(None, max_length=24)


class Block(CreateBlockedTimeRequest):
    confirm: Literal[True]


class ApproveBatch(Strict):
    token: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: Literal[True]


def today():
    return datetime.now(SL_TIMEZONE).date()


@router.get("/schedule")
def schedule(start: date | None = None, end: date | None = None, user=Depends(require_doctor), db=Depends(get_database)):
    start = start or today()
    return {"appointments": workflow.schedule(db, user, start, end or start)}


@router.get("/queue")
def queue(day: date | None = None, user=Depends(require_doctor), db=Depends(get_database)):
    return workflow.patient_queue(db, user, day or today())


@router.post("/queue/{identifier}")
def queue_action(identifier: str, request: QueueAction, user=Depends(require_doctor), db=Depends(get_database)):
    return workflow.change_queue(db, user, identifier, request)


@router.get("/preparation/{identifier}")
def preparation(identifier: str, user=Depends(require_doctor), db=Depends(get_database)):
    return workflow.preparation(db, user, identifier)


@router.get("/follow-ups")
def follow_ups(user=Depends(require_doctor), db=Depends(get_database)):
    return {"followUps": workflow.follow_ups(db, user)}


@router.get("/analytics")
def analytics(start: date | None = None, end: date | None = None, user=Depends(require_doctor), db=Depends(get_database)):
    start = start or today()
    return workflow.analytics(db, user, start, end or start)


@router.post("/blocked-time", status_code=201)
async def block_time(request: Block, user=Depends(require_doctor), db=Depends(get_database)):
    workflow.ConsultationService._verify_approved_doctor(db, user)
    return await DoctorService.create_doctor_blocked_time(db, user, request)


def batch_token(user, day, recipients):
    authorization = json.dumps([str(user.id), day.isoformat(), communications.TITLE, communications.BODY, recipients])
    return hmac.new(settings.JWT_SECRET.encode(), authorization.encode(), hashlib.sha256).hexdigest()


def check_batch_day(day):
    if not today() <= day <= today() + timedelta(days=7):
        raise HTTPException(422, "Choose a date in the next seven days.")


@router.get("/reminders/{day}")
def reminder_preview(day: date, user=Depends(require_doctor), db=Depends(get_database)):
    check_batch_day(day)
    recipients = communications.preview(db, user, day)
    return {"date": day, "count": len(recipients), "channel": "in_app", "title": communications.TITLE,
            "body": communications.BODY, "token": batch_token(user, day, recipients),
            "statuses": communications.batch_status(db, user, day)}


@router.post("/reminders/{day}")
def approve_reminders(day: date, request: ApproveBatch, user=Depends(require_doctor), db=Depends(get_database)):
    check_batch_day(day)
    recipients = communications.preview(db, user, day)
    if not hmac.compare_digest(request.token, batch_token(user, day, recipients)):
        raise HTTPException(409, "The recipient list changed. Preview the draft again.")
    return {"statuses": communications.queue_batch(db, user, day, recipients)}


WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def requested_range(query):
    """Date range named in a doctor's question, in Asia/Colombo (P03-N20).

    "tomorrow", "next monday" / "on friday" (the next such day after today), "this week" (today + 6 days),
    "this month" (1st to last day of the current month); otherwise today.
    """
    base = today()
    day = base + timedelta(days=int(any(word in query for word in ("tomorrow", "heta", "හෙට", "நாளை"))))
    for index, name in enumerate(WEEKDAYS):
        if re.search(rf"\b{name}\b", query):
            day = base + timedelta(days=(index - base.weekday()) % 7 or 7)
            break
    if "month" in query:
        first = base.replace(day=1)
        following = (first + timedelta(days=32)).replace(day=1)
        return first, following - timedelta(days=1)
    return day, (day + timedelta(days=6) if "week" in query else day)


@router.post("/assistant")
async def assistant(request: Chat, user=Depends(require_doctor), db=Depends(get_database)):
    workflow.ConsultationService._verify_approved_doctor(db, user)
    query = request.message.casefold()
    day, end = requested_range(query)
    orch = AIOrchestrator(db, user, None)
    if any(word in query for word in ("follow-up", "follow up", "followup")) and any(
        word in query for word in ("set", "create", "schedule", "karanna")
    ):
        if not request.appointmentId:
            return {"message": "Select an appointment first to prepare a follow-up."}
        workflow.owned_appointment(db, user, request.appointmentId)
        interval = re.search(r"(\d{1,2})\s*(weeks?|days?)| (weeks?|days?)\s*(\d{1,2})", query)
        if not interval:
            return {"message": "Specify the follow-up interval in days or weeks."}
        value, unit, reverse_unit, reverse_value = interval.groups()
        days = int(value or reverse_value) * (7 if (unit or reverse_unit).startswith("week") else 1)
        if not 1 <= days <= 365:
            return {"message": "Choose a follow-up date within the next year."}
        return {"message": "Review the proposed date and enter your instructions before saving.",
                "followUpDate": (today() + timedelta(days=days)).isoformat(), "appointmentId": request.appointmentId}
    if "reminder" in query:
        result = reminder_preview(day, user, db)
        return {"message": f"Draft ready for {result['count']} eligible appointments. Review it before approving.",
                "reminder": result}
    if any(word in query for word in ("summary", "previous visits", "preparation")):
        if request.appointmentId:
            name, args = "get_consultation_preparation", {"appointment_id": request.appointmentId}
        else:
            next_result = await orch.execute("get_next_queue_patient", {"start": day}, {"get_next_queue_patient"})
            next_row = next_result.get("nextPatient")
            if not next_row:
                return {"message": "Select an appointment. There is no checked-in patient waiting."}
            name, args = "get_consultation_preparation", {"appointment_id": next_row["id"]}
    elif any(word in query for word in ("free slot", "available slot", "available time", "availability", "gap",
                                        "හිස් වේලා", "காலி நேரம்")):
        name, args = "get_my_available_slots", {"start": day}
    elif any(word in query for word in ("next patient", "queue", "පෝලිම", "வரிசை")):
        name = "get_next_queue_patient" if "next patient" in query else "get_my_patient_queue"
        args = {"start": day}
    elif any(word in query for word in ("follow-up", "follow up", "followup")):
        name, args = "get_my_follow_up_tasks", {}
    elif any(word in query for word in ("count", "analytics", "statistics", "how many", "complete", "attention",
                                        "revenue", "earning", "payment")):
        name, args = "get_my_doctor_analytics", {"start": day, "end": end}
    elif any(word in query for word in ("appointment", "schedule", "හමුවීම්", "சந்திப்பு")):
        name, args = "get_my_doctor_schedule", {"start": day, "end": end}
    else:
        return {"message": "Ask about your schedule, free slots, patient queue, analytics, or follow-ups."}
    result = await orch.execute(name, args, {name})
    if "error" in result:
        return {"message": "I could not retrieve that information. Check the selection and try again."}
    messages = {
        "get_my_doctor_schedule": lambda: f"{len(result['appointments'])} appointments in the selected date range.",
        "get_my_available_slots": lambda: (f"{len(result['slots'])} open slots for {day.isoformat()} in Asia/Colombo."
                                           if day == end else
                                           f"{len(result['slots'])} open slots for {day.isoformat()} in Asia/Colombo. "
                                           "Ask about one day at a time for other days."),
        "get_next_queue_patient": lambda: "Here is the next checked-in patient." if result["nextPatient"] else "No checked-in patient is waiting.",
        "get_my_patient_queue": lambda: "Here is your patient queue.",
        "get_consultation_preparation": lambda: result["summary"],
        "get_my_follow_up_tasks": lambda: f"{len(result['followUps'])} recent follow-up plans.",
        # Every number below comes from the analytics service; the reply only formats it (P03-N20).
        "get_my_doctor_analytics": lambda: (
            f"{result['from']} to {result['to']} (Asia/Colombo): {result['confirmed']} confirmed, "
            f"{result['completed']} completed and {result['cancelled']} cancelled appointments; "
            f"{result['financials']['awaitingPayment']} awaiting payment and "
            f"{result['financials']['openRefundRequests']} open refund requests."),
    }
    return {"message": messages[name](), "result": result, "tool": name}
