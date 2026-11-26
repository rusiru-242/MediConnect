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
from app.agents.doctor_ranking import (
    coerce_fee,
    constraint_reasons,
    dedupe_doctors,
    published_ratings,
    rank_doctors,
    selection_explanation,
)
from app.agents import clinical_intent
from app.agents.emergency_detector import (
    AMBULANCE_NUMBER,
    crisis_metadata,
    detect_emergency,
    emergency_message,
    informational_message,
    last_assistant_was_emergency,
    recent_user_texts,
)
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

# "Recommend a good doctor" shows the most suitable one or two by default (Phase 01 requirement).
RECOMMENDATION_LIMIT = 2

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



def medication_change_message(lang: str) -> str:
    """B16 (Phase 05): the assistant never changes a prescribed dose or schedule."""
    if lang == "si":
        return ("**ඔබේ බෙහෙත් මාත්‍රාව හෝ වේලාවන් මට වෙනස් කළ නොහැක.** බෙහෙත් වෙනස් කිරීම ඒවා නියම කළ වෛද්‍යවරයා "
                "විසින් පමණක් තීරණය කළ යුතුය. ඔබේ කාලසටහනේ කිසිවක් වෙනස් කර නැත.\n\n"
                "- ඔබේ වෛද්‍යවරයා සමඟ කතා කරන්න, නැතහොත් වෛද්‍ය හමුවක් වෙන් කරන්න.\n"
                "- නියම කළ ප්‍රමාණයට වඩා දැනටමත් ගෙන ඇත්නම් හෝ අසනීප බවක් දැනේ නම්, වහාම 1990 අමතන්න හෝ ළඟම ETU එකට යන්න.")
    return ("**I can't change your dose or medicine times.** Changes to a prescribed medicine must be decided by the "
            "doctor who prescribed it, so nothing in your schedule has been changed.\n\n"
            "- Talk to your doctor, or book an appointment to review your medicine.\n"
            "- Keep taking it exactly as prescribed until your doctor tells you otherwise.\n"
            "- If you have already taken more than prescribed or feel unwell, call 1990 or go to the nearest ETU now.")


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

        session_data.setdefault("messages", [])
        detected_language = detect_language(clean_text)
        turn_lang = detected_language if detected_language in ("si", "ta") else (
            "en" if re.search(r"[a-z]{3,}", clean_text, re.I) and detected_language == "en" else prefs.get("language", "en")
        )

        # 1. Emergency triage runs BEFORE any routing, search, booking, medicine or wellness logic (BUG-013).
        #    Deterministic, multilingual, and aware of recent conversation context.
        emergency = detect_emergency(
            clean_text,
            recent_user_texts(session_data),
            last_assistant_was_emergency(session_data),
        )
        legacy_urgent, legacy_reason = check_urgency(clean_text)
        triage, triage_reason, _ = SymptomTriageEngine.classify_triage_pre_check(clean_text, "en")
        if not emergency.is_emergency and emergency.suppressed is None and (
            legacy_urgent or triage == TriageLevel.EMERGENCY
        ):
            # Keep the previous English/Tamil keyword nets as an additional safety layer.
            emergency.is_emergency, emergency.reason = True, legacy_reason or triage_reason
        if emergency.is_emergency:
            session_data["isUrgent"] = True
            session_data["urgencyReason"] = emergency.reason
            if turn_lang == "ta":
                emergency_text = EMERGENCY_TA_ALERT
            else:
                emergency_text = emergency_message(emergency, "si" if turn_lang == "si" else "en")
            session_data["activeIntent"] = CompanionIntent.EMERGENCY_GUIDANCE.value
            session_data["candidateSlots"] = []
            for key in ("activeMedicineCard", "activeWellnessCard", "activeImageAnalysis"):
                session_data[key] = None
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
                    "type": "emergency",
                    "isUrgent": True,
                    "ambulanceCall": AMBULANCE_NUMBER,
                    "reason": emergency.reason,
                    "category": emergency.category,
                    "fromContext": emergency.from_context,
                    **crisis_metadata(emergency),
                },
            })
            session_data["updatedAt"] = utc_now()
            return session_data

        def reply(content: str, metadata: Dict[str, Any], *, intent_value: str,
                  preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            session_data["messages"].append({
                "id": str(ObjectId()), "sender": "user", "content": clean_text, "timestamp": utc_now(),
                "metadata": {"imageUrl": image_url} if image_url else None,
            })
            session_data["messages"].append({
                "id": str(ObjectId()), "sender": "assistant", "content": content, "timestamp": utc_now(),
                "metadata": metadata,
            })
            session_data["activeIntent"] = intent_value
            session_data["candidateSlots"] = []
            for key in ("activeMedicineCard", "activeWellnessCard", "activeImageAnalysis"):
                session_data[key] = None
            if preferences is not None:
                session_data["preferences"] = {**preferences, "language": turn_lang if turn_lang in ("si", "en")
                                               else preferences.get("language", "en")}
            elif turn_lang in ("si", "en"):
                session_data["preferences"] = {**previous_preferences, "language": turn_lang}
            session_data["updatedAt"] = utc_now()
            return session_data

        has_real_image = bool(image_bytes) or bool(image_url)
        reply_lang = "si" if turn_lang == "si" else "en"

        # 1b. Educational or hypothetical questions about an emergency condition ("What are the common symptoms of a
        #     heart attack?") get information plus conditional "if this is happening now, call 1990" guidance,
        #     not an emergency alarm (Phase 01 false positives). Emergencies are never routed to booking here.
        if not has_real_image and emergency.suppressed in {"informational", "hypothetical"} and emergency.category:
            return reply(
                informational_message(emergency, reply_lang),
                {"type": "emergency_information", "category": emergency.category, "conditionalEmergency": True,
                 "ambulanceCall": AMBULANCE_NUMBER, "questionType": emergency.suppressed},
                intent_value="HEALTH_INFORMATION",
            )

        # 1c. General prevention / cause questions ("How can I prevent heart disease?") are health information,
        #     not a doctor search.
        if not has_real_image:
            info = clinical_intent.general_health_information(clean_text, reply_lang)
            if info is not None:
                return reply(info["text"], {"type": "health_information", "topic": info["topic"]},
                             intent_value="HEALTH_INFORMATION")

        # 1d. Phase 05 (component 33). Emergencies were handled above; these run before the prescription refusal.
        #     B16: a request to change a clinician-approved dose never changes anything and says who decides.
        #     Questions about the patient's own medicine times or medical tests are answered from their records.
        if not has_real_image:
            from app.agents.intent_router import classify as classify_intent_p05
            patient_intent = classify_intent_p05("PATIENT", clean_text).intent
            if patient_intent == "medication_change_request":
                return reply(medication_change_message(reply_lang),
                             {"type": "medication_change_requires_clinician", "scheduleChanged": False,
                              "ambulanceCall": AMBULANCE_NUMBER},
                             intent_value="MEDICATION_CHANGE_REQUEST")
            if patient_intent in {"medication_schedule", "medical_tests"}:
                if patient_user:
                    from app.agents.patient_care import respond_to_care
                    care = await respond_to_care(db, patient_user, get_ai_provider(), session_data, clean_text,
                                                 category="medication" if patient_intent == "medication_schedule"
                                                 else "test")
                    if care is not None:
                        return care
                return reply(
                    "Your medicine times and scheduled tests are the ones your doctor approved. Sign in and open "
                    "My Care Plan to see them; I can't set or change medicine times.",
                    {"type": "care_records_sign_in_required"}, intent_value="CARE_RECORDS")

        # 2. Unauthorized prescription / exact-dose requests (BUG-018).
        if not has_real_image and clinical_intent.is_prescription_request(clean_text):
            return reply(
                clinical_intent.prescription_refusal(clean_text, reply_lang),
                {"type": "prescription_request_declined"},
                intent_value="PRESCRIPTION_REQUEST",
            )

        # 3. Symptom + "what should I do?" is a health-guidance request, not a doctor search (BUG-012).
        if not has_real_image and clinical_intent.is_health_advice_request(clean_text):
            advice = clinical_intent.build_symptom_advice(clean_text, reply_lang)
            return reply(
                advice.text,
                {"type": "health_guidance", "symptoms": advice.symptoms, "durationDays": advice.duration_days,
                 "suggestedSpecialty": advice.specialty, "followUpQuestions": advice.follow_up_questions},
                intent_value="HEALTH_GUIDANCE",
            )

        # 4. Wellness questions covering several topics are answered together (BUG-019), and
        #    "without sleeping pills" is a wellness question, not a medicine lookup (BUG-020).
        topics = clinical_intent.wellness_topics(clean_text)
        medication_negated = clinical_intent.has_medication_negation(clean_text)
        if not has_real_image and (len(topics) >= 2 or (topics and medication_negated)) and not (
            clinical_intent.is_explicit_doctor_search(clean_text)
        ):
            if len(topics) >= 2:
                combined = clinical_intent.combine_wellness(topics, clean_text, reply_lang)
                result = reply(combined["text"], {"type": "general_wellness", "topics": topics},
                               intent_value=CompanionIntent.GENERAL_WELLNESS.value)
                result["activeWellnessCard"] = None
                return result
            single = WellnessKnowledge.get_wellness_guidance(clean_text, lang=reply_lang)
            if topics[0] == "diet":
                single = WellnessKnowledge.get_healthy_food_guidance(clean_text, lang=reply_lang)
            elif topics[0] == "exercise":
                single = WellnessKnowledge.get_exercise_guidance(clean_text, lang=reply_lang)
            result = reply(single.get("text", ""), {"type": "general_wellness", "card": single.get("card")},
                           intent_value=CompanionIntent.GENERAL_WELLNESS.value)
            result["activeWellnessCard"] = single.get("card")
            return result

        intent = CompanionIntentClassifier.classify_intent(
            query=clean_text,
            current_state=current_state,
            has_image=bool(image_bytes or image_url),
            candidate_count=len(session_data.get("candidateDoctors") or []),
        )
        parsed_delta = parse_query_deterministically(clean_text)
        provider = get_ai_provider()
        if patient_user and not (image_url or image_bytes):
            from app.agents.patient_care import respond_to_care
            care = await respond_to_care(db, patient_user, provider, session_data, clean_text)
            if care is not None:
                return care
        if patient_user and not (image_url or image_bytes) and re.search(
            r"\b(?:appointment status|booking status|mage booking|heta mata appointment|my appointments|my care tasks)\b",
            clean_text, re.I,
        ):
            return await cls._patient_status_turn(db, patient_user, provider, session_data, clean_text)
        requested_time = extract_appointment_time(clean_text)
        date_refinement = bool(parsed_delta.get("date")) and bool(re.search(
            r"\b(?:what|how)\s+about\b|\binstead\b|\bany\s+(?:slots?|doctors?|times?)\b|\bavailable\b",
            clean_text, re.I)) and not re.search(r"\b(?:book|reserve|channel|confirm)\b", clean_text, re.I)
        if not date_refinement and (requested_time or parsed_delta.get("timeRange")) and parsed_delta.get("date") and (
            intent == CompanionIntent.FIND_DOCTOR or patient_user and (prefs.get("specialty") or prefs.get("city"))
        ):
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
            # Stops before "on <date>", "for", "tomorrow", month names... so "Dr. UAT Neuro on November 26"
            # yields "UAT Neuro" (Phase 01 named-doctor slots request).
            "doctorName": (r"\bdr\.?\s+([\w][\w.'-]*(?:\s+[\w][\w.'-]*){0,3}?)"
                           r"(?=\s+(?:in|at|near|on|for|tomorrow|today|next|this|from|with|between|during|"
                           r"jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)\b"
                           r"|\s*'s\b|[?!,]|\.(?:\s|$)|$)"),
            "hospital": r"\bat\s+([\w .'-]+(?:hospital|clinic|centre|center))\b",
        }.items():
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                prefs[key] = parsed_delta[key] = match.group(1).strip()[:100]

        # Bounded LLM-assisted understanding (Phase 01): only for a message the deterministic parser could not turn
        # into any search preference. Emergency, prescription and health-advice messages returned earlier and never
        # reach the provider. The proposal is schema-validated and can only fill preferences (see intent_proposal).
        searchable_keys = ("specialty", "city", "maxFee", "minRating", "sortBy", "doctorName", "hospital", "date")
        if patient_user and not (image_url or image_bytes) and intent == CompanionIntent.FOLLOW_UP and not any(
            parsed_delta.get(key) not in (None, "") for key in searchable_keys
        ):
            from app.agents.intent_proposal import propose_preferences

            try:
                proposal, proposal_source = await asyncio.wait_for(
                    asyncio.to_thread(propose_preferences, provider, clean_text),
                    timeout=settings.AI_TIMEOUT_SECONDS + 1,
                )
            except Exception as exc:
                proposal, proposal_source = {}, "provider_unavailable"
                logger.warning("Intent proposal timed out or failed (%s).", type(exc).__name__)
            if proposal:
                parsed_delta.update(proposal)
                if proposal.get("specialty") or proposal.get("city"):
                    intent = CompanionIntent.FIND_DOCTOR
            session_data["understandingSource"] = proposal_source

        selection_text = re.sub(r"^(?:in|near|around)\s+", "", clean_text, flags=re.IGNORECASE)
        selection_text = selection_text.strip(".!? ").casefold()
        filter_only = any(
            isinstance(parsed_delta.get(key), str) and parsed_delta[key].casefold() == selection_text
            for key in ("city", "specialty")
        )
        search_requested = (
            intent == CompanionIntent.FIND_DOCTOR
            or (intent == CompanionIntent.BOOK_APPOINTMENT and bool(parsed_delta.get("specialty") or parsed_delta.get("city") or (requested_time or parsed_delta.get("timeRange")) and prefs.get("specialty")))
            or filter_only
            or any(parsed_delta.get(key) for key in ("doctorName", "hospital"))
            or (parsed_delta.get("specialty") and parsed_delta.get("language") == "si")
            or parsed_delta.get("maxFee") is not None
            or parsed_delta.get("sortBy") is not None
        )
        search_requested = search_requested or parsed_delta.get("minRating") is not None
        has_search_context = bool(prefs.get("specialty") or prefs.get("city") or prefs.get("doctorName")
                                  or session_data.get("candidateDoctors"))
        selection_request = clinical_intent.wants_auto_selection(clean_text)
        show_all_request = clinical_intent.wants_all_results(clean_text)
        # "Show me all cardiologists in Colombo" names what to search for; the intent classifier labelled it FOLLOW_UP.
        if parsed_delta.get("specialty") and (show_all_request or re.search(
                r"\b(?:show|find|search|list|need|want|looking|get me|give me)\b", clean_text, re.I)):
            search_requested = True
        if has_search_context and (
            selection_request or show_all_request
            # "Search in Colombo instead." / "What about Kandy?" — a city alone in an unrelated question
            # ("What is the weather in Colombo?") is not a search refinement.
            or (parsed_delta.get("city") and re.search(
                r"\b(?:search|find|look(?:ing)?|try|instead|show|switch|change|move|what about|how about|hoyanna|hoyala)\b",
                clean_text, re.I))
            or date_refinement                     # "What about tomorrow morning?"
        ):
            search_requested = True
        # A new search names a specialty, city or doctor; a message that only changes the budget,
        # rating or ordering ("mata 3000ta aduwen kenek hoyala denna") refines the previous search
        # and must keep the earlier specialty and location (BUG-001 conversation memory).
        fresh_search = bool(parsed_delta.get("specialty") or parsed_delta.get("doctorName") or parsed_delta.get("hospital")
                            or (parsed_delta.get("city") and not has_search_context))
        if search_requested and fresh_search and re.search(
            r"\b(?:find|search(?: for)?|recommend|show me|look(?:ing)? for|hoyala|hoyanna)\b", clean_text, re.IGNORECASE,
        ):
            prefs = {
                key: parsed_delta[key]
                for key in ("doctorName", "hospital") if parsed_delta.get(key)
            }
            if prefs_language := previous_preferences.get("language"):
                prefs["language"] = prefs_language

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
        if parsed_delta.get("minRating") is not None:
            prefs["minRating"] = float(parsed_delta["minRating"])
        if parsed_delta.get("specialty"):
            explicit = re.search(r"\b\w+(?:ologist|iatrician|iatrist|surgeon|specialist|physician|practitioner)s?\b|\bgp\b",
                                 clean_text, re.IGNORECASE)
            prefs["specialtyFromSymptoms"] = None if explicit else (parsed_delta.get("symptoms") or True)

        # Detect query language (Sinhala Unicode or Singlish) and persist
        detected_lang = detect_language(clean_text)
        if detected_lang == "si":
            prefs["language"] = "si"
        lang = prefs.get("language", "en")
        session_data["preferences"] = prefs

        # Locations MediConnect does not serve must not fall back to unrelated cities (BUG-011).
        unsupported = parsed_delta.get("unsupportedLocation")
        if unsupported and not parsed_delta.get("city"):
            kept = {key: value for key, value in prefs.items() if key != "city"}
            session_data["preferences"] = {**kept, "language": lang}
            return reply(
                (f"MediConnect currently lists verified doctors in Sri Lanka only, so I can't search in \"{unsupported}\". "
                 "Supported areas include Colombo, Kandy, Galle, Gampaha, Negombo, Kurunegala, Matara and Jaffna. "
                 "Which Sri Lankan city should I search instead?") if lang != "si" else
                (f"MediConnect හි දැනට ලැයිස්තුගත කර ඇත්තේ ශ්‍රී ලංකාවේ වෛද්‍යවරුන් පමණයි. එම නිසා \"{unsupported}\" හි සෙවිය නොහැක. "
                 "කොළඹ, මහනුවර, ගාල්ල, ගම්පහ, මීගමුව, කුරුණෑගල, මාතර, යාපනය වැනි නගරවල සෙවිය හැකියි. කුමන නගරයේ සොයන්නද?"),
                {"type": "unsupported_location", "location": unsupported},
                intent_value=CompanionIntent.FIND_DOCTOR.value,
                preferences={**kept, "language": lang},
            )

        # Add user message to history
        session_data["messages"].append({
            "id": str(ObjectId()),
            "sender": "user",
            "content": clean_text,
            "timestamp": utc_now(),
            "metadata": ({"attachment": {"type": "image", "name": (image_filename or "image")[:80]}} if image_bytes else {"imageUrl": image_url} if image_url else None),
        })

        # -----------------------------------------------------------------
        # Unified Intent Routing across Companion Capabilities (Phase 40)
        # -----------------------------------------------------------------
        session_data["activeIntent"] = intent.value

        # Capability 1: Medicine Image Analysis (Packaging/Label OCR & Uncertainty)
        if intent == CompanionIntent.MEDICINE_IMAGE_ANALYSIS or image_bytes or image_url:
            if not (image_bytes and image_filename):
                # Never analyze placeholder bytes or claim to have read an image we did not receive (BUG-023).
                session_data["activeImageAnalysis"] = None
                session_data["activeMedicineCard"] = None
                session_data["activeWellnessCard"] = None
                session_data["messages"].append({
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": (
                        "මට තවම පින්තූරයක් ලැබී නැහැ. ඖෂධ පැකේජයේ හෝ ලේබලයේ පැහැදිලි ඡායාරූපයක් කැමරා බොත්තම භාවිතයෙන් එවන්න."
                        if lang == "si" else
                        "I haven't received an image yet. Please use the camera button to upload a clear photo of the medicine "
                        "package or label, and I'll read what is printed on it."
                    ),
                    "timestamp": utc_now(),
                    "metadata": {"type": "image_required"},
                })
                session_data["updatedAt"] = utc_now()
                return session_data
            img_res = await MedicineImageAgent.analyze_medicine_image(
                image_bytes=image_bytes,
                filename=image_filename,
                user_prompt=clean_text,
                lang="si" if lang == "si" else "en",
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
                    "status": img_res.get("status"),
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
        # A message that names a doctor who is not already a candidate ("Show me all available appointment slots for
        # Dr. UAT Neuro on November 26, 2026") is a new search, not a follow-up about an earlier result
        # (Phase 01: it used to ask "Which doctor should I look up?").
        names_new_doctor = bool(parsed_delta.get("doctorName")) and not named
        if not names_new_doctor and (greeting or follow_up or (pending_action and (ordinal is not None or named))):
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
        wanted_date = parsed_delta.get("date")
        if selected_doctor and not selected_slot and (candidate_slots or wanted_date):
            time_match = re.search(r"(\d{1,2}[:.]\d{2})", clean_text)
            raw_time = None
            if time_match:
                raw_time = time_match.group(1).replace(".", ":")
                if len(raw_time) == 4:
                    raw_time = "0" + raw_time
            raw_time = raw_time or requested_time
            # Slots loaded when the doctor was picked can belong to another date (BUG-061 / P02-N01):
            # a time typed for a named date must be matched against that date's real slots only.
            if wanted_date and (not candidate_slots or any(s.get("date") != wanted_date for s in candidate_slots)):
                candidate_slots = await cls._fetch_available_slots(db, selected_doctor["doctorId"], wanted_date)
                session_data["candidateSlots"] = candidate_slots
            if raw_time:
                for s in candidate_slots:
                    if s.get("startTime") == raw_time and (not wanted_date or s.get("date") == wanted_date):
                        matched_slot = s
                        break
                if not matched_slot and intent in {CompanionIntent.BOOK_APPOINTMENT, CompanionIntent.FOLLOW_UP}:
                    return await cls._offer_same_doctor_alternatives(
                        db, session_data, selected_doctor, wanted_date or (candidate_slots[0].get("date")
                                                                           if candidate_slots else None),
                        raw_time, lang, current_state,
                    )
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
            # The model may choose which read-only tools to call, but the final list always comes from the
            # trusted, ranked search so hard constraints, ratings, de-duplication and ordering are consistent.
            doctors = await cls._search_candidate_doctors(db, prefs)
            if result is not None:
                _, tool_slots, grounded_reply = result
                known = {doctor["doctorId"] for doctor in doctors}
                slots_by_doctor = {key: value for key, value in tool_slots.items() if key in known}
                if not doctors:
                    grounded_reply = None
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
            doctors = dedupe_doctors(doctors)
            session_data["candidateDoctors"] = doctors

            if doctors:
                next_state = BookingAgentState.AWAITING_DOCTOR_SELECTION.value
                if validate_state_transition(session_data["state"], next_state):
                    session_data["state"] = next_state
                explanation = None
                if prefs.get("specialtyFromSymptoms") and prefs.get("specialty"):
                    symptoms = prefs.get("symptoms") if isinstance(prefs.get("symptoms"), str) else None
                    explanation = clinical_intent.specialty_explanation(prefs["specialty"], symptoms, lang)
                metadata: Dict[str, Any] = {"type": "doctor_options", "count": len(doctors), "doctors": doctors}
                if selection_request:
                    # BUG-010: pick one doctor from the ranked, constraint-satisfying list. No booking or payment.
                    selected = doctors[0]
                    assistant_msg = selection_explanation(selected, doctors, prefs, lang)
                    metadata = {"type": "doctor_auto_selected", "count": 1, "doctors": [selected],
                                "selectedDoctorId": selected["doctorId"], "consideredCount": len(doctors)}
                    session_data["autoSelectedDoctorId"] = selected["doctorId"]
                elif (clinical_intent.wants_recommendation(clean_text) and not show_all_request
                      and len(doctors) > RECOMMENDATION_LIMIT):
                    # "Recommend a good doctor": the most suitable one or two, not a long list. All matches stay
                    # in candidateDoctors so "show all" or a selection follow-up can use them.
                    shown = doctors[:RECOMMENDATION_LIMIT]
                    metadata = {"type": "doctor_options", "count": len(shown), "doctors": shown,
                                "totalMatches": len(doctors), "limitedToTop": RECOMMENDATION_LIMIT}
                    assistant_msg = cls._build_recommendation_message(shown, doctors, prefs, lang)
                elif grounded_reply and lang == "en":
                    assistant_msg = grounded_reply
                else:
                    assistant_msg = cls._build_doctor_options_message(doctors, prefs, lang)
                if explanation:
                    assistant_msg = f"{assistant_msg}\n\n{explanation}"
                session_data["messages"].append({
                    "id": str(ObjectId()),
                    "sender": "assistant",
                    "content": assistant_msg,
                    "timestamp": utc_now(),
                    "metadata": metadata,
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

        if prefs.get("doctorName"):
            # Filter by name in the database so a named doctor is never cut off by the result cap.
            named_users = db["users"].find(
                {"role": UserRole.DOCTOR.value,
                 "fullName": {"$regex": re.escape(prefs["doctorName"].strip()), "$options": "i"}},
                {"_id": 1},
            )
            named_ids = [str(u["_id"]) for u in named_users]
            if not named_ids:
                return []
            profile_query["userId"] = {"$in": named_ids}

        # Rank across the full matching set (the previous unsorted 200-row cap could drop the best match).
        profiles = list(db["doctor_profiles"].find(profile_query).sort([("_id", 1)]).limit(2000))
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
        min_rating = prefs.get("minRating")
        target_date = prefs.get("date")
        ratings = published_ratings(
            db, [str(u["_id"]) for _, u in verified_candidates], [str(p["_id"]) for p, _ in verified_candidates],
        )

        candidates: List[Dict[str, Any]] = []
        for p, user in verified_candidates:
            uid_str = str(user["_id"])
            prof_id = str(p["_id"])
            doc_name = user.get("fullName") or "Name unavailable"
            if prefs.get("doctorName") and prefs["doctorName"].casefold() not in doc_name.casefold():
                continue
            doc_fee = coerce_fee(p.get("consultationFee"))
            # Hard constraint: a doctor with an unknown fee cannot be shown as "within budget".
            if max_fee is not None and (doc_fee is None or doc_fee > float(max_fee)):
                continue
            rating, rating_count = ratings.get(uid_str) or ratings.get(prof_id) or (0.0, 0)
            if min_rating is not None and (rating_count == 0 or rating < float(min_rating)):
                continue
            doctor = {
                "doctorId": str(p.get("doctorId", "")),
                "doctorProfileId": prof_id,
                "doctorUserId": uid_str,
                "fullName": doc_name,
                "specialty": p.get("specialty") or "Specialty not listed",
                "qualifications": p.get("qualifications"),
                "profileImage": user.get("profileImage"),
                "city": p.get("city"),
                "hospitalOrClinic": p.get("hospitalOrClinic") or "",
                "experienceYears": int(p.get("experienceYears") or 0),
                "consultationFee": doc_fee,
                "rating": rating,
                "ratingCount": rating_count,
            }
            doctor["matchReasons"] = constraint_reasons(doctor, prefs)
            doctor["matchReason"] = doctor["matchReasons"][0] if doctor["matchReasons"] else "Verified doctor"
            candidates.append(doctor)

        results = rank_doctors(dedupe_doctors(candidates), prefs)[:5]
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
        fee = coerce_fee(doctor.get("consultationFee"))
        if fee is None:
            # Never invent a price for a booking summary.
            raise HTTPException(status_code=409, detail="This doctor's consultation fee is not available yet.")
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

    @classmethod
    def _build_recommendation_message(cls, shown: List[Dict[str, Any]], pool: List[Dict[str, Any]],
                                      prefs: Dict[str, Any], lang: str) -> str:
        from app.agents.doctor_ranking import DEFAULT_BASIS, SORT_LABELS
        basis = SORT_LABELS.get(prefs.get("sortBy"), DEFAULT_BASIS)
        if lang == "si":
            return (f"ඔබේ කොන්දේසි සපුරාලන වෛද්‍යවරුන් {len(pool)} දෙනා අතරින් වඩාත් ගැළපෙන {len(shown)} දෙනා මෙන්න "
                    f"(ශ්‍රේණිගත කිරීමේ පදනම: {basis}). සියල්ල බැලීමට 'show all' ලෙස කියන්න. "
                    "මෙය පැතිකඩ තොරතුරු මත පදනම් වූවකි; සායනික දක්ෂතාව පිළිබඳ තක්සේරුවක් නොවේ.")
        names = " and ".join(f"**{doctor['fullName']}**" for doctor in shown)
        return (f"From {len(pool)} verified doctors that meet your requirements, my top {len(shown)} are {names}, "
                f"ranked by {basis}. Say \"show all\" to see every match. This is based on listed profile "
                "information, not a judgement of clinical quality. Nothing has been booked.")

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

        if prefs.get("minRating") is not None:
            criteria.append(f"rated at least {float(prefs['minRating']):g}/5")
        c_text = " ".join(criteria) or "your search"
        # BUG-011: never present an arbitrary city as "nearby"; only offer to change the criteria.
        if lang == "si":
            return (
                f"සමාවන්න, {c_text} සඳහා ගැළපෙන තහවුරු කළ වෛද්‍යවරුන් හමු නොවුණා. "
                "වෙනත් නගරයක්, දිනයක් හෝ ගාස්තු සීමාවක් සමඟ නැවත සොයන්නද?"
            )
        return (
            f"I couldn't find any verified doctors matching {c_text}. "
            "Would you like to try a different city, another date, or a higher fee limit?"
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
    async def _offer_same_doctor_alternatives(
        cls,
        db: Database,
        session_data: Dict[str, Any],
        doctor: Dict[str, Any],
        requested_date: Optional[str],
        requested_time: str,
        lang: str,
        current_state: str,
    ) -> Dict[str, Any]:
        """The requested time is not open: keep the doctor and offer real nearby times (BUG-061).

        Same date first; another date only when that date has no openings. The doctor, specialty,
        location and budget preferences are left unchanged, and no availability is invented.
        """
        name = doctor.get("fullName", "the doctor")
        nearby = await cls._fetch_available_slots(
            db, doctor["doctorId"], requested_date, preferred_time=requested_time,
        ) if requested_date else []
        nearby = [slot for slot in nearby if not requested_date or slot.get("date") == requested_date][:4]
        other_date = None
        if not nearby:
            upcoming = await cls._fetch_available_slots(db, doctor["doctorId"])
            later = [slot for slot in upcoming if not requested_date or slot.get("date", "") > requested_date]
            if later:
                other_date = later[0]["date"]
                target = int(requested_time[:2]) * 60 + int(requested_time[3:])
                same_day = [slot for slot in later if slot["date"] == other_date]
                nearby = sorted(same_day, key=lambda slot: abs(
                    int(slot["startTime"][:2]) * 60 + int(slot["startTime"][3:]) - target))[:4]
        when = f"{requested_time} on {requested_date}" if requested_date else requested_time
        times = ", ".join(slot["startTime"] for slot in nearby)
        if nearby and not other_date:
            content = (f"{name} වෛද්‍යතුමා {when} ලබා ගත නොහැක. එදින ආසන්නම වේලාවන්: {times}. පහතින් එකක් තෝරන්න."
                       if lang == "si" else
                       f"{name} is not available at {when}. The nearest open times with {name} that day are "
                       f"{times}. Choose one below, or ask for another date.")
        elif nearby:
            content = (f"{name} වෛද්‍යතුමාට {requested_date} දින වේලාවන් නැත. ඊළඟ දිනය {other_date}: {times}."
                       if lang == "si" else
                       f"{name} has no open times on {requested_date}. The next date with openings is "
                       f"{other_date}: {times}. Choose one below, or ask for another date.")
        else:
            content = (f"{name} වෛද්‍යතුමාට දැනට ලබාගත හැකි වේලාවන් නොමැත."
                       if lang == "si" else
                       f"{name} is not available at {when}, and there are no upcoming open times for {name}. "
                       f"Would you like me to search for another doctor? I will not change the doctor unless you ask.")
        session_data["candidateSlots"] = nearby
        session_data["selectedSlot"] = None
        session_data["bookingSummary"] = None
        session_data["activeIntent"] = CompanionIntent.BOOK_APPOINTMENT.value
        target_state = BookingAgentState.AWAITING_SLOT_SELECTION.value
        if validate_state_transition(current_state, target_state) or session_data.get("persistent"):
            session_data["state"] = target_state
        session_data["messages"].append({
            "id": str(ObjectId()), "sender": "assistant", "content": content, "timestamp": utc_now(),
            "metadata": {"type": "slot_unavailable_alternatives", "doctorId": doctor["doctorId"],
                         "requestedDate": requested_date, "requestedTime": requested_time,
                         "alternativeDate": other_date, "alternatives": nearby},
        })
        session_data["updatedAt"] = utc_now()
        return session_data

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
