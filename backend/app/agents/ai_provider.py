"""AI Provider abstraction for parsing natural-language doctor discovery requests.

Supports Gemini, OpenAI, and a reliable deterministic fallback when no LLM provider is configured.
"""

from abc import ABC, abstractmethod
import json
import logging
from typing import Any, Dict, Optional, Tuple
import requests

from app.agents.nlp_parser import parse_query_deterministically
from app.config.settings import settings
from app.models.specialty import SUPPORTED_SPECIALTIES

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are a specialized Medical Discovery Assistant for MediConnect in Sri Lanka.
Your sole job is to extract structured search filters from patient inquiries in English or Sinhala.

CRITICAL MEDICAL SAFETY & DISCOVERY CONSTRAINTS:
1. You are NOT a diagnostic system and MUST NOT diagnose illnesses or prescribe medications.
2. Supported specialties are STRICTLY limited to the following list:
{json.dumps(SUPPORTED_SPECIALTIES, indent=2)}
If the query mentions symptoms, map them to the most appropriate supported specialty, or null if uncertain.
3. If the query mentions potentially life-threatening or urgent symptoms (such as acute chest pain, heart attack, severe difficulty breathing, stroke symptoms like slurred speech or facial droop, heavy uncontrolled bleeding, or loss of consciousness), flag "isUrgent": true with a concise medical safety caution.
4. Extract location/city in Sri Lanka (e.g., Colombo, Kandy, Galle, Gampaha, Negombo, etc., or hospital names like Asiri, Nawaloka, Durdans).
5. Extract preferred date in YYYY-MM-DD if explicitly stated or relative (today, tomorrow, next Monday, etc.).
6. Extract preferred time range ("morning", "afternoon", "evening").
7. Extract maximum consultation fee in LKR as a numeric float if mentioned.
8. Output MUST be a valid JSON object matching this exact schema:
{{
  "specialty": string | null,
  "city": string | null,
  "date": string | null,
  "timeRange": "morning" | "afternoon" | "evening" | null,
  "maxFee": number | null,
  "isUrgent": boolean,
  "urgencyReason": string | null,
  "clarificationQuestion": string | null,
  "language": "en" | "si"
}}
Do NOT output any markdown, HTML, or explanations outside the JSON object.
"""


class AIProvider(ABC):
    """Abstract interface for AI query interpretation providers."""

    @abstractmethod
    def parse_request(
        self,
        query: str,
        explicit_filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """Parse natural-language query and return structured filters and provider name."""
        pass


class DeterministicNLPProvider(AIProvider):
    """Rule-based NLP provider using regex and vocabulary mapping in English and Sinhala."""

    def parse_request(
        self,
        query: str,
        explicit_filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        filters = explicit_filters or {}
        parsed = parse_query_deterministically(
            query=query,
            explicit_specialty=filters.get("specialty"),
            explicit_city=filters.get("city"),
            explicit_date=filters.get("date"),
            explicit_time_range=filters.get("timeRange"),
            explicit_max_fee=filters.get("maxFee"),
            explicit_consultation_type=filters.get("consultationType"),
        )
        return parsed, "deterministic_fallback"


class GeminiAIProvider(AIProvider):
    """Gemini-powered natural-language query parser with deterministic fallback."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", timeout_seconds: int = 5):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.fallback = DeterministicNLPProvider()

    def parse_request(
        self,
        query: str,
        explicit_filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        filters = explicit_filters or {}
        # Clean and truncate query to avoid giant payload injection
        sanitized_query = query.strip()[:1000]

        model_name = self.model
        if model_name in ["gemini-1.5-flash", "gemini-2.5-flash"]:
            model_name = "gemini-flash-latest"
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent"
            f"?key={self.api_key}"
        )

        user_content = f"Patient Inquiry: {sanitized_query}\n"
        if filters:
            user_content += f"Explicit User Filters: {json.dumps(filters)}\n"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": SYSTEM_PROMPT},
                        {"text": user_content},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        try:
            response = requests.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout_seconds,
            )

            if response.status_code != 200:
                logger.warning(
                    "Gemini API returned status %d. Falling back to deterministic NLP parser.",
                    response.status_code,
                )
                return self.fallback.parse_request(query, explicit_filters)

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return self.fallback.parse_request(query, explicit_filters)

            part_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not part_text:
                return self.fallback.parse_request(query, explicit_filters)

            extracted = json.loads(part_text)

            # Validate extracted specialty against supported list
            spec = extracted.get("specialty")
            if spec and spec not in SUPPORTED_SPECIALTIES:
                matched = None
                for s in SUPPORTED_SPECIALTIES:
                    if s.lower() == str(spec).strip().lower():
                        matched = s
                        break
                extracted["specialty"] = matched

            # Apply explicit filter overrides if provided
            if filters.get("specialty"):
                extracted["specialty"] = filters["specialty"]
            if filters.get("city"):
                extracted["city"] = filters["city"]
            if filters.get("date"):
                extracted["date"] = filters["date"]
            if filters.get("timeRange"):
                extracted["timeRange"] = filters["timeRange"]
            if filters.get("maxFee") is not None:
                extracted["maxFee"] = filters["maxFee"]

            # Double check urgency with deterministic heuristics
            det_urgent, det_reason = self.fallback.parse_request(query, explicit_filters)[0].get("isUrgent"), None
            if det_urgent:
                extracted["isUrgent"] = True
                if not extracted.get("urgencyReason"):
                    extracted["urgencyReason"] = "Immediate emergency medical evaluation advised."

            return extracted, "gemini"

        except Exception as exc:
            logger.warning("Gemini AI parsing failed with error: %s. Using deterministic fallback.", exc)
            return self.fallback.parse_request(query, explicit_filters)


