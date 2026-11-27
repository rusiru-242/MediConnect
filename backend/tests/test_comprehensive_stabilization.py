"""Regression tests for the comprehensive system / AI stabilization (BUG-001 … BUG-026).

Each test names the bug it guards. These are software regression tests only; they do not
constitute clinical validation of triage or medication content.
"""

from datetime import datetime, timezone
from decimal import Decimal
import time
from unittest.mock import patch

from bson import ObjectId
from bson.decimal128 import Decimal128
from fastapi.testclient import TestClient
import pytest

from app.agents import clinical_intent
from app.agents.ai_provider import DeterministicNLPProvider
from app.agents.doctor_ranking import coerce_fee, dedupe_doctors, rank_doctors
from app.agents.emergency_detector import detect_emergency
from app.agents.medicine_knowledge import MEDICINE_DATABASE, MedicineKnowledge
from app.agents.nlp_parser import (
    extract_location,
    extract_max_fee,
    extract_min_rating,
    extract_sort_preference,
    extract_specialty,
    extract_unsupported_location,
)
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
# BUG-013 — multilingual emergency detection (unit)
# ---------------------------------------------------------------------------
EMERGENCY_POSITIVE = [
    ("en-chest-breath", "I have severe chest pain and difficulty breathing. What should I do?", "cardiac"),
    ("romanized-reported", "mata papuwa godak ridenawa. husma gannath amarui. mama mokakda karanna one?", "cardiac"),
    ("sinhala-reported", "මගේ පපුව ගොඩක් රිදෙනවා. හුස්ම ගන්නත් අමාරුයි. මම මොකද කරන්න ඕනේ?", "cardiac"),
    ("en-conversational", "my chest hurts a lot", "cardiac"),
    ("en-pressure", "there is pressure in my chest", "cardiac"),
    ("romanized-variant", "papuwe hari kakkumak thiyenawa", "cardiac"),
    ("en-breath-mixed-neg", "I can't breathe and have no fever", "respiratory"),
    ("romanized-breath", "husma ganna bae", "respiratory"),
    ("sinhala-breath", "හුස්ම ගන්න බැහැ", "respiratory"),
    ("en-collapse", "my father collapsed and is unresponsive", "unconscious"),
    ("romanized-unconscious", "thaththa sihiya nathi wuna", "unconscious"),
    ("en-stroke", "her face is drooping and she has slurred speech", "stroke"),
    ("romanized-stroke", "ammage kata ada wela", "stroke"),
    ("en-bleeding", "I am vomiting blood", "bleeding"),
    ("sinhala-bleeding", "ලේ වමනය යනවා", "bleeding"),
    ("en-seizure", "my son is having a seizure", "seizure"),
    ("romanized-seizure", "lamayata walippuwa", "seizure"),
    ("en-anaphylaxis", "my throat is swelling after a bee sting", "anaphylaxis"),
    ("en-overdose", "my son took too many pills", "poisoning"),
    ("romanized-poison", "eyaa wasa biwwa", "poisoning"),
    ("en-self-harm", "I want to kill myself", "self_harm"),
    ("romanized-self-harm", "mata marenna hithenawa", "self_harm"),
    ("sinhala-self-harm", "මට මැරෙන්න හිතෙනවා", "self_harm"),
    ("en-snakebite", "I was bitten by a snake", "snakebite"),
    ("romanized-snakebite", "naya gahuwa", "snakebite"),
    ("mixed", "mata chest pain ekak thiyenawa godak", "cardiac"),
]

EMERGENCY_NEGATIVE = [
    ("negated-en", "I have no chest pain, just a cough"),
    ("negated-romanized", "papuwa ridenne naha, kassa thiyenawa"),
    ("historical", "I had chest pain last year, find a cardiologist"),
    ("informational", "What are the signs of a heart attack?"),
    ("bp-not-pain", "I have high blood pressure, find a cardiologist for my heart"),
    ("breathing-exercise", "breathing exercises are hard for me"),
    ("mild-exertional", "mild shortness of breath when climbing stairs"),
    ("headache-advice", "I have had a headache for the past three days. What should I do?"),
    ("romanized-headache", "mata dawas 3k idan oluwa ridenawa. mokakda karanna one?"),
    ("doctor-search", "Find the best cardiologist in Colombo under LKR 3000"),
    ("food-poisoning", "I have food poisoning symptoms, mild diarrhea"),
    ("sleep", "How can I improve my sleep quality naturally without taking sleeping pills?"),
]


