"""Phase 01 regression tests: patient AI intelligence and clinical safety.

Each test names the Phase 01 defect it guards (see docs/uat/phase-01/PHASE_01_BUG_FIX_REPORT.md). These are software
regression tests; they are not clinical validation of the triage or medicine content.
"""

import time
from unittest.mock import MagicMock, patch

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.agents import clinical_intent
from app.agents.ai_provider import DeterministicNLPProvider
from app.agents.doctor_ranking import rank_doctors
from app.agents.emergency_detector import (
    SELF_HARM_GUIDANCE_EN,
    SELF_HARM_GUIDANCE_SI,
    crisis_metadata,
    detect_emergency,
    emergency_message,
    informational_message,
)
from app.agents.intent_proposal import propose_preferences, redact
from app.agents.medicine_knowledge import MedicineKnowledge
from app.agents.nlp_parser import detect_language, extract_max_fee, parse_query_deterministically
from app.config.database import get_database
from app.main import app
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.review import get_review_collection
from app.models.user import AccountStatus, UserRole, utc_now
from app.routes.ai_booking import _RATE_LIMIT_BUCKET
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(autouse=True)
def deterministic_provider():
    _RATE_LIMIT_BUCKET.clear()
    with patch("app.agents.booking_agent.get_ai_provider", return_value=DeterministicNLPProvider()):
        yield


# ---------------------------------------------------------------------------
# P01-EMERG: emergency detection matrix (unit)
# ---------------------------------------------------------------------------
POSITIVE = [
    ("I have severe chest pain and difficulty breathing. What should I do?", "cardiac"),
    ("mata papuwa godak ridenawa. husma gannath amarui. mama mokakda karanna one?", "cardiac"),
    ("මගේ පපුව ගොඩක් රිදෙනවා. හුස්ම ගන්නත් අමාරුයි. මම මොකද කරන්න ඕනේ?", "cardiac"),
    ("thaththa sihiya nathi wuna", "unconscious"),
    ("mata marenna hithenawa", "self_harm"),
    ("I want to kill myself", "self_harm"),
    ("I accidentally took 10 paracetamol tablets", "poisoning"),
    ("my son swallowed some tablets", "poisoning"),
    ("My father collapsed and is not breathing", "unconscious"),
    ("I think I am having a heart attack", "cardiac"),
    ("what are the symptoms of a heart attack, I have chest pain right now", "cardiac"),
    ("How can I tell if I am having a heart attack? my chest hurts", "cardiac"),
    ("what if I want to end my life", "self_harm"),
]


@pytest.mark.parametrize("text,category", POSITIVE)
def test_p01_emergency_positive(text, category):
    result = detect_emergency(text)
    assert result.is_emergency and result.category == category


@pytest.mark.parametrize("text,suppressed", [
    ("I have no chest pain, just a cough.", "negated"),
    ("I had chest pain last year but I am fine now", "historical"),
    ("What are the common symptoms of a heart attack?", "informational"),
    ("What causes a stroke?", "informational"),
    ("Is a stroke dangerous?", "informational"),
    ("What should I do if someone has chest pain?", "hypothetical"),
    ("What are the warning signs of suicide?", "informational"),
])
def test_p01_informational_negated_historical_not_alarmed(text, suppressed):
    result = detect_emergency(text)
    assert not result.is_emergency and result.suppressed == suppressed


@pytest.mark.parametrize("text", ["How can I prevent heart disease?", "I took 2 paracetamol tablets for headache",
                                  "What happens when a lung collapses?"])
def test_p01_no_false_alarm(text):
    assert not detect_emergency(text).is_emergency


def test_p01_context_keeps_emergency_including_informational_follow_up():
    assert detect_emergency("What should I do?", ["My chest is very tight."]).is_emergency
    # An informational question right after a current symptom stays escalated (do not weaken detection).
    assert detect_emergency("What are the symptoms of a heart attack?", ["My chest is very tight."]).is_emergency


# ---------------------------------------------------------------------------
# P01-GUIDE: category-specific and mental-health guidance (BUG-044, P01-BUG-SELFHARM-UI)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text,needle", [
    ("my face is drooping and my speech is slurred", "time the symptoms started"),
    ("I was bitten by a snake", "do not cut, suck or tie"),
    ("I accidentally took 10 paracetamol tablets", "even if you feel well"),
    ("she is having a seizure", "do not put anything in their mouth"),
    ("heavy bleeding from my leg", "press firmly"),
])
def test_p01_guidance_is_category_specific(text, needle):
    message = emergency_message(detect_emergency(text), "en")
    assert "1990" in message and needle in message.lower()


