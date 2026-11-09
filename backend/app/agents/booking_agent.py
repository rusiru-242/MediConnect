"""Conversational AI Booking Agent with bilingual multi-turn dialog, state machine, and safety checks."""

from collections import defaultdict
from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
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
)
from app.models.booking_session import (
    ALLOWED_STATE_TRANSITIONS,
    BookingAgentState,
    BookingSessionDocument,
    ChatMessageDocument,
    utc_now,
)
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.specialty import SUPPORTED_SPECIALTIES
from app.models.user import AccountStatus, UserRole
from app.services.doctor_service import (
    DoctorService,
    get_sl_now,
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
    ) -> Dict[str, Any]:
        """Process a user conversational turn, update preferences, and transition state."""
        clean_text = user_message.strip()
        current_state = session_data.get("state", BookingAgentState.COLLECTING_PREFERENCES.value)
        prefs = dict(session_data.get("preferences") or {})

        # 1. Emergency symptom check
        is_urgent, urgency_reason = check_urgency(clean_text)
        if is_urgent:
            session_data["isUrgent"] = True
            session_data["urgencyReason"] = urgency_reason
            lang = prefs.get("language", "en")
            emergency_text = EMERGENCY_SI_ALERT if lang == "si" else EMERGENCY_EN_ALERT

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

        # 2. Extract structured preferences from query using AI / deterministic NLP
        ai_provider = get_ai_provider()
        parsed_delta, _ = ai_provider.parse_request(
            query=clean_text,
            explicit_filters={
                "specialty": prefs.get("specialty"),
                "city": prefs.get("city"),
                "date": prefs.get("date"),
                "timeRange": prefs.get("timeRange"),
                "maxFee": prefs.get("maxFee"),
            },
        )

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
        intent = CompanionIntentClassifier.classify_intent(
            query=clean_text,
            current_state=current_state,
            has_image=bool(image_bytes or image_url),
            candidate_count=len(session_data.get("candidateDoctors") or []),
        )
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
            session_data["candidateDoctors"] = []
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
            session_data["candidateDoctors"] = []
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
            session_data["candidateDoctors"] = []
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
            session_data["candidateDoctors"] = []
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
                "metadata": {"type": "doctor_options", "count": len(doctors), "sortedBy": "fee_asc"},
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
        if not selected_doctor and candidate_doctors:
            ordinal = parsed_delta.get("ordinalDoctorIndex")
            if ordinal is not None and 0 <= ordinal < len(candidate_doctors):
                matched_doctor = candidate_doctors[ordinal]
            else:
                text_lower = clean_text.lower()
                for doc in candidate_doctors:
                    doc_name = doc.get("fullName", "").lower()
                    doc_id = doc.get("doctorId", "").lower()
                    name_parts = [p for p in doc_name.replace("dr.", "").strip().split() if len(p) > 2]
                    if doc_name in text_lower or doc_id in text_lower or any(p in text_lower for p in name_parts):
                        matched_doctor = doc
                        break

        if matched_doctor:
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
        if selected_doctor and not selected_slot:
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
        if prefs.get("specialty") or prefs.get("city") or prefs.get("symptoms"):
            target_state = BookingAgentState.SEARCHING_DOCTORS.value
            if validate_state_transition(current_state, target_state):
                session_data["state"] = target_state

            doctors = await cls._search_candidate_doctors(db, prefs)
            session_data["candidateDoctors"] = doctors

            if doctors:
                next_state = BookingAgentState.AWAITING_DOCTOR_SELECTION.value
                if validate_state_transition(session_data["state"], next_state):
                    session_data["state"] = next_state
                assistant_msg = cls._build_doctor_options_message(doctors, prefs, lang)
                session_data["messages"].append({
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": assistant_msg,
                    "timestamp": utc_now(),
                    "metadata": {"type": "doctor_options", "count": len(doctors)},
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
        if city and city.strip():
            profile_query["hospitalOrClinic"] = {"$regex": re.escape(city.strip()), "$options": "i"}

        profiles = list(db["doctor_profiles"].find(profile_query).limit(20))
        if not profiles and city:
            # If city produced 0 results, retry without city to suggest available specialists
            profile_query.pop("hospitalOrClinic", None)
            profiles = list(db["doctor_profiles"].find(profile_query).limit(20))

        if not profiles:
            return []

        user_ids = []
        for p in profiles:
            uid = p.get("userId")
            if uid:
                user_ids.append(ObjectId(uid) if ObjectId.is_valid(uid) else uid)

        users_cursor = db["users"].find({
            "_id": {"$in": user_ids},
            "role": UserRole.DOCTOR.value,
            "accountStatus": AccountStatus.ACTIVE.value,
        })
        active_users = {str(u["_id"]): u for u in users_cursor}

        verified_candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for p in profiles:
            uid_str = str(p.get("userId", ""))
            user = active_users.get(uid_str)
            if user:
                verified_candidates.append((p, user))

        if not verified_candidates:
            return []

        # Batch retrieve available slots
        sl_today = get_sl_today_str()
        cand_prof_ids = [str(p["_id"]) for p, _ in verified_candidates]
        cand_user_ids = [str(u["_id"]) for _, u in verified_candidates]

        avails_cursor = db["doctor_availabilities"].find({
            "doctorProfileId": {"$in": cand_prof_ids},
            "isActive": True,
            "date": {"$gte": sl_today},
        }).sort([("date", 1), ("startTime", 1)])
        avails_by_prof: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for av in avails_cursor:
            avails_by_prof[str(av.get("doctorProfileId", ""))].append(av)

        now_utc = datetime.now(timezone.utc)
        appts_cursor = db["appointments"].find(
            {
                "doctorUserId": {"$in": cand_user_ids},
                "status": {"$in": ["HOLD", "PENDING", "CONFIRMED", "COMPLETED"]},
                "appointmentDate": {"$gte": sl_today},
            },
            {"doctorUserId": 1, "appointmentDate": 1, "startTime": 1, "status": 1, "holdExpiresAt": 1, "paymentStatus": 1},
        )
        booked_by_doc: Dict[str, set] = defaultdict(set)
        for a in appts_cursor:
            st = a.get("status")
            hold = a.get("holdExpiresAt")
            paid = a.get("paymentStatus") == "PAID"
            if st in ["HOLD", "PENDING"] and not paid and hold:
                if hold.tzinfo is None:
                    hold = hold.replace(tzinfo=timezone.utc)
                if hold <= now_utc:
                    continue
            d_uid = str(a.get("doctorUserId", ""))
            booked_by_doc[d_uid].add((a.get("appointmentDate"), a.get("startTime")))

        max_fee = prefs.get("maxFee")
        target_date = prefs.get("date")

        scored_candidates: List[Dict[str, Any]] = []

        for p, user in verified_candidates:
            uid_str = str(user["_id"])
            prof_id = str(p["_id"])
            doc_id = str(p.get("doctorId", ""))
            doc_name = user.get("fullName", "Doctor")
            doc_spec = p.get("specialty", "General Medicine")
            doc_hospital = p.get("hospitalOrClinic", "MediConnect Clinic")
            doc_fee = float(p.get("consultationFee", 2500.0))
            doc_exp = int(p.get("experienceYears", 0))
            doc_rating = float(p.get("rating", 4.8))
            doc_quals = p.get("qualifications", "MBBS")

            # Hard budget filter if maxFee specified
            if max_fee is not None and doc_fee > float(max_fee):
                continue

            # Calculate available unbooked slots
            avails = avails_by_prof.get(prof_id, [])
            booked_set = booked_by_doc.get(uid_str, set())
            unbooked_slots: List[Dict[str, Any]] = []

            for av in avails:
                d_str = av["date"]
                s_t = av["startTime"]
                e_t = av["endTime"]
                dur = int(av.get("slotDurationMinutes", 30))
                av_id = str(av["_id"])

                gen_slots = DoctorService._generate_slots_for_window(
                    date_str=d_str,
                    start_time_str=s_t,
                    end_time_str=e_t,
                    slot_duration_mins=dur,
                    availability_id=av_id,
                )
                for gs in gen_slots:
                    if (d_str, gs.startTime) not in booked_set:
                        unbooked_slots.append({
                            "availabilityId": av_id,
                            "date": d_str,
                            "startTime": gs.startTime,
                            "endTime": gs.endTime,
                        })

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
                reasons.append(f"Approved specialist in {doc_spec}")

            # 2. Location match (up to 25 pts)
            if city:
                if city.lower() in doc_hospital.lower():
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

            # 4. Availability match (up to 10 pts)
            next_date = unbooked_slots[0]["date"] if unbooked_slots else None
            if target_date:
                has_date = any(s["date"] == target_date for s in unbooked_slots)
                if has_date:
                    score += 10.0
                    reasons.append(f"Has appointment slot available on {target_date}")
                elif unbooked_slots:
                    score += 5.0
            elif unbooked_slots:
                score += 10.0
                reasons.append(f"Next available slot on {next_date}")

            # 5. Rating bonus (up to 5 pts)
            score += min(5.0, doc_rating)

            scored_candidates.append({
                "doctorId": doc_id,
                "doctorProfileId": prof_id,
                "doctorUserId": uid_str,
                "fullName": doc_name,
                "specialty": doc_spec,
                "qualifications": doc_quals,
                "hospitalOrClinic": doc_hospital,
                "experienceYears": doc_exp,
                "consultationFee": doc_fee,
                "rating": doc_rating,
                "matchScore": round(min(100.0, score), 1),
                "matchReason": reasons[0] if reasons else f"Approved specialist in {doc_spec}",
                "matchReasons": reasons,
                "nextAvailableDate": next_date,
                "availableSlots": unbooked_slots[:4],
            })

        # Sorting: if fee_asc requested, sort by consultationFee ascending
        if prefs.get("sortBy") == "fee_asc":
            scored_candidates.sort(key=lambda x: (x["consultationFee"], -x["matchScore"]))
        elif prefs.get("sortBy") == "rating_desc":
            scored_candidates.sort(key=lambda x: (-x["rating"], -x["matchScore"]))
        else:
            scored_candidates.sort(key=lambda x: (-x["matchScore"], x["consultationFee"]))

        return scored_candidates[:5]

    @classmethod
    async def _fetch_available_slots(
        cls,
        db: Database,
        doctor_id: str,
        preferred_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve real discrete unbooked slots for doctor."""
        try:
            raw_slots = await DoctorService.get_doctor_patient_slots(
                db=db,
                doctor_id=doctor_id,
                date_filter=preferred_date,
            )
        except Exception as e:
            logger.warning(f"Error fetching doctor slots for {doctor_id}: {e}")
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
        count = len(doctors)
        spec = prefs.get("specialty", "specialist")
        city = prefs.get("city")
        loc_str = f" in {city}" if city else ""

        if lang == "si":
            return (
                f"ඔබට ගැළපෙන පිළිගත් {spec} වෛද්‍යවරුන් {count} දෙනෙකු සොයා ගන්නා ලදී.\n"
                "වේලාවන් බැලීමට පහත කාඩ්පතකින් වෛද්‍යවරයකු තෝරන්න."
            )

        return (
            f"I found {count} approved {spec}{loc_str} matching your preferences.\n"
            "Please select a doctor below to view available appointment slots."
        )

    @classmethod
    def _build_comparison_message(
        cls,
        doctors: List[Dict[str, Any]],
        lang: str,
    ) -> str:
        if lang == "si":
            lines = ["වෛද්‍යවරුන්ගේ සංසන්දනය:"]
            for i, d in enumerate(doctors[:3], 1):
                lines.append(
                    f"\n{i}. {d['fullName']}\n"
                    f"   • විශේෂත්වය: {d['specialty']}\n"
                    f"   • සුදුසුකම්: {d.get('qualifications', 'MBBS')}\n"
                    f"   • රෝහල: {d.get('hospitalOrClinic', 'MediConnect')}\n"
                    f"   • උපදේශන ගාස්තුව: LKR {d['consultationFee']:,.0f}\n"
                    f"   • පළපුරුද්ද: වසර {d.get('experienceYears', 0)}\n"
                    f"   • ශ්‍රේණිගත කිරීම: ⭐ {d.get('rating', 4.8):.1f}\n"
                    f"   • ඊළඟ වේලාව: {d.get('nextAvailableDate') or 'ලබාගත හැක'}"
                )
            lines.append("\nකරුණාකර ඔබ කැමති වෛද්‍යවරයකු තෝරන්න.")
            return "\n".join(lines)

        lines = ["Here is a side-by-side comparison of the top recommended doctors:"]
        for i, d in enumerate(doctors[:3], 1):
            score_val = d.get('matchScore', 90)
            lines.append(
                f"\n{i}. {d['fullName']}\n"
                f"   • Specialty: {d['specialty']}\n"
                f"   • Qualifications: {d.get('qualifications', 'MBBS')}\n"
                f"   • Hospital/Clinic: {d.get('hospitalOrClinic', 'MediConnect Clinic')}\n"
                f"   • Fee: LKR {d['consultationFee']:,.0f}\n"
                f"   • Experience: {d.get('experienceYears', 0)} years\n"
                f"   • Rating: ⭐ {d.get('rating', 4.8):.1f} ({score_val:.0f}% Match)\n"
                f"   • Next Available: {d.get('nextAvailableDate') or 'Slots available'}"
            )
        lines.append("\nTo proceed, select a doctor or reply with their number (e.g., 'Book the 2nd doctor').")
        return "\n".join(lines)

    @classmethod
    def _build_no_doctors_message(cls, prefs: Dict[str, Any], lang: str) -> str:
        spec = prefs.get("specialty", "doctor")
        city = prefs.get("city")
        fee = prefs.get("maxFee")
        criteria = []
        if spec:
            criteria.append(spec)
        if city:
            criteria.append(f"in {city}")
        if fee:
            criteria.append(f"under LKR {fee:,.0f}")
        c_text = " ".join(criteria)

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
