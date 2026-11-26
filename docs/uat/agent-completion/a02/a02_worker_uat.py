"""A02 live worker check (A02-S02, A02-S03): restart and concurrent workers on mediconnect_uat.

Run from backend/ in three phases (the backend restart between phases is done by the operator):
  venv\\Scripts\\python.exe -I ..\\docs\\uat\\agent-completion\\a02\\a02_worker_uat.py prepare STATE.json
  venv\\Scripts\\python.exe -I ..\\docs\\uat\\agent-completion\\a02\\a02_worker_uat.py race STATE.json
  venv\\Scripts\\python.exe -I ..\\docs\\uat\\agent-completion\\a02\\a02_worker_uat.py verify STATE.json OUT.json

prepare  approves two synthetic medication schedules for uat.p03.patienta (due in ~4 and ~6 minutes).
race     starts two extra scheduler processes against mediconnect_uat (local, no port) that loop run_scheduler with
         the real clock for 7 minutes, competing with the 8001 backend's own worker; the operator restarts the
         backend while they run.
verify   checks each occurrence produced exactly one in-app notification and one processed event.
Only 127.0.0.1:8001 and local MongoDB are used; synthetic data only.
"""
import json
import os
import subprocess
import sys
import textwrap
import time
import uuid
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'phase-03'))
from p03api import BASE, DOMAIN, call, colombo_now, login, unwrap  # noqa: E402
from pymongo import MongoClient  # noqa: E402

assert BASE == 'http://127.0.0.1:8001/api'
DB = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000)['mediconnect_uat']


def uid(key):
    return str(DB.users.find_one({'email': f'{key}@{DOMAIN}'})['_id'])


def prepare(state_path):
    run = uuid.uuid4().hex[:6]
    alpha, pa_id = login('uat.p03.doctor.alpha'), uid('uat.p03.patienta')
    now = colombo_now()
    out = {'run': run, 'schedules': [], 'preparedAt': now.isoformat(timespec='seconds')}
    for i, minutes in enumerate((4, 6)):
        item = {'medicationName': f'Synthoworker{i} A02 {run}', 'strength': '5 mg', 'dose': '1 tablet', 'route': 'Oral',
                'frequency': 'Once daily', 'duration': '2 days', 'quantity': '2'}
        rx = unwrap(call('POST', '/clinical/prescriptions/sign', {'patientUserId': pa_id, 'medicationItems': [item]}, tok=alpha)[1])
        doc = DB.prescriptions.find_one({'prescriptionId': rx['prescriptionId']})
        at = (now + timedelta(minutes=minutes)).strftime('%H:%M')
        s, d = call('PUT', f"/care-automation/prescriptions/{doc['_id']}/schedule",
                    {'medicationIndex': 0, 'times': [at], 'startDate': now.date().isoformat(),
                     'endDate': (now.date() + timedelta(days=1)).isoformat(), 'confirm': True}, tok=alpha)
        out['schedules'].append({'scheduleId': unwrap(d)['scheduleId'], 'time': at, 'approve': s})
    json.dump(out, open(state_path, 'w'), indent=1)
    print(json.dumps(out))


def race(state_path):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'backend'))
    code = textwrap.dedent("""
        import os, time
        from datetime import datetime, timezone
        from pymongo import MongoClient
        from app.services import care_scheduler as s
        db = MongoClient('mongodb://127.0.0.1:27017')['mediconnect_uat']
        sent, end = 0, time.time() + 420
        while time.time() < end:
            sent += s.run_scheduler(db, datetime.now(timezone.utc))
            time.sleep(7)
        print('SENT', sent)
    """)
    env = {**os.environ, 'MONGODB_URI': 'mongodb://127.0.0.1:27017/mediconnect_uat', 'DATABASE_NAME': 'mediconnect_uat',
           'ENVIRONMENT': 'staging', 'GEMINI_API_KEY': ' ', 'OPENAI_API_KEY': ' ', 'SMTP_HOST': ' ', 'SMTP_PASSWORD': ' ',
           'SMTP_USERNAME': ' ', 'FIREBASE_CREDENTIALS_PATH': ' ', 'FIREBASE_SERVICE_ACCOUNT_JSON': ' ',
           'TWILIO_ACCOUNT_SID': ' ', 'TWILIO_AUTH_TOKEN': ' ', 'TWILIO_MESSAGING_SERVICE_SID': ' '}
    procs = [subprocess.Popen([sys.executable, '-c', code], cwd=root, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) for _ in range(2)]
    results = []
    for p in procs:
        out, err = p.communicate(timeout=600)
        results.append({'returncode': p.returncode, 'stdout': out.strip()[-80:], 'stderrTail': err.strip()[-300:]})
    state = json.load(open(state_path))
    state['extraWorkers'] = results
    json.dump(state, open(state_path, 'w'), indent=1)
    print(json.dumps(results))


def verify(state_path, out_path):
    state = json.load(open(state_path))
    rows = []
    for sched in state['schedules']:
        events = list(DB.care_reminder_events.find({'sourceId': sched['scheduleId']}))
        notes = DB.notifications.count_documents({'relatedCareEventId': {'$in': [e['_id'] for e in events]}})
        rows.append({'time': sched['time'], 'events': len(events), 'states': [e['state'] for e in events],
                     'inAppAttempts': [len([a for a in e.get('deliveryAttempts', []) if a['channel'] == 'inApp']) for e in events],
                     'notifications': notes, 'push': [((e.get('channels') or {}).get('push') or {}).get('status') for e in events]})
    ok = all(r['events'] == 1 and r['states'] == ['processed'] and r['inAppAttempts'] == [1] and r['notifications'] == 1
             for r in rows)
    extra_sent = sum(int(w['stdout'].split('SENT')[-1]) for w in state.get('extraWorkers', []) if 'SENT' in w['stdout'])
    out = {**state, 'rows': rows, 'deliveredByExtraWorkers': extra_sent, 'status': 'PASS' if ok else 'FAIL'}
    json.dump(out, open(out_path, 'w'), indent=1, default=str)
    print(json.dumps(out, default=str)[:1500])


if __name__ == '__main__':
    {'prepare': lambda: prepare(sys.argv[2]), 'race': lambda: race(sys.argv[2]),
     'verify': lambda: verify(sys.argv[2], sys.argv[3])}[sys.argv[1]]()
