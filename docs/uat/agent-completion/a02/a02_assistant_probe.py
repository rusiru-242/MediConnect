"""A02 probe: read-only reminder and notification questions to the patient and doctor assistants (section 15).

Run from backend/:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\agent-completion\\a02\\a02_assistant_probe.py OUT.json
Targets only the local UAT backend (127.0.0.1:8001, mediconnect_uat) through the Phase 03 helper, which refuses any
other host. Synthetic UAT accounts only; the password is read from git-ignored backend/uat.env and never printed.
Records replies, card types and tool names only (no tokens).
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'phase-03'))
from p03api import BASE, call, login  # noqa: E402

assert BASE == 'http://127.0.0.1:8001/api'

PATIENT = [
    ('Q-1', 'Show my medicine reminders for today.', 'care_agenda:medication'),
    ('Q-2', 'When is my next appointment?', 'care_agenda:appointment'),
    ('Q-3', 'What medical tests do I have this week?', 'care_agenda:test'),
    ('Q-4', 'Show my missed medicine reminders.', 'missed_medication'),
    ('Q-5', 'mata ada bonna thiyena beheth monawada?', 'care_agenda:medication'),
    ('Q-7', 'Show my unread notifications.', 'unread_notifications'),
    ('Q-8', 'Do I have any new notifications?', 'unread_notifications'),
    ('Q-9', 'Did I miss any doses yesterday?', 'missed_medication'),
    ('Q-10', 'Change my reminder to 3 tablets at night.', 'medication_change_refusal'),
    ('Q-11', 'Mark all my notifications as read.', 'no_state_change'),
]
DOCTOR = [
    ('Q-6', 'Show my patients requiring follow-up.', 'follow_ups'),
]


def _last_assistant(d):
    d = d if isinstance(d, dict) else {}
    msgs = [m for m in d.get('messages', []) if m.get('sender', m.get('role')) == 'assistant']
    msg = msgs[-1] if msgs else {}
    return (msg.get('content') or str(d.get('detail', '')))[:600], (msg.get('metadata') or {}).get('type')


def main(out_path, patient='uat.patient1', doctor='uat.doctor.cardio'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    out = {'backend': '127.0.0.1:8001', 'database': 'mediconnect_uat', 'rows': []}
    p_tok, d_tok = login(patient), login(doctor)
    for rid, text, expected in PATIENT:
        s, d = call('POST', '/ai/conversations', {'initialMessage': text}, tok=p_tok)
        reply, card = _last_assistant(d)
        out['rows'].append({'id': rid, 'role': 'PATIENT', 'message': text, 'expected': expected, 'status': s,
                            'card': card, 'reply': reply})
    for rid, text, expected in DOCTOR:
        s, d = call('POST', '/doctor/workflow/assistant', {'message': text}, tok=d_tok)
        d = d if isinstance(d, dict) else {}
        out['rows'].append({'id': rid, 'role': 'DOCTOR', 'message': text, 'expected': expected, 'status': s,
                            'intent': d.get('intent'), 'tool': d.get('tool') or d.get('toolCalled'),
                            'reply': str(d.get('message') or d.get('reply'))[:600]})
    pathlib.Path(out_path).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    for r in out['rows']:
        print(r['id'], r['status'], r.get('card') or r.get('tool'), '|', r['reply'][:120].replace('\n', ' '))


if __name__ == '__main__':
    main(sys.argv[1])
