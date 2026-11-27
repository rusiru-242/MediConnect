"""A05 fraud defect reproduction, runnable against any backend checkout (pre-fix main or the A05 branch).

Uses only FraudDetectionService.evaluate_account_risk / review_assessment, which exist in both versions, on a fresh
isolated local database whose name ends in _test (refused otherwise). Synthetic records only; no HTTP, no Stripe.

  <venv python> -I docs/uat/agent-completion/a05/a05_repro_fraud.py <backend dir> <label>

Checks:
  BUG-002  6 simultaneous evaluations of one account -> number of assessments stored
  BUG-003  after an administrator dismisses, re-evaluating the same evidence -> new alert?
  BUG-010  4 payment-retry holds released on ONE slot -> RAPID_CANCELLATION_PATTERN raised?
  P04-N12  slot hoarding (4 distinct unpaid slots) -> SLOT_HOARDING_ATTEMPT raised?
"""
import json
import os
import pathlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import uuid

backend, label = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2]
NAME = f"mediconnect_a05repro_{label}_test"
os.environ.update(MONGODB_URI=f"mongodb://127.0.0.1:27017/{NAME}", DATABASE_NAME=NAME,
                  STRIPE_SECRET_KEY="sk_test_mock_secret_key", STRIPE_WEBHOOK_SECRET="whsec_test_mock",
                  GEMINI_API_KEY="", OPENAI_API_KEY="", ENVIRONMENT="test")
assert NAME.endswith("_test")
sys.path.insert(0, str(backend))
from pymongo import MongoClient  # noqa: E402

client = MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=3000)
client.drop_database(NAME)
db = client[NAME]
from app.models.fraud_assessment import create_fraud_assessments_indexes  # noqa: E402
from app.services import fraud_detection_service as fds  # noqa: E402

create_fraud_assessments_indexes(db)
S = fds.FraudDetectionService
now = datetime.now(timezone.utc)
result = {"label": label, "backend": backend.name, "at": now.isoformat()}


def holds(account, slots, *, released=True):
    for i, start in enumerate(slots):
        db.appointments.insert_one({
            "patientUserId": account, "doctorUserId": "doc-a05", "appointmentDate": "2026-12-05", "startTime": start,
            "status": "CANCELLED", "cancelledBy": "PATIENT", "cancellationReason": "Reservation released by patient before payment",
            "paymentStatus": "UNPAID", "holdReleasedAt": now, "createdAt": now - timedelta(minutes=30 - i), "updatedAt": now})


# BUG-002: concurrency
holds("acct-race", ["09:00", "09:30", "10:00", "10:30"])
for _ in range(3):
    db.payments.insert_one({"patientUserId": "acct-race", "status": "FAILED", "createdAt": now, "stripePaymentIntentId": f"pi_{uuid.uuid4().hex}"})
barrier, real = threading.Barrier(6), uuid.uuid4


def lockstep():
    try:
        barrier.wait(timeout=2)
    except threading.BrokenBarrierError:
        pass
    return real()


with patch.object(fds, "uuid4", side_effect=lockstep):
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda _: S.evaluate_account_risk("acct-race", db=db), range(6)))
result["BUG-002_assessmentsStoredFor6ParallelEvaluations"] = db.fraud_risk_assessments.count_documents(
    {"relatedAccountId": "acct-race"})

# BUG-003: dismissal respected
first = S.evaluate_account_risk("acct-race", db=db)
S.review_assessment(first.assessmentId, "dismiss", "admin-a05", "Synthetic: explained", db=db)
again = S.evaluate_account_risk("acct-race", db=db)
result["BUG-003_newAlertFromSameEvidenceAfterDismissal"] = bool(again and again.assessmentId != first.assessmentId)

# BUG-010: payment retries on one slot
holds("acct-retry", ["11:00", "11:00", "11:00", "11:00"])
retry = S.evaluate_account_risk("acct-retry", db=db)
result["BUG-010_rulesForFourRetriesOnOneSlot"] = retry.triggeredRules if retry else []

# P04-N12: slot hoarding
holds("acct-hoard", ["13:00", "13:30", "14:00", "14:30"])
hoard = S.evaluate_account_risk("acct-hoard", db=db)
result["N12_rulesForFourDistinctUnpaidSlots"] = hoard.triggeredRules if hoard else []

client.drop_database(NAME)
out = pathlib.Path(__file__).resolve().parent / "evidence" / f"a05_repro_fraud_{label}.json"
out.write_text(json.dumps(result, indent=1), encoding="utf-8")
print(json.dumps(result, indent=1))
