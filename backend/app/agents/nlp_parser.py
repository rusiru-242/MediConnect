"""Deterministic NLP parser for multilingual (English and Sinhala) doctor recommendation requests."""

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Optional, Tuple

from app.models.specialty import SUPPORTED_SPECIALTIES, DoctorSpecialty

# Sri Lanka Standard Time (Asia/Colombo = UTC+05:30)
SL_TIMEZONE = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# EMERGENCY RED FLAGS (ENGLISH & SINHALA)
# ---------------------------------------------------------------------------
EMERGENCY_KEYWORDS_EN = [
    r"\bchest\s+pain\b",
    r"\bheart\s+attack\b",
    r"\bcardiac\s+arrest\b",
    r"\bcan'?t\s+breathe\b",
    r"\bcannot\s+breathe\b",
    r"\bsevere\s+(?:shortness\s+of\s+breath|difficulty\s+breathing)\b",
    r"\bstroke\b",
    r"\bslurred\s+speech\b",
    r"\bfacial\s+droop(?:ing)?\b",
    r"\bsudden\s+numbness\b",
    r"\bheavy\s+bleeding\b",
    r"\buncontrolled\s+bleeding\b",
    r"\bvomiting\s+blood\b",
    r"\bcoughing\s+up\s+blood\b",
    r"\bloss\s+of\s+consciousness\b",
    r"\bunconscious\b",
    r"\bpassed\s+out\b",
    r"\bsevere\s+head\s+injury\b",
    r"\bseizure\b",
    r"\banaphylaxis\b",
    r"\bsuicid(?:e|al)\b",
    r"\bkill\s+myself\b",
]

EMERGENCY_KEYWORDS_SI = [
    "පපුවේ කැක්කුම",
    "පපුව රිදෙනවා",
    "හුස්ම ගන්න අමාරුයි",
    "හුස්ම හිරවෙනවා",
    "ලේ යනවා",
    "සිහිය නැති වුණා",
    "කලන්තේ",
    "ස්ට්‍රෝක්",
    "හාට් ඇටෑක්",
    "වමනයට ලේ",
    "කැස්සට ලේ",
]

