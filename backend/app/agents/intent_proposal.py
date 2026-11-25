"""Bounded LLM-assisted preference understanding (Phase 01).

The language model may only *propose* search preferences for a message the deterministic parser could not
understand. The server keeps authority over everything else:

- Emergency detection, prescription refusal and health-advice routing run BEFORE this layer, so those messages
  never reach the provider from here.
- The proposal is validated against a strict schema: specialty and city must be supported values, fees and
  ratings must be in range, the sort order must be one of three values, and the date must be ISO formatted.
  Anything else (unknown fields, booking/payment instructions, free text) is discarded.
- Identifiers (emails, phone numbers, NIC numbers, "my name is ...") are redacted before sending.
- No tool is executed from a proposal; it can only fill search preferences, which then go through the normal
  server-side search with its own verification, prices and availability.
- Any provider error, timeout or invalid output falls back to the deterministic result (no proposal).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.agents.nlp_parser import LOCATION_PATTERNS
from app.models.specialty import SUPPORTED_SPECIALTIES

logger = logging.getLogger(__name__)

SUPPORTED_CITIES = tuple(city for city, _ in LOCATION_PATTERNS)
ALLOWED_FIELDS = ("specialty", "city", "maxFee", "minRating", "sortBy", "date")

_REDACTIONS = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"(?:\+94|0)\s?\d{2}\s?\d{3}\s?\d{4}\b"), "[phone]"),
    (re.compile(r"\b\d{9}[vVxX]\b|\b\d{12}\b"), "[id]"),
    (re.compile(r"\b(?:my name is|i am called|mage nama)\s+[\w .'-]{1,40}", re.I), "[name]"),
)


def redact(text: str) -> str:
    """Remove identifiers the provider does not need."""
    cleaned = (text or "")[:500]
    for pattern, token in _REDACTIONS:
        cleaned = pattern.sub(token, cleaned)
    return cleaned


class PreferenceProposal(BaseModel):
    """Strict schema for model-proposed search preferences. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    specialty: Optional[str] = None
    city: Optional[str] = None
    maxFee: Optional[float] = Field(default=None, ge=100, le=100000)
    minRating: Optional[float] = Field(default=None, ge=1, le=5)
    sortBy: Optional[Literal["experience_desc", "rating_desc", "fee_asc"]] = None
    date: Optional[str] = None

    @field_validator("specialty")
    @classmethod
    def _supported_specialty(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        match = next((s for s in SUPPORTED_SPECIALTIES if s.casefold() == value.strip().casefold()), None)
        if match is None:
            raise ValueError("unsupported specialty")
        return match

    @field_validator("city")
    @classmethod
    def _supported_city(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        match = next((c for c in SUPPORTED_CITIES if c.casefold() == value.strip().casefold()), None)
        if match is None:
            raise ValueError("unsupported city")
        return match

    @field_validator("date")
    @classmethod
    def _iso_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        parsed = date.fromisoformat(value.strip())
        if parsed < date.today():
            raise ValueError("date in the past")
        return parsed.isoformat()


def _validate_fields(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate each allowed field on its own, so one bad value does not discard the rest."""
    accepted: Dict[str, Any] = {}
    for key in ALLOWED_FIELDS:
        value = raw.get(key)
        if value in (None, "", []):
            continue
        try:
            accepted.update({k: v for k, v in PreferenceProposal.model_validate({key: value}).model_dump().items()
                             if v is not None})
        except (ValidationError, ValueError, TypeError):
            logger.info("Discarded invalid model-proposed field %s.", key)
    return accepted


def propose_preferences(provider, text: str) -> Tuple[Dict[str, Any], str]:
    """Return (validated preference proposal, source).

    source is "deterministic" when no LLM provider is configured, "provider_unavailable" when the provider fell
    back or failed, and "llm_proposal" when a validated proposal was produced.
    """
    from app.agents.ai_provider import DeterministicNLPProvider

    if provider is None or isinstance(provider, DeterministicNLPProvider):
        return {}, "deterministic"
    try:
        raw, source = provider.parse_request(query=redact(text), explicit_filters={})
    except Exception as exc:  # network, timeout, malformed JSON
        logger.warning("Intent proposal failed (%s); using deterministic result.", type(exc).__name__)
        return {}, "provider_unavailable"
    if not isinstance(raw, dict) or str(source).startswith("deterministic"):
        return {}, "provider_unavailable"
    accepted = _validate_fields(raw)
    return accepted, "llm_proposal" if accepted else "provider_unavailable"
