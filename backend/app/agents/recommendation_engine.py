"""Doctor recommendation engine combining AI request understanding and deterministic ranking."""

from collections import defaultdict
from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo.database import Database

from app.agents.ai_provider import get_ai_provider
from app.config.settings import settings
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.specialty import SUPPORTED_SPECIALTIES
from app.models.user import AccountStatus, UserRole
from app.schemas.recommendation import (
    DoctorRecommendationItem,
    DoctorRecommendationRequest,
    DoctorRecommendationResponse,
    InterpretedPreferences,
    RecommendedSlotItem,
)
from app.services.doctor_service import (
    DoctorService,
    get_sl_now,
    get_sl_today_str,
)

logger = logging.getLogger(__name__)

EMERGENCY_DISCLAIMER_TEXT = (
    "MediConnect Doctor Discovery Assistant is an informational matching tool, not a diagnostic or "
    "prescribing system. No doctor-patient relationship is created by this recommendation. In the event "
    "of a medical emergency, please call 1990 immediately or visit the nearest emergency facility."
)

EMERGENCY_GUIDANCE_TEXT = (
    "POTENTIAL MEDICAL EMERGENCY DETECTED: Symptoms such as sudden chest pain, breathing difficulty, "
    "sudden numbness, heavy bleeding, or loss of consciousness require immediate professional evaluation. "
    "Please proceed immediately to the nearest hospital emergency department (ETU) or call Sri Lanka "
    "emergency ambulance service (1990). Do not delay for a scheduled clinic appointment."
)


