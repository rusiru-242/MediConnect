"""R03 final verification regressions.

R03-BUG-002: an educational question that also said "I'm just curious", "I have a question" or "I am a student"
was escalated as an emergency, because the bare first-person phrase counted as a personal experience.
"""
import pytest

from app.agents.emergency_detector import detect_emergency

EDUCATIONAL = [
    "What is a heart attack? I'm just curious for a school project.",
    "I have a question: what is a heart attack?",
    "I am a student. What are the warning signs of a stroke?",
    "I'm wondering what are the symptoms of a stroke?",
    "I am doing a school project. What causes a heart attack?",
]

STILL_EMERGENCY = [
    "I'm curious, I have chest pain right now",
    "I have a question, my chest hurts and I can't breathe",
    "I am a student and I have crushing chest pain",
    "I have chest pain spreading to my left arm",
    "I'm having a heart attack",
    "My father collapsed and is not breathing",
    "I have a question about suicide, I want to kill myself",
    "I am just curious what are the signs of suicide",  # self-harm keeps the support path for first-person framing
]


@pytest.mark.parametrize("text", EDUCATIONAL)
def test_educational_questions_with_first_person_framing_are_not_emergencies(text):
    result = detect_emergency(text)
    assert not result.is_emergency, text
    assert result.suppressed == "informational"


@pytest.mark.parametrize("text", STILL_EMERGENCY)
def test_real_or_first_person_risk_messages_still_escalate(text):
    assert detect_emergency(text).is_emergency, text


# ---------------------------------------------------------------------------------------------------------------
# Workflow E at scale: the real rules (no stubbed evaluation) over more than 200 recently active accounts.
# ---------------------------------------------------------------------------------------------------------------
from bson import ObjectId  # noqa: E402

from app.models.appointment import utc_now  # noqa: E402
from app.services.fraud_detection_service import FraudDetectionService  # noqa: E402
from tests.test_payment import db  # noqa: E402,F401


def test_real_fraud_sweep_over_230_normal_accounts_flags_only_the_newest_hoarder(db):
    tag = str(ObjectId())
    now = utc_now()
    normal_ids = [f"{tag[:12]}{i:012d}" for i in range(230)]
    hoarder = "f" * 12 + tag[-12:]  # sorts after every normal id, the position R02-BUG-006 used to skip
    rows = [{"patientUserId": pid, "doctorUserId": f"r03doc{tag}", "appointmentDate": "2099-01-01", "startTime": "09:00",
             "status": "CANCELLED", "holdReleasedAt": now, "paymentStatus": "PENDING", "confirmedAt": None,
             "createdAt": now, "updatedAt": now, "r03Fixture": tag} for pid in normal_ids]  # one ordinary change of mind
    rows += [{"patientUserId": hoarder, "doctorUserId": f"r03doc{tag}", "appointmentDate": "2099-01-02", "startTime": t,
              "status": "PENDING", "paymentStatus": "PENDING", "confirmedAt": None, "createdAt": now, "updatedAt": now,
              "r03Fixture": tag} for t in ("09:00", "09:30", "10:00", "10:30", "11:00")]
    db["appointments"].insert_many(rows)
    before = {c: db[c].count_documents({}) for c in ("payments", "refund_requests", "users")}
    FraudDetectionService._last_sweep_at = None
    try:
        stats = FraudDetectionService.run_detection_sweep(db, force=True)
        assert stats["deferred"] == 0 and stats["candidates"] >= 231 and stats["evaluated"] == stats["candidates"]
        flagged = db["fraud_risk_assessments"].find_one({"relatedAccountId": hoarder})
        assert flagged and "SLOT_HOARDING_ATTEMPT" in flagged["triggeredRules"]
        assert db["fraud_risk_assessments"].count_documents({"relatedAccountId": {"$in": normal_ids}}) == 0
        # Review signals only: no payment, refund or account record is created or changed by the sweep.
        assert before == {c: db[c].count_documents({}) for c in before}
        appts = list(db["appointments"].find({"patientUserId": hoarder}, {"status": 1}))
        assert {a["status"] for a in appts} == {"PENDING"}  # the hoarder's holds are not cancelled automatically
    finally:
        db["appointments"].delete_many({"r03Fixture": tag})
        db["fraud_risk_assessments"].delete_many({"relatedAccountId": {"$in": normal_ids + [hoarder]}})
