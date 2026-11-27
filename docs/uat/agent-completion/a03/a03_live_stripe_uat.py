"""A03 live UAT: Stripe test mode, Stripe CLI webhook delivery, refunds and reservations (Agent 01).

Targets only the local UAT backend (127.0.0.1:8001 and, for the multi-process checks, 127.0.0.1:8002) on the local
`mediconnect_uat` database. Stripe calls use the sk_test_ key from backend/.env (never printed); every object must be
livemode=false. Webhooks are delivered by `stripe listen --forward-to 127.0.0.1:8001/api/payments/webhook` (owner
approved, A03). Payment methods are Stripe's test PaymentMethods. No real money moves, no real person is contacted.

Usage (repository root):
  backend\\venv\\Scripts\\python.exe -I docs\\uat\\agent-completion\\a03\\a03_live_stripe_uat.py main
  ... restart1 | restart2 | restart3   (backend restart during payment; the operator stops/starts the backend)
"""
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "docs" / "uat" / "phase-02"))
from p02api import call, login, unwrap  # noqa: E402  (refuses anything but 127.0.0.1:8001)

import stripe  # noqa: E402
from bson import ObjectId  # noqa: E402
from pymongo import MongoClient  # noqa: E402


def _env(name):
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(name + "="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


KEY = _env("STRIPE_SECRET_KEY")
assert KEY.startswith("sk_test_"), "Refusing: not a Stripe test key"
stripe.api_key = KEY
DB = MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=3000)["mediconnect_uat"]
COLOMBO = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(COLOMBO).date()
RUN = datetime.now(COLOMBO).strftime("%H%M%S")
OUT = HERE / "evidence"
STATE = OUT / "a03_restart_state.json"
EVIDENCE = {"mode": "stripe_test_mode", "backend": "127.0.0.1:8001", "database": "mediconnect_uat",
            "webhookDelivery": "stripe listen (Stripe CLI 1.50.1) -> 127.0.0.1:8001/api/payments/webhook",
            "colomboDate": str(TODAY), "run": RUN, "steps": []}
mask = lambda v: (v[:8] + "…" + v[-4:]) if isinstance(v, str) and len(v) > 14 else v  # noqa: E731


def step(sid, ok, **data):
    row = {"id": sid, "result": "PASS" if ok else "FAIL", **data}
    EVIDENCE["steps"].append(row)
    print(sid, row["result"], json.dumps(data, default=str)[:260], flush=True)
    return ok


def day(n):
    return str(TODAY + timedelta(days=n))


def free_slots(tok, doctor, date):
    return unwrap(call("GET", f"/doctors/{doctor}/availability?date={date}", tok=tok)[1]).get("slots", [])


def hold(tok, doctor, date, slot, base=None):
    body = {"doctorId": doctor, "availabilityId": slot["availabilityId"], "date": date, "startTime": slot["startTime"]}
    if base:
        return raw_call(base, "POST", "/appointments", body, tok)
    s, d = call("POST", "/appointments", body, tok=tok)
    return s, (unwrap(d).get("appointment") or d)


def raw_call(base, method, path, body, tok):
    assert base in ("http://127.0.0.1:8001/api", "http://127.0.0.1:8002/api")
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + tok})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read() or b"{}")
            return r.status, (unwrap(d).get("appointment") or d)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def intent(tok, appt_id):
    s, d = call("POST", "/payments/create-intent", {"appointmentId": appt_id, "amount": 1}, tok=tok)  # amount ignored
    return s, unwrap(d)


def pi_of(payment_id):
    return DB.payments.find_one({"_id": ObjectId(payment_id)})["stripePaymentIntentId"]


def confirm(pi, pm):
    try:
        return stripe.PaymentIntent.confirm(pi, payment_method=pm, return_url="https://example.invalid/return").status
    except stripe.error.CardError as exc:
        return f"card_error:{exc.code}"
    except stripe.error.InvalidRequestError as exc:
        return f"invalid_request:{exc.code}"