class RecommendationEngine:
    """Hybrid recommendation engine for verified doctors."""

    @classmethod
    async def recommend_doctors(
        cls,
        db: Database,
        request: DoctorRecommendationRequest,
    ) -> DoctorRecommendationResponse:
        """Execute 7-step recommendation workflow with batched database lookups."""
        # -------------------------------------------------------------
        # STEP 1: Parse patient preferences via AI or deterministic NLP
        # -------------------------------------------------------------
        ai_provider = get_ai_provider()
        explicit_filters = {
            "specialty": request.specialty,
            "city": request.city,
            "date": request.date,
            "timeRange": request.timeRange,
            "maxFee": request.maxFee,
            "consultationType": request.consultationType,
        }
        parsed_prefs, provider_used = ai_provider.parse_request(request.query, explicit_filters)

        # -------------------------------------------------------------
        # STEP 2: Validate and normalize extracted filters
        # -------------------------------------------------------------
        target_specialty = parsed_prefs.get("specialty")
        if target_specialty:
            valid_spec = None
            for s in SUPPORTED_SPECIALTIES:
                if s.lower() == str(target_specialty).strip().lower():
                    valid_spec = s
                    break
            target_specialty = valid_spec

        target_city = parsed_prefs.get("city")
        target_date = parsed_prefs.get("date")
        target_time_range = parsed_prefs.get("timeRange")
        target_max_fee = parsed_prefs.get("maxFee")
        consultation_type = parsed_prefs.get("consultationType") or "in-person"
        is_urgent = bool(parsed_prefs.get("isUrgent", False))
        urgency_reason = parsed_prefs.get("urgencyReason")
        clarification = parsed_prefs.get("clarificationQuestion")
        lang = parsed_prefs.get("language", "en")

        interpreted = InterpretedPreferences(
            specialty=target_specialty,
            city=target_city,
            date=target_date,
            timeRange=target_time_range,
            maxFee=float(target_max_fee) if target_max_fee is not None else None,
            consultationType=consultation_type,
            languageDetected=lang,
        )

        # -------------------------------------------------------------
        # STEP 3: Query MongoDB for APPROVED and ACTIVE doctors only
        # -------------------------------------------------------------
        profile_query: Dict[str, Any] = {
            "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        }

        # Query all approved profiles
        profiles = list(db["doctor_profiles"].find(profile_query))
        if not profiles:
            return DoctorRecommendationResponse(
                interpretedPreferences=interpreted,
                recommendations=[],
                totalMatches=0,
                isUrgent=is_urgent,
                safetyGuidance=EMERGENCY_GUIDANCE_TEXT if is_urgent else None,
                disclaimer=EMERGENCY_DISCLAIMER_TEXT,
                clarificationQuestion=clarification,
                aiProviderUsed=provider_used,
            )

        # Fetch active doctor users in a single query
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

        # Filter profiles that map to an active doctor user
        verified_doctors: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for p in profiles:
            uid_str = str(p.get("userId", ""))
            user = active_users.get(uid_str)
            if user:
                verified_doctors.append((p, user))

        if not verified_doctors:
            return DoctorRecommendationResponse(
                interpretedPreferences=interpreted,
                recommendations=[],
                totalMatches=0,
                isUrgent=is_urgent,
                safetyGuidance=EMERGENCY_GUIDANCE_TEXT if is_urgent else None,
                disclaimer=EMERGENCY_DISCLAIMER_TEXT,
                clarificationQuestion=clarification,
                aiProviderUsed=provider_used,
            )

        # -------------------------------------------------------------
        # STEP 4: Apply hard filters to candidates
        # -------------------------------------------------------------
        candidate_doctors: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for profile, user in verified_doctors:
            fee = float(profile.get("consultationFee", 2500.0))

            # Hard filter: maxFee
            if target_max_fee is not None and fee > target_max_fee:
                continue

            candidate_doctors.append((profile, user))

        # If hard fee filter excluded everyone, fallback to verified doctors
        if not candidate_doctors:
            candidate_doctors = verified_doctors

        # -------------------------------------------------------------
        # STEP 5: Batch-retrieve real available slots for candidates
        # -------------------------------------------------------------
        sl_today = get_sl_today_str()
        cand_prof_ids = [str(p["_id"]) for p, _ in candidate_doctors]
        cand_user_ids = [str(u["_id"]) for _, u in candidate_doctors]

        # Single batch query for doctor availabilities
        avails_cursor = db["doctor_availabilities"].find({
            "doctorProfileId": {"$in": cand_prof_ids},
            "isActive": True,
            "date": {"$gte": sl_today},
        }).sort([("date", 1), ("startTime", 1)])
        avails_by_prof: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for av in avails_cursor:
            avails_by_prof[str(av.get("doctorProfileId", ""))].append(av)

        # Single batch query for active bookings
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
                    continue  # Expired hold does not block slot
            d_uid = str(a.get("doctorUserId", ""))
            booked_by_doc[d_uid].add((a.get("appointmentDate"), a.get("startTime")))

        # Generate slots per candidate doctor
        doctor_slots_map: Dict[str, List[RecommendedSlotItem]] = {}
        for profile, user in candidate_doctors:
            doc_user_id = str(user["_id"])
            doc_prof_id = str(profile["_id"])
            avails = avails_by_prof.get(doc_prof_id, [])
            booked_set = booked_by_doc.get(doc_user_id, set())

            doc_slots: List[RecommendedSlotItem] = []
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
                        doc_slots.append(
                            RecommendedSlotItem(
                                date=d_str,
                                startTime=gs.startTime,
                                endTime=gs.endTime,
                                availabilityId=av_id,
                            )
                        )

            doctor_slots_map[doc_user_id] = doc_slots

        # -------------------------------------------------------------
        # STEP 6: Deterministic Multi-Factor Ranking
        # -------------------------------------------------------------
        # Batch fetch verified review ratings for candidates
        candidate_uids = [str(u["_id"]) for _, u in candidate_doctors]
        candidate_pids = [str(p["_id"]) for p, _ in candidate_doctors]
        ratings_by_doc: Dict[str, Tuple[float, int]] = {}
        if candidate_uids and "doctor_reviews" in db.list_collection_names():
            rev_coll = db["doctor_reviews"]
            rating_aggr = rev_coll.aggregate([
                {
                    "$match": {
                        "$or": [
                            {"doctorUserId": {"$in": candidate_uids}},
                            {"doctorProfileId": {"$in": candidate_pids}},
                        ],
                        "status": "PUBLISHED",
                    }
                },
                {
                    "$group": {
                        "_id": "$doctorUserId",
                        "totalReviews": {"$sum": 1},
                        "avgRating": {"$avg": "$rating"},
                    }
                },
            ])
            for r in rating_aggr:
                ratings_by_doc[str(r["_id"])] = (float(r["avgRating"]), int(r["totalReviews"]))

        scored_candidates: List[Tuple[float, List[str], Dict[str, Any], Dict[str, Any]]] = []

        for profile, user in candidate_doctors:
            doc_user_id = str(user["_id"])
            doc_spec = str(profile.get("specialty", ""))
            doc_hospital = str(profile.get("hospitalOrClinic", ""))
            doc_fee = float(profile.get("consultationFee", 2500.0))
            doc_exp = int(profile.get("experienceYears", 0))
            slots = doctor_slots_map.get(doc_user_id, [])

            score = 0.0
            reasons: List[str] = []

            # 1. Specialty Match (up to 40 pts)
            if target_specialty:
                if doc_spec.lower() == target_specialty.lower():
                    score += 40.0
                    reasons.append(f"Direct match for requested specialty: {doc_spec}")
                elif "general" in doc_spec.lower():
                    score += 15.0
                    reasons.append(f"Provides general primary care as {doc_spec}")
                else:
                    score += 0.0
            else:
                score += 15.0  # Baseline when no specialty requested

            # 2. Location Match (up to 25 pts)
            if target_city:
                if target_city.lower() in doc_hospital.lower():
                    score += 25.0
                    reasons.append(f"Located in {target_city} ({doc_hospital})")
                else:
                    score += 0.0
            else:
                score += 10.0  # Baseline when no city requested

            # 3. Availability Match (up to 20 pts)
            has_exact_date_slot = False
            has_time_range_slot = False
            if target_date:
                exact_date_slots = [s for s in slots if s.date == target_date]
                if exact_date_slots:
                    has_exact_date_slot = True
                    if target_time_range:
                        for s in exact_date_slots:
                            hour = int(s.startTime[:2])
                            if (
                                (target_time_range == "morning" and 6 <= hour < 12)
                                or (target_time_range == "afternoon" and 12 <= hour < 17)
                                or (target_time_range == "evening" and 17 <= hour < 22)
                            ):
                                has_time_range_slot = True
                                break

            if has_time_range_slot:
                score += 20.0
                reasons.append(f"Has appointment slot available on {target_date} during {target_time_range}")
            elif has_exact_date_slot:
                score += 15.0
                reasons.append(f"Has slot available on requested date ({target_date})")
            elif slots:
                score += 10.0
                first_slot = slots[0]
                reasons.append(f"Available slot on {first_slot.date} at {first_slot.startTime}")
            else:
                reasons.append("No active open slots currently scheduled")

            # 4. Fee Preference Match (up to 10 pts)
            if target_max_fee is not None:
                if doc_fee <= target_max_fee:
                    score += 10.0
                    reasons.append(
                        f"Fee of LKR {doc_fee:,.0f} is within your budget (max LKR {target_max_fee:,.0f})"
                    )
                else:
                    score += 0.0
            else:
                if doc_fee <= 2500.0:
                    score += 8.0
                    reasons.append(f"Affordable fee of LKR {doc_fee:,.0f}")
                else:
                    score += 5.0

            # 5. Clinical Experience (up to 5 pts)
            exp_points = min(5.0, doc_exp * 0.4)
            score += exp_points
            if doc_exp >= 5:
                reasons.append(f"{doc_exp} years of clinical experience")

            # 6. Verified Patient Reviews & Ratings (fair shrinkage, no fabricated ratings)
            doc_rating_info = ratings_by_doc.get(doc_user_id)
            if doc_rating_info and doc_rating_info[1] > 0:
                avg_r, total_r = doc_rating_info
                # Bayesian smoothing towards 4.0 baseline with m=3 pseudo-reviews
                smoothed_rating = (total_r * avg_r + 3.0 * 4.0) / (total_r + 3.0)
                rating_bonus = round((smoothed_rating / 5.0) * 5.0, 1)
                score += rating_bonus
                reasons.append(
                    f"Rated {avg_r:.1f}/5 by verified patients ({total_r} verified review{'s' if total_r > 1 else ''})"
                )

            final_score = round(min(100.0, max(0.0, score)), 1)
            scored_candidates.append((final_score, reasons, profile, user))

        # Sort by score descending, then verified rating count, then available slots count descending, then fee ascending
        scored_candidates.sort(
            key=lambda item: (
                item[0],
                ratings_by_doc.get(str(item[3]["_id"]), (0.0, 0))[1],
                len(doctor_slots_map.get(str(item[3]["_id"]), [])),
                -float(item[2].get("consultationFee", 2500.0)),
            ),
            reverse=True,
        )

        # -------------------------------------------------------------
        # STEP 7: Format structured recommendations with explanations
        # -------------------------------------------------------------
        recommendations: List[DoctorRecommendationItem] = []
        max_recs = settings.AI_MAX_RECOMMENDATIONS

        for score, reasons, profile, user in scored_candidates[:max_recs]:
            doc_user_id = str(user["_id"])
            all_slots = doctor_slots_map.get(doc_user_id, [])

            # Filter slots to target date if requested, otherwise show first upcoming slots
            matched_slots = []
            if target_date:
                matched_slots = [s for s in all_slots if s.date == target_date]
            if not matched_slots:
                matched_slots = all_slots[:6]
            else:
                matched_slots = matched_slots[:6]

            recommendations.append(
                DoctorRecommendationItem(
                    doctorId=str(profile.get("doctorId", "")),
                    fullName=user.get("fullName", ""),
                    specialty=profile.get("specialty", ""),
                    hospitalOrClinic=profile.get("hospitalOrClinic", ""),
                    experienceYears=int(profile.get("experienceYears", 0)),
                    consultationFee=float(profile.get("consultationFee", 2500.0)),
                    bio=profile.get("bio"),
                    profileImage=user.get("profileImage"),
                    score=score,
                    matchReasons=reasons,
                    availableSlots=matched_slots,
                )
            )

        safety_guidance = EMERGENCY_GUIDANCE_TEXT if is_urgent else None
        if is_urgent and urgency_reason:
            safety_guidance = f"{urgency_reason} {EMERGENCY_GUIDANCE_TEXT}"

        return DoctorRecommendationResponse(
            interpretedPreferences=interpreted,
            recommendations=recommendations,
            totalMatches=len(recommendations),
            isUrgent=is_urgent,
            safetyGuidance=safety_guidance,
            disclaimer=EMERGENCY_DISCLAIMER_TEXT,
            clarificationQuestion=clarification if not recommendations else None,
            aiProviderUsed=provider_used,
        )
