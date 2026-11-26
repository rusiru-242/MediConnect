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
                    r"\bloss of consciousness\b", r"\bnot waking up\b", r"\bwon'?t wake up\b", r"\b(?<!lung )(?<!lungs )collaps(?:ed|es|ing)\b",
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
               # "took 10 paracetamol tablets", "swallowed twenty pills", "ate a whole strip of tablets"
               r"\b(?:took|taken|swallowed|ate|had|drank|given)\s+(?:\w+\s+){0,2}?"
               r"(?:[1-9]\d+|ten|eleven|twelve|fifteen|twenty|thirty|many|lots\s+of|a\s+lot\s+of|a\s+(?:whole|full)\s+(?:bottle|strip|pack|packet|box)(?:\s+of)?)"
               r"\s+(?:\w+\s+){0,2}?(?:pills?|tablets?|capsules?|beheth|pethi)\b",
               r"\b(?:swallowed|ate|drank)\s+(?:\w+\s+){0,3}?(?:pills?|tablets?|medicine|medication|beheth)\b.*\b(?:accident\w*|by mistake|mistakenly)\b",
               r"\b(?:accident\w*|by mistake|mistakenly)\b.*\b(?:took|swallowed|ate|drank)\s+(?:\w+\s+){0,3}?(?:[1-9]\d+|many|too many|a lot)\b",
               r"\b(?:child|son|daughter|baby|kid|toddler)\s+(?:\w+\s+){0,2}(?:swallowed|ate|drank)\s+(?:\w+\s+){0,6}(?:pills?|tablets?|capsules?|medicine|bleach|kerosene|poison|chemicals?|batter(?:y|ies))\b",
               # A01-N01: "My child swallowed a whole strip of my blood pressure tablets" was missed because the
               # medicine name put more than two words between the quantity and "tablets".
               r"\b(?:took|taken|swallowed|ate|had|drank|given|gave)\b[^.!?]{0,30}\b(?:whole|full|entire)\s+(?:bottle|strip|pack|packet|box|sheet|card|blister)\b",
               r"\b(?:took|taken|swallowed|ate)\s+all\s+(?:of\s+)?(?:my|his|her|the|their)\s+(?:\w+\s+){0,3}(?:pills?|tablets?|capsules?|medicines?|medication)\b",
               r"\bpethi\s+(?:okkoma|ekapaara|ekathuwak|pathakma|pattiyakma|godakma)\s+(?:biw|biv|gil|kaa|kae|ka)\w*",
               "පෙති ඔක්කොම බිව්", "පෙති පතක්ම", "පෙති ඔක්කොම ගිල",
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
INFORMATIONAL = (r"\b(?:what|which) (?:are|is) (?:the )?(?:\w+ ){0,2}(?:signs?|symptoms?|warning signs?|causes?|risk factors?|"
                 r"treatments?|types?|complications?)\b",
                 r"\b(?:symptoms?|signs?|causes?|risk factors?|treatment|prevention|complications?) (?:of|for) (?:a |an )?\w+",
                 r"\bwhat (?:causes|cause|triggers|leads to|happens (?:in|during))\b", r"\bwhy do (?:people|some people)\b",
                 r"\bhow (?:do|can|to|should) (?:i |you |we |people |one )?(?:prevent|avoid|reduce (?:the )?risk|lower (?:the )?risk)\b",
                 r"\bhow (?:is|are) (?:a |an )?\w+(?: \w+)? (?:diagnosed|treated|prevented)\b", r"\btell me about\b",
                 r"\bwhat (?:does|do) (?:a |an )?\w+(?: \w+)? (?:feel|look) like\b", r"\bis (?:a |an )?\w+(?: \w+)? (?:dangerous|serious|hereditary|curable)\b",
                 r"\bsigns? (?:and symptoms )?of (?:a )?(?:heart attack|stroke|anaphylaxis)\b",
                 r"\bhow (?:do|can) (?:i|you) (?:recogni[sz]e|tell|know)\b", r"\bwhat is (?:a )?(?:stroke|heart attack)\b",
                 r"\bexplain\b", r"\blearn about\b", r"\bfirst aid for\b")
