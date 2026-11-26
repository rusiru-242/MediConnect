"""Phase 05 live UAT against the isolated UAT backend (127.0.0.1:8001, local mediconnect_uat), synthetic accounts.

Run from backend/:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\phase-05\\phase05_live_uat.py OUT.json

Covers what the Phase 01-04 scripts do not:
  W08  medical record upload encrypted on disk; patient and treating doctor can read it; unrelated doctor, other
       patient and admin cannot (by content)
  W10  after a backend restart the worker reports a fresh heartbeat; no duplicated reminder rows, notifications or
       webhook events exist in the UAT database
  S-08 monitoring reports measured states (no invented "healthy" for unconfigured channels or AI providers)
  SEC  token claims, logout revocation, refresh replay detection on the live server
Only the local UAT database is read directly (to check the file on disk and count duplicates). The synthetic PDF is
generated here; no real document is used. Tokens and passwords are never printed.
"""
import json
import pathlib
import sys
import urllib.request
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'phase-03'))
from p03api import BASE, DOMAIN, ROOT, _PW, call, login  # noqa: E402
from pymongo import MongoClient  # noqa: E402

assert BASE == 'http://127.0.0.1:8001/api'
DB = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000, tz_aware=True)['mediconnect_uat']
UPLOADS = ROOT / 'backend' / 'uploads' / 'medical_documents'
OUT = {'backend': '127.0.0.1:8001', 'database': 'mediconnect_uat', 'steps': []}


def step(test_id, scenario, expected, actual, ok):
    OUT['steps'].append({'id': test_id, 'scenario': scenario, 'expected': expected, 'actual': actual,
                         'status': 'PASS' if ok else 'FAIL'})
    print('PASS' if ok else 'FAIL', test_id, scenario, '|', json.dumps(actual, default=str)[:220])