def appt(aid):
    return DB.appointments.find_one({"_id": ObjectId(aid)}) or {}


def wait(cond, timeout=40, every=1.0):
    end = time.time() + timeout
    while time.time() < end:
        value = cond()
        if value:
            return value
        time.sleep(every)
    return cond()


def stripe_event(event_type, object_id, timeout=40):
    """The Stripe-generated event for an object (from Stripe's own event list)."""
    def find():
        for ev in stripe.Event.list(type=event_type, limit=20).data:
            obj = ev.data.object.to_dict()
            if obj.get("id") == object_id or obj.get("payment_intent") == object_id:
                return ev
        return None
    return wait(find, timeout, 2.0)


def delivered(event):
    """Whether the backend stored and processed that exact Stripe event id (delivered by the CLI)."""
    if not event:
        return None
    return wait(lambda: DB.stripe_webhook_events.find_one({"_id": event.id, "status": "processed"}), 40)


def notifications(user_id, ntype, appointment_id):
    return DB.notifications.count_documents({"recipientUserId": user_id, "type": ntype,
                                             "relatedAppointmentId": appointment_id})


def uid(tok):
    return unwrap(call("GET", "/auth/me", tok=tok)[1]).get("id")


def main():
    a, b, c = login("uat.p02.patienta"), login("uat.p02.patientb"), login("uat.p02.patientc")
    admin, ortho = login("uat.admin"), login("uat.p02.doctor.ortho")
    a_id = uid(a)
    doctor = "UAT-P02-ORTHO"
    d_main, d_alt = day(5), day(6)
    slots = free_slots(a, doctor, d_main)
    step("fixture", len(slots) >= 6, date=d_main, freeSlots=len(slots), doctor=doctor)

    # ---------------------------------------------------------------- P01 success, P06 amount/currency, W05/W06
    s, ap = hold(a, doctor, d_main, slots[0])
    hold_secs = (ap.get("holdExpiresAt") and (datetime.fromisoformat(ap["holdExpiresAt"].replace("Z", "+00:00")) -
                                               datetime.fromisoformat(ap["createdAt"].replace("Z", "+00:00"))).total_seconds())
    step("A03-R01_atomic_reservation", s == 201 and ap.get("status") in ("PENDING", "HOLD"), http=s,
         status=ap.get("status"), holdSeconds=hold_secs)
    step("A03-R03_server_owned_10_minute_hold", hold_secs is not None and 595 <= hold_secs <= 605, holdSeconds=hold_secs)
    s2, pi = intent(a, ap["id"])
    real = stripe.PaymentIntent.retrieve(pi_of(pi["paymentId"]))
    fee = ap.get("consultationFee")
    step("A03-P06_amount_and_currency_server_owned",
         s2 == 201 and real.amount == int(round(fee * 100)) and real.currency == "lkr" and pi.get("amount") == real.amount
         and real.livemode is False, http=s2, clientSentAmount=1, consultationFee=fee, stripeAmountMinor=real.amount,
         currency=real.currency, livemode=real.livemode)
    s3, again = intent(a, ap["id"])
    step("A03-P05a_duplicate_intent_request_reuses_intent", s3 == 201 and pi_of(again["paymentId"]) == real.id, http=s3)
    st = confirm(real.id, "pm_card_visa")
    ev = stripe_event("payment_intent.succeeded", real.id)
    got = delivered(ev)
    cur = appt(ap["id"])
    step("A03-P01_test_payment_success_via_cli_webhook", st == "succeeded" and cur.get("status") == "CONFIRMED"
         and cur.get("paymentStatus") == "PAID" and bool(got), stripeStatus=st, appointment=cur.get("status"),
         confirmedBeforeAnyStatusCall=True, stripeEventId=mask(ev.id if ev else None),
         backendOutcome=(got or {}).get("outcome"))
    step("A03-W05_actual_stripe_test_webhook_delivery", bool(got) and got.get("outcome") == "success",
         eventType="payment_intent.succeeded", livemode=ev.livemode if ev else None, attempts=(got or {}).get("attempts"))
    pay = DB.payments.find_one({"_id": ObjectId(pi["paymentId"])})
    step("A03-W06_payment_success_reconciliation", pay["status"] == "SUCCEEDED" and pay.get("reconciliationState") == "CONFIRMED"
         and notifications(a_id, "PAYMENT_SUCCESS", ap["id"]) == 1, payment=pay["status"],
         reconciliation=pay.get("reconciliationState"), successNotices=notifications(a_id, "PAYMENT_SUCCESS", ap["id"]))
    s4, dup = intent(a, ap["id"])
    # Every PaymentIntent recorded for the appointment, retrieved directly (Stripe search is eventually consistent).
    charges = [stripe.PaymentIntent.retrieve(x["stripePaymentIntentId"]) for x in DB.payments.find({"appointmentId": ap["id"]})]
    step("A03-P05_duplicate_charge_prevention", s4 == 400 and sum(1 for x in charges if x.status == "succeeded") == 1,
         http=s4, detail=dup.get("detail"), intentsForAppointment=len(charges))
    for i in range(3):
        st_http, ps = call("GET", f"/payments/{pi['paymentId']}/status", tok=a)
    step("A03-P01b_repeated_status_refresh", st_http == 200 and unwrap(ps)["paymentStatus"] == "SUCCEEDED"
         and DB.appointment_events.count_documents({"appointmentId": ap["id"], "event": "PAYMENT_CONFIRMED"}) == 1,
         paymentConfirmedEvents=DB.appointment_events.count_documents({"appointmentId": ap["id"], "event": "PAYMENT_CONFIRMED"}))
    s5, other = call("GET", f"/payments/{pi['paymentId']}/status", tok=b)
    s6, other2 = intent(b, ap["id"])
    step("A03-P07_payment_ownership", s5 == 403 and s6 == 403, statusAsOtherPatient=s5, intentAsOtherPatient=s6)
    redeliver = stripe_event("payment_intent.succeeded", real.id)
    EVIDENCE["paidAppointment"] = ap["id"]

    # ---------------------------------------------------------------- P02 decline, P04 retry, W04 real ordering
    s, ap2 = hold(a, doctor, d_main, slots[1])
    _, pi2 = intent(a, ap2["id"])
    pid2 = pi_of(pi2["paymentId"])
    st = confirm(pid2, "pm_card_chargeDeclined")
    evf = stripe_event("payment_intent.payment_failed", pid2)
    gotf = delivered(evf)
    p2 = DB.payments.find_one({"_id": ObjectId(pi2["paymentId"])})
    step("A03-P02_declined_payment", st.startswith("card_error") and p2["status"] == "FAILED" and appt(ap2["id"])["status"]
         in ("PENDING", "HOLD") and notifications(a_id, "PAYMENT_FAILED", ap2["id"]) == 1 and bool(gotf),
         stripe=st, payment=p2["status"], appointment=appt(ap2["id"])["status"],
         failedEventOutcome=(gotf or {}).get("outcome"), failureNotices=notifications(a_id, "PAYMENT_FAILED", ap2["id"]))
    s7, retry = intent(a, ap2["id"])
    step("A03-P04a_retry_reuses_intent", s7 == 201 and pi_of(retry["paymentId"]) == pid2, http=s7)
    st = confirm(pid2, "pm_card_visa")
    evs = stripe_event("payment_intent.succeeded", pid2)
    gots = delivered(evs)
    step("A03-P04_payment_retry_after_decline", st == "succeeded" and appt(ap2["id"])["status"] == "CONFIRMED" and bool(gots),
         stripe=st, appointment=appt(ap2["id"])["status"], payment=DB.payments.find_one({"_id": ObjectId(pi2["paymentId"])})["status"],
         failureNoticesAfterSuccess=notifications(a_id, "PAYMENT_FAILED", ap2["id"]))

    # ---------------------------------------------------------------- P03 cancelled payment (release), R05, R06
    s, ap3 = hold(a, doctor, d_main, slots[2])
    _, pi3 = intent(a, ap3["id"])
    pid3 = pi_of(pi3["paymentId"])
    rs, rel = call("POST", f"/appointments/{ap3['id']}/release-hold", {}, tok=a)
    evc = stripe_event("payment_intent.canceled", pid3)
    gotc = delivered(evc)
    late = confirm(pid3, "pm_card_visa")
    free_again = any(x["startTime"] == slots[2]["startTime"] for x in free_slots(c, doctor, d_main))
    step("A03-P03_cancelled_payment", rs == 200 and stripe.PaymentIntent.retrieve(pid3).status == "canceled"
         and late.startswith("invalid_request") and bool(gotc), release=rs, stripe=stripe.PaymentIntent.retrieve(pid3).status,
         payAfterRelease=late, canceledEventOutcome=(gotc or {}).get("outcome"),
         payment=DB.payments.find_one({"_id": ObjectId(pi3["paymentId"])})["status"])
    step("A03-R05_manual_release", rs == 200 and appt(ap3["id"])["status"] == "CANCELLED"
         and appt(ap3["id"]).get("paymentStatus") == "UNPAID", status=appt(ap3["id"])["status"])
    step("A03-R06_released_slot_available", free_again, slot=slots[2]["startTime"])

    # ---------------------------------------------------------------- P08 expired hold (A03-BUG-005), R04
    s, ap4 = hold(b, doctor, d_main, slots[3])
    _, pi4 = intent(b, ap4["id"])
    pid4 = pi_of(pi4["paymentId"])
    DB.appointments.update_one({"_id": ObjectId(ap4["id"])}, {"$set": {"holdExpiresAt": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    released = wait(lambda: appt(ap4["id"]).get("status") == "CANCELLED", 150, 3)
    cancelled = wait(lambda: stripe.PaymentIntent.retrieve(pid4).status == "canceled", 150, 5)
    late4 = confirm(pid4, "pm_card_visa")
    step("A03-R04_automatic_expiry", bool(released) and appt(ap4["id"]).get("cancelledBy") == "SYSTEM",
         note="hold expiry simulated by moving holdExpiresAt into the past; released by the backend worker",
         status=appt(ap4["id"]).get("status"))
    step("A03-P08_expired_hold_payment", bool(cancelled) and late4.startswith("invalid_request")
         and appt(ap4["id"]).get("paymentStatus") != "PAID", stripeIntent=stripe.PaymentIntent.retrieve(pid4).status,
         payAfterExpiry=late4, payment=DB.payments.find_one({"_id": ObjectId(pi4["paymentId"])})["status"])
    s, exp = intent(b, ap4["id"])
    step("A03-P08b_new_intent_for_expired_hold_rejected", s == 400, http=s, detail=exp.get("detail"))
    before = json.loads((OUT / "before_open_intents_on_cancelled_holds.json").read_text())
    after = [{"paymentId": row["paymentId"], "stripeStatus": stripe.PaymentIntent.retrieve(
        DB.payments.find_one({"_id": ObjectId(row["paymentId"])})["stripePaymentIntentId"]).status,
        "payment": DB.payments.find_one({"_id": ObjectId(row["paymentId"])})["status"]} for row in before]
    step("A03-BUG-005_preexisting_open_intents_cancelled", all(x["stripeStatus"] == "canceled" for x in after), after=after)

    # ---------------------------------------------------------------- P09 payment after appointment cancellation
    s, ap5 = hold(c, doctor, d_main, slots[4])
    _, pi5 = intent(c, ap5["id"])
    cs, _ = call("POST", f"/appointments/{ap5['id']}/cancel", {"reason": "A03 cancel before paying"}, tok=c)
    late5 = confirm(pi_of(pi5["paymentId"]), "pm_card_visa")
    step("A03-P09_cancelled_appointment_payment", cs == 200 and late5.startswith("invalid_request")
         and appt(ap5["id"])["status"] == "CANCELLED", cancel=cs, payAfterCancel=late5)

    # ---------------------------------------------------------------- R08 duplicate reservation, R02 concurrency
    s1, first = hold(c, doctor, d_main, slots[5])
    s2_, second = hold(c, doctor, d_main, slots[5])
    step("A03-R08_duplicate_reservation_request", s1 == 201 and s2_ in (200, 201, 409)
         and DB.appointments.count_documents({"doctorUserId": appt(first["id"])["doctorUserId"], "appointmentDate": d_main,
                                              "startTime": slots[5]["startTime"], "status": {"$in": ["HOLD", "PENDING", "CONFIRMED"]}}) == 1,
         first=s1, second=s2_, secondDetail=second.get("detail"))
    call("POST", f"/appointments/{first['id']}/release-hold", {}, tok=c)

    alt = free_slots(a, doctor, d_alt)
    rounds = []
    toks = [a, b]
    for i, slot in enumerate(alt[:6]):
        bases = ["http://127.0.0.1:8001/api", "http://127.0.0.1:8002/api"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            res = list(pool.map(lambda k: hold(toks[k % 2], doctor, d_alt, slot, base=bases[k % 2]), range(4)))
        winners = [(k, r) for k, r in enumerate(res) if r[0] == 201]
        rounds.append({"slot": slot["startTime"], "codes": [r[0] for r in res], "winners": len(winners)})
        for k, w in winners:
            call("POST", f"/appointments/{w[1]['id']}/release-hold", {}, tok=toks[k % 2])
    step("A03-R02_concurrent_reservation_two_patients_two_processes", all(r["winners"] == 1 for r in rounds), rounds=rounds,
         processes=["127.0.0.1:8001", "127.0.0.1:8002"], index="idx_appt_doctor_slot_unique_active" in
         [i["name"] for i in DB.appointments.list_indexes()])

    refunds(a, b, admin, ortho, doctor, d_alt)
    webhook_local_checks()
    (OUT / "a03_live_stripe_uat.json").write_text(json.dumps(EVIDENCE, indent=1, default=str), encoding="utf-8")
    fails = [s["id"] for s in EVIDENCE["steps"] if s["result"] != "PASS"]
    print("SUMMARY", len(EVIDENCE["steps"]) - len(fails), "/", len(EVIDENCE["steps"]), "failed:", fails)


def paid(tok, doctor, date, slot, pm="pm_card_visa"):
    s, ap = hold(tok, doctor, date, slot)
    _, pi = intent(tok, ap["id"])
    pid = pi_of(pi["paymentId"])
    st = confirm(pid, pm)
    wait(lambda: appt(ap["id"]).get("status") == "CONFIRMED", 40)
    return ap, pi, pid, st


def refund_of(aid):
    return DB.refund_requests.find_one({"appointmentId": aid}, sort=[("createdAt", -1)]) or {}


def refunds(a, b, admin, ortho, doctor, date):
    slots = free_slots(a, doctor, date)
    # C01 patient cancellation (>24 h ahead -> existing 100% rule), C05 request, C06 approval, C10 reconciliation
    ap, pi, pid, st = paid(a, doctor, date, slots[0])
    s, pv = call("GET", f"/appointments/{ap['id']}/cancellation-preview", tok=a)
    cs, _ = call("POST", f"/appointments/{ap['id']}/cancel", {"reason": "A03 patient cancellation"}, tok=a)
    req = refund_of(ap["id"])
    step("A03-C01_patient_cancellation", cs == 200 and appt(ap["id"])["status"] == "CANCELLED", cancel=cs, preview=s)
    step("A03-C05_refund_request", bool(req) and req.get("status") == "requested" and req.get("source") == "patient",
         refundId=req.get("refundId"), rule=(req.get("policyEligibility") or {}).get("ruleApplied"),
         eligibleAmount=(req.get("policyEligibility") or {}).get("eligibleAmount"), paid=req.get("amount"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        outs = list(pool.map(lambda _: call("POST", f"/admin/workflow/refunds/{req['refundId']}/approve", {"notes": "A03"},
                                            tok=admin)[0], range(4)))
    stripe_refunds = stripe.Refund.list(payment_intent=pid).data
    step("A03-C09_concurrent_refund_approval", outs.count(200) == 1 and len(stripe_refunds) == 1, httpCodes=outs,
         stripeRefunds=len(stripe_refunds))
    step("A03-C06_admin_refund_approval", outs.count(200) == 1 and refund_of(ap["id"]).get("status") == "succeeded",
         status=refund_of(ap["id"]).get("status"), stripeRefund=stripe_refunds[0].status if stripe_refunds else None,
         metadataRefundId=(stripe_refunds[0].metadata.to_dict() if stripe_refunds[0].metadata else {}).get("refundId") if stripe_refunds else None)
    s2, _ = call("POST", f"/admin/workflow/refunds/{req['refundId']}/approve", {"notes": "again"}, tok=admin)
    s3, _ = call("POST", "/appointments/" + ap["id"] + "/cancel", {"reason": "again"}, tok=a)
    step("A03-C08_duplicate_refund_prevention", s2 in (400, 409) and len(stripe.Refund.list(payment_intent=pid).data) == 1,
         reapprove=s2, recancel=s3)
    events = [stripe_event(t, pid, 30) for t in ("charge.refunded", "refund.created")]
    got = [delivered(e) for e in events if e]
    pay = DB.payments.find_one({"_id": ObjectId(pi["paymentId"])})
    step("A03-C10_stripe_test_refund_reconciliation", pay["status"] == "REFUNDED" and pay.get("refundedAmount") == pay["amount"]
         and refund_of(ap["id"]).get("status") == "succeeded" and appt(ap["id"]).get("paymentStatus") == "REFUNDED",
         payment=pay["status"], refunded=pay.get("refundedAmount"), captured=pay["amount"],
         refundWebhooks=[{"type": e.type, "outcome": (g or {}).get("outcome")} for e, g in zip([e for e in events if e], got)],
         requestStatusAfterWebhooks=refund_of(ap["id"]).get("status"))
    step("A03-W07_refund_status_reconciliation_via_cli", bool(got) and all(got) and refund_of(ap["id"]).get("status") == "succeeded",
         outcomes=[(g or {}).get("outcome") for g in got])

    # C07 rejection
    ap2, pi2, pid2, _ = paid(b, doctor, date, slots[1])
    call("POST", f"/appointments/{ap2['id']}/cancel", {"reason": "A03 rejection case"}, tok=b)
    r2 = refund_of(ap2["id"])
    rs, _ = call("POST", f"/admin/workflow/refunds/{r2['refundId']}/reject", {"reason": "A03 synthetic rejection"}, tok=admin)
    step("A03-C07_admin_refund_rejection", rs == 200 and refund_of(ap2["id"])["status"] == "rejected"
         and not stripe.Refund.list(payment_intent=pid2).data, http=rs)

    # C02 doctor cancellation -> 100% (existing rule), refund failure card if Stripe offers one
    ap3, pi3, pid3, st3 = paid(a, doctor, date, slots[2], pm="pm_card_refundFail")
    if not st3 == "succeeded":
        ap3, pi3, pid3, st3 = paid(a, doctor, date, slots[2])
    ds, _ = call("POST", f"/doctors/me/appointments/{ap3['id']}/cancel", {"reason": "A03 doctor unavailable"}, tok=ortho)
    r3 = refund_of(ap3["id"])
    step("A03-C02_doctor_cancellation", ds == 200 and r3.get("source") == "doctor"
         and (r3.get("policyEligibility") or {}).get("eligibleAmount") == r3.get("amount"), http=ds,
         rule=(r3.get("policyEligibility") or {}).get("ruleApplied"), paymentMethod="pm_card_refundFail" if st3 else None)
    a3, _ = call("POST", f"/admin/workflow/refunds/{r3['refundId']}/approve", {"notes": "A03 doctor cancellation"}, tok=admin)
    failed = wait(lambda: refund_of(ap3["id"]).get("requiresReview") or refund_of(ap3["id"]).get("status") == "failed", 90, 5)
    EVIDENCE["refundFailureCard"] = {"approve": a3, "status": refund_of(ap3["id"]).get("status"),
                                     "requiresReview": refund_of(ap3["id"]).get("requiresReview"),
                                     "stripe": [x.status for x in stripe.Refund.list(payment_intent=pid3).data]}
    step("A03-C10b_refund_failure_after_success_flagged_for_review", bool(failed), **EVIDENCE["refundFailureCard"])

    # C03 reschedule to a valid slot; C04 failed reschedule keeps the booking; U07 obsolete reminders
    ap4, pi4, pid4, _ = paid(b, doctor, date, slots[3])
    taken_by_a, _, _, _ = paid(a, doctor, date, slots[4])
    new = free_slots(b, doctor, day(7))[0]
    f_s, f_d = call("POST", f"/appointments/{ap4['id']}/reschedule", {"newDate": date, "newStartTime": slots[4]["startTime"]}, tok=b)
    kept = appt(ap4["id"])
    step("A03-C04_failed_reschedule_preserves_booking", f_s == 409 and kept["startTime"] == slots[3]["startTime"]
         and kept["status"] == "CONFIRMED" and kept["paymentStatus"] == "PAID", http=f_s, detail=f_d.get("detail"))
    r_s, _ = call("POST", f"/appointments/{ap4['id']}/reschedule", {"newDate": day(7), "newStartTime": new["startTime"]}, tok=b)
    moved = appt(ap4["id"])
    step("A03-C03_rescheduling", r_s == 200 and moved["appointmentDate"] == day(7) and moved["startTime"] == new["startTime"]
         and moved["paymentStatus"] == "PAID" and moved.get("appointmentVersion", 1) >= 2, http=r_s,
         version=moved.get("appointmentVersion"), remindersSent=moved.get("remindersSent"))
    EVIDENCE["rescheduledAppointment"] = ap4["id"]
    EVIDENCE["occupiedAppointment"] = taken_by_a["id"]


def webhook_local_checks():
    """Locally signed events (W01-W04) against the same running backend and its CLI signing secret."""
    import hashlib
    import hmac
    secret = (pathlib.Path(os.environ["A03_WHSEC_FILE"]).read_text().strip())
    assert secret.startswith("whsec_")

    def post(event, sec=None, tamper=False):
        body = json.dumps(event).encode()
        ts = str(int(time.time()))
        sig = hmac.new((sec or secret).encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        if tamper:
            body = body.replace(b'"livemode": false', b'"livemode": true')
        return call("POST", "/payments/webhook", raw=body, headers={"Stripe-Signature": f"t={ts},v1={sig}"})

    ev = {"id": f"evt_a03_local_{RUN}", "object": "event", "type": "payment_intent.canceled", "livemode": False,
          "created": int(time.time()), "data": {"object": {"id": "pi_a03_unknown", "object": "payment_intent"}}}
    s1, d1 = post(ev)
    step("A03-W01_valid_locally_signed_event", s1 == 200, http=s1, outcome=d1.get("status"))
    s2, _ = post({**ev, "id": ev["id"] + "_bad"}, sec="whsec_not_the_secret")
    s3, _ = post({**ev, "id": ev["id"] + "_tampered"}, tamper=True)
    step("A03-W02_invalid_signature", s2 == 400 and s3 == 400, wrongSecret=s2, tamperedBody=s3)
    s4, d4 = post(ev)
    step("A03-W03_duplicate_event", s4 == 200 and d4.get("status") == "already_processed", http=s4, outcome=d4.get("status"))
    paid_id = EVIDENCE.get("paidAppointment")
    pay = DB.payments.find_one({"appointmentId": paid_id}) if paid_id else None
    if pay:
        late = {"id": f"evt_a03_late_fail_{RUN}", "object": "event", "type": "payment_intent.payment_failed",
                "livemode": False, "created": int(time.time()) - 600,
                "data": {"object": {"id": pay["stripePaymentIntentId"], "object": "payment_intent",
                                    "last_payment_error": {"message": "late decline"}}}}
        s5, d5 = post(late)
        step("A03-W04_out_of_order_event", s5 == 200 and d5.get("status") == "ignored_out_of_order"
             and appt(paid_id)["status"] in ("CONFIRMED", "CANCELLED")
             and DB.payments.find_one({"_id": pay["_id"]})["status"] in ("SUCCEEDED", "REFUNDED"), http=s5,
             outcome=d5.get("status"))


# ------------------------------------------------------------------------- backend restart during payment (R07/P10)
def restart1():
    a = login("uat.p02.patientc")
    doctor = "UAT-P02-SPINE"
    slot = free_slots(a, doctor, day(4))[0]
    s, ap = hold(a, doctor, day(4), slot)
    _, pi = intent(a, ap["id"])
    STATE.write_text(json.dumps({"appointmentId": ap["id"], "paymentId": pi["paymentId"], "intent": pi_of(pi["paymentId"])}))
    print("restart1", s, ap.get("status"), "now stop the backend")


def restart2():
    st = json.loads(STATE.read_text())
    try:
        urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=3)
        print("backend still up: stop it first")
        return
    except Exception:
        pass
    status = confirm(st["intent"], "pm_card_visa")
    st["confirmedWhileDown"] = status
    st["appointmentWhileDown"] = appt(st["appointmentId"]).get("status")
    STATE.write_text(json.dumps(st))
    print("restart2 paid while backend down:", status, st["appointmentWhileDown"], "now start the backend")


def restart3():
    st = json.loads(STATE.read_text())
    a = login("uat.p02.patientc")
    before = appt(st["appointmentId"]).get("status")
    s, ps = call("GET", f"/payments/{st['paymentId']}/status", tok=a)
    after = appt(st["appointmentId"]).get("status")
    ev = stripe_event("payment_intent.succeeded", st["intent"], 20)
    logged = DB.stripe_webhook_events.find_one({"_id": ev.id}) if ev else None
    out = {"paidWhileBackendDown": st.get("confirmedWhileDown"), "appointmentWhileDown": st.get("appointmentWhileDown"),
           "appointmentAfterRestartBeforeRefresh": before, "statusRefreshHttp": s,
           "paymentStatus": unwrap(ps).get("paymentStatus"), "appointmentAfterRefresh": after,
           "stripeEvent": mask(ev.id if ev else None), "eventReachedBackend": bool(logged),
           "note": "The Stripe CLI does not redeliver an event that failed while the backend was down; the patient's "
                   "status refresh (Stripe read) recovers it. Production Stripe retries for up to 3 days."}
    out["result"] = "PASS" if (st.get("confirmedWhileDown") == "succeeded" and after == "CONFIRMED"
                               and unwrap(ps).get("paymentStatus") == "SUCCEEDED") else "FAIL"
    (OUT / "a03_backend_restart_during_payment.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"main": main, "restart1": restart1, "restart2": restart2, "restart3": restart3}[sys.argv[1]]()