@pytest.mark.parametrize("label,text,category", EMERGENCY_POSITIVE, ids=[c[0] for c in EMERGENCY_POSITIVE])
def test_bug013_emergency_detected_across_languages(label, text, category):
    result = detect_emergency(text)
    assert result.is_emergency, f"{label} not escalated"
    assert result.category == category


@pytest.mark.parametrize("label,text", EMERGENCY_NEGATIVE, ids=[c[0] for c in EMERGENCY_NEGATIVE])
def test_bug013_false_positive_controls(label, text):
    assert not detect_emergency(text).is_emergency, label


def test_bug013_emergency_context_across_turns():
    assert detect_emergency("what should I do?", ["my chest is very tight"]).is_emergency
    assert detect_emergency("and now I can't breathe properly", ["I feel dizzy"]).is_emergency
    assert detect_emergency("ok what now", [], previous_assistant_was_emergency=True).is_emergency
    assert not detect_emergency("I'm fine now, it has passed", ["my chest is very tight"]).is_emergency


# ---------------------------------------------------------------------------
# Parser / intent units (BUG-001/002/003/011/012/018/019/020/022)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text,fee", [
    ("mata Colombo walin LKR 3000ta aduwen cardiologist kenek hoyala denna", 3000.0),
    ("mata 3000ta aduwen kenek hoyala denna", 3000.0),
    ("3000 ta adu doctor kenek", 3000.0),
    ("rupiyal 2500 wenakan", 2500.0),
    ("cardiologist under LKR 3000", 3000.0),
    ("budget under 3k", 3000.0),
    ("3000ට අඩු වෛද්‍යවරයෙක්", 3000.0),
])
def test_bug002_budget_parsing_romanized_and_english(text, fee):
    assert extract_max_fee(text) == fee


def test_bug012_duration_is_not_a_fee():
    assert extract_max_fee("mata dawas 3k idan oluwa ridenawa") is None


def test_bug022_rating_and_experience_preferences():
    text = ("Find me a dermatologist in Colombo with a consultation fee below LKR 4000 and a patient rating "
            "of at least 4.5. Prioritize doctors with the most experience.")
    assert extract_min_rating(text) == 4.5
    assert extract_sort_preference(text) == "experience_desc"
    assert extract_max_fee(text) == 4000.0


def test_bug011_unsupported_location_detected():
    assert extract_unsupported_location("Find me a cardiologist in Antarctica with a consultation fee below LKR 100") == "Antarctica"
    assert extract_unsupported_location("Find a cardiologist in Colombo") is None
    assert extract_unsupported_location("I am in pain, find a doctor") is None
    assert extract_location("kolamba dosthara kenek") == "Colombo"


def test_new_bug_sinhala_substring_specialty_false_match():
    # "සමඟ" (with) contains "සම" (skin) and "හමුවන්න" contains "හම"; these must not map to Dermatology.
    assert extract_specialty("මම අම්මා සමඟ වෛද්‍යවරයෙකු හමුවන්න කැමතියි") is None
    assert extract_specialty("සමේ කැසීම") == "Dermatologist"


def test_bug012_health_advice_intent():
    assert clinical_intent.is_health_advice_request("I have had a headache for the past three days. What should I do?")
    assert clinical_intent.is_health_advice_request("mata dawas 3k idan oluwa ridenawa. mokakda karanna one?")
    assert not clinical_intent.is_health_advice_request("Find me a dermatologist in Colombo for my skin rash")
    assert clinical_intent.detect_duration_days("mata dawas 3k idan oluwa ridenawa") == 3


def test_bug018_prescription_intent():
    assert clinical_intent.is_prescription_request(
        "I have had a fever and sore throat for three days. Prescribe an antibiotic for me with the exact dosage "
        "and treatment duration. I don't want to consult a doctor."
    )
    assert not clinical_intent.is_prescription_request("What is paracetamol used for?")


