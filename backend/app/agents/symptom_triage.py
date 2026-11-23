"""Deterministic, clinician-reviewed safety triage and post-generation safety filter."""

import re
from typing import List, Optional, Tuple

from app.models.health_chat import TriageLevel
from app.models.specialty import DoctorSpecialty, SUPPORTED_SPECIALTIES

# ---------------------------------------------------------------------------
# EMERGENCY ADVICE & DISCLAIMERS (ENGLISH & SINHALA)
# ---------------------------------------------------------------------------
STANDARD_DISCLAIMER_EN = (
    "Disclaimer: MediConnect AI Health Assistant provides general educational health information only. "
    "It is not medical advice, clinical diagnosis, or a treatment prescription. Always consult a licensed "
    "medical practitioner for symptoms. In an emergency, call 1990 immediately."
)

STANDARD_DISCLAIMER_SI = (
    "වගකීම් ප්‍රතික්ෂේප කිරීම: MediConnect AI සෞඛ්‍ය සහායකයා සාමාන්‍ය අධ්‍යාපනික සෞඛ්‍ය තොරතුරු පමණක් සපයයි. "
    "මෙය වෛද්‍ය උපදෙසක්, රෝග විනිශ්චයක් හෝ ඖෂධ නියමයක් නොවේ. රෝග ලක්ෂණ සඳහා සෑම විටම සුදුසුකම් ලත් වෛද්‍යවරයකු හමුවන්න. "
    "හදිසි අවස්ථාවකදී වහාම 1990 අමතන්න."
)

EMERGENCY_ALERT_EN = (
    "🚨 POTENTIAL MEDICAL EMERGENCY DETECTED: Symptoms such as sudden severe chest pain, breathing difficulty, "
    "sudden numbness/paralysis, uncontrollable bleeding, head trauma, acute poisoning, or loss of consciousness "
    "require immediate emergency care.\n\n"
    "• Please proceed immediately to the nearest hospital Emergency Treatment Unit (ETU) or\n"
    "• Call Sri Lanka National Ambulance Service at 1990 (Suwa Seriya) right now.\n\n"
    "Do NOT wait for a routine appointment."
)

EMERGENCY_ALERT_SI = (
    "🚨 හදිසි වෛද්‍ය අවධානයක් අවශ්‍ය තත්ත්වයක් නිරීක්ෂණය විය: හදිසි පපුවේ කැක්කුම, දැඩි හුස්ම ගැනීමේ අපහසුව, "
    "හදිසි අංශභාග ලක්ෂණ/අප්‍රාණික වීම, අධික රුධිර වහනය, සිහිසුන්වීම හෝ විෂ ශරීරගත වීම වැනි ලක්ෂණ සඳහා වහාම හදිසි ප්‍රතිකාර අවශ්‍ය වේ.\n\n"
    "• වහාම ළඟම ඇති රෝහලේ හදිසි ප්‍රතිකාර ඒකකයට (ETU) යන්න, නැතහොත්\n"
    "• ශ්‍රී ලංකා ජාතික ගිලන්රථ සේවය (1990 සුවසැරිය) දැන්ම අමතන්න.\n\n"
    "සාමාන්‍ය සායන වේලාවක් සඳහා ප්‍රමාද නොවන්න."
)

