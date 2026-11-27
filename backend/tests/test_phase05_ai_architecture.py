"""Phase 05 components 31/32/38: bounded orchestration, provider gateway and AI run monitoring.

Provider behaviour is exercised only with controlled test doubles (requests.post is patched); no live provider is
called, so none of these results counts as live provider verification.
"""
import asyncio
import json
from unittest.mock import MagicMock, patch

from bson import ObjectId
import pytest
import requests

from app.agents import orchestrator as orch_mod
from app.agents import provider_gateway as gw
from app.agents.orchestrator import AIOrchestrator
from app.agents.tool_registry import TOOLS, Arguments, Tool
from app.config.settings import settings
from app.schemas.user import UserResponseSchema
from app.services.ai_provider_monitoring_service import AIProviderMonitoringService
from tests.test_payment import _make_test_doctor, _make_test_patient, client, db  # noqa: F401
from tests.test_phase02_booking_payment import _admin, _auth


def _user(db, role="PATIENT"):
    from app.models.appointment import utc_now
    return UserResponseSchema(id=str(ObjectId()), fullName="P05 Test", email=f"p05_{ObjectId()}@mediconnect.lk",
                              role=role, emailVerified=True, accountStatus="ACTIVE", createdAt=utc_now())


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------------------------------------ S-01
def test_s01abc_role_routing_tools_only_for_their_roles(db):
    for role, allowed_tool, foreign_tool in (("PATIENT", "get_my_prescriptions", "get_pending_doctor_verifications"),
                                             ("DOCTOR", "get_my_doctor_schedule", "get_my_prescriptions"),
                                             ("ADMIN", "get_pending_doctor_verifications", "get_my_doctor_schedule")):
        o = AIOrchestrator(db, _user(db, role), None)
        assert allowed_tool in o.authorized(set(TOOLS))
        assert foreign_tool not in o.authorized(set(TOOLS))
        assert run(o.execute(foreign_tool, {}, {foreign_tool})) == {"error": "tool_unavailable"}


def test_s01d_valid_structured_call_and_s01e_invalid_arguments(db):
    o = AIOrchestrator(db, _user(db, "PATIENT"), None)
    ok = run(o.execute("search_verified_doctors", {"specialty": "Cardiology"}, {"search_verified_doctors"}))
    assert "doctors" in ok
    bad = run(o.execute("search_verified_doctors", '{"specialty": 12345, "unexpected": "x"}',
                        {"search_verified_doctors"}))
    assert bad == {"error": "invalid_arguments"}


def test_s01f_unauthorized_tool_and_unknown_tool_rejected(db):
    o = AIOrchestrator(db, _user(db, "PATIENT"), None)
    assert run(o.execute("get_admin_dashboard_metrics", {}, {"get_admin_dashboard_metrics"}))["error"] == "tool_unavailable"
    assert run(o.execute("drop_database", {}, {"drop_database"}))["error"] == "tool_unavailable"
    assert run(o.execute(None, {}, set()))["error"] == "tool_unavailable"


def test_s01g_total_tool_call_limit_and_duplicate_prevention(db):
    o = AIOrchestrator(db, _user(db, "PATIENT"), None)
    calls = {"n": 0}

    async def counting(ctx, args):
        calls["n"] += 1
        return {"ok": True}

    with patch.dict(TOOLS, {"p05_counter": Tool("test", Arguments, counting, frozenset({"PATIENT"}))}):
        first = run(o.execute("p05_counter", {}, {"p05_counter"}))
        dup = run(o.execute("p05_counter", {}, {"p05_counter"}))
        assert first == {"ok": True} and dup.get("duplicateCall") is True and calls["n"] == 1
        for _ in range(orch_mod.MAX_TOTAL_CALLS):
            last = run(o.execute("p05_counter", {}, {"p05_counter"}))
        assert last == {"error": "tool_call_limit"}
    outcomes = [t["outcome"] for t in o.trace]
    assert "tool_call_limit" in outcomes
    record = db[orch_mod.RUN_COLLECTION].find_one({"_id": o.request_id})
    assert record and record["toolCalls"] == len(o.trace) and record["role"] == "PATIENT"
    assert "args" not in json.dumps(record, default=str)


