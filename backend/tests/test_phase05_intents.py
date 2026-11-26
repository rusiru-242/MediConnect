"""Phase 05 component 33: shared role-specific intent classification and its use by the three assistants.

Covers English, Sinhala script, Romanized Sinhala, paraphrases, multiple constraints, role separation, ambiguity,
the bounded LLM proposal (test double only, never a live provider) and B16.
"""
from unittest.mock import MagicMock, patch

from bson import ObjectId
import pytest

from app.agents.intent_router import classify, detect_language, propose_intent
from tests.test_payment import _make_test_doctor, _make_test_patient, client, db  # noqa: F401
from tests.test_phase02_booking_payment import _admin, _auth


@pytest.mark.parametrize("role,text,intent", [
    # Section 8 examples
    ("ADMIN", "Show me pending doctor verification applications.", "pending_doctor_verifications"),
    ("ADMIN", "Which refunds need attention?", "refunds_attention"),
    ("ADMIN", "How many successful payments were recorded this week?", "payment_summary"),
    ("ADMIN", "Show notification failures.", "notification_failures"),
    ("ADMIN", "Explain why this fraud assessment was generated.", "fraud_explanation"),
    ("DOCTOR", "Show my appointments for tomorrow.", "schedule"),
    ("DOCTOR", "Find the patients requiring follow-up this week.", "follow_ups"),
    ("DOCTOR", "Prepare the consultation summary for my next patient.", "consultation_preparation"),
    ("DOCTOR", "Show my pending prescription renewal requests.", "renewal_queue"),
    ("DOCTOR", "How many consultations did I complete this month?", "analytics"),
    ("PATIENT", "Show me my next appointment.", "appointments"),
    ("PATIENT", "When should I take the medicine prescribed by my doctor?", "medication_schedule"),
    ("PATIENT", "Show my upcoming medical tests.", "medical_tests"),
    # Semantic paraphrases (S-03e)
    ("ADMIN", "Are any messages failing to reach users?", "notification_failures"),
    ("ADMIN", "Which doctors are still waiting for approval?", "pending_doctor_verifications"),
    ("ADMIN", "Is the platform working properly right now? check system status", "system_health"),
    ("DOCTOR", "Who still needs a follow up from me in the coming days?", "follow_ups"),
    ("DOCTOR", "any refill requests for me to look at?", "renewal_queue"),
    ("PATIENT", "What time do I need to take my tablets?", "medication_schedule"),
    ("PATIENT", "Are any blood tests coming up for me?", "medical_tests"),
    # Sinhala script and Romanized Sinhala (S-03b/c)
    ("ADMIN", "මේ සතියේ සාර්ථක ගෙවීම් කීයද?", "payment_summary"),
    ("ADMIN", "doctorlage applications kiyak approve karanna thiyenawada?", "pending_doctor_verifications"),
    ("ADMIN", "system eka healthy da?", "system_health"),
    ("ADMIN", "failed payments tika check karanna", "failed_payments"),
    ("DOCTOR", "heta mage appointments monawada?", "schedule"),
    ("PATIENT", "beheth bonna one welawa mokakda?", "medication_schedule"),
    ("PATIENT", "මගේ බෙහෙත් මාත්‍රාව වැඩි කරන්න", "medication_change_request"),
    # Mixed language (S-03d)
    ("ADMIN", "me week eke successful payments keeyada?", "payment_summary"),
    # B16 variants
    ("PATIENT", "change my dose to two tablets", "medication_change_request"),
    ("PATIENT", "can I double my dose of metformin", "medication_change_request"),
    ("PATIENT", "Should I stop my medication now that I feel fine?", "medication_change_request"),
])
def test_s03_classification(role, text, intent):
    assert classify(role, text).intent == intent


def test_s03_language_detection():
    assert detect_language("Show my appointments") == "en"
    assert detect_language("මට කොළඹ වෛද්‍යවරයෙක්") == "si"
    assert detect_language("mata doctor kenek hoyala denna") == "si-Latn"
    assert detect_language("நாளை சந்திப்பு") == "ta"


def test_s03_timeframes_and_multiple_constraints():
    r = classify("ADMIN", "How many successful payments were recorded this week?")
    assert (r.intent, r.timeframe) == ("payment_summary", "last_7_days")
    assert classify("ADMIN", "revenue for this month").timeframe == "last_30_days"
    assert classify("ADMIN", "ada bookings keeyada").timeframe == "today"
    # payments + revenue are compatible constraints of one question, not an ambiguity
    assert classify("ADMIN", "successful payments and revenue this month").intent == "payment_summary"


def test_s03_role_specific_intents_do_not_leak_between_roles():
    assert classify("PATIENT", "Show me pending doctor verification applications.").intent == "unknown"
    assert classify("DOCTOR", "Which refunds need attention?").intent == "unknown"
    assert classify("ADMIN", "change my dose to two tablets").intent == "unknown"


def test_s03_ambiguous_and_unknown():
    r = classify("ADMIN", "show refunds and support tickets")
    assert r.intent == "ambiguous" and set(r.candidates) == {"refunds_attention", "support_tickets"}
    assert classify("ADMIN", "show me the numbers").intent == "unknown"


