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
from app.schemas.appointment import CreateAppointmentRequest
from app.services.ai_booking_proposal import prepare_proposal
from app.schemas.booking_session import (
    BookingPreferencesSchema,
    AssistantResponse,
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

    def message_timestamp(message: Dict[str, Any]) -> datetime:
        timestamp = message.get("timestamp") or utc_now()
        # MongoDB stores BSON dates at millisecond precision.
        return timestamp.replace(microsecond=timestamp.microsecond // 1000 * 1000)

    messages = [
        ChatMessageSchema(
            id=str(m.get("id", ObjectId())),
            sender=m.get("sender", "assistant"),
            content=m.get("content", ""),
            timestamp=message_timestamp(m),
            metadata=m.get("metadata"),
        )
        for m in doc.get("messages", [])
    ]

    def _map_doctor_card(d: Dict[str, Any]) -> DoctorCardSummary:
        raw_slots = d.get("availableSlots") or []
        slots = [
            SlotCardSummary(
                availabilityId=str(s.get("availabilityId", "")),
                date=s.get("date", ""),
                startTime=s.get("startTime", ""),
                endTime=s.get("endTime", ""),
            )
            for s in raw_slots
        ]
        return DoctorCardSummary(
            doctorId=str(d.get("doctorId", "")),
            doctorProfileId=str(d.get("doctorProfileId", "")),
            doctorUserId=str(d.get("doctorUserId", "")),
            fullName=d.get("fullName", "Doctor"),
            specialty=d.get("specialty") or "Specialty not listed",
            hospitalOrClinic=d.get("hospitalOrClinic"),
            experienceYears=int(d.get("experienceYears") or 0),
            consultationFee=d.get("consultationFee"),
            city=d.get("city"),
            profileImage=d.get("profileImage"),
            rating=float(d.get("rating") or 0),
            nextAvailableDate=d.get("nextAvailableDate"),
            matchReason=d.get("matchReason"),
            qualifications=d.get("qualifications"),
            matchScore=float(d["matchScore"]) if d.get("matchScore") is not None else None,
            matchReasons=list(d.get("matchReasons") or []),
            ratingCount=d.get("ratingCount"),
            rankPosition=d.get("rankPosition"),
            rankingExplanation=d.get("rankingExplanation"),
            availableSlots=slots,
            requestedDate=d.get("requestedDate"),
            requestedTime=d.get("requestedTime"),
        )

    selected_doc = _map_doctor_card(doc["selectedDoctor"]) if doc.get("selectedDoctor") else None

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
    bs = doc.get("bookingSummary") or {}
    # A03-BUG-017: a summary without the server-owned fee and total is not presented (it defaulted to LKR 2,500).
    if bs and isinstance(bs.get("consultationFee"), (int, float)) and isinstance(bs.get("totalAmount"), (int, float)):
        booking_summary = BookingSummary(
            doctorName=bs.get("doctorName", "Doctor"),
            specialty=bs.get("specialty", ""),
            hospitalOrClinic=bs.get("hospitalOrClinic"),
            appointmentDate=bs.get("appointmentDate", ""),
            startTime=bs.get("startTime", ""),
            endTime=bs.get("endTime", ""),
            consultationFee=float(bs["consultationFee"]),
            serviceFee=float(bs.get("serviceFee", 0.0)),
            totalAmount=float(bs["totalAmount"]),
            currency=bs.get("currency", "lkr"),
            **{key: bs.get(key) for key in ("proposalId", "proposalExpiresAt", "timezone", "city", "patientName",
                                           "maskedEmail", "maskedPhone", "requestedTime", "selectionReason")},
            visitType=bs.get("visitType") or "IN_PERSON",
        )

    candidate_docs = [_map_doctor_card(d) for d in doc.get("candidateDoctors", [])]

    candidate_slots = [
        SlotCardSummary(
            availabilityId=str(s.get("availabilityId", "")),
            date=s.get("date", ""),
            startTime=s.get("startTime", ""),
            endTime=s.get("endTime", ""),
        )
        for s in doc.get("candidateSlots", [])
    ]

    last = messages[-1] if messages else None
    structured = None
    if doc.get("persistent") and last and last.sender == "assistant":
        metadata = last.metadata or {}
        cards = [_map_doctor_card(doctor) for doctor in metadata.get("doctors") or []]
        structured = AssistantResponse(
            assistant_message=last.content,
            detected_intent=doc.get("activeIntent") or metadata.get("type") or "FOLLOW_UP",
            conversation_id=str(doc["_id"]),
            doctor_cards=cards,
            availability_slots=candidate_slots or [slot for card in cards for slot in card.availableSlots],
            tool_results=[{"doctor_count": len(cards)}] if metadata.get("type") in {"doctor_options", "no_results"} else [],
            error_code=metadata.get("error_code"),
            booking_state=doc.get("state"),
            requires_user_action=bool(cards or candidate_slots),
        )
    return BookingSessionResponse(
        assistantResponse=structured,
        bookingResult=doc.get("bookingResult"),
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
            symptoms=prefs.get("symptoms"),
            preferredGender=prefs.get("preferredGender"),
            sortBy=prefs.get("sortBy"),
            minRating=prefs.get("minRating"),
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
        activeIntent=doc.get("activeIntent"),
        activeMedicineCard=doc.get("activeMedicineCard"),
        activeWellnessCard=doc.get("activeWellnessCard"),
        activeImageAnalysis=doc.get("activeImageAnalysis"),
        createdAt=doc.get("createdAt", utc_now()),
        updatedAt=doc.get("updatedAt", utc_now()),
        expiresAt=doc.get("expiresAt"),
    )



def conversation_retention():
    """Saved AI conversations may contain health information. With CONVERSATION_RETENTION_DAYS > 0 each saved
    conversation expires that many days after its last message (the existing TTL index on expiresAt deletes it).
    The default 0 keeps conversations until the patient deletes them, as before; the retention period is an owner
    privacy decision (Phase 05)."""
    from app.config.settings import settings
    days = int(getattr(settings, "CONVERSATION_RETENTION_DAYS", 0) or 0)
    return {"expiresAt": utc_now() + timedelta(days=days)} if days > 0 else {}


class BookingSessionService:
    """Coordinates conversational turns, state verification, doctor selection, and booking hold creation."""

    @classmethod
    async def create_session(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        req: CreateSessionRequest,
        *,
        persistent: bool = False,
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
                patient_user=patient_user if persistent else None,
                user_message=req.initialMessage.strip(),
            )
            if persistent:
                try:
                    await prepare_proposal(db, patient_user, initial_dict, automatic=True)
                except HTTPException as exc:
                    if exc.status_code not in {400, 404, 409}:
                        raise
        else:
            greeting = (
                "Hello! I'm your MediConnect AI Assistant. "
                "Tell me which doctor, specialty, or city you're looking for. "
                "I can also help you check slots or answer general health questions."
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

        if persistent:
            initial_dict.pop("expiresAt", None)
            initial_dict.update(conversation_retention())
            initial_dict["persistent"] = True
            initial_dict["draft"] = not bool(req.initialMessage and req.initialMessage.strip())
            initial_dict["title"] = (req.initialMessage or "").strip()[:70] or "New Chat"
            initial_dict["preview"] = initial_dict["messages"][-1]["content"][:160]
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
        message_count = len(doc["messages"])
        cls._sync_hold_and_payment_status(db, doc)
        if doc.get("persistent") and len(doc["messages"]) != message_count:
            cls._save(db, doc)
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

        message = req.message.strip()
        if not message:
            raise HTTPException(422, "Enter a message.")
        if req.requestId:
            for item in doc["messages"]:
                if (item.get("metadata") or {}).get("requestId") == req.requestId:
                    if item["content"] != message:
                        raise HTTPException(409, "This request ID already belongs to another message.")
                    return _to_response_schema(doc)
        if doc.get("persistent") and len(doc["messages"]) >= 500:
            raise HTTPException(409, "This conversation is full. Start a New Chat to continue.")
        if not doc.get("persistent") and doc.get("state") in (
            BookingAgentState.BOOKING_CONFIRMED.value, BookingAgentState.CANCELLED.value,
        ):
            raise HTTPException(400, "This booking session has ended. Start a new session.")

        cls._sync_hold_and_payment_status(db, doc)

        first_new_message = len(doc["messages"])
        # Process user message through conversational agent
        updated_dict = await BookingAgent.process_user_turn(
            db=db,
            session_data=doc,
            patient_user=patient_user if doc.get("persistent") else None,
            user_message=message,
            image_url=req.imageUrl,
        )

        if updated_dict.get("persistent"):
            try:
                await prepare_proposal(db, patient_user, updated_dict, automatic=True)
                last_meta = updated_dict["messages"][-1].get("metadata") or {}
                summary = updated_dict.get("bookingSummary") or {}
                if last_meta.get("type") == "booking_summary" and not summary.get("proposalId"):
                    # A time typed for the selected doctor becomes a server-owned proposal, exactly like a
                    # slot picked from the cards (re-verified price and slot; patient acceptance required).
                    await prepare_proposal(db, patient_user, updated_dict)
                    updated_dict["messages"][-1]["content"] = (
                        "Review the proposed appointment below. Your booking requires your acceptance."
                    )
                    updated_dict["messages"][-1]["metadata"] = {
                        "type": "booking_proposal", "proposalId": updated_dict["bookingSummary"]["proposalId"],
                    }
            except HTTPException as exc:
                if exc.status_code not in {400, 404, 409}:
                    raise
        if req.requestId:
            user_message = updated_dict["messages"][first_new_message]
            user_message["metadata"] = {**(user_message.get("metadata") or {}), "requestId": req.requestId}
        if not updated_dict.get("persistent"):
            updated_dict["updatedAt"] = utc_now()
            updated_dict["expiresAt"] = utc_now() + timedelta(minutes=30)
        if updated_dict.get("draft"):
            updated_dict["title"] = message[:70]
            updated_dict["draft"] = False
        cls._save(db, updated_dict)
        return _to_response_schema(updated_dict)

    @classmethod
    async def handle_image_message(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        session_id: str,
        image_bytes: bytes,
        filename: str,
        message: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> BookingSessionResponse:
        """Process an uploaded medicine package or label image directly in the companion session."""
        doc = cls._get_session_or_404(db, patient_user, session_id)

        current_state = doc.get("state")
        if not doc.get("persistent") and current_state in [
            BookingAgentState.BOOKING_CONFIRMED.value, BookingAgentState.CANCELLED.value,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This session is already {current_state.lower()}. Please start a new session.",
            )
        if doc.get("persistent") and len(doc.get("messages") or []) >= 500:
            raise HTTPException(409, "This conversation is full. Start a New Chat to continue.")

        cls._sync_hold_and_payment_status(db, doc)

        updated_dict = await BookingAgent.process_user_turn(
            db=db,
            session_data=doc,
            user_message=message or "Please analyze this medicine label photo.",
            image_bytes=image_bytes,
            image_filename=filename,
            image_url=image_url,
        )

        updated_dict["updatedAt"] = utc_now()
        if updated_dict.get("draft"):
            updated_dict["draft"] = False
            updated_dict["title"] = (message or "").strip()[:70] or "Medicine label photo"
        if not updated_dict.get("persistent"):
            updated_dict["expiresAt"] = utc_now() + timedelta(minutes=30)

        cls._save(db, updated_dict)

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

        cls._sync_hold_and_payment_status(db, doc)
        current_state = doc.get("state")
        if doc.get("persistent") and current_state in {
            BookingAgentState.AWAITING_PAYMENT.value,
            BookingAgentState.PAYMENT_PENDING_VERIFICATION.value,
            BookingAgentState.BOOKING_HOLD_CREATED.value,
        }:
            raise HTTPException(409, "Complete the current booking or start a New Chat to check another slot.")
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
            "specialty": profile.get("specialty") or "Specialty not listed",
            "hospitalOrClinic": profile.get("hospitalOrClinic"),
            "experienceYears": int(profile.get("experienceYears", 0)),
            "consultationFee": profile.get("consultationFee"),
            "rating": profile.get("rating") or 0,
        }

        if doctor_dict["consultationFee"] is None:
            raise HTTPException(422, "This doctor has no consultation fee listed. Contact the clinic for booking.")
        doc["selectedDoctor"] = doctor_dict
        doc["selectedSlot"] = None
        doc["bookingSummary"] = None

        # Fetch unbooked discrete slots
        prefs = doc.get("preferences") or {}
        slots = await BookingAgent._fetch_available_slots(db, doctor_dict["doctorId"], req.date or prefs.get("date"))
        doc["candidateSlots"] = slots

        target_state = BookingAgentState.AWAITING_SLOT_SELECTION.value
        if validate_state_transition(current_state, target_state) or doc.get("persistent"):
            doc["state"] = target_state
            if current_state in {BookingAgentState.EXPIRED.value, BookingAgentState.BOOKING_CONFIRMED.value}:
                doc["appointmentId"] = None
                doc["paymentId"] = None
                doc["holdExpiresAt"] = None

        lang = prefs.get("language", "en")
        assistant_msg = BookingAgent._build_slot_selection_message(doctor_dict, slots, lang)
        doc["messages"].append({
            "id": str(ObjectId()),
            "sender": "assistant",
            "content": assistant_msg,
            "timestamp": utc_now(),
            "metadata": {"type": "slot_selection", "doctorId": doctor_dict["doctorId"], "date": req.date},
        })

        doc["updatedAt"] = utc_now()
        cls._save(db, doc)
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

        proposal_enabled = doc.get("phase2Proposal") or (doc.get("persistent") and req.prepareProposal)
        if proposal_enabled:
            day = await DoctorService.get_doctor_patient_slots(db, selected_doctor["doctorId"], req.date)
            match = next((slot for slot in day.slots if slot.availabilityId == req.availabilityId
                          and slot.startTime == req.startTime), None)
            if not match:
                raise HTTPException(409, "The selected slot is no longer available.")
            if doc.get("appointmentId") and current_state in {"AWAITING_PAYMENT", "BOOKING_CONFIRMED"}:
                raise HTTPException(409, "Manage the existing booking before changing the slot.")
            slot_dict = {"availabilityId": req.availabilityId, "date": req.date,
                         "startTime": match.startTime, "endTime": match.endTime}
        else:
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
        if proposal_enabled:
            await prepare_proposal(db, patient_user, doc)
            summary = doc["bookingSummary"]

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
            "metadata": {"type": "booking_summary", "summary": BookingSummary.model_validate(summary).model_dump()},
        })

        doc["updatedAt"] = utc_now()
        cls._save(db, doc)
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
        if not doc.get("persistent"):
            return await cls._create_hold(db, patient_user, doc, req)

        # Claim the conversation before calling the appointment service. A concurrent
        # send, selection, rename, or delete cannot replace it during confirmation.
        now = utc_now()
        collection = get_booking_session_collection(db)
        revision = doc.get("revision", {"$exists": False})
        token = str(ObjectId())
        claimed = collection.update_one(
            {
                "_id": doc["_id"],
                "patientUserId": doc["patientUserId"],
                "revision": revision,
                "confirmationUntil": {"$not": {"$gt": now}},
            },
            {"$set": {"confirmationUntil": now + timedelta(seconds=90), "confirmationToken": token}},
        )
        if not claimed.matched_count:
            raise HTTPException(409, "A booking update is in progress. Please retry.")
        doc["confirmationToken"] = token
        try:
            return await cls._create_hold(db, patient_user, doc, req, confirmation_token=token)
        finally:
            collection.update_one(
                {"_id": doc["_id"], "confirmationToken": token},
                {"$unset": {"confirmationUntil": "", "confirmationToken": ""}},
            )

    @classmethod
    async def _create_hold(
        cls, db, patient_user, doc, req, *, confirmation_token=None,
    ) -> BookingSessionResponse:
        current_state = doc.get("state")

        proposal = doc.get("bookingSummary") or {}
        proposal_id = proposal.get("proposalId")
        if (proposal_id and req.proposalId != proposal_id) or (req.proposalId and not proposal_id) or (
            doc.get("phase2Proposal") and not proposal_id
        ):
            raise HTTPException(409, "Review and accept the current booking proposal.")
        if proposal_id and not doc.get("appointmentId"):
            expiry = proposal["proposalExpiresAt"]
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= utc_now() and not db["appointments"].find_one({
                "_id": ObjectId(proposal_id), "patientUserId": str(patient_user.id),
            }, {"_id": 1}):
                raise HTTPException(409, "The proposal expired. Request an updated slot.")
        if proposal_id and doc.get("state") == "BOOKING_CONFIRMED":
            return _to_response_schema(doc)

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
            patientNote=req.patientNote if proposal_id else req.patientNote or (doc.get("preferences") or {}).get("patientNote"),
        )

        options = {}
        if proposal_id:
            if (selected_doctor["doctorId"] != proposal.get("doctorId")
                or selected_slot != proposal.get("acceptedSlot")):
                raise HTTPException(409, "The booking details changed. Review a new proposal.")
            prof_query = {"doctorId": selected_doctor["doctorId"]}
            if selected_doctor.get("doctorProfileId") and ObjectId.is_valid(selected_doctor["doctorProfileId"]):
                prof_query = {"$or": [{"_id": ObjectId(selected_doctor["doctorProfileId"])}, {"doctorId": selected_doctor["doctorId"]}]}
            live_doc_prof = db["doctor_profiles"].find_one(prof_query)
            if live_doc_prof and live_doc_prof.get("consultationFee") is not None and proposal.get("consultationFee") is not None:
                if float(live_doc_prof["consultationFee"]) != float(proposal["consultationFee"]):
                    raise HTTPException(409, "The consultation fee changed. Review a new proposal.")
            options = {"accepted_proposal": proposal, "proposal_slot": selected_slot,
                       "sms_consent": req.smsConsent and bool(proposal.get("maskedPhone"))}
        try:
            appt_response = await AppointmentService.create_appointment(
                db=db, patient_user=patient_user, req=appt_req, **options,
            )
        except HTTPException as e:
            # Slot no longer available or double booking conflict
            if e.status_code in [status.HTTP_409_CONFLICT, status.HTTP_400_BAD_REQUEST]:
                doc["state"] = BookingAgentState.BOOKING_FAILED.value
                doc["updatedAt"] = now
                # P-05n: the losing patient gets real nearby times for the same doctor (nothing about who
                # holds the slot is revealed).
                try:
                    alternatives = [s for s in await BookingAgent._fetch_available_slots(
                        db, selected_doctor["doctorId"], selected_slot["date"],
                        preferred_time=selected_slot["startTime"],
                    ) if s.get("date") == selected_slot["date"]][:4]
                except Exception:
                    alternatives = []
                if alternatives:
                    doc["candidateSlots"] = alternatives
                times = ", ".join(s["startTime"] for s in alternatives)
                doc["messages"].append({
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": (
                        "Unfortunately, this appointment slot is no longer available. "
                        + (f"Open times with {selected_doctor.get('fullName', 'the doctor')} that day: {times}. "
                           "Choose one, or select another doctor." if alternatives else
                           "Please select another available slot or another doctor.")
                    ),
                    "timestamp": now,
                    "metadata": {"type": "booking_conflict", "error": e.detail, "alternatives": alternatives},
                })
                cls._save(db, doc, confirmation_token=confirmation_token)
            raise e

        # Hold created successfully
        appointment_data = appt_response.appointment
        doc["appointmentId"] = str(appointment_data.id)
        doc["holdExpiresAt"] = appointment_data.holdExpiresAt
        if proposal_id and appointment_data.status == "CONFIRMED":
            cls._sync_hold_and_payment_status(db, doc)
            cls._save(db, doc, confirmation_token=confirmation_token)
            return _to_response_schema(doc)

        target_state = BookingAgentState.AWAITING_PAYMENT.value
        if validate_state_transition(current_state, target_state):
            doc["state"] = target_state

        lang = (doc.get("preferences") or {}).get("language", "en")
        doc_name = selected_doctor.get("fullName", "Doctor")
        # A03-BUG-017: never an invented amount (BUG-028); the summary always carries the server-owned total.
        total_amt = (doc.get("bookingSummary") or {}).get("totalAmount")
        pay_label = f"Pay Now (LKR {total_amt:,.0f})" if isinstance(total_amt, (int, float)) else "Pay Now"

        assistant_msg = (
            f"ඔබේ වේලාව සාර්ථකව විනාඩි 10 ක කාලයක් සඳහා වෙන් කර ඇත (Hold Created). "
            f"කරුණාකර පහත '{pay_label}' බොත්තම ඔබා Stripe හරහා ඔබගේ ගෙවීම සිදු කරන්න."
            if lang == "si"
            else f"Your appointment slot with {doc_name} has been held for 10 minutes. "
            f"Please tap '{pay_label}' below to securely complete your payment with Stripe."
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
        cls._sync_hold_and_payment_status(db, doc)
        cls._save(db, doc, confirmation_token=confirmation_token)
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
        if doc.get("appointmentId"):
            appointment_id = doc["appointmentId"]
            if not ObjectId.is_valid(appointment_id):
                raise HTTPException(409, "The linked appointment could not be verified.")
            appointment = db["appointments"].find_one({
                "_id": ObjectId(appointment_id), "patientUserId": str(patient_user.id),
            })
            if not appointment:
                raise HTTPException(404, "The linked appointment could not be found.")
            if appointment["status"] in {AppointmentStatus.HOLD.value, AppointmentStatus.PENDING.value}:
                # Same race-safe path as the Release Reservation action (BUG-063): open PaymentIntents are
                # cancelled before the slot is released, and a paid hold is never cancelled here.
                await AppointmentService.cancel_patient_appointment(
                    db=db, patient_user=patient_user, appointment_id=appointment_id,
                    reason="Patient cancelled AI booking session", only_hold=True,
                )
            elif appointment["status"] != AppointmentStatus.CANCELLED.value:
                raise HTTPException(409, "Manage this appointment from My Appointments.")

        now = utc_now()
        released = bool(doc.get("appointmentId"))
        doc["state"] = BookingAgentState.CANCELLED.value
        doc["updatedAt"] = now
        doc["holdExpiresAt"] = None
        doc["messages"].append({
            "id": str(ObjectId()),
            "sender": "system",
            "content": ("Your reservation was released and the time slot is available again. No payment was taken."
                        if released else "Booking session has been cancelled."),
            "timestamp": now,
            "metadata": {"type": "session_cancelled"},
        })

        cls._save(db, doc)
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
        if doc.get("appointmentId") and doc.get("phase2Proposal"):
            payment = db["payments"].find_one(
                {"appointmentId": doc["appointmentId"], "patientUserId": str(patient_user.id)},
                sort=[("createdAt", -1)],
            )
            if payment and payment.get("status") in {"PENDING", "FAILED"}:  # a decline can be followed by a success (A03-BUG-004)
                from app.services.payment_service import PaymentService
                await PaymentService.get_payment_status(db, str(payment["_id"]), patient_user)
        cls._sync_hold_and_payment_status(db, doc)
        cls._save(db, doc)
        return _to_response_schema(doc)

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------
    @staticmethod
    def _save(db: Database, doc: Dict[str, Any], *, confirmation_token: str | None = None) -> None:
        collection = get_booking_session_collection(db)
        query = {"_id": doc["_id"], "patientUserId": doc["patientUserId"]}
        if doc.get("draft") and (doc.get("selectedDoctor") or doc.get("appointmentId") or doc.get("bookingSummary")):
            # P02-N06: a chat that holds booking state is no longer an empty draft, so "New Chat" never reopens it.
            doc["draft"] = False
            if doc.get("title") in (None, "", "New Chat"):
                doc["title"] = "Appointment booking"
        if doc.get("persistent"):
            revision = doc.get("revision")
            query["revision"] = revision if revision is not None else {"$exists": False}
            if confirmation_token:
                query["confirmationToken"] = confirmation_token
            else:
                query["confirmationUntil"] = {"$not": {"$gt": utc_now()}}
            doc.pop("confirmationUntil", None)
            doc.pop("confirmationToken", None)
            doc["revision"] = (revision or 0) + 1
            doc["updatedAt"] = utc_now()
            doc["preview"] = doc["messages"][-1]["content"][:160]
            doc.pop("expiresAt", None)
            doc.update(conversation_retention())
        result = collection.replace_one(query, doc)
        if doc.get("persistent") and not result.matched_count:
            raise HTTPException(409, "The conversation changed. Reload it and retry.")

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

        if appt.get("bookingSource") == "ai_agent":
            doc["bookingResult"] = {
                "reference": str(appt["_id"]), "status": appt_status, "paymentStatus": pay_status,
                "doctor": appt.get("bookingDoctorName"), "clinic": appt.get("hospitalOrClinic"),
                "date": appt["appointmentDate"], "time": appt["startTime"],
                "notifications": {name: item["status"] for name, item in
                                  (appt.get("confirmationOutbox") or {}).items()},
            }
            if appt_status != "CONFIRMED":
                reconciliation = db["payments"].find_one({
                    "appointmentId": str(appt["_id"]), "reconciliationState": {"$in": ["REVIEW_REQUIRED", "REFUND_PENDING", "REFUNDED"]},
                }, {"reconciliationState": 1})
                if reconciliation:
                    doc["bookingResult"]["reconciliationState"] = reconciliation["reconciliationState"]

        # Payment succeeded
        if (pay_status == ApptPaymentStatus.PAID.value or appt.get("acceptedAmountMinor") == 0) and appt_status == AppointmentStatus.CONFIRMED.value:
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
