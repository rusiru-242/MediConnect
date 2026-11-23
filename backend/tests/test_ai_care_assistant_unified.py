"""Comprehensive tests for Phase 39 Unified MediConnect AI Care Assistant."""

import pytest
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.config.database import get_database
from app.agents.nlp_parser import (
    extract_max_fee,
    extract_ordinal_doctor_index,
    extract_sort_preference,
    extract_symptoms,
    parse_query_deterministically,
)
from app.agents.booking_agent import BookingAgent
from app.models.booking_session import BookingAgentState


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_nlp_parser_unified_intent_extraction():
    """Verify natural language understanding of symptoms, budgets, ordinals, and sorting."""
    # 1. Budget extraction
    assert extract_max_fee("My budget is LKR 3,000.") == 3000.0
    assert extract_max_fee("my budget is 3500") == 3500.0
    assert extract_max_fee("fee under LKR 2,500") == 2500.0

    # 2. Ordinal doctor selection
    assert extract_ordinal_doctor_index("I want to book the second doctor") == 1
    assert extract_ordinal_doctor_index("select the 1st doctor") == 0
    assert extract_ordinal_doctor_index("book doctor 3") == 2
    assert extract_ordinal_doctor_index("the first one") == 0

    # 3. Sorting preferences
    assert extract_sort_preference("Show me doctors with lower consultation fees") == "fee_asc"
    assert extract_sort_preference("Find a cheaper doctor") == "fee_asc"
    assert extract_sort_preference("Show top rated doctors") == "rating_desc"

    # 4. Symptoms extraction
    sym = extract_symptoms("I have a severe headache and fever")
    assert sym is not None
    assert "headache" in sym.lower()

    # 5. Full parse query deterministically
    parsed = parse_query_deterministically("I have a headache for three days in Colombo under LKR 3000")
    assert parsed["city"] == "Colombo"
    assert parsed["maxFee"] == 3000.0
    assert parsed["specialty"] is not None


@pytest.mark.anyio
async def test_care_assistant_conversational_turn_handling():
    """Verify BookingAgent processes symptoms, ordinals, and comparisons in session data."""
    # Mock database
    class FakeDB:
        def __init__(self):
            self.doctor_profiles = FakeColl([])
            self.users = FakeColl([])
            self.doctor_availabilities = FakeColl([])
            self.appointments = FakeColl([])

        def __getitem__(self, name):
            return getattr(self, name)

    class FakeColl:
        def __init__(self, items):
            self.items = items
        def find(self, *args, **kwargs):
            return self
        def limit(self, n):
            return self.items[:n]
        def sort(self, *args, **kwargs):
            return self
        def find_one(self, *args, **kwargs):
            return None

    db = FakeDB()

    # 1. Emergency test
    urgent_session = {
        "state": BookingAgentState.COLLECTING_PREFERENCES.value,
        "preferences": {"language": "en"},
        "messages": [],
    }
    res_urgent = await BookingAgent.process_user_turn(db, urgent_session, "I have severe sudden chest pain and numbness")
    assert res_urgent.get("isUrgent") is True
    assert "1990" in res_urgent["messages"][-1]["content"]

    # 2. Doctor comparison test
    comparison_session = {
        "state": BookingAgentState.AWAITING_DOCTOR_SELECTION.value,
        "preferences": {"language": "en", "specialty": "Cardiologist"},
        "candidateDoctors": [
            {
                "doctorId": "DOC-1",
                "fullName": "Dr. Sunil Perera",
                "specialty": "Cardiologist",
                "qualifications": "MBBS, MD - Cardiology",
                "hospitalOrClinic": "Asiri Central Hospital",
                "consultationFee": 3000.0,
                "experienceYears": 15,
                "rating": 4.9,
                "matchScore": 95.0,
            },
            {
                "doctorId": "DOC-2",
                "fullName": "Dr. Anura Silva",
                "specialty": "Cardiologist",
                "qualifications": "MBBS, MRCP",
                "hospitalOrClinic": "Durdans Hospital",
                "consultationFee": 2500.0,
                "experienceYears": 10,
                "rating": 4.7,
                "matchScore": 90.0,
            },
        ],
        "messages": [],
    }
    res_comp = await BookingAgent.process_user_turn(db, comparison_session, "Can you compare these doctors?")
    assert "side-by-side comparison" in res_comp["messages"][-1]["content"]
    assert "Dr. Sunil Perera" in res_comp["messages"][-1]["content"]
    assert "Dr. Anura Silva" in res_comp["messages"][-1]["content"]

    # 3. Ordinal doctor selection test ("I want to book the second doctor")
    res_ord = await BookingAgent.process_user_turn(db, comparison_session, "I want to book the second doctor")
    assert res_ord.get("selectedDoctor") is not None
    assert res_ord["selectedDoctor"]["fullName"] == "Dr. Anura Silva"
    assert res_ord["state"] == BookingAgentState.AWAITING_SLOT_SELECTION.value

    # 4. Reset / Cancel test
    res_reset = await BookingAgent.process_user_turn(db, res_ord, "cancel")
    assert res_reset.get("selectedDoctor") is None
    assert res_reset["state"] == BookingAgentState.COLLECTING_PREFERENCES.value

