"""Conversational AI Health Assistant Agent with safety-first triage and doctor referrals."""

from datetime import datetime, timezone
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo.database import Database

from app.agents.ai_provider import get_ai_provider
from app.agents.symptom_triage import (
    SymptomTriageEngine,
    TriageLevel,
)
from app.config.settings import settings
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.health_chat import utc_now
from app.models.specialty import DoctorSpecialty, SUPPORTED_SPECIALTIES
from app.models.user import AccountStatus, UserRole
from app.services.doctor_service import DoctorService, get_sl_today_str

logger = logging.getLogger(__name__)

HEALTH_ASSISTANT_SYSTEM_PROMPT = """You are MediConnect AI Health Assistant, an educational and patient-triage guidance assistant for Sri Lanka.
Your job is to provide safe, objective, and empathetic general symptom education and help patients navigate to qualified doctors.

CRITICAL MEDICAL SAFETY & CLINICAL RULES:
1. You are NOT a doctor. You MUST NOT diagnose illnesses, name confirmed conditions for the user ("You have X"), or prescribe medications or specific dosages.
2. If symptoms suggest emergency (e.g. chest pain, breathing difficulty, stroke symptoms, loss of consciousness), you MUST recommend immediate emergency care (1990 ambulance or hospital ETU).
3. For non-emergencies, explain potential general causes objectively without certainty, discuss general self-care or lifestyle considerations, and advise an in-person medical evaluation.
4. Output MUST be a valid JSON object matching this schema:
{
  "triage_level": "emergency" | "prompt_care" | "routine_care" | "general_info",
  "response_text": string,
  "clarifying_questions": string[],
  "recommended_specialty": string | null
}
Do NOT produce text outside the JSON object.
"""