def test_p01_categories_do_not_share_identical_guidance():
    texts = ["I have severe chest pain", "I was bitten by a snake", "my face is drooping and my speech is slurred"]
    messages = {emergency_message(detect_emergency(t), "en") for t in texts}
    assert len(messages) == 3


@pytest.mark.parametrize("text", ["I want to kill myself", "mata marenna hithenawa", "මට මැරෙන්න හිතෙනවා"])
def test_p01_self_harm_response_is_supportive_and_verified(text):
    result = detect_emergency(text)
    lang = "si" if detect_language(text) == "si" else "en"
    message = emergency_message(result, lang)
    assert message in (SELF_HARM_GUIDANCE_EN, SELF_HARM_GUIDANCE_SI)
    for number in ("1926", "1333", "1990"):
        assert number in message
    assert "011 2 696 666" not in message  # unverified number removed
    meta = crisis_metadata(result)
    assert meta["crisisType"] == "mental_health"
    assert [line["number"] for line in meta["supportLines"]] == ["1926", "1333"]


def test_p01_self_harm_english_text_safety_elements():
    text = SELF_HARM_GUIDANCE_EN.lower()
    assert "are you safe right now" in text
    assert "someone you trust" in text and "not to be alone" in text
    assert "move away from anything you could use to hurt yourself" in text
    assert "automated assistant" in text  # does not imply the chatbot resolves the crisis


def test_p01_informational_message_has_conditional_escalation():
    message = informational_message(detect_emergency("What are the common symptoms of a heart attack?"), "en")
    assert "chest pain" in message and "If you or someone near you has these symptoms now, call 1990" in message


# ---------------------------------------------------------------------------
# P01-COUGH: tiered cough guidance
# ---------------------------------------------------------------------------
def test_p01_long_cough_is_doctor_soon_not_ambulance():
    advice = clinical_intent.build_symptom_advice("I have had a cough for three weeks", "en").text
    soon, emergency = advice.split("**Call 1990 or go to the nearest ETU now if you have:**")
    assert "a cough lasting 3 weeks or more" in soon
    assert "3 weeks" not in emergency.split("**When to see a doctor:**")[0]
    assert "not an ambulance emergency" in advice


def test_p01_prevention_question_gets_information():
    info = clinical_intent.general_health_information("How can I prevent heart disease?", "en")
    assert info and info["topic"] == "heart_disease" and "smoke" in info["text"]
    assert clinical_intent.general_health_information("Find a cardiologist in Colombo", "en") is None


# ---------------------------------------------------------------------------
# P01-PARSE / P01-SELECT: understanding follow-ups
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text,fee", [("Increase my budget to LKR 3000.", 3000), ("raise the limit to 5000", 5000),
                                      ("change the maximum fee to Rs. 2500", 2500), ("my budget is LKR 4000", 4000)])
def test_p01_budget_change_parsed(text, fee):
    assert extract_max_fee(text) == fee


def test_p01_plural_specialty_parsed():
    assert parse_query_deterministically("Show me all cardiologists in Colombo")["specialty"] == "Cardiologist"


@pytest.mark.parametrize("text", [
    "Select the most experienced doctor from these two doctors and explain why you selected that doctor.",
    "Select only one doctor and explain why you selected that doctor.",
    "Which one should I choose?", "pick the cheapest one", "Give me a single doctor",
])
def test_p01_selection_requests_recognised(text):
    assert clinical_intent.wants_auto_selection(text)


@pytest.mark.parametrize("text", ["Show me all cardiologists in Colombo", "Find a cardiologist in Colombo",
                                  "show me more options"])
def test_p01_not_selection(text):
    assert not clinical_intent.wants_auto_selection(text)


def test_p01_small_review_count_does_not_outrank_established_rating():
    doctors = [
        {"doctorId": "a", "fullName": "One Review", "rating": 5.0, "ratingCount": 1, "experienceYears": 5},
        {"doctorId": "b", "fullName": "Many Reviews", "rating": 4.7, "ratingCount": 30, "experienceYears": 5},
        {"doctorId": "c", "fullName": "No Reviews", "rating": None, "ratingCount": 0, "experienceYears": 40},
    ]
    assert [d["doctorId"] for d in rank_doctors(doctors, {})] == ["b", "a", "c"]


@pytest.mark.parametrize("text", ["mata marenna hithenawa", "thaththa sihiya nathi wuna"])
def test_p01_romanized_crisis_language_detected(text):
    assert detect_language(text) == "si"