PERSONAL = (r"\bi\b", r"\bi'?m\b", r"\bmy\b", r"\bme\b", r"\bmine\b", r"\bhe\b", r"\bshe\b", r"\bhis\b",
            r"\bher\b", r"\bfather\b", r"\bmother\b", r"\bchild\b", r"\bson\b", r"\bdaughter\b", r"\bwife\b",
            r"\bhusband\b", r"\bfriend\b",
            r"\bmata\b", r"\bmage\b", r"\bmama\b", r"\bmaa\b", r"\bapi\b", r"\bthaththa\w*", r"\bamma\w*",
            r"\bduwa\w*", r"\bputha\w*", r"\blamaya\w*", "මට", "මගේ", "මම", "අපේ", "තාත්තා", "අම්මා", "දරුවා")

# Signs that the writer (or someone with them) is experiencing the problem now. Unlike PERSONAL, a bare
# "I" or "my" in a question ("How can I tell...?", "What should I do if...") does not count.
PERSONAL_EXPERIENCE = (
    r"\bi(?:'?m| am| have| feel| felt| got| think i(?:'?m| am)| keep| can'?t| cannot)\b", r"\bi'?ve (?:got|been|had)\b",
    r"\bmy (?:chest|heart|head|arm|jaw|face|throat|breath\w*|body|left|right|stomach|lips?|tongue|leg)\b",
    r"\b(?:my|our) (?:father|mother|dad|mum|mom|son|daughter|child|baby|wife|husband|friend|brother|sister|"
    r"grand(?:father|mother|pa|ma)|uncle|aunt|neighbou?r|colleague|partner|boss)\b",
    r"\b(?:he|she|they) (?:is|are|has|have|was|can'?t|cannot|collapsed|fainted|fell|stopped)\b",
    r"(?<!if )\bsomeone (?:here|near me|next to me|is|has|just)\b", r"\bright now\b", r"\bat the moment\b",
    r"\bmata\b", r"\bmage\b", r"\bmama\b", r"\bthaththa\w*", r"\bamma\w*", r"\bduwa\w*", r"\bputha\w*",
    "මට", "මගේ", "මම", "තාත්තා", "අම්මා", "දරුවා",
)

# Hypothetical questions ("What should I do if someone has chest pain?").
HYPOTHETICAL = (r"\bif (?:someone|somebody|a person|anyone|a patient|people|a child|you)\b", r"\bwhat if\b",
                r"\bin case (?:of|someone|somebody)\b", r"\bsuppose\b", r"\bhypothetical\w*", r"\bimagine\b")

# Clearly new requests that must not inherit an earlier emergency from conversation context.
NEW_REQUEST = (r"\b(?:find|search|show|book|booking|appointment|channel|recommend|doctor|specialist|"
               r"\w+ologist|dermatolog\w*|cardiolog\w*|hoyala|hoyanna|denna|lkr|rs\.?|budget|medicine|tablet|"
               r"paracetamol|beheth|sleep|diet|exercise|food)\b",
               "වෛද්‍ය", "දොස්තර", "හොයලා", "බෙහෙත්")

# Messages that indicate the user is answering an emergency follow-up with an
# explicit resolution. These end context-carried escalation.
RESOLUTION = (r"\b(?:i'?m|i am|feeling) (?:fine|ok(?:ay)?|better) now\b", r"\bit (?:has )?(?:stopped|passed|gone)\b",
              r"\bthat was (?:a )?(?:mistake|test|typo)\b", r"\bjust (?:testing|asking)\b",
              r"\bdan\s+hondai\b", r"\bdan\s+kamak\s+na\w*", "දැන් හොඳයි", "දැන් කමක් නැ")