# ---------------------------------------------------------------------------
# SPECIALTY MAPPINGS (SYMPTOMS & KEYWORDS IN ENGLISH & SINHALA)
# ---------------------------------------------------------------------------
SPECIALTY_RULES: List[Tuple[str, List[str]]] = [
    (
        DoctorSpecialty.CARDIOLOGIST.value,
        [
            r"\bcardiolog(?:ist|y)\b",
            r"\bheart\b",
            r"\bpalpitation(?:s)?\b",
            r"\bblood\s+pressure\b",
            r"\bhypertension\b",
            r"\bhigh\s+bp\b",
            r"\becg\b",
            r"\becho\b",
            "හෘද",
            "හාට්",
            "ලේ පීඩනය",
            "පීඩනය වැඩි",
        ],
    ),
    (
        DoctorSpecialty.DERMATOLOGIST.value,
        [
            r"\bdermatolog(?:ist|y)\b",
            r"\bskin\b",
            r"\brash(?:es)?\b",
            r"\bacne\b",
            r"\bpimple(?:s)?\b",
            r"\beczema\b",
            r"\bpsoriasis\b",
            r"\bhair\s+loss\b",
            r"\bitching\b",
            "චර්ම",
            "සම",
            "හම",
            "කුරුලෑ",
            "කැසීම",
        ],
    ),
    (
        DoctorSpecialty.PEDIATRICIAN.value,
        [
            r"\bpediatric(?:ian)?\b",
            r"\bpaediatric(?:ian)?\b",
            r"\bchild(?:ren)?\b",
            r"\bbaby\b",
            r"\binfant\b",
            r"\bkid(?:s)?\b",
            r"\btoddler\b",
            r"\bvaccination\b",
            "ළමා",
            "බබා",
            "ළමයි",
            "දරුවා",
            "ළමා වෛද්‍ය",
        ],
    ),
    (
        DoctorSpecialty.NEUROLOGIST.value,
        [
            r"\bneurolog(?:ist|y)\b",
            r"\bmigraine(?:s)?\b",
            r"\bchronic\s+headache\b",
            r"\bheadache\b",
            r"\bnerve\b",
            r"\bneuropathy\b",
            r"\btremor(?:s)?\b",
            r"\bepilepsy\b",
            r"\bdizziness\b",
            "ස්නායු",
            "ඉරුවාරදය",
            "ඔළුව කැක්කුම",
            "කරකැවිල්ල",
        ],
    ),
    (
        DoctorSpecialty.PSYCHIATRIST.value,
        [
            r"\bpsychiatr(?:ist|y)\b",
            r"\bmental\s+health\b",
            r"\bdepression\b",
            r"\banxiety\b",
            r"\bstress\b",
            r"\binsomnia\b",
            r"\bsleep\s+disorder\b",
            r"\bbipolar\b",
            "මානසික",
            "විශාදය",
            "නින්ද නොයාම",
            "මානසික පීඩනය",
        ],
    ),
    (
        DoctorSpecialty.GYNECOLOGIST.value,
        [
            r"\bgynecolog(?:ist|y)\b",
            r"\bgynaecolog(?:ist|y)\b",
            r"\bobstetric(?:ian)?\b",
            r"\bpregnancy\b",
            r"\bpregnant\b",
            r"\bmaternity\b",
            r"\bmenstrua(?:l|tion)\b",
            r"\bperiod(?:s)?\b",
            r"\bpcos\b",
            r"\bfertility\b",
            "ප්‍රසව",
            "නාරි",
            "ගර්භනී",
            "ඔසප්",
            "කාන්තා රෝග",
        ],
    ),
    (
        DoctorSpecialty.ENT_SPECIALIST.value,
        [
            r"\bent\b",
            r"\bear\b",
            r"\bnose\b",
            r"\bthroat\b",
            r"\bsinus(?:itis)?\b",
            r"\btonsil(?:s|itis)?\b",
            r"\bhearing\s+loss\b",
            r"\btinnitus\b",
            r"\bsore\s+throat\b",
            "කන",
            "නාසය",
            "උගුර",
            "උගුරේ අමාරුව",
            "සයිනස්",
        ],
    ),
    (
        DoctorSpecialty.OPHTHALMOLOGIST.value,
        [
            r"\bophthalmolog(?:ist|y)\b",
            r"\beye(?:s)?\b",
            r"\bvision\b",
            r"\bcataract\b",
            r"\bglaucoma\b",
            r"\bblurry\s+vision\b",
            r"\bglasses\b",
            "ඇස්",
            "පෙනීම",
            "ඇසේ අමාරුව",
            "ඇස් දොස්තර",
        ],
    ),
    (
        DoctorSpecialty.ORTHOPEDIC_SURGEON.value,
        [
            r"\borthopedic(?:s)?\b",
            r"\borthopaedic(?:s)?\b",
            r"\bbone\b",
            r"\bfracture\b",
            r"\bjoint\s+pain\b",
            r"\bknee\s+pain\b",
            r"\bback\s+pain\b",
            r"\bspine\b",
            r"\barthritis\b",
            "ඇටකටු",
            "සන්ධි",
            "කොන්දේ කැක්කුම",
            "දණහිසේ කැක්කුම",
            "අස්ථි",
        ],
    ),
    (
        DoctorSpecialty.GASTROENTEROLOGIST.value,
        [
            r"\bgastroenterolog(?:ist|y)\b",
            r"\bgastro\b",
            r"\bstomach\s+pain\b",
            r"\bgastritis\b",
            r"\bacid\s+reflux\b",
            r"\bgerd\b",
            r"\bdigest(?:ion|ive)\b",
            r"\bliver\b",
            r"\bconstipation\b",
            r"\bdiarrhea\b",
            "ආමාශ",
            "බඩේ කැක්කුම",
            "ගැස්ට්‍රයිටිස්",
            "ආහාර ජීර්ණ",
            "අක්මාව",
        ],
    ),
    (
        DoctorSpecialty.ENDOCRINOLOGIST.value,
        [
            r"\bendocrinolog(?:ist|y)\b",
            r"\bdiabetes\b",
            r"\bdiabetic\b",
            r"\bthyroid\b",
            r"\bhormone(?:s)?\b",
            r"\bblood\s+sugar\b",
            "දියවැඩියාව",
            "තයිරොයිඩ්",
            "හෝමෝන",
            "සීනි වැඩි",
        ],
    ),
    (
        DoctorSpecialty.PULMONOLOGIST.value,
        [
            r"\bpulmonolog(?:ist|y)\b",
            r"\blung(?:s)?\b",
            r"\basthma\b",
            r"\bwheezing\b",
            r"\bbronchitis\b",
            r"\bcopd\b",
            r"\bchronic\s+cough\b",
            r"\brespiratory\b",
            "පෙනහළු",
            "ඇදුම",
            "හුස්ම",
            "ශ්වසන",
        ],
    ),
    (
        DoctorSpecialty.NEPHROLOGIST.value,
        [
            r"\bnephrolog(?:ist|y)\b",
            r"\bkidney(?:s)?\b",
            r"\brenal\b",
            r"\bdialysis\b",
            r"\bkidney\s+failure\b",
            "වකුගඩු",
            "වකුගඩු රෝග",
        ],
    ),
    (
        DoctorSpecialty.UROLOGIST.value,
        [
            r"\burolog(?:ist|y)\b",
            r"\burinary\b",
            r"\bbladder\b",
            r"\bprostate\b",
            r"\bkidney\s+stone(?:s)?\b",
            r"\burine\s+infection\b",
            r"\buti\b",
            "මුත්‍රා",
            "ප්‍රොස්ටේට්",
            "මුත්‍රා ආසාදන",
        ],
    ),
    (
        DoctorSpecialty.GENERAL_SURGEON.value,
        [
            r"\bgeneral\s+surgeon\b",
            r"\bsurgery\b",
            r"\bhernia\b",
            r"\bappendix\b",
            r"\bgallbladder\b",
            r"\babscess\b",
            "ශල්‍ය",
            "ශල්‍ය වෛද්‍ය",
            "සැත්කම්",
        ],
    ),
    (
        DoctorSpecialty.GENERAL_PHYSICIAN.value,
        [
            r"\bgeneral\s+physician\b",
            r"\bphysician\b",
            r"\bconsultant\s+physician\b",
            r"\bunexplained\s+weight\s+loss\b",
            "කායික",
            "කායික රෝග",
            "විශේෂඥ වෛද්‍ය",
        ],
    ),
    (
        DoctorSpecialty.GENERAL_PRACTITIONER.value,
        [
            r"\bgeneral\s+practitioner\b",
            r"\bgp\b",
            r"\bgeneral\s+doctor\b",
            r"\bfever\b",
            r"\bcold\b",
            r"\bflu\b",
            r"\bcough\b",
            r"\bgeneral\s+checkup\b",
            r"\broutine\s+checkup\b",
            r"\bvomiting\b",
            "සාමාන්‍ය වෛද්‍ය",
            "උණ",
            "කැස්ස",
            "සෙම්ප්‍රතිශ්‍යාව",
            "වමනය",
        ],
    ),
]

