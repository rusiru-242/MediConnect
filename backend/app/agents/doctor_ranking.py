"""Transparent doctor filtering, ranking and selection for the AI assistant.

Fixes:
- BUG-002/003: hard constraints (budget, rating) are always enforced server-side.
- BUG-007/022: duplicate cards — results are de-duplicated by canonical doctor identity.
- BUG-008: fees stored as strings/Decimal128 were shown as "Fee unavailable" or crashed comparisons.
- BUG-010: automatic single-doctor selection with a factual explanation.
- BUG-022: requested preferences (experience, rating, fee) drive ordering, and the ranking is
  explained with real profile data instead of an opaque "% match" score.

Nothing here invents ratings, experience or fees: missing values are reported as missing.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:  # bson is always present with pymongo, but keep the import defensive for tooling.
    from bson.decimal128 import Decimal128
except Exception:  # pragma: no cover
    Decimal128 = None  # type: ignore


def coerce_fee(value: Any) -> Optional[float]:
    """Normalize a stored consultation fee to a float, or None when genuinely unavailable."""
    if value is None or isinstance(value, bool):
        return None
    if Decimal128 is not None and isinstance(value, Decimal128):
        value = value.to_decimal()
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
    elif isinstance(value, str):
        cleaned = value.strip().lower().replace(",", "").replace("lkr", "").replace("rs.", "").replace("rs", "").strip()
        try:
            number = float(Decimal(cleaned))
        except (InvalidOperation, ValueError):
            return None
    else:
        return None
    if number != number or number < 0:  # NaN or negative
        return None
    return number


def published_ratings(db, doctor_user_ids: Iterable[str], doctor_profile_ids: Iterable[str]) -> Dict[str, Tuple[float, int]]:
    """Return {doctorUserId|doctorProfileId: (average, count)} from PUBLISHED reviews only."""
    user_ids = [str(x) for x in doctor_user_ids if x]
    profile_ids = [str(x) for x in doctor_profile_ids if x]
    if not user_ids and not profile_ids:
        return {}
    try:
        from app.models.review import ReviewStatus, get_review_collection

        rows = get_review_collection(db).aggregate([
            {"$match": {"status": ReviewStatus.PUBLISHED.value,
                        "$or": [{"doctorUserId": {"$in": user_ids}}, {"doctorProfileId": {"$in": profile_ids}}]}},
            {"$group": {"_id": {"u": "$doctorUserId", "p": "$doctorProfileId"},
                        "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
        ])
        ratings: Dict[str, Tuple[float, int]] = {}
        for row in rows:
            key = row["_id"] or {}
            avg = round(float(row.get("avg") or 0), 1)
            count = int(row.get("count") or 0)
            for identity in (key.get("u"), key.get("p")):
                if identity:
                    previous = ratings.get(str(identity))
                    if previous:
                        total = previous[1] + count
                        avg_combined = round((previous[0] * previous[1] + avg * count) / total, 1)
                        ratings[str(identity)] = (avg_combined, total)
                    else:
                        ratings[str(identity)] = (avg, count)
        return ratings
    except Exception:
        return {}


def dedupe_doctors(doctors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the first occurrence per canonical identity (doctor user, then doctorId, then profile)."""
    seen = set()
    unique = []
    for doctor in doctors:
        keys = {("u", str(doctor.get("doctorUserId") or "")), ("d", str(doctor.get("doctorId") or "")),
                ("p", str(doctor.get("doctorProfileId") or ""))}
        keys = {key for key in keys if key[1]}
        if keys & seen:
            continue
        seen |= keys
        unique.append(doctor)
    return unique


SORT_LABELS = {
    "experience_desc": "most years of experience",
    "rating_desc": "highest published patient rating (few-review ratings weighted toward a neutral 3.5/5)",
    "fee_asc": "lowest consultation fee",
}
DEFAULT_BASIS = ("published patient rating (few-review ratings weighted toward a neutral 3.5/5), "
                 "then years of experience, then lower fee")

# Small review counts are unreliable: a single 5-star review must not outrank 30 reviews averaging 4.7.
# Bayesian average toward a neutral prior. This is a transparent ordering rule, not a quality score.
RATING_PRIOR = 3.5
RATING_PRIOR_WEIGHT = 3


def adjusted_rating(doctor: Dict[str, Any]) -> float:
    count = int(doctor.get("ratingCount") or 0)
    if not count or doctor.get("rating") is None:
        return 0.0  # No published reviews: ranked after reviewed doctors, never given an invented rating.
    return (float(doctor["rating"]) * count + RATING_PRIOR * RATING_PRIOR_WEIGHT) / (count + RATING_PRIOR_WEIGHT)


