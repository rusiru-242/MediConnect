"""A05 UAT negative check (F04): an account with no unpaid holds in the last 24 hours books one slot and releases it.

The account used as "normal" in a05_probe.py (uat.p02.patientb) already had four unpaid holds from the A03 UAT run
earlier the same day, so the rule correctly flagged it; this run uses an account whose 24-hour history is empty first.
Local UAT only. Writes evidence/a05_negative.json.
"""
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "phase-02"))
from a05_probe import DB, free_slots, hold, uid  # noqa: E402
from p02api import call, login, unwrap  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
admin, alpha = login("uat.admin"), login("uat.p03.doctor.alpha")
alpha_id = uid(alpha)
profile_id = str(DB.doctor_profiles.find_one({"userId": alpha_id})["_id"])
since = datetime.now(timezone.utc) - timedelta(hours=24)
result = {"at": datetime.now(timezone.utc).isoformat(), "candidates": []}
for key in ("uat.patient2", "uat.patient1", "uat.p04.patienta", "uat.p04.patientb"):
    tok = login(key)
    pid = uid(tok)
    recent = DB.appointments.count_documents({"patientUserId": pid, "createdAt": {"$gte": since}})
    result["candidates"].append({"account": key, "bookingsLast24h": recent})
    if recent == 0:
        break
assert recent == 0, "no account without recent bookings"
result["account"] = key
slot = free_slots(alpha_id, 1)[0]
appt = hold(tok, profile_id, slot)
result["release"] = call("POST", f"/appointments/{appt}/release-hold", {}, tok=tok)[0]
s, body = call("POST", f"/security/fraud/assessments/evaluate?accountId={pid}", tok=admin)
result["evaluate"] = {"http": s, "result": body}
result["openAssessments"] = DB.fraud_risk_assessments.count_documents({"relatedAccountId": pid,
                                                                       "openKey": {"$exists": True}})
result["accountStatus"] = DB.users.find_one({"_id": __import__("bson").ObjectId(pid)})["accountStatus"]
(HERE / "evidence" / "a05_negative.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
print(json.dumps(result, default=str))