def test_s01h_tool_timeout_and_provider_loop_detection(db):
    o = AIOrchestrator(db, _user(db, "PATIENT"), None)

    async def slow(ctx, args):
        await asyncio.sleep(5)
        return {"late": True}

    with patch.object(orch_mod, "TOOL_TIMEOUT_SECONDS", 0.05), \
            patch.dict(TOOLS, {"p05_slow": Tool("test", Arguments, slow, frozenset({"PATIENT"}))}):
        assert run(o.execute("p05_slow", {}, {"p05_slow"})) == {"error": "tool_timeout"}

    provider = MagicMock()
    same = [{"name": "search_verified_doctors", "arguments": {"specialty": "Cardiology"}, "id": "1"}]
    provider.tool_turn.return_value = (same, {}, "")  # the model asks for the same call forever
    o2 = AIOrchestrator(db, _user(db, "PATIENT"), provider)
    result = run(o2.run_search("cardiologist", {"messages": []}, {}))
    assert provider.tool_turn.call_count <= 3  # stopped by loop detection, not by the round limit
    assert result is None or isinstance(result, tuple)


def test_mutating_tool_requires_server_side_confirmation(db):
    assert TOOLS["prepare_renewal_request"].mutates is True
    o = AIOrchestrator(db, _user(db, "PATIENT"), None)
    res = run(o.execute("prepare_renewal_request", {"original_prescription_id": "x", "medication_name": "y",
                                                    "reason": "z"}, {"prepare_renewal_request"}))
    assert res == {"error": "confirmation_required"}
    read_only = [n for n, t in TOOLS.items() if t.mutates]
    assert read_only == ["prepare_renewal_request"]  # every other registry tool is read-only


def test_admin_and_doctor_tools_never_mutate(db):
    for name, tool in TOOLS.items():
        if "ADMIN" in tool.roles or "DOCTOR" in tool.roles:
            assert not tool.mutates, name


# ------------------------------------------------------------------------------------------------ S-02
class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


@pytest.fixture
def fresh_metrics(db):
    AIProviderMonitoringService.reset()
    db[gw.COLLECTION].delete_many({})
    yield
    AIProviderMonitoringService.reset()