INFORMATIONAL_SELF_HARM_SAFE = (r"\b(?:warning )?signs? (?:of|that) (?:suicid\w*|someone)\b", r"\bhow (?:can|do) i help (?:someone|a friend|my)\b",
                                r"\bsuicide prevention\b", r"\bstatistics\b")


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
    suppressed: Optional[str] = None  # "negated" | "historical" | "informational" | "hypothetical" | "resolved"


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
    experiencing = _has(norm, PERSONAL_EXPERIENCE)
    informational = bool(_has(norm, INFORMATIONAL)) and not experiencing
    hypothetical = bool(_has(norm, HYPOTHETICAL)) and not experiencing and not _has(norm, CURRENT)
    suppressed = None
    suppressed_category = None
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
        if category == "self_harm" and (informational or hypothetical) and not _has(norm, INFORMATIONAL_SELF_HARM_SAFE):
            # Questions that mention suicide are never treated as purely educational unless clearly about
            # third-party facts ("what are the warning signs of suicide"); err on the side of support.
            return EmergencyResult(True, category, CATEGORY_REASONS[category], matched)
        if informational or hypothetical:
            suppressed = "informational" if informational else "hypothetical"
            suppressed_category = category
            continue
        return EmergencyResult(True, category, CATEGORY_REASONS[category], matched)
    return EmergencyResult(False, category=suppressed_category, suppressed=suppressed)


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
    # Context only carries into a short follow-up ("what should I do?") or a message that itself has a
    # symptom/distress signal. A clearly new request (doctor search, booking, medicine, wellness) is not
    # re-escalated because of an earlier message.
    symptom_signal = bool(_has(norm, CHEST) or _has(norm, HEART) or _has(norm, PAIN)
                          or _has(norm, BREATH_SUBJECT) or _has(norm, SEVERITY))
    short_follow_up = len(norm) <= 80 and not _has(norm, NEW_REQUEST)
    if not (symptom_signal or short_follow_up):
        return current
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
    if previous_assistant_was_emergency and short_follow_up:
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
#
# Phase 01: guidance is category-specific (BUG-044) instead of one cardiac-style text for every emergency,
# self-harm gets a dedicated supportive response, and informational questions get conditional guidance.
# CONTENT STATUS: PENDING CLINICAL REVIEW. Every statement below must be approved by a qualified clinician
# before real-patient use. Phone numbers were checked on 2026-11-25:
#   1990 - 1990 Suwa Seriya free ambulance (official site 1990.lk)
#   1926 - National Mental Health Helpline, National Institute of Mental Health (NIMH annual report; 24 hours)
#   1333 - CCCline crisis support, CCC Foundation (Lifeline International member; 24/7, toll free, si/ta/en)
# The previously shown Sumithrayo number "011 2 696 666" could not be verified and was removed.
# ---------------------------------------------------------------------------
MENTAL_HEALTH_LINES = (
    {"number": "1926", "name": "National Mental Health Helpline (NIMH)", "hours": "24 hours"},
    {"number": "1333", "name": "CCCline crisis support", "hours": "24 hours"},
)

_CALL_EN = "Call **1990** (Suwa Seriya ambulance) now, or go to the nearest hospital Emergency Treatment Unit (ETU)."
_CALL_SI = "දැන්ම **1990** (සුවසැරිය ගිලන්රථ සේවය) අමතන්න, නැත්නම් ළඟම රෝහලේ හදිසි ප්‍රතිකාර ඒකකයට (ETU) යන්න."
_CLOSE_EN = ("\n\nDo not wait for a routine appointment. I will not continue doctor search or booking until you are safe. "
             "This is general first-aid information, not a diagnosis.")
_CLOSE_SI = "\n\nසාමාන්‍ය වෛද්‍ය හමුවක් එනතුරු රැඳී නොසිටින්න. මෙය සාමාන්‍ය ප්‍රථමාධාර තොරතුරක් මිස රෝග විනිශ්චයක් නොවේ."

