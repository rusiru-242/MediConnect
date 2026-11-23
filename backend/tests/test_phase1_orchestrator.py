"""Phase 1 tests use mocked provider and service boundaries."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.ai_provider import GeminiAIProvider, OpenAIAIProvider
from app.agents.nlp_parser import extract_appointment_time, extract_date
from app.agents.orchestrator import AIOrchestrator, context_messages, redact
from app.agents.tool_registry import TOOLS
from app.services.booking_session_service import BookingSessionService
from bson import ObjectId
from fastapi import HTTPException


def actor(role="PATIENT", id="patient-a"):
    return SimpleNamespace(role=role, id=id)


def reply(name, args):
    return ([{"name": name, "arguments": args, "id": "call-id"}], {}, "")


@pytest.mark.anyio
async def test_registry_rejects_unknown_tools_invalid_arguments_and_roles():
    patient = AIOrchestrator(None, actor(), None)
    names = set(TOOLS)
    assert set(patient.authorized(names)) == names
    for role in ("DOCTOR", "ADMIN"):
        orch = AIOrchestrator(None, actor(role), None)
        assert orch.authorized(names) == {}
        assert await orch.execute("get_patient_appointments", {}, names) == {"error": "tool_unavailable"}
    assert await patient.execute("shell", {}, names) == {"error": "tool_unavailable"}
    assert await patient.execute("get_patient_appointments", {"patient_id": "other"}, names) == {
        "error": "invalid_arguments",
    }
    assert await patient.execute("check_doctor_availability", {
        "doctor_id": "DOC-1", "requested_date": "2026-02-30",
    }, names) == {"error": "invalid_arguments"}


@pytest.mark.anyio
async def test_uses_server_filters_real_slots_and_safe_provider_results(monkeypatch):
    from app.agents import tool_registry
    from app.agents.tool_registry import DoctorService

    monkeypatch.setattr(tool_registry, "get_sl_today_str", lambda: "2026-11-23")
    doctor = SimpleNamespace(doctorId="DOC-1", fullName="Dr Test", specialty="Neurology",
                             hospitalOrClinic="Clinic, Colombo", profileImage="private-asset-reference")
    search = AsyncMock(return_value=SimpleNamespace(items=[doctor]))
    monkeypatch.setattr(DoctorService, "list_approved_doctors", search)
    monkeypatch.setattr(DoctorService, "get_approved_doctor_detail", AsyncMock(return_value=doctor))
    slot = SimpleNamespace(model_dump=lambda **kwargs: {
        "date": "2026-12-05", "startTime": "16:30", "endTime": "17:00", "availabilityId": "internal",
    })
    monkeypatch.setattr(DoctorService, "get_doctor_patient_slots", AsyncMock(
        return_value=SimpleNamespace(date="2026-12-05", slots=[slot]),
    ))
    received = []

    def turn(system, messages, definitions, exchanges):
        received.append((system, messages, definitions))
        if not exchanges:
            return reply("search_verified_doctors", {"city": "Kandy"})
        if len(exchanges) == 1:
            assert "private-asset-reference" not in str(exchanges)
            return reply("check_doctor_availability", {"doctor_id": "DOC-1", "requested_date": "2026-11-01"})
        assert "internal" not in str(exchanges)
        return [], {}, "I booked your appointment."

    session = {"messages": [{"content": "private symptoms", "metadata": {"type": "doctor_options"}}]}
    orch = AIOrchestrator(None, actor(), SimpleNamespace(tool_turn=turn))
    doctors, slots, final = await orch.run_search(
        "Patient email person@example.com", session, {"city": "Colombo"}, "2026-12-05", "16:00",
    )
    assert search.call_args.kwargs["city"] == "Colombo"
    assert doctors[0]["doctorId"] == "DOC-1"
    assert slots["DOC-1"]["slots"][0]["startTime"] == "16:30"
    assert final is None
    assert "private symptoms" not in str(received)
    assert "person@example.com" not in str(received)
    assert "get_patient_appointments" not in str(received)


@pytest.mark.anyio
async def test_round_limit_and_provider_failure(monkeypatch):
    from app.agents.tool_registry import DoctorService

    search = AsyncMock(return_value=SimpleNamespace(items=[]))
    monkeypatch.setattr(DoctorService, "list_approved_doctors", search)
    provider = SimpleNamespace(tool_turn=Mock(return_value=reply("search_verified_doctors", {})))
    orch = AIOrchestrator(None, actor(), provider)
    assert await orch.run_search("doctor", {}, {}) is None
    assert search.await_count == 3
    assert provider.tool_turn.call_count == 4
    provider.tool_turn = Mock(side_effect=TimeoutError)
    assert await orch.run_search("doctor", {}, {}) is None


@pytest.mark.anyio
async def test_private_reads_bind_authenticated_patient_and_hide_foreign_sessions(monkeypatch):
    from app.agents.tool_registry import AppointmentService

    patient = actor()
    read = AsyncMock(return_value=SimpleNamespace(items=[]))
    monkeypatch.setattr(AppointmentService, "list_patient_appointments", read)
    orch = AIOrchestrator(None, patient, None)
    assert await orch.execute("get_patient_appointments", {"from_date": "2026-12-05"}, set(TOOLS)) == {
        "appointments": [],
    }
    assert read.call_args.args[1] is patient
    assert read.call_args.kwargs["from_date"] == "2026-12-05"
    monkeypatch.setattr(BookingSessionService, "_get_session_or_404", Mock(side_effect=HTTPException(403)))
    assert await orch.execute("get_booking_session_status", {"session_id": str(ObjectId())}, set(TOOLS)) == {
        "error": "resource_unavailable",
    }


@pytest.mark.anyio
async def test_cancellation_error_never_saves_cancelled_chat(monkeypatch):
    from app.services.booking_session_service import AppointmentService

    appointment_id = ObjectId()
    session = {"appointmentId": str(appointment_id), "messages": [], "state": "AWAITING_PAYMENT"}
    collection = Mock()
    collection.find_one.return_value = {"status": "HOLD"}
    patient = actor()
    monkeypatch.setattr(BookingSessionService, "_get_session_or_404", Mock(return_value=session))
    save = Mock()
    monkeypatch.setattr(BookingSessionService, "_save", save)
    cancel = AsyncMock(side_effect=HTTPException(409))
    monkeypatch.setattr(AppointmentService, "cancel_patient_appointment", cancel)
    with pytest.raises(HTTPException):
        await BookingSessionService.cancel_session({"appointments": collection}, patient, str(ObjectId()))
    assert cancel.await_count == 1
    assert collection.find_one.call_args.args[0]["patientUserId"] == patient.id
    assert session["state"] == "AWAITING_PAYMENT"
    save.assert_not_called()


@pytest.mark.parametrize("gemini", [True, False])
def test_provider_native_function_exchange(gemini, monkeypatch):
    from app.agents import tool_provider

    tool = {"name": "search_verified_doctors", "description": "Search", "parameters": {"type": "object"}}
    content = {"role": "model", "parts": [{"functionCall": {
        "name": tool["name"], "args": {}, "id": "1",
    }, "thoughtSignature": "opaque"}]}
    openai_content = {"role": "assistant", "content": None, "tool_calls": [{
        "id": "1", "type": "function", "function": {"name": tool["name"], "arguments": "{}"},
    }]}
    wire = {"candidates": [{"content": content}]} if gemini else {"choices": [{"message": openai_content}]}
    post = Mock(return_value=wire)
    monkeypatch.setattr(tool_provider, "_post", post)
    provider = (GeminiAIProvider if gemini else OpenAIAIProvider)("test-only-placeholder")
    messages = [{"role": "user", "content": "Find a doctor"}]
    calls, native, _ = provider.tool_turn("System", messages, [tool], [])
    provider.tool_turn("System", messages, [tool], [(calls, native, [(calls[0], {"doctors": []})])])
    payload = post.call_args.args[2]
    if gemini:
        assert "functionDeclarations" in payload["tools"][0]
        assert payload["contents"][-2]["parts"][0]["thoughtSignature"] == "opaque"
        assert payload["contents"][-1]["parts"][0]["functionResponse"]["id"] == "1"
    else:
        assert payload["tools"][0]["type"] == "function"
        assert payload["messages"][-1]["tool_call_id"] == "1"


def test_colombo_date_time_and_context_minimization(monkeypatch):
    from app.agents import nlp_parser

    monkeypatch.setattr(nlp_parser, "get_sl_now", lambda: datetime(2027, 12, 6, tzinfo=timezone.utc))
    assert extract_date("mata December 5 hawasa 4ta doctor kenek book karanna") == "2028-12-05"
    assert extract_appointment_time("December 5 hawasa 4ta") == "16:00"
    assert extract_appointment_time("December 5 4pm ta") == "16:00"
    assert extract_date("heta mata appointment ekak thiyenawada") == "2027-12-07"
    assert not context_messages({})
    assert "person@example.com" not in redact("Contact person@example.com")


@pytest.mark.anyio
async def test_romanized_booking_search_attaches_authoritative_slots(monkeypatch):
    from app.agents import nlp_parser
    from app.agents.booking_agent import BookingAgent

    monkeypatch.setattr(nlp_parser, "get_sl_now", lambda: datetime(2026, 11, 23, tzinfo=timezone.utc))
    tool = AsyncMock(return_value=([{
        "doctorId": "DOC-1", "fullName": "Dr Test", "specialty": "Neurology",
    }], {"DOC-1": {"slots": [{
        "availabilityId": "slot-id", "date": "2026-12-05", "startTime": "16:00", "endTime": "16:30",
    }]}}, None))
    monkeypatch.setattr(AIOrchestrator, "run_search", tool)
    session = await BookingAgent.process_user_turn(
        None, {"messages": []}, "mata colombo walin neurologist kenek december 5 4pm ta one",
        patient_user=actor(),
    )
    assert session["activeIntent"] == "BOOK_APPOINTMENT"
    assert session["preferences"]["city"] == "Colombo"
    assert session["preferences"]["date"] == "2026-12-05"
    assert session["preferences"]["requestedTime"] == "16:00"
    assert session["candidateDoctors"][0]["availableSlots"][0]["startTime"] == "16:00"
    assert "appointmentId" not in session