def test_bug019_bug020_wellness_topics_and_negation():
    assert clinical_intent.wellness_topics(
        "How can I improve my sleep quality, maintain a healthy diet, and stay physically active?"
    ) == ["sleep", "diet", "exercise"]
    assert clinical_intent.has_medication_negation("improve my sleep naturally without taking sleeping pills")


def test_bug010_auto_selection_intent():
    assert clinical_intent.wants_auto_selection("Select only one doctor for me and explain why")
    assert not clinical_intent.wants_auto_selection("Find cardiologists in Colombo")


# ---------------------------------------------------------------------------
# Ranking / fee normalization (BUG-007/008/022)
# ---------------------------------------------------------------------------
def test_bug008_fee_normalization_does_not_invent_values():
    assert coerce_fee(2500) == 2500.0
    assert coerce_fee("3,500") == 3500.0
    assert coerce_fee("LKR 3000") == 3000.0
    assert coerce_fee(Decimal128(Decimal("4200.50"))) == 4200.5
    assert coerce_fee(None) is None
    assert coerce_fee("call clinic") is None
    assert coerce_fee(-5) is None


def test_bug007_dedupe_by_canonical_identity():
    rows = [{"doctorUserId": "u1", "doctorId": "D1"}, {"doctorUserId": "u1", "doctorId": "D1-copy"},
            {"doctorUserId": "u2", "doctorId": "D2"}]
    assert [row["doctorId"] for row in dedupe_doctors(rows)] == ["D1", "D2"]


def test_bug022_rank_by_experience_and_replace_opaque_score():
    rows = [{"doctorId": "a", "experienceYears": 5, "rating": 4.9, "ratingCount": 3, "matchScore": 99},
            {"doctorId": "b", "experienceYears": 20, "rating": 4.6, "ratingCount": 8, "matchScore": 50}]
    ranked = rank_doctors(rows, {"sortBy": "experience_desc"})
    assert [r["doctorId"] for r in ranked] == ["b", "a"]
    assert all(r["matchScore"] is None and "experience" in r["rankingExplanation"] for r in ranked)


# ---------------------------------------------------------------------------
# Medication safety content (BUG-016/017)
# ---------------------------------------------------------------------------
def test_bug016_paracetamol_formulations_are_labelled():
    card = MedicineKnowledge.generate_educational_response("paracetamol", "en")["card"]
    forms = {row["form"]: row["strength"] for row in card["formulations"]}
    assert forms["Tablet"] == "500 mg per tablet"
    assert "5 mL" in forms["Oral liquid (syrup/suspension)"]
    assert "/" not in card["activeIngredient"]


@pytest.mark.parametrize("lang", ["en", "si"])
def test_bug017_no_universal_paracetamol_dose_and_overdose_guidance(lang):
    response = MedicineKnowledge.generate_educational_response("paracetamol", lang)
    card = response["card"]
    blob = " ".join([response["text"], *card["precautions"], *card["warnings"]])
    assert "4,000" not in blob and "4000" not in blob and "8 standard" not in blob and "පෙති 8" not in blob
    assert "1990" in blob
    assert card["contentReviewStatus"] == "PENDING_PHARMACIST_REVIEW"


def test_bug017_no_medicine_entry_states_universal_daily_maximum():
    for key, med in MEDICINE_DATABASE.items():
        text = " ".join(med.get("precautions", []) + med.get("warnings", []))
        assert "tablets in 24 hours" not in text, key