# ---------------------------------------------------------------------------
# SRI LANKA CITIES & HOSPITALS (ENGLISH & SINHALA)
# ---------------------------------------------------------------------------
LOCATION_PATTERNS: List[Tuple[str, List[str]]] = [
    ("Colombo", [r"\bcolombo\b", r"\bkollupitiya\b", r"\bbambalapitiya\b", r"\bnarahenpita\b", "කොළඹ"]),
    ("Kandy", [r"\bkandy\b", r"\bperadeniya\b", "මහනුවර", "නුවර"]),
    ("Galle", [r"\bgalle\b", r"\bkarapitiya\b", "ගාල්ල"]),
    ("Gampaha", [r"\bgampaha\b", "ගම්පහ"]),
    ("Negombo", [r"\bnegombo\b", "මීගමුව"]),
    ("Kurunegala", [r"\bkurunegala\b", "කුරුණෑගල"]),
    ("Kalutara", [r"\bkalutara\b", r"\bpanadura\b", "කළුතර", "පානදුර"]),
    ("Matara", [r"\bmatara\b", "මාතර"]),
    ("Jaffna", [r"\bjaffna\b", "යාපනය"]),
    ("Batticaloa", [r"\bbatticaloa\b", "මඩකලපුව"]),
    ("Anuradhapura", [r"\banuradhapura\b", "අනුරාධපුර"]),
    ("Ratnapura", [r"\bratnapura\b", "රත්නපුර"]),
    ("Badulla", [r"\bbadulla\b", "බදුල්ල"]),
    ("Asiri", [r"\basiri\b"]),
    ("Nawaloka", [r"\bnawaloka\b"]),
    ("Lanka Hospitals", [r"\blanka\s+hospitals?\b"]),
    ("Durdans", [r"\bdurdans\b"]),
    ("Kings Hospital", [r"\bkings?\s+hospitals?\b"]),
]