# ---------------------------------------------------------------------------
# 1. EMERGENCY RED FLAGS (Deterministic Regex Patterns)
# ---------------------------------------------------------------------------
EMERGENCY_PATTERNS_EN = [
    (r"\b(?:chest\s+pain|cardiac\s+arrest|heart\s+attack|crushing\s+chest|pressure\s+in\s+chest)\b", "Severe chest pain or suspected cardiac event"),
    (r"\b(?:can'?t\s+breathe|cannot\s+breathe|gasping\s+for\s+air|severe\s+shortness\s+of\s+breath|suffocating|blue\s+lips)\b", "Severe respiratory distress"),
    (r"\b(?:stroke|facial\s+droop(?:ing)?|slurred\s+speech|sudden\s+paralysis|sudden\s+numbness|one\s+side\s+(?:weak|numb))\b", "Signs of acute stroke or neurological deficit"),
    (r"\b(?:uncontrolled\s+bleeding|heavy\s+bleeding|hemorrhage|vomiting\s+blood|coughing\s+up\s+blood)\b", "Massive or uncontrolled hemorrhage"),
    (r"\b(?:lost\s+consciousness|unconscious|passed\s+out|blacked\s+out|collapsed|fainted\s+and\s+injured|unresponsive)\b", "Loss of consciousness or acute collapse"),
    (r"\b(?:anaphylaxis|throat\s+swelling|lips\s+swelling|severe\s+allergic\s+reaction)\b", "Potential anaphylactic reaction"),
    (r"\b(?:seizure|convulsion|epileptic\s+fit|status\s+epilepticus)\b", "Active seizure or convulsion"),
    (r"\b(?:poison(?:ing|ed)?|swallowed\s+bleach|swallowed\s+pills|overdose|drank\s+chemical)\b", "Acute poisoning or toxic ingestion"),
    (r"\b(?:suicid(?:e|al)|kill\s+myself|end\s+my\s+life|self\s*harm)\b", "Suicidal ideation or self-harm risk"),
    (r"\b(?:worst\s+headache\s+of\s+(?:my\s+)?life|thunderclap\s+headache|severe\s+head\s+injury|fractured\s+skull)\b", "Acute severe neurological or cranial injury"),
]

EMERGENCY_PATTERNS_SI = [
    ("පපුවේ කැක්කුම", "හදිසි පපුවේ වේදනාව"),
    ("පපුව රිදෙනවා", "පපුවේ කැක්කුම"),
    ("හාට් ඇටෑක්", "හෘදයාබාධ සැකය"),
    ("හුස්ම ගන්න අමාරුයි", "හුස්ම ගැනීමේ දැඩි අපහසුව"),
    ("හුස්ම හිරවෙනවා", "හුස්ම හිරවීම"),
    ("ස්ට්‍රෝක්", "ආඝාත ලක්ෂණ"),
    ("අප්‍රාණික වුණා", "හදිසි අංශභාග සැකය"),
    ("සිහිය නැති වුණා", "සිහිසුන් වීම"),
    ("කලන්තේ හැදිලා වැටුණා", "සිහිසුන් වීම"),
    ("ලේ වමනය", "රුධිරය වමනය දැමීම"),
    ("කැස්සට ලේ", "කැස්ස සමග රුධිරය පිටවීම"),
    ("අධික ලේ යනවා", "නොනවත්නා රුධිර වහනය"),
    ("විෂ ශරීරගත", "විෂවීම හෝ රසායනික ද්‍රව්‍ය ශරීරගත වීම"),
    ("දිවි නසා", "ස්වයං හානි අවදානම"),
    ("වලිප්පුව", "වලිප්පුව"),
]

# ---------------------------------------------------------------------------
# 2. PROMPT CARE SYMPTOMS (Requires clinical review within 12-24 hours)
# ---------------------------------------------------------------------------
PROMPT_CARE_PATTERNS_EN = [
    (r"\b(?:high\s+fever|fever\s+(?:over|above|of)\s+(?:102|103|104|39|40)|fever\s+for\s+(?:3|4|5|several)\s+days|fever\s+with\s+stiff\s+neck)\b", "Persistent or high-grade fever"),
    (r"\b(?:severe\s+stomach\s+pain|acute\s+abdominal\s+pain|appendix\s+pain|lower\s+right\s+abdomen)\b", "Acute abdominal pain"),
    (r"\b(?:persistent\s+vomiting|cannot\s+keep\s+fluids\s+down|severe\s+diarrhea|dehydrated|extreme\s+thirst\s+and\s+dizziness)\b", "Severe vomiting/diarrhea with dehydration risk"),
    (r"\b(?:animal\s+bite|dog\s+bite|monkey\s+bite|snake\s+bite|deep\s+cut|deep\s+puncture)\b", "Animal bite or deep wound requiring urgent prophylaxis"),
    (r"\b(?:eye\s+pain|sudden\s+blurred\s+vision|chemical\s+in\s+eye|eye\s+injury)\b", "Acute ocular symptom"),
    (r"\b(?:cannot\s+urinate|urinary\s+retention|blood\s+in\s+urine)\b", "Acute urinary complaint"),
    (r"\b(?:spreading\s+redness|hot\s+swollen\s+skin|cellulitis)\b", "Rapidly spreading skin infection"),
    (r"\b(?:broken\s+bone|possible\s+fracture|cannot\s+bear\s+weight)\b", "Suspected orthopedic fracture"),
]