CATEGORY_GUIDANCE_EN = {
    "cardiac": ["Stop what you are doing and sit or lie in the position that is most comfortable.",
                "Do not drive yourself. Ask someone nearby to stay with you.",
                "If the person stops responding or is not breathing normally, tell the 1990 operator — they will guide you."],
    "respiratory": ["Sit upright and loosen tight clothing. Do not lie flat.",
                    "If you have your own prescribed reliever inhaler, use it as your doctor instructed.",
                    "Do not walk or exert yourself. Ask someone to stay with you."],
    "stroke": ["Note the time the symptoms started — the hospital will need it.",
               "Check FAST: Face drooping, Arm weakness, Speech difficulty — Time to call 1990.",
               "Do not give food, drink or medicines."],
    "unconscious": ["Check whether the person is breathing normally.",
                    "If they are breathing, turn them on their side (recovery position) and stay with them.",
                    "If they are not breathing normally, tell the 1990 operator immediately — they will guide you through CPR.",
                    "Do not give anything by mouth."],
    "bleeding": ["Press firmly on the wound with a clean cloth and keep pressing.",
                 "If blood soaks through, add more cloth on top — do not remove the first one.",
                 "Lie the person down if they feel faint."],
    "seizure": ["Move hard or sharp objects away and cushion the head.",
                "Do not hold the person down and do not put anything in their mouth.",
                "When the shaking stops, turn them on their side and stay with them. Note how long the seizure lasted."],
    "anaphylaxis": ["If an adrenaline auto-injector has been prescribed, use it now as instructed.",
                    "Sit up if breathing is difficult; otherwise lie down with the legs raised.",
                    "Stay with the person — symptoms can return."],
    "poisoning": ["Go now even if you feel well — some overdoses (for example paracetamol) cause no symptoms at first.",
                  "Do not try to make the person vomit.",
                  "Take the medicine or chemical container with you, and note the amount and the time it was taken."],
    "head": ["Keep the person still. If they fell or were in an accident, do not move their neck.",
             "Do not give food or drink.",
             "Watch for vomiting, confusion, drowsiness or a worsening headache and tell the 1990 operator."],
    "snakebite": ["Keep the person calm and still, and keep the bitten limb still.",
                  "Remove rings, watches or tight items near the bite.",
                  "Do not cut, suck or tie the wound, and do not use herbal remedies — go to a hospital now.",
                  "Do not try to catch the snake; note its appearance only if it is safe."],
}
CATEGORY_GUIDANCE_SI = {
    "cardiac": ["කරන දේ නවත්වා වඩාත් පහසු ඉරියව්වෙන් වාඩි වන්න හෝ වැතිරෙන්න.",
                "තනියම වාහනය පදවන්න එපා. ළඟ සිටින කෙනෙකුට ඔබ සමඟ රැඳී සිටින්න කියන්න.",
                "රෝගියා ප්‍රතිචාර නොදක්වන්නේ නම් හෝ සාමාන්‍ය ලෙස හුස්ම නොගන්නේ නම් 1990 ක්‍රියාකරුට කියන්න — ඔවුන් ඔබට මඟ පෙන්වයි."],
    "respiratory": ["කෙළින් වාඩි වී තද ඇඳුම් ලිහිල් කරන්න. පැතලිව වැතිරෙන්න එපා.",
                    "ඔබට නියම කළ ඉන්හේලරයක් ඇත්නම් වෛද්‍ය උපදෙස් පරිදි භාවිතා කරන්න.",
                    "ඇවිදීම හෝ වෙහෙසීම නොකරන්න. කෙනෙකුට ඔබ සමඟ සිටින්න කියන්න."],
    "stroke": ["රෝග ලක්ෂණ ආරම්භ වූ වේලාව සටහන් කරගන්න — රෝහලට එය අවශ්‍යයි.",
               "මුහුණ ඇද වීම, අතක දුර්වලතාව, කතා කිරීමේ අපහසුව ඇත්දැයි බලන්න — වහාම 1990 අමතන්න.",
               "කෑම, බීම හෝ බෙහෙත් දෙන්න එපා."],
    "unconscious": ["රෝගියා සාමාන්‍ය ලෙස හුස්ම ගන්නවාදැයි බලන්න.",
                    "හුස්ම ගන්නේ නම් ඇලයට හරවා (recovery position) ඔවුන් සමඟ රැඳී සිටින්න.",
                    "සාමාන්‍ය ලෙස හුස්ම නොගන්නේ නම් වහාම 1990 ක්‍රියාකරුට කියන්න — CPR සඳහා ඔවුන් මඟ පෙන්වයි.",
                    "මුඛයෙන් කිසිවක් දෙන්න එපා."],
    "bleeding": ["පිරිසිදු රෙද්දකින් තුවාලය මත තදින් තද කර දිගටම තබන්න.",
                 "ලේ රෙද්ද හරහා පෙඟේ නම් පළමු රෙද්ද ඉවත් නොකර තවත් රෙදි උඩින් තබන්න.",
                 "ක්ලාන්ත ගතියක් ඇත්නම් රෝගියා වැතිරවන්න."],
    "seizure": ["තද හෝ තියුණු දේවල් ඈත් කර හිසට මෘදු දෙයක් තබන්න.",
                "රෝගියා තදින් අල්ලා ගන්න එපා, කටට කිසිවක් දමන්න එපා.",
                "වලිප්පුව නැවතුණු පසු ඇලයට හරවා ඔවුන් සමඟ රැඳී සිටින්න. එය පැවති කාලය සටහන් කරන්න."],
    "anaphylaxis": ["ඇඩ්‍රිනලින් auto-injector එකක් නියම කර ඇත්නම් උපදෙස් පරිදි දැන්ම භාවිතා කරන්න.",
                    "හුස්ම ගැනීම අපහසු නම් වාඩි වන්න; නැතිනම් කකුල් උස් කර වැතිරෙන්න.",
                    "රෝගියා සමඟ රැඳී සිටින්න — රෝග ලක්ෂණ නැවත ඇති විය හැකියි."],
    "poisoning": ["දැන් හොඳින් දැනුණත් වහාම යන්න — සමහර අධි මාත්‍රා (උදා: පැරසිටමෝල්) මුලින් රෝග ලක්ෂණ නොපෙන්වයි.",
                  "රෝගියාට වමනය කරවීමට උත්සාහ කරන්න එපා.",
                  "බෙහෙත් හෝ රසායන ද්‍රව්‍යයේ බහාලුම රැගෙන යන්න, ගත් ප්‍රමාණය සහ වේලාව සටහන් කරන්න."],
    "head": ["රෝගියා නිශ්චලව තබන්න. වැටීමක් හෝ අනතුරක් නම් බෙල්ල හොලවන්න එපා.",
             "කෑම බීම දෙන්න එපා.",
             "වමනය, ව්‍යාකූලත්වය, නිදිමත හෝ හිසරදය වැඩිවීම ගැන 1990 ක්‍රියාකරුට කියන්න."],
    "snakebite": ["රෝගියා සන්සුන්ව සහ නිශ්චලව තබන්න, දෂ්ට කළ අත හෝ පාද නොසොල්වා තබන්න.",
                  "දෂ්ට කළ ස්ථානය අසල මුදු, ඔරලෝසු හෝ තද දේවල් ඉවත් කරන්න.",
                  "තුවාලය කපන්න, උරන්න, බඳින්න එපා; දේශීය බෙහෙත් භාවිතා නොකර වහාම රෝහලට යන්න.",
                  "සර්පයා අල්ලන්න උත්සාහ කරන්න එපා; ආරක්ෂිත නම් පමණක් එහි පෙනුම සටහන් කරන්න."],
}
_GENERIC_EN = ["Do not drive yourself if you feel faint, have chest pain or are short of breath. Ask someone nearby to help.",
               "Stay with the person, keep them still and comfortable, and do not give food or drink.",
               "If the person stops responding or breathing normally, tell the 1990 operator immediately and follow their instructions."]
