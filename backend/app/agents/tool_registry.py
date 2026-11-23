"""Typed read-only capabilities for the conversation orchestrator."""
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from app.models.appointment import AppointmentStatus
from app.schemas.user import UserResponseSchema
from app.services.appointment_service import AppointmentService
from app.services.doctor_service import DoctorService, get_sl_today_str
from app.services.care_plan_service import CarePlanService

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,100}$")]


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Search(Arguments):
    specialty: ShortText | None = None
    city: ShortText | None = None
    name: ShortText | None = None
    hospital: ShortText | None = None
    max_fee: float | None = Field(default=None, ge=0, le=1000000)


class Doctor(Arguments):
    doctor_id: Identifier


class Availability(Doctor):
    requested_date: date
    requested_time: Annotated[str, StringConstraints(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")] | None = None


class Appointments(Arguments):
    status: AppointmentStatus | None = None
    from_date: date | None = None
    to_date: date | None = None


class Session(Arguments):
    session_id: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{24}$")]


@dataclass(frozen=True)
class ToolContext:
    db: object
    user: UserResponseSchema


@dataclass(frozen=True)
class Tool:
    description: str
    arguments: type[Arguments]
    run: Callable[[ToolContext, Arguments], Awaitable[dict]]
    roles: frozenset[str] = frozenset({"PATIENT"})


def public_doctor(profile):
    fields = ("doctorId", "fullName", "specialty", "hospitalOrClinic", "city", "consultationFee",
              "qualifications", "experienceYears", "profileImage", "verificationStatus")
    return {field: getattr(profile, field) for field in fields
            if getattr(profile, field, None) is not None}


async def search_doctors(ctx, args):
    response = await DoctorService.list_approved_doctors(
        ctx.db, limit=5, specialty=args.specialty, search=args.name,
        city=args.city, hospital=args.hospital, max_fee=args.max_fee, specialty_variants=True,
    )
    return {"doctors": [public_doctor(row) for row in response.items]}


async def doctor_profile(ctx, args):
    profile = await DoctorService.get_approved_doctor_detail(ctx.db, args.doctor_id)
    return {"doctors": [public_doctor(profile)]}


async def availability(ctx, args):
    if args.requested_date.isoformat() < get_sl_today_str():
        return {"error": "date_in_past"}
    day = await DoctorService.get_doctor_patient_slots(ctx.db, args.doctor_id, args.requested_date.isoformat())
    profile = await DoctorService.get_approved_doctor_detail(ctx.db, args.doctor_id)
    slots = [
        {**slot.model_dump(mode="json"), "date": day.date}
        for slot in day.slots
    ]
    if args.requested_time:
        target = int(args.requested_time[:2]) * 60 + int(args.requested_time[3:])
        slots.sort(key=lambda slot: abs(
            int(slot["startTime"][:2]) * 60 + int(slot["startTime"][3:]) - target
        ))
    slots = slots[:20]
    return {"doctor_id": profile.doctorId, "date": day.date, "timezone": "Asia/Colombo",
            "location": profile.hospitalOrClinic, "requested_time": args.requested_time, "slots": slots}


async def appointments(ctx, args):
    if args.from_date and args.to_date and args.from_date > args.to_date:
        return {"error": "invalid_date_range"}
    result = await AppointmentService.list_patient_appointments(
        ctx.db, ctx.user, limit=10, status_filter=args.status,
        from_date=args.from_date.isoformat() if args.from_date else None,
        to_date=args.to_date.isoformat() if args.to_date else None,
    )
    fields = {"appointmentDate", "startTime", "endTime", "status", "paymentStatus"}
    return {"appointments": [item.model_dump(mode="json", include=fields) for item in result.items]}


async def booking_status(ctx, args):
    from app.services.booking_session_service import BookingSessionService

    session = BookingSessionService._get_session_or_404(ctx.db, ctx.user, args.session_id)
    # Synchronize in memory. The interactive API owns MongoDB writes.
    BookingSessionService._sync_hold_and_payment_status(ctx.db, session)
    return {"booking_state": session["state"]}


async def care_tasks(ctx, args):
    plans = await CarePlanService.list_patient_care_plans(ctx.db, ctx.user, status_filter="ACTIVE")
    tasks = [{"title": task.title, "completed": task.isCompleted}
             for plan in plans.plans for task in plan.tasks]
    return {"tasks": tasks[:20]}


TOOLS = {
    "search_verified_doctors": Tool("Find approved active doctors with matching public filters.", Search, search_doctors),
    "get_doctor_profile": Tool("Read an approved doctor's public profile.", Doctor, doctor_profile),
    "check_doctor_availability": Tool("Check slots and alternatives on a date in Asia/Colombo.", Availability, availability),
    "get_patient_appointments": Tool("Read the signed-in patient's appointments.", Appointments, appointments),
    "get_patient_care_tasks": Tool("Read assigned care tasks for the signed-in patient.", Arguments, care_tasks),
    "get_booking_session_status": Tool("Read the signed-in patient's booking state.", Session, booking_status),
}
