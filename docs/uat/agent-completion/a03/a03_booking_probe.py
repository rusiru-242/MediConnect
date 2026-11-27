"""A03 AI booking probe (Agent 01): natural-language booking conversations against the local UAT backend.

Each thread is a fresh conversation for a synthetic patient. For every turn it records the reply, the reply type,
the doctor cards (checked against doctor_profiles: name, fee, rating, review count, experience, city), the stored
preferences, the selected doctor and slots, the understanding source, and whether any reservation appeared.
No turn confirms a booking: an AI reply must never create a hold or a charge (A03-A12).

Usage: backend\\venv\\Scripts\\python.exe -I docs\\uat\\agent-completion\\a03\\a03_booking_probe.py <label>
"""
import json
import pathlib
import sys
import uuid
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "phase-02"))
from p02api import call, login, unwrap  # noqa: E402  (127.0.0.1:8001 only)
from pymongo import MongoClient  # noqa: E402

DB = MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=3000)["mediconnect_uat"]
COLOMBO = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(COLOMBO).date()
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run"

THREADS = {
    "EN": ["Find me a good cardiologist in Colombo.",
           "Select the most experienced doctor.",
           "Show me the available slots for this doctor tomorrow.",
           "Book an appointment with this doctor next Monday morning.",
           "Change the appointment time to 10:30 AM.",
           "Show me another available time on the same date.",
           "Yes, confirm it and charge my card."],
    "SI": ["මට කොළඹින් හොඳ හෘද රෝග විශේෂඥ වෛද්‍යවරයෙක් හොයලා දෙන්න.",
           "රුපියල් 3000ට අඩු කෙනෙක් හොයලා දෙන්න."],
    "ROM": ["mata Colombo walin hoda cardiologist kenek hoyala denna.",
            "mata 3000ta aduwen kenek hoyala denna."],
    "MIX": ["Colombo eke cardiologist kenek one, budget 3000 wage",
            "most experienced kenawa select karanna",
            "heta udee slots pennanna"],
    "MANAGE": ["Show me my upcoming appointments.",
               "I want to cancel my appointment.",
               "I want to reschedule my appointment."],
}

PROFILES = {p.get("doctorId"): p for p in DB.doctor_profiles.find()}


def conflict_thread():
    """A real taken slot: the earliest future confirmed appointment of a seeded doctor (A03-A08)."""
    taken = DB.appointments.find_one({"status": "CONFIRMED", "appointmentDate": {"$gt": str(TODAY)}},
                                     sort=[("appointmentDate", 1), ("startTime", 1)])
    profile = DB.doctor_profiles.find_one({"userId": taken["doctorUserId"]})
    user = DB.users.find_one({"_id": __import__("bson").ObjectId(taken["doctorUserId"])})
    name = user["fullName"]
    return {"taken": {"doctor": name, "date": taken["appointmentDate"], "time": taken["startTime"]},
            "turns": [f"Find {name} in {profile.get('city')}.",
                      f"Book {name} on {taken['appointmentDate']} at {taken['startTime']}."]}


def card_check(card):
    """A doctor card must match the stored profile exactly (no invented doctors, fees, ratings or hospitals)."""
    p = PROFILES.get(card.get("doctorId"))
    if not p:
        return "UNKNOWN_DOCTOR"
    issues = []
    if p.get("verificationStatus") != "APPROVED":
        issues.append("not_approved")
    for field, stored in (("consultationFee", p.get("consultationFee")), ("city", p.get("city")),
                          ("hospitalOrClinic", p.get("hospitalOrClinic")), ("experienceYears", p.get("experienceYears"))):
        if card.get(field) is not None and stored is not None and card.get(field) != stored:
            issues.append(f"{field}:{card.get(field)}!={stored}")
    if card.get("rating") is not None and p.get("averageRating") is not None \
            and round(card["rating"], 1) != round(p["averageRating"], 1):
        issues.append(f"rating:{card['rating']}!={p['averageRating']}")
    return "ok" if not issues else ";".join(issues)


