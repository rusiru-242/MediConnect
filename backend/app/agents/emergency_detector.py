"""Deterministic multilingual emergency red-flag detection (BUG-013).

This module is the single source of truth for emergency escalation in the
patient-facing assistants. It deliberately does not depend on any external LLM
so it keeps working when AI providers are slow or unavailable.

Supported input styles:
- English (including conversational phrasing such as "my chest hurts a lot")
- Sinhala script, including common spelling variants (e.g. "පපුව ගොඩක් රිදෙනවා",
  "හුස්ම ගන්නත් අමාරුයි")
- Romanized Sinhala / Singlish (e.g. "mata papuwa godak ridenawa",
  "husma gannath amarui")
- Mixed-language messages

Detection model
---------------
Each emergency category combines a *body/subject* concept with a *distress*
concept inside the same clause (or uses a self-contained phrase such as
"heart attack"). Clauses that are explicitly negated ("no chest pain",
"papuwa ridenne naha") or purely historical ("I had chest pain last year")
are ignored. Purely informational questions ("what are the signs of a stroke?")
without a first/third person report are not escalated.

When uncertain, the detector errs on the side of escalation. These rules are a
software safety net and have NOT been clinically validated; see
docs/SECURITY_AND_CLINICAL_SAFETY_REPORT.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata
from typing import Iterable, List, Optional, Sequence

AMBULANCE_NUMBER = "1990"

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------
_ZW = re.compile("[​‌‍﻿]")


def normalize(text: str) -> str:
    """Lower-case, NFC-normalize, strip zero-width joiners and collapse spaces."""
    text = unicodedata.normalize("NFC", text or "")
    text = _ZW.sub("", text).lower()
    text = text.replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", text).strip()


_CLAUSE_SPLIT = re.compile(r"[.!?;\n]+|\s(?:but|however|namuth|ehet|eth)\s|,\s*(?:but|namuth)\s")


def clauses(text: str) -> List[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(text) if c and c.strip()]


# ---------------------------------------------------------------------------
# Concept vocabularies. Sinhala script terms are matched as substrings because
# Sinhala inflects by suffix (පපුව / පපුවේ / පපුවට ...).
# ---------------------------------------------------------------------------
CHEST = (r"\bchest\b", r"\bpapu(?:wa|we|ve|va|wata|vata|wehi|wen)?\b", r"\bpapuw\w*", r"\blaya\b",
         "පපුව", "පපුවේ", "පපුවට", "ළය")
HEART = (r"\bheart\b", r"\bhrud\w*", r"\bhadawat\w*", r"\bhadawath\w*", "හදවත", "හෘද")
PAIN = (r"\bpain\w*", r"\bhurt\w*", r"\bache\w*", r"\btight\w*", r"\bsqueez\w*", r"\bcrush\w*",
        r"\bheav(?:y|iness)\b", r"\bburning\b", r"\bdiscomfort\b",
        r"\bri(?:d|dd)en\w*", r"\bredenaw\w*", r"\brid(?:u|i)n\w*", r"\bkakku\w*", r"\bkakkum\w*",
        r"\bwedana\w*", r"\bvedana\w*", r"\bhira(?:wenaw\w*|wela|wel\w*)?\b", r"\btada\w*", r"\bthada\w*",
        r"\bamaru\w*",
        "රිදෙ", "රිදුම", "කැක්කුම", "වේදනා", "හිර", "තද", "අමාරු")
BREATH_SUBJECT = (r"\bbreath\w*", r"\bbreathe\w*", r"\bbreathing\b",
                  r"\bhus(?:h)?m\w*", r"\bhusum\w*", r"\bhuss?ma\w*", r"\bsw(?:a|ha)sa\w*",
                  "හුස්ම", "ශ්වසන")
BREATH_DISTRESS = (r"\bdifficult\w*", r"\bshort(?:ness)?\b", r"\bcan'?t\b", r"\bcannot\b", r"\bunable\b",
                   r"\bstruggl\w*", r"\btrouble\b", r"\bhard\b", r"\bgasp\w*", r"\bchok\w*", r"\bsuffocat\w*",
                   r"\bamaru\w*", r"\bbaha\b", r"\bbae\b", r"\bba\b", r"\bhira\w*",
                   r"\bpiruna\w*", r"\bmaduy?i\b", r"\bmadi\b",
                   "අමාරු", "බැහැ", "බෑ", "බැ", "හිර", "මදි")
BREATH_SELF = (r"\bbreathless\w*", r"\bshortness of breath\b", r"\bshort of breath\b", r"\bcan'?t breathe\b",
               r"\bcannot breathe\b", r"\bblue lips\b", r"\bgasping\b", r"\bwheez\w* badly\b",
               "හුස්ම හිර", "හුස්ම ගන්න බැ", "හුස්ම ගන්න අමාරු")
CARDIAC_SELF = (r"\bpressure (?:in|on) (?:my |his |her |the )?chest\b", r"\bchest pressure\b", r"\bheart attack\b", r"\bcardiac arrest\b", r"\bhart attack\b", r"\bheart atack\b",
                r"\bheart eka\s+\w*\s*(?:nawathi|natha|nathi)\b", "හාට් ඇටෑක්", "හෘදයාබාධ")
STROKE_SELF = (r"\bstroke\b", r"\bfacial droop\w*", r"\bface (?:is )?droop\w*", r"\bslurred speech\b",
               r"\bsudden (?:numbness|weakness|paralysis|confusion)\b",
               r"\bone side (?:of (?:my|his|her|the) (?:body|face) )?(?:is )?(?:weak|numb|paraly\w*)\b",
               r"\bcan'?t (?:move|feel) (?:my|his|her) (?:arm|leg|face)\b",
               r"\bam(?:s|sh)abag\w*", r"\bansha?bag\w*", r"\bkata\s+ada\w*", r"\bmuna\s+ada\w*",
               r"\bek(?:a)?\s*paththak\w*\s+pana\s+na\w*",
               "අංශභාග", "අප්‍රාණික", "ආඝාත", "ස්ට්‍රෝක්", "කට ඇද", "මුහුණ ඇද")
UNCONSCIOUS_SELF = (r"\bunconscious\b", r"\bunresponsive\b", r"\bpassed out\b", r"\blost consciousness\b",
                    r"\bloss of consciousness\b", r"\bnot waking up\b", r"\bwon'?t wake up\b", r"\bcollapsed\b",
                    r"\bblacked out\b", r"\bfainted\b",
                    r"\bsihiya\s+nath\w*", r"\bsihi\s*nath\w*", r"\bsihisun\w*", r"\bkalanth\w*\s+(?:wela\s+)?wetun\w*",
                    "සිහිය නැති", "සිහිසුන්", "සිහිය නැත", "කලන්තේ හැදිලා වැටුණා", "ක්ලාන්ත වී වැටුණා")
BLEEDING_SELF = (r"\b(?:heavy|severe|uncontrolled|uncontrollable|non[- ]stop|massive) bleeding\b",
                 r"\bbleeding (?:heavily|a lot|won'?t stop|that won'?t stop|nonstop)\b",
                 r"\bvomit\w* (?:up )?blood\b", r"\bcough\w* (?:up )?blood\b", r"\bblood in (?:my )?vomit\b",
                 r"\ble\s+wamane\w*", r"\ble\s+wamana\w*", r"\bwamane\w*\s+le\b", r"\bkassata\s+le\b",
                 r"\ble\s+(?:godak\s+)?yanaw\w*\s+(?:nawath|nawaththanna)\w*",
                 "ලේ වමනය", "වමනයට ලේ", "කැස්සට ලේ", "අධික ලේ", "නොනවතින ලේ", "ලේ නවතින්නේ නැ")
SEIZURE_SELF = (r"\bseizure\w*\b", r"\bconvuls\w*", r"\bfitting\b", r"\bhaving (?:a )?fits?\b",
                r"\bwalippu\w*", r"\bwali\s+(?:dana|ena|enaw)\w*",
                "වලිප්පු", "වලි දානවා", "වලි එනවා")
ANAPHYLAXIS_SELF = (r"\banaphyla\w*", r"\b(?:throat|tongue|lips?|face) (?:is |are )?swell\w*",
                    r"\bswell\w* (?:of|in) (?:my |the )?(?:throat|tongue|lips?)\b",
                    r"\bsevere allergic reaction\b", "උගුර ඉදිමී", "දිව ඉදිමී")
POISON_SELF = (r"(?<!food )\bpoison\w*", r"\boverdos\w*", r"\btook too many (?:pills|tablets)\b",
               r"\bswallowed (?:bleach|poison|chemical\w*|kerosene|pesticide\w*|pills)\b",
               r"\bdrank (?:bleach|poison|chemical\w*|kerosene|pesticide\w*)\b",
               r"\bwasa\s+(?:biw|biv|bow|bon)\w*", r"\bwas\s+(?:biw|biv)\w*",
               r"\bpethi\s+godak\s+(?:biw|biv|gil)\w*",
               "වස බිව්", "වස බීල", "විෂ ශරීරගත", "විෂ බිව්", "පෙති ගොඩක් බිව්")
SELF_HARM_SELF = (r"\bsuicid\w*", r"\bkill (?:my ?self|myself)\b", r"\bend (?:my|it all|my life)\b",
                  r"\bwant to die\b", r"\bdon'?t want to live\b", r"\bself[- ]?harm\w*", r"\bhurt myself\b",
                  r"\bdiwi\s+nas\w*", r"\bmarenna\s+(?:one|oni|ona|hithenaw\w*)\b", r"\bjiwath\w*\s+wenna\s+(?:one\s+)?na\w*",
                  "දිවි නසා", "සියදිවි", "මැරෙන්න ඕන", "මැරෙන්න හිතෙනවා", "ජීවත් වෙන්න ඕන නැ")
HEAD_SELF = (r"\bworst headache\b", r"\bthunderclap headache\b", r"\bsevere head (?:injury|trauma)\b",
             r"\bhead injury\b.*\b(?:vomit\w*|unconscious|bleeding|confus\w*)\b",
             r"\bsudden severe headache\b")
SNAKE_SELF = (r"\bsnake ?bite\b", r"\bbitten by (?:a )?snake\b", r"\bsnake bit\b",
              r"\b(?:naya|nayek|polonga|thelissa|sarpa\w*)\s+(?:gahuw\w*|kawa\w*|dasht\w*)",
              "සර්ප දෂ්ට", "නයා ගැහුව", "නයෙක් ගැහුව", "පොළඟා ගැහුව", "පොළඟෙක් ගැහුව")

SEVERITY = (r"\bsevere\w*", r"\bbad(?:ly)?\b", r"\ba lot\b", r"\bvery\b", r"\bterribl\w*", r"\bsudden\w*",
            r"\bgodak\b", r"\bgodaak\b", r"\bdaruna\w*", r"\bhodatama\b", r"\bloku\b",
            "ගොඩක්", "දරුණු", "හොඳටම", "හදිසි")

# Negation markers. English negators precede the symptom; Sinhala and Romanized
# Sinhala negators follow the verb (SOV word order).
NEGATION_BEFORE = (r"\bno\b", r"\bnot\b", r"\bnever\b", r"\bwithout\b", r"\bdenies\b", r"\bdon'?t have\b",
                   r"\bdoesn'?t have\b", r"\bdidn'?t have\b", r"\bno longer\b", r"\bfree of\b", r"\bnone\b")
NEGATION_AFTER = re.compile(r"^\S*\s+(?:naha|nehe|nae|na|නැහැ|නෑ|නැ)(?:\b|$|\s)")
MILD_RESPIRATORY = (r"\bmild\w*", r"\bslight\w*", r"\ba (?:little|bit)\b",
                    r"\b(?:after|when|while|during) (?:running|exercis\w*|workouts?|climbing|walking fast|jogging|sports?)\b",
                    r"\bbreathing (?:exercises?|techniques?)\b", r"\bmeditat\w*")
HISTORICAL = (r"\blast (?:year|month|week)\b", r"\byears? ago\b", r"\bmonths? ago\b", r"\bused to\b",
              r"\bin the past\b", r"\bhistory of\b", r"\bprevious(?:ly)?\b", r"\bonce had\b",
              r"\bkalin\b", r"\bgiya\s+(?:awurudde|masa)\b", r"\bawurudu\w*\s+kipay\w*\s+kalin\b",
              "කලින්", "ගිය අවුරුද්දේ", "අවුරුදු කිහිපයකට පෙර")
CURRENT = (r"\bnow\b", r"\btoday\b", r"\bright now\b", r"\bcurrently\b", r"\bagain\b", r"\bstill\b",
           r"\bdan\b", r"\bada\b", r"\bawa\b", "දැන්", "අද", "ආයෙත්")
INFORMATIONAL = (r"\b(?:what|which) (?:are|is) (?:the )?(?:signs?|symptoms?|warning signs?)\b",
                 r"\bsigns? (?:and symptoms )?of (?:a )?(?:heart attack|stroke|anaphylaxis)\b",
                 r"\bhow (?:do|can) (?:i|you) (?:recogni[sz]e|tell|know)\b", r"\bwhat is (?:a )?(?:stroke|heart attack)\b",
                 r"\bexplain\b", r"\blearn about\b", r"\bfirst aid for\b")
PERSONAL = (r"\bi\b", r"\bi'?m\b", r"\bmy\b", r"\bme\b", r"\bmine\b", r"\bhe\b", r"\bshe\b", r"\bhis\b",
            r"\bher\b", r"\bfather\b", r"\bmother\b", r"\bchild\b", r"\bson\b", r"\bdaughter\b", r"\bwife\b",
            r"\bhusband\b", r"\bfriend\b",
            r"\bmata\b", r"\bmage\b", r"\bmama\b", r"\bmaa\b", r"\bapi\b", r"\bthaththa\w*", r"\bamma\w*",
            r"\bduwa\w*", r"\bputha\w*", r"\blamaya\w*", "මට", "මගේ", "මම", "අපේ", "තාත්තා", "අම්මා", "දරුවා")

# Messages that indicate the user is answering an emergency follow-up with an
# explicit resolution. These end context-carried escalation.
RESOLUTION = (r"\b(?:i'?m|i am|feeling) (?:fine|ok(?:ay)?|better) now\b", r"\bit (?:has )?(?:stopped|passed|gone)\b",
              r"\bthat was (?:a )?(?:mistake|test|typo)\b", r"\bjust (?:testing|asking)\b",
              r"\bdan\s+hondai\b", r"\bdan\s+kamak\s+na\w*", "දැන් හොඳයි", "දැන් කමක් නැ")


def _has(text: str, terms: Iterable[str]) -> Optional[str]:
    for term in terms:
        if term.startswith(r"\b") or "\\" in term or "(" in term:
            match = re.search(term, text)
            if match:
                return match.group(0)
        elif term in text:
            return term
    return None


@dataclass
class EmergencyResult:
    is_emergency: bool
    category: Optional[str] = None
    reason: Optional[str] = None
    matched: List[str] = field(default_factory=list)
    from_context: bool = False
    suppressed: Optional[str] = None  # "negated" | "historical" | "informational"


CATEGORY_REASONS = {
    "cardiac": "Possible heart-related emergency (chest pain or pressure)",
    "respiratory": "Severe breathing difficulty",
    "stroke": "Possible stroke signs",
    "unconscious": "Loss of consciousness or collapse",
    "bleeding": "Severe or uncontrolled bleeding",
    "seizure": "Seizure or convulsions",
    "anaphylaxis": "Possible severe allergic reaction",
    "poisoning": "Possible poisoning or overdose",
    "self_harm": "Risk of suicide or self-harm",
    "head": "Severe head injury or sudden severe headache",
    "snakebite": "Snake bite",
}


def _clause_category(clause: str) -> Optional[tuple[str, List[str]]]:
    """Return (category, matched terms) for a single clause, ignoring negation."""
    checks = (
        ("cardiac", CARDIAC_SELF),
        ("stroke", STROKE_SELF),
        ("unconscious", UNCONSCIOUS_SELF),
        ("bleeding", BLEEDING_SELF),
        ("seizure", SEIZURE_SELF),
        ("anaphylaxis", ANAPHYLAXIS_SELF),
        ("poisoning", POISON_SELF),
        ("self_harm", SELF_HARM_SELF),
        ("head", HEAD_SELF),
        ("snakebite", SNAKE_SELF),
        ("respiratory", BREATH_SELF),
    )
    # Chest pain takes priority so combined chest pain + breathlessness is reported as cardiac.
    chest = _has(clause, CHEST) or _has(clause, HEART)
    pain = _has(clause, PAIN)
    if chest and pain and chest != pain:
        return "cardiac", [chest, pain]

    for category, terms in checks:
        hit = _has(clause, terms)
        if hit and not (category == "respiratory" and _has(clause, MILD_RESPIRATORY)):
            return category, [hit]

    breath = _has(clause, BREATH_SUBJECT)
    distress = _has(clause, BREATH_DISTRESS)
    if breath and distress and breath != distress and not _has(clause, MILD_RESPIRATORY):
        return "respiratory", [breath, distress]
    return None


def _is_negated(clause: str, matched: Sequence[str]) -> bool:
    """Negation scoped to the symptom: up to 4 words before, or an SOV negator right after."""
    spans = [m.span() for term in matched for m in [re.search(re.escape(term), clause)] if m]
    if not spans:
        return False
    first = min(start for start, _ in spans)
    last = max(end for _, end in spans)
    before = re.split(r"[,]|\band\b|\bwith\b|\bsaha\b|\bsamaga\b", clause[:first])[-1]
    before = " ".join(before.split()[-4:])
    if _has(before, NEGATION_BEFORE):
        return True
    return bool(NEGATION_AFTER.search(clause[last:last + 14]))


def _evaluate(text: str) -> EmergencyResult:
    norm = normalize(text)
    if not norm:
        return EmergencyResult(False)
    informational = bool(_has(norm, INFORMATIONAL)) and not _has(norm, PERSONAL)
    suppressed = None
    for clause in clauses(norm) or [norm]:
        found = _clause_category(clause)
        if not found:
            continue
        category, matched = found
        if _is_negated(clause, matched):
            suppressed = "negated"
            continue
        if _has(clause, HISTORICAL) and not _has(clause, CURRENT):
            suppressed = "historical"
            continue
        if informational:
            suppressed = "informational"
            continue
        return EmergencyResult(True, category, CATEGORY_REASONS[category], matched)
    return EmergencyResult(False, suppressed=suppressed)


def detect_emergency(text: str, recent_user_messages: Sequence[str] = (),
                     previous_assistant_was_emergency: bool = False) -> EmergencyResult:
    """Detect emergency red flags in the current turn and recent conversation context.

    - The current message is evaluated first.
    - Up to three recent user messages are then combined with the current one so
      symptoms split across turns (e.g. "my chest hurts" then "and I can't breathe
      well") are still escalated.
    - If the previous assistant turn was an emergency alert, a short follow-up such
      as "what should I do?" keeps the escalation unless the user explicitly says
      the problem resolved.
    """
    current = _evaluate(text)
    if current.is_emergency:
        return current
    norm = normalize(text)
    if current.suppressed in {"negated", "historical"}:
        return current
    if _has(norm, RESOLUTION):
        return EmergencyResult(False, suppressed="resolved")
    recent = [m for m in recent_user_messages if m][-3:]
    for earlier in reversed(recent):
        previous = _evaluate(earlier)
        if previous.is_emergency:
            previous.from_context = True
            return previous
    if recent:
        combined = _evaluate(" , ".join([*recent, text]).replace(".", " "))
        if combined.is_emergency:
            combined.from_context = True
            return combined
    if previous_assistant_was_emergency and len(norm) <= 80:
        return EmergencyResult(True, None, "Follow-up to a possible emergency", [], from_context=True)
    return current


def recent_user_texts(session: dict, limit: int = 3, max_age_minutes: int = 60) -> List[str]:
    """Return recent user messages from a session document (oldest first)."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    rows = []
    for message in reversed(session.get("messages") or []):
        if message.get("sender") != "user":
            continue
        stamp = message.get("timestamp")
        if isinstance(stamp, datetime):
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            if stamp < cutoff:
                break
        rows.append(str(message.get("content") or ""))
        if len(rows) >= limit:
            break
    return list(reversed(rows))


def last_assistant_was_emergency(session: dict) -> bool:
    for message in reversed(session.get("messages") or []):
        if message.get("sender") == "assistant":
            metadata = message.get("metadata") or {}
            return bool(metadata.get("isUrgent") and metadata.get("ambulanceCall") == AMBULANCE_NUMBER
                        or metadata.get("type") == "emergency")
    return False


# ---------------------------------------------------------------------------
# Patient-facing emergency guidance
# ---------------------------------------------------------------------------
EMERGENCY_GUIDANCE_EN = (
    "**This may be a medical emergency.**\n\n"
    "- Call **1990** (Suwa Seriya ambulance) now, or go to the nearest hospital Emergency Treatment Unit (ETU).\n"
    "- Do not drive yourself if you feel faint, have chest pain or are short of breath. Ask someone nearby to help.\n"
    "- Stay with the person, keep them still and comfortable, and do not give food or drink.\n"
    "- If the person stops responding or breathing normally, tell the 1990 operator immediately and follow their instructions.\n\n"
    "Do not wait for a routine appointment. I will not continue doctor search or booking until you are safe."
)

EMERGENCY_GUIDANCE_SI = (
    "**මෙය හදිසි වෛද්‍ය තත්ත්වයක් විය හැකියි.**\n\n"
    "- දැන්ම **1990** (සුවසැරිය ගිලන්රථ සේවය) අමතන්න, නැත්නම් ළඟම රෝහලේ හදිසි ප්‍රතිකාර ඒකකයට (ETU) යන්න.\n"
    "- ක්ලාන්ත ගතියක්, පපුවේ වේදනාවක් හෝ හුස්ම ගැනීමේ අපහසුවක් තිබේ නම් තනියම වාහනය පදවන්න එපා. ළඟ සිටින කෙනෙකුගේ උදව් ගන්න.\n"
    "- රෝගියා සමඟ රැඳී සිටින්න, නිශ්චලව සහ සුවපහසුව තබන්න. කෑම බීම දෙන්න එපා.\n"
    "- රෝගියා ප්‍රතිචාර නොදක්වන්නේ නම් හෝ සාමාන්‍ය ලෙස හුස්ම නොගන්නේ නම්, 1990 ක්‍රියාකරුට වහාම කියා ඔවුන්ගේ උපදෙස් පිළිපදින්න.\n\n"
    "සාමාන්‍ය වෛද්‍ය හමුවක් එනතුරු රැඳී නොසිටින්න."
)

SELF_HARM_GUIDANCE_EN = (
    "**I'm really sorry you're going through this. Your safety matters.**\n\n"
    "- If you might act on these thoughts or are in danger now, call **1990** or go to the nearest hospital ETU.\n"
    "- National Mental Health Helpline: **1926** (free, 24 hours).\n"
    "- Sumithrayo emotional support: **011 2 696 666**.\n"
    "- Please tell someone you trust and stay with them right now.\n\n"
    "You don't have to face this alone."
)

SELF_HARM_GUIDANCE_SI = (
    "**ඔබ මේ අත්විඳින දේ ගැන මට ඇත්තටම කනගාටුයි. ඔබේ ආරක්ෂාව ඉතා වැදගත්.**\n\n"
    "- ඔබට දැන් අනතුරක් ඇත්නම් **1990** අමතන්න, නැත්නම් ළඟම රෝහලේ ETU එකට යන්න.\n"
    "- ජාතික මානසික සෞඛ්‍ය උපකාරක අංකය: **1926** (නොමිලේ, පැය 24).\n"
    "- සුමිත්‍රයෝ: **011 2 696 666**.\n"
    "- ඔබ විශ්වාස කරන කෙනෙකුට දැන්ම කියන්න, ඔවුන් සමඟ රැඳී සිටින්න.\n\n"
    "ඔබ මේකට තනියම මුහුණ දෙන්න ඕන නැහැ."
)


def emergency_message(result: EmergencyResult, lang: str) -> str:
    if result.category == "self_harm":
        return SELF_HARM_GUIDANCE_SI if lang == "si" else SELF_HARM_GUIDANCE_EN
    return EMERGENCY_GUIDANCE_SI if lang == "si" else EMERGENCY_GUIDANCE_EN
