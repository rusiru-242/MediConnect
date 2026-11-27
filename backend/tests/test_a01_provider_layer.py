"""A01 component 32 (AI Provider Management): adapters, model selection, failure handling and fallback.

All provider behaviour here uses controlled test doubles (requests.post is patched, and conftest blocks any real
request to a provider host). None of these results counts as live provider verification; the live rows are recorded
separately in docs/uat/agent-completion/a01/evidence.
"""
import json
import logging
from unittest.mock import patch

import pytest
import requests

from app.agents import llm_client as llm
from app.agents import provider_gateway as gw
from app.config.settings import settings
from app.services.ai_provider_monitoring_service import AIProviderMonitoringService
from pydantic import BaseModel
from tests.test_payment import client, db  # noqa: F401
from tests.test_phase02_booking_payment import _admin, _auth

GEMINI_KEY = "test-gemini-key-not-real-a01"
OPENAI_KEY = "test-openai-key-not-real-a01"


class _Resp:
    def __init__(self, status, body, headers=None):
        self.status_code = status
        self._body = body
        self.text = body if isinstance(body, str) else json.dumps(body)
        self.headers = headers or {}

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


class Pong(BaseModel):
    answer: str
    ok: bool


SCHEMA = llm.strict_object({"answer": {"type": "string"}, "ok": {"type": "boolean"}})