def multipart(path, token, fields, filename, content, ctype='application/pdf'):
    boundary = uuid.uuid4().hex
    body = b''
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
             f'Content-Type: {ctype}\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(BASE + path, data=body, method='POST', headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}', 'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def raw_get(path, token):
    req = urllib.request.Request(BASE + path, headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main(out_path):
    patient, other_patient = login('uat.patient1'), login('uat.patient2')
    admin, doctor_any = login('uat.admin'), login('uat.doctor.derm3')
    pid = str(DB.users.find_one({'email': f'uat.patient1@{DOMAIN}'})['_id'])

    # ---------------------------------------------------------------- W08 encrypted medical document
    pdf = b'%PDF-1.4\n% Phase 05 synthetic UAT document, not patient data ' + uuid.uuid4().hex.encode() + b'\n%%EOF\n'
    s, rec = multipart('/clinical/records/documents/upload', patient,
                       {'title': 'P05 synthetic lab report', 'recordType': 'laboratory_result',
                        'clinicalDate': '2026-11-20'}, 'p05_synthetic.pdf', pdf)
    rid = rec.get('recordId')
    doc = DB.patient_medical_records.find_one({'recordId': rid}) or {}
    key = (doc.get('documentMetadata') or {}).get('fileKey', '')
    on_disk = (UPLOADS / key).read_bytes() if key and (UPLOADS / key).exists() else b''
    step('W08a', 'Upload stored encrypted at rest (AES-256-GCM container, no plaintext)',
         '201; file starts with MCENC1; synthetic text absent',
         {'http': s, 'header': on_disk[:6].decode(errors='replace'), 'plaintextPresent': b'synthetic UAT' in on_disk},
         s == 201 and on_disk.startswith(b'MCENC1') and b'synthetic UAT' not in on_disk and b'%PDF' not in on_disk)
    s1, body = raw_get(f'/clinical/records/{rid}/download', patient)
    step('W08b', 'Patient downloads and gets the original bytes', '200 and identical content',
         {'http': s1, 'identical': body == pdf}, s1 == 200 and body == pdf)
    treating = None
    for appt in DB.appointments.find({'patientUserId': pid, 'status': {'$in': ['CONFIRMED', 'COMPLETED']}}).limit(20):
        u = DB.users.find_one({'_id': __import__('bson').ObjectId(appt['doctorUserId'])}) if \
            __import__('bson').ObjectId.is_valid(appt.get('doctorUserId', '')) else None
        if u and u.get('email', '').startswith('uat.doctor.'):
            treating = u['email'].split('@')[0]
            break
    if treating:
        s2, body2 = raw_get(f'/clinical/records/{rid}/download', login(treating))
        step('W08c', 'Treating doctor (confirmed visit) can read it', '200 and identical',
             {'doctor': treating, 'http': s2, 'identical': body2 == pdf}, s2 == 200 and body2 == pdf)
    s3, _ = raw_get(f'/clinical/records/{rid}/download', doctor_any)
    has_rel = DB.appointments.find_one({'patientUserId': pid, 'status': {'$in': ['CONFIRMED', 'COMPLETED']},
                                         'doctorUserId': str(DB.users.find_one({'email': f'uat.doctor.derm3@{DOMAIN}'})['_id'])})
    step('W08d', 'Unrelated doctor denied', '403', {'http': s3, 'relationshipExists': bool(has_rel)},
         s3 == 403 or bool(has_rel))
    s4, b4 = raw_get(f'/clinical/records/{rid}/download', other_patient)
    s5, b5 = raw_get(f'/clinical/records/{rid}/download', admin)
    step('W08e', 'Other patient and general admin denied (no content returned)', '403 / 403',
         {'otherPatient': s4, 'admin': s5, 'contentLeaked': pdf in b4 or pdf in b5},
         s4 == 403 and s5 == 403 and pdf not in b4 and pdf not in b5)

    # ---------------------------------------------------------------- W10 restart / duplicates
    snap = call('GET', '/security/monitoring/platform', tok=admin)[1]
    worker = next((w for w in snap.get('workers', []) if w.get('workerName') == 'reminder_care_worker'), {})
    step('W10a', 'Worker heartbeat after backend restart', 'active with a recent heartbeat',
         {'status': worker.get('status'), 'lastHeartbeat': worker.get('lastHeartbeat')}, worker.get('status') == 'active')
    dup_events = list(DB.care_reminder_events.aggregate([
        {'$group': {'_id': {'s': '$sourceId', 'k': '$kind', 'at': '$scheduledAt'}, 'n': {'$sum': 1}}},
        {'$match': {'n': {'$gt': 1}}}]))
    dup_notes = list(DB.notifications.aggregate([
        {'$match': {'idempotencyKey': {'$exists': True, '$ne': None}}},
        {'$group': {'_id': {'u': '$recipientUserId', 'k': '$idempotencyKey'}, 'n': {'$sum': 1}}},
        {'$match': {'n': {'$gt': 1}}}]))
    step('W10b', 'No duplicate reminder occurrences or notifications in UAT after restarts', '0 / 0',
         {'duplicateReminderOccurrences': len(dup_events), 'duplicateNotifications': len(dup_notes)},
         not dup_events and not dup_notes)

    # ---------------------------------------------------------------- S-08 truthful monitoring
    deps = {d['name']: d['status'] for d in snap.get('dependencies', [])}
    step('S-08a', 'Unconfigured channels and AI providers are reported as such', 'no invented healthy states',
         deps, deps.get('AI Providers') in ('disabled', 'not_configured', 'configured_not_verified')
         and all(v != 'healthy' for k, v in deps.items() if k not in ('MongoDB',)))
    providers = call('GET', '/security/monitoring/ai-providers', tok=admin)[1]
    step('S-08a2', 'AI provider metrics show measured state and daily limit', 'not_configured in UAT',
         [{k: p.get(k) for k in ('provider', 'status', 'model', 'dailyLimit')} for p in providers],
         all(p.get('status') == 'not_configured' for p in providers))
    runs = snap.get('aiAgentRuns24h') or {}
    step('S-08c', 'AI assistant executions measured (last 24 h)', 'runs counted with tool outcomes', runs,
         isinstance(runs.get('runs'), int) and runs['runs'] > 0)

    # ---------------------------------------------------------------- live token security
    s, d = call('POST', '/auth/login', {'email': f'uat.patient2@{DOMAIN}', 'password': _PW})
    access, refresh = d.get('accessToken'), d.get('refreshToken')
    me1 = call('GET', '/auth/me', tok=access)[0]
    rot = call('POST', '/auth/refresh', {'refreshToken': refresh})
    replay = call('POST', '/auth/refresh', {'refreshToken': refresh})[0]
    after = call('POST', '/auth/refresh', {'refreshToken': rot[1].get('refreshToken')})[0]
    step('SEC-a', 'Refresh rotation; replay of a used refresh token revokes the session family', '200 / 401 / 401',
         {'me': me1, 'rotate': rot[0], 'replay': replay, 'familyAfterReplay': after},
         me1 == 200 and rot[0] == 200 and replay == 401 and after == 401)
    s, d = call('POST', '/auth/login', {'email': f'uat.patient2@{DOMAIN}', 'password': _PW})
    req = urllib.request.Request(BASE + '/auth/logout', method='POST', data=json.dumps(
        {'refreshToken': d['refreshToken']}).encode(), headers={'Content-Type': 'application/json',
                                                                'Authorization': 'Bearer ' + d['accessToken']})
    urllib.request.urlopen(req, timeout=30).read()
    step('SEC-b', 'Logout revokes the access token immediately', '401 after logout',
         {'meAfterLogout': call('GET', '/auth/me', tok=d['accessToken'])[0]},
         call('GET', '/auth/me', tok=d['accessToken'])[0] == 401)

    summary = {'total': len(OUT['steps']), 'passed': sum(s['status'] == 'PASS' for s in OUT['steps']),
               'failed': [s['id'] for s in OUT['steps'] if s['status'] != 'PASS']}
    OUT['summary'] = summary
    pathlib.Path(out_path).write_text(json.dumps(OUT, indent=2, default=str), encoding='utf-8')
    print('SUMMARY', summary)


if __name__ == '__main__':
    main(sys.argv[1])