class OpenAIAIProvider(AIProvider):
    """OpenAI-powered natural-language query parser with deterministic fallback."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout_seconds: int = 5):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.fallback = DeterministicNLPProvider()

    def parse_request(
        self,
        query: str,
        explicit_filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        filters = explicit_filters or {}
        sanitized_query = query.strip()[:1000]

        endpoint = "https://api.openai.com/v1/chat/completions"
        user_content = f"Patient Inquiry: {sanitized_query}\n"
        if filters:
            user_content += f"Explicit User Filters: {json.dumps(filters)}\n"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        try:
            response = requests.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )

            if response.status_code != 200:
                logger.warning(
                    "OpenAI API returned status %d. Falling back to deterministic NLP parser.",
                    response.status_code,
                )
                return self.fallback.parse_request(query, explicit_filters)

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            extracted = json.loads(content)

            # Validate specialty against supported list
            spec = extracted.get("specialty")
            if spec and spec not in SUPPORTED_SPECIALTIES:
                matched = None
                for s in SUPPORTED_SPECIALTIES:
                    if s.lower() == str(spec).strip().lower():
                        matched = s
                        break
                extracted["specialty"] = matched

            # Apply explicit overrides
            if filters.get("specialty"):
                extracted["specialty"] = filters["specialty"]
            if filters.get("city"):
                extracted["city"] = filters["city"]
            if filters.get("date"):
                extracted["date"] = filters["date"]
            if filters.get("timeRange"):
                extracted["timeRange"] = filters["timeRange"]
            if filters.get("maxFee") is not None:
                extracted["maxFee"] = filters["maxFee"]

            return extracted, "openai"

        except Exception as exc:
            logger.warning("OpenAI AI parsing failed with error: %s. Using deterministic fallback.", exc)
            return self.fallback.parse_request(query, explicit_filters)


def get_ai_provider() -> AIProvider:
    """Return configured AI provider or deterministic fallback."""
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip():
        return GeminiAIProvider(
            api_key=settings.GEMINI_API_KEY.strip(),
            model=settings.GEMINI_MODEL,
            timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        )

    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
        return OpenAIAIProvider(
            api_key=settings.OPENAI_API_KEY.strip(),
            model=settings.OPENAI_MODEL,
            timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        )

    return DeterministicNLPProvider()
