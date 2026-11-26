"""Provider-neutral structured LLM calls with primary/secondary fallback (A01, component 32).

Before A01 every feature talked to one provider in its own way: the Health Assistant called only Gemini, the medicine
image agent picked Gemini or OpenAI but never fell back from one to the other, and the doctor-search parser used
whichever key was present first. Responses were accepted after ``json.loads`` without a schema.

:func:`generate_json` is now the one entry point for structured generation:

* Providers are tried in the configured order (``AI_PRIMARY_PROVIDER`` then ``AI_SECONDARY_PROVIDER``); a provider
  without a key, or whose model cannot handle the requested capability (for example image input), is skipped.
* Each attempt goes through :mod:`app.agents.provider_gateway` (usage limit, circuit breaker, bounded retry,
  failure categories, privacy-safe metrics; credentials only in headers).
* The provider is asked for JSON matching a schema, and the answer is validated again here with a pydantic model.
  Output that is blocked, truncated, not JSON or not valid against the schema is rejected, counted as a provider
  failure (not a success) and the next provider is tried.
* When every provider fails, :class:`LLMUnavailable` lists what happened to each attempt, and the caller uses its
  deterministic answer. Nothing here can raise anything else, so a provider failure never crashes a request.

The caller decides what a provider may be used for. Emergency detection, prescription refusals, permissions and every
authoritative value (doctors, slots, fees, payments) stay deterministic and server-side.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError

from app.config.settings import settings

logger = logging.getLogger(__name__)

PROVIDERS = ("gemini", "openai")
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"

# Capability table by model family. Both current defaults (gemini-3.8-flash, gpt-6-luna) accept text and images
# (official model pages, checked 2026-11-26). A configured model outside these families is treated as text-only.
VISION_PREFIXES = {"gemini": ("gemini-",), "openai": ("gpt-4o", "gpt-4.1", "gpt-5", "gpt-6", "o3", "o4")}
# OpenAI reasoning families take reasoning_effort and not a custom temperature; reasoning tokens count against
# max_completion_tokens, so their budget is larger.
OPENAI_REASONING_PREFIXES = ("gpt-5", "gpt-6", "o1", "o3", "o4")
GEMINI_THINKING: Dict[str, str] = {"thinkingLevel": "low"}
GEMINI_BLOCKED_FINISH = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY"}


class LLMUnavailable(Exception):
    """No provider produced valid output. ``attempts`` holds one {provider, model, category} entry per try."""

    def __init__(self, attempts: List[Dict[str, Any]]):
        super().__init__(", ".join(f"{a.get('provider')}:{a.get('category')}" for a in attempts) or "not_configured")
        self.attempts = attempts

    @property
    def reason(self) -> str:
        return self.attempts[-1]["category"] if self.attempts else "not_configured"


@dataclass
class LLMResult:
    data: BaseModel
    provider: str
    model: str
    latency_ms: float
    attempts: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def fell_back(self) -> bool:
        """True when the secondary provider answered because the primary failed."""
        return any(a.get("category") != "ok" for a in self.attempts[:-1])

    def meta(self) -> Dict[str, Any]:
        return {"responseSource": "llm", "provider": self.provider, "model": self.model,
                "providerFallback": self.fell_back, "attempts": [
                    {k: a.get(k) for k in ("provider", "model", "category")} for a in self.attempts]}


def _key(provider: str) -> str:
    raw = settings.GEMINI_API_KEY if provider == "gemini" else settings.OPENAI_API_KEY
    return (raw or "").strip()


def provider_order() -> List[str]:
    """Configured providers in the order they are tried (only providers that have a key)."""
    order: List[str] = []
    for name in (settings.AI_PRIMARY_PROVIDER, settings.AI_SECONDARY_PROVIDER):
        name = (name or "").strip().lower()
        if name in PROVIDERS and name not in order and _key(name):
            order.append(name)
    return order


def text_model(provider: str) -> str:
    from app.agents.provider_gateway import resolve_gemini_model, resolve_openai_model
    return resolve_gemini_model(settings.GEMINI_MODEL) if provider == "gemini" else resolve_openai_model(
        settings.OPENAI_MODEL)


def vision_model(provider: str) -> str:
    from app.agents.provider_gateway import resolve_gemini_model, resolve_openai_model
    if provider == "gemini":
        return resolve_gemini_model(settings.GEMINI_VISION_MODEL or settings.GEMINI_MODEL)
    return resolve_openai_model(settings.OPENAI_VISION_MODEL or settings.OPENAI_MODEL)


def supports_vision(provider: str, model: str) -> bool:
    return model.startswith(VISION_PREFIXES.get(provider, ()))


# ---------------------------------------------------------------------------------------------------------------
# Adapters: build the request and extract the JSON text. Same inputs and outputs for both providers.
# ---------------------------------------------------------------------------------------------------------------
def _gemini_request(model: str, system: str, user: str, image: Optional[Tuple[bytes, str]], schema: dict,
                    temperature: float, max_tokens: int) -> Tuple[str, Dict[str, str], dict]:
    parts: List[dict] = [{"text": user}]
    if image:
        parts.append({"inline_data": {"mime_type": image[1], "data": base64.b64encode(image[0]).decode("ascii")}})
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        # Gemini 3.x models think by default and thought tokens count against maxOutputTokens, so the budget is
        # raised and thinking is kept low for these short structured answers.
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json",
                             "responseJsonSchema": schema, "maxOutputTokens": max_tokens + 2048,
                             **({"thinkingConfig": dict(GEMINI_THINKING)} if GEMINI_THINKING else {})},
    }
    return GEMINI_ENDPOINT.format(model=model), {"x-goog-api-key": _key("gemini")}, payload


def _gemini_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("blocked" if (data.get("promptFeedback") or {}).get("blockReason") else "no_candidates")
    candidate = candidates[0]
    finish = candidate.get("finishReason")
    if finish in GEMINI_BLOCKED_FINISH:
        raise ValueError("blocked")
    if finish == "MAX_TOKENS":
        raise ValueError("truncated")
    parts = (candidate.get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _openai_request(model: str, system: str, user: str, image: Optional[Tuple[bytes, str]], schema: dict,
                    temperature: float, max_tokens: int, schema_name: str) -> Tuple[str, Dict[str, str], dict]:
    content: Any = user
    if image:
        encoded = base64.b64encode(image[0]).decode("ascii")
        content = [{"type": "text", "text": user},
                   {"type": "image_url", "image_url": {"url": f"data:{image[1]};base64,{encoded}"}}]
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
    }
    if model.startswith(OPENAI_REASONING_PREFIXES):
        payload["reasoning_effort"] = "low"
        payload["max_completion_tokens"] = max_tokens + 2048
    else:
        payload["temperature"] = temperature
        payload["max_completion_tokens"] = max_tokens
    return OPENAI_ENDPOINT, {"Authorization": f"Bearer {_key('openai')}"}, payload


def _openai_text(data: dict) -> str:
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    if message.get("refusal"):
        raise ValueError("refused")
    if choice.get("finish_reason") == "length":
        raise ValueError("truncated")
    if choice.get("finish_reason") == "content_filter":
        raise ValueError("blocked")
    return message.get("content") or ""


def parse_json_text(text: str) -> Dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.MULTILINE).strip()
    if not cleaned:
        raise ValueError("empty")
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("not_an_object")
    return data


def generate_json(*, task: str, system: str, user: str, model_cls: Type[BaseModel], schema: dict,
                  image: Optional[Tuple[bytes, str]] = None, timeout: Optional[float] = None,
                  max_output_tokens: int = 1024, temperature: float = 0.2,
                  providers: Optional[List[str]] = None) -> LLMResult:
    """Return validated structured output from the first provider that produces it, or raise LLMUnavailable."""
    from app.agents.provider_gateway import ProviderCallError, record_output_rejected, send

    attempts: List[Dict[str, Any]] = []
    order = providers if providers is not None else provider_order()
    if not order:
        raise LLMUnavailable([{"provider": None, "model": None, "category": "not_configured"}])
    if int(settings.AI_DAILY_REQUEST_LIMIT) <= 0:
        raise LLMUnavailable([{"provider": None, "model": None, "category": "disabled"}])
    budget = float(timeout or (settings.AI_VISION_TIMEOUT_SECONDS if image else settings.AI_TIMEOUT_SECONDS))
    for provider in order:
        model = vision_model(provider) if image else text_model(provider)
        if image and not supports_vision(provider, model):
            attempts.append({"provider": provider, "model": model, "category": "capability_unsupported"})
            continue
        if provider == "gemini":
            url, headers, payload = _gemini_request(model, system, user, image, schema, temperature, max_output_tokens)
        else:
            url, headers, payload = _openai_request(model, system, user, image, schema, temperature,
                                                    max_output_tokens, task)
        started = time.monotonic()
        try:
            data = send(provider, model, url, headers, payload, budget)
        except ProviderCallError as exc:
            attempts.append({"provider": provider, "model": model, "category": exc.category})
            continue
        except Exception as exc:  # defensive: the gateway should only raise ProviderCallError
            attempts.append({"provider": provider, "model": model, "category": f"error:{type(exc).__name__}"})
            continue
        try:
            text = _gemini_text(data) if provider == "gemini" else _openai_text(data)
            validated = model_cls.model_validate(parse_json_text(text))
        except (ValueError, ValidationError, TypeError, KeyError, IndexError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, ValidationError) else \
                type(exc).__name__
            reason = reason if re.fullmatch(r"[a-z_]{3,30}", reason or "") else type(exc).__name__
            record_output_rejected(provider, reason)
            attempts.append({"provider": provider, "model": model, "category": "invalid_output", "detail": reason})
            continue
        attempts.append({"provider": provider, "model": model, "category": "ok"})
        return LLMResult(validated, provider, model, round((time.monotonic() - started) * 1000, 1), attempts)
    raise LLMUnavailable(attempts)


def nullable(schema: dict) -> dict:
    """JSON-schema "value or null" that both providers' structured-output modes accept."""
    return {"anyOf": [schema, {"type": "null"}]}


def strict_object(properties: Dict[str, dict]) -> dict:
    """Object schema with every property required and no extras (OpenAI strict mode rules; Gemini accepts it)."""
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