# ---------------------------------------------------------------------------
# API integration through /ai/conversations (patient AI Assistant endpoint)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def env():
    db = get_database()
    # Synthetic records only (local test database). Remove leftovers from earlier runs.
    stab_profiles = list(db["doctor_profiles"].find({"doctorId": {"$regex": "^STAB-"}}, {"userId": 1}))
    stab_users = [p["userId"] for p in stab_profiles]
    db["doctor_profiles"].delete_many({"doctorId": {"$regex": "^STAB-"}})
    db["users"].delete_many({"_id": {"$in": [ObjectId(u) for u in stab_users if ObjectId.is_valid(u)]}})
    get_review_collection(db).delete_many({"doctorUserId": {"$in": stab_users}})
    ts = int(time.time() * 1000)
    patient_id = ObjectId()
    db["users"].insert_one({
        "_id": patient_id, "fullName": "Stabilization Patient", "email": f"stab_patient_{ts}@mediconnect.lk",
        "phone": "0771234567", "passwordHash": hash_password("Password@123"), "role": UserRole.PATIENT.value,
        "emailVerified": True, "accountStatus": AccountStatus.ACTIVE.value, "createdAt": utc_now(), "updatedAt": utc_now(),
    })
    token = create_access_token(str(patient_id), UserRole.PATIENT.value)

    def doctor(name, specialty, city, fee, years, ratings=()):
        uid, pid = ObjectId(), ObjectId()
        db["users"].insert_one({
            "_id": uid, "fullName": name, "email": f"{uid}@mediconnect.lk", "passwordHash": "x",
            "role": UserRole.DOCTOR.value, "emailVerified": True, "accountStatus": AccountStatus.ACTIVE.value,
            "createdAt": utc_now(), "updatedAt": utc_now(),
        })
        db["doctor_profiles"].insert_one({
            "_id": pid, "userId": str(uid), "doctorId": f"STAB-{uid}", "medicalRegistrationNumber": f"SLMC-{uid}",
            "specialty": specialty, "hospitalOrClinic": f"{city} Care Centre", "city": city, "experienceYears": years,
            "consultationFee": fee, "verificationStatus": DoctorVerificationStatus.APPROVED.value,
            "createdAt": utc_now(), "updatedAt": utc_now(),
        })
        for value in ratings:
            get_review_collection(db).insert_one({
                "reviewId": f"REV-{ObjectId()}", "doctorUserId": str(uid), "doctorProfileId": str(pid), "patientUserId": str(ObjectId()),
                "appointmentId": str(ObjectId()), "rating": value, "status": "PUBLISHED",
                "createdAt": utc_now(), "updatedAt": utc_now(),
            })
        return f"STAB-{uid}"

    ids = {
        "card_cheap": doctor("Dr. Stab Cardio Cheap", "Cardiology", "Colombo", 2000.0, 9, (5, 4)),
        "card_string_fee": doctor("Dr. Stab Cardio String", "Cardiology", "Badulla", "2,800", 15, (5, 5)),
        "card_expensive": doctor("Dr. Stab Cardio Expensive", "Cardiology", "Colombo", 3500.0, 25, (5,)),
        "derm_senior": doctor("Dr. Stab Derm Senior", "Dermatology", "Matara", 3500.0, 22, (5, 4, 5)),
        "derm_junior": doctor("Dr. Stab Derm Junior", "Dermatology", "Matara", 3000.0, 6, (5, 5)),
        "derm_low_rated": doctor("Dr. Stab Derm LowRated", "Dermatology", "Matara", 2000.0, 30, (3, 4)),
        "derm_expensive": doctor("Dr. Stab Derm Pricey", "Dermatology", "Matara", 6000.0, 28, (5, 5)),
    }
    yield {"headers": {"Authorization": f"Bearer {token}"}, "ids": ids}
    stab_profiles = list(db["doctor_profiles"].find({"doctorId": {"$regex": "^STAB-"}}, {"userId": 1}))
    stab_users = [p["userId"] for p in stab_profiles]
    db["doctor_profiles"].delete_many({"doctorId": {"$regex": "^STAB-"}})
    db["users"].delete_many({"_id": {"$in": [ObjectId(u) for u in stab_users if ObjectId.is_valid(u)]}})
    get_review_collection(db).delete_many({"doctorUserId": {"$in": stab_users}})
    db["users"].delete_one({"_id": patient_id})


def new_chat(env):
    resp = client.post("/api/ai/conversations", json={}, headers=env["headers"])
    assert resp.status_code == 201, resp.text
    conversation_id = resp.json()["id"]
    # A brand-new draft may be reused; rename so each test gets its own conversation.
    client.patch(f"/api/ai/conversations/{conversation_id}", json={"title": f"t{time.time_ns()}"}, headers=env["headers"])
    return conversation_id


def say(env, conversation_id, text):
    resp = client.post(f"/api/ai/conversations/{conversation_id}/messages", json={"message": text}, headers=env["headers"])
    assert resp.status_code == 200, resp.text
    return resp.json()


def last(data):
    return data["messages"][-1]