@pytest.mark.parametrize("text", ["I want to eat healthy food", "Find a cardiologist in Colombo"])
def test_p01_english_not_misdetected(text):
    assert detect_language(text) == "en"


# ---------------------------------------------------------------------------
# P01-MED: concise medicine text (no duplication of the card) and situation notes
# ---------------------------------------------------------------------------
def test_p01_medicine_text_does_not_repeat_card():
    response = MedicineKnowledge.generate_educational_response("What is paracetamol used for?")
    assert "Paracetamol (Paracetamol" not in response["text"]
    assert "Available strengths" not in response["text"]
    assert "500 mg" not in response["text"]
    assert response["card"]["formulations"] and response["card"]["commonUses"]


@pytest.mark.parametrize("text,needle", [
    ("Can I give paracetamol to my 2 year old child?", "For a child"),
    ("Is ibuprofen safe during pregnancy?", "During pregnancy"),
    ("Can I take paracetamol with liver disease?", "Liver or kidney disease"),
    ("Can I take paracetamol together with ibuprofen tablets?", "more than one medicine"),
])
def test_p01_medicine_situation_notes(text, needle):
    assert needle in MedicineKnowledge.generate_educational_response(text)["text"]


# ---------------------------------------------------------------------------
# P01-LLM: bounded LLM-assisted preference proposals (mocked providers; NOT live provider verification)
# ---------------------------------------------------------------------------
def test_p01_llm_layer_inactive_with_deterministic_provider():
    assert propose_preferences(DeterministicNLPProvider(), "a heart doctor near the capital") == ({}, "deterministic")


def _provider(result=None, error=None):
    provider = MagicMock()
    provider.parse_request.side_effect = error
    if error is None:
        provider.parse_request.return_value = result
    return provider


def test_p01_llm_valid_proposal_accepted():
    provider = _provider(({"specialty": "cardiologist", "city": "colombo", "maxFee": 3000, "sortBy": "rating_desc"}, "gemini"))
    proposal, source = propose_preferences(provider, "heart doctor in the capital, not too expensive")
    assert source == "llm_proposal"
    assert proposal == {"specialty": "Cardiologist", "city": "Colombo", "maxFee": 3000.0, "sortBy": "rating_desc"}


def test_p01_llm_invalid_fields_rejected():
    provider = _provider(({"specialty": "Astrologer", "city": "Antarctica", "maxFee": 5, "minRating": 9,
                           "sortBy": "random", "date": "2001-01-01", "bookAndPay": True, "doctorId": "x"}, "openai"))
    assert propose_preferences(provider, "anything") == ({}, "provider_unavailable")


def test_p01_llm_failure_falls_back():
    assert propose_preferences(_provider(error=TimeoutError()), "x") == ({}, "provider_unavailable")
    assert propose_preferences(_provider(({"specialty": "Cardiologist"}, "deterministic_fallback")), "x")[1] == "provider_unavailable"


def test_p01_llm_input_redacted():
    text = redact("my name is Nimal Perera, email nimal@example.com, phone 0771234567, NIC 199012345678")
    for secret in ("Nimal", "nimal@example.com", "0771234567", "199012345678"):
        assert secret not in text