def rank_doctors(doctors: List[Dict[str, Any]], prefs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Order doctors by the patient's explicit preference, with transparent tie-breakers."""
    sort_by = prefs.get("sortBy")

    def fee_key(d):
        return d["consultationFee"] if d.get("consultationFee") is not None else float("inf")

    def rating_key(d):
        return -adjusted_rating(d), -(d.get("ratingCount") or 0)

    if sort_by == "experience_desc":
        key = lambda d: (-(d.get("experienceYears") or 0), *rating_key(d), fee_key(d))  # noqa: E731
    elif sort_by == "rating_desc":
        key = lambda d: (*rating_key(d), -(d.get("experienceYears") or 0), fee_key(d))  # noqa: E731
    elif sort_by == "fee_asc":
        key = lambda d: (fee_key(d), *rating_key(d), -(d.get("experienceYears") or 0))  # noqa: E731
    else:
        # Default: soonest availability is unknown here, so prefer published rating with enough reviews,
        # then experience, then lower fee. This is stated in the explanation.
        key = lambda d: (*rating_key(d), -(d.get("experienceYears") or 0), fee_key(d))  # noqa: E731
    ordered = sorted(doctors, key=key)
    basis = SORT_LABELS.get(sort_by, DEFAULT_BASIS)
    for position, doctor in enumerate(ordered, 1):
        doctor["rankPosition"] = position
        doctor["rankingExplanation"] = f"Ranked #{position} by {basis}."
        doctor["matchScore"] = None  # Replaced an opaque score with transparent ranking (BUG-022).
    return ordered


def constraint_reasons(doctor: Dict[str, Any], prefs: Dict[str, Any]) -> List[str]:
    reasons = []
    if prefs.get("specialty"):
        reasons.append(f"Specialty: {doctor.get('specialty')}")
    if prefs.get("city"):
        place = doctor.get("city") or doctor.get("hospitalOrClinic")
        reasons.append(f"Location: {place}")
    fee = doctor.get("consultationFee")
    if prefs.get("maxFee") is not None and fee is not None:
        reasons.append(f"Consultation fee LKR {fee:,.0f} is within your LKR {float(prefs['maxFee']):,.0f} limit")
    elif fee is not None:
        reasons.append(f"Consultation fee LKR {fee:,.0f}")
    if doctor.get("ratingCount"):
        reasons.append(f"Patient rating {doctor['rating']:.1f}/5 from {doctor['ratingCount']} published review"
                       f"{'s' if doctor['ratingCount'] != 1 else ''}")
    elif prefs.get("minRating") is None:
        reasons.append("No published patient reviews yet")
    if doctor.get("experienceYears"):
        reasons.append(f"{doctor['experienceYears']} years of experience (as listed on the profile)")
    else:
        reasons.append("Years of experience not listed on the profile")
    return reasons


def comparison_lines(selected: Dict[str, Any], pool: List[Dict[str, Any]], prefs: Dict[str, Any]) -> List[str]:
    """How the selected doctor compares with the other eligible doctors on the ranking criterion."""
    sort_by = prefs.get("sortBy")
    lines = []
    for other in pool:
        if other is selected or other.get("doctorId") == selected.get("doctorId"):
            continue
        if sort_by == "experience_desc":
            value = f"{other['experienceYears']} years" if other.get("experienceYears") else "experience not listed"
        elif sort_by == "fee_asc":
            value = f"LKR {other['consultationFee']:,.0f}" if other.get("consultationFee") is not None else "fee unavailable"
        else:
            value = (f"rating {other['rating']:.1f}/5 from {other['ratingCount']} review{'s' if other['ratingCount'] != 1 else ''}"
                     if other.get("ratingCount") else "no published reviews")
        lines.append(f"{other.get('fullName')}: {value}")
    return lines[:4]


def selection_explanation(selected: Dict[str, Any], pool: List[Dict[str, Any]], prefs: Dict[str, Any], lang: str) -> str:
    """Explain an automatic selection using only real data (BUG-010)."""
    reasons = constraint_reasons(selected, prefs)
    basis = SORT_LABELS.get(prefs.get("sortBy"), DEFAULT_BASIS)
    count = len(pool)
    if lang == "si":
        lines = [f"ඔබේ කොන්දේසි සපුරාලන වෛද්‍යවරුන් {count} දෙනා අතරින් මම **{selected['fullName']}** තෝරා ගත්තා.",
                 "", "**තේරීමට හේතු (පැතිකඩ දත්ත අනුව):**", *[f"- {r}" for r in reasons], "",
                 f"ශ්‍රේණිගත කිරීමේ පදනම: {basis}.",
                 "මෙම තේරීම පැතිකඩ තොරතුරු මත පදනම් වූවකි; වෛද්‍යවරයාගේ සායනික දක්ෂතාව පිළිබඳ තක්සේරුවක් නොවේ.",
                 "මම තවම වෙන්කිරීමක් හෝ ගෙවීමක් කර නැහැ. ඉදිරියට යාමට 'View Available Slots' ඔබන්න."]
    else:
        others = comparison_lines(selected, pool, prefs)
        lines = [f"From {count} verified doctor{'s' if count != 1 else ''} that meet all your requirements, I selected **{selected['fullName']}**.",
                 "", "**Why this doctor (from their profile data):**", *[f"- {r}" for r in reasons], "",
                 *(["**Other eligible doctors:**", *[f"- {line}" for line in others], ""] if others else []),
                 f"Ranking basis: {basis}.",
                 "This choice is based on listed profile information, not a judgement of clinical quality.",
                 "I have not booked or charged anything. Tap View Available Slots when you want to continue."]
    return "\n".join(lines)