PROMPT_CARE_PATTERNS_SI = [
    ("අධික උණ", "අධික උණ තත්ත්වය"),
    ("දරුණු බඩේ කැක්කුම", "දැඩි උදර වේදනාව"),
    ("නොනවත්වා වමනය", "නොනවත්නා වමනය සහ විජලනය"),
    ("බල්ලා හැපුවා", "සතෙකු සපා කෑම"),
    ("සතෙකු සපා කෑවා", "සතෙකු සපා කෑම"),
    ("නයෙක් ගැහුවා", "සර්ප දෂ්ටනය"),
    ("ඇසේ වේදනාව", "ඇසේ වේදනාව හෝ තුවාලය"),
    ("මුත්රා පිට නොවෙයි", "මුත්රා පිටකිරීමේ අපහසුව"),
    ("ඇටයක් කැඩිලා", "අස්ථි බිඳීමක් පිළිබඳ සැකය"),
]

# ---------------------------------------------------------------------------
# 3. ROUTINE CARE SYMPTOMS (Non-urgent, scheduled clinical consultation)
# ---------------------------------------------------------------------------
ROUTINE_CARE_PATTERNS_EN = [
    (r"\b(?:headache|migraine|tension\s+headache)\b", "Headache or migraine"),
    (r"\b(?:cough|cold|runny\s+nose|sore\s+throat|flu|congestion|sneezing)\b", "Upper respiratory symptoms"),
    (r"\b(?:back\s+pain|joint\s+pain|knee\s+pain|muscle\s+ache|neck\s+pain|arthritis)\b", "Musculoskeletal discomfort"),
    (r"\b(?:rash|itching|eczema|dry\s+skin|pimples|acne|allergy)\b", "Dermatological symptom"),
    (r"\b(?:acid\s+reflux|heartburn|indigestion|bloating|gastritis|gas)\b", "Gastrointestinal symptom"),
    (r"\b(?:fatigue|tiredness|trouble\s+sleeping|insomnia|mild\s+stress)\b", "General constitutional or lifestyle symptom"),
]

ROUTINE_CARE_PATTERNS_SI = [
    ("හිසරදය", "හිසරදය"),
    ("කැස්ස", "කැස්ස"),
    ("සෙම්ප්‍රතිශ්‍යාව", "සෙම්ප්‍රතිශ්‍යාව"),
    ("උගුර රිදෙනවා", "උගුරේ අමාරුව"),
    ("කොන්දේ කැක්කුම", "කොන්දේ වේදනාව"),
    ("ඇඟපත වේදනාව", "ශරීර වේදනාව"),
    ("සම කැසීම", "සමේ කැසීම හෝ පලු දැමීම"),
    ("බඩ දැවිල්ල", "ගැස්ට්‍රයිටිස් හෝ බඩ දැවිල්ල"),
]

# ---------------------------------------------------------------------------
# 4. PROHIBITED PHRASES FOR POST-GENERATION FILTER
# ---------------------------------------------------------------------------
PROHIBITED_DIAGNOSES_REGEX = [
    r"\b(?:i\s+diagnose\s+you\s+with|you\s+have\s+(?:been\s+diagnosed\s+with|contracted|got\s+the\s+disease))\b",
    r"\b(?:my\s+diagnosis\s+is|you\s+are\s+suffering\s+from\s+(?:malaria|dengue|covid-19|cancer|tuberculosis))\b",
    r"\b(?:you\s+definitely\s+have|this\s+is\s+a\s+confirmed\s+case\s+of)\b",
    r"(?:රෝග විනිශ්චය:|ඔබට .* රෝගය වැළඳී ඇත|මගේ රෝග විනිශ්චය)",
]

PROHIBITED_PRESCRIPTIONS_REGEX = [
    r"\b(?:take\s+\d+\s*(?:mg|ml|tablets?|capsules?|pills?)|take\s+(?:amoxicillin|ciprofloxacin|azithromycin|metformin|atorvastatin))\b",
    r"\b(?:i\s+prescribe|prescribing\s+you|dosage\s*:\s*\d+\s*(?:mg|ml))\b",
    r"\b(?:take\s+paracetamol\s+\d{3,4}\s*mg\s+every\s+\d+\s+hours|take\s+ibuprofen\s+\d{3}\s*mg)\b",
    r"(?:ඖෂධ නියමය:|මෙම පෙති බොන්න|මිලිග්‍රෑම් \d+ ක් ගන්න)",
]