_GENERIC_SI = ["ක්ලාන්ත ගතියක්, පපුවේ වේදනාවක් හෝ හුස්ම ගැනීමේ අපහසුවක් තිබේ නම් තනියම වාහනය පදවන්න එපා. ළඟ සිටින කෙනෙකුගේ උදව් ගන්න.",
               "රෝගියා සමඟ රැඳී සිටින්න, නිශ්චලව සහ සුවපහසුව තබන්න. කෑම බීම දෙන්න එපා.",
               "රෝගියා ප්‍රතිචාර නොදක්වන්නේ නම් හෝ සාමාන්‍ය ලෙස හුස්ම නොගන්නේ නම්, 1990 ක්‍රියාකරුට වහාම කියා ඔවුන්ගේ උපදෙස් පිළිපදින්න."]

# Kept for callers that import the generic text.
EMERGENCY_GUIDANCE_EN = ("**This may be a medical emergency.**\n\n" + "\n".join(f"- {line}" for line in [_CALL_EN, *_GENERIC_EN])
                         + _CLOSE_EN)
EMERGENCY_GUIDANCE_SI = ("**මෙය හදිසි වෛද්‍ය තත්ත්වයක් විය හැකියි.**\n\n" + "\n".join(f"- {line}" for line in [_CALL_SI, *_GENERIC_SI])
                         + _CLOSE_SI)