# ---------------------------------------------------------------------------
# API integration through /ai/conversations and /ai/health-chat (local MongoDB, deterministic provider)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def env():
    db = get_database()

    def cleanup():
        profiles = list(db["doctor_profiles"].find({"doctorId": {"$regex": "^P01-"}}, {"userId": 1}))
        users = [p["userId"] for p in profiles]
        db["doctor_profiles"].delete_many({"doctorId": {"$regex": "^P01-"}})
        db["users"].delete_many({"_id": {"$in": [ObjectId(u) for u in users if ObjectId.is_valid(u)]}})
        get_review_collection(db).delete_many({"doctorUserId": {"$in": users}})

    cleanup()
    ts = int(time.time() * 1000)
    patients = []
    for index in range(2):
        pid = ObjectId()
        db["users"].insert_one({
            "_id": pid, "fullName": f"Phase01 Patient {index}", "email": f"p01_patient{index}_{ts}@mediconnect.lk",
            "phone": "0771234567", "passwordHash": hash_password("Password@123"), "role": UserRole.PATIENT.value,
            "emailVerified": True, "accountStatus": AccountStatus.ACTIVE.value, "createdAt": utc_now(), "updatedAt": utc_now(),
        })
        patients.append(pid)

    def doctor(name, specialty, fee, years, ratings=(), status=DoctorVerificationStatus.APPROVED.value):
        uid, pid = ObjectId(), ObjectId()
        db["users"].insert_one({
            "_id": uid, "fullName": name, "email": f"{uid}@mediconnect.lk", "passwordHash": "x",
            "role": UserRole.DOCTOR.value, "emailVerified": True, "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": utc_now(), "updatedAt": utc_now(),
        })
        db["doctor_profiles"].insert_one({
            "_id": pid, "userId": str(uid), "doctorId": f"P01-{uid}", "medicalRegistrationNumber": f"SLMC-P01-{uid}",
            "specialty": specialty, "hospitalOrClinic": "Negombo Care Centre", "city": "Negombo", "experienceYears": years,
            "consultationFee": fee, "verificationStatus": status, "createdAt": utc_now(), "updatedAt": utc_now(),
        })
        for value in ratings:
            get_review_collection(db).insert_one({
                "reviewId": f"REV-{ObjectId()}", "doctorUserId": str(uid), "doctorProfileId": str(pid),
                "patientUserId": str(ObjectId()), "appointmentId": str(ObjectId()), "rating": value, "status": "PUBLISHED",
                "createdAt": utc_now(), "updatedAt": utc_now(),
            })
        return f"P01-{uid}"

    ids = {
        "derm_senior": doctor("Dr. P01 Derm Senior", "Dermatology", 3000.0, 22, (5, 4, 5)),
        "derm_junior": doctor("Dr. P01 Derm Junior", "Dermatology", 3500.0, 6, (5, 5, 4)),
        "derm_third": doctor("Dr. P01 Derm Third", "Dermatology", 2500.0, 10, (4, 4, 4)),
        "derm_pending": doctor("Dr. P01 Derm Unverified", "Dermatology", 1000.0, 40, (5, 5, 5),
                               status=DoctorVerificationStatus.PENDING.value),
        "card": doctor("Dr. P01 Cardio", "Cardiology", 2800.0, 12, (5, 4)),
    }
    headers = [{"Authorization": f"Bearer {create_access_token(str(p), UserRole.PATIENT.value)}"} for p in patients]
    yield {"headers": headers[0], "other_headers": headers[1], "ids": ids}
    cleanup()
    db["users"].delete_many({"_id": {"$in": patients}})


def new_chat(env, headers=None):
    headers = headers or env["headers"]
    resp = client.post("/api/ai/conversations", json={}, headers=headers)
    assert resp.status_code == 201, resp.text
    conversation_id = resp.json()["id"]
    client.patch(f"/api/ai/conversations/{conversation_id}", json={"title": f"t{time.time_ns()}"}, headers=headers)
    return conversation_id


def say(env, conversation_id, text, headers=None):
    resp = client.post(f"/api/ai/conversations/{conversation_id}/messages", json={"message": text},
                       headers=headers or env["headers"])
    assert resp.status_code == 200, resp.text
    return resp.json()


def last(data):
    return data["messages"][-1]


def shown_ids(data):
    return [d["doctorId"] for d in last(data)["metadata"].get("doctors") or []]


def test_p01_scenario_a_unsupported_location_then_colombo_keeps_context(env):
    chat = new_chat(env)
    first = say(env, chat, "Find me a cardiologist in Antarctica with a consultation fee below LKR 3000.")
    assert last(first)["metadata"]["type"] == "unsupported_location"
    assert first["preferences"]["specialty"] == "Cardiologist" and first["preferences"]["maxFee"] == 3000
    data = say(env, chat, "Search in Negombo instead.")
    prefs = data["preferences"]
    assert prefs["specialty"] == "Cardiologist" and prefs["city"] == "Negombo" and prefs["maxFee"] == 3000
    assert env["ids"]["card"] in shown_ids(data)


def test_p01_scenario_b_budget_increase_after_empty_result(env):
    chat = new_chat(env)
    empty = say(env, chat, "Find me a cardiologist in Negombo with a consultation fee below LKR 100.")
    assert last(empty)["metadata"]["type"] == "no_results"
    data = say(env, chat, "Increase my budget to LKR 3000.")
    prefs = data["preferences"]
    assert prefs["specialty"] == "Cardiologist" and prefs["city"] == "Negombo" and prefs["maxFee"] == 3000
    assert shown_ids(data) == [env["ids"]["card"]]