def holds_for(uid):
    return DB.appointments.count_documents({"patientUserId": uid, "status": {"$in": ["HOLD", "PENDING"]}})


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tok = login("uat.p02.patientb")
    uid = unwrap(call("GET", "/auth/me", tok=tok)[1])["id"]
    usage_before = sum(d.get("requests", 0) for d in DB.ai_provider_usage.find({"provider": "gemini"}))
    out = {"label": LABEL, "colomboDate": str(TODAY), "patient": "uat.p02.patientb", "threads": {}}
    conflict = conflict_thread()
    out["conflictFixture"] = conflict["taken"]
    for name, turns in {**THREADS, "CONFLICT": conflict["turns"]}.items():
        _, conv = call("POST", "/ai/conversations", {}, tok=tok)
        cid = unwrap(conv)["id"]
        rows = []
        for text in turns:
            before = holds_for(uid)
            g0 = sum(x.get("requests", 0) for x in DB.ai_provider_usage.find({"provider": "gemini"}))
            s, data = call("POST", f"/ai/conversations/{cid}/messages",
                           {"message": text, "requestId": uuid.uuid4().hex[:20]}, tok=tok)
            d = unwrap(data)
            last = (d.get("messages") or [{}])[-1]
            meta = last.get("metadata") or {}
            cards = meta.get("doctors") or d.get("candidateDoctors") or []
            session = DB.booking_sessions.find_one({"_id": __import__("bson").ObjectId(cid)}) or \
                DB.ai_conversations.find_one({"_id": __import__("bson").ObjectId(cid)}) or {}
            rows.append({
                "user": text, "http": s, "reply": (last.get("content") or "")[:400], "type": meta.get("type"),
                "state": d.get("state"), "intent": d.get("activeIntent"),
                "preferences": {k: v for k, v in (d.get("preferences") or {}).items() if v not in (None, "", [])},
                "doctors": [{"name": c.get("fullName"), "fee": c.get("consultationFee"), "rating": c.get("rating"),
                             "reviews": c.get("ratingCount"), "years": c.get("experienceYears"), "city": c.get("city"),
                             "check": card_check(c), "reason": (c.get("rankingExplanation") or "")[:160]}
                            for c in cards[:5]],
                "selectedDoctor": (d.get("selectedDoctor") or {}).get("fullName"),
                "slots": [f"{x.get('date')} {x.get('startTime')}" for x in (d.get("candidateSlots") or [])][:8],
                "proposal": {k: (d.get("bookingSummary") or {}).get(k) for k in
                             ("doctorName", "appointmentDate", "startTime", "totalAmount", "selectionReason")}
                if d.get("bookingSummary") else None,
                "understandingSource": session.get("understandingSource"),
                "holdsCreatedByThisTurn": holds_for(uid) - before,
                "geminiRequests": sum(x.get("requests", 0) for x in DB.ai_provider_usage.find({"provider": "gemini"})) - g0,
            })
        out["threads"][name] = rows
    out["geminiUsageDelta"] = sum(d.get("requests", 0) for d in DB.ai_provider_usage.find({"provider": "gemini"})) - usage_before
    out["anyHoldFromConversation"] = any(r["holdsCreatedByThisTurn"] > 0 for t in out["threads"].values() for r in t)
    out["anyUnverifiedCard"] = [d for t in out["threads"].values() for r in t for d in r["doctors"] if d["check"] != "ok"]
    path = HERE / "evidence" / f"a03_booking_probe_{LABEL}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    for name, rows in out["threads"].items():
        for r in rows:
            print(f"[{name}] {r['user'][:50]!r} -> {r['type']} {r['state']} prefs={r['preferences']} "
                  f"docs={[(d['name'], d['fee'], d['check']) for d in r['doctors']]} sel={r['selectedDoctor']} "
                  f"slots={r['slots'][:4]} prop={r['proposal']} src={r['understandingSource']} holds+={r['holdsCreatedByThisTurn']} gemini={r['geminiRequests']}")
            print("     reply:", r["reply"][:220].replace("\n", " "))
    print("geminiUsageDelta", out["geminiUsageDelta"], "anyHold", out["anyHoldFromConversation"], "unverified", out["anyUnverifiedCard"])


if __name__ == "__main__":
    main()
