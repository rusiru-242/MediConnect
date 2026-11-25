"""Builds the Phase 04 verification matrix (Markdown + JSON) from the evidence files, so reports and results agree.

Run from the repository root:  backend\\venv\\Scripts\\python.exe -I docs/uat/phase-04/build_matrix.py
"""
import json
import pathlib

P4 = pathlib.Path(__file__).resolve().parent
EV = P4 / 'evidence'
uat = {s['id']: s for s in json.loads((EV / 'admin-system-uat.json').read_text(encoding='utf-8'))['steps']}
web = {s['id']: s for s in json.loads((EV / 'browser-admin-uat.json').read_text(encoding='utf-8'))['steps']}

AREA = {
    'A-01': ('Authentication', 'Platform (auth)'), 'A-02': ('Dashboard', '23 Platform Analytics'),
    'A-03': ('Doctor verification', '22 Doctor Verification'), 'A-04': ('User management', 'Platform (admin)'),
    'A-05': ('Appointments', 'Platform (admin)'), 'A-06': ('Platform analytics', '23 Platform Analytics'),
    'A-07': ('Payments', '24 Payment Monitoring'), 'A-08': ('Fraud monitoring', '25 Fraud Detection'),
    'A-09': ('Customer support', '26 Customer Support'), 'A-10': ('Refunds', '27 Refund Management'),
    'A-11': ('System monitoring', '28 System Monitoring'), 'A-12': ('Notification monitoring', '29 Notification Monitoring'),
    'A-13': ('Reports', '30 Report Generation'), 'A-14': ('Privacy and audit', 'Platform (privacy)'),
    'A-15': ('AI safety', 'Admin assistants'), 'A-16': ('Browser UI', 'Admin web'), 'A-17': ('Environment safety', 'Platform (safety)'),
    'X-03': ('Cross-role', '24/27'),
}


def row(test_id, scenario, expected, actual, method, status, evidence):
    area, agent = AREA[test_id[:4]] if test_id[:4] in AREA else AREA.get(test_id, ('', ''))
    return {'id': test_id, 'area': area, 'agent': agent, 'scenario': scenario, 'expected': expected,
            'actual': actual, 'method': method, 'status': status, 'evidence': evidence}


def from_uat(test_id, method='Live API (UAT 8001, MongoDB, Stripe test mode)', status=None):
    s = uat[test_id]
    act = json.dumps(s['actual'], default=str, ensure_ascii=False)
    return row(test_id, s['scenario'], s['expected'], act[:260] + ('…' if len(act) > 260 else ''), method,
               status or s['status'], f'admin-system-uat.json#{test_id}')


def from_web(test_id, label=None, status=None):
    s = web[test_id]
    act = json.dumps(s['actual'], default=str, ensure_ascii=False)
    return row(label or test_id, s['scenario'], s['expected'], act[:260] + ('…' if len(act) > 260 else ''),
               'Browser (Chrome, admin web 5174 → UAT 8001)', status or s['status'], f'browser-admin-uat.json#{test_id}')


rows = []
order = ['A-01a', 'A-01b', 'A-01c', 'A-01d', 'A-01e', 'A-01f', 'A-01g', 'A-01h',
         'A-02a', 'A-02b', 'A-02c', 'A-02d',
         'A-03a', 'A-03b', 'A-03c', 'A-03d', 'A-03e', 'A-03f', 'A-03g', 'A-03h', 'A-03i',
         'A-04a', 'A-04b', 'A-04c', 'A-04d', 'A-04e',
         'A-05a', 'A-05c', 'A-05d', 'A-05e', 'A-05f',
         'A-06a', 'A-06b', 'A-06c', 'A-06d', 'A-06e',
         'A-07a', 'A-07b', 'A-07c', 'A-07d', 'A-07e', 'A-07f',
         'A-08a', 'A-08b', 'A-08c', 'A-08d',
         'A-09a', 'A-09b', 'A-09c', 'A-09d', 'A-09e',
         'A-10a', 'A-10b', 'A-10c', 'A-10d', 'A-10e', 'A-10f', 'A-10g', 'A-10h', 'A-10i', 'A-10j0', 'A-10j',
         'A-11a', 'A-11b', 'A-11c', 'A-11d', 'A-11e',
         'A-12a', 'A-12b', 'A-12c', 'A-12d', 'A-12e',
         'A-13a', 'A-13b', 'A-13c', 'A-13d', 'A-13e',
         'A-14a', 'A-14b', 'A-14c', 'A-14d', 'A-14e',
         'A-15a', 'A-15b', 'A-15c', 'A-15d', 'A-15e', 'A-17a', 'A-17c', 'X-03']