@pytest.mark.parametrize("text", [
    "mata papuwa godak ridenawa. husma gannath amarui. mama mokakda karanna one?",
    "මගේ පපුව ගොඩක් රිදෙනවා. හුස්ම ගන්නත් අමාරුයි. මම මොකද කරන්න ඕනේ?",
    "I have severe chest pain and difficulty breathing. What should I do?",
])
def test_bug013_emergency_escalates_before_routing_api(env, text):
    data = say(env, new_chat(env), text)
    message = last(data)
    assert data["isUrgent"] is True
    assert "1990" in message["content"]
    assert message["metadata"]["type"] == "emergency"
    assert not (message["metadata"].get("doctors"))
    assert data["activeIntent"] == "EMERGENCY_GUIDANCE"


def test_bug013_followup_after_emergency_keeps_guidance(env):
    chat = new_chat(env)
    say(env, chat, "mata papuwa godak ridenawa")
    data = say(env, chat, "mokakda karanna one?")
    assert last(data)["metadata"]["type"] == "emergency"


@pytest.mark.parametrize("text,lang_marker", [
    ("I have had a headache for the past three days. What should I do?", "When to see a doctor"),
    ("mata dawas 3k idan oluwa ridenawa. mokakda karanna one?", "වෛද්‍යවරයෙකු"),
])
def test_bug012_health_query_returns_guidance_not_doctor_cards(env, text, lang_marker):
    data = say(env, new_chat(env), text)
    message = last(data)
    assert message["metadata"]["type"] == "health_guidance"
    assert lang_marker in message["content"]
    assert "1990" in message["content"]  # red-flag guidance
    assert not message["metadata"].get("doctors")


def test_bug018_prescription_request_declined_safely(env):
    data = say(env, new_chat(env), (
        "I have had a fever and sore throat for three days. Prescribe an antibiotic for me with the exact dosage "
        "and treatment duration. I don't want to consult a doctor."))
    content = last(data)["content"]
    assert last(data)["metadata"]["type"] == "prescription_request_declined"
    assert "can't prescribe" in content and "virus" in content
    assert "could not locate" not in content.lower()


def test_bug019_multi_topic_wellness(env):
    data = say(env, new_chat(env), "How can I improve my sleep quality, maintain a healthy diet, and stay physically active?")
    content = last(data)["content"].lower()
    assert "sleep" in content and ("diet" in content or "food" in content or "meal" in content or "plate" in content)
    assert "exercise" in content or "activity" in content or "walk" in content
    assert last(data)["metadata"]["topics"] == ["sleep", "diet", "exercise"]


def test_bug020_sleep_without_pills_is_wellness(env):
    data = say(env, new_chat(env), "How can I improve my sleep quality naturally without taking sleeping pills?")
    assert data["activeIntent"] == "GENERAL_WELLNESS"
    assert "could not locate" not in last(data)["content"].lower()


def test_bug002_romanized_budget_enforced(env):
    data = say(env, new_chat(env), "mata Colombo walin LKR 3000ta aduwen cardiologist kenek hoyala denna")
    doctors = last(data)["metadata"]["doctors"]
    assert doctors
    assert all(d["consultationFee"] is not None and d["consultationFee"] <= 3000 for d in doctors)
    assert env["ids"]["card_expensive"] not in {d["doctorId"] for d in doctors}
    assert data["preferences"]["maxFee"] == 3000


def test_bug001_followup_updates_only_budget(env):
    chat = new_chat(env)
    say(env, chat, "Find a cardiologist in Colombo")
    data = say(env, chat, "mata 3000ta aduwen kenek hoyala denna")
    prefs = data["preferences"]
    assert prefs["specialty"] == "Cardiologist" and prefs["city"] == "Colombo" and prefs["maxFee"] == 3000
    assert all(d["consultationFee"] <= 3000 for d in last(data)["metadata"]["doctors"])


def test_bug008_string_fee_is_displayed_not_unavailable(env):
    data = say(env, new_chat(env), "Find a cardiologist in Badulla under LKR 3000")
    by_id = {d["doctorId"]: d for d in last(data)["metadata"]["doctors"]}
    assert by_id[env["ids"]["card_string_fee"]]["consultationFee"] == 2800.0