# Dedicated mental-health crisis response (Phase 01). Supportive, asks about immediate safety, gives verified
# lines, and keeps 1990/ETU for immediate danger. It never claims the assistant can resolve a crisis.
SELF_HARM_GUIDANCE_EN = (
    "**I'm really glad you told me. What you're feeling matters, and you deserve support right now.**\n\n"
    "I'm an automated assistant, so I can't give you the care a person can — but you don't have to go through this alone.\n\n"
    "**Are you safe right now?** If you might act on these thoughts soon, or you have already hurt yourself or taken something, "
    "call **1990** or go to the nearest hospital ETU now.\n\n"
    "**Right now, please:**\n"
    "- Reach out to someone you trust and ask them to stay with you. Try not to be alone.\n"
    "- If it is safe to do so, move away from anything you could use to hurt yourself (such as medicines, poisons or sharp objects), "
    "or ask someone to keep them for you.\n\n"
    "**Free, confidential support (24 hours):**\n"
    "- National Mental Health Helpline: **1926**\n"
    "- CCCline crisis support: **1333** (Sinhala, Tamil and English)\n\n"
    "If you'd like, tell me whether you are safe right now."
)
SELF_HARM_GUIDANCE_SI = (
    "**ඔබ මට මේ ගැන කීම ගැන මම ඇත්තටම සතුටුයි. ඔබට දැනෙන දේ වැදගත්, ඔබට දැන්ම සහාය ලැබිය යුතුයි.**\n\n"
    "මම ස්වයංක්‍රීය සහායකයෙක් නිසා මිනිසෙකුට දිය හැකි රැකවරණය මට දිය නොහැකියි — නමුත් ඔබ මෙයට තනියම මුහුණ දිය යුතු නැහැ.\n\n"
    "**ඔබ දැන් ආරක්ෂිතද?** ඔබ ඉක්මනින් මේ සිතුවිලි අනුව ක්‍රියා කිරීමට ඉඩ ඇත්නම්, නැත්නම් ඔබ දැනටමත් ඔබටම හානි කරගෙන හෝ යමක් ගෙන ඇත්නම්, "
    "දැන්ම **1990** අමතන්න හෝ ළඟම රෝහලේ ETU එකට යන්න.\n\n"
    "**දැන්ම කරුණාකර:**\n"
    "- ඔබ විශ්වාස කරන කෙනෙකුට කතා කර ඔබ සමඟ රැඳී සිටින්න කියන්න. තනියම නොසිටීමට උත්සාහ කරන්න.\n"
    "- එසේ කිරීම ආරක්ෂිත නම්, ඔබට හානි කරගත හැකි දේවල්වලින් (බෙහෙත්, විෂ, තියුණු දේවල්) ඈත් වන්න, නැත්නම් ඒවා තබාගන්න කෙනෙකුට දෙන්න.\n\n"
    "**නොමිලේ, රහසිගත සහාය (පැය 24):**\n"
    "- ජාතික මානසික සෞඛ්‍ය උපකාරක අංකය: **1926**\n"
    "- CCCline අර්බුද සහාය: **1333** (සිංහල, දෙමළ, ඉංග්‍රීසි)\n\n"
    "ඔබ කැමති නම්, ඔබ දැන් ආරක්ෂිතදැයි මට කියන්න."
)

# Conditional guidance for educational or hypothetical questions about an emergency condition. The question is
# answered as information, with a clear "if this is happening now" escalation instead of an alarm banner.
INFORMATION_TOPICS_EN = {
    "cardiac": ("**Common warning signs of a heart attack** can include chest pain, pressure or tightness; pain spreading to "
                "the arm, neck, jaw or back; shortness of breath; sweating; nausea; or light-headedness. Symptoms can be "
                "milder or unusual in women, older people and people with diabetes."),
    "stroke": ("**A stroke** happens when blood flow to part of the brain is blocked (most often by a clot) or a blood vessel "
               "bursts. Risk factors include high blood pressure, diabetes, smoking, high cholesterol and heart rhythm problems. "
               "Warning signs follow FAST: Face drooping, Arm weakness, Speech difficulty — Time to call 1990."),
    "respiratory": ("**Breathing difficulty** has many causes, such as asthma, infections, heart problems or allergic reactions. "
                    "Danger signs include struggling to speak, blue or grey lips, or confusion."),
}
_INFO_GENERIC_EN = "Here is general information about this topic. A doctor can explain how it applies to you."
_INFO_ESCALATION_EN = ("**If you or someone near you has these symptoms now, call 1990 or go to the nearest ETU immediately** — "
                       "do not wait for an appointment.")