def gemini_ok(payload, finish="STOP"):
    return _Resp(200, {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": json.dumps(payload)}]}}],
                       "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 5}})


def openai_ok(payload, finish="stop"):
    return _Resp(200, {"choices": [{"finish_reason": finish, "message": {"content": json.dumps(payload)}}],
                       "usage": {"prompt_tokens": 9, "completion_tokens": 4}})


@pytest.fixture
def providers(db):
    AIProviderMonitoringService.reset()
    db[gw.COLLECTION].delete_many({})
    with patch.object(settings, "GEMINI_API_KEY", GEMINI_KEY), patch.object(settings, "OPENAI_API_KEY", OPENAI_KEY), \
            patch.object(settings, "GEMINI_MODEL", "gemini-3.8-flash"), patch.object(settings, "OPENAI_MODEL", "gpt-6-luna"), \
            patch.object(settings, "AI_PRIMARY_PROVIDER", "gemini"), patch.object(settings, "AI_SECONDARY_PROVIDER", "openai"), \
            patch.object(gw, "RETRY_BACKOFF_SECONDS", 0.01):
        yield
    AIProviderMonitoringService.reset()


def call():
    return llm.generate_json(task="probe", system="sys", user="user text", model_cls=Pong, schema=SCHEMA, timeout=5)


def by_host(gemini, openai):
    def fake(url, **kwargs):
        return gemini(url, **kwargs) if "googleapis" in url else openai(url, **kwargs)
    return fake


def today(provider):
    return gw._db()[gw.COLLECTION].find_one({"_id": gw._day_key(provider)}) or {}


# ------------------------------------------------------------------------------------------ P01 / P02 configuration
def test_p01_p02_configuration_order_models_and_lifecycle(providers):
    assert llm.provider_order() == ["gemini", "openai"]
    with patch.object(settings, "AI_PRIMARY_PROVIDER", "openai"), patch.object(settings, "AI_SECONDARY_PROVIDER", "gemini"):
        assert llm.provider_order() == ["openai", "gemini"]
    with patch.object(settings, "OPENAI_API_KEY", ""):
        assert llm.provider_order() == ["gemini"]  # a provider without a key is skipped
    with patch.object(settings, "AI_SECONDARY_PROVIDER", "none"):
        assert llm.provider_order() == ["gemini"]
    status = gw.provider_status("gemini")
    assert status["status"] == "configured_not_verified" and status["role"] == "primary"
    assert status["model"] == "gemini-3.8-flash" and status["visionModel"] == "gemini-3.8-flash"
    assert status["liveVerified"] is False
    with patch.object(settings, "GEMINI_MODEL", "gemini-1.5-flash"):  # retired id in an old .env
        remapped = gw.provider_status("gemini")
        assert remapped["model"] == "gemini-3.8-flash" and remapped["modelRemapped"] is True
    with patch.object(settings, "OPENAI_MODEL", "gpt-4o-mini"):
        assert gw.provider_status("openai")["modelShutdownDate"] == "2027-01-14"
    assert gw.provider_status("openai")["role"] == "secondary"
    assert GEMINI_KEY not in json.dumps(status, default=str)


def test_p01_vision_capability_aware_model_selection(providers):
    assert llm.supports_vision("gemini", "gemini-3.8-flash") and llm.supports_vision("openai", "gpt-6-luna")
    assert not llm.supports_vision("openai", "gpt-3.5-turbo")
    with patch.object(settings, "OPENAI_VISION_MODEL", "gpt-3.5-turbo"), \
            patch.object(settings, "AI_PRIMARY_PROVIDER", "openai"), patch.object(settings, "AI_SECONDARY_PROVIDER", "gemini"), \
            patch.object(gw.requests, "post", side_effect=by_host(lambda u, **k: gemini_ok({"answer": "pong", "ok": True}),
                                                                 lambda u, **k: pytest.fail("text-only model got an image"))):
        res = llm.generate_json(task="t", system="s", user="u", model_cls=Pong, schema=SCHEMA, image=(b"\x89PNG", "image/png"))
    assert res.provider == "gemini" and res.attempts[0]["category"] == "capability_unsupported"


# ------------------------------------------------------------------------------------------ adapters (shape)
def test_adapters_share_one_shape_and_keep_keys_in_headers(providers):
    with patch.object(gw.requests, "post", return_value=gemini_ok({"answer": "pong", "ok": True})) as post:
        res = call()
    url, kw = post.call_args[0][0], post.call_args[1]
    assert res.provider == "gemini" and res.model == "gemini-3.8-flash" and res.data.answer == "pong"
    assert url.endswith("/models/gemini-3.8-flash:generateContent") and GEMINI_KEY not in url
    assert kw["headers"]["x-goog-api-key"] == GEMINI_KEY
    cfg = kw["json"]["generationConfig"]
    assert cfg["responseMimeType"] == "application/json" and cfg["responseJsonSchema"] == SCHEMA
    assert kw["json"]["systemInstruction"]["parts"][0]["text"] == "sys"

    with patch.object(settings, "AI_PRIMARY_PROVIDER", "openai"), \
            patch.object(gw.requests, "post", return_value=openai_ok({"answer": "pong", "ok": True})) as post:
        res = call()
    body = post.call_args[1]["json"]
    assert res.provider == "openai" and body["model"] == "gpt-6-luna"
    assert body["response_format"]["type"] == "json_schema" and body["response_format"]["json_schema"]["strict"] is True
    # gpt-6 is a reasoning family: no custom temperature, reasoning_effort set, room for reasoning tokens.
    assert "temperature" not in body and body["reasoning_effort"] == "low" and body["max_completion_tokens"] > 1024
    assert post.call_args[1]["headers"]["Authorization"] == f"Bearer {OPENAI_KEY}"
    with patch.object(settings, "OPENAI_MODEL", "gpt-4o-mini"), patch.object(settings, "AI_PRIMARY_PROVIDER", "openai"), \
            patch.object(gw.requests, "post", return_value=openai_ok({"answer": "pong", "ok": True})) as post:
        call()
    assert post.call_args[1]["json"]["temperature"] == 0.2 and "reasoning_effort" not in post.call_args[1]["json"]


def test_image_bytes_reach_both_adapters(providers):
    png = b"\x89PNG\r\n\x1a\nA01-synthetic-bytes"
    with patch.object(gw.requests, "post", return_value=gemini_ok({"answer": "pong", "ok": True})) as post:
        llm.generate_json(task="t", system="s", user="u", model_cls=Pong, schema=SCHEMA, image=(png, "image/png"))
    import base64
    part = post.call_args[1]["json"]["contents"][0]["parts"][1]["inline_data"]
    assert part == {"mime_type": "image/png", "data": base64.b64encode(png).decode()}
    with patch.object(settings, "AI_PRIMARY_PROVIDER", "openai"), \
            patch.object(gw.requests, "post", return_value=openai_ok({"answer": "pong", "ok": True})) as post:
        llm.generate_json(task="t", system="s", user="u", model_cls=Pong, schema=SCHEMA, image=(png, "image/png"))
    content = post.call_args[1]["json"]["messages"][1]["content"]
    assert content[1]["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(png).decode()


# ------------------------------------------------------------------------------------------ P06-P09 failures
@pytest.mark.parametrize("status,body,category,calls", [
    (401, {"error": {"message": "API key not valid"}}, "auth_failed", 1),                  # P06
    (404, {"error": {"message": "model not found"}}, "invalid_model", 1),                  # P07
    (429, {"error": {"message": "Resource exhausted"}}, "rate_limited", 2),                # P09 transient
    (429, {"error": {"code": "insufficient_quota", "message": "no credits"}}, "quota_exhausted", 1),  # A01-N02
    (429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "You exceeded your current quota, please check your "
                     "plan and billing details. " + "For more information see the rate-limit documentation. " * 8 +
                     "Quota exceeded for metric: generate_content_free_tier_"
                     "requests, limit: 20, description: Generate content requests per day limit exceeded on Free "
                     "Tier. Please retry in 21h55m."}}, "quota_exhausted", 1),                         # live 2026-11-26
    (503, {"error": {"message": "high demand"}}, "server_error", 2),
])
def test_p06_p07_p09_failure_categories_and_bounded_retry(providers, status, body, category, calls):
    with patch.object(settings, "AI_SECONDARY_PROVIDER", "none"), \
            patch.object(gw.requests, "post", return_value=_Resp(status, body)) as post:
        with pytest.raises(llm.LLMUnavailable) as exc:
            call()
    assert exc.value.attempts == [{"provider": "gemini", "model": "gemini-3.8-flash", "category": category}]
    assert post.call_count == calls
    assert today("gemini")[f"failure_{category}"] == 1


def test_p09_retry_after_is_honoured_but_capped(providers):
    import threading
    sleeps = []
    caller = threading.current_thread()

    def record(seconds):
        # gw.time is the global time module: record only this thread's waits. pymongo's monitor threads also call
        # time.sleep(0.5) and, with sleep patched to a no-op, made this test flaky (A03 final run).
        if threading.current_thread() is caller:
            sleeps.append(seconds)

    with patch.object(settings, "AI_SECONDARY_PROVIDER", "none"), patch.object(gw.time, "sleep", record), \
            patch.object(gw.requests, "post", return_value=_Resp(429, {}, {"Retry-After": "30"})):
        with pytest.raises(llm.LLMUnavailable):
            call()
    assert sleeps == [gw.MAX_RETRY_AFTER_SECONDS]


def test_p08_timeout_not_retried_and_falls_through(providers):
    def fake(url, **kwargs):
        if "googleapis" in url:
            raise requests.Timeout()
        return openai_ok({"answer": "pong", "ok": True})
    with patch.object(gw.requests, "post", side_effect=fake) as post:
        res = call()
    assert res.provider == "openai" and res.fell_back
    assert [a["category"] for a in res.attempts] == ["timeout", "ok"] and post.call_count == 2


# ------------------------------------------------------------------------------------------ P10 structured output
@pytest.mark.parametrize("bad", [
    _Resp(200, "<html>not json</html>"),                                                    # body is not JSON
    gemini_ok({"answer": "pong"}),                                                          # schema: missing field
    gemini_ok({"answer": 5, "ok": "yes please"}),                                           # schema: wrong types
    gemini_ok({"answer": "pong", "ok": True}, finish="MAX_TOKENS"),                         # truncated
    gemini_ok({"answer": "pong", "ok": True}, finish="SAFETY"),                             # blocked
    _Resp(200, {"candidates": [{"content": {"parts": [{"text": "Sure! here you go"}]}}]}),  # prose, not JSON
])
def test_p10_invalid_structured_output_is_rejected_and_counted_as_failure(providers, bad):
    with patch.object(settings, "AI_SECONDARY_PROVIDER", "none"), patch.object(gw.requests, "post", return_value=bad):
        with pytest.raises(llm.LLMUnavailable) as exc:
            call()
    assert exc.value.attempts[0]["category"] == "invalid_output"
    record = today("gemini")
    assert record.get("successes", 0) == 0 and record["failures"] == 1   # A01-N03: no longer a "success"


# ------------------------------------------------------------------------------------------ P11-P14 fallback
def test_p11_p12_primary_failure_uses_secondary(providers):
    with patch.object(gw.requests, "post", side_effect=by_host(lambda u, **k: _Resp(503, {}),
                                                               lambda u, **k: openai_ok({"answer": "pong", "ok": True}))):
        res = call()
    assert res.provider == "openai" and res.fell_back
    assert res.meta()["providerFallback"] is True and res.meta()["responseSource"] == "llm"


def test_p13_both_providers_unavailable(providers):
    with patch.object(gw.requests, "post", side_effect=by_host(lambda u, **k: _Resp(401, {}),
                                                               lambda u, **k: _Resp(429, {"error": {"code": "insufficient_quota"}}))):
        with pytest.raises(llm.LLMUnavailable) as exc:
            call()
    assert [(a["provider"], a["category"]) for a in exc.value.attempts] == [("gemini", "auth_failed"),
                                                                           ("openai", "quota_exhausted")]
    assert gw.provider_status("gemini")["status"] == "unavailable"
    assert gw.provider_status("openai")["status"] == "unavailable"   # no credits is not "rate_limited"


def test_p14_not_configured_and_disabled_never_call_the_network(providers):
    with patch.object(settings, "GEMINI_API_KEY", ""), patch.object(settings, "OPENAI_API_KEY", ""), \
            patch.object(gw.requests, "post") as post:
        with pytest.raises(llm.LLMUnavailable) as exc:
            call()
        assert exc.value.reason == "not_configured" and post.call_count == 0
    with patch.object(settings, "AI_DAILY_REQUEST_LIMIT", 0), patch.object(gw.requests, "post") as post:
        with pytest.raises(llm.LLMUnavailable) as exc:
            call()
        assert exc.value.reason == "disabled" and post.call_count == 0


def test_p14_doctor_search_parser_chain_then_deterministic(providers):
    from app.agents.ai_provider import ChainedAIProvider, get_ai_provider
    parsed_ok = {"specialty": "Cardiologist", "city": "Colombo"}
    provider = get_ai_provider()
    assert isinstance(provider, ChainedAIProvider)
    with patch.object(gw.requests, "post", side_effect=by_host(lambda u, **k: _Resp(503, {}),
                                                               lambda u, **k: openai_ok(parsed_ok))):
        parsed, source = provider.parse_request("heart doctor in Colombo")
    assert source == "openai" and parsed["specialty"] == "Cardiologist"
    with patch.object(gw.requests, "post", return_value=_Resp(500, {})):
        parsed, source = get_ai_provider().parse_request("cardiologist in Colombo")
    assert source.startswith("deterministic")
    # A wrong type from the provider is rejected (schema), not passed on.
    with patch.object(settings, "AI_SECONDARY_PROVIDER", "none"), \
            patch.object(gw.requests, "post", return_value=gemini_ok({"specialty": "Cardiologist", "maxFee": "cheap"})):
        _, source = get_ai_provider().parse_request("cardiologist under cheap")
    assert source.startswith("deterministic")


def test_tool_calling_sticks_to_one_provider_within_a_run(providers):
    from app.agents.ai_provider import ChainedAIProvider, get_ai_provider
    chain = get_ai_provider()
    assert isinstance(chain, ChainedAIProvider)
    gemini, openai = chain.providers
    with patch.object(gemini, "tool_turn", side_effect=gw.ProviderCallError("server_error")), \
            patch.object(openai, "tool_turn", return_value=([], {}, "ok")) as oa:
        assert chain.tool_turn("s", [], [], []) == ([], {}, "ok")
        chain.tool_turn("s", [], [], [("x", {}, [])])   # later turn of the same run
    assert oa.call_count == 2


# ------------------------------------------------------------------------------------------ P15 monitoring
def test_p15_monitoring_reflects_measured_state(providers, db):
    with patch.object(settings, "AI_SECONDARY_PROVIDER", "none"):
        with patch.object(gw.requests, "post", return_value=gemini_ok({"answer": "pong", "ok": True})):
            call()
        assert gw.provider_status("gemini")["status"] == "available"
        assert gw.provider_status("gemini")["liveVerified"] is True
        for _ in range(2):
            with patch.object(gw.requests, "post", return_value=gemini_ok({"answer": "pong"})):
                with pytest.raises(llm.LLMUnavailable):
                    call()
    status = gw.provider_status("gemini")
    assert status["status"] in {"degraded", "unavailable"} and status["today"]["outputRejected"] == 2
    admin = _admin(db)
    res = client.get("/api/security/monitoring/ai-providers", headers=_auth(admin))
    assert res.status_code == 200
    assert GEMINI_KEY not in res.text and OPENAI_KEY not in res.text


# ------------------------------------------------------------------------------------------ P16 privacy
def test_p16_no_secret_or_prompt_leaks_into_metrics_logs_or_errors(providers, caplog):
    caplog.set_level(logging.DEBUG)
    with patch.object(gw.requests, "post", side_effect=by_host(lambda u, **k: _Resp(401, {"error": GEMINI_KEY}),
                                                               lambda u, **k: _Resp(500, {}))):
        with pytest.raises(llm.LLMUnavailable) as exc:
            llm.generate_json(task="t", system="s", user="patient Nimal 0771234567 has a rash", model_cls=Pong,
                              schema=SCHEMA)
    stored = json.dumps([today("gemini"), today("openai")], default=str)
    for secret in (GEMINI_KEY, OPENAI_KEY, "Nimal", "0771234567", "rash"):
        assert secret not in stored and secret not in caplog.text and secret not in str(exc.value)
        assert secret not in json.dumps(exc.value.attempts)


def test_live_requests_are_blocked_in_the_test_suite():
    """The conftest guard: nothing in the suite can reach a real provider host."""
    with pytest.raises(requests.ConnectionError):
        requests.post("https://api.openai.com/v1/chat/completions", json={}, timeout=2)