# ---------------------------------------------------------------------------
# TIME RANGE PATTERNS
# ---------------------------------------------------------------------------
TIME_RANGE_PATTERNS: List[Tuple[str, List[str]]] = [
    ("morning", [r"\bmorning\b", r"\bam\b", r"\bearly\b", "උදේ", "උදෑසන"]),
    ("afternoon", [r"\bafternoon\b", r"\bmidday\b", r"\bnoon\b", "දවල්", "සවස"]),
    ("evening", [r"\bevening\b", r"\bnight\b", r"\bpm\b", "හවස", "රෑ", "රාත්‍රී"]),
]

# ---------------------------------------------------------------------------
# DAY OF WEEK MAPPINGS
# ---------------------------------------------------------------------------
DAY_NAME_TO_INT = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "සඳුදා": 0,
    "අඟහරුවාදා": 1,
    "බදාදා": 2,
    "බ්‍රහස්පතින්දා": 3,
    "සිකුරාදා": 4,
    "සෙනසුරාදා": 5,
    "ඉරිදා": 6,
}


def get_sl_now() -> datetime:
    """Return current datetime in Sri Lanka Standard Time."""
    return datetime.now(SL_TIMEZONE)


def detect_language(text: str) -> str:
    """Detect if text contains Sinhala characters, else default to English."""
    if re.search(r"[\u0d80-\u0dff]", text):
        return "si"
    return "en"


def check_urgency(text: str) -> Tuple[bool, Optional[str]]:
    """Scan query for urgent/emergency symptom patterns."""
    text_lower = text.lower()

    for pattern in EMERGENCY_KEYWORDS_EN:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True, (
                "Potentially critical medical symptom detected (e.g., chest pain, respiratory distress, "
                "or acute neurological symptoms). Please seek immediate emergency medical care."
            )

    for keyword in EMERGENCY_KEYWORDS_SI:
        if keyword in text:
            return True, (
                "හදිසි වෛද්‍ය ප්‍රතිකාර අවශ්‍ය විය හැකි තත්ත්වයක් නිරීක්ෂණය විය. "
                "කරුණාකර ප්‍රමාද නොවී ළඟම ඇති රෝහලේ හදිසි ප්‍රතිකාර ඒකකයට (ETU) යොමු වන්න හෝ 1990 අමතන්න."
            )

    return False, None


def extract_specialty(text: str) -> Optional[str]:
    """Extract supported medical specialty from query keywords."""
    text_lower = text.lower()

    # 1. Exact match with supported specialty names
    for specialty in SUPPORTED_SPECIALTIES:
        if re.search(rf"\b{re.escape(specialty.lower())}\b", text_lower):
            return specialty

    # 2. Match with mapped symptoms and keyword rules
    for specialty, patterns in SPECIALTY_RULES:
        for p in patterns:
            if p.startswith(r"\b"):
                if re.search(p, text_lower, re.IGNORECASE):
                    return specialty
            else:
                if p.lower() in text_lower:
                    return specialty

    return None


def extract_location(text: str) -> Optional[str]:
    """Extract Sri Lanka city, district, or hospital preference."""
    text_lower = text.lower()
    for location, patterns in LOCATION_PATTERNS:
        for p in patterns:
            if p.startswith(r"\b"):
                if re.search(p, text_lower, re.IGNORECASE):
                    return location
            else:
                if p.lower() in text_lower:
                    return location
    return None