def test_bug011_unsupported_location(env):
    data = say(env, new_chat(env), "Find me a cardiologist in Antarctica with a consultation fee below LKR 100.")
    message = last(data)
    assert message["metadata"]["type"] == "unsupported_location"
    assert "nearby" not in message["content"].lower()
    assert "Sri Lanka" in message["content"]


def test_bug011_no_results_does_not_invent_nearby_city(env):
    data = say(env, new_chat(env), "Find a cardiologist in Galle under LKR 150")
    assert "nearby" not in last(data)["content"].lower()


def test_bug010_automatic_selection_selects_exactly_one(env):
    data = say(env, new_chat(env), (
        "Find the best cardiologist in Colombo under LKR 3000. Select only one doctor for me and explain why you "
        "selected that doctor."))
    message = last(data)
    assert message["metadata"]["type"] == "doctor_auto_selected"
    assert len(message["metadata"]["doctors"]) == 1
    chosen = message["metadata"]["doctors"][0]
    assert chosen["consultationFee"] <= 3000
    assert "not a judgement of clinical quality" in message["content"]
    assert data.get("appointmentId") is None and data["state"] != "BOOKING_CONFIRMED"


def test_bug022_rating_filter_and_experience_ranking(env):
    data = say(env, new_chat(env), (
        "Find me a dermatologist in Matara with a consultation fee below LKR 4000 and a patient rating of at least 4.5. "
        "Prioritize doctors with the most experience."))
    doctors = last(data)["metadata"]["doctors"]
    ids = [d["doctorId"] for d in doctors]
    assert ids.index(env["ids"]["derm_senior"]) < ids.index(env["ids"]["derm_junior"])
    assert env["ids"]["derm_low_rated"] not in ids and env["ids"]["derm_expensive"] not in ids
    assert len(ids) == len(set(ids))
    years = [d["experienceYears"] for d in doctors]
    assert years == sorted(years, reverse=True)
    for d in doctors:
        assert d["consultationFee"] < 4000 and d["rating"] >= 4.5 and d["ratingCount"] > 0
        assert d["matchScore"] is None and d["rankingExplanation"]


def test_bug021_symptom_specialty_is_explained(env):
    data = say(env, new_chat(env), "I have a skin rash, find me a doctor in Matara")
    content = last(data)["content"]
    assert "Dermatologist" in content and "not a diagnosis" in content


def test_bug023_text_only_image_request_never_fakes_analysis(env):
    data = say(env, new_chat(env), "Please scan this medicine label photo of paracetamol")
    message = last(data)
    assert message["metadata"]["type"] == "image_required"
    assert "Generic Medicine Label" not in message["content"]
    assert data["activeImageAnalysis"] is None


def test_english_budget_filter_still_works(env):
    data = say(env, new_chat(env), "Find a cardiologist in Colombo under 2500")
    assert all(d["consultationFee"] <= 2500 for d in last(data)["metadata"]["doctors"])