def test_s03_llm_proposal_is_bounded_to_the_role_schema():
    provider = MagicMock()
    provider.classify_intent.return_value = "support_tickets"
    r = classify("ADMIN", "anything the team should look at first?", provider=provider)
    assert (r.intent, r.source) == ("support_tickets", "llm_proposal")
    sent_text, allowed = provider.classify_intent.call_args[0]
    assert "support_tickets" in allowed and "approve_refund" not in allowed
    provider.classify_intent.return_value = "approve_refund"            # not in the schema: discarded
    assert classify("ADMIN", "anything else?", provider=provider).intent == "unknown"
    provider.classify_intent.side_effect = TimeoutError()                # provider failure: deterministic result
    r = classify("ADMIN", "anything else?", provider=provider)
    assert (r.intent, r.source) == ("unknown", "provider_unavailable")
    provider.classify_intent.side_effect = None
    provider.classify_intent.return_value = "support_tickets"
    classify("ADMIN", "my email is someone@example.com, anything urgent?", provider=provider)
    assert "someone@example.com" not in provider.classify_intent.call_args[0][0]  # identifiers redacted
    assert propose_intent(None, "ADMIN", "x") == (None, "deterministic")


# ------------------------------------------------------------------------------------------------ admin API
def _admin_chat(admin, text, **extra):
    res = client.post("/api/admin/workflow/assistant", json={"message": text, **extra}, headers=_auth(admin))
    assert res.status_code == 200, res.text
    return res.json()


def test_admin_assistant_routes_new_intents_to_read_only_tools(db):
    admin = _admin(db)
    cases = {
        "How many successful payments were recorded this week?": "get_admin_dashboard_metrics",
        "Show notification failures.": "get_notification_queue_status",
        "Explain why this fraud assessment was generated.": "get_fraud_alerts",
        "Is the system healthy?": "get_platform_health",
        "මේ සතියේ සාර්ථක ගෙවීම් කීයද?": "get_admin_dashboard_metrics",
    }
    for text, tool in cases.items():
        body = _admin_chat(admin, text)
        assert body["toolCalled"] == tool, (text, body)
        assert body["intent"] and body["intentSource"] == "deterministic"
    week = _admin_chat(admin, "How many successful payments were recorded this week?")
    assert "successful payment" in week["reply"] and week["dateRange"]


def test_admin_fraud_explanation_uses_the_stored_assessment_and_says_signal_not_finding(db):
    admin = _admin(db)
    aid = f"FRAUD-P05-{ObjectId()}"
    db["fraud_risk_assessments"].insert_one({
        "assessmentId": aid, "relatedEntityReference": "acct", "riskScore": 55.0, "riskLevel": "MEDIUM",
        "triggeredRules": ["REPEATED_PAYMENT_FAILURES"], "explanation": "Three declined card attempts in 10 minutes.",
        "reviewStatus": "AWAITING_REVIEW"})
    body = _admin_chat(admin, "Explain why this fraud assessment was generated.", contextFilter={"assessmentId": aid})
    assert body["toolCalled"] == "get_fraud_review_details"
    assert "REPEATED_PAYMENT_FAILURES" in body["reply"] and "not a finding" in body["reply"]


def test_admin_ambiguous_request_asks_instead_of_guessing(db):
    body = _admin_chat(_admin(db), "show refunds and support tickets")
    assert body["intent"] == "ambiguous" and body["toolCalled"] is None and "Which one" in body["reply"]


def test_admin_assistant_refuses_other_roles(db):
    patient = _make_test_patient(db, "P05INTP")
    res = client.post("/api/admin/workflow/assistant", json={"message": "Show notification failures."},
                      headers=_auth(patient))
    assert res.status_code == 403


# ------------------------------------------------------------------------------------------------ doctor API
def test_doctor_assistant_renewal_queue_and_paraphrase(db):
    doctor = _make_test_doctor(db, "P05INTD")
    res = client.post("/api/doctor/workflow/assistant", json={"message": "Show my pending prescription renewal requests."},
                      headers=_auth(doctor))
    assert res.status_code == 200 and res.json()["tool"] == "get_prescription_renewal_queue"
    assert "cannot approve" in res.json()["message"]
    res = client.post("/api/doctor/workflow/assistant", json={"message": "any refill requests for me to look at?"},
                      headers=_auth(doctor))
    assert res.json()["tool"] == "get_prescription_renewal_queue"


# ------------------------------------------------------------------------------------------------ patient API
def _patient_turn(patient, text):
    from app.routes.ai_booking import _RATE_LIMIT_BUCKET
    _RATE_LIMIT_BUCKET.clear()
    res = client.post("/api/ai/conversations", json={"initialMessage": text}, headers=_auth(patient))
    assert res.status_code == 201, res.text
    body = res.json()
    last = [m for m in body["messages"] if m["sender"] == "assistant"][-1]
    return body, last


def test_b16_dose_change_request_changes_nothing_and_names_the_clinician(db):
    patient = _make_test_patient(db, "P05B16")
    before = db["care_tracking_schedules"].count_documents({"patientUserId": patient["id"]})
    _, last = _patient_turn(patient, "change my dose to two tablets")
    assert last["metadata"]["type"] == "medication_change_requires_clinician"
    assert last["metadata"]["scheduleChanged"] is False
    assert "doctor who prescribed" in last["content"] and "1990" in last["content"]
    assert db["care_tracking_schedules"].count_documents({"patientUserId": patient["id"]}) == before


def test_patient_medicine_time_question_reads_own_care_agenda_not_a_refusal(db):
    patient = _make_test_patient(db, "P05MED")
    _, last = _patient_turn(patient, "When should I take the medicine prescribed by my doctor?")
    assert last["metadata"]["type"] != "prescription_request_declined"
    assert "no matching scheduled records" in last["content"] or "Asia/Colombo" in last["content"]


def test_emergency_still_wins_over_medication_intents(db):
    patient = _make_test_patient(db, "P05EMG")
    body, last = _patient_turn(patient, "I took ten tablets of my medicine at once and I can't breathe")
    assert body.get("isUrgent") is True or "1990" in last["content"]
    assert last["metadata"]["type"] != "medication_change_requires_clinician"