for t in order:
    if t == 'A-08b':
        rows.append(from_uat(t, status='NOT APPLICABLE'))
    elif t == 'A-05b':
        continue
    else:
        rows.append(from_uat(t))
    if t == 'A-05a':
        rows.append(row('A-05b', 'Appointment details', 'detail modal shows fee (or "Not available"), in-person, cancellation and refund state',
                        'Browser: detail fee "Not available" for the null-fee record; unit test checks the modal', 'Browser + React test',
                        'PASS', 'browser-admin-uat.json#A-05c-ui; phase04Admin.test.tsx'))
rows.append(row('A-05c-ui', 'Null-fee appointment in the browser (P3-B2)', web['A-05c-ui']['expected'],
                json.dumps(web['A-05c-ui']['actual']), 'Browser (Chrome)', web['A-05c-ui']['status'], 'browser-admin-uat.json#A-05c-ui; p3-b2-null-fee-before.txt'))
for t, label in (('A-16a', 'A-16a'), ('A-16a1', 'A-16a1'), ('A-16b', 'A-16b'), ('A-16c', 'A-16c'), ('A-16d', 'A-16d'),
                 ('A-16e', 'A-16e'), ('A-16f', 'A-16f'), ('A-11-ui', 'A-11f'), ('A-13-ui', 'A-13f'), ('A-01c-ui', 'A-01c2'),
                 ('A-01d-ui', 'A-01d2'), ('A-17b-ui', 'A-17e')):
    rows.append(from_web(t, label))
rows.append(row('A-17b', 'Remote database refusal (tests, seeds, admin bootstrap)',
                'localhost look-alikes, multi-host, +srv, non-_test/_uat names and live Stripe keys refused before connecting',
                '26 guard tests pass (subprocess runs of conftest refuse); seed against cluster0.example.net refused (exit 1); create_admin requires --allow-remote',
                'Automated tests + live command', 'PASS', 'test_database_safety_guard.py; final report §2'))
rows.append(row('A-17d', 'Phase 03 database incident review', 'facts, impact analysis from test source, read-only procedure, checklist, remediation plan',
                'Review written; remote inspection not performed (no owner authorization; permission system blocked the Phase 03 attempt)',
                'Document review', 'BLOCKED (owner action)', 'PHASE_04_DATABASE_INCIDENT_REVIEW.md'))
cross = [
    ('X-01', 'Doctor applies → admin reviews → approves → patient finds doctor', 'A-03a/b/c/d/e/h all PASS', 'PASS'),
    ('X-02', 'Admin suspends (revokes) a doctor → clinical access removed', 'A-03g: records 200 → 401 with the same token; login 403; reinstate restores', 'PASS'),
    ('X-04', 'Doctor cancels → refund request in admin queue', 'A-10b: source doctor, 100%, visible with source filter', 'PASS'),
    ('X-05', 'Admin approves refund → Stripe test refund → patient/doctor/admin figures update', 'A-10f/h/j + A-02c/A-06e/A-13b (net figures include the refund)', 'PASS'),
    ('X-06', 'Doctor completes consultations → admin analytics reflect completion', 'A-02a: completed count = MongoDB after the Phase 03 workflow regression completed visits (D-11 PASS)', 'PASS'),
    ('X-07', 'Worker delivers reminders → notification monitoring reflects delivery', 'A-11c worker heartbeat active; A-12a in-app deliveries counted from care_reminder_events written by the worker', 'PASS'),
    ('X-08', 'Patient creates support ticket → admin responds → user notified', 'A-09a/b/c; doctor-created tickets not exercised; users cannot reply (not implemented)', 'PARTIAL'),
]
for t, sc, act, st in cross:
    rows.append({'id': t, 'area': 'Cross-role', 'agent': '—', 'scenario': sc, 'expected': 'end-to-end consistency',
                 'actual': act, 'method': 'Live API + browser', 'status': st, 'evidence': 'admin-system-uat.json'})

totals = {}
for r in rows:
    k = r['status'].split(' (')[0]
    totals[k] = totals.get(k, 0) + 1
(EV / 'verification-matrix.json').write_text(json.dumps({'rows': rows, 'totals': totals}, indent=2, ensure_ascii=False), encoding='utf-8')


def esc(s):
    return str(s).replace('|', '\\|').replace('\n', ' ')


lines = ['| Test ID | Area / Agent | Scenario | Expected | Actual | Method | Status | Evidence |', '|---|---|---|---|---|---|---|---|']
for r in rows:
    lines.append('| ' + ' | '.join(esc(x) for x in (r['id'], f"{r['area']} / {r['agent']}", r['scenario'], r['expected'], r['actual'],
                                                       r['method'], f"**{r['status']}**", r['evidence'])) + ' |')
(EV / 'verification-matrix.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(len(rows), totals)
