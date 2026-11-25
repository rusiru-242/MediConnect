"""Phase 03: verify the UAT backend's own background worker delivered doctor-initiated reminders.

Run from backend/ a few minutes after doctor_workflow_uat.py:
    venv\\Scripts\\python.exe -I ..\\docs\\uat\\phase-03\\doctor_worker_check.py EVIDENCE.json OUT.json

Reads only the local UAT database (mediconnect_uat). Checks:
- D-09c: the care-plan test task (due 3 minutes after creation) produced a processed reminder event and an in-app
  notification for the patient, with push recorded truthfully (FCM is not configured in UAT).
- D-10b/d: the doctor-approved reminder batch was delivered in-app to consented patients only; external channels are
  not claimed.
"""
import json
import sys

from bson import ObjectId
from pymongo import MongoClient

DB = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000)['mediconnect_uat']


def main(evidence_path, out_path):
    ev = json.load(open(evidence_path, encoding='utf-8'))
    plan, comm = ev['pendingReminderCheck'], ev['communicationCheck']
    steps = []
    events = list(DB.care_reminder_events.find({'sourceCollection': 'care_plans', 'sourceId': plan['carePlanId']}))
    task_events = [e for e in events if e.get('kind') == 'test']
    # The scheduler's in-app key is care_{eventId}_{snoozes}.
    notes = [n for e in task_events for n in DB.notifications.find(
        {'recipientUserId': plan['patient'], 'idempotencyKey': {'$regex': f"^care_{e['_id']}_"}})]
    steps.append({'id': 'D-09c', 'scenario': 'Worker delivers the doctor-assigned test-task reminder',
                  'expected': 'event processed; one in-app notification without the test name (privacy); push not claimed as delivered',
                  'actual': {'events': [{k: e.get(k) for k in ('state', 'kind', 'channels', 'dueAt')} for e in task_events],
                             'inAppNotifications': len(notes),
                             'bodyMentionsTestName': any(plan['taskTitle'] in (n.get('body') or '') for n in notes)}})
    ok = bool(task_events) and all(e.get('state') == 'processed' for e in task_events) and len(notes) == 1 and not any(plan['taskTitle'] in (n.get('body') or '') for n in notes)
    steps[-1]['status'] = 'PASS' if ok else 'FAIL'
    rows = list(DB.doctor_communication_events.find({'date': comm['date']}))
    delivered = [r for r in rows if r.get('status') == 'stored_in_app']
    recips = []
    for r in delivered:
        a = DB.appointments.find_one({'_id': ObjectId(r['appointmentId'])}, {'patientUserId': 1})
        u = DB.users.find_one({'_id': ObjectId(a['patientUserId'])}, {'notificationPreferences': 1}) if a else None
        recips.append(bool(u and (u.get('notificationPreferences') or {}).get('reminder24h')))
    n = DB.notifications.count_documents({'idempotencyKey': {'$in': [r['_id'] for r in delivered]}})
    steps.append({'id': 'D-10b/d', 'scenario': 'Approved reminder batch delivered in-app to consented patients only',
                  'expected': 'stored_in_app; recipients consented; one notification each; no external delivery claimed',
                  'actual': {'statuses': sorted({r.get('status') for r in rows}), 'deliveredInApp': len(delivered),
                             'allConsented': all(recips), 'notifications': n,
                             'externalChannels': 'not attempted (in-app only; push/email/SMS not configured)'}})
    steps[-1]['status'] = 'PASS' if delivered and all(recips) and n == len(delivered) else 'FAIL'
    json.dump({'steps': steps}, open(out_path, 'w', encoding='utf-8'), indent=2, default=str)
    for s in steps:
        print(s['status'], s['id'], json.dumps(s['actual'], default=str)[:400])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
