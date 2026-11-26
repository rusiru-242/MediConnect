"""A02 live UAT: reminders, notifications and patient communication on the real UAT backend and worker.

Run from backend/:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\agent-completion\\a02\\a02_live_uat.py OUT.json

* Targets only 127.0.0.1:8001 (mediconnect_uat, local MongoDB) through the Phase 03 helper, which refuses other hosts.
* The backend's own background worker (60 s interval) executes every reminder; this script only waits and reads.
* Synthetic Phase 03 accounts (uat.p03.*) and synthetic medicines/instructions only. Stripe TEST mode with Stripe's
  documented test PaymentMethod, as in Phases 02-05. No e-mail, SMS or push provider is configured in UAT, so every
  external channel must report "disabled" or "skipped", never "accepted" or "delivered".
* Read-only MongoDB access verifies persistence. No token, password or full payment id is written.
"""
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'phase-03'))
from p03api import BASE, DOMAIN, _PW, call, colombo_now, env_value, free_slots, book, login, unwrap  # noqa: E402

import stripe  # noqa: E402
from bson import ObjectId  # noqa: E402
from pymongo import MongoClient  # noqa: E402

assert BASE == 'http://127.0.0.1:8001/api'
KEY = env_value('STRIPE_SECRET_KEY')
assert KEY.startswith('sk_test_'), 'Refusing: not a Stripe test key'
stripe.api_key = KEY
DB = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000)['mediconnect_uat']
OUT = {'backend': '127.0.0.1:8001', 'database': 'mediconnect_uat', 'stripe': 'test_mode', 'workerIntervalSeconds': 60,
       'steps': []}
EXTERNAL_OK = {'disabled', 'skipped', 'no_device', None}


def step(test_id, scenario, expected, actual, ok, status=None):
    row = {'id': test_id, 'scenario': scenario, 'expected': expected, 'actual': actual,
           'status': status or ('PASS' if ok else 'FAIL'), 'at': colombo_now().isoformat(timespec='seconds')}
    OUT['steps'].append(row)
    print(row['status'], test_id, scenario, '|', json.dumps(actual, default=str)[:260], flush=True)
    return ok


def uid(key):
    return str(DB.users.find_one({'email': f'{key}@{DOMAIN}'})['_id'])


def hhmm(dt):
    return dt.strftime('%H:%M')


def wait_for(fn, seconds=240, every=10):
    end = time.time() + seconds
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(every)
    return fn()


def pay(tok, appt_id):
    pi = unwrap(call('POST', '/payments/create-intent', {'appointmentId': appt_id, 'amount': 1}, tok=tok)[1])
    intent = DB.payments.find_one({'_id': ObjectId(pi['paymentId'])})['stripePaymentIntentId']
    stripe.PaymentIntent.confirm(intent, payment_method='pm_card_visa', return_url='https://example.invalid/r')
    call('GET', f"/payments/{pi['paymentId']}/status", tok=tok)
    return wait_for(lambda: DB.appointments.find_one({'_id': ObjectId(appt_id), 'status': 'CONFIRMED'}), 90, 3)


def event(source_id, kind=None, scheduled=None):
    query = {'sourceId': str(source_id)}
    if kind:
        query['kind'] = kind
    if scheduled:
        query['scheduledAt'] = scheduled
    return DB.care_reminder_events.find_one(query, sort=[('scheduledAt', 1)])


def channels(row):
    return {k: (v or {}).get('status') for k, v in ((row or {}).get('channels') or {}).items()}


def delivered(row):
    return bool(row) and channels(row).get('inApp') == 'stored' and row.get('state') == 'processed'


