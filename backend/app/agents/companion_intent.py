"""Unified Intent Classifier for MediConnect AI Health Companion (Phase 40).

Routes conversational user messages to the appropriate companion capability:
- FIND_DOCTOR: Looking for a medical specialist, clinic, or doctor recommendation.
- BOOK_APPOINTMENT: Selecting a slot, reviewing booking summary, confirming hold.
- MEDICINE_INFORMATION: Questions about uses, side effects, precautions, active ingredients.
- MEDICINE_IMAGE_ANALYSIS: Label/package photo upload, scan, or OCR inquiry.
- HEALTHY_FOOD: Nutrition, meal suggestions, Sri Lankan balanced diet, sugar reduction.
- EXERCISE_GUIDANCE: Physical activity, walking, beginner strength, stretching, posture.
- GENERAL_WELLNESS: Sleep hygiene, stress reduction, daily hydration, lifestyle habits.
- EMERGENCY_GUIDANCE: Potentially life-threatening acute red-flag symptoms (chest pain, stroke, etc.).
- FOLLOW_UP: Contextual continuation of existing active discussion.
"""

from enum import Enum
import re
from typing import Any, Dict, List, Optional

from app.agents.symptom_triage import SymptomTriageEngine, TriageLevel


class CompanionIntent(str, Enum):
    FIND_DOCTOR = "FIND_DOCTOR"
    BOOK_APPOINTMENT = "BOOK_APPOINTMENT"
    MEDICINE_INFORMATION = "MEDICINE_INFORMATION"
    MEDICINE_IMAGE_ANALYSIS = "MEDICINE_IMAGE_ANALYSIS"
    HEALTHY_FOOD = "HEALTHY_FOOD"
    EXERCISE_GUIDANCE = "EXERCISE_GUIDANCE"
    GENERAL_WELLNESS = "GENERAL_WELLNESS"
    EMERGENCY_GUIDANCE = "EMERGENCY_GUIDANCE"
    FOLLOW_UP = "FOLLOW_UP"


# Patterns for Food & Nutrition
FOOD_PATTERNS = [
    r"\b(?:food|diet|nutrition|breakfast|lunch|dinner|meal|meals|eat|eating|snack)\b",
    r"\b(?:sugar|sweet|sweetener|protein|calorie|calories|carbs|vegetable|vegetables|fruit|fruits)\b",
    r"\b(?:kola\s+kenda|red\s+rice|parippu|dhal|sambol|kurakkan|pittu|string\s+hoppers?)\b",
    r"(?:කෑම|ආහාර|උදේ|උදෑසන|සීනි|පෝෂණය)",
]

# Patterns for Exercise
EXERCISE_PATTERNS = [
    r"\b(?:exercise|exercises|workout|walking|walk|jogging|run|running|gym)\b",
    r"\b(?:strength|stretch|stretching|mobility|cardio|push-?up|squats?|aerobic)\b",
    r"\b(?:physical\s+activity|fitness|bodyweight|training)\b",
    r"(?:ව්‍යායාම|ඇවිදීම)",
]

# Patterns for Wellness (Sleep, Stress, Hydration, Mental)
WELLNESS_PATTERNS = [
    r"\b(?:sleep|insomnia|tired|fatigue|rest|bedtime|nap)\b",
    r"\b(?:stress|anxiety|calm|relax|relaxation|meditation|mindfulness|mental\s+health)\b",
    r"\b(?:water|hydration|hydrate|daily\s+habit|habits|lifestyle)\b",
    r"(?:නින්ද|පීඩනය|සුවතාවය)",
]

# Patterns for Medicine & Pharmacology
MEDICINE_PATTERNS = [
    r"\b(?:medicine|medicines|medication|medications|drug|drugs|tablet|tablets|pill|pills|capsule|capsules)\b",
    r"\b(?:paracetamol|panadol|amoxicillin|augmentin|metformin|glucophage|omeprazole|omez|atorvastatin|lipitor)\b",
    r"\b(?:cetirizine|zyrtec|ibuprofen|brufen|salbutamol|ventolin|losartan|cozaar|aspirin|piriton|antibiotic)\b",
    r"\b(?:side\s+effects?|precaution|precautions|active\s+ingredient|contraindications?|dosage|dose|used\s+for)\b",
    r"(?:බෙහෙත්|පෙති|ඖෂධ|පැරසිටමෝල්|පැනඩෝල්|ඇමොක්සිසිලින්)",
]

# Patterns for Image / Label scanning
IMAGE_PATTERNS = [
    r"\b(?:photo|image|picture|scan|label|packaging|bottle|box|camera|strip|blister)\b",
    r"(?:ඡායාරූප|පින්තූර)",
]