INFORMATION_TOPICS_SI = {
    "cardiac": ("**හෘදයාබාධයක සාමාන්‍ය අනතුරු ඇඟවීම්** ලෙස පපුවේ වේදනාව, තදගතිය හෝ පීඩනය; අත, බෙල්ල, හකු හෝ පිටට පැතිරෙන වේදනාව; "
                "හුස්ම හිරවීම; දහඩිය දැමීම; ඔක්කාරය හෝ ක්ලාන්තය ඇතුළත් විය හැකියි."),
    "stroke": ("**ආඝාතයක්** ඇති වන්නේ මොළයේ කොටසකට රුධිරය ගලායාම අවහිර වූ විට හෝ රුධිර නාලයක් පිපිරුණු විටයි. "
               "අධි රුධිර පීඩනය, දියවැඩියාව, දුම්පානය අවදානම වැඩි කරයි. මුහුණ ඇද වීම, අතක දුර්වලතාව, කතා කිරීමේ අපහසුව අනතුරු ඇඟවීම් වේ."),
}
_INFO_GENERIC_SI = "මෙය මෙම මාතෘකාව පිළිබඳ සාමාන්‍ය තොරතුරකි. එය ඔබට අදාළ වන්නේ කෙසේදැයි වෛද්‍යවරයෙකුට පැහැදිලි කළ හැකියි."
_INFO_ESCALATION_SI = "**ඔබට හෝ ඔබ අසල කෙනෙකුට දැන් මෙම රෝග ලක්ෂණ ඇත්නම් වහාම 1990 අමතන්න හෝ ළඟම ETU එකට යන්න.**"


def emergency_message(result: EmergencyResult, lang: str) -> str:
    if result.category == "self_harm":
        return SELF_HARM_GUIDANCE_SI if lang == "si" else SELF_HARM_GUIDANCE_EN
    si = lang == "si"
    specific = (CATEGORY_GUIDANCE_SI if si else CATEGORY_GUIDANCE_EN).get(result.category or "")
    lines = [_CALL_SI if si else _CALL_EN, *(specific or (_GENERIC_SI if si else _GENERIC_EN))]
    title = "**මෙය හදිසි වෛද්‍ය තත්ත්වයක් විය හැකියි.**" if si else "**This may be a medical emergency.**"
    reason = CATEGORY_REASONS.get(result.category or "")
    lead = f"{title}\n\n" if si or not reason else f"{title} ({reason})\n\n"
    return lead + "\n".join(f"- {line}" for line in lines) + (_CLOSE_SI if si else _CLOSE_EN)


def informational_message(result: EmergencyResult, lang: str) -> str:
    """Answer an educational or hypothetical question about an emergency condition with conditional guidance."""
    si = lang == "si"
    topic = (INFORMATION_TOPICS_SI if si else INFORMATION_TOPICS_EN).get(result.category or "")
    body = topic or (_INFO_GENERIC_SI if si else _INFO_GENERIC_EN)
    escalation = _INFO_ESCALATION_SI if si else _INFO_ESCALATION_EN
    note = ("මෙය සාමාන්‍ය අධ්‍යාපනික තොරතුරකි; රෝග විනිශ්චයක් නොවේ." if si else
            "This is general educational information, not a diagnosis.")
    return f"{body}\n\n{escalation}\n\n{note}"


def crisis_metadata(result: EmergencyResult) -> dict:
    """Extra structured fields the app uses to show the right emergency experience."""
    if result.category == "self_harm":
        return {"crisisType": "mental_health", "supportLines": [dict(line) for line in MENTAL_HEALTH_LINES]}
    return {"crisisType": "medical"}
