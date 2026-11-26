"""Phase 05 S-04 emergency triage regression through the app's conversation API (/ai/conversations), including B17
(Sinhala emergency follow-ups keep the language and the emergency context). Deterministic engine only.
Clinical approval of this behaviour is still pending (B1); these tests only fix the implemented behaviour.
"""
import re

import pytest

from tests.test_payment import _make_test_patient, client, db  # noqa: F401
from tests.test_phase02_booking_payment import _auth

SINHALA = re.compile(r"[඀-෿]")


def _new(patient, text):
    from app.routes.ai_booking import _RATE_LIMIT_BUCKET
    _RATE_LIMIT_BUCKET.clear()
    res = client.post("/api/ai/conversations", json={"initialMessage": text}, headers=_auth(patient))
    assert res.status_code == 201, res.text
    return res.json()


def _send(patient, cid, text):
    from app.routes.ai_booking import _RATE_LIMIT_BUCKET
    _RATE_LIMIT_BUCKET.clear()
    res = client.post(f"/api/ai/conversations/{cid}/messages", json={"message": text}, headers=_auth(patient))
    assert res.status_code == 200, res.text
    return res.json()


def _last(body):
    return [m for m in body["messages"] if m["sender"] == "assistant"][-1]


@pytest.mark.parametrize("text", [
    "I have severe chest pain spreading to my left arm",
    "my father collapsed and is not breathing",
    "her face is drooping and she cannot speak properly",
    "my throat is swelling after eating peanuts and I can't breathe",
    "මට පපුවේ දැඩි වේදනාවක් තියෙනවා, හුස්ම ගන්න අමාරුයි",
])
def test_s04a_emergencies_get_1990_and_no_booking(db, text):
    last = _last(_new(_make_test_patient(db, "P05S04A"), text))
    assert last["metadata"]["type"] == "emergency" and last["metadata"]["ambulanceCall"] == "1990"
    assert "1990" in last["content"]


def test_s04b_negated_symptom_is_not_an_emergency(db):
    last = _last(_new(_make_test_patient(db, "P05S04B"), "I don't have chest pain, I just need a skin doctor in Colombo"))
    assert last["metadata"]["type"] != "emergency"


def test_s04c_educational_question_gets_conditional_guidance_not_an_alarm(db):
    last = _last(_new(_make_test_patient(db, "P05S04C"), "What are the warning signs of a stroke?"))
    assert last["metadata"]["type"] in {"emergency_information", "health_information"}
    assert last["metadata"].get("conditionalEmergency", True)


def test_s04d_short_follow_up_keeps_emergency_context(db):
    patient = _make_test_patient(db, "P05S04D")
    first = _new(patient, "I have crushing chest pain and I am sweating")
    follow = _send(patient, first["id"], "it is getting worse")
    assert _last(follow)["metadata"]["type"] == "emergency"


def test_s04e_b17_sinhala_emergency_follow_ups_stay_in_sinhala(db):
    patient = _make_test_patient(db, "P05B17")
    first = _new(patient, "මට පපුවේ දැඩි වේදනාවක් තියෙනවා")
    assert SINHALA.search(_last(first)["content"])
    for follow_up in ("ok", "mata dan mokada karanna one?", "1990?"):
        body = _send(patient, first["id"], follow_up)
        assert SINHALA.search(_last(body)["content"]), (follow_up, _last(body)["content"][:120])
    # A clear English follow-up is answered in English.
    body = _send(patient, first["id"], "What should I do while I wait for the ambulance?")
    assert not SINHALA.search(_last(body)["content"][:80])


def test_s04f_self_harm_gets_verified_support_lines_and_follow_up_stays_supportive(db):
    patient = _make_test_patient(db, "P05S04F")
    first = _new(patient, "I want to end my life")
    meta = _last(first)["metadata"]
    assert meta["type"] == "emergency" and meta["crisisType"] == "mental_health"
    assert {line["number"] for line in meta["supportLines"]} == {"1926", "1333"}  # grounded official lines only
    follow = _last(_send(patient, first["id"], "I don't know"))
    assert follow["metadata"]["type"] == "emergency"  # the crisis context is not reset by a short reply


def test_s04g_medicine_overdose_escalates(db):
    last = _last(_new(_make_test_patient(db, "P05S04G"), "I took 20 paracetamol tablets an hour ago"))
    assert last["metadata"]["type"] == "emergency" and "1990" in last["content"]


def test_s04_unrelated_question_after_emergency_is_not_escalated(db):
    patient = _make_test_patient(db, "P05S04U")
    first = _new(patient, "I want to end my life")
    later = _send(patient, first["id"], "What are healthy foods for breakfast?")
    assert _last(later)["metadata"]["type"] != "emergency" or "1926" in _last(later)["content"]
