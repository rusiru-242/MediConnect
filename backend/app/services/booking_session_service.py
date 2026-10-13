"""Service implementing session lifecycle, state transitions, and booking execution."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.agents.booking_agent import BookingAgent, validate_state_transition
from app.models.appointment import AppointmentStatus, PaymentStatus as ApptPaymentStatus
from app.models.booking_session import (
    BookingAgentState,
    BookingSessionDocument,
    ChatMessageDocument,
    get_booking_session_collection,
    utc_now,
)
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole
from app.schemas.appointment import CancelAppointmentRequest, CreateAppointmentRequest
from app.schemas.booking_session import (
    BookingPreferencesSchema,
    BookingSessionResponse,
    BookingSummary,
    ChatMessageSchema,
    ConfirmBookingRequest,
    CreateSessionRequest,
    DoctorCardSummary,
    SelectDoctorRequest,
    SelectSlotRequest,
    SendMessageRequest,
    SlotCardSummary,
)
from app.schemas.user import UserResponseSchema
from app.services.appointment_service import AppointmentService
from app.services.doctor_service import DoctorService

logger = logging.getLogger(__name__)


def _to_response_schema(doc: Dict[str, Any]) -> BookingSessionResponse:
    """Map MongoDB session document to Pydantic response schema."""
    prefs = doc.get("preferences") or {}
    messages = [
        ChatMessageSchema(
            id=str(m.get("id", ObjectId())),
            sender=m.get("sender", "assistant"),
            content=m.get("content", ""),
            timestamp=m.get("timestamp", utc_now()),
            metadata=m.get("metadata"),
        )
        for m in doc.get("messages", [])
    ]

    selected_doc = None
    if doc.get("selectedDoctor"):
        sd = doc["selectedDoctor"]
        selected_doc = DoctorCardSummary(
            doctorId=str(sd.get("doctorId", "")),
            doctorProfileId=str(sd.get("doctorProfileId", "")),
            doctorUserId=str(sd.get("doctorUserId", "")),
            fullName=sd.get("fullName", "Doctor"),
            specialty=sd.get("specialty", ""),
            hospitalOrClinic=sd.get("hospitalOrClinic"),
            experienceYears=int(sd.get("experienceYears", 0)),
            consultationFee=float(sd.get("consultationFee", 2500.0)),
            rating=float(sd.get("rating", 4.8)),
            nextAvailableDate=sd.get("nextAvailableDate"),
            matchReason=sd.get("matchReason"),
        )

    selected_slot = None
    if doc.get("selectedSlot"):
        ss = doc["selectedSlot"]
        selected_slot = SlotCardSummary(
            availabilityId=str(ss.get("availabilityId", "")),
            date=ss.get("date", ""),
            startTime=ss.get("startTime", ""),
            endTime=ss.get("endTime", ""),
        )

    booking_summary = None
    if doc.get("bookingSummary"):
        bs = doc["bookingSummary"]
        booking_summary = BookingSummary(
            doctorName=bs.get("doctorName", "Doctor"),
            specialty=bs.get("specialty", ""),
            hospitalOrClinic=bs.get("hospitalOrClinic"),
            appointmentDate=bs.get("appointmentDate", ""),
            startTime=bs.get("startTime", ""),
            endTime=bs.get("endTime", ""),
            consultationFee=float(bs.get("consultationFee", 2500.0)),
            serviceFee=float(bs.get("serviceFee", 0.0)),
            totalAmount=float(bs.get("totalAmount", 2500.0)),
            currency=bs.get("currency", "lkr"),
        )

    candidate_docs = [
        DoctorCardSummary(
            doctorId=str(d.get("doctorId", "")),
            doctorProfileId=str(d.get("doctorProfileId", "")),
            doctorUserId=str(d.get("doctorUserId", "")),
            fullName=d.get("fullName", "Doctor"),
            specialty=d.get("specialty", ""),
            hospitalOrClinic=d.get("hospitalOrClinic"),
            experienceYears=int(d.get("experienceYears", 0)),
            consultationFee=float(d.get("consultationFee", 2500.0)),
            rating=float(d.get("rating", 4.8)),
            nextAvailableDate=d.get("nextAvailableDate"),
            matchReason=d.get("matchReason"),
        )
        for d in doc.get("candidateDoctors", [])
    ]

    candidate_slots = [
        SlotCardSummary(
            availabilityId=str(s.get("availabilityId", "")),
            date=s.get("date", ""),
            startTime=s.get("startTime", ""),
            endTime=s.get("endTime", ""),
        )
        for s in doc.get("candidateSlots", [])
    ]

    return BookingSessionResponse(
        id=str(doc["_id"]),
        patientUserId=str(doc["patientUserId"]),
        state=doc.get("state", BookingAgentState.COLLECTING_PREFERENCES.value),
        preferences=BookingPreferencesSchema(
            specialty=prefs.get("specialty"),
            city=prefs.get("city"),
            date=prefs.get("date"),
            timeRange=prefs.get("timeRange"),
            maxFee=prefs.get("maxFee"),
            language=prefs.get("language", "en"),
            patientNote=prefs.get("patientNote"),
        ),
        selectedDoctor=selected_doc,
        selectedSlot=selected_slot,
        bookingSummary=booking_summary,
        candidateDoctors=candidate_docs,
        candidateSlots=candidate_slots,
        appointmentId=doc.get("appointmentId"),
        paymentId=doc.get("paymentId"),
        holdExpiresAt=doc.get("holdExpiresAt"),
        messages=messages,
        isUrgent=bool(doc.get("isUrgent", False)),
        urgencyReason=doc.get("urgencyReason"),
        createdAt=doc.get("createdAt", utc_now()),
        updatedAt=doc.get("updatedAt", utc_now()),
        expiresAt=doc.get("expiresAt", utc_now()),
    )


class BookingSessionService:
    """Coordinates conversational turns, state verification, doctor selection, and booking hold creation."""

    @classmethod
    async def create_session(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        req: CreateSessionRequest,
    ) -> BookingSessionResponse:
        """Initialize a new booking conversation session for the patient."""
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can use the AI Booking Assistant.",
            )

        if patient_user.accountStatus != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account must be active to book appointments.",
            )

        collection = get_booking_session_collection(db)
        now = utc_now()
        session_doc = BookingSessionDocument(
            patientUserId=str(patient_user.id),
            state=BookingAgentState.COLLECTING_PREFERENCES,
            createdAt=now,
            updatedAt=now,
            expiresAt=now + timedelta(minutes=30),
        )

        initial_dict = session_doc.to_mongo_dict()

        if req.initialMessage and req.initialMessage.strip():
            # Process initial query through agent
            initial_dict = await BookingAgent.process_user_turn(
                db=db,
                session_data=initial_dict,
                user_message=req.initialMessage.strip(),
            )
        else:
            # Add welcoming introduction
            greeting = (
                "Hello! I'm your MediConnect AI Booking Assistant. "
                "I can help you find verified doctors, select convenient appointment slots, "
                "and book your consultation.\n\n"
                "What kind of doctor or medical specialist are you looking for today? "
                "(You can also inquire in Sinhala: ඔබට සිංහලෙන්ද විමසිය හැක)"
            )
            initial_dict["messages"] = [
                {
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": greeting,
                    "timestamp": now,
                    "metadata": {"type": "welcome"},
                }
            ]

        res = collection.insert_one(initial_dict)
        initial_dict["_id"] = res.inserted_id
        return _to_response_schema(initial_dict)

    @classmethod
    async def get_session(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
    ) -> BookingSessionResponse:
        """Fetch session by ID with ownership verification and hold expiration sync."""
        doc = cls._get_session_or_404(db, patient_user, session_id)
        cls._sync_hold_and_payment_status(db, doc)
        return _to_response_schema(doc)

    @classmethod
    async def handle_message(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
        req: SendMessageRequest,
    ) -> BookingSessionResponse:
        """Process an incoming conversational message from the patient."""
        doc = cls._get_session_or_404(db, patient_user, session_id)

        # Check if session is already completed or cancelled
        current_state = doc.get("state")
        if current_state in [BookingAgentState.BOOKING_CONFIRMED.value, BookingAgentState.CANCELLED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This booking session is already {current_state.lower()}. Please start a new session.",
            )

        cls._sync_hold_and_payment_status(db, doc)

        # Process user message through conversational agent
        updated_dict = await BookingAgent.process_user_turn(
            db=db,
            session_data=doc,
            user_message=req.message,
        )

        updated_dict["updatedAt"] = utc_now()
        # Extend session TTL on active interaction
        updated_dict["expiresAt"] = utc_now() + timedelta(minutes=30)

        collection = get_booking_session_collection(db)
        collection.replace_one({"_id": ObjectId(session_id)}, updated_dict)

        return _to_response_schema(updated_dict)

    @classmethod
    async def select_doctor(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
        req: SelectDoctorRequest,
    ) -> BookingSessionResponse:
        """Explicitly select a doctor from recommendation cards."""
        doc = cls._get_session_or_404(db, patient_user, session_id)
        current_state = doc.get("state")

        # Resolve doctor: must be APPROVED and ACTIVE
        clean_id = req.doctorId.strip()
        query = (
            {"$or": [{"doctorId": clean_id}, {"_id": ObjectId(clean_id)}]}
            if ObjectId.is_valid(clean_id)
            else {"doctorId": clean_id}
        )
        profile = db["doctor_profiles"].find_one(query)
        if not profile or profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found or is not currently active.",
            )

        user_id_raw = profile.get("userId")
        user = db["users"].find_one({"_id": ObjectId(user_id_raw) if ObjectId.is_valid(str(user_id_raw)) else user_id_raw})
        if not user or user.get("role") != UserRole.DOCTOR.value or user.get("accountStatus") != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor account is not active.",
            )

        doctor_dict = {
            "doctorId": str(profile.get("doctorId", "")),
            "doctorProfileId": str(profile["_id"]),
            "doctorUserId": str(user["_id"]),
            "fullName": user.get("fullName", "Doctor"),
            "specialty": profile.get("specialty", ""),
            "hospitalOrClinic": profile.get("hospitalOrClinic"),
            "experienceYears": int(profile.get("experienceYears", 0)),
            "consultationFee": float(profile.get("consultationFee", 2500.0)),
            "rating": float(profile.get("rating", 4.8)),
        }

        doc["selectedDoctor"] = doctor_dict
        doc["selectedSlot"] = None
        doc["bookingSummary"] = None

        # Fetch unbooked discrete slots
        prefs = doc.get("preferences") or {}
        slots = await BookingAgent._fetch_available_slots(db, doctor_dict["doctorId"], prefs.get("date"))
        doc["candidateSlots"] = slots

        target_state = BookingAgentState.AWAITING_SLOT_SELECTION.value
        if validate_state_transition(current_state, target_state):
            doc["state"] = target_state

        lang = prefs.get("language", "en")
        assistant_msg = BookingAgent._build_slot_selection_message(doctor_dict, slots, lang)
        doc["messages"].append({
            "id": str(ObjectId()),
            "sender": "assistant",
            "content": assistant_msg,
            "timestamp": utc_now(),
            "metadata": {"type": "slot_selection", "doctorId": doctor_dict["doctorId"]},
        })

        doc["updatedAt"] = utc_now()
        get_booking_session_collection(db).replace_one({"_id": ObjectId(session_id)}, doc)
        return _to_response_schema(doc)

    @classmethod
    async def select_slot(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
        req: SelectSlotRequest,
    ) -> BookingSessionResponse:
        """Explicitly select an appointment slot from available slot cards."""
        doc = cls._get_session_or_404(db, patient_user, session_id)
        current_state = doc.get("state")
        selected_doctor = doc.get("selectedDoctor")

        if not selected_doctor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please select a doctor before selecting a slot.",
            )

        # Validate availability window exists and belongs to selected doctor
        if not ObjectId.is_valid(req.availabilityId):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid availabilityId format.",
            )

        avail_doc = db["doctor_availabilities"].find_one({"_id": ObjectId(req.availabilityId)})
        if not avail_doc or not avail_doc.get("isActive", False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected availability window is no longer active.",
            )

        if str(avail_doc.get("doctorUserId")) != selected_doctor.get("doctorUserId"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slot does not belong to the selected doctor.",
            )

        # Compute derived endTime if not provided
        duration = int(avail_doc.get("slotDurationMinutes", 30))
        start_h, start_m = int(req.startTime[:2]), int(req.startTime[3:5])
        end_mins = start_h * 60 + start_m + duration
        derived_end = f"{end_mins // 60:02d}:{end_mins % 60:02d}"
        end_time_str = req.endTime or derived_end

        slot_dict = {
            "availabilityId": req.availabilityId,
            "date": req.date,
            "startTime": req.startTime,
            "endTime": end_time_str,
        }

        doc["selectedSlot"] = slot_dict
        summary = BookingAgent._build_booking_summary(selected_doctor, slot_dict)
        doc["bookingSummary"] = summary

        target_state = BookingAgentState.AWAITING_BOOKING_CONFIRMATION.value
        if validate_state_transition(current_state, target_state):
            doc["state"] = target_state

        lang = (doc.get("preferences") or {}).get("language", "en")
        assistant_msg = BookingAgent._build_confirmation_prompt_message(summary, lang)
        doc["messages"].append({
            "id": str(ObjectId()),
            "sender": "assistant",
            "content": assistant_msg,
            "timestamp": utc_now(),
            "metadata": {"type": "booking_summary", "summary": summary},
        })

        doc["updatedAt"] = utc_now()
        get_booking_session_collection(db).replace_one({"_id": ObjectId(session_id)}, doc)
        return _to_response_schema(doc)

    @classmethod
    async def confirm_booking(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
        req: ConfirmBookingRequest,
    ) -> BookingSessionResponse:
        """Patient explicitly confirms the booking summary, creating a 10-minute hold."""
        doc = cls._get_session_or_404(db, patient_user, session_id)
        current_state = doc.get("state")

        # Idempotency: If hold is already created and unexpired, return it
        now = utc_now()
        if doc.get("appointmentId") and doc.get("holdExpiresAt"):
            hold_exp = doc["holdExpiresAt"]
            if hold_exp.tzinfo is None:
                hold_exp = hold_exp.replace(tzinfo=timezone.utc)
            if hold_exp > now:
                return _to_response_schema(doc)

        if current_state != BookingAgentState.AWAITING_BOOKING_CONFIRMATION.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm booking in state '{current_state}'. Please select a slot first.",
            )

        selected_doctor = doc.get("selectedDoctor")
        selected_slot = doc.get("selectedSlot")
        if not selected_doctor or not selected_slot:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor and slot must be selected before confirming.",
            )

        # Call existing AppointmentService to create appointment with 10-min hold
        appt_req = CreateAppointmentRequest(
            doctorId=selected_doctor["doctorId"],
            availabilityId=selected_slot["availabilityId"],
            date=selected_slot["date"],
            startTime=selected_slot["startTime"],
            patientNote=req.patientNote or (doc.get("preferences") or {}).get("patientNote"),
        )

        try:
            appt_response = await AppointmentService.create_appointment(
                db=db,
                patient_user=patient_user,
                req=appt_req,
            )
        except HTTPException as e:
            # Slot no longer available or double booking conflict
            if e.status_code in [status.HTTP_409_CONFLICT, status.HTTP_400_BAD_REQUEST]:
                doc["state"] = BookingAgentState.BOOKING_FAILED.value
                doc["updatedAt"] = now
                doc["messages"].append({
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": (
                        "Unfortunately, this appointment slot is no longer available. "
                        "Please select another available slot or another doctor."
                    ),
                    "timestamp": now,
                    "metadata": {"type": "booking_conflict", "error": e.detail},
                })
                get_booking_session_collection(db).replace_one({"_id": ObjectId(session_id)}, doc)
            raise e

        # Hold created successfully
        appointment_data = appt_response.appointment
        doc["appointmentId"] = str(appointment_data.id)
        doc["holdExpiresAt"] = appointment_data.holdExpiresAt or (now + timedelta(minutes=10))

        target_state = BookingAgentState.AWAITING_PAYMENT.value
        if validate_state_transition(current_state, target_state):
            doc["state"] = target_state

        lang = (doc.get("preferences") or {}).get("language", "en")
        doc_name = selected_doctor.get("fullName", "Doctor")
        total_amt = doc.get("bookingSummary", {}).get("totalAmount", 2500.0)

        assistant_msg = (
            f"ඔබේ වේලාව සාර්ථකව විනාඩි 10 ක කාලයක් සඳහා වෙන් කර ඇත (Hold Created). "
            f"කරුණාකර පහත 'Pay Now (LKR {total_amt:,.0f})' බොත්තම ඔබා Stripe හරහා ඔබගේ ගෙවීම සිදු කරන්න."
            if lang == "si"
            else f"Your appointment slot with {doc_name} has been held for 10 minutes. "
            f"Please tap 'Pay Now (LKR {total_amt:,.0f})' below to securely complete your payment with Stripe."
        )

        doc["messages"].append({
            "id": str(ObjectId()),
            "sender": "assistant",
            "content": assistant_msg,
            "timestamp": now,
            "metadata": {
                "type": "hold_created",
                "appointmentId": str(appointment_data.id),
                "holdExpiresAt": doc["holdExpiresAt"].isoformat() if hasattr(doc["holdExpiresAt"], "isoformat") else str(doc["holdExpiresAt"]),
            },
        })

        doc["updatedAt"] = now
        get_booking_session_collection(db).replace_one({"_id": ObjectId(session_id)}, doc)
        return _to_response_schema(doc)

    @classmethod
    async def cancel_session(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
    ) -> BookingSessionResponse:
        """Cancel the active booking session and release any held appointment."""
        doc = cls._get_session_or_404(db, patient_user, session_id)
        current_state = doc.get("state")

        # Cancel held appointment if present
        if doc.get("appointmentId"):
            appt_id = doc["appointmentId"]
            if ObjectId.is_valid(appt_id):
                appt = db["appointments"].find_one({"_id": ObjectId(appt_id)})
                if appt and appt.get("status") in [AppointmentStatus.HOLD.value, AppointmentStatus.PENDING.value]:
                    try:
                        await AppointmentService.cancel_appointment(
                            db=db,
                            patient_user=patient_user,
                            appointment_id=appt_id,
                            req=CancelAppointmentRequest(reason="Patient cancelled AI booking session"),
                        )
                    except Exception as e:
                        logger.warning(f"Error cancelling appointment {appt_id} on session cancel: {e}")

        now = utc_now()
        doc["state"] = BookingAgentState.CANCELLED.value
        doc["updatedAt"] = now
        doc["messages"].append({
            "id": str(ObjectId()),
            "sender": "system",
            "content": "Booking session has been cancelled.",
            "timestamp": now,
            "metadata": {"type": "session_cancelled"},
        })

        get_booking_session_collection(db).replace_one({"_id": ObjectId(session_id)}, doc)
        return _to_response_schema(doc)

    @classmethod
    async def sync_payment_status(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
    ) -> BookingSessionResponse:
        """Authoritatively verify payment & appointment status from database."""
        doc = cls._get_session_or_404(db, patient_user, session_id)
        cls._sync_hold_and_payment_status(db, doc)
        get_booking_session_collection(db).replace_one({"_id": ObjectId(session_id)}, doc)
        return _to_response_schema(doc)

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------
    @classmethod
    def _get_session_or_404(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
    ) -> Dict[str, Any]:
        """Fetch session and strictly enforce patient ownership."""
        if not ObjectId.is_valid(session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format.",
            )

        collection = get_booking_session_collection(db)
        doc = collection.find_one({"_id": ObjectId(session_id)})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking session not found.",
            )

        # Strict Ownership Security Check
        if str(doc.get("patientUserId")) != str(patient_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this booking session.",
            )

        return doc

    @classmethod
    def _sync_hold_and_payment_status(cls, db: Database, doc: Dict[str, Any]) -> None:
        """Check appointment and hold validity against database."""
        now = utc_now()
        appt_id = doc.get("appointmentId")
        if not appt_id or not ObjectId.is_valid(appt_id):
            return

        appt = db["appointments"].find_one({"_id": ObjectId(appt_id)})
        if not appt:
            return

        appt_status = appt.get("status")
        pay_status = appt.get("paymentStatus")

        # Payment succeeded
        if pay_status == ApptPaymentStatus.PAID.value or appt_status == AppointmentStatus.CONFIRMED.value:
            if doc.get("state") != BookingAgentState.BOOKING_CONFIRMED.value:
                doc["state"] = BookingAgentState.BOOKING_CONFIRMED.value
                doc["updatedAt"] = now
                doc["messages"].append({
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": (
                        "🎉 Payment confirmed! Your appointment has been successfully scheduled. "
                        "You can view your appointment details anytime under 'My Appointments'."
                    ),
                    "timestamp": now,
                    "metadata": {"type": "booking_confirmed", "appointmentId": str(appt["_id"])},
                })
            return

        # Check for hold expiration
        hold_exp = appt.get("holdExpiresAt")
        if hold_exp:
            if hold_exp.tzinfo is None:
                hold_exp = hold_exp.replace(tzinfo=timezone.utc)
            if hold_exp <= now and appt_status in [AppointmentStatus.HOLD.value, AppointmentStatus.PENDING.value]:
                if doc.get("state") not in [BookingAgentState.EXPIRED.value, BookingAgentState.BOOKING_CONFIRMED.value]:
                    doc["state"] = BookingAgentState.EXPIRED.value
                    doc["updatedAt"] = now
                    doc["messages"].append({
                        "id": str(ObjectId()),
                        "sender": "assistant",
                        "content": (
                            "Your 10-minute booking hold has expired. The time slot has been released. "
                            "Please choose a slot again to book your appointment."
                        ),
                        "timestamp": now,
                        "metadata": {"type": "hold_expired"},
                    })
