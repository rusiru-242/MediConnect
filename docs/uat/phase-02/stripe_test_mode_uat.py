"""Phase 02 Stripe TEST-MODE verification against the local UAT backend (127.0.0.1:8001, mediconnect_uat).

Run from backend/ with the backend virtualenv:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\phase-02\\stripe_test_mode_uat.py OUT.json

Safety:
- Refuses to run unless STRIPE_SECRET_KEY in backend/.env starts with sk_test_ (test mode only).
- Card data never touches this script: Stripe's documented test PaymentMethods are used
  (pm_card_visa = success, pm_card_chargeDeclined = decline). No real money moves.
- Secrets (API key, webhook secret, client secrets) are never printed or written; PaymentIntent and refund
  ids are masked in the evidence file.
- Uses only the dedicated synthetic Phase 02 fixtures (uat.p02.*), never the owner's bookings.
- Webhook: the Stripe CLI is not installed, so Stripe cannot deliver events to this local backend. The
  "webhook" steps sign the REAL test-mode PaymentIntent object locally with the configured webhook secret
  and POST it. This verifies signature checking and idempotent processing, NOT external delivery.
"""
import hashlib
import hmac
import json
import os
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p02api import call, login, unwrap  # noqa: E402

import stripe  # noqa: E402
from pymongo import MongoClient  # noqa: E402
from bson import ObjectId  # noqa: E402


def _env(name):
    for line in (pathlib.Path(__file__).resolve().parents[3] / 'backend' / '.env').read_text(encoding='utf-8').splitlines():
        if line.strip().startswith(name + '='):
            return line.split('=', 1)[1].strip().strip('"\'')
    return ''


KEY, WHSEC = _env('STRIPE_SECRET_KEY'), _env('STRIPE_WEBHOOK_SECRET')
assert KEY.startswith('sk_test_'), 'Refusing: not a Stripe test key'
stripe.api_key = KEY
DB = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000)['mediconnect_uat']
mask = lambda v: (v[:3] + '…' + v[-6:]) if isinstance(v, str) and len(v) > 12 else v  # noqa: E731
EVIDENCE = {'mode': 'stripe_test_mode', 'backend': '127.0.0.1:8001', 'database': 'mediconnect_uat', 'steps': []}


def step(name, **data):
    EVIDENCE['steps'].append({'step': name, **data})
    print(name, json.dumps(data, default=str)[:300])


def free_slots(tok, doctor, date):
    day = unwrap(call('GET', f'/doctors/{doctor}/availability?date={date}', tok=tok)[1])
    return [s for s in day.get('slots', [])]


def hold(tok, doctor, date, slot):
    s, d = call('POST', '/appointments', {'doctorId': doctor, 'availabilityId': slot['availabilityId'], 'date': date,
                                          'startTime': slot['startTime']}, tok=tok)
    return s, (unwrap(d).get('appointment') or {})


def intent(tok, appt_id):
    s, d = call('POST', '/payments/create-intent', {'appointmentId': appt_id, 'amount': 1}, tok=tok)  # amount ignored
    return s, unwrap(d)


def pi_id_of(payment_id):
    return DB.payments.find_one({'_id': ObjectId(payment_id)})['stripePaymentIntentId']


def confirm(pi, pm):
    try:
        return stripe.PaymentIntent.confirm(pi, payment_method=pm, return_url='https://example.invalid/return').status
    except stripe.error.CardError as exc:
        return f'card_error:{exc.code}'


def signed_webhook(event_type, obj, signature_secret=None):
    payload = json.dumps({'id': f'evt_local_{int(time.time()*1000)}', 'object': 'event', 'type': event_type,
                          'livemode': False, 'data': {'object': obj}}).encode()
    ts = str(int(time.time()))
    sig = hmac.new((signature_secret or WHSEC).encode(), f'{ts}.'.encode() + payload, hashlib.sha256).hexdigest()
    return call('POST', '/payments/webhook', raw=payload, headers={'Stripe-Signature': f't={ts},v1={sig}'})