@pytest.mark.parametrize("follow_up", [
    "Select the most experienced doctor from these two doctors and explain why you selected that doctor.",
    "Select only one doctor and explain why you selected that doctor.",
    "Which one should I choose?",
])
def test_p01_scenario_c_selects_exactly_one(env, follow_up):
    chat = new_chat(env)
    first = say(env, chat, "Find me a dermatologist in Negombo with a consultation fee below LKR 4000 and a patient "
                           "rating of at least 4.5. Prioritize doctors with the most experience.")
    assert set(shown_ids(first)) == {env["ids"]["derm_senior"], env["ids"]["derm_junior"]}
    data = say(env, chat, follow_up)
    message = last(data)
    assert message["metadata"]["type"] == "doctor_auto_selected"
    assert shown_ids(data) == [env["ids"]["derm_senior"]]
    assert "22 years" in message["content"] and "Dr. P01 Derm Junior" in message["content"]
    assert "not a judgement of clinical quality" in message["content"]


def test_p01_recommendation_defaults_to_top_two_and_show_all(env):
    chat = new_chat(env)
    data = say(env, chat, "Recommend a good dermatologist in Negombo")
    meta = last(data)["metadata"]
    assert len(shown_ids(data)) == 2 and meta["totalMatches"] == 3
    assert env["ids"]["derm_pending"] not in shown_ids(data)  # unverified doctors are never recommended
    everything = say(env, chat, "show all")
    assert len(shown_ids(everything)) == 3 and env["ids"]["derm_pending"] not in shown_ids(everything)


def test_p01_show_me_all_with_plural_specialty_searches(env):
    data = say(env, new_chat(env), "Show me all dermatologists in Negombo")
    assert len(shown_ids(data)) == 3


def test_p01_named_doctor_slots_request_searches(env):
    data = say(env, new_chat(env), "Show me all available appointment slots for Dr. P01 Cardio on November 26, 2030.")
    assert "Which doctor should I look up" not in last(data)["content"]
    assert shown_ids(data) == [env["ids"]["card"]]
    assert data["preferences"]["date"] == "2030-11-26"


def test_p01_unrelated_city_question_is_not_search(env):
    chat = new_chat(env)
    say(env, chat, "Find a cardiologist in Negombo")
    data = say(env, chat, "What is the weather in Colombo?")
    assert last(data)["metadata"]["type"] == "clarification_needed"


def test_p01_new_chat_resets_context(env):
    chat = new_chat(env)
    say(env, chat, "Find a dermatologist in Negombo under LKR 4000")
    fresh = say(env, new_chat(env), "Increase my budget to LKR 3000.")
    assert not fresh["preferences"].get("specialty") and not fresh["preferences"].get("city")


def test_p01_conversation_is_not_visible_to_another_patient(env):
    chat = new_chat(env)
    say(env, chat, "Find a dermatologist in Negombo")
    other = client.post(f"/api/ai/conversations/{chat}/messages", json={"message": "show all"},
                        headers=env["other_headers"])
    assert other.status_code in (403, 404)


def test_p01_informational_question_api_no_alarm(env):
    data = say(env, new_chat(env), "What are the common symptoms of a heart attack?")
    message = last(data)
    assert message["metadata"]["type"] == "emergency_information"
    assert not data.get("isUrgent")
    assert "call 1990" in message["content"]


def test_p01_overdose_api_escalates(env):
    data = say(env, new_chat(env), "I accidentally took 10 paracetamol tablets")
    message = last(data)
    assert data["isUrgent"] and message["metadata"]["category"] == "poisoning"
    assert not data.get("activeMedicineCard")


def test_p01_self_harm_api_mental_health_metadata(env):
    data = say(env, new_chat(env), "mata marenna hithenawa")
    meta = last(data)["metadata"]
    assert meta["crisisType"] == "mental_health" and meta["category"] == "self_harm"
    assert "1926" in last(data)["content"] and "1333" in last(data)["content"]


def test_p01_health_chat_entry_point(env):
    def session():
        resp = client.post("/api/ai/health-chat/sessions", json={"language": "en", "consentGiven": True},
                           headers=env["headers"])
        assert resp.status_code in (200, 201), resp.text
        return resp.json()["id"]

    def ask(text):
        resp = client.post(f"/api/ai/health-chat/sessions/{session()}/messages", json={"message": text},
                           headers=env["headers"])
        assert resp.status_code == 200, resp.text
        return resp.json()["messages"][-1]

    info = ask("What are the common symptoms of a heart attack?")
    assert info["metadata"]["isUrgent"] is False and info["metadata"]["conditionalEmergency"]
    crisis = ask("I want to kill myself")
    assert crisis["metadata"]["isUrgent"] and crisis["metadata"]["crisisType"] == "mental_health"
    cardiac = ask("I have severe chest pain and difficulty breathing")
    assert cardiac["metadata"]["isUrgent"] and cardiac["metadata"]["category"] == "cardiac"