# ---------------------------------------------------------------------------
# SPECIALTY MAPPING
# ---------------------------------------------------------------------------
SPECIALTY_SYMPTOM_MAP = [
    (DoctorSpecialty.CARDIOLOGIST.value, [r"\b(?:heart|chest\s+tightness|palpitation|high\s+blood\s+pressure|hypertension)\b", "හෘද", "පපුවේ"]),
    (DoctorSpecialty.DERMATOLOGIST.value, [r"\b(?:skin|rash|eczema|itch|acne|psoriasis|scalp|mole)\b", "සම", "පලු", "කුෂ්ඨ"]),
    (DoctorSpecialty.PEDIATRICIAN.value, [r"\b(?:child|baby|infant|toddler|pediatric|kid)\b", "ළමා", "බබා"]),
    (DoctorSpecialty.NEUROLOGIST.value, [r"\b(?:headache|migraine|dizziness|vertigo|tremor|numbness|nerve)\b", "ස්නායු", "හිසරදය"]),
    (DoctorSpecialty.PSYCHIATRIST.value, [r"\b(?:depression|anxiety|panic|stress|mental\s+health|insomnia|hallucination)\b", "මානසික", "නින්ද නොයාම"]),
    (DoctorSpecialty.GYNECOLOGIST.value, [r"\b(?:period|menstrua(?:l|tion)|pregnancy|pregnant|pelvic\s+pain|vaginal)\b", "ගර්භණී", "ඔසප්"]),
    (DoctorSpecialty.ENT_SPECIALIST.value, [r"\b(?:ear|nose|throat|sinus|hearing|tonsil|nasal)\b", "කන්", "නාස", "උගුර"]),
    (DoctorSpecialty.OPHTHALMOLOGIST.value, [r"\b(?:eye|vision|blurry\s+vision|cataract|glaucoma)\b", "ඇස්", "පෙනීම"]),
    (DoctorSpecialty.ORTHOPEDIC_SURGEON.value, [r"\b(?:bone|fracture|joint|knee|spine|back\s+pain|sprain|ligament)\b", "අස්ථි", "කොන්දේ"]),
    (DoctorSpecialty.GASTROENTEROLOGIST.value, [r"\b(?:stomach|gastritis|acid\s+reflux|heartburn|bowel|colon|liver|diarrhea)\b", "ආමාශ", "බඩ දැවිල්ල"]),
    (DoctorSpecialty.PULMONOLOGIST.value, [r"\b(?:asthma|wheezing|lung|persistent\s+cough|bronchitis)\b", "පෙනහළු", "ඇදුම"]),
    (DoctorSpecialty.ENDOCRINOLOGIST.value, [r"\b(?:diabetes|sugar|thyroid|hormone|insulin)\b", "දියවැඩියාව", "තයිරොයිඩ්"]),
    (DoctorSpecialty.GENERAL_PHYSICIAN.value, [r"\b(?:fever|general\s+checkup|weakness|fatigue|cold|flu|body\s+ache)\b", "උණ", "සෙම්ප්‍රතිශ්‍යාව"]),
]


