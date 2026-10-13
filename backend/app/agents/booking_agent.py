"""Conversational AI Booking Agent with bilingual multi-turn dialog, state machine, and safety checks."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo.database import Database

from app.agents.ai_provider import get_ai_provider
from app.agents.nlp_parser import (
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
                "metadata": None,
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

        lang = prefs.get("language", "en")
        session_data["preferences"] = prefs

        # Add user message to history
        session_data["messages"].append({
            "id": str(ObjectId()),
            "sender": "user",
            "content": clean_text,
            "timestamp": utc_now(),
            "metadata": None,
        })

        # 3. Handle explicit selections via conversational text if applicable
        selected_doctor = session_data.get("selectedDoctor")
        selected_slot = session_data.get("selectedSlot")
        candidate_doctors = session_data.get("candidateDoctors") or []
        candidate_slots = session_data.get("candidateSlots") or []

        # Check if user mentioned a doctor name from candidates
        matched_doctor = None
        if not selected_doctor and candidate_doctors:
            text_lower = clean_text.lower()
            for doc in candidate_doctors:
                doc_name = doc.get("fullName", "").lower()
                doc_id = doc.get("doctorId", "").lower()
                # Check for "dr. name" or last name match
                name_parts = [p for p in doc_name.replace("dr.", "").strip().split() if len(p) > 2]
                if doc_name in text_lower or doc_id in text_lower or any(p in text_lower for p in name_parts):
                    matched_doctor = doc
                    break

        if matched_doctor:
            session_data["selectedDoctor"] = matched_doctor
            selected_doctor = matched_doctor
            # Clear candidates and transition to slot selection
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

        # Check if user mentioned a time slot from candidate slots
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

        # 4. If doctor already selected and awaiting slot
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

        # 5. Doctor Discovery Search
        # If specialty is known or query has enough intent, search approved doctors
        if prefs.get("specialty") or prefs.get("city"):
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
                "මම ඔබට වෛද්‍යවරයකු සොයා ගැනීමට සහ වේලාවක් වෙන්කරවා ගැනීමට උදව් කළ හැකියි. "
                "කරුණාකර ඔබට අවශ්‍ය වෛද්‍ය විශේෂඥතාවය (උදා: චර්ම රෝග, හෘද රෝග) හෝ ඔබ සිටින නගරය සඳහන් කරන්න."
                if lang == "si"
                else "I'm your MediConnect Booking Assistant. I can help you find verified doctors and book an appointment. "
                "Could you please share what specialty or symptoms you're looking for, or your preferred city?"
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
        """Find approved and active doctors matching accumulated preferences."""
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

        max_fee = prefs.get("maxFee")
        if max_fee is not None:
            profile_query["consultationFee"] = {"$lte": float(max_fee)}

        profiles = list(db["doctor_profiles"].find(profile_query).limit(10))
        if not profiles:
            # If city match produced 0 results, retry without city to suggest available specialists
            if city:
                profile_query.pop("hospitalOrClinic", None)
                profiles = list(db["doctor_profiles"].find(profile_query).limit(10))

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

        results: List[Dict[str, Any]] = []
        for p in profiles:
            uid_str = str(p.get("userId", ""))
            user = active_users.get(uid_str)
            if not user:
                continue

            results.append({
                "doctorId": str(p.get("doctorId", "")),
                "doctorProfileId": str(p["_id"]),
                "doctorUserId": uid_str,
                "fullName": user.get("fullName", "Doctor"),
                "specialty": p.get("specialty", "General Medicine"),
                "hospitalOrClinic": p.get("hospitalOrClinic", "MediConnect Clinic"),
                "experienceYears": int(p.get("experienceYears", 0)),
                "consultationFee": float(p.get("consultationFee", 2500.0)),
                "rating": float(p.get("rating", 4.8)),
                "matchReason": f"Approved specialist in {p.get('specialty')} with {p.get('experienceYears', 0)} years experience",
            })

        return results[:5]

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
            lines = [f"ඔබේ අවශ්‍යතාවයට ගැළපෙන පිළිගත් {spec} වෛද්‍යවරුන් {count} දෙනෙකු සොයා ගන්නා ලදී:"]
            for i, d in enumerate(doctors, 1):
                lines.append(
                    f"{i}. {d['fullName']} - {d.get('hospitalOrClinic', 'රෝහල')} "
                    f"(ගාස්තුව: LKR {d['consultationFee']:,.0f})"
                )
            lines.append("කරුණාකර ලබාගත හැකි වේලාවන් බැලීමට වෛද්‍යවරයකු තෝරන්න.")
            return "\n".join(lines)

        lines = [f"I found {count} approved {spec}{loc_str} matching your preferences:"]
        for i, d in enumerate(doctors, 1):
            lines.append(
                f"{i}. {d['fullName']} - {d.get('hospitalOrClinic', 'Clinic')} "
                f"(Fee: LKR {d['consultationFee']:,.0f})"
            )
        lines.append("Please select a doctor to view their available appointment slots.")
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
            lines = [f"{name} වෛද්‍යතුමාගේ {date_sample} දින ලබාගත හැකි වේලාවන් ({slot_count}):"]
            for s in slots[:5]:
                lines.append(f"• {s['startTime']} - {s['endTime']}")
            lines.append("කරුණාකර ඔබ කැමති වේලාව තෝරන්න.")
            return "\n".join(lines)

        lines = [f"Here are the available appointment slots for {name} on {date_sample}:"]
        for s in slots[:5]:
            lines.append(f"• {s['startTime']} - {s['endTime']}")
        if slot_count > 5:
            lines.append(f"(and {slot_count - 5} more slots)")
        lines.append("Please select your preferred time slot.")
        return "\n".join(lines)

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
            return (
                f"නියමයි! ඔබ තෝරාගත් වෙන්කිරීමේ විස්තර:\n"
                f"• වෛද්‍යවරයා: {name}\n"
                f"• දිනය: {date}\n"
                f"• වේලාව: {time}\n"
                f"• මුළු ගාස්තුව: LKR {fee:,.0f}\n\n"
                "මෙම වේලාව වෙන්කරවා ගැනීමට කරුණාකර පහත 'Confirm Booking' බොත්තම ඔබන්න. "
                "ඉන්පසු ඔබට ආරක්ෂිතව Stripe හරහා ගෙවීම සම්පූර්ණ කළ හැකිය."
            )
        return (
            f"Great choice! Here is your booking summary:\n"
            f"• Doctor: {name}\n"
            f"• Date: {date}\n"
            f"• Time: {time}\n"
            f"• Total Payable: LKR {fee:,.0f}\n\n"
            "Please review the summary below and tap 'Confirm Booking' to reserve your 10-minute hold. "
            "You can then proceed to pay securely with Stripe."
        )