def main(out_path):
    run = uuid.uuid4().hex[:6]
    OUT['run'] = run
    alpha, beta = login('uat.p03.doctor.alpha'), login('uat.p03.doctor.beta')
    pa, pb = login('uat.p03.patienta'), login('uat.p03.patientb')
    alpha_id, pa_id, pb_id = uid('uat.p03.doctor.alpha'), uid('uat.p03.patienta'), uid('uat.p03.patientb')
    pending_status, pending_body = call('POST', '/auth/login', {'email': f'uat.doctor.pending1@{DOMAIN}', 'password': _PW})
    pending = (pending_body or {}).get('accessToken') or (pending_body or {}).get('access_token')
    now = colombo_now()
    assert now.hour < 21, 'Run before 21:00 Asia/Colombo so every scheduled time falls on today'
    today = now.date()
    OUT['startedAt'] = now.isoformat(timespec='seconds')

    # ------------------------------------------------------------- notification baseline (agent 13)
    unread0 = unwrap(call('GET', '/notifications/unread-count', tok=pa)[1]).get('unreadCount')

    # ------------------------------------------------------------- A02-M01/M02 prescription and approved schedule
    item = {'medicationName': f'Synthomox A02 {run}', 'strength': '250 mg', 'dose': '1 capsule', 'route': 'Oral',
            'frequency': 'Twice daily', 'duration': '5 days', 'quantity': '10'}
    st, rx = call('POST', '/clinical/prescriptions/sign', {'patientUserId': pa_id, 'medicationItems': [item]}, tok=alpha)
    rx = unwrap(rx)
    rxdoc = DB.prescriptions.find_one({'prescriptionId': rx.get('prescriptionId')})
    t1, t2 = now + timedelta(minutes=3), now + timedelta(minutes=4)
    body = {'medicationIndex': 0, 'times': [hhmm(t1), hhmm(t2)], 'startDate': today.isoformat(),
            'endDate': (today + timedelta(days=4)).isoformat(), 'confirm': True}
    path = f"/care-automation/prescriptions/{rxdoc['_id']}/schedule"
    checks = {
        'unrelatedDoctor': call('PUT', path, body, tok=beta)[0],
        'patient': call('PUT', path, body, tok=pa)[0],
        'pendingDoctor': call('PUT', path, body, tok=pending)[0] if pending else f'login {pending_status}',
        'wrongTimeCount': call('PUT', path, {**body, 'times': [hhmm(t1)]}, tok=alpha)[0],
        'longerThanPrescribed': call('PUT', path, {**body, 'endDate': (today + timedelta(days=10)).isoformat()}, tok=alpha)[0],
    }
    approve = call('PUT', path, body, tok=alpha)
    sched_id = unwrap(approve[1]).get('scheduleId')
    rem = DB.medication_reminders.find_one({'_id': ObjectId(sched_id)}) if sched_id else {}
    step('A02-M01', 'Only the prescribing approved doctor can approve a schedule that matches the prescription',
         'sign 201; approve 200; unrelated 404; patient 403; pending 403; 1 time 422; 10 days 422',
         {'sign': st, 'approve': approve[0], **checks},
         st == 201 and approve[0] == 200 and checks['unrelatedDoctor'] == 404 and checks['patient'] == 403
         and checks['pendingDoctor'] in (403, 'login 403') and checks['wrongTimeCount'] == 422
         and checks['longerThanPrescribed'] == 422)
    step('A02-M02', 'Stored schedule carries the prescribed medicine, dose and frequency; times are the approved ones',
         'name/strength/dose/frequency equal the prescription; times as approved; approvedBy = prescriber',
         {k: rem.get(k) for k in ('medicationName', 'strength', 'dose', 'frequency', 'duration', 'scheduledTimes')}
         | {'approvedBySelf': rem.get('approvedBy') == alpha_id},
         all(rem.get(k) == item[k] for k in ('medicationName', 'strength', 'dose', 'frequency', 'duration'))
         and rem.get('scheduledTimes') == sorted([hhmm(t1), hhmm(t2)]) and rem.get('approvedBy') == alpha_id)

    # PRN prescription: neither doctor schedule nor patient-created reminder (A02-BUG-011 live)
    prn = {**item, 'medicationName': f'Synthopar A02 {run}', 'frequency': 'PRN (as needed, synthetic)',
           'strength': '500 mg', 'dose': '1 tablet'}
    rx2 = unwrap(call('POST', '/clinical/prescriptions/sign', {'patientUserId': pa_id, 'medicationItems': [prn]}, tok=alpha)[1])
    rx2doc = DB.prescriptions.find_one({'prescriptionId': rx2.get('prescriptionId')})
    prn_doctor = call('PUT', f"/care-automation/prescriptions/{rx2doc['_id']}/schedule", body, tok=alpha)[0]
    prn_patient = call('POST', '/medication-reminders', {'prescriptionId': str(rx2doc['_id']), 'prescriptionMedicationIndex': 0,
                                                         'scheduledTimes': ['08:00']}, tok=pa)
    rx4 = unwrap(call('POST', '/clinical/prescriptions/sign', {'patientUserId': pa_id, 'medicationItems': [
        {**item, 'medicationName': f'Synthoval A02 {run}'}]}, tok=alpha)[1])
    rx4doc = DB.prescriptions.find_one({'prescriptionId': rx4.get('prescriptionId')})
    long_patient = call('POST', '/medication-reminders', {
        'prescriptionId': str(rx4doc['_id']), 'prescriptionMedicationIndex': 0, 'scheduledTimes': ['09:00', '21:00'],
        'endDate': (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()}, tok=pa)[0]
    step('A02-M01b', 'An as-needed (PRN) medicine gets no fixed reminder times; a patient cannot outlast the course',
         'doctor 422; patient PRN 422 (was 201 before A02); patient 60-day end date 422',
         {'doctorPRN': prn_doctor, 'patientPRN': prn_patient[0], 'patientPRNdetail': str(prn_patient[1].get('detail'))[:120],
          'patient60days': long_patient},
         prn_doctor == 422 and prn_patient[0] == 422 and long_patient == 422)

    # Once-daily medicine never acted on -> "no action recorded" (missed) list
    once = {**item, 'medicationName': f'Synthocet A02 {run}', 'frequency': 'Once daily', 'strength': '10 mg',
            'dose': '1 tablet'}
    rx3 = unwrap(call('POST', '/clinical/prescriptions/sign', {'patientUserId': pa_id, 'medicationItems': [once]}, tok=alpha)[1])
    rx3doc = DB.prescriptions.find_one({'prescriptionId': rx3.get('prescriptionId')})
    path3 = f"/care-automation/prescriptions/{rx3doc['_id']}/schedule"
    s3 = unwrap(call('PUT', path3, {**body, 'times': [hhmm(t1)]}, tok=alpha)[1]).get('scheduleId')

    # ------------------------------------------------------------- follow-up and medical test (agents 08, 09)
    visit = next(a for a in DB.appointments.find({'doctorUserId': alpha_id, 'patientUserId': pa_id, 'status': 'COMPLETED'})
                 if not DB.care_plans.find_one({'appointmentId': str(a['_id']), 'status': {'$in': ['ACTIVE', 'OVERDUE']}}))
    test_due = (now + timedelta(minutes=5)).replace(second=0, microsecond=0)
    later_test = (now + timedelta(minutes=40)).replace(second=0, microsecond=0)
    plan_body = {'appointmentId': str(visit['_id']), 'followUpDate': (today + timedelta(days=10)).isoformat(),
                 'reason': f'A02 synthetic follow-up {run}', 'instructions': 'Synthetic instruction: bring the diary.',
                 'tasks': [{'title': f'A02 synthetic fasting blood test {run}', 'kind': 'test', 'dueAt': test_due.isoformat(),
                            'description': 'Synthetic instruction: no food after 22:00 the evening before.',
                            'location': 'UAT synthetic lab'},
                           {'title': f'A02 synthetic urine test {run}', 'kind': 'test', 'dueAt': later_test.isoformat(),
                            'location': 'UAT synthetic lab'}]}
    st, cp = call('POST', '/care-plans', plan_body, tok=alpha)
    cp = unwrap(cp)
    plan_id = cp.get('id')
    created_notice = DB.notifications.find_one({'recipientUserId': pa_id, 'idempotencyKey': f'care_plan_created_{plan_id}'})
    step('A02-F01', 'Doctor-authored follow-up plan with a test task; the patient is notified without clinical text',
         '201; patient notification; body has no instruction text; patient B cannot read the plan',
         {'create': st, 'notified': bool(created_notice), 'body': (created_notice or {}).get('body'),
          'patientBRead': call('GET', f'/care-plans/{plan_id}', tok=pb)[0]},
         st == 201 and bool(created_notice) and 'diary' not in (created_notice or {}).get('body', '')
         and call('GET', f'/care-plans/{plan_id}', tok=pb)[0] in (403, 404))
    agenda = unwrap(call('GET', '/care-automation/agenda', tok=pa)[1]).get('items', [])
    test_item = next((i for i in agenda if i.get('kind') == 'test' and run in i.get('title', '') and 'fasting' in i['title']), {})
    step('A02-T01/T02', 'Assigned test appears for the right patient with the clinician-entered instructions, verbatim',
         'agenda item kind test; instructions and location exactly as entered; not in patient B agenda',
         {'title': test_item.get('title'), 'instructions': test_item.get('instructions'), 'location': test_item.get('location'),
          'inPatientB': any(run in i.get('title', '') for i in unwrap(call('GET', '/care-automation/agenda', tok=pb)[1]).get('items', []))},
         test_item.get('instructions') == plan_body['tasks'][0]['description']
         and test_item.get('location') == 'UAT synthetic lab'
         and not any(run in i.get('title', '') for i in unwrap(call('GET', '/care-automation/agenda', tok=pb)[1]).get('items', [])))

    # ------------------------------------------------------------- appointments (agent 07)
    # The doctor's existing availability today (30-minute slots); the first slot is >= 2 h ahead so its 2-hour
    # reminder falls due during this run.
    earliest = hhmm(now + timedelta(hours=2, minutes=3))
    doctor_public = DB.doctor_profiles.find_one({'userId': alpha_id})['doctorId']
    slots = [s for s in free_slots(pa, doctor_public, today.isoformat()) if s.get('startTime') >= earliest]
    OUT['appointmentSlots'] = [s['startTime'] for s in slots]
    s1, s2, s3 = slots[:3]
    avail = (200, 'existing availability')
    b1 = book(pa, doctor_public, today.isoformat(), s1)[1]
    pay(pa, b1['id'])
    b2 = book(pa, doctor_public, today.isoformat(), s2)[1]
    pay(pa, b2['id'])
    resched = call('POST', f"/appointments/{b2['id']}/reschedule", {'newDate': today.isoformat(), 'newStartTime': s3['startTime']}, tok=pa)
    after_resched = DB.appointments.find_one({'_id': ObjectId(b2['id'])})
    cancel = call('POST', f"/appointments/{b2['id']}/cancel", {'reason': 'A02 synthetic cancellation'}, tok=pa)
    b3 = book(pb, doctor_public, today.isoformat(), s2)[1]          # unpaid reservation on the vacated slot
    b_agenda = unwrap(call('GET', '/care-automation/agenda', tok=pb)[1]).get('items', [])
    step('A02-A05', 'An unpaid reservation produces no reminder', 'patient B reservation not CONFIRMED; not in B agenda',
         {'availability': avail[0], 'bStatus': (DB.appointments.find_one({'_id': ObjectId(b3['id'])}) or {}).get('status'),
          'inBAgenda': any(i.get('appointmentId') == b3['id'] for i in b_agenda)},
         (DB.appointments.find_one({'_id': ObjectId(b3['id'])}) or {}).get('status') != 'CONFIRMED'
         and not any(i.get('appointmentId') == b3['id'] for i in b_agenda))

    # ------------------------------------------------------------- device tokens (agent 13, N08/N09/N10)
    token = f'a02-synthetic-device-token-{run}'
    reg_a = call('POST', '/notifications/devices', {'fcmToken': token, 'deviceType': 'android'}, tok=pa)[0]
    refreshed = call('POST', '/notifications/devices', {'fcmToken': token + '-refreshed', 'deviceType': 'android'}, tok=pa)[0]
    reg_b = call('POST', '/notifications/devices', {'fcmToken': token, 'deviceType': 'android'}, tok=pb)[0]
    owner = [d['userId'] for d in DB.device_tokens.find({'fcmToken': token})]
    bad_type = call('POST', '/notifications/devices', {'fcmToken': token + 'x', 'deviceType': 'fridge'}, tok=pa)[0]
    removed = call('DELETE', '/notifications/devices', {'fcmToken': token + '-refreshed'}, tok=pa)
    removed_other = call('DELETE', '/notifications/devices', {'fcmToken': token}, tok=pa)[1].get('modifiedCount')
    call('DELETE', '/notifications/devices', {'fcmToken': token}, tok=pb)
    step('A02-N08/N09', 'Token refresh, account switch on one device, logout removal; nobody removes another user\'s token',
         'register 200 x3; token owned only by B after B signs in; bad type 422; logout removes 1; A cannot remove B\'s',
         {'registerA': reg_a, 'refresh': refreshed, 'registerB': reg_b, 'ownerIsB': owner == [pb_id], 'badType': bad_type,
          'logoutRemoved': (removed[1] or {}).get('modifiedCount'), 'aRemovesB': removed_other},
         reg_a == refreshed == reg_b == 200 and owner == [pb_id] and bad_type == 422
         and (removed[1] or {}).get('modifiedCount') == 1 and removed_other == 0)

    # ------------------------------------------------------------- doctor-approved communication batch (agent 19)
    preview = unwrap(call('GET', f'/doctor/workflow/reminders/{today.isoformat()}', tok=alpha)[1])
    unauthorized = {'patient': call('GET', f'/doctor/workflow/reminders/{today.isoformat()}', tok=pa)[0],
                    'pending': call('GET', f'/doctor/workflow/reminders/{today.isoformat()}', tok=pending)[0] if pending else f'login {pending_status}',
                    'noConfirm': call('POST', f'/doctor/workflow/reminders/{today.isoformat()}', {'token': preview.get('token'), 'confirm': False}, tok=alpha)[0],
                    'forgedToken': call('POST', f'/doctor/workflow/reminders/{today.isoformat()}', {'token': '0' * 64, 'confirm': True}, tok=alpha)[0]}
    approve1 = call('POST', f'/doctor/workflow/reminders/{today.isoformat()}', {'token': preview.get('token'), 'confirm': True}, tok=alpha)
    approve2 = call('POST', f'/doctor/workflow/reminders/{today.isoformat()}', {'token': preview.get('token'), 'confirm': True}, tok=alpha)
    ai_draft = call('POST', '/doctor/workflow/assistant', {'message': 'Draft reminders for my appointments today'}, tok=alpha)
    step('A02-C01/C02/C04', 'Doctor previews a fixed reminder draft and approves it explicitly; others cannot',
         'preview lists consenting confirmed patients; patient 403; pending 403; confirm=false 422; forged token 409; '
         'assistant returns a draft that still needs approval',
         {'count': preview.get('count'), 'body': preview.get('body'), **unauthorized, 'approve': approve1[0],
          'assistant': str(unwrap(ai_draft[1]).get('message'))[:120]},
         approve1[0] == 200 and unauthorized['patient'] == 403 and unauthorized['noConfirm'] == 422
         and unauthorized['forgedToken'] == 409 and unauthorized['pending'] in (403, 'login 403')
         and 'Review it before approving' in str(unwrap(ai_draft[1]).get('message')))

    # ------------------------------------------------------------- wait for the worker: medication occurrence 1
    r1 = wait_for(lambda: (lambda e: e if delivered(e) else None)(
        DB.care_reminder_events.find_one({'sourceId': sched_id, 'kind': 'medication'}, sort=[('scheduledAt', 1)])), 360)
    n1 = DB.notifications.find_one({'relatedCareEventId': (r1 or {}).get('_id')})
    lag = ((r1 or {}).get('channels', {}).get('inApp', {}).get('attemptedAt') - r1['scheduledAt']).total_seconds() if r1 else None
    step('A02-M03/S01', 'The backend worker executes the medication reminder at the approved Asia/Colombo time',
         'event processed; scheduledAt = approved time; in-app stored within 2 worker cycles; push/email/sms not "accepted"',
         {'scheduledAtColombo': r1 and r1['scheduledAt'].replace(tzinfo=timezone.utc).astimezone(t1.tzinfo).strftime('%H:%M'),
          'approvedTime': hhmm(t1), 'channels': channels(r1), 'secondsLate': lag, 'notificationBody': (n1 or {}).get('body')},
         delivered(r1) and r1['scheduledAt'].replace(tzinfo=timezone.utc).astimezone(t1.tzinfo).strftime('%H:%M') == hhmm(t1)
         and lag is not None and 0 <= lag <= 150 and bool(n1) and item['medicationName'] not in n1['body']
         and set(channels(r1).values()) - {'stored'} <= EXTERNAL_OK)
    step('A02-I08', 'With no provider configured, external channels are reported disabled/skipped, never delivered',
         'push "disabled" (Firebase not configured); email/sms "skipped" (no consent) or "disabled"',
         channels(r1), channels(r1).get('push') == 'disabled' and channels(r1).get('email') in EXTERNAL_OK
         and channels(r1).get('sms') in EXTERNAL_OK)
    ev = f"/care-automation/events/{r1['_id']}/actions"
    req_id = f'a02-{run}-taken-1'
    taken = call('POST', ev, {'action': 'taken', 'requestId': req_id}, tok=pa)[0]
    again = call('POST', ev, {'action': 'taken', 'requestId': req_id}, tok=pa)[0]
    other = call('POST', ev, {'action': 'skipped', 'requestId': f'a02-{run}-b-1x'}, tok=pb)[0]
    step('A02-M04', 'Taken is recorded once (idempotent request id); another patient cannot act on it',
         'taken 200; repeat 200 with one audit entry; patient B 404',
         {'taken': taken, 'repeat': again, 'patientB': other,
          'audit': len(DB.care_reminder_events.find_one({'_id': r1['_id']})['audit'])},
         taken == again == 200 and other == 404 and len(DB.care_reminder_events.find_one({'_id': r1['_id']})['audit']) == 1)

    # occurrence 2: snooze -> redelivered -> skip
    r2 = wait_for(lambda: (lambda e: e if delivered(e) else None)(
        DB.care_reminder_events.find_one({'sourceId': sched_id, 'kind': 'medication', '_id': {'$ne': r1['_id']}},
                                         sort=[('scheduledAt', 1)])), 240)
    ev2 = f"/care-automation/events/{r2['_id']}/actions"
    snooze = call('POST', ev2, {'action': 'snooze', 'requestId': f'a02-{run}-snooze-2', 'snoozeMinutes': 5}, tok=pa)[0]
    snoozed_at = datetime.now(timezone.utc)
    redelivered = wait_for(lambda: DB.notifications.count_documents({'relatedCareEventId': r2['_id']}) >= 2, 480)
    step('A02-M05', 'Snooze re-delivers the same occurrence after the chosen interval, once',
         'snooze 200; a second in-app reminder after ~5 min; exactly 2 notifications for this occurrence',
         {'snooze': snooze, 'notifications': DB.notifications.count_documents({'relatedCareEventId': r2['_id']}),
          'minutesAfterSnooze': round((datetime.now(timezone.utc) - snoozed_at).total_seconds() / 60, 1)},
         snooze == 200 and redelivered and DB.notifications.count_documents({'relatedCareEventId': r2['_id']}) == 2)
    skip = call('POST', ev2, {'action': 'skipped', 'requestId': f'a02-{run}-skip-2'}, tok=pa)[0]
    activity = unwrap(call('GET', f"/care-automation/prescriptions/{rxdoc['_id']}/activity", tok=alpha)[1])
    beta_activity = call('GET', f"/care-automation/prescriptions/{rxdoc['_id']}/activity", tok=beta)[0]
    step('A02-M06', 'Skip is recorded; the prescribing doctor sees patient-reported history; another doctor cannot',
         'skip 200; activity shows taken and skipped, source patient_reported; unrelated doctor 404',
         {'skip': skip, 'actions': sorted(a.get('action') or '' for a in activity), 'beta': beta_activity},
         skip == 200 and {'taken', 'skipped'} <= {a.get('action') for a in activity} and beta_activity == 404
         and all(a.get('source') == 'patient_reported' for a in activity))

    # missed (no action recorded) via the assistant
    wait_for(lambda: delivered(event(s3, 'medication')), 120)
    s, d = call('POST', '/ai/conversations', {'initialMessage': 'Show my missed medicine reminders.'}, tok=pa)
    missed_reply = [m for m in d.get('messages', []) if m.get('sender') == 'assistant'][-1]['content']
    s, d = call('POST', '/ai/conversations', {'initialMessage': 'Show my unread notifications.'}, tok=pa)
    unread_reply = [m for m in d.get('messages', []) if m.get('sender') == 'assistant'][-1]['content']
    s, d = call('POST', '/ai/conversations', {'initialMessage': 'Mark all my notifications as read.'}, tok=pa)
    action_reply = [m for m in d.get('messages', []) if m.get('sender') == 'assistant'][-1]['content']
    unread_now = unwrap(call('GET', '/notifications/unread-count', tok=pa)[1]).get('unreadCount')
    step('A02-M06b', 'Assistant lists the dose with no recorded action from the database; does not change state',
         'reply names the un-acted once-daily medicine and not the taken one; unread list from DB; mark-all refused',
         {'missed': missed_reply[:300], 'unread': unread_reply[:200], 'markAll': action_reply[:120], 'unreadCount': unread_now},
         # this run's taken and skipped doses must not be listed (other runs' un-acted doses may be)
         once['medicationName'] in missed_reply and item['medicationName'] not in missed_reply
         and f'You have {unread_now} unread' in unread_reply and "can't change your notifications" in action_reply)

    # schedule update and cancellation
    new_times = [hhmm(now.replace(hour=21, minute=10)), hhmm(now.replace(hour=21, minute=40))]
    upd = call('PUT', path, {**body, 'times': new_times}, tok=alpha)[0]
    rem2 = DB.medication_reminders.find_one({'_id': ObjectId(sched_id)})
    agenda = unwrap(call('GET', '/care-automation/agenda', tok=pa)[1]).get('items', [])
    mine = sorted(datetime.fromisoformat(str(i['scheduledAt']).replace('Z', '+00:00')).astimezone(t1.tzinfo).strftime('%H:%M')
                  for i in agenda if i.get('title') == item['medicationName'])
    step('A02-M07', 'Doctor changes the times: new version; today\'s agenda shows old (history) and new times only',
         'update 200; scheduleVersion +1; agenda = 2 recorded old occurrences + 2 new times',
         {'update': upd, 'version': rem2.get('scheduleVersion'), 'times': rem2.get('scheduledTimes'), 'agendaTimes': mine},
         upd == 200 and rem2.get('scheduledTimes') == new_times and set(new_times) <= set(mine))
    disc = call('DELETE', f'{path3}/0', tok=alpha)[0]
    beta_disc = call('DELETE', f'{path}/0', tok=beta)[0]
    agenda = unwrap(call('GET', '/care-automation/agenda', tok=pa)[1]).get('items', [])
    step('A02-M08', 'Discontinued schedule disappears from the agenda; an unrelated doctor cannot discontinue',
         'discontinue 200; once-daily medicine absent from agenda; unrelated doctor 404',
         {'discontinue': disc, 'unrelated': beta_disc,
          'stillListed': any(i.get('title') == once['medicationName'] for i in agenda)},
         disc == 200 and beta_disc == 404 and not any(i.get('title') == once['medicationName'] for i in agenda))

    # medical test reminder execution, completion, date change, follow-up update/close
    rt = wait_for(lambda: (lambda e: e if delivered(e) else None)(event(plan_id, 'test')), 300)
    step('A02-T03', 'The worker delivers the test reminder at its due time (in-app); private text only',
         'event kind test processed; in-app stored; body has no test name or instruction',
         {'channels': channels(rt), 'body': (DB.notifications.find_one({'relatedCareEventId': (rt or {}).get('_id')}) or {}).get('body')},
         delivered(rt) and 'fasting' not in (DB.notifications.find_one({'relatedCareEventId': rt['_id']}) or {}).get('body', 'fasting'))
    done = call('POST', f"/care-automation/events/{rt['_id']}/actions", {'action': 'completed', 'requestId': f'a02-{run}-done'}, tok=pa)[0]
    tasks = unwrap(call('GET', f'/care-plans/{plan_id}', tok=alpha)[1]).get('tasks', [])
    moved = (now + timedelta(minutes=55)).replace(second=0, microsecond=0)
    def with_offset(value):  # stored UTC datetimes may be returned without an offset
        return value if not value or value.endswith('Z') or '+' in value[10:] else value + '+00:00'
    new_tasks = [{'title': t['title'], 'kind': t.get('kind', 'task'),
                  'dueAt': (moved.isoformat() if 'urine' in t['title'] else with_offset(t.get('dueAt'))),
                  'description': t.get('description'), 'location': t.get('location')} for t in tasks]
    up1 = call('PUT', f'/care-plans/{plan_id}', {'tasks': new_tasks, 'followUpDate': (today + timedelta(days=14)).isoformat()}, tok=alpha)[0]
    up2 = call('PUT', f'/care-plans/{plan_id}', {'followUpDate': (today + timedelta(days=14)).isoformat()}, tok=alpha)[0]
    beta_up = call('PUT', f'/care-plans/{plan_id}', {'followUpDate': (today + timedelta(days=20)).isoformat()}, tok=beta)[0]
    updates = DB.notifications.count_documents({'recipientUserId': pa_id, 'idempotencyKey': {'$regex': f'^care_plan_updated_{plan_id}'}})
    agenda = unwrap(call('GET', '/care-automation/agenda', tok=pa)[1]).get('items', [])
    urine = [datetime.fromisoformat(str(i['scheduledAt']).replace('Z', '+00:00')).astimezone(t1.tzinfo).strftime('%H:%M')
             for i in agenda if 'urine' in i.get('title', '') and run in i['title']]
    step('A02-T04/F03', 'Test completion recorded; date change moves the reminder; patient told once; unrelated doctor refused',
         'completed 200; update 200; unchanged re-save 200 without a 2nd notice; urine test at new time; beta 403',
         {'completed': done, 'update': up1, 'resave': up2, 'updateNotices': updates, 'urineTimes': urine, 'beta': beta_up},
         done == 200 and up1 == 200 and up2 == 200 and updates == 1 and urine == [hhmm(moved)] and beta_up == 403)
    close = call('POST', f'/care-plans/{plan_id}/cancel', {'reason': 'A02 synthetic closure'}, tok=alpha)[0]
    agenda = unwrap(call('GET', '/care-automation/agenda', tok=pa)[1]).get('items', [])
    step('A02-F04', 'Closing the plan removes its remaining reminders and tells the patient once',
         'cancel 200; no task of this plan in the agenda; 1 "Care plan closed" notice',
         {'cancel': close, 'remaining': [i['title'] for i in agenda if run in i.get('title', '') and i.get('kind') != 'medication'],
          'closedNotices': DB.notifications.count_documents({'recipientUserId': pa_id, 'idempotencyKey': f'care_plan_cancelled_{plan_id}'})},
         close == 200 and not any(run in i.get('title', '') and i.get('kind') != 'medication' for i in agenda)
         and DB.notifications.count_documents({'recipientUserId': pa_id, 'idempotencyKey': f'care_plan_cancelled_{plan_id}'}) == 1)

    # appointment 2-hour reminder (agent 07)
    ra = wait_for(lambda: (lambda e: e if delivered(e) else None)(event(b1['id'], 'appointment')), 2400, 20)
    na = DB.notifications.find_one({'relatedCareEventId': (ra or {}).get('_id')})
    s1_local = datetime.combine(today, datetime.strptime(s1['startTime'], '%H:%M').time(), tzinfo=t1.tzinfo)
    step('A02-A01/A02', 'Confirmed paid appointment: 2-hour reminder at the configured time (Asia/Colombo), right patient',
         'event for this appointment; scheduledAt = slot time; due 2 h before; recipient = patient A only',
         {'slot': s1['startTime'], 'scheduledAt': ra and ra['scheduledAt'].replace(tzinfo=timezone.utc).astimezone(t1.tzinfo).strftime('%H:%M'),
          'hoursBefore': ra and round((ra['scheduledAt'] - ra['dueAt']).total_seconds() / 3600, 2),
          'recipient': (na or {}).get('recipientUserId') == pa_id, 'channels': channels(ra), 'body': (na or {}).get('body')},
         delivered(ra) and ra['scheduledAt'].replace(tzinfo=timezone.utc) == s1_local.astimezone(timezone.utc)
         and (ra['scheduledAt'] - ra['dueAt']) == timedelta(hours=2) and (na or {}).get('recipientUserId') == pa_id)
    detail = call('GET', f"/care-automation/events/{ra['_id']}", tok=pa)
    step('A02-A06', 'Tapping the reminder resolves to the appointment (deep-link target)',
         'event detail 200 with appointmentId = booked appointment; patient B 404',
         {'detail': detail[0], 'appointmentId': unwrap(detail[1]).get('appointmentId') == b1['id'],
          'patientB': call('GET', f"/care-automation/events/{ra['_id']}", tok=pb)[0]},
         detail[0] == 200 and unwrap(detail[1]).get('appointmentId') == b1['id']
         and call('GET', f"/care-automation/events/{ra['_id']}", tok=pb)[0] == 404)
    step('A02-A03/A04', 'Rescheduled and then cancelled appointment never produces a reminder for either time',
         'reschedule 200 (new version); cancel 200; no reminder event for this appointment',
         {'reschedule': resched[0], 'newStart': (after_resched or {}).get('startTime'), 'cancel': cancel[0],
          'events': DB.care_reminder_events.count_documents({'sourceId': b2['id']})},
         resched[0] == 200 and cancel[0] == 200 and DB.care_reminder_events.count_documents({'sourceId': b2['id']}) == 0)

    # notifications list / read state / isolation (agent 13)
    lst = unwrap(call('GET', '/notifications?limit=50', tok=pa)[1])
    first = lst['items'][0]
    b_mark = call('PATCH', f"/notifications/{first['id']}/read", tok=pb)[0]
    mark = call('PATCH', f"/notifications/{first['id']}/read", tok=pa)[0]
    count_after_one = unwrap(call('GET', '/notifications/unread-count', tok=pa)[1]).get('unreadCount')
    b_items = unwrap(call('GET', '/notifications?limit=50', tok=pb)[1])['items']
    step('A02-N01/N06/N07/N10', 'In-app list, unread count and mark-as-read are per recipient',
         'unread grew from baseline; mark own 200 and count -1; patient B 403 and sees none of A\'s',
         {'unreadBefore': unread0, 'unreadPeak': lst.get('unreadCount'), 'markByB': b_mark, 'mark': mark,
          'afterMark': count_after_one, 'bSeesA': any(i['id'] == first['id'] for i in b_items)},
         lst.get('unreadCount', 0) > (unread0 or 0) and mark == 200 and count_after_one == lst['unreadCount'] - 1
         and b_mark == 403 and not any(i['id'] == first['id'] for i in b_items))
    mark_all = unwrap(call('PATCH', '/notifications/read-all', tok=pa)[1])
    step('A02-N07b', 'Mark all as read', 'unread count 0', {'modified': mark_all.get('modifiedCount'),
         'unread': unwrap(call('GET', '/notifications/unread-count', tok=pa)[1]).get('unreadCount')},
         unwrap(call('GET', '/notifications/unread-count', tok=pa)[1]).get('unreadCount') == 0)

    # duplicate check across everything this run produced
    dup = list(DB.notifications.aggregate([
        {'$match': {'recipientUserId': pa_id, 'createdAt': {'$gte': datetime.fromisoformat(OUT['startedAt']).astimezone(timezone.utc)}}},
        {'$group': {'_id': {'e': '$relatedCareEventId', 'k': '$idempotencyKey'}, 'n': {'$sum': 1}}}, {'$match': {'n': {'$gt': 1}}}]))
    step('A02-S05', 'No duplicate notification for any occurrence or idempotency key in this run',
         '0 duplicate groups (the snoozed occurrence has 2 distinct keys by design)', {'duplicateGroups': len(dup)}, not dup)
    approve_after = call('GET', f'/doctor/workflow/reminders/{today.isoformat()}', tok=alpha)
    step('A02-C05', 'Approving the same communication batch twice queues it once',
         'second approve 200; batch status counts unchanged', {'approve2': approve2[0],
         'statuses': unwrap(approve_after[1]).get('statuses')},
         approve2[0] == 200 and sum((unwrap(approve_after[1]).get('statuses') or {}).values()) == preview.get('count'))

    OUT['finishedAt'] = colombo_now().isoformat(timespec='seconds')
    OUT['summary'] = {s: sum(1 for r in OUT['steps'] if r['status'] == s) for s in ('PASS', 'FAIL')}
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(OUT, fh, indent=2, default=str, ensure_ascii=False)
    print(OUT['summary'])


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    finally:
        if 'summary' not in OUT:
            with open(sys.argv[1], 'w', encoding='utf-8') as fh:
                json.dump({**OUT, 'aborted': True}, fh, indent=2, default=str, ensure_ascii=False)
