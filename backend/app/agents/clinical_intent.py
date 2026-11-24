"""Clinical intent understanding for the patient AI assistant.

Fixes routing defects found in manual testing:
- BUG-012: symptom + "what should I do?" questions were routed to doctor search.
- BUG-018: unauthorized prescription requests produced "medicine not found".
- BUG-019: multi-topic wellness questions only answered one topic.
- BUG-020: "without sleeping pills" was routed to medicine lookup.
- BUG-021: symptom-based specialty suggestions had no explanation.

All functions are deterministic so they keep working without an AI provider.
Generated guidance is general education, not diagnosis or prescription.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional

from app.agents.emergency_detector import normalize

# ---------------------------------------------------------------------------
# Intent cues
# ---------------------------------------------------------------------------
ADVICE_CUES = (
    r"\bwhat (?:should|can|do) i do\b", r"\bwhat to do\b", r"\bhow (?:can|do|should) i (?:treat|manage|relieve|get rid|stop|ease|cope)\b",
    r"\bany (?:advice|tips|remed\w*)\b", r"\bis (?:it|this) (?:serious|normal|dangerous)\b", r"\bshould i (?:worry|be worried|see a doctor)\b",
    r"\bhome remed\w*", r"\bself[- ]care\b", r"\bwhy (?:do|am|is) (?:i|my)\b",
    r"\bmok(?:a|o)k?da\s+karanna\b", r"\bmokada\s+karanna\b", r"\bmonawada\s+karanna\b", r"\bkohomada\s+(?:hondak|suwa|adu)\w*",
    r"\bkarannada\b", r"\bkaranna\s+one\s+mokadda\b", r"\bupades\w*", r"\bbeheth\s+nathuwa\b",
    "මොකද කරන්න", "මොකක්ද කරන්න", "කුමක් කළ යුතු", "මොනවද කරන්න", "උපදෙස්",
)
DOCTOR_SEARCH_CUES = (
    r"\b(?:find|search|show|recommend|book|get|need|see|suggest|list)\b[^.?!]{0,30}\b(?:doctor|specialist|physician|\w+(?:ologist|iatrician|surgeon))s?\b",
    r"\b(?:which|what (?:kind of|type of)?)\s+(?:doctor|specialist)\b", r"\bwho should i see\b",
    r"\bdoctor\s+kenek\b", r"\bdosthara\s+kenek\b", r"\bhoyala\s+denna\b", r"\bhoyanna\b", r"\bchannel\b",
    "වෛද්‍යවරයෙක් හොයා", "දොස්තර කෙනෙක්", "වෛද්‍යවරයකු සොයා", "හොයලා දෙන්න",
)
SYMPTOM_TERMS: Dict[str, tuple] = {
    "headache": (r"\bhead ?ache\w*", r"\bmigraine\w*", r"\boluwa\s+(?:ridenaw\w*|kakku\w*|redenaw\w*|ridum\w*)",
                 r"\boluwe\s+(?:kakku\w*|amaru\w*)", "හිසරදය", "ඔළුව රිදෙ", "ඔළුවේ කැක්කුම", "ඔළුව කැක්කුම"),
    "fever": (r"\bfever\w*", r"\btemperature\b", r"\bpyrexia\b", r"\buna\b", r"\bunak\b", r"\bune\b", "උණ"),
    "sore_throat": (r"\bsore throat\b", r"\bthroat (?:pain|hurts|is sore)\b", r"\bugura\s+(?:ridenaw\w*|kakku\w*|amaru\w*)",
                    "උගුර රිදෙ", "උගුරේ අමාරු"),
    "cough": (r"\bcough\w*", r"\bkass?a\b", r"\bkassak\b", "කැස්ස"),
    "cold": (r"\b(?:common )?cold\b", r"\brunny nose\b", r"\bblocked nose\b", r"\bsemprath\w*", r"\bhembirissa\w*", "සෙම්ප්‍රතිශ්‍යාව", "හෙම්බිරිස්සාව"),
    "rash": (r"\brash\w*", r"\bitch\w*", r"\bhives\b", r"\bpalu\b", r"\bkasee\w*", r"\bkasi\w*", "පළු", "කැසීම", "කසනවා"),
    "stomach": (r"\bstomach\s+(?:ache|pain|upset)\b", r"\babdominal pain\b", r"\bdiarrh\w*", r"\bvomit\w*", r"\bnause\w*",
                r"\bbada\s+(?:ridenaw\w*|kakku\w*|amaru\w*)", r"\bbade\s+kakku\w*", r"\bwamane\w*", "බඩේ කැක්කුම", "බඩ රිදෙ", "වමනය", "පාචනය"),
    "back_pain": (r"\bback ?pain\b", r"\bbackache\b", r"\bkonda\s+(?:ridenaw\w*|kakku\w*)", r"\bkonde\s+kakku\w*", "කොන්දේ කැක්කුම", "කොන්ද රිදෙ"),
    "dizziness": (r"\bdizz\w*", r"\blight[- ]?headed\w*", r"\bkarakawill\w*", "කරකැවිල්ල", "ක්ලාන්ත"),
    "fatigue": (r"\bfatigue\w*", r"\btired\w* all the time\b", r"\balways tired\b", r"\bexhaust\w*", r"\bmahansi\w*", "මහන්සි", "තෙහෙට්ටුව"),
}
DURATION = re.compile(
    r"(?:\b(\d+|one|two|three|four|five|six|seven|a|few|several)\s*(?:k\s+)?(?:days?|dawas\w*|weeks?|sathi\w*|months?|masa\w*|hours?|paya\w*)\b)"
    r"|(?:(?:dawas|sathi|masa|paya)\w*\s+(\d+)\s*(?:k|ka|kata|ak)?)"
    r"|(?:(\d+)\s*(?:දින|සති|මාස|පැය))",
)
NUMBER_WORDS = {"one": 1, "a": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "few": 3, "several": 3}

PRESCRIPTION_CUES = (
    r"\bprescribe\w*\b", r"\bgive me (?:an? |some )?(?:antibiotic|prescription|medicine|medication|tablets?)\b",
    r"\b(?:exact|correct|right) (?:dose|dosage)\b", r"\bhow (?:many|much) (?:tablets?|mg|pills?) should i\b",
    r"\btreatment duration\b", r"\bwhich antibiotic\b", r"\bwhat antibiotic\b", r"\bantibiotic for me\b",
    r"\bwrite (?:me )?a prescription\b", r"\bwithout (?:seeing|consulting) a doctor\b", r"\bdon'?t want to (?:see|consult|visit) a doctor\b",
    r"\bbeheth\s+(?:liyala|liyanna|denna|kiyanna)\b", r"\bmonawada\s+bonna\s+one\b", r"\bmokada\s+bonna\s+one\b",
    r"\bantibiotic\s+(?:ekak|ekk)\b", "බෙහෙත් නියම", "ඖෂධ නියම", "මොනවද බොන්න ඕන", "ඇන්ටිබයොටික්",
)
MEDICATION_NEGATION = (
    r"\bwithout (?:taking |using |any )?(?:sleeping |sleep )?(?:pills?|tablets?|medicines?|medications?|drugs?)\b",
    r"\bno (?:sleeping )?(?:pills?|tablets?|medicines?|medications?)\b", r"\bnaturally\b", r"\bnatural(?:ly)? way\w*\b",
    r"\bdon'?t want (?:to take )?(?:pills?|tablets?|medicines?|medication)\b", r"\bbeheth\s+nathuwa\b", r"\bpethi\s+nathuwa\b",
    "බෙහෙත් නැතුව", "පෙති නැතුව",
)
WELLNESS_TOPICS = {
    "sleep": (r"\bsleep\w*", r"\binsomnia\b", r"\bninda\w*", r"\bnidaganna\b", "නින්ද"),
    "diet": (r"\bdiet\w*", r"\bnutrition\w*", r"\bhealthy (?:food|eating|meals?)\b", r"\beat(?:ing)? healthy\b", r"\bmeals?\b",
             r"\bkama\b", r"\bkeema\b", r"\bposhana\w*", "ආහාර", "කෑම"),
    "exercise": (r"\bexercis\w*", r"\bphysical(?:ly)? active\b", r"\bphysical activity\b", r"\bworkout\w*", r"\bfitness\b",
                 r"\bstay active\b", r"\bwalking\b", r"\bviyayam\w*", "ව්‍යායාම"),
    "stress": (r"\bstress\w*", r"\banxiety\b", r"\brelax\w*", r"\bmental (?:health|wellbeing)\b", r"\bpeedan\w*", "ආතතිය", "පීඩනය"),
    "hydration": (r"\bhydrat\w*", r"\bdrink(?:ing)? (?:more )?water\b", r"\bwathura\b", "වතුර", "ජලය"),
}
AUTO_SELECT_CUES = (
    r"\bselect (?:only )?one\b", r"\bchoose (?:only )?one\b", r"\bpick (?:only )?one\b", r"\bjust one\b", r"\bonly one doctor\b",
    r"\b(?:select|choose|pick) (?:the )?best\b", r"\bselect (?:a|one) doctor for me\b", r"\bchoose for me\b", r"\byou (?:choose|decide|pick)\b",
    r"\bek(?:a)?\s+kenek\s+(?:witharak|withrak|thoranna|thorala)\b", r"\bhondama\s+kenek\b", r"\bthorala\s+denna\b",
    "එක් කෙනෙක් තෝරා", "හොඳම කෙනෙක්", "තෝරලා දෙන්න",
)


def _has(text: str, terms) -> Optional[str]:
    for term in terms:
        if "\\" in term or "(" in term:
            match = re.search(term, text)
            if match:
                return match.group(0)
        elif term in text:
            return term
    return None


def detect_symptoms(text: str) -> List[str]:
    norm = normalize(text)
    return [name for name, terms in SYMPTOM_TERMS.items() if _has(norm, terms)]


def detect_duration_days(text: str) -> Optional[float]:
    norm = normalize(text)
    match = DURATION.search(norm)
    if not match:
        return None
    raw = match.group(1) or match.group(2) or match.group(3)
    amount = NUMBER_WORDS.get(raw, None) if raw and not raw.isdigit() else int(raw) if raw else None
    if amount is None:
        return None
    unit = match.group(0)
    if re.search(r"week|sathi|සති", unit):
        return amount * 7.0
    if re.search(r"month|masa|මාස", unit):
        return amount * 30.0
    if re.search(r"hour|paya|පැය", unit):
        return amount / 24.0
    return float(amount)


def is_prescription_request(text: str) -> bool:
    return bool(_has(normalize(text), PRESCRIPTION_CUES))


def has_medication_negation(text: str) -> bool:
    return bool(_has(normalize(text), MEDICATION_NEGATION))


def wellness_topics(text: str) -> List[str]:
    norm = normalize(text)
    return [topic for topic, terms in WELLNESS_TOPICS.items() if _has(norm, terms)]


def wants_auto_selection(text: str) -> bool:
    return bool(_has(normalize(text), AUTO_SELECT_CUES))


def is_explicit_doctor_search(text: str) -> bool:
    return bool(_has(normalize(text), DOCTOR_SEARCH_CUES))


def is_health_advice_request(text: str) -> bool:
    """Symptoms described with a request for guidance, and no explicit doctor search."""
    norm = normalize(text)
    if is_explicit_doctor_search(norm):
        return False
    symptoms = detect_symptoms(norm)
    if not symptoms:
        return False
    if _has(norm, ADVICE_CUES):
        return True
    # "I have had a headache for 3 days" (statement with a duration) is a request for guidance.
    return detect_duration_days(norm) is not None or bool(re.search(r"\b(?:i have|i'?ve|i am having|i'?m having|mata|මට)\b", norm))


# ---------------------------------------------------------------------------
# Specialty explanation (BUG-021)
# ---------------------------------------------------------------------------
SPECIALTY_EXPLANATIONS = {
    "Dermatologist": ("Dermatologists assess and treat skin, hair and nail problems such as rashes, itching and eczema.",
                      "චර්ම රෝග විශේෂඥ වෛද්‍යවරු සමේ පළු, කැසීම, එක්සිමා වැනි සම, හිසකෙස් සහ නියපොතු ආශ්‍රිත ගැටලු පරීක්ෂා කර ප්‍රතිකාර කරනවා."),
    "Cardiologist": ("Cardiologists assess heart and blood-vessel problems such as palpitations and high blood pressure.",
                     "හෘද රෝග විශේෂඥ වෛද්‍යවරු හෘද ස්පන්දන ගැටලු, අධි රුධිර පීඩනය වැනි හදවත හා රුධිර නාල ආශ්‍රිත ගැටලු පරීක්ෂා කරනවා."),
    "Neurologist": ("Neurologists assess problems of the brain and nerves, including persistent or unusual headaches, dizziness and numbness.",
                    "ස්නායු රෝග විශේෂඥ වෛද්‍යවරු දිගටම පවතින හෝ අසාමාන්‍ය හිසරදය, කරකැවිල්ල, හිරිවැටීම වැනි මොළය හා ස්නායු ආශ්‍රිත ගැටලු පරීක්ෂා කරනවා."),
    "ENT Specialist": ("ENT specialists assess ear, nose and throat problems such as a persistent sore throat or sinus symptoms.",
                       "කන, නාසය සහ උගුර විශේෂඥ වෛද්‍යවරු දිගටම පවතින උගුරේ අමාරුව, සයිනස් වැනි ගැටලු පරීක්ෂා කරනවා."),
    "Gastroenterologist": ("Gastroenterologists assess stomach, bowel and liver problems such as ongoing abdominal pain, reflux or diarrhoea.",
                           "ආමාශ හා අන්ත්‍ර රෝග විශේෂඥ වෛද්‍යවරු දිගටම පවතින බඩේ කැක්කුම, අම්ලපිත්තය, පාචනය වැනි ගැටලු පරීක්ෂා කරනවා."),
    "Pulmonologist": ("Pulmonologists assess lung and breathing problems such as asthma, wheezing or a long-lasting cough.",
                      "පෙනහළු රෝග විශේෂඥ වෛද්‍යවරු ඇදුම, හුස්ම හිරවීම, දිගුකාලීන කැස්ස වැනි ගැටලු පරීක්ෂා කරනවා."),
    "Pediatrician": ("Pediatricians care for babies, children and teenagers.", "ළමා රෝග විශේෂඥ වෛද්‍යවරු ළදරුවන්, ළමයින් සහ නව යොවුන් වියේ අයට ප්‍රතිකාර කරනවා."),
    "Orthopedic Surgeon": ("Orthopedic surgeons assess bone, joint, back and muscle problems.", "අස්ථි හා සන්ධි විශේෂඥ වෛද්‍යවරු ඇට, සන්ධි, කොන්ද සහ මාංශ පේශි ගැටලු පරීක්ෂා කරනවා."),
    "Ophthalmologist": ("Ophthalmologists assess eye and vision problems.", "අක්ෂි විශේෂඥ වෛද්‍යවරු ඇස් සහ පෙනීම ආශ්‍රිත ගැටලු පරීක්ෂා කරනවා."),
    "Psychiatrist": ("Psychiatrists assess mental health concerns such as persistent anxiety, low mood or sleep problems.",
                     "මනෝ වෛද්‍යවරු දිගටම පවතින කාංසාව, අවපීඩනය, නින්දේ ගැටලු වැනි මානසික සෞඛ්‍ය ගැටලු පරීක්ෂා කරනවා."),
    "General Practitioner": ("A general practitioner is a good first contact for common symptoms like fever, cough or cold and can refer you on if needed.",
                             "උණ, කැස්ස, සෙම්ප්‍රතිශ්‍යාව වැනි සාමාන්‍ය රෝග ලක්ෂණ සඳහා මුලින්ම හමුවීමට සාමාන්‍ය වෛද්‍යවරයා සුදුසුයි. අවශ්‍ය නම් ඔවුන් විශේෂඥයෙකුට යොමු කරනවා."),
    "General Physician": ("A general physician assesses a wide range of adult medical problems and can coordinate further tests.",
                          "කායික රෝග විශේෂඥ වෛද්‍යවරු වැඩිහිටියන්ගේ විවිධ රෝග ලක්ෂණ පරීක්ෂා කර අවශ්‍ය පරීක්ෂණ සංවිධානය කරනවා."),
}


def specialty_explanation(specialty: Optional[str], symptoms: Optional[str], lang: str) -> Optional[str]:
    if not specialty:
        return None
    pair = SPECIALTY_EXPLANATIONS.get(specialty)
    if not pair:
        return None
    if lang == "si":
        return f"{pair[1]} මෙය රෝග විනිශ්චයක් නොවෙයි; නිවැරදි තක්සේරුව වෛද්‍යවරයා කරනු ඇත."
    lead = f"You mentioned {symptoms}. " if symptoms else ""
    return f"{lead}{pair[0]} This is a suggestion of the right type of doctor, not a diagnosis."


# ---------------------------------------------------------------------------
# Symptom guidance (BUG-012)
# ---------------------------------------------------------------------------
@dataclass
class SymptomAdvice:
    text: str
    specialty: Optional[str]
    symptoms: List[str] = field(default_factory=list)
    duration_days: Optional[float] = None
    follow_up_questions: List[str] = field(default_factory=list)


_GUIDE = {
    "headache": {
        "en": dict(
            care=["Rest in a quiet, dim room and drink enough water.", "Eat regular meals and limit caffeine and screen time.",
                  "Note when headaches happen and anything that seems to trigger them."],
            red=["a sudden, severe 'worst ever' headache", "headache with fever and a stiff neck, confusion or a rash",
                 "weakness, numbness, trouble speaking or vision loss", "headache after a head injury"],
            see="A headache lasting several days should be checked by a doctor, especially if it is getting worse or is new for you.",
            questions=["Is the headache getting worse, or does it wake you from sleep?", "Do you also have fever, vomiting or vision changes?"],
            specialty="General Practitioner"),
        "si": dict(
            care=["නිස්කලංක, අඳුරු කාමරයක විවේක ගන්න. ප්‍රමාණවත් තරම් වතුර බොන්න.", "වේලාවට කෑම ගන්න. කෝපි/තේ සහ ජංගම දුරකථන භාවිතය අඩු කරන්න.",
                  "හිසරදය එන වේලාවන් සහ ඊට හේතු විය හැකි දේ සටහන් කරගන්න."],
            red=["හදිසියේ ඇතිවන ඉතා දරුණු හිසරදයක්", "උණ සහ ගෙල තද වීම, ව්‍යාකූල බව හෝ පළු සමඟ හිසරදය",
                 "ශරීරයේ දුර්වලතාවය, හිරිවැටීම, කතා කිරීමේ අපහසුව හෝ පෙනීම නැතිවීම", "හිසට තුවාලයකින් පසු හිසරදය"],
            see="දින කිහිපයක් තිස්සේ පවතින හිසරදයක් වෛද්‍යවරයෙකු ලවා පරීක්ෂා කරගැනීම වැදගත්. විශේෂයෙන් එය වැඩිවෙනවා නම් හෝ ඔබට අලුත් නම්.",
            questions=["හිසරදය දිනෙන් දින වැඩිවෙනවාද, නැත්නම් නින්දෙන් අවදි කරනවාද?", "උණ, වමනය හෝ පෙනීමේ වෙනසක් තිබේද?"],
            specialty="General Practitioner"),
    },
    "fever": {
        "en": dict(
            care=["Rest and drink plenty of fluids such as water, king coconut water or soup.", "Wear light clothing and check your temperature regularly."],
            red=["difficulty breathing, chest pain or confusion", "a rash, bleeding gums or severe abdominal pain (possible dengue warning signs)",
                 "very little urine, persistent vomiting or extreme weakness", "fever in a baby under 3 months"],
            see="In Sri Lanka, a fever lasting 2 days or more should be checked by a doctor, including a blood test to rule out dengue if advised.",
            questions=["How high has your temperature been?", "Do you have body aches, rash, vomiting or bleeding?"],
            specialty="General Practitioner"),
        "si": dict(
            care=["විවේක ගන්න. වතුර, තැඹිලි වතුර හෝ සුප් වැනි දියර බහුලව පානය කරන්න.", "සැහැල්ලු ඇඳුම් අඳින්න. උෂ්ණත්වය නිතර මනින්න."],
            red=["හුස්ම ගැනීමේ අපහසුව, පපුවේ වේදනාව හෝ ව්‍යාකූල බව", "පළු, විදුරුමස්වලින් ලේ යාම හෝ දරුණු බඩේ කැක්කුම (ඩෙංගු අනතුරු ලකුණු විය හැක)",
                 "මුත්‍රා ඉතා අඩුවීම, නොනවතින වමනය හෝ දැඩි දුර්වලතාවය", "මාස 3ට අඩු ළදරුවෙකුට උණ"],
            see="ශ්‍රී ලංකාවේ දින 2ක් හෝ ඊට වැඩි කාලයක් උණ පවතී නම් වෛද්‍යවරයෙකු හමුවන්න. ඩෙංගු පරීක්ෂාවක් අවශ්‍ය දැයි ඔවුන් තීරණය කරාවි.",
            questions=["උෂ්ණත්වය කොපමණ තිබුණාද?", "ඇඟපත වේදනාව, පළු, වමනය හෝ ලේ යාමක් තිබේද?"],
            specialty="General Practitioner"),
    },
    "sore_throat": {
        "en": dict(
            care=["Drink warm fluids and gargle with warm salt water.", "Rest your voice and avoid smoking or smoke exposure."],
            red=["difficulty swallowing saliva or breathing", "drooling, a muffled voice or swelling in the neck", "high fever that does not settle"],
            see="Most sore throats are viral and improve within a week. Antibiotics only help bacterial infections, which a doctor needs to assess.",
            questions=["Do you have fever, swollen glands or white patches on the tonsils?", "Is it hard to swallow?"],
            specialty="General Practitioner"),
        "si": dict(
            care=["උණුසුම් දියර පානය කරන්න. උණු ලුණු වතුරෙන් කට සෝදන්න.", "කටහඬට විවේක දෙන්න. දුම්පානයෙන් සහ දුමෙන් වළකින්න."],
            red=["කෙළ ගිලීමට හෝ හුස්ම ගැනීමට අපහසු වීම", "කෙළ හැලීම, කටහඬ වෙනස් වීම හෝ බෙල්ල ඉදිමීම", "අඩු නොවන අධික උණ"],
            see="බොහෝ උගුරේ අමාරු වෛරස් නිසා ඇතිවන අතර සතියක් ඇතුළත සුව වෙනවා. ඇන්ටිබයොටික් බලපාන්නේ බැක්ටීරියා ආසාදනවලට පමණයි; එය වෛද්‍යවරයා තීරණය කළ යුතුයි.",
            questions=["උණ, ගෙලේ ගැටිති ඉදිමීම හෝ ටොන්සිල් මත සුදු ලප තිබේද?", "ගිලීමට අපහසුද?"],
            specialty="General Practitioner"),
    },
    "cough": {
        "en": dict(care=["Drink warm fluids and rest.", "Avoid smoke and dust."],
                   red=["breathlessness, chest pain or coughing up blood", "a cough lasting more than 3 weeks", "high fever with a cough"],
                   see="See a doctor if the cough is not improving after a week or you have fever or breathlessness.",
                   questions=["Is the cough dry or with phlegm?", "Do you have fever or wheezing?"], specialty="General Practitioner"),
        "si": dict(care=["උණුසුම් දියර පානය කර විවේක ගන්න.", "දුම සහ දූවිලිවලින් වළකින්න."],
                   red=["හුස්ම හිරවීම, පපුවේ වේදනාව හෝ කැස්සත් සමඟ ලේ", "සති 3කට වඩා පවතින කැස්ස", "කැස්ස සමඟ අධික උණ"],
                   see="සතියකින් පසුවත් කැස්ස අඩු නොවේ නම් හෝ උණ, හුස්ම හිරවීම ඇත්නම් වෛද්‍යවරයෙකු හමුවන්න.",
                   questions=["කැස්ස වියළිද, සෙම සහිතද?", "උණ හෝ හුස්ම හිරවීමක් තිබේද?"], specialty="General Practitioner"),
    },
    "rash": {
        "en": dict(care=["Keep the area clean and dry and avoid scratching.", "Stop any new soap, cream or product that may have caused it."],
                   red=["swelling of the face, lips or tongue, or difficulty breathing", "a rash with fever, or one that is spreading fast or blistering"],
                   see="See a doctor if the rash lasts more than a few days, keeps spreading, or is very itchy or painful.",
                   questions=["Where on the body is the rash and is it spreading?", "Have you started any new medicine or product?"],
                   specialty="Dermatologist"),
        "si": dict(care=["එම ස්ථානය පිරිසිදුව සහ වියළිව තබාගන්න. කසන්න එපා.", "අලුතින් භාවිතා කළ සබන්, ක්‍රීම් වැනි දේ නවත්වන්න."],
                   red=["මුහුණ, තොල් හෝ දිව ඉදිමීම, හුස්ම ගැනීමේ අපහසුව", "උණ සමඟ පළු, ඉක්මනින් පැතිරෙන හෝ බිබිලි සහිත පළු"],
                   see="දින කිහිපයකට වඩා පළු පවතී නම්, පැතිරෙනවා නම්, හෝ දැඩි කැසීම/වේදනාව ඇත්නම් වෛද්‍යවරයෙකු හමුවන්න.",
                   questions=["පළු ඇත්තේ ශරීරයේ කොතැනද, පැතිරෙනවාද?", "අලුත් බෙහෙතක් හෝ නිෂ්පාදනයක් භාවිතා කළාද?"],
                   specialty="Dermatologist"),
    },
    "stomach": {
        "en": dict(care=["Sip oral rehydration solution (Jeewani) or water often.", "Eat light, plain food and avoid oily or spicy meals."],
                   red=["severe or constant abdominal pain", "blood in vomit or stool, or black stools", "signs of dehydration such as very little urine or dizziness"],
                   see="See a doctor if symptoms last more than 2 days, or sooner for children, older adults or pregnant women.",
                   questions=["Do you have vomiting, diarrhoea or fever?", "Where exactly is the pain?"], specialty="General Practitioner"),
        "si": dict(care=["ජීවනී හෝ වතුර නිතර ටිකෙන් ටික බොන්න.", "සැහැල්ලු, සරල ආහාර ගන්න. තෙල් හා සැර කෑම වලින් වළකින්න."],
                   red=["දරුණු හෝ නොනවතින බඩේ කැක්කුම", "වමනයේ හෝ මළපහේ ලේ, කළු පැහැති මළපහ", "මුත්‍රා අඩුවීම, කරකැවිල්ල වැනි විජලනයේ ලක්ෂණ"],
                   see="දින 2කට වඩා රෝග ලක්ෂණ පවතී නම් වෛද්‍යවරයෙකු හමුවන්න. ළමුන්, වැඩිහිටියන් සහ ගර්භනී මව්වරුන් ඊට වඩා ඉක්මනින් හමුවිය යුතුයි.",
                   questions=["වමනය, පාචනය හෝ උණ තිබේද?", "කැක්කුම තියෙන්නේ හරියටම කොතැනද?"], specialty="General Practitioner"),
    },
}
_DEFAULT_GUIDE = {
    "en": dict(care=["Rest, drink enough fluids and keep track of how your symptoms change."],
               red=["chest pain, difficulty breathing, fainting or confusion", "symptoms that get worse quickly"],
               see="If symptoms continue for more than a few days or worry you, see a doctor.",
               questions=["How long have you had these symptoms?", "Are they getting better or worse?"], specialty="General Practitioner"),
    "si": dict(care=["විවේක ගන්න, ප්‍රමාණවත් දියර පානය කරන්න, රෝග ලක්ෂණ වෙනස් වන ආකාරය සටහන් කරගන්න."],
               red=["පපුවේ වේදනාව, හුස්ම ගැනීමේ අපහසුව, ක්ලාන්ත වීම හෝ ව්‍යාකූල බව", "ඉක්මනින් වැඩිවන රෝග ලක්ෂණ"],
               see="රෝග ලක්ෂණ දින කිහිපයකට වඩා පවතී නම් හෝ ඔබට කනස්සල්ලක් ඇත්නම් වෛද්‍යවරයෙකු හමුවන්න.",
               questions=["මෙම රෝග ලක්ෂණ කොපමණ කලක සිට තිබේද?", "ඒවා අඩුවෙනවාද, වැඩිවෙනවාද?"], specialty="General Practitioner"),
}
_LABELS = {
    "en": {"headache": "a headache", "fever": "a fever", "sore_throat": "a sore throat", "cough": "a cough", "cold": "cold symptoms",
           "rash": "a skin rash", "stomach": "stomach symptoms", "back_pain": "back pain", "dizziness": "dizziness", "fatigue": "tiredness"},
    "si": {"headache": "හිසරදය", "fever": "උණ", "sore_throat": "උගුරේ අමාරුව", "cough": "කැස්ස", "cold": "සෙම්ප්‍රතිශ්‍යාව",
           "rash": "සමේ පළු/කැසීම", "stomach": "බඩේ අපහසුතා", "back_pain": "කොන්දේ කැක්කුම", "dizziness": "කරකැවිල්ල", "fatigue": "මහන්සිය"},
}


def _duration_phrase(days: Optional[float], lang: str) -> str:
    if days is None:
        return ""
    if days < 1:
        return " for a few hours" if lang == "en" else " පැය කිහිපයක සිට"
    whole = int(round(days))
    if lang == "si":
        return f" දින {whole}ක සිට"
    return f" for {whole} day{'s' if whole != 1 else ''}"


def build_symptom_advice(text: str, lang: str) -> SymptomAdvice:
    symptoms = detect_symptoms(text)
    days = detect_duration_days(text)
    primary = next((s for s in symptoms if s in _GUIDE), None)
    guide = (_GUIDE[primary] if primary else _DEFAULT_GUIDE)["si" if lang == "si" else "en"]
    labels = _LABELS["si" if lang == "si" else "en"]
    named = ", ".join(labels.get(s, s) for s in symptoms) or ("රෝග ලක්ෂණ" if lang == "si" else "these symptoms")
    duration = _duration_phrase(days, "si" if lang == "si" else "en")

    if lang == "si":
        lines = [f"ඔබට{duration} {named} තිබෙන බව තේරුණා. මෙය සාමාන්‍ය සෞඛ්‍ය තොරතුරු පමණයි, රෝග විනිශ්චයක් නොවෙයි.", "",
                 "**දැන් කළ හැකි දේ:**", *[f"- {c}" for c in guide["care"]], "",
                 "**මේ කිසිවක් ඇත්නම් වහාම 1990 අමතන්න හෝ ETU එකට යන්න:**", *[f"- {r}" for r in guide["red"]], "",
                 f"**වෛද්‍යවරයෙකු හමුවිය යුත්තේ කවදාද:** {guide['see']}"]
        if days is not None and days >= 3:
            lines.append("ඔබේ රෝග ලක්ෂණ දින කිහිපයක සිට පවතින නිසා වෛද්‍යවරයෙකු ලවා පරීක්ෂා කරගැනීම නිර්දේශ කරනවා.")
        lines += ["", "ඖෂධයක් හෝ මාත්‍රාවක් තීරණය කිරීමට ඖෂධවේදියෙකුගෙන් හෝ වෛද්‍යවරයෙකුගෙන් විමසන්න.",
                  "ඔබට ගැළපෙන වෛද්‍යවරයෙකු සොයා දීමට අවශ්‍ය නම් කියන්න."]
    else:
        lines = [f"I understand you've had {named}{duration}. Here is general guidance — it is not a diagnosis.", "",
                 "**What you can do now:**", *[f"- {c}" for c in guide["care"]], "",
                 "**Call 1990 or go to the nearest ETU now if you have:**", *[f"- {r}" for r in guide["red"]], "",
                 f"**When to see a doctor:** {guide['see']}"]
        if days is not None and days >= 3:
            lines.append("Because this has lasted several days, I recommend booking a doctor's assessment.")
        lines += ["", "Please ask a pharmacist or doctor before taking any medicine, so the right product and dose are chosen for you.",
                  "Would you like me to find a suitable doctor for you?"]
    return SymptomAdvice("\n".join(lines), guide.get("specialty"), symptoms, days, list(guide["questions"]))


# ---------------------------------------------------------------------------
# Prescription request handling (BUG-018)
# ---------------------------------------------------------------------------
def prescription_refusal(text: str, lang: str) -> str:
    symptoms = detect_symptoms(text)
    antibiotic = bool(re.search(r"antibiotic|ඇන්ටිබයොටික්", normalize(text)))
    advice = build_symptom_advice(text, lang) if symptoms else None
    if lang == "si":
        parts = [
            "**මට ඖෂධ නියම කිරීමට හෝ ඔබට ගැළපෙන නිශ්චිත මාත්‍රාවක්, ප්‍රතිකාර කාලයක් කියන්න බැහැ.**",
            "ඖෂධයක් නියම කිරීමට පෙර ලියාපදිංචි වෛද්‍යවරයෙකු ඔබව පරීක්ෂා කර, ඔබේ වයස, බර, අසාත්මිකතා, ගර්භනීභාවය සහ වෙනත් ඖෂධ ගැන සලකා බැලිය යුතුයි.",
        ]
        if antibiotic:
            parts.append("උගුරේ අමාරුව සහ උණ බොහෝ විට වෛරස් නිසා ඇතිවන අතර ඇන්ටිබයොටික් එවැනි ආසාදනවලට බලපාන්නේ නැහැ. "
                         "අනවශ්‍ය ලෙස ඇන්ටිබයොටික් ගැනීමෙන් අතුරු ආබාධ, ආසාත්මිකතා සහ ඖෂධ ප්‍රතිරෝධය ඇතිවිය හැකියි.")
    else:
        parts = [
            "**I can't prescribe medicines or give you a personal dose or treatment length.**",
            "A licensed doctor needs to assess you first — your age, weight, allergies, pregnancy, other medicines and the likely cause all change what is safe.",
        ]
        if antibiotic:
            parts.append("Fever with a sore throat is very often caused by a virus, and antibiotics do not work against viruses. "
                         "Taking antibiotics when they aren't needed can cause side effects and allergic reactions, and helps create antibiotic-resistant infections.")
    if advice:
        parts += ["", advice.text]
    else:
        parts.append("Would you like me to find a doctor you can consult?" if lang != "si" else "ඔබට උපදෙස් ගත හැකි වෛද්‍යවරයෙකු සොයා දීමට අවශ්‍යද?")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Multi-topic wellness (BUG-019)
# ---------------------------------------------------------------------------
def combine_wellness(topics: List[str], query: str, lang: str) -> Dict[str, object]:
    from app.agents.wellness_knowledge import WellnessKnowledge

    sections = []
    cards = []
    topic_query = {"sleep": "sleep", "stress": "stress", "hydration": "water daily habits", "diet": "healthy diet", "exercise": "exercise"}
    for topic in topics:
        if topic == "diet":
            result = WellnessKnowledge.get_healthy_food_guidance(topic_query[topic], lang=lang)
        elif topic == "exercise":
            result = WellnessKnowledge.get_exercise_guidance(topic_query[topic], lang=lang)
        else:
            result = WellnessKnowledge.get_wellness_guidance(topic_query[topic], lang=lang)
        card = result.get("card") or {}
        cards.append(card)
        tips = list(card.get("tips") or [])[:3] + list(card.get("sriLankanOptions") or [])[:1]
        title = card.get("title") or topic.title()
        sections.append(f"**{title}**\n" + "\n".join(f"- {tip}" for tip in tips))
    intro = ("ඔබ ඇසූ සෑම මාතෘකාවක් සඳහාම උපදෙස් මෙන්න:" if lang == "si"
             else "Here is guidance for each part of your question:")
    outro = ("මේවා සාමාන්‍ය සුවතා උපදෙස් පමණයි. නිදන්ගත රෝග ඇත්නම් වෛද්‍යවරයෙකුගෙන් විමසන්න." if lang == "si"
             else "These are general wellness tips. If you have a long-term condition, check with your doctor before changing diet or exercise.")
    return {"text": "\n\n".join([intro, *sections, outro]), "card": cards[0] if cards else None, "topics": topics}