class HealthAssistantAgent:
    """Conversational health agent with safety-first triage and doctor referral integration."""

    @classmethod
    async def process_user_turn(
        cls,
        db: Database,
        session_data: Dict[str, Any],
        user_message: str,
        language_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process one conversational turn from a patient."""
        clean_text = user_message.strip()[:1000]

        # Determine language (Sinhala detection or override or session default)
        lang = language_override or session_data.get("language", "en")
        if re.search(r"[\u0D80-\u0DFF]", clean_text):
            lang = "si"
        session_data["language"] = lang

        # Add user message to session transcript
        user_msg_id = str(ObjectId())
        session_data.setdefault("messages", []).append({
            "id": user_msg_id,
            "sender": "user",
            "content": clean_text,
            "timestamp": utc_now(),
            "metadata": None,
        })

        # -----------------------------------------------------------------
        # STEP 1: Deterministic Pre-generation Safety Triage Check
        # -----------------------------------------------------------------
        triage_level, triage_reason, detected_spec = SymptomTriageEngine.classify_triage_pre_check(
            clean_text, lang
        )

        # -----------------------------------------------------------------
        # EMERGENCY PATH: Zero-delay bypass of LLM
        # -----------------------------------------------------------------
        if triage_level == TriageLevel.EMERGENCY:
            emergency_text = SymptomTriageEngine.get_emergency_response(lang, triage_reason)
            disclaimer_text = SymptomTriageEngine.get_disclaimer(lang)

            session_data["triageLevel"] = TriageLevel.EMERGENCY.value
            session_data["updatedAt"] = utc_now()
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": emergency_text,
                "timestamp": utc_now(),
                "metadata": {
                    "triageLevel": TriageLevel.EMERGENCY.value,
                    "isUrgent": True,
                    "emergencyNumber": "1990",
                    "reason": triage_reason,
                    "disclaimer": disclaimer_text,
                    "clarifyingQuestions": [],
                    "doctorReferrals": [],
                    "recommendedSpecialty": None,
                },
            })
            return session_data

        # -----------------------------------------------------------------
        # STEP 2: Response Generation (LLM or Deterministic Fallback)
        # -----------------------------------------------------------------
        ai_response_dict = await cls._generate_guidance_response(
            clean_text=clean_text,
            lang=lang,
            triage_level=triage_level,
            detected_spec=detected_spec,
        )

        # Determine effective triage level (pre-check takes precedence if more severe)
        effective_triage = triage_level
        if effective_triage == TriageLevel.GENERAL_INFO and ai_response_dict.get("triage_level") in [
            TriageLevel.PROMPT_CARE.value,
            TriageLevel.ROUTINE_CARE.value,
        ]:
            effective_triage = TriageLevel(ai_response_dict["triage_level"])

        spec_to_recommend = ai_response_dict.get("recommended_specialty") or detected_spec
        if spec_to_recommend and spec_to_recommend not in SUPPORTED_SPECIALTIES:
            spec_to_recommend = DoctorSpecialty.GENERAL_PHYSICIAN.value

        raw_response_text = ai_response_dict.get("response_text", "")
        clarifying_questions = ai_response_dict.get("clarifying_questions", [])

        # -----------------------------------------------------------------
        # STEP 3: Deterministic Post-generation Safety Filter
        # -----------------------------------------------------------------
        sanitized_text, was_modified, violations = SymptomTriageEngine.sanitize_and_validate_post_generation(
            raw_response_text, lang
        )
        if was_modified:
            logger.info("Safety filter sanitized assistant response. Violations: %s", violations)

        disclaimer_text = SymptomTriageEngine.get_disclaimer(lang)

        # -----------------------------------------------------------------
        # STEP 4: Doctor Referral Resolution (Real Verified Doctors Only)
        # -----------------------------------------------------------------
        doctor_referrals: List[Dict[str, Any]] = []
        if effective_triage in [TriageLevel.ROUTINE_CARE, TriageLevel.PROMPT_CARE]:
            target_specialty = spec_to_recommend or DoctorSpecialty.GENERAL_PHYSICIAN.value
            doctor_referrals = await cls._fetch_verified_doctor_referrals(db, target_specialty)

        # -----------------------------------------------------------------
        # STEP 5: Append Assistant Message to Session
        # -----------------------------------------------------------------
        session_data["triageLevel"] = effective_triage.value
        session_data["recommendedSpecialty"] = spec_to_recommend
        session_data["updatedAt"] = utc_now()

        session_data["messages"].append({
            "id": str(ObjectId()),
            "sender": "assistant",
            "content": sanitized_text,
            "timestamp": utc_now(),
            "metadata": {
                "triageLevel": effective_triage.value,
                "isUrgent": effective_triage == TriageLevel.PROMPT_CARE,
                "emergencyNumber": "1990" if effective_triage == TriageLevel.PROMPT_CARE else None,
                "disclaimer": disclaimer_text,
                "clarifyingQuestions": clarifying_questions[:2],
                "recommendedSpecialty": spec_to_recommend,
                "doctorReferrals": doctor_referrals,
            },
        })

        return session_data

    @classmethod
    async def _generate_guidance_response(
        cls,
        clean_text: str,
        lang: str,
        triage_level: TriageLevel,
        detected_spec: Optional[str],
    ) -> Dict[str, Any]:
        """Generate guidance via configured AI Provider with deterministic fallback."""
        # Check if an LLM is configured
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip():
            try:
                llm_res = await cls._call_gemini_health_model(clean_text, lang)
                if llm_res:
                    return llm_res
            except Exception as e:
                logger.warning("Gemini health assistant call failed: %s. Using deterministic fallback.", e)

        # Use robust deterministic fallback
        return cls._generate_deterministic_fallback(clean_text, lang, triage_level, detected_spec)

    @classmethod
    async def _call_gemini_health_model(cls, text: str, lang: str) -> Optional[Dict[str, Any]]:
        """Call Gemini for health guidance generation."""
        import requests
        api_key = settings.GEMINI_API_KEY.strip()
        model_name = settings.GEMINI_MODEL or "gemini-1.5-flash"
        if model_name in ["gemini-1.5-flash", "gemini-2.5-flash"]:
            model_name = "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{HEALTH_ASSISTANT_SYSTEM_PROMPT}\n\nPatient Query ({lang}): {text}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        resp = requests.post(url, json=payload, timeout=settings.AI_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json()
            raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_json)
        return None

    @classmethod
    def _generate_deterministic_fallback(
        cls,
        text: str,
        lang: str,
        triage_level: TriageLevel,
        detected_spec: Optional[str],
    ) -> Dict[str, Any]:
        """Produce safe, high-quality rule-based responses in English and Sinhala."""
        spec = detected_spec or DoctorSpecialty.GENERAL_PHYSICIAN.value

        if lang == "si":
            if triage_level == TriageLevel.PROMPT_CARE:
                return {
                    "triage_level": TriageLevel.PROMPT_CARE.value,
                    "response_text": (
                        f"ඔබ සඳහන් කළ රෝග ලක්ෂණ අනුව, කඩිනම් වෛද්‍ය පරීක්ෂාවක් (Prompt Medical Evaluation) "
                        f"ලබා ගැනීම වඩාත් සුදුසුය. මෙම තත්ත්වය පිළිබඳව {spec} හෝ සාමාන්‍ය වෛද්‍යවරයකු හමුවී "
                        "පරීක්ෂා කරවා ගැනීම රෙකමදාරු කරනු ලැබේ. කිසිවිටෙකත් වෛද්‍ය උපදෙස් නොමැතිව ඖෂධ ගැනීමෙන් වළකින්න."
                    ),
                    "clarifying_questions": [
                        "මෙම රෝග ලක්ෂණ කොපමණ වේලාවක් හෝ දින කීයක් පවතීද?",
                        "වෙනත් අමතර අපහසුතා (උදා: වමනය, ක්ලාන්තය) තිබේද?",
                    ],
                    "recommended_specialty": spec,
                }
            elif triage_level == TriageLevel.ROUTINE_CARE:
                return {
                    "triage_level": TriageLevel.ROUTINE_CARE.value,
                    "response_text": (
                        f"ඔබ දක්වන රෝග ලක්ෂණ සාමාන්‍යයෙන් විවේකය, ප්‍රමාණවත් ජලය පානය සහ සුවදායී ජීවන රටාවක් මගින් "
                        f"පාලනය කළ හැකි වුවද, නිසි තක්සේරුවක් සඳහා {spec} වෛද්‍යවරයකු සමඟ සායනික උපදේශනයක් වෙන්කරවා ගැනීම සුදුසුය."
                    ),
                    "clarifying_questions": [
                        "මෙම අපහසුතාවය උග්‍රවන හෝ අඩුවන විශේෂ අවස්ථා තිබේද?",
                    ],
                    "recommended_specialty": spec,
                }
            else:
                return {
                    "triage_level": TriageLevel.GENERAL_INFO.value,
                    "response_text": (
                        "මෙය සාමාන්‍ය සෞඛ්‍ය අධ්‍යාපනික තොරතුරකි: සෞඛ්‍ය සම්පන්න ආහාර වේලක්, නිසි නින්ද සහ විජලනයෙන් "
                        "වැළකීම සමස්ත යහපැවැත්මට උපකාරී වේ. කිසියම් අපහසුතාවක් ඇත්නම් සුදුසුකම් ලත් වෛද්‍යවරයකු හමුවන්න."
                    ),
                    "clarifying_questions": [],
                    "recommended_specialty": spec,
                }

        # English Fallback
        if triage_level == TriageLevel.PROMPT_CARE:
            return {
                "triage_level": TriageLevel.PROMPT_CARE.value,
                "response_text": (
                    f"Based on the symptoms described, prompt medical attention is recommended within the next 12 to 24 hours. "
                    f"These signs warrant an in-person clinical assessment by a {spec} or at an outpatient clinic to prevent complications. "
                    "Please do not start self-prescribed antibiotics or medications without clinical guidance."
                ),
                "clarifying_questions": [
                    "How long have you been experiencing these symptoms?",
                    "Are you experiencing any other symptoms such as chills, vomiting, or dizziness?",
                ],
                "recommended_specialty": spec,
            }
        elif triage_level == TriageLevel.ROUTINE_CARE:
            return {
                "triage_level": TriageLevel.ROUTINE_CARE.value,
                "response_text": (
                    f"Your symptoms can be associated with several common factors. While general self-care measures like hydration and rest "
                    f"may provide comfort, scheduling a routine consultation with a verified {spec} is recommended for a personalized evaluation."
                ),
                "clarifying_questions": [
                    "Does anything specific seem to trigger or worsen these symptoms?",
                ],
                "recommended_specialty": spec,
            }
        else:
            return {
                "triage_level": TriageLevel.GENERAL_INFO.value,
                "response_text": (
                    "Here is general health information: Balanced nutrition, adequate hydration, regular rest, and stress management "
                    "are vital components of maintaining wellness. If you have personal health concerns, a consultation with a licensed practitioner is always advisable."
                ),
                "clarifying_questions": [],
                "recommended_specialty": spec,
            }

    @classmethod
    async def _fetch_verified_doctor_referrals(
        cls,
        db: Database,
        specialty: str,
    ) -> List[Dict[str, Any]]:
        """Fetch up to 3 real, approved, and active doctors for the recommended specialty."""
        # Find doctor profiles for this specialty (or fallback to General Physician)
        profile_query = {
            "verificationStatus": DoctorVerificationStatus.APPROVED.value,
            "specialty": specialty,
        }
        profiles = list(db["doctor_profiles"].find(profile_query).limit(5))

        if not profiles and specialty != DoctorSpecialty.GENERAL_PHYSICIAN.value:
            # Fallback to General Physician
            profiles = list(db["doctor_profiles"].find({
                "verificationStatus": DoctorVerificationStatus.APPROVED.value,
                "specialty": DoctorSpecialty.GENERAL_PHYSICIAN.value,
            }).limit(3))

        if not profiles:
            # Try any approved doctor
            profiles = list(db["doctor_profiles"].find({
                "verificationStatus": DoctorVerificationStatus.APPROVED.value,
            }).limit(3))

        if not profiles:
            return []

        user_ids = []
        for p in profiles:
            uid = p.get("userId")
            if uid:
                user_ids.append(ObjectId(uid) if ObjectId.is_valid(uid) else uid)

        active_users = {}
        if user_ids:
            users_cursor = db["users"].find({
                "_id": {"$in": user_ids},
                "role": UserRole.DOCTOR.value,
                "accountStatus": AccountStatus.ACTIVE.value,
            })
            active_users = {str(u["_id"]): u for u in users_cursor}

        cards: List[Dict[str, Any]] = []
        today_str = get_sl_today_str()

        for p in profiles:
            uid_str = str(p.get("userId", ""))
            user = active_users.get(uid_str)
            if not user:
                continue

            doc_id = str(p.get("doctorId", p.get("_id", "")))

            # Attempt to fetch next available slot
            next_slot_str = None
            try:
                avail_doc = db["doctor_availability"].find_one({
                    "doctorId": doc_id,
                    "date": {"$gte": today_str},
                    "slots": {"$elemMatch": {"isBooked": False}},
                })
                if avail_doc:
                    unbooked = [s for s in avail_doc.get("slots", []) if not s.get("isBooked")]
                    if unbooked:
                        next_slot_str = f"{avail_doc.get('date')} at {unbooked[0].get('startTime')}"
            except Exception:
                pass

            cards.append({
                "doctorId": doc_id,
                "fullName": user.get("fullName", "Doctor"),
                "specialty": p.get("specialty", specialty),
                "qualifications": p.get("qualifications", "MBBS"),
                "hospitalOrClinic": p.get("hospitalOrClinic", "MediConnect Clinic"),
                "experienceYears": int(p.get("experienceYears", 0)),
                "consultationFee": float(p.get("consultationFee", 2500.0)),
                "rating": float(p.get("rating", 4.8)),
                "city": p.get("city") or "Colombo",
                "nextAvailableSlot": next_slot_str,
                "matchReason": f"Verified {p.get('specialty')} with {p.get('experienceYears', 0)} years experience",
            })

            if len(cards) >= 3:
                break

        return cards