# Patterns for Doctor finding
DOCTOR_PATTERNS = [
    r"\b(?:find\s+(?:a\s+)?doctor|recommend\s+(?:a\s+)?doctor|need\s+(?:a\s+)?doctor|see\s+(?:a\s+)?doctor|specialist)\b",
    r"\b(?:cardiologist|dermatologist|pediatrician|neurologist|psychiatrist|gynecologist|surgeon|physician)\b",
    r"\b(?:gastroenterologist|endocrinologist|oncologist|urologist|nephrologist|pulmonologist|rheumatologist)\b",
    r"\b(?:ent\s+doctor|eye\s+doctor|orthopedic|general\s+practitioner)\b",
    r"\b(?:doctor\s+(?:in|near|around)|hospital|clinic)\b",
    r"(?:දොස්තර|වෛද්‍ය|වෛද්‍යවර|හෘද\s*රෝග)",
]

# Patterns for Booking & Appointment
BOOKING_PATTERNS = [
    r"\b(?:book|booking|appointment|slot|reserve|schedule|confirm\s+booking)\b",
    r"\b(?:select\s+doctor|select\s+slot|first\s+doctor|second\s+doctor|1st\s+doctor|2nd\s+doctor)\b",
    r"(?:වෙන්\s+කරන්න|ඇපොයින්ට්මන්ට්)",
]


class CompanionIntentClassifier:
    """Classifies user turn intent with multi-topic and safety preservation."""

    @classmethod
    def classify_intent(
        cls,
        query: str,
        current_state: str = "COLLECTING_PREFERENCES",
        has_image: bool = False,
        candidate_count: int = 0,
    ) -> CompanionIntent:
        """Classify user turn into CompanionIntent."""
        clean_q = query.strip().lower()

        # 1. Explicit image attachment
        if has_image or any(re.search(p, clean_q) for p in IMAGE_PATTERNS):
            if any(re.search(p, clean_q) for p in MEDICINE_PATTERNS) or has_image:
                return CompanionIntent.MEDICINE_IMAGE_ANALYSIS

        # 2. Emergency Safety Check
        triage_level, _, _ = SymptomTriageEngine.classify_triage_pre_check(clean_q, "en")
        if triage_level == TriageLevel.EMERGENCY:
            return CompanionIntent.EMERGENCY_GUIDANCE

        # 3. Active Booking Flow Continuity (if currently awaiting doctor selection or slot selection)
        if current_state in ["AWAITING_DOCTOR_SELECTION", "AWAITING_SLOT_SELECTION", "AWAITING_BOOKING_CONFIRMATION"]:
            # If user explicitly asks an educational question, switch topics!
            is_asking_food = any(re.search(p, clean_q) for p in FOOD_PATTERNS)
            is_asking_exercise = any(re.search(p, clean_q) for p in EXERCISE_PATTERNS)
            is_asking_wellness = any(re.search(p, clean_q) for p in WELLNESS_PATTERNS)
            is_asking_medicine = any(re.search(p, clean_q) for p in MEDICINE_PATTERNS)

            if not (is_asking_food or is_asking_exercise or is_asking_wellness or is_asking_medicine):
                return CompanionIntent.BOOK_APPOINTMENT

        # 4. Explicit booking intent
        if any(re.search(p, clean_q) for p in BOOKING_PATTERNS):
            return CompanionIntent.BOOK_APPOINTMENT

        # 5. Doctor search intent
        if any(re.search(p, clean_q) for p in DOCTOR_PATTERNS):
            return CompanionIntent.FIND_DOCTOR

        # 6. Medicine information intent
        if any(re.search(p, clean_q) for p in MEDICINE_PATTERNS):
            return CompanionIntent.MEDICINE_INFORMATION

        # 7. Healthy food intent
        if any(re.search(p, clean_q) for p in FOOD_PATTERNS):
            return CompanionIntent.HEALTHY_FOOD

        # 8. Exercise guidance intent
        if any(re.search(p, clean_q) for p in EXERCISE_PATTERNS):
            return CompanionIntent.EXERCISE_GUIDANCE

        # 9. General wellness intent
        if any(re.search(p, clean_q) for p in WELLNESS_PATTERNS):
            return CompanionIntent.GENERAL_WELLNESS

        # 10. Default / Follow-up / Symptom exploration
        if any(w in clean_q for w in ["fever", "cough", "headache", "rash", "pain", "discomfort", "sick", "ඇඟපත", "උණ", "කැස්ස"]):
            return CompanionIntent.FIND_DOCTOR

        return CompanionIntent.FOLLOW_UP
