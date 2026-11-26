"""Role-specific intent classification shared by the patient, doctor and admin assistants (Phase 05, component 33).

Design (extends the Phase 01 bounded proposal layer):

1. Emergency detection always runs first in the patient flow (booking_agent); nothing here replaces it.
2. A deterministic multilingual classifier maps a message to one intent from the caller's role schema. It covers
   English, Sinhala script, Romanized Sinhala and basic Tamil keywords, and paraphrases ("Are any messages failing
   to reach users?" -> notification_failures), not only exact phrases.
3. When the deterministic classifier finds nothing and an LLM provider is configured and healthy, the provider may
   *propose* an intent. The proposal must be one of the role's intents (pydantic Literal); anything else is
   discarded. The provider never sees tokens, account data or tool output, and its proposal cannot execute
   anything: the assistant still runs only the read-only tool mapped to that intent, under the user's own role.
4. Two different intents in one message (for example "refunds and support tickets") return ``ambiguous`` with
   the candidates, so the assistant asks which one the user means instead of guessing.

Facts in replies always come from tools (database); this module only decides which tool to call.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

SINHALA = re.compile(r"[඀-෿]")
TAMIL = re.compile(r"[஀-௿]")
ROMANIZED_SINHALA = re.compile(
    r"\b(?:mage|mata|mama|oya|keeyada|kiyada|kiyak|keeyak|thiyenawada|thiyenawa|karanna|monawada|mokakda|hoyala|"
    r"denna|walin|heta|ada|sathiye|sathiya|mase|masaye|innawada|gewim|beheth|bonna|welawa|dawase|aduwen|"
    r"pariksha|nathi|wenas|ona|one)\b")


def detect_language(text: str) -> str:
    if SINHALA.search(text or ""):
        return "si"
    if TAMIL.search(text or ""):
        return "ta"
    if ROMANIZED_SINHALA.search((text or "").casefold()):
        return "si-Latn"
    return "en"


# (intent, patterns). Order is priority: specific intents come before broad ones.
ADMIN_INTENTS: Sequence[Tuple[str, str]] = (
    ("notification_failures",
     r"notification\w*\s+(?:fail|error|problem|issue)|dead[- ]?letter|(?:fail|failing|failed|undelivered)\w*\s+"
     r"(?:notification|message|email|sms|push)|(?:message|email|sms|push|notification)s?\b.{0,30}\b(?:fail|"
     r"not\s+(?:reach|deliver|sent)|bounc)|failing to reach|delivery (?:fail|problem)|"
     r"දැනුම්දීම්.{0,20}(?:අසාර්ථක|දෝෂ)|notification.{0,12}(?:wada nathi|fail wela)|அறிவிப்பு.{0,15}தோல்வி"),
    ("fraud_explanation",
     r"fraud|suspicious|risk (?:score|assessment|flag)|why .{0,30}(?:flag|assessment)|වංචා|සැක සහිත|மோசடி"),
    ("system_health",
     r"system\s+(?:health|status|healthy|up|down|ok|working)|platform\s+(?:health|status)|is the (?:system|platform|"
     r"backend|api)|health check|uptime|background worker|workers? (?:status|running|alive)|ai provider|"
     r"පද්ධතිය|system eka|healthy da|வேலை செய்கிறதா"),
    ("pending_doctor_verifications",
     r"(?:pending|awaiting|waiting|unreviewed|outstanding)\b.{0,25}\b(?:doctor|verification|application|"
     r"registration)|doctor\w*\s+(?:verification|application|registration)s?|verification (?:backlog|queue|"
     r"request)|(?:doctor\w*|applications?)\b.{0,40}\b(?:approve|approval|review)|approve karanna|"
     r"වෛද්‍ය.{0,25}(?:අනුමත|ඉල්ලුම්|සත්‍යාපන|ලියාපදිංචි)|மருத்துவர்.{0,20}(?:சரிபார்ப்பு|விண்ணப்ப)"),
    ("payment_reconciliation",
     r"reconcil|discrepanc|mismatch|unmatched|paid but (?:not|un)\w*|stripe (?:vs|and) (?:database|mongo)|"
     r"ගැළපීම|ගැලපීම"),
    ("failed_payments",
     r"(?:failed|declined|unsuccessful|rejected)\s+(?:card\s+)?payments?|payments?\s+(?:that\s+)?(?:failed|"
     r"declined)|අසාර්ථක ගෙවීම්|gewim fail"),
    ("refunds_attention",
     r"refund|money back|reimburs|මුදල් ආපසු|ආපසු ගෙවීම්|பணம் திரும்ப"),
    ("payment_summary",
     r"(?:successful|succeeded|completed|captured|paid)\s+payments?|payments?\s+(?:were\s+)?(?:recorded|"
     r"received|made|captured|count|total)|how many payments|payment (?:count|summary|success)|success rate|"
     r"සාර්ථක ගෙවීම්|ගෙවීම් කීය|gewim (?:keeyada|kiyada|kiyak)|வெற்றிகரமான பணம்"),
    ("revenue",
     r"revenue|gross|income|collections?|net collect|earnings|ආදායම|வருமானம்"),
    ("support_tickets",
     r"support|tickets?|complain|help ?desk|උපකාරක|පැමිණිලි|ஆதரவு"),
    ("booking_analytics",
     r"bookings?|appointments?|analytics|conversion|cancellations?|හමුවීම්|වෙන්කිරීම්|சந்திப்பு"),
)

DOCTOR_INTENTS: Sequence[Tuple[str, str]] = (
    ("renewal_queue",
     r"renewal|refill|renew|repeat prescription|prescription request|අලුත් කිරීම|புதுப்பித்தல்"),
    ("follow_up_create",
     r"(?:set|create|schedule|book)\b.{0,20}follow[- ]?up|follow[- ]?up\b.{0,20}\b(?:karanna|set)"),
    ("consultation_preparation",
     r"prepar|consultation summary|brief me|patient summary|before (?:the|my) (?:next )?consult|"
     r"සාකච්ඡාවට සූදානම්"),
    ("analytics",
     r"how many|count|total|completed (?:consultations|visits)|statistics|stats|analytics|performance|"
     r"කීයද|කීයක්|keeyada|kiyada|kiyak"),
    ("follow_ups",
     r"follow[- ]?ups?|needs? (?:a )?(?:follow|review)|check[- ]?back|පසු විපරම|பின்தொடர்"),
    ("next_patient",
     r"next patient|who is next|ilaga patient|ඊළඟ රෝගියා"),
    ("queue",
     r"queue|waiting (?:room|patients|list)|checked[- ]in"),
    ("free_slots",
     r"free slots?|available slots?|open slots?|free time|nidahas|availability"),
    ("schedule",
     r"appointments?|schedule|bookings?|today|tomorrow|heta|ada|හෙට|අද|நாளை|இன்று"),
)

PATIENT_INTENTS: Sequence[Tuple[str, str]] = (
    # B16: a change to a clinician-approved medicine or dose is never made by the assistant.
    ("medication_change_request",
     r"(?:change|increase|reduce|decrease|lower|raise|double|halve|adjust|stop|skip)\b.{0,25}\b(?:my\s+)?"
     r"(?:dose|dosage|medicine|medication|tablets?|pills?)|(?:dose|dosage)\b.{0,20}\b(?:change|increase|reduce|"
     r"double)|(?:take|use)\s+(?:two|2|three|3|more|extra|double)\s+(?:tablets?|pills?|doses?)\s+instead|"
     r"dose eka (?:wenas|adu|wadi)|beheth (?:nawattanna|wenas)|මාත්‍රාව.{0,15}(?:වෙනස්|වැඩි|අඩු)|"
     r"அளவை.{0,10}மாற்ற"),
    ("medication_schedule",
     r"when (?:should|do|can|must) i take|what time .{0,30}(?:medicine|medication|tablet|pill)|"
     r"(?:my|prescribed)\s+(?:medicine|medication)s?\s+(?:schedule|times?|timetable)|medicine schedule|"
     r"medication schedule|beheth (?:bonna|ganna) (?:one )?welawa|බෙහෙත් බොන්න ඕනේ වෙලාව|மருந்து எப்போது"),
    ("medical_tests",
     r"(?:medical|lab|laboratory|blood|urine|scheduled|upcoming)\s+tests?|tests? (?:scheduled|due|coming)|"
     r"investigations?|pariksha|පරීක්ෂණ|பரிசோதனை"),
    ("appointments",
     r"(?:next|upcoming|my)\s+appointments?|when is my appointment|ඊළඟ හමුව|mage appointment"),
)

ROLE_INTENTS: Dict[str, Sequence[Tuple[str, str]]] = {
    "ADMIN": ADMIN_INTENTS, "DOCTOR": DOCTOR_INTENTS, "PATIENT": PATIENT_INTENTS,
}
# Intents that may share a message without making it ambiguous (the first one wins).
COMPATIBLE = {
    frozenset({"payment_summary", "revenue"}), frozenset({"payment_summary", "booking_analytics"}),
    frozenset({"failed_payments", "payment_summary"}), frozenset({"refunds_attention", "payment_summary"}),
    frozenset({"payment_reconciliation", "failed_payments"}), frozenset({"booking_analytics", "revenue"}),
    frozenset({"pending_doctor_verifications", "booking_analytics"}),
    frozenset({"analytics", "schedule"}), frozenset({"follow_ups", "schedule"}), frozenset({"queue", "schedule"}),
    frozenset({"next_patient", "consultation_preparation"}), frozenset({"next_patient", "queue"}),
    frozenset({"consultation_preparation", "schedule"}), frozenset({"free_slots", "schedule"}),
    frozenset({"renewal_queue", "schedule"}), frozenset({"follow_up_create", "follow_ups"}),
    frozenset({"follow_up_create", "schedule"}), frozenset({"consultation_preparation", "queue"}),
    frozenset({"medication_change_request", "medication_schedule"}), frozenset({"medical_tests", "appointments"}),
    frozenset({"notification_failures", "failed_payments"}), frozenset({"system_health", "notification_failures"}),
    frozenset({"fraud_explanation", "failed_payments"}), frozenset({"analytics", "follow_ups"}),
    frozenset({"refunds_attention", "booking_analytics"}),
}

TIMEFRAMES = (
    ("today", r"\btoday\b|\bada\b|අද|இன்று"),
    ("last_7_days", r"\bweek\b|7 days|\bsathiy[ae]\b|සතිය|සතියේ|வாரம்"),
    ("last_30_days", r"\bmonth\b|30 days|\bmas[ae]\b|මාසය|මාසයේ|மாதம்"),
)


@dataclass
class IntentResult:
    intent: str                      # one of the role's intents, "ambiguous" or "unknown"
    role: str
    language: str
    source: str = "deterministic"    # deterministic | llm_proposal | provider_unavailable
    candidates: List[str] = field(default_factory=list)
    timeframe: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        return {"intent": self.intent, "language": self.language, "source": self.source,
                "candidates": self.candidates, "timeframe": self.timeframe}


def _matches(role: str, text: str) -> List[str]:
    folded = (text or "").casefold()
    return [intent for intent, pattern in ROLE_INTENTS.get(role, ()) if re.search(pattern, folded)]


def timeframe_of(text: str, default: Optional[str] = None) -> Optional[str]:
    folded = (text or "").casefold()
    return next((name for name, pattern in TIMEFRAMES if re.search(pattern, folded)), default)


def classify(role: str, text: str, provider=None) -> IntentResult:
    """Classify ``text`` into one intent of ``role``'s schema. Never raises."""
    role = (role or "").upper()
    language = detect_language(text)
    found = _matches(role, text)
    result = IntentResult(intent="unknown", role=role, language=language, timeframe=timeframe_of(text))
    if found:
        primary = found[0]
        conflicting = [i for i in found[1:] if frozenset({primary, i}) not in COMPATIBLE
                       and not any(frozenset({primary, i}) <= c for c in COMPATIBLE)]
        if conflicting:
            result.intent, result.candidates = "ambiguous", [primary, *conflicting][:3]
        else:
            result.intent, result.candidates = primary, found[:3]
        return result
    proposed, source = propose_intent(provider, role, text)
    result.source = source
    if proposed:
        result.intent, result.candidates = proposed, [proposed]
    return result


def propose_intent(provider, role: str, text: str) -> Tuple[Optional[str], str]:
    """Ask a configured provider to choose one intent from the role's schema. Returns (intent or None, source)."""
    from app.agents.ai_provider import DeterministicNLPProvider
    if provider is None or isinstance(provider, DeterministicNLPProvider) or not callable(
            getattr(provider, "classify_intent", None)):
        return None, "deterministic"
    allowed = [name for name, _ in ROLE_INTENTS.get(role, ())]
    from app.agents.intent_proposal import redact
    try:
        raw = provider.classify_intent(redact(text), allowed)
    except Exception as exc:  # timeout, auth, rate limit, invalid JSON
        logger.info("Intent proposal unavailable (%s); deterministic result kept.", type(exc).__name__)
        return None, "provider_unavailable"
    return (raw, "llm_proposal") if isinstance(raw, str) and raw in allowed else (None, "provider_unavailable")