GEMINI_OK = {"candidates": [{"content": {"parts": [{"text": json.dumps({"specialty": "Cardiologist"})}]}}],
             "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 9}}
OPENAI_OK = {"choices": [{"message": {"content": json.dumps({"specialty": "Cardiologist"})}}],
             "usage": {"prompt_tokens": 30, "completion_tokens": 7}}


def test_s02a_gemini_adapter_key_in_header_and_metrics_recorded(fresh_metrics):
    from app.agents.ai_provider import GeminiAIProvider
    with patch.object(gw.requests, "post", return_value=_Resp(200, GEMINI_OK)) as post:
        parsed, source = GeminiAIProvider("test-key-not-real", "gemini-1.5-flash").parse_request("heart doctor")
    assert source == "gemini" and parsed["specialty"] == "Cardiologist"
    url, kwargs = post.call_args[0][0], post.call_args[1]
    assert "key=" not in url and "test-key-not-real" not in url
    assert kwargs["headers"]["x-goog-api-key"] == "test-key-not-real"
    # Retired id remapped, and reported. A01 changed the target from the alias gemini-flash-latest (whose target the
    # Gemini docs no longer state) to the pinned stable gemini-3.8-flash, confirmed with a live model lookup.
    assert "gemini-3.8-flash" in url
    today = gw._db()[gw.COLLECTION].find_one({"_id": gw._day_key("gemini")})
    assert today["successes"] == 1 and today["promptTokens"] == 40 and today["completionTokens"] == 9
    assert "heart doctor" not in json.dumps(today, default=str)  # no prompt text stored


def test_s02b_openai_adapter(fresh_metrics):
    from app.agents.ai_provider import OpenAIAIProvider
    with patch.object(gw.requests, "post", return_value=_Resp(200, OPENAI_OK)) as post:
        parsed, source = OpenAIAIProvider("test-key-not-real", "gpt-4o-mini").parse_request("heart doctor")
    assert source == "openai" and post.call_args[1]["headers"]["Authorization"] == "Bearer test-key-not-real"


@pytest.mark.parametrize("status,category", [(401, "auth_failed"), (403, "auth_failed"), (429, "rate_limited"),
                                             (404, "invalid_model"), (503, "server_error")])
def test_s02cde_failure_categories_and_deterministic_fallback(fresh_metrics, status, category):
    from app.agents.ai_provider import GeminiAIProvider
    with patch.object(gw.requests, "post", return_value=_Resp(status, {"error": {"message": "model x"}})) as post:
        parsed, source = GeminiAIProvider("k", "gemini-flash-latest").parse_request("cardiologist in Colombo")
    assert source.startswith("deterministic")  # S-02g
    assert post.call_count == (2 if category in {"rate_limited", "server_error"} else 1)  # bounded retry
    today = gw._db()[gw.COLLECTION].find_one({"_id": gw._day_key("gemini")})
    assert today[f"failure_{category}"] == 1 and today["fallbacks"] == 1


def test_s02d_timeout_is_classified_and_not_retried(fresh_metrics):
    with patch.object(gw.requests, "post", side_effect=requests.Timeout()) as post:
        with pytest.raises(gw.ProviderCallError) as exc:
            gw.send("openai", "gpt-4o-mini", "https://x.invalid", {}, {}, 1)
    assert exc.value.category == "timeout" and post.call_count == 1


def test_s02f_invalid_structured_output_falls_back(fresh_metrics):
    from app.agents.ai_provider import GeminiAIProvider
    broken = {"candidates": [{"content": {"parts": [{"text": "not json at all"}]}}]}
    with patch.object(gw.requests, "post", return_value=_Resp(200, broken)):
        _, source = GeminiAIProvider("k").parse_request("cardiologist")
    assert source.startswith("deterministic")


def test_s02h_usage_limit_circuit_breaker_and_status(fresh_metrics):
    with patch.object(settings, "AI_DAILY_REQUEST_LIMIT", 2), \
            patch.object(gw.requests, "post", return_value=_Resp(200, OPENAI_OK)) as post:
        gw.send("openai", "m", "https://x.invalid", {}, {}, 1)
        gw.send("openai", "m", "https://x.invalid", {}, {}, 1)
        with pytest.raises(gw.ProviderCallError) as exc:
            gw.send("openai", "m", "https://x.invalid", {}, {}, 1)
        assert exc.value.category == "usage_limit" and post.call_count == 2  # third call never sent
    with patch.object(settings, "AI_DAILY_REQUEST_LIMIT", 0):
        with pytest.raises(gw.ProviderCallError) as exc:
            gw.send("openai", "m", "https://x.invalid", {}, {}, 1)
        assert exc.value.category == "disabled"
    with patch.object(gw.requests, "post", return_value=_Resp(500, {})) as post:
        for _ in range(AIProviderMonitoringService.FAILURE_THRESHOLD):
            with pytest.raises(gw.ProviderCallError):
                gw.send("gemini", "m", "https://x.invalid", {}, {}, 1)
        calls_before = post.call_count
        with pytest.raises(gw.ProviderCallError) as exc:
            gw.send("gemini", "m", "https://x.invalid", {}, {}, 1)
        assert exc.value.category == "circuit_open" and post.call_count == calls_before


def test_s02h_status_vocabulary(fresh_metrics):
    with patch.object(settings, "GEMINI_API_KEY", ""):
        assert gw.provider_status("gemini")["status"] == "not_configured"
    with patch.object(settings, "GEMINI_API_KEY", "k"):
        assert gw.provider_status("gemini")["status"] == "configured_not_verified"
        with patch.object(gw.requests, "post", return_value=_Resp(200, GEMINI_OK)):
            gw.send("gemini", "m", "https://x.invalid", {}, {}, 1)
        assert gw.provider_status("gemini")["status"] == "available"
        with patch.object(gw.requests, "post", return_value=_Resp(401, {})):
            with pytest.raises(gw.ProviderCallError):
                gw.send("gemini", "m", "https://x.invalid", {}, {}, 1)
        assert gw.provider_status("gemini")["status"] == "unavailable"
        with patch.object(settings, "AI_DAILY_REQUEST_LIMIT", 0):
            assert gw.provider_status("gemini")["status"] == "disabled"
    with patch.object(settings, "OPENAI_API_KEY", "k"), \
            patch.object(gw.requests, "post", return_value=_Resp(429, {})):
        with pytest.raises(gw.ProviderCallError):
            gw.send("openai", "m", "https://x.invalid", {}, {}, 1)
        assert gw.provider_status("openai")["status"] == "rate_limited"


def test_s08a_admin_sees_measured_provider_status_and_ai_runs(db, fresh_metrics):
    admin = _admin(db)
    res = client.get("/api/security/monitoring/ai-providers", headers=_auth(admin))
    assert res.status_code == 200
    rows = {r["provider"]: r for r in res.json()}
    assert set(rows) >= {"gemini", "openai"}
    for row in rows.values():
        assert row["status"] in {"not_configured", "configured_not_verified", "available", "rate_limited",
                                 "degraded", "unavailable", "disabled"}
    client.post("/api/admin/workflow/assistant", json={"message": "Show notification failures."}, headers=_auth(admin))
    snap = client.get("/api/security/monitoring/platform", headers=_auth(admin)).json()
    assert snap["aiAgentRuns24h"]["runs"] >= 1
