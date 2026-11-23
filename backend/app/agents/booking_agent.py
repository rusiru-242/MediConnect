"""Conversational AI Booking Agent with bilingual multi-turn dialog, state machine, and safety checks."""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException
from pymongo.database import Database

from app.agents.ai_provider import get_ai_provider
from app.agents.companion_intent import CompanionIntent, CompanionIntentClassifier
from app.agents.medicine_knowledge import MedicineKnowledge
from app.agents.wellness_knowledge import WellnessKnowledge
from app.agents.medicine_image_agent import MedicineImageAgent
from app.agents.nlp_parser import (
    detect_language,
    check_urgency,
    parse_query_deterministically,
    extract_appointment_time,
)
from app.agents.orchestrator import AIOrchestrator
from app.agents.symptom_triage import SymptomTriageEngine, TriageLevel
from app.config.settings import settings
from app.models.booking_session import (
    ALLOWED_STATE_TRANSITIONS,
    BookingAgentState,
    utc_now,
)
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole
from app.services.doctor_service import (
    DoctorService,
    get_sl_today_str,
)

logger = logging.getLogger(__name__)

EMERGENCY_EN_ALERT = (
    "POTENTIAL MEDICAL EMERGENCY DETECTED: Symptoms such as sudden chest pain, breathing difficulty, "
    "sudden numbness, heavy bleeding, or loss of consciousness require immediate professional evaluation. "
    "Please proceed immediately to the nearest hospital emergency department (ETU) or call Sri Lanka "
    "emergency ambulance service (1990). Do not delay for a scheduled clinic appointment."
)

EMERGENCY_SI_ALERT = (
    "හදිසි වෛද්‍ය අවධානයක් අවශ්‍ය විය හැකිය: හදිසි පපුවේ කැක්කුම, හුස්ම ගැනීමේ අපහසුව, සිහිසුන්වීම හෝ "
    "අධික රුධිර වහනය වැනි රෝග ලක්ෂණ ඇත්නම් වහාම ළඟම ඇති රෝහලේ හදිසි ප්‍රතිකාර ඒකකයට (ETU) යන්න "
    "හෝ 1990 සුවසැරිය ගිලන්රථ සේවය අමතන්න. සායන වේලාවක් වෙන්කරවා ගැනීම සඳහා කාලය ප්‍රමාද නොකරන්න."
)

EMERGENCY_TA_ALERT = (
    "அவசர மருத்துவ கவனிப்பு தேவைப்படலாம்: திடீர் நெஞ்சு வலி, மூச்சுத்திணறல், "
    "திடீர் மரத்துப்போதல், கடுமையான இரத்தப்போக்கு அல்லது மயக்கம் போன்ற அறிகுறிகள் இருந்தால், "
    "உடனடியாக அருகிலுள்ள அவசர சிகிச்சை பிரிவுக்கு (ETU) செல்லவும் அல்லது 1990 அவசர ஆம்புலன்ஸ் "
    "சேவையை அழைக்கவும். கிளினிக் சந்திப்புக்காக நேரத்தை வீணடிக்க வேண்டாம்."
)


def validate_state_transition(from_state: str, to_state: str) -> bool:
    """Check if the transition between two booking agent states is permitted."""
    allowed = ALLOWED_STATE_TRANSITIONS.get(from_state, set())
    return to_state in allowed


