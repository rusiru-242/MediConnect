"""Phase 02 P-05n: real concurrent booking attempts across TWO backend processes sharing mediconnect_uat.

Processes: 127.0.0.1:8001 and 127.0.0.1:8002 (both started with backend/scripts/start_uat_backend.ps1, the second
with -Port 8002). Only those two local ports are allowed. Synthetic uat.p02.* fixtures only.
Run from backend/:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\phase-02\\concurrency_uat.py OUT.json
"""
import json
import os
import pathlib
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p02api  # noqa: E402
from p02api import login, unwrap  # noqa: E402
from bson import ObjectId  # noqa: E402
from pymongo import MongoClient  # noqa: E402

PORTS = ('http://127.0.0.1:8001/api', 'http://127.0.0.1:8002/api')
DB = MongoClient('mongodb://127.0.0.1:27017')['mediconnect_uat']
_lock = threading.Lock()


def call(base, method, path, body=None, tok=None):
    assert base in PORTS
    with _lock:
        p02api.BASE = base
        # p02api.call reads BASE at call time; the lock only covers the swap, requests still run concurrently below
    import urllib.request, urllib.error
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, method=method, data=data, headers={
        'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + tok} if tok else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}


def main(out):
    toks = {k: login(k) for k in ('uat.p02.patienta', 'uat.p02.patientb', 'uat.p02.patientc')}
    a, b, c = toks.values()
    evidence = {'processes': list(PORTS), 'database': 'mediconnect_uat', 'rounds': []}
    date = '2026-12-04'
    day = unwrap(call(PORTS[0], 'GET', f'/doctors/UAT-P02-SPINE/availability?date={date}', tok=a)[1])
    slots = day['slots']

    # C1: 5 rounds x 6 simultaneous REST reservation requests (3 patients x 2 processes) for one slot
    for slot in slots[:5]:
        jobs = [(base, tok) for tok in (a, b, c) for base in PORTS]
        barrier = threading.Barrier(len(jobs))

        def attempt(job):
            base, tok = job
            barrier.wait()
            return call(base, 'POST', '/appointments', {'doctorId': 'UAT-P02-SPINE', 'availabilityId': slot['availabilityId'],
                                                        'date': date, 'startTime': slot['startTime']}, tok=tok)
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            results = list(pool.map(attempt, jobs))
        codes = [r[0] for r in results]
        winner = next(unwrap(r[1])['appointment'] for r in results if r[0] == 201)
        active = DB.appointments.count_documents({'doctorUserId': winner['doctorUserId'], 'appointmentDate': date,
                                                  'startTime': slot['startTime'],
                                                  'status': {'$in': ['HOLD', 'PENDING', 'CONFIRMED', 'COMPLETED']}})
        losers = [t for (base, t), r in zip(jobs, results) if r[0] != 201]
        winner_tok = next(t for (base, t), r in zip(jobs, results) if r[0] == 201)
        peek = [call(PORTS[1], 'GET', f"/appointments/{winner['id']}", tok=t)[0] for t in set(losers) if t != winner_tok]
        loser_detail = next((r[1].get('detail') for r in results if r[0] == 409), None)
        rel = call(PORTS[0], 'POST', f"/appointments/{winner['id']}/release-hold", {}, tok=winner_tok)[0]
        evidence['rounds'].append({'slot': slot['startTime'], 'http_codes': sorted(codes), 'created': codes.count(201),
                                   'active_records_for_slot': active, 'loser_reads_winner_appointment': peek,
                                   'conflict_detail': loser_detail, 'cleanup_release_http': rel})
        print(evidence['rounds'][-1])

    # C2: AI proposal acceptance race (A on 8001, B on 8002) for the same slot
    slot = slots[5]
    sessions = []
    for tok, base in ((a, PORTS[0]), (b, PORTS[1])):
        cid = unwrap(call(base, 'POST', '/ai/conversations', {}, tok=tok)[1])['id']
        call(base, 'POST', f'/ai/booking/sessions/{cid}/select-doctor', {'doctorId': 'UAT-P02-SPINE', 'date': date}, tok=tok)
        st, s = call(base, 'POST', f'/ai/booking/sessions/{cid}/select-slot',
                     {'availabilityId': slot['availabilityId'], 'date': date, 'startTime': slot['startTime'],
                      'prepareProposal': True}, tok=tok)
        sessions.append((tok, base, cid, unwrap(s)['bookingSummary']['proposalId']))
    barrier = threading.Barrier(2)

    def accept(item):
        tok, base, cid, proposal = item
        barrier.wait()
        return call(base, 'POST', f'/ai/booking/sessions/{cid}/confirm', {'proposalId': proposal}, tok=tok)
    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted = list(pool.map(accept, sessions))
    loser = next((i for i, r in enumerate(accepted) if r[0] != 200), None)
    loser_session = unwrap(call(sessions[loser][1], 'GET', f'/ai/booking/sessions/{sessions[loser][2]}', tok=sessions[loser][0])[1]) if loser is not None else {}
    last = (loser_session.get('messages') or [{}])[-1]
    win = next(i for i, r in enumerate(accepted) if r[0] == 200)
    win_appt = unwrap(accepted[win][1]).get('appointmentId')
    evidence['ai_accept_race'] = {
        'http_codes': [r[0] for r in accepted], 'winner_state': unwrap(accepted[win][1]).get('state'),
        'loser_message': last.get('content'), 'loser_alternatives': [x['startTime'] for x in (last.get('metadata') or {}).get('alternatives', [])],
        'loser_message_mentions_other_patient': 'P02 Patient' in (last.get('content') or ''),
        'active_records_for_slot': DB.appointments.count_documents({'appointmentDate': date, 'startTime': slot['startTime'],
                                                                    'doctorProfileId': {'$exists': True},
                                                                    'status': {'$in': ['HOLD', 'PENDING', 'CONFIRMED']},
                                                                    'bookingDoctorName': 'Dr. P02 Spine'}),
    }
    print(evidence['ai_accept_race'])

    # C3: double-tapped PaymentIntent creation for the winner's hold, one request to each process (real Stripe test mode)
    tok = sessions[win][0]
    barrier = threading.Barrier(2)

    def create(base):
        barrier.wait()
        return call(base, 'POST', '/payments/create-intent', {'appointmentId': win_appt}, tok=tok)
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(create, PORTS))
    payments = list(DB.payments.find({'appointmentId': win_appt}))
    evidence['double_tap_intent'] = {'http_codes': [r[0] for r in created],
                                     'payment_records': len(payments),
                                     'distinct_payment_intents': len({p['stripePaymentIntentId'] for p in payments}),
                                     'same_payment_id_returned': len({unwrap(r[1]).get('paymentId') for r in created if r[0] == 201}) == 1}
    print(evidence['double_tap_intent'])
    evidence['cleanup_winner_session_cancel_http'] = call(PORTS[0], 'POST', f"/ai/booking/sessions/{sessions[win][2]}/cancel", tok=tok)[0]
    evidence['cleanup_intents_cancelled_in_stripe'] = [p['status'] for p in DB.payments.find({'appointmentId': win_appt})]
    pathlib.Path(out).write_text(json.dumps(evidence, indent=1, default=str), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