def main(out):
    a, b, c = login('uat.p02.patienta'), login('uat.p02.patientb'), login('uat.p02.patientc')
    admin, doc = login('uat.admin'), login('uat.p02.doctor.ortho')
    date = '2026-12-02'
    slots = free_slots(a, 'UAT-P02-ORTHO', date)
    step('fixture_free_slots', date=date, count=len(slots))

    # S1 success, server-owned amount, duplicate submissions, status refresh, webhook duplicates
    s, appt = hold(a, 'UAT-P02-ORTHO', date, slots[0])
    s2, pi = intent(a, appt['id'])
    real = stripe.PaymentIntent.retrieve(pi_id_of(pi['paymentId']))
    step('S1_hold_and_intent', hold_http=s, intent_http=s2, amount_minor=pi.get('amount'), currency=pi.get('currency'),
         stripe_amount=real.amount, stripe_currency=real.currency, livemode=real.livemode,
         client_amount_sent=1, appointment_fee=appt.get('consultationFee'))
    s3, pi_again = intent(a, appt['id'])
    step('S1_duplicate_intent_before_pay_reuses_same', http=s3, same_payment=pi_again.get('paymentId') == pi['paymentId'],
         same_intent=pi_id_of(pi_again['paymentId']) == real.id)
    step('S1_confirm_visa', stripe_status=confirm(real.id, 'pm_card_visa'))
    for i in range(2):
        st, ps = call('GET', f"/payments/{pi['paymentId']}/status", tok=a)
        step(f'S1_status_refresh_{i+1}', http=st, paymentStatus=unwrap(ps).get('paymentStatus'),
             appointmentStatus=unwrap(ps).get('appointmentStatus'))
    s4, dup = intent(a, appt['id'])
    step('S1_duplicate_intent_after_pay_rejected', http=s4, detail=dup.get('detail'))
    succeeded = stripe.PaymentIntent.retrieve(real.id)
    for i in range(2):
        ws, wd = signed_webhook('payment_intent.succeeded', succeeded.to_dict())
        step(f'S1_locally_signed_webhook_delivery_{i+1}', http=ws, result=wd.get('status'))
    bs, bd = signed_webhook('payment_intent.succeeded', {'id': real.id}, signature_secret='whsec_wrong_secret')
    step('S1_invalid_signature_rejected', http=bs, detail=bd.get('detail'))
    ap = DB.appointments.find_one({'_id': ObjectId(appt['id'])})
    step('S1_db_reconciliation', appointment_status=ap['status'], payment_status=ap['paymentStatus'],
         payments_for_appointment=DB.payments.count_documents({'appointmentId': appt['id']}),
         stripe_amount_received=succeeded.amount_received, stripe_status=succeeded.status,
         intents_for_appointment=len(list(stripe.PaymentIntent.search(query=f"metadata['appointmentId']:'{appt['id']}'")
                                         .auto_paging_iter())),
         notifications_patient=DB.notifications.count_documents({'relatedAppointmentId': appt['id'], 'type': 'PAYMENT_SUCCESS'}),
         events=[e['event'] for e in DB.appointment_events.find({'appointmentId': appt['id']})])
    det = [call('GET', f"/appointments/{appt['id']}", tok=t) for t in (a, doc)]
    step('S1_detail_patient_and_doctor', http=[x[0] for x in det], amountPaid=[unwrap(x[1]).get('amountPaid') for x in det],
         bookingReference_full=unwrap(det[0][1]).get('bookingReference') == appt['id'])
    s1_appt = appt

    # S2 decline then retry on the same intent
    s, appt = hold(b, 'UAT-P02-ORTHO', date, slots[1])
    _, pi = intent(b, appt['id'])
    pid = pi_id_of(pi['paymentId'])
    step('S2_confirm_declined_card', stripe_status=confirm(pid, 'pm_card_chargeDeclined'))
    st, ps = call('GET', f"/payments/{pi['paymentId']}/status", tok=b)
    step('S2_status_after_decline', paymentStatus=unwrap(ps).get('paymentStatus'), appointmentStatus=unwrap(ps).get('appointmentStatus'))
    _, retry = intent(b, appt['id'])
    step('S2_retry_reuses_intent', same_intent=pi_id_of(retry['paymentId']) == pid)
    step('S2_confirm_visa_after_decline', stripe_status=confirm(pid, 'pm_card_visa'))
    call('GET', f"/payments/{pi['paymentId']}/status", tok=b)
    ap = DB.appointments.find_one({'_id': ObjectId(appt['id'])})
    step('S2_db', appointment_status=ap['status'], payment_status=ap['paymentStatus'],
         payments=DB.payments.count_documents({'appointmentId': appt['id']}))
    s2_appt = appt

    # S3 PaymentSheet closed (no confirmation), then explicit release (BUG-063)
    s, appt = hold(c, 'UAT-P02-ORTHO', date, slots[2])
    _, pi = intent(c, appt['id'])
    pid = pi_id_of(pi['paymentId'])
    ap = DB.appointments.find_one({'_id': ObjectId(appt['id'])})
    step('S3_after_sheet_closed', appointment_status=ap['status'], payment_status=ap['paymentStatus'])
    rs, rd = call('POST', f"/appointments/{appt['id']}/release-hold", {}, tok=c)
    step('S3_release_hold', http=rs, status=unwrap(rd).get('status'), stripe_intent_status=stripe.PaymentIntent.retrieve(pid).status,
         slot_free_again=slots[2]['startTime'] in [x['startTime'] for x in free_slots(a, 'UAT-P02-ORTHO', date)])
    rs2, _ = call('POST', f"/appointments/{appt['id']}/release-hold", {}, tok=c)
    step('S3_release_again_idempotent', http=rs2)
    xs, xd = hold(a, 'UAT-P02-ORTHO', date, slots[2])
    step('S3_other_patient_books_released_slot', http=xs)
    if xd.get('id'):
        call('POST', f"/appointments/{xd['id']}/release-hold", {}, tok=a)

    # S4 payment completing after the hold expired: never confirmed; admin verification and refund (P-05r)
    s, appt = hold(c, 'UAT-P02-ORTHO', date, slots[3])
    _, pi = intent(c, appt['id'])
    pid = pi_id_of(pi['paymentId'])
    DB.appointments.update_one({'_id': ObjectId(appt['id'])}, {'$set': {'holdExpiresAt': DB.client.admin.command('isMaster')['localTime']}})
    step('S4_hold_expiry_simulated_on_fixture', note='holdExpiresAt set to now on the synthetic fixture instead of waiting 10 minutes')
    step('S4_confirm_visa_after_expiry', stripe_status=confirm(pid, 'pm_card_visa'))
    call('GET', f"/payments/{pi['paymentId']}/status", tok=c)
    pay = DB.payments.find_one({'_id': ObjectId(pi['paymentId'])})
    ap = DB.appointments.find_one({'_id': ObjectId(appt['id'])})
    step('S4_not_confirmed_review_required', appointment_status=ap['status'], appointment_payment=ap['paymentStatus'],
         reconciliationState=pay.get('reconciliationState'), reason=pay.get('reconciliationReason'))
    ls, ld = call('GET', '/admin/payments?status=SUCCEEDED&page=1&pageSize=50', tok=admin)
    step('S4_admin_payment_list', http=ls, total=unwrap(ld).get('total'))
    rcs, rcd = call('POST', '/admin/workflow/reconciliation/run', {}, tok=admin)
    step('S4_admin_reconciliation_run', http=rcs, keys=sorted(unwrap(rcd).keys())[:8] if isinstance(unwrap(rcd), dict) else None)
    fs, fd = call('POST', f"/payments/{pi['paymentId']}/reconcile-refund", {}, tok=admin)
    step('S4_admin_reconcile_refund', http=fs, state=unwrap(fd).get('reconciliationState'),
         stripe_refunds=[r.status for r in stripe.Refund.list(payment_intent=pid).auto_paging_iter()])
    fs2, fd2 = call('POST', f"/payments/{pi['paymentId']}/reconcile-refund", {}, tok=admin)
    step('S4_admin_reconcile_refund_repeat', http=fs2, stripe_refund_count=len(list(stripe.Refund.list(payment_intent=pid).auto_paging_iter())))

    # S5 paid cancellation -> refund request -> admin approval -> real test-mode refund (P-05o/P-05p)
    pv, pvd = call('GET', f"/appointments/{s1_appt['id']}/cancellation-preview", tok=a)
    step('S5_cancellation_preview', http=pv, refund=unwrap(pvd).get('refund'), requiresAdminApproval=unwrap(pvd).get('requiresAdminApproval'))
    cs, cd = call('POST', f"/appointments/{s1_appt['id']}/cancel", {'reason': 'Phase 02 UAT cancellation'}, tok=a)
    step('S5_cancel_paid', http=cs, status=unwrap(cd).get('status'), refundStatus=unwrap(cd).get('refundStatus'))
    cs2, _ = call('POST', f"/appointments/{s1_appt['id']}/cancel", {}, tok=a)
    step('S5_cancel_again_rejected', http=cs2)
    req = DB.refund_requests.find_one({'appointmentId': s1_appt['id']})
    over, overd = call('POST', f"/admin/workflow/refunds/{req['refundId']}/approve", {'approvedAmount': 999999}, tok=admin)
    step('S5_over_refund_rejected', http=over, detail=overd.get('detail'))
    ap1, apd = call('POST', f"/admin/workflow/refunds/{req['refundId']}/approve", {'notes': 'Phase 02 UAT'}, tok=admin)
    step('S5_admin_approve', http=ap1, status=unwrap(apd).get('status'), amount=unwrap(apd).get('amount'))
    ap2, _ = call('POST', f"/admin/workflow/refunds/{req['refundId']}/approve", {}, tok=admin)
    s1_pi = DB.payments.find_one({'appointmentId': s1_appt['id']})['stripePaymentIntentId']
    step('S5_duplicate_approve_rejected', http=ap2,
         stripe_refunds=[(r.status, r.amount) for r in stripe.Refund.list(payment_intent=s1_pi).auto_paging_iter()],
         payment_status=DB.payments.find_one({'appointmentId': s1_appt['id']})['status'],
         slot_free_again=slots[0]['startTime'] in [x['startTime'] for x in free_slots(b, 'UAT-P02-ORTHO', date)])

    # S6 reschedule a paid booking (P-05q)
    bad, badd = call('POST', f"/appointments/{s2_appt['id']}/reschedule", {'newDate': date, 'newStartTime': '03:00'}, tok=b)
    step('S6_reschedule_to_non_slot_rejected', http=bad, detail=badd.get('detail'))
    target = next(x for x in free_slots(b, 'UAT-P02-ORTHO', '2026-12-03'))
    ok, okd = call('POST', f"/appointments/{s2_appt['id']}/reschedule", {'newDate': '2026-12-03', 'newStartTime': target['startTime']}, tok=b)
    ap = DB.appointments.find_one({'_id': ObjectId(s2_appt['id'])})
    step('S6_reschedule_ok', http=ok, new=f"{ap['appointmentDate']} {ap['startTime']}", status=ap['status'], paid=ap['paymentStatus'],
         version=ap.get('appointmentVersion'), payments=DB.payments.count_documents({'appointmentId': s2_appt['id']}),
         notifications=DB.notifications.count_documents({'relatedAppointmentId': s2_appt['id'], 'type': 'APPOINTMENT_RESCHEDULED'}))

    for st in EVIDENCE['steps']:
        for k, v in list(st.items()):
            if isinstance(v, str) and (v.startswith('pi_') or v.startswith('re_')):
                st[k] = mask(v)
    pathlib.Path(out).write_text(json.dumps(EVIDENCE, indent=1, default=str), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
