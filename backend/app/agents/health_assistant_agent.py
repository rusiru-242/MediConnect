"""Conversational AI Health Assistant Agent with safety-first triage and doctor referrals.

A01: non-emergency answers come from the source-grounded composer in :mod:`app.agents.health_guidance`; a configured
provider (primary, then secondary) may only rephrase them, and every reply records whether it came from a provider
or from the deterministic engine ("responseSource").
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo.database import Database

from app.agents.doctor_ranking import coerce_fee
from app.agents.symptom_triage import (
    SymptomTriageEngine,
    TriageLevel,
)
from app.config.settings import settings
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.health_chat import utc_now
from app.models.specialty import DoctorSpecialty, SUPPORTED_SPECIALTIES
from app.models.user import AccountStatus, UserRole
from app.services.doctor_service import DoctorService

logger = logging.getLogger(__name__)

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
        # Multilingual, context-aware red-flag detection (BUG-013) supplements the legacy patterns.
        from app.agents.emergency_detector import (
            crisis_metadata, detect_emergency, emergency_message, informational_message, normalize,
            recent_user_texts,
        )

        history = recent_user_texts({"messages": session_data["messages"][:-1]})
        emergency = detect_emergency(clean_text, history)
        if emergency.is_emergency:
            triage_level, triage_reason = TriageLevel.EMERGENCY, emergency.reason
        elif emergency.suppressed in {"negated", "historical", "informational", "hypothetical"} and triage_level == TriageLevel.EMERGENCY:
            # e.g. "I have no chest pain" or "what are the signs of a heart attack?"
            triage_level = TriageLevel.GENERAL_INFO
        if re.search(r"[a-z]{3,}", clean_text, re.I) and not re.search(r"[඀-෿]", clean_text):
            from app.agents.nlp_parser import detect_language

            if detect_language(clean_text) == "si":
                lang = "si"
                session_data["language"] = lang

        # -----------------------------------------------------------------
        # EMERGENCY PATH: Zero-delay bypass of LLM
        # -----------------------------------------------------------------
        if triage_level == TriageLevel.EMERGENCY:
            emergency_text = (emergency_message(emergency, lang) if emergency.is_emergency
                              else SymptomTriageEngine.get_emergency_response(lang, triage_reason))
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
                    "category": emergency.category if emergency.is_emergency else None,
                    **(crisis_metadata(emergency) if emergency.is_emergency else {"crisisType": "medical"}),
                },
            })
            return session_data

        # Educational / hypothetical questions about an emergency condition: information with conditional
        # escalation instead of the emergency path (Phase 01 false positive in the Health Chat too).
        if emergency.suppressed in {"informational", "hypothetical"} and emergency.category:
            session_data["triageLevel"] = TriageLevel.GENERAL_INFO.value
            session_data["updatedAt"] = utc_now()
            session_data["messages"].append({
                "id": str(ObjectId()),
                "sender": "assistant",
                "content": informational_message(emergency, lang),
                "timestamp": utc_now(),
                "metadata": {
                    "triageLevel": TriageLevel.GENERAL_INFO.value,
                    "isUrgent": False,
                    "conditionalEmergency": True,
                    "emergencyNumber": "1990",
                    "category": emergency.category,
                    "disclaimer": SymptomTriageEngine.get_disclaimer(lang),
                    "clarifyingQuestions": [],
                    "doctorReferrals": [],
                    "recommendedSpecialty": None,
                },
            })
            return session_data

        # -----------------------------------------------------------------
        # STEP 2: Source-grounded answer (A01). The deterministic composer decides what may be said; a configured
        # provider may only rephrase non-authoritative answers, and its output is validated before use.
        # -----------------------------------------------------------------
        from app.agents.health_guidance import compose

        draft = compose(clean_text, lang, triage_level, detected_spec, history)
        effective_triage = draft.triage_level
        if triage_level == TriageLevel.PROMPT_CARE and effective_triage != TriageLevel.PROMPT_CARE and \
                draft.kind in {"symptom_guidance", "clarification", "prescription_refusal"}:
            effective_triage = TriageLevel.PROMPT_CARE
        raw_response_text = draft.text
        clarifying_questions = list(draft.clarifying_questions)
        spec_to_recommend = draft.specialty
        source = await cls._rephrase(draft, clean_text, lang, session_data["messages"][:-1])
        if source.get("reply") is not None:
            reply = source.pop("reply")
            raw_response_text = reply.response_text
            clarifying_questions = reply.clarifying_questions or clarifying_questions
            # A provider may refine a specialty only when the grounded answer recommends one (live A01: a sleep
            # question came back with "General Practitioner").
            if spec_to_recommend and reply.recommended_specialty:
                spec_to_recommend = reply.recommended_specialty
            if reply.triage_level == TriageLevel.PROMPT_CARE.value:
                effective_triage = TriageLevel.PROMPT_CARE
        if spec_to_recommend and spec_to_recommend not in SUPPORTED_SPECIALTIES:
            spec_to_recommend = DoctorSpecialty.GENERAL_PHYSICIAN.value

        # -----------------------------------------------------------------
        # STEP 3: Deterministic Post-generation Safety Filter
        # -----------------------------------------------------------------
        sanitized_text, was_modified, violations = SymptomTriageEngine.sanitize_and_validate_post_generation(
            raw_response_text, lang
        )
        if was_modified:
            logger.info("Safety filter sanitized assistant response. Violations: %s", violations)

        # Duplicate prevention (A01-H19): the same question again gets a short pointer, not the same long answer.
        previous = next((m for m in reversed(session_data["messages"][:-1]) if m.get("sender") == "assistant"), None)
        previous_user = next((m for m in reversed(session_data["messages"][:-1]) if m.get("sender") == "user"), None)
        if previous and (previous.get("content") == sanitized_text or (
                previous_user and normalize(previous_user.get("content", "")) == normalize(clean_text))):
            sanitized_text = (
                "ඔබ මේ ප්‍රශ්නය දැන් ඇසුවා — ඉහත පිළිතුර තවමත් අදාළයි. ඒ පිළිතුරේ කිසියම් කොටසක් ගැන වැඩි විස්තර, නැත්නම් "
                "වෛද්‍යවරයෙකු සොයා දීම අවශ්‍යද?" if lang == "si" else
                "You asked this just now — my answer above still applies. Would you like more detail on any part of it, "
                "or help finding a doctor?")
            clarifying_questions = []
            source["duplicateOfPrevious"] = True

        disclaimer_text = SymptomTriageEngine.get_disclaimer(lang)

        # -----------------------------------------------------------------
        # STEP 4: Doctor Referral Resolution (Real Verified Doctors Only)
        # -----------------------------------------------------------------
        doctor_referrals: List[Dict[str, Any]] = []
        if effective_triage in [TriageLevel.ROUTINE_CARE, TriageLevel.PROMPT_CARE] and not source.get(
                "duplicateOfPrevious"):
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
                "answerKind": draft.kind,
                **source,
            },
        })

        return session_data

    @classmethod
    async def _rephrase(cls, draft, clean_text: str, lang: str, previous_messages) -> Dict[str, Any]:
        """Optional provider rephrasing. Returns source metadata, plus "reply" when a validated rewrite was produced.

        Authoritative answers (refusals, medicine library facts) are never sent to a provider. Any provider failure,
        timeout or rejected output keeps the deterministic answer, and the reason is recorded (never the content).
        """
        from app.agents.health_guidance import health_timeout, llm_rewrite
        from app.agents.llm_client import LLMUnavailable, provider_order
        from app.agents.provider_gateway import record_fallback

        meta: Dict[str, Any] = {"responseSource": "deterministic", "provider": None, "model": None}
        order = provider_order()
        if draft.authoritative:
            meta["providerSkipped"] = "authoritative_answer"
            return meta
        if not order:
            meta["providerSkipped"] = "not_configured"
            return meta
        conversation = [{"sender": m.get("sender"), "content": str(m.get("content") or "")}
                        for m in previous_messages if m.get("sender") in {"user", "assistant"}]
        try:
            reply, result = await asyncio.wait_for(
                asyncio.to_thread(llm_rewrite, draft, clean_text, lang, conversation),
                timeout=2 * health_timeout(lang) + 6)
        except LLMUnavailable as exc:
            meta["providerFallbackReason"] = exc.reason
            meta["attempts"] = [{k: a.get(k) for k in ("provider", "model", "category")} for a in exc.attempts]
            for attempt in exc.attempts:
                if attempt.get("provider"):
                    record_fallback(attempt["provider"], attempt.get("category") or "unknown")
            return meta
        except asyncio.TimeoutError:
            meta["providerFallbackReason"] = "timeout"
            record_fallback(order[0], "timeout")
            return meta
        except ValueError as exc:  # validated but rejected (language, dropped danger signs, new numbers, ...)
            meta["providerFallbackReason"] = f"rejected:{str(exc)[:40]}"
            record_fallback(order[0], "rejected_output")
            return meta
        except Exception as exc:  # never let a provider problem fail the turn
            logger.warning("Health assistant rephrasing failed (%s).", type(exc).__name__)
            meta["providerFallbackReason"] = "error"
            return meta
        return {**result.meta(), "reply": reply}

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

        for p in profiles:
            uid_str = str(p.get("userId", ""))
            user = active_users.get(uid_str)
            if not user:
                continue

            doc_id = str(p.get("doctorId", p.get("_id", "")))

            result = await DoctorService.get_doctor_patient_slots(db, doc_id)
            days = result if isinstance(result, list) else [result]
            next_slot_str = next(
                (f"{day.date} at {day.slots[0].startTime}" for day in days if day.slots), None,
            )

            cards.append({
                "doctorId": doc_id,
                "fullName": user.get("fullName", "Doctor"),
                "specialty": p.get("specialty", specialty),
                "qualifications": p.get("qualifications", "MBBS"),
                "hospitalOrClinic": p.get("hospitalOrClinic", "MediConnect Clinic"),
                "experienceYears": int(p.get("experienceYears", 0)),
                "consultationFee": coerce_fee(p.get("consultationFee")),
                "rating": None,  # Ratings come only from published reviews; never invented.
                "city": p.get("city") or "Colombo",
                "nextAvailableSlot": next_slot_str,
                "matchReason": f"Verified {p.get('specialty')} with {p.get('experienceYears', 0)} years experience",
            })

            if len(cards) >= 3:
                break

        return cards