class BookingAgent:
    """Conversational booking agent maintaining session context and state transitions."""

    @classmethod
    async def process_user_turn(
        cls,
        db: Database,
        session_data: Dict[str, Any],
        user_message: str,
        image_bytes: Optional[bytes] = None,
        image_filename: Optional[str] = None,
        image_url: Optional[str] = None,
        patient_user=None,
    ) -> Dict[str, Any]:
        """Process a user conversational turn, update preferences, and transition state."""
        clean_text = user_message.strip()
        current_state = session_data.get("state", BookingAgentState.COLLECTING_PREFERENCES.value)
        prefs = dict(session_data.get("preferences") or {})
        previous_preferences = dict(prefs)

        # 1. Emergency symptom check
        is_urgent, urgency_reason = check_urgency(clean_text)
        triage, triage_reason, _ = SymptomTriageEngine.classify_triage_pre_check(clean_text, "en")
        if is_urgent or triage == TriageLevel.EMERGENCY:
            urgency_reason = urgency_reason or triage_reason
            session_data["isUrgent"] = True
            session_data["urgencyReason"] = urgency_reason
            detected = detect_language(clean_text)
            lang = detected if detected in ("si", "ta") else prefs.get("language", "en")
            if lang == "si":
                emergency_text = EMERGENCY_SI_ALERT
            elif lang == "ta":
                emergency_text = EMERGENCY_TA_ALERT
            else:
                emergency_text = EMERGENCY_EN_ALERT

            # Append user message and emergency assistant response
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "user",
                "content": clean_text,
                "timestamp": utc_now(),
                "metadata": {"imageUrl": image_url} if image_url else None,
            })
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": emergency_text,
                "timestamp": utc_now(),
                "metadata": {
                    "isUrgent": True,
                    "ambulanceCall": "1990",
                    "reason": urgency_reason,
                },
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        intent = CompanionIntentClassifier.classify_intent(
            query=clean_text,
            current_state=current_state,
            has_image=bool(image_bytes or image_url),
            candidate_count=len(session_data.get("candidateDoctors") or []),
        )
        parsed_delta = parse_query_deterministically(clean_text)
        provider = get_ai_provider()
        if patient_user and not (image_url or image_bytes) and re.search(
            r"\b(?:appointment status|booking status|mage booking|heta mata appointment|my appointments|my care tasks)\b",
            clean_text, re.I,
        ):
            return await cls._patient_status_turn(db, patient_user, provider, session_data, clean_text)
        requested_time = extract_appointment_time(clean_text)
        if intent == CompanionIntent.FIND_DOCTOR and requested_time and parsed_delta.get("date"):
            intent = CompanionIntent.BOOK_APPOINTMENT
        if re.search(r"\b(?:neurolgist|neurolagist|dermatolgist|cardiolagist)\b", clean_text, re.I):
            session_data.setdefault("messages", []).extend([
                {"id": str(ObjectId()), "sender": "user", "content": clean_text, "timestamp": utc_now()},
                {"id": str(ObjectId()), "sender": "assistant", "content": "Which specialty did you mean? Please confirm the name.",
                 "timestamp": utc_now(), "metadata": {"type": "clarification_needed"}},
            ])
            return session_data
        if not patient_user and intent in {CompanionIntent.FIND_DOCTOR, CompanionIntent.BOOK_APPOINTMENT}:
            try:
                parsed_delta, _ = await asyncio.wait_for(
                    asyncio.to_thread(provider.parse_request, query=clean_text, explicit_filters={}),
                    timeout=settings.AI_TIMEOUT_SECONDS + 1,
                )
                local_date = parse_query_deterministically(clean_text).get('date')
                if local_date:
                    parsed_delta['date'] = local_date
            except Exception as exc:
                logger.warning("Booking preference extraction failed (%s).", type(exc).__name__)

        for key, pattern in {
            "doctorName": r"\bdr\.?\s+([\w .'-]+?)(?=\s+(?:in|at|near)\b|[?!,]|$)",
            "hospital": r"\bat\s+([\w .'-]+(?:hospital|clinic|centre|center))\b",
        }.items():
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                prefs[key] = parsed_delta[key] = match.group(1).strip()[:100]

        selection_text = re.sub(r"^(?:in|near|around)\s+", "", clean_text, flags=re.IGNORECASE)
        selection_text = selection_text.strip(".!? ").casefold()
        filter_only = any(
            isinstance(parsed_delta.get(key), str) and parsed_delta[key].casefold() == selection_text
            for key in ("city", "specialty")
        )
        search_requested = (
            intent == CompanionIntent.FIND_DOCTOR
            or (intent == CompanionIntent.BOOK_APPOINTMENT and bool(parsed_delta.get("specialty") or parsed_delta.get("city")))
            or filter_only
            or any(parsed_delta.get(key) for key in ("doctorName", "hospital"))
            or (parsed_delta.get("specialty") and parsed_delta.get("language") == "si")
            or parsed_delta.get("maxFee") is not None
            or parsed_delta.get("sortBy") is not None
        )
        if re.search(r"\b(?:find|search for|recommend)\b", clean_text, re.IGNORECASE) and search_requested:
            prefs = {
                key: parsed_delta[key]
                for key in ("doctorName", "hospital") if parsed_delta.get(key)
            }

        if requested_time:
            prefs["requestedTime"] = requested_time

        # Merge extracted preferences into session (incremental accumulation)
        if parsed_delta.get("specialty"):
            prefs["specialty"] = parsed_delta["specialty"]
        if parsed_delta.get("city"):
            prefs["city"] = parsed_delta["city"]
        if parsed_delta.get("date"):
            prefs["date"] = parsed_delta["date"]
        if parsed_delta.get("timeRange"):
            prefs["timeRange"] = parsed_delta["timeRange"]
        if parsed_delta.get("maxFee") is not None:
            prefs["maxFee"] = float(parsed_delta["maxFee"])
        if parsed_delta.get("language"):
            prefs["language"] = parsed_delta["language"]
        if parsed_delta.get("symptoms"):
            prefs["symptoms"] = parsed_delta["symptoms"]
        if parsed_delta.get("sortBy"):
            prefs["sortBy"] = parsed_delta["sortBy"]

        # Detect query language (Sinhala Unicode or Singlish) and persist
        detected_lang = detect_language(clean_text)
        if detected_lang == "si":
            prefs["language"] = "si"
        lang = prefs.get("language", "en")
        session_data["preferences"] = prefs

        # Add user message to history
        session_data["messages"].append({
            "id": str(ObjectId()),
            "sender": "user",
            "content": clean_text,
            "timestamp": utc_now(),
            "metadata": {"imageUrl": image_url} if image_url else None,
        })

        # -----------------------------------------------------------------
        # Unified Intent Routing across Companion Capabilities (Phase 40)
        # -----------------------------------------------------------------
        session_data["activeIntent"] = intent.value

        # Capability 1: Medicine Image Analysis (Packaging/Label OCR & Uncertainty)
        if intent == CompanionIntent.MEDICINE_IMAGE_ANALYSIS or image_bytes or image_url:
            if image_bytes and image_filename:
                img_res = await MedicineImageAgent.analyze_medicine_image(
                    image_bytes=image_bytes,
                    filename=image_filename,
                    user_prompt=clean_text,
                )
            else:
                img_res = await MedicineImageAgent.analyze_medicine_image(
                    image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 32,
                    filename="medicine_label.png",
                    user_prompt=clean_text,
                )

            session_data["activeImageAnalysis"] = img_res.get("analysis")
            session_data["activeMedicineCard"] = img_res.get("medicineCard")
            session_data["activeWellnessCard"] = None
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": img_res.get("text", ""),
                "timestamp": utc_now(),
                "metadata": {
                    "type": "medicine_image_analysis",
                    "analysis": img_res.get("analysis"),
                    "card": img_res.get("medicineCard"),
                },
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # Capability 2: Medicine Information Assistant
        if intent == CompanionIntent.MEDICINE_INFORMATION:
            med_res = MedicineKnowledge.generate_educational_response(clean_text, lang=lang)
            session_data["candidateSlots"] = []
            session_data["activeMedicineCard"] = med_res.get("card")
            session_data["activeWellnessCard"] = None
            session_data["activeImageAnalysis"] = None
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": med_res.get("text", ""),
                "timestamp": utc_now(),
                "metadata": {
                    "type": "medicine_information",
                    "card": med_res.get("card"),
                },
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # Capability 3: Healthy Food & Nutrition Assistant
        if intent == CompanionIntent.HEALTHY_FOOD:
            food_res = WellnessKnowledge.get_healthy_food_guidance(clean_text, lang=lang)
            session_data["candidateSlots"] = []
            session_data["activeWellnessCard"] = food_res.get("card")
            session_data["activeMedicineCard"] = None
            session_data["activeImageAnalysis"] = None
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": food_res.get("text", ""),
                "timestamp": utc_now(),
                "metadata": {
                    "type": "healthy_food",
                    "card": food_res.get("card"),
                },
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # Capability 4: Exercise & Mobility Guidance
        if intent == CompanionIntent.EXERCISE_GUIDANCE:
            ex_res = WellnessKnowledge.get_exercise_guidance(clean_text, lang=lang)
            session_data["candidateSlots"] = []
            if ex_res.get("intent") == "EMERGENCY_GUIDANCE":
                session_data["isUrgent"] = True
                session_data["urgencyReason"] = "Concerning symptoms reported during physical activity inquiry."
                session_data["messages"].append({
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": ex_res.get("text", ""),
                    "timestamp": utc_now(),
                    "metadata": {"isUrgent": True, "ambulanceCall": "1990"},
                })
                session_data["updatedAt"] = utc_now()
                return session_data

            session_data["activeWellnessCard"] = ex_res.get("card")
            session_data["activeMedicineCard"] = None
            session_data["activeImageAnalysis"] = None
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": ex_res.get("text", ""),
                "timestamp": utc_now(),
                "metadata": {
                    "type": "exercise_guidance",
                    "card": ex_res.get("card"),
                },
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # Capability 5: General Wellness, Sleep & Lifestyle Habits
        if intent == CompanionIntent.GENERAL_WELLNESS:
            well_res = WellnessKnowledge.get_wellness_guidance(clean_text, lang=lang)
            session_data["candidateSlots"] = []
            session_data["activeWellnessCard"] = well_res.get("card")
            session_data["activeMedicineCard"] = None
            session_data["activeImageAnalysis"] = None
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": well_res.get("text", ""),
                "timestamp": utc_now(),
                "metadata": {
                    "type": "general_wellness",
                    "card": well_res.get("card"),
                },
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # CRITICAL: For all non-wellness turns (doctor search, booking, slots, reset, compare):
        # Clear any previously active wellness, medicine, or image cards so they do NOT linger below
        session_data["activeWellnessCard"] = None
        session_data["activeMedicineCard"] = None
        session_data["activeImageAnalysis"] = None

        # 3. Handle explicit cancel / reset commands
        if re.search(r"\b(?:cancel|abort|start\s+over|reset|අවලංගු)\b", clean_text, re.IGNORECASE):
            if session_data.get("appointmentId"):
                session_data["messages"].append({
                    "id": str(ObjectId()), "sender": "assistant",
                    "content": "Use My Appointments to manage your existing booking. You can start a New Chat to search again.",
                    "timestamp": utc_now(), "metadata": {"type": "booking_status"},
                })
                return session_data
            session_data["selectedDoctor"] = None
            session_data["selectedSlot"] = None
            session_data["bookingSummary"] = None
            session_data["state"] = BookingAgentState.COLLECTING_PREFERENCES.value
            assistant_msg = (
                "ඔබේ තේරීම අවලංගු කරන ලදී. ඔබට නැවත නව වෛද්‍යවරයකු සෙවිය හැකිය."
                if lang == "si"
                else "Your booking selection has been reset. You can search for another doctor or specialty whenever you're ready."
            )
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": assistant_msg,
                "timestamp": utc_now(),
                "metadata": {"type": "reset"},
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        candidate_doctors = session_data.get("candidateDoctors") or []
        candidate_slots = session_data.get("candidateSlots") or []
        selected_doctor = session_data.get("selectedDoctor")
        selected_slot = session_data.get("selectedSlot")

        def mentions(doctor):
            name = re.sub(r"^dr\.?\s+", "", doctor["fullName"], flags=re.IGNORECASE)
            return bool(name) and bool(re.search(rf"\b{re.escape(name)}\b", clean_text, re.IGNORECASE))

        follow_up = re.search(
            r"\b(details?|profile|slots?|availability|booking status|appointment status)\b|විස්තර|වේලාව",
            clean_text, re.IGNORECASE,
        )
        greeting = re.fullmatch(r"(?:hi|hello|hey|ayubowan|ආයුබෝවන්)[!. ]*", clean_text, re.IGNORECASE)
        ordinal = parsed_delta.get("ordinalDoctorIndex")
        named = [doctor for doctor in candidate_doctors if mentions(doctor)]
        pending_action = session_data.pop("pendingDoctorAction", None)
        if greeting or follow_up or (pending_action and (ordinal is not None or named)):
            session_data["preferences"] = {**previous_preferences, "language": lang}
            metadata = {"type": "clarification_needed"}
            if greeting:
                reply = "Hello! I can help you find doctors and book appointments. Which specialty or city should I search?"
            elif follow_up and "status" in follow_up.group().lower():
                status_messages = {
                    BookingAgentState.BOOKING_CONFIRMED.value: "Your appointment and payment are confirmed.",
                    BookingAgentState.AWAITING_PAYMENT.value: "Your slot is held. Payment is required to confirm the appointment.",
                    BookingAgentState.EXPIRED.value: "Your booking hold expired. Choose another slot to continue.",
                }
                reply = status_messages.get(current_state, "Open My Appointments to check your booking and payment status.")
            else:
                action = follow_up.group().lower() if follow_up else pending_action
                details = action in {"detail", "details", "profile", "විස්තර"}
                pool = candidate_doctors or ([selected_doctor] if selected_doctor else [])
                if named:
                    pool = named
                elif ordinal is not None and 0 <= ordinal < len(pool):
                    pool = [pool[ordinal]]
                elif selected_doctor:
                    pool = [selected_doctor]
                if len(pool) == 1:
                    doctor = pool[0]
                    if details:
                        try:
                            profile = await DoctorService.get_approved_doctor_detail(db, doctor["doctorId"])
                        except HTTPException as exc:
                            if exc.status_code != 404:
                                raise
                            reply = "That doctor?s profile is no longer available."
                        else:
                            current = profile.model_dump()
                            metadata = {"type": "doctor_details", "doctors": [{**doctor, **current}]}
                            reply = f"Here are the profile details for {profile.fullName}."
                    else:
                        metadata = {"type": "doctor_details", "doctors": pool}
                        reply = f"Choose View Available Slots for {doctor['fullName']} to check times by date."
                elif pool:
                    session_data["pendingDoctorAction"] = action
                    reply = "Which doctor do you mean? Please use the doctor's name or a card below."
                    metadata = {"type": "doctor_options", "doctors": pool}
                else:
                    reply = "Which doctor should I look up? Share a name, specialty, or city."
            session_data["messages"].append({
                "id": str(ObjectId()), "sender": "assistant", "content": reply,
                "timestamp": utc_now(), "metadata": metadata,
            })
            return session_data

        if intent == CompanionIntent.BOOK_APPOINTMENT and current_state in {
            BookingAgentState.AWAITING_PAYMENT.value,
            BookingAgentState.BOOKING_HOLD_CREATED.value,
            BookingAgentState.PAYMENT_PENDING_VERIFICATION.value,
        }:
            session_data["messages"].append({
                "id": str(ObjectId()), "sender": "assistant",
                "content": "Your current slot is held. Complete payment here, or start a New Chat for another booking.",
                "timestamp": utc_now(), "metadata": {"type": "booking_status"},
            })
            return session_data

        # 4. Handle "compare" / "compare doctors" request
        if candidate_doctors and re.search(r"\b(?:compare|comparison|සසඳන්න)\b", clean_text, re.IGNORECASE):
            assistant_msg = cls._build_comparison_message(candidate_doctors, lang)
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": assistant_msg,
                "timestamp": utc_now(),
                "metadata": {"type": "doctor_comparison", "count": len(candidate_doctors)},
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # 5. Handle "show me doctors with lower consultation fees" or "cheaper doctor"
        if parsed_delta.get("sortBy") == "fee_asc" or re.search(r"\b(?:cheaper|lower\s+fee|lower\s+fees|lowest\s+fee|අඩු\s+ගාස්තු)\b", clean_text, re.IGNORECASE):
            prefs["sortBy"] = "fee_asc"
            session_data["preferences"] = prefs
            session_data["selectedDoctor"] = None
            session_data["selectedSlot"] = None
            session_data["bookingSummary"] = None
            doctors = await cls._search_candidate_doctors(db, prefs)
            session_data["candidateDoctors"] = doctors
            session_data["state"] = BookingAgentState.AWAITING_DOCTOR_SELECTION.value
            assistant_msg = (
                "මෙන්න අඩුම උපදේශන ගාස්තු සහිත පිළිගත් වෛද්‍යවරුන්:\n"
                if lang == "si"
                else "Here are the verified doctors sorted by lowest consultation fee:\n"
            )
            assistant_msg += cls._build_doctor_options_message(doctors, prefs, lang)
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": assistant_msg,
                "timestamp": utc_now(),
                "metadata": {"type": "doctor_options", "count": len(doctors), "doctors": doctors, "sortedBy": "fee_asc"},
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # 6. If user changes search criteria while a doctor was already selected, reset selection
        if selected_doctor and (parsed_delta.get("specialty") or parsed_delta.get("city") or parsed_delta.get("maxFee") is not None):
            session_data["selectedDoctor"] = None
            session_data["selectedSlot"] = None
            session_data["bookingSummary"] = None
            selected_doctor = None
            selected_slot = None

        # 7. Check if user mentioned a doctor (by name or ordinal: 'second doctor', 'doctor 1', etc.)
        matched_doctor = None
        if not selected_doctor and candidate_doctors and not search_requested and intent == CompanionIntent.BOOK_APPOINTMENT:
            ordinal = parsed_delta.get("ordinalDoctorIndex")
            if ordinal is not None and 0 <= ordinal < len(candidate_doctors):
                matched_doctor = candidate_doctors[ordinal]
            else:
                text_lower = clean_text.lower()
                for doc in candidate_doctors:
                    doc_name = doc.get("fullName", "").lower()
                    doc_id = doc.get("doctorId", "").lower()
                    if (doc_name and doc_name in text_lower) or (doc_id and doc_id in text_lower):
                        matched_doctor = doc
                        break
                if not matched_doctor and len(candidate_doctors) == 1:
                    matched_doctor = candidate_doctors[0]
                elif not matched_doctor:
                    session_data["pendingDoctorAction"] = "book"
                    session_data["messages"].append({
                        "id": str(ObjectId()), "sender": "assistant",
                        "content": "Which doctor would you like to book? Reply with a name or choose a card.",
                        "timestamp": utc_now(),
                        "metadata": {"type": "doctor_options", "doctors": candidate_doctors},
                    })
                    return session_data

        if matched_doctor and matched_doctor.get("consultationFee") is not None:
            session_data["activeIntent"] = CompanionIntent.BOOK_APPOINTMENT.value
            session_data["selectedDoctor"] = matched_doctor
            selected_doctor = matched_doctor
            slots = await cls._fetch_available_slots(db, matched_doctor["doctorId"], prefs.get("date"))
            session_data["candidateSlots"] = slots
            target_state = BookingAgentState.AWAITING_SLOT_SELECTION.value
            if validate_state_transition(current_state, target_state):
                session_data["state"] = target_state

            assistant_msg = cls._build_slot_selection_message(matched_doctor, slots, lang)
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": assistant_msg,
                "timestamp": utc_now(),
                "metadata": {"type": "slot_selection", "doctorId": matched_doctor["doctorId"]},
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # 8. Check if user mentioned a time slot from candidate slots (by time or ordinal)
        matched_slot = None
        if selected_doctor and not selected_slot and candidate_slots:
            time_match = re.search(r"(\d{1,2}[:.]\d{2})", clean_text)
            if time_match:
                raw_time = time_match.group(1).replace(".", ":")
                if len(raw_time) == 4:
                    raw_time = "0" + raw_time
                for s in candidate_slots:
                    if s.get("startTime") == raw_time:
                        matched_slot = s
                        break
            else:
                # Check for ordinal slot selection e.g. "first slot", "second slot"
                slot_ord = parsed_delta.get("ordinalDoctorIndex")
                if slot_ord is not None and 0 <= slot_ord < len(candidate_slots):
                    matched_slot = candidate_slots[slot_ord]

        if matched_slot:
            session_data["activeIntent"] = CompanionIntent.BOOK_APPOINTMENT.value
            session_data["selectedSlot"] = matched_slot
            summary = cls._build_booking_summary(selected_doctor, matched_slot)
            session_data["bookingSummary"] = summary
            target_state = BookingAgentState.AWAITING_BOOKING_CONFIRMATION.value
            if validate_state_transition(current_state, target_state):
                session_data["state"] = target_state

            assistant_msg = cls._build_confirmation_prompt_message(summary, lang)
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": assistant_msg,
                "timestamp": utc_now(),
                "metadata": {"type": "booking_summary", "summary": summary},
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # 9. If doctor already selected and awaiting slot selection
        if selected_doctor and not selected_slot and intent == CompanionIntent.BOOK_APPOINTMENT:
            slots = await cls._fetch_available_slots(db, selected_doctor["doctorId"], prefs.get("date"))
            session_data["candidateSlots"] = slots
            target_state = BookingAgentState.AWAITING_SLOT_SELECTION.value
            if validate_state_transition(current_state, target_state):
                session_data["state"] = target_state

            assistant_msg = cls._build_slot_selection_message(selected_doctor, slots, lang)
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": assistant_msg,
                "timestamp": utc_now(),
                "metadata": {"type": "slot_selection", "doctorId": selected_doctor["doctorId"]},
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        # 10. Doctor Discovery Search (specialty, symptoms, or location specified)
        if search_requested:
            session_data["activeIntent"] = intent.value if intent == CompanionIntent.BOOK_APPOINTMENT else CompanionIntent.FIND_DOCTOR.value
            target_state = BookingAgentState.SEARCHING_DOCTORS.value
            if validate_state_transition(current_state, target_state):
                session_data["state"] = target_state

            slots_by_doctor = {}
            grounded_reply = None
            result = None
            if patient_user:
                filters = {
                    key: prefs[source] for key, source in (
                        ("specialty", "specialty"), ("city", "city"), ("name", "doctorName"),
                        ("hospital", "hospital"), ("max_fee", "maxFee"),
                    ) if prefs.get(source) is not None
                }
                result = await AIOrchestrator(db, patient_user, provider).run_search(
                    clean_text, session_data, filters, prefs.get("date"), prefs.get("requestedTime"),
                )
            if result is None:
                doctors = await cls._search_candidate_doctors(db, prefs)
            else:
                doctors, slots_by_doctor, grounded_reply = result
            if prefs.get("date"):
                for doctor in doctors:
                    doctor_id = doctor["doctorId"]
                    if doctor_id not in slots_by_doctor:
                        slots_by_doctor[doctor_id] = {
                            "slots": await cls._fetch_available_slots(
                                db, doctor_id, prefs["date"], preferred_time=prefs.get("requestedTime"),
                            ),
                        }
                    doctor["availableSlots"] = slots_by_doctor[doctor_id]["slots"]
                    doctor["requestedTime"] = prefs.get("requestedTime")
                    doctor["requestedDate"] = prefs["date"]
            session_data["candidateDoctors"] = doctors

            if doctors:
                next_state = BookingAgentState.AWAITING_DOCTOR_SELECTION.value
                if validate_state_transition(session_data["state"], next_state):
                    session_data["state"] = next_state
                assistant_msg = grounded_reply if grounded_reply and lang == 'en' else cls._build_doctor_options_message(doctors, prefs, lang)
                session_data["messages"].append({
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": assistant_msg,
                    "timestamp": utc_now(),
                    "metadata": {"type": "doctor_options", "count": len(doctors), "doctors": doctors},
                })
            else:
                next_state = BookingAgentState.COLLECTING_PREFERENCES.value
                if validate_state_transition(session_data["state"], next_state):
                    session_data["state"] = next_state
                assistant_msg = cls._build_no_doctors_message(prefs, lang)
                session_data["messages"].append({
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": assistant_msg,
                    "timestamp": utc_now(),
                    "metadata": {"type": "no_results"},
                })
        else:
            # Need more details from user
            if not parsed_delta.get("date"):
                session_data["preferences"] = {**previous_preferences, "language": lang}
            target_state = BookingAgentState.COLLECTING_PREFERENCES.value
            if validate_state_transition(current_state, target_state):
                session_data["state"] = target_state

            assistant_msg = (
                "ඔබට අවශ්‍ය වෛද්‍ය විශේෂඥතාවය (උදා: චර්ම රෝග, හෘද රෝග), රෝග ලක්ෂණ හෝ නගරය සඳහන් කරන්න."
                if lang == "si"
                else "Could you please share your symptoms, preferred doctor specialty (e.g., Cardiologist), or city?"
            )
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": assistant_msg,
                "timestamp": utc_now(),
                "metadata": {"type": "clarification_needed"},
            })

        session_data["updatedAt"] = utc_now()
        return session_data

    # -------------------------------------------------------------------------
    # DATABASE SEARCH HELPERS
    # -------------------------------------------------------------------------
    @classmethod
    async def _patient_status_turn(cls, db, user, provider, session, text):
        appointment_query = bool(re.search(r"\b(?:heta mata appointment|my appointments)\b", text, re.I))
        care_query = "my care tasks" in text.casefold()
        if care_query:
            tool = "get_patient_care_tasks"
        elif appointment_query:
            tool = "get_patient_appointments"
        else:
            tool = "get_booking_session_status"
        args = {"session_id": str(session.get("_id", ""))}
        if appointment_query:
            date = parse_query_deterministically(text).get("date")
            args = {"from_date": date, "to_date": date}
        if care_query:
            args = {}
        result = await AIOrchestrator(db, user, provider).execute(tool, args, {tool})
        session["activeIntent"] = tool.upper()
        if result.get("error"):
            reply = "I couldn?t read your booking status. Open My Appointments to check."
        elif care_query:
            count = len(result["tasks"])
            reply = f"I found {count} tasks in your active care plans. Open your care plan for details."
        elif appointment_query:
            count = len(result["appointments"])
            reply = f"I found {count} appointment records for that search. Open My Appointments for details."
        else:
            state = result["booking_state"].replace("_", " ").lower()
            reply = f"Your booking session status is {state}."
        session["messages"].extend([
            {"id": str(ObjectId()), "sender": "user", "content": text, "timestamp": utc_now()},
            {"id": str(ObjectId()), "sender": "assistant", "content": reply, "timestamp": utc_now(),
             "metadata": {"type": "booking_status", "error_code": result.get("error")}},
        ])
        return session

    @classmethod
    async def _search_candidate_doctors(
        cls,
        db: Database,
        prefs: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Find approved and active doctors matching accumulated preferences with multi-factor scoring."""
        profile_query: Dict[str, Any] = {
            "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        }

        specialty = prefs.get("specialty")
        if specialty and specialty.strip():
            clean_spec = specialty.strip()
            stem = clean_spec[:-4] if clean_spec.lower().endswith("gist") else clean_spec
            stem = stem[:-2] if stem.lower().endswith("gy") else stem
            profile_query["specialty"] = {"$regex": re.escape(stem), "$options": "i"}

        city = prefs.get("city")
        if city:
            location = {"$regex": re.escape(city.strip()), "$options": "i"}
            profile_query["$or"] = [{"city": location}, {"hospitalOrClinic": location}]
        if prefs.get("hospital"):
            profile_query["hospitalOrClinic"] = {
                "$regex": re.escape(prefs["hospital"]), "$options": "i",
            }

        profiles = list(db["doctor_profiles"].find(profile_query).limit(200))
        if not profiles:
            return []

        user_ids = []
        for p in profiles:
            uid = p.get("userId")
            if uid:
                user_ids.append(uid)
                if ObjectId.is_valid(uid):
                    user_ids.append(ObjectId(uid))

        users_cursor = db["users"].find({
            "_id": {"$in": user_ids},
            "role": UserRole.DOCTOR.value,
            "accountStatus": AccountStatus.ACTIVE.value,
        })
        active_users = {str(u["_id"]): u for u in users_cursor}

        verified_candidates = []
        for p in profiles:
            uid_str = str(p.get("userId", ""))
            user = active_users.get(uid_str)
            if user:
                verified_candidates.append((p, user))

        if not verified_candidates:
            return []

        max_fee = prefs.get("maxFee")
        target_date = prefs.get("date")

        scored_candidates: List[Dict[str, Any]] = []

        for p, user in verified_candidates:
            uid_str = str(user["_id"])
            prof_id = str(p["_id"])
            doc_id = str(p.get("doctorId", ""))
            doc_name = user.get("fullName") or "Name unavailable"
            if prefs.get("doctorName") and prefs["doctorName"].casefold() not in doc_name.casefold():
                continue
            doc_spec = p.get("specialty") or "Specialty not listed"
            doc_hospital = p.get("hospitalOrClinic") or ""
            doc_fee = p.get("consultationFee")
            doc_exp = p.get("experienceYears") or 0
            doc_rating = p.get("rating") or 0
            doc_quals = p.get("qualifications")

            if max_fee is not None and (doc_fee is None or doc_fee > float(max_fee)):
                continue

            # Multi-factor score (0-100) & match reasons
            score = 0.0
            reasons: List[str] = []

            # 1. Specialty match (up to 40 pts)
            if specialty:
                if specialty.lower() in doc_spec.lower() or doc_spec.lower() in specialty.lower():
                    score += 40.0
                    reasons.append(f"Direct match for requested specialty: {doc_spec}")
                else:
                    score += 20.0
                    reasons.append(f"Provides care as {doc_spec}")
            else:
                score += 20.0
                reasons.append("Verified doctor")

            # 2. Location match (up to 25 pts)
            if city:
                if city.lower() in (p.get("city") or doc_hospital).lower():
                    score += 25.0
                    reasons.append(f"Located in {city} ({doc_hospital})")
                else:
                    score += 5.0
            else:
                score += 15.0

            # 3. Budget match (up to 20 pts)
            if max_fee is not None:
                if doc_fee <= float(max_fee):
                    score += 20.0
                    reasons.append(f"Consultation fee LKR {doc_fee:,.0f} is within your budget of LKR {float(max_fee):,.0f}")
            else:
                score += 15.0

            # 5. Rating bonus (up to 5 pts)
            score += min(5.0, doc_rating)

            scored_candidates.append({
                "doctorId": doc_id,
                "doctorProfileId": prof_id,
                "doctorUserId": uid_str,
                "fullName": doc_name,
                "specialty": doc_spec,
                "qualifications": doc_quals,
                "profileImage": user.get("profileImage"),
                "city": p.get("city"),
                "hospitalOrClinic": doc_hospital,
                "experienceYears": doc_exp,
                "consultationFee": doc_fee,
                "rating": doc_rating,
                "matchScore": round(min(100.0, score), 1),
                "matchReason": reasons[0] if reasons else "Verified doctor",
                "matchReasons": reasons,
            })

        # Sorting: if fee_asc requested, sort by consultationFee ascending
        if prefs.get("sortBy") == "fee_asc":
            scored_candidates.sort(key=lambda x: (x["consultationFee"] if x["consultationFee"] is not None else float("inf"), -x["matchScore"]))
        elif prefs.get("sortBy") == "rating_desc":
            scored_candidates.sort(key=lambda x: (-x["rating"], -x["matchScore"]))
        else:
            scored_candidates.sort(key=lambda x: (-x["matchScore"], x["consultationFee"] if x["consultationFee"] is not None else float("inf")))

        results = scored_candidates[:5]
        for doctor in results:
            slots = await cls._fetch_available_slots(db, doctor["doctorId"], target_date)
            doctor["availableSlots"] = slots[:4]
            doctor["nextAvailableDate"] = slots[0]["date"] if slots else None
        return results

    @classmethod
    async def _fetch_available_slots(
        cls,
        db: Database,
        doctor_id: str,
        preferred_date: Optional[str] = None,
        *,
        preferred_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve real discrete unbooked slots for doctor."""
        try:
            raw_slots = await DoctorService.get_doctor_patient_slots(
                db=db,
                doctor_id=doctor_id,
                date_filter=preferred_date,
            )
        except HTTPException as exc:
            logger.warning("Doctor slot lookup failed with status %s", exc.status_code)
            return []

        slots: List[Dict[str, Any]] = []
        if isinstance(raw_slots, list):
            for day in raw_slots:
                day_date = getattr(day, "date", "")
                day_slots = getattr(day, "slots", [])
                for s in day_slots:
                    slots.append({
                        "availabilityId": getattr(s, "availabilityId", "") or "",
                        "date": day_date,
                        "startTime": getattr(s, "startTime", ""),
                        "endTime": getattr(s, "endTime", ""),
                    })
        elif hasattr(raw_slots, "slots"):
            day_date = getattr(raw_slots, "date", preferred_date or get_sl_today_str())
            for s in getattr(raw_slots, "slots", []):
                slots.append({
                    "availabilityId": getattr(s, "availabilityId", "") or "",
                    "date": day_date,
                    "startTime": getattr(s, "startTime", ""),
                    "endTime": getattr(s, "endTime", ""),
                })

        if preferred_date and preferred_time:
            hour, minute = map(int, preferred_time.split(":"))
            target = hour * 60 + minute
            slots.sort(key=lambda slot: abs(
                int(slot["startTime"][:2]) * 60 + int(slot["startTime"][3:]) - target
            ))
        return slots[:12]

    # -------------------------------------------------------------------------
    # SUMMARY BUILDER
    # -------------------------------------------------------------------------
    @classmethod
    def _build_booking_summary(
        cls,
        doctor: Dict[str, Any],
        slot: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construct authoritative booking summary before patient confirms."""
        fee = float(doctor.get("consultationFee", 2500.0))
        service_fee = 0.0
        return {
            "doctorName": doctor.get("fullName", "Doctor"),
            "specialty": doctor.get("specialty", ""),
            "hospitalOrClinic": doctor.get("hospitalOrClinic"),
            "appointmentDate": slot.get("date", ""),
            "startTime": slot.get("startTime", ""),
            "endTime": slot.get("endTime", ""),
            "consultationFee": fee,
            "serviceFee": service_fee,
            "totalAmount": fee + service_fee,
            "currency": "lkr",
        }

    # -------------------------------------------------------------------------
    # MESSAGE GENERATORS (Bilingual English & Sinhala)
    # -------------------------------------------------------------------------
    @classmethod
    def _build_doctor_options_message(
        cls,
        doctors: List[Dict[str, Any]],
        prefs: Dict[str, Any],
        lang: str,
    ) -> str:
        if not doctors:
            return cls._build_no_doctors_message(prefs, lang)
        count = len(doctors)
        city = prefs.get("city")
        location = f" in {city}" if city else ""
        noun = "doctor" if count == 1 else "doctors"
        if lang == "si":
            return (
                f"ඔබේ සෙවුමට ගැළපෙන වෛද්‍යවරුන් {count} දෙනෙක් හමු වුණා. "
                "විස්තර හෝ වෙන් කළ හැකි වේලාවන් බැලීමට වෛද්‍යවරයෙකු තෝරන්න."
            )
        return (
            f"I found {count} verified {noun}{location} matching your search. "
            "Select a doctor to view their profile or check appointment slots."
        )

    @staticmethod
    def _format_fee(doctor: Dict[str, Any]) -> str:
        fee = doctor.get("consultationFee")
        return f"LKR {fee:,.0f}" if fee is not None else "Fee unavailable"

    @classmethod
    def _build_comparison_message(
        cls,
        doctors: List[Dict[str, Any]],
        lang: str,
    ) -> str:
        lines = ["Here is a side-by-side comparison of the doctors:"]
        for number, doctor in enumerate(doctors[:3], 1):
            lines.append(f"\n{number}. {doctor['fullName']}")
            for key in ("specialty", "qualifications", "hospitalOrClinic"):
                if doctor.get(key):
                    lines.append(f"   - {doctor[key]}")
            lines.append(f"   - {cls._format_fee(doctor)}")
        lines.append("\nChoose a doctor to check available times by date.")
        return "\n".join(lines)

    @classmethod
    def _build_no_doctors_message(cls, prefs: Dict[str, Any], lang: str) -> str:
        spec = prefs.get("specialty")
        city = prefs.get("city")
        fee = prefs.get("maxFee")
        criteria = []
        if prefs.get("doctorName"):
            criteria.append(prefs["doctorName"])
        if spec:
            criteria.append(spec)
        if city:
            criteria.append(f"in {city}")
        if prefs.get("hospital"):
            criteria.append(f"at {prefs['hospital']}")
        if fee:
            criteria.append(f"under LKR {fee:,.0f}")
        c_text = " ".join(criteria) or "your search"

        if lang == "si":
            return (
                f"සමාවන්න, {c_text} සඳහා ගැළපෙන පිළිගත් වෛද්‍යවරුන් හමු නොවීය. "
                "වෙනත් දිනයක්, නගරයක් (උදා: කොළඹ) හෝ වෙනත් ගාස්තු සීමාවක් උත්සාහ කිරීමට කැමතිද?"
            )
        return (
            f"I couldn't find any approved doctors matching {c_text}. "
            "Would you like to search a nearby city (e.g. Colombo), choose a different date, or adjust your fee filter?"
        )

    @classmethod
    def _build_slot_selection_message(
        cls,
        doctor: Dict[str, Any],
        slots: List[Dict[str, Any]],
        lang: str,
    ) -> str:
        name = doctor.get("fullName", "Doctor")
        if not slots:
            if lang == "si":
                return f"{name} වෛද්‍යතුමා සඳහා දැනට ලබාගත හැකි වේලාවන් නොමැත. කරුණාකර වෙනත් දිනයක් හෝ වෙනත් වෛද්‍යවරයකු තෝරන්න."
            return f"There are currently no remaining slots available for {name}. Would you like to check a different date or another doctor?"

        slot_count = len(slots)
        date_sample = slots[0].get("date", "")
        if lang == "si":
            return f"{name} වෛද්‍යතුමාගේ {date_sample} දින වේලාවන් ({slot_count}) පහතින් තෝරන්න:"

        return f"Please select an available appointment slot for {name} on {date_sample}:" 

    @classmethod
    def _build_confirmation_prompt_message(
        cls,
        summary: Dict[str, Any],
        lang: str,
    ) -> str:
        name = summary.get("doctorName", "")
        date = summary.get("appointmentDate", "")
        time = f"{summary.get('startTime')} - {summary.get('endTime')}"
        fee = summary.get("totalAmount", 0.0)

        if lang == "si":
            return f"නියමයි! {name} සමඟ {date} ({time}) වේලාව තහවුරු කිරීමට පහත 'Confirm Booking' ඔබන්න."

        return f"Great! Please tap 'Confirm Booking' below to reserve your slot with {name} on {date} ({time})." 