def extract_date(text: str) -> Optional[str]:
    """Extract and resolve target appointment date in YYYY-MM-DD format."""
    text_lower = text.lower()
    sl_today = get_sl_now().date()

    # 1. Explicit ISO date format YYYY-MM-DD
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso_match:
        try:
            d = datetime.strptime(iso_match.group(0), "%Y-%m-%d").date()
            if d >= sl_today:
                return d.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 2. Relative dates in English and Sinhala
    if "today" in text_lower or "අද" in text:
        return sl_today.strftime("%Y-%m-%d")

    if "day after tomorrow" in text_lower or "අනිද්දා" in text:
        return (sl_today + timedelta(days=2)).strftime("%Y-%m-%d")

    if "tomorrow" in text_lower or "හෙට" in text:
        return (sl_today + timedelta(days=1)).strftime("%Y-%m-%d")

    # 3. Days of the week (e.g., "this friday", "next monday", "සිකුරාදා")
    for day_name, target_weekday in DAY_NAME_TO_INT.items():
        if re.search(rf"\b{re.escape(day_name)}\b", text_lower) or day_name in text:
            current_weekday = sl_today.weekday()
            days_ahead = target_weekday - current_weekday
            if days_ahead <= 0:
                days_ahead += 7  # upcoming day
            return (sl_today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    return None


def extract_time_range(text: str) -> Optional[str]:
    """Extract preferred time range (morning, afternoon, evening)."""
    text_lower = text.lower()
    for tr, patterns in TIME_RANGE_PATTERNS:
        for p in patterns:
            if p.startswith(r"\b"):
                if re.search(p, text_lower, re.IGNORECASE):
                    return tr
            else:
                if p.lower() in text_lower:
                    return tr
    return None


def extract_max_fee(text: str) -> Optional[float]:
    """Extract maximum consultation fee from natural language text."""
    text_lower = text.lower()

    patterns = [
        r"(?:under|below|less\s+than|max|maximum|up\s+to|within)\s*(?:lkr|rs\.?|රු\.?)?\s*(\d+(?:,\d+)?(?:\.\d+)?)",
        r"(?:lkr|rs\.?|රු\.?)\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:or\s+less|max|below|under)",
        r"(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:ට\s*අඩු|නොවැඩි)",
        r"(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:lkr|rs\.?)\s*(?:budget|limit)",
    ]

    for p in patterns:
        m = re.search(p, text_lower)
        if m:
            val_str = m.group(1).replace(",", "")
            try:
                val = float(val_str)
                if 100 <= val <= 100000:
                    return val
            except ValueError:
                pass

    return None


def parse_query_deterministically(
    query: str,
    explicit_specialty: Optional[str] = None,
    explicit_city: Optional[str] = None,
    explicit_date: Optional[str] = None,
    explicit_time_range: Optional[str] = None,
    explicit_max_fee: Optional[float] = None,
    explicit_consultation_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse patient request into structured preferences using deterministic rules."""
    lang = detect_language(query)
    is_urgent, urgency_reason = check_urgency(query)

    # 1. Specialty: Explicit takes priority if valid
    parsed_specialty = None
    if explicit_specialty and explicit_specialty.strip():
        cand = explicit_specialty.strip()
        for s in SUPPORTED_SPECIALTIES:
            if s.lower() == cand.lower():
                parsed_specialty = s
                break
    if not parsed_specialty:
        parsed_specialty = extract_specialty(query)

    # 2. Location/City
    parsed_city = explicit_city.strip() if explicit_city and explicit_city.strip() else extract_location(query)

    # 3. Date
    parsed_date = explicit_date.strip() if explicit_date and explicit_date.strip() else extract_date(query)

    # 4. Time Range
    parsed_time_range = (
        explicit_time_range.strip().lower()
        if explicit_time_range and explicit_time_range.strip()
        else extract_time_range(query)
    )

    # 5. Max Fee
    parsed_max_fee = explicit_max_fee if explicit_max_fee is not None else extract_max_fee(query)

    # 6. Consultation Type
    parsed_consultation_type = explicit_consultation_type or "in-person"

    # 7. Clarification Question
    clarification = None
    if not parsed_specialty and not parsed_city and not parsed_date:
        if lang == "si":
            clarification = (
                "ඔබට අවශ්‍ය විශේෂඥ වෛද්‍ය ක්ෂේත්‍රය (උදා: හෘද, ළමා, චර්ම), ඔබ කැමති නගරය හෝ රෝහල "
                "සඳහන් කරන්නේ නම් වඩාත් නිවැරදි වෛද්‍යවරුන් සොයා දිය හැක."
            )
        else:
            clarification = (
                "Could you specify your health concern (e.g. skin rash, chest pain), preferred specialty, "
                "preferred city (e.g. Colombo, Kandy), or target date to help us narrow down recommendations?"
            )

    return {
        "specialty": parsed_specialty,
        "city": parsed_city,
        "date": parsed_date,
        "timeRange": parsed_time_range,
        "maxFee": parsed_max_fee,
        "consultationType": parsed_consultation_type,
        "language": lang,
        "isUrgent": is_urgent,
        "urgencyReason": urgency_reason,
        "clarificationQuestion": clarification,
    }