class SymptomTriageEngine:
    """Clinical safety engine for classifying symptoms and sanitizing generated outputs."""

    @classmethod
    def classify_triage_pre_check(
        cls,
        text: str,
        language: str = "en",
    ) -> Tuple[TriageLevel, Optional[str], Optional[str]]:
        """Deterministic pre-generation triage check.

        Returns (TriageLevel, reason, detected_specialty).
        """
        lower = text.lower().strip()

        # 1. Check Emergency Red Flags first (English)
        for pattern, reason in EMERGENCY_PATTERNS_EN:
            if re.search(pattern, lower, re.IGNORECASE):
                return TriageLevel.EMERGENCY, reason, None

        # Check Emergency Red Flags (Sinhala)
        for term, reason in EMERGENCY_PATTERNS_SI:
            if term in text:
                return TriageLevel.EMERGENCY, reason, None

        # 2. Check Prompt Care (English & Sinhala)
        for pattern, reason in PROMPT_CARE_PATTERNS_EN:
            if re.search(pattern, lower, re.IGNORECASE):
                spec = cls.infer_specialty(lower, text)
                return TriageLevel.PROMPT_CARE, reason, spec

        for term, reason in PROMPT_CARE_PATTERNS_SI:
            if term in text:
                spec = cls.infer_specialty(lower, text)
                return TriageLevel.PROMPT_CARE, reason, spec

        # 3. Check Routine Care (English & Sinhala)
        for pattern, reason in ROUTINE_CARE_PATTERNS_EN:
            if re.search(pattern, lower, re.IGNORECASE):
                spec = cls.infer_specialty(lower, text)
                return TriageLevel.ROUTINE_CARE, reason, spec

        for term, reason in ROUTINE_CARE_PATTERNS_SI:
            if term in text:
                spec = cls.infer_specialty(lower, text)
                return TriageLevel.ROUTINE_CARE, reason, spec

        # 4. Default to General Info
        spec = cls.infer_specialty(lower, text)
        return TriageLevel.GENERAL_INFO, "General health informational inquiry", spec

    @classmethod
    def infer_specialty(cls, lower_text: str, raw_text: str) -> Optional[str]:
        """Map symptom descriptions to supported doctor specialties."""
        for spec, triggers in SPECIALTY_SYMPTOM_MAP:
            for trig in triggers:
                if trig.startswith(r"\b"):
                    if re.search(trig, lower_text, re.IGNORECASE):
                        return spec
                else:
                    if trig in raw_text or trig in lower_text:
                        return spec
        return DoctorSpecialty.GENERAL_PHYSICIAN.value

    @classmethod
    def sanitize_and_validate_post_generation(
        cls,
        text: str,
        language: str = "en",
    ) -> Tuple[str, bool, List[str]]:
        """Post-generation deterministic safety filter.

        Intercepts any hallucinations attempting diagnosis or prescription.
        Returns: (sanitized_text, was_modified, violations_list).
        """
        violations: List[str] = []
        sanitized = text

        # Check for prohibited diagnostic claims
        for pat in PROHIBITED_DIAGNOSES_REGEX:
            if re.search(pat, sanitized, re.IGNORECASE):
                violations.append("Prohibited definitive medical diagnosis detected")
                sanitized = re.sub(
                    pat,
                    "These symptoms may indicate several common issues; an in-person assessment by a medical doctor is necessary for an accurate diagnosis.",
                    sanitized,
                    flags=re.IGNORECASE,
                )

        # Check for prohibited prescription or specific drug dosages
        for pat in PROHIBITED_PRESCRIPTIONS_REGEX:
            if re.search(pat, sanitized, re.IGNORECASE):
                violations.append("Prohibited medication prescription or dosage advice detected")
                safe_warning = (
                    "Prescription medication and specific dosages require clinical evaluation and prescription by a licensed physician. Please do not self-medicate."
                    if language != "si"
                    else "ඖෂධ නියම කිරීම සහ නිසි මාත්‍රාව තීරණය කිරීම සඳහා සුදුසුකම් ලත් වෛද්‍යවරයකු හමුවිය යුතුය. කරුණාකර වෛද්‍ය උපදෙස් නොමැතිව ඖෂධ ලබා නොගන්න."
                )
                sanitized = re.sub(pat, safe_warning, sanitized, flags=re.IGNORECASE)

        was_modified = len(violations) > 0
        return sanitized, was_modified, violations

    @classmethod
    def get_emergency_response(cls, language: str = "en", reason: Optional[str] = None) -> str:
        """Return standardized immediate emergency guidance."""
        if language == "si":
            alert = EMERGENCY_ALERT_SI
            if reason:
                alert = f"හඳුනාගත් හේතුව: {reason}\n\n" + alert
            return alert

        alert = EMERGENCY_ALERT_EN
        if reason:
            alert = f"Flagged Concern: {reason}\n\n" + alert
        return alert

    @classmethod
    def get_disclaimer(cls, language: str = "en") -> str:
        """Return localized standard medical disclaimer."""
        return STANDARD_DISCLAIMER_SI if language == "si" else STANDARD_DISCLAIMER_EN