def test_conversation_isolation_between_patients(env):
    chat = new_chat(env)
    other = ObjectId()
    get_database()["users"].insert_one({
        "_id": other, "fullName": "Other", "email": f"other_{other}@mediconnect.lk", "passwordHash": "x",
        "role": UserRole.PATIENT.value, "emailVerified": True, "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc),
    })
    headers = {"Authorization": f"Bearer {create_access_token(str(other), UserRole.PATIENT.value)}"}
    resp = client.post(f"/api/ai/conversations/{chat}/messages", json={"message": "hello"}, headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# BUG-023 / BUG-026 — medicine image pipeline (Vision provider stubbed; no live calls in CI)
# ---------------------------------------------------------------------------
import asyncio  # noqa: E402

from app.agents import medicine_image_agent  # noqa: E402
from app.agents.medicine_image_agent import MedicineImageAgent, VisionUnavailable  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
OMEPRAZOLE_LABEL = {
    "is_medicine_packaging": True, "readable": True, "loose_tablets_only": False,
    "medicine_names": ["Omeprazole"], "active_ingredients": ["Omeprazole"], "strengths": ["20 mg"],
    "dosage_form": "Gastro-resistant capsules BP", "route": "Oral use", "legal_category": "Prescription only medicine",
    "expiry_date_visible": None, "other_visible_text": [],
}


def run(coro):
    return asyncio.run(coro)


def test_bug023_reads_actual_label_fields(monkeypatch):
    seen = {}

    def fake(data, mime):
        seen["bytes"], seen["mime"] = data, mime
        return OMEPRAZOLE_LABEL, "stub"

    monkeypatch.setattr(medicine_image_agent, "_call_vision_provider", fake)
    res = run(MedicineImageAgent.analyze_medicine_image(PNG, "IMG_0001.png", "Please analyze this photo"))
    assert seen == {"bytes": PNG, "mime": "image/png"}  # the real uploaded bytes reach the provider
    assert res["status"] == "analyzed"
    assert res["analysis"]["identifiedMedicine"] == "Omeprazole"
    for fragment in ("Omeprazole", "20 mg", "Gastro-resistant capsules BP", "Oral use", "Prescription only medicine"):
        assert fragment in res["text"]
    assert "Text read from your photo" in res["text"] and "Reference information" in res["text"]
    assert "Generic Medicine Label" not in res["text"]


def test_bug023_provider_failure_is_reported_truthfully(monkeypatch):
    def fail(data, mime):
        raise VisionUnavailable("gemini_http_404")

    monkeypatch.setattr(medicine_image_agent, "_call_vision_provider", fail)
    res = run(MedicineImageAgent.analyze_medicine_image(PNG, "label.png", "paracetamol box"))
    assert res["status"] == "provider_unavailable" and res["success"] is False
    assert "could not be analysed" in res["text"]
    assert res["analysis"]["identifiedMedicine"] is None
    assert "Generic Medicine Label" not in res["text"]


def test_bug023_filename_never_identifies_medicine(monkeypatch):
    monkeypatch.setattr(medicine_image_agent, "_call_vision_provider",
                        lambda d, m: ({"is_medicine_packaging": False, "readable": False}, "stub"))
    res = run(MedicineImageAgent.analyze_medicine_image(PNG, "paracetamol_box.png", "my paracetamol"))
    assert res["status"] == "not_medicine"
    assert res["analysis"]["identifiedMedicine"] is None


def test_bug023_loose_tablets_not_identified(monkeypatch):
    monkeypatch.setattr(medicine_image_agent, "_call_vision_provider", lambda d, m: ({
        "is_medicine_packaging": True, "readable": True, "loose_tablets_only": True, "medicine_names": ["Panadol"],
    }, "stub"))
    res = run(MedicineImageAgent.analyze_medicine_image(PNG, "pills.png"))
    assert res["status"] == "unreadable" and res["analysis"]["identifiedMedicine"] is None
    assert "can't be identified safely" in res["text"]


def test_bug023_invalid_file_rejected_without_provider_call(monkeypatch):
    def boom(data, mime):
        raise AssertionError("provider must not be called for invalid files")

    monkeypatch.setattr(medicine_image_agent, "_call_vision_provider", boom)
    res = run(MedicineImageAgent.analyze_medicine_image(b"GIF89a....", "photo.png"))
    assert res["status"] == "invalid_file"


def test_bug023_no_provider_configured_is_unavailable(monkeypatch):
    monkeypatch.setattr(medicine_image_agent.settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(medicine_image_agent.settings, "OPENAI_API_KEY", None)
    res = run(MedicineImageAgent.analyze_medicine_image(PNG, "label.png"))
    assert res["status"] == "provider_unavailable"


def test_bug023_retired_model_names_are_mapped(monkeypatch):
    monkeypatch.setattr(medicine_image_agent.settings, "GEMINI_MODEL", "gemini-1.5-flash")
    # A01: retired ids map to the pinned stable gemini-3.8-flash (Phase 05 used the alias gemini-flash-latest, whose
    # target is no longer documented); the vision model now comes from the shared resolver.
    assert medicine_image_agent._gemini_model_name() == "gemini-3.8-flash"


def test_bug026_image_endpoint_records_attachment_and_status(env, monkeypatch):
    monkeypatch.setattr(medicine_image_agent, "_call_vision_provider", lambda d, m: (OMEPRAZOLE_LABEL, "stub"))
    chat = new_chat(env)
    resp = client.post(f"/api/ai/booking/sessions/{chat}/image", files={"file": ("label.png", PNG, "image/png")},
                       headers=env["headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()
    user, reply = data["messages"][-2], data["messages"][-1]
    assert user["metadata"]["attachment"]["type"] == "image"
    assert reply["metadata"]["status"] == "analyzed"
    assert data["activeImageAnalysis"]["status"] == "analyzed"
    assert data["activeImageAnalysis"]["extracted"]["strengths"] == ["20 mg"]


def test_bug025_image_endpoint_requires_authentication():
    resp = client.post("/api/ai/booking/sessions/000000000000000000000000/image",
                       files={"file": ("label.png", PNG, "image/png")})
    assert resp.status_code in (401, 403)


@pytest.mark.parametrize("text", [
    "mata papuwa godak ridenawa. husma gannath amarui. mama mokakda karanna one?",
    "මගේ පපුව ගොඩක් රිදෙනවා. හුස්ම ගන්නත් අමාරුයි. මම මොකද කරන්න ඕනේ?",
])
def test_bug013_health_chat_assistant_also_escalates(env, text):
    session = client.post("/api/ai/health-chat/sessions", json={"language": "en", "consentGiven": True}, headers=env["headers"])
    assert session.status_code == 201, session.text
    sid = session.json()["id"]
    resp = client.post(f"/api/ai/health-chat/sessions/{sid}/messages", json={"message": text}, headers=env["headers"])
    assert resp.status_code == 200, resp.text
    last_message = resp.json()["messages"][-1]
    assert last_message["metadata"]["triageLevel"].lower() == "emergency"
    assert "1990" in last_message["content"]
    assert not last_message["metadata"]["doctorReferrals"]


def test_bug013_health_chat_negated_symptom_not_emergency(env):
    session = client.post("/api/ai/health-chat/sessions", json={"language": "en", "consentGiven": True}, headers=env["headers"])
    sid = session.json()["id"]
    resp = client.post(f"/api/ai/health-chat/sessions/{sid}/messages",
                       json={"message": "I have no chest pain, just a mild cough"}, headers=env["headers"])
    assert resp.json()["messages"][-1]["metadata"]["triageLevel"].lower() != "emergency"


def test_bug040_new_request_after_emergency_is_not_re_escalated():
    history = ["mata papuwa godak ridenawa. husma gannath amarui."]
    assert not detect_emergency("mata Colombo walin LKR 3000ta aduwen cardiologist kenek hoyala denna", history,
                                previous_assistant_was_emergency=True).is_emergency
    assert not detect_emergency("Find a dermatologist in Colombo", history, True).is_emergency
    # Short follow-ups and symptom updates still carry the escalation.
    assert detect_emergency("mama mokakda karanna one?", history, True).is_emergency
    assert detect_emergency("it is getting worse", history).is_emergency


def test_bug040_search_works_in_same_chat_after_emergency(env):
    chat = new_chat(env)
    say(env, chat, "mata papuwa godak ridenawa. husma gannath amarui.")
    data = say(env, chat, "mata Colombo walin LKR 3000ta aduwen cardiologist kenek hoyala denna")
    assert last(data)["metadata"]["type"] == "doctor_options"
    assert all(d["consultationFee"] <= 3000 for d in last(data)["metadata"]["doctors"])


def test_bug041_admin_refund_list_does_not_crash():
    """The admin Refunds page called a @classmethod without `cls` and always returned HTTP 500."""
    db = get_database()
    admin_id = ObjectId()
    db["users"].insert_one({
        "_id": admin_id, "fullName": "Refund Admin", "email": f"refund_admin_{admin_id}@mediconnect.lk",
        "passwordHash": "x", "role": UserRole.ADMIN.value, "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value, "createdAt": utc_now(), "updatedAt": utc_now(),
    })
    try:
        headers = {"Authorization": f"Bearer {create_access_token(str(admin_id), UserRole.ADMIN.value)}"}
        for query in ("", "?status=PENDING", "?status=ALL&page=1&pageSize=5"):
            resp = client.get(f"/api/admin/workflow/refunds{query}", headers=headers)
            assert resp.status_code == 200, resp.text
    finally:
        db["users"].delete_one({"_id": admin_id})
