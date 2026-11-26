"""Phase 05 natural-language probe of the patient, doctor and admin assistants (section 8 examples + paraphrases).

Run from backend/:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\phase-05\\intent_probe.py OUT.json
Targets only the local UAT backend (127.0.0.1:8001, mediconnect_uat) through the Phase 03 helper, which refuses
any other host. Synthetic UAT accounts only; the password is read from git-ignored backend/uat.env, never printed.
Only replies, tool names and card types are recorded (no tokens).
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'phase-03'))
from p03api import BASE, call, login, unwrap  # noqa: E402

assert BASE == 'http://127.0.0.1:8001/api'

PATIENT = [
    ('P-1', 'mata Colombo walin hoda cardiologist kenek hoyala denna', 'doctor_search'),
    ('P-2', 'mata 3000ta aduwen kenek hoyala denna', 'doctor_search'),
    ('P-3', 'Select the most experienced doctor.', 'doctor_selection'),
    ('P-4', 'Show me my next appointment.', 'appointments'),
    ('P-5', 'When should I take the medicine prescribed by my doctor?', 'medication_schedule'),
    ('P-6', 'Show my upcoming medical tests.', 'medical_tests'),
    ('P-7', 'මට කොළඹ හෘද වෛද්‍යවරයෙක් හොයලා දෙන්න', 'doctor_search'),
    ('P-8', 'I want a skin doctor in Kandy under 2500', 'doctor_search'),
    ('P-9', 'change my dose to two tablets', 'medication_change_refusal'),
]
DOCTOR = [
    ('D-1', 'Show my appointments for tomorrow.', 'schedule'),
    ('D-2', 'Find the patients requiring follow-up this week.', 'follow_ups'),
    ('D-3', 'Prepare the consultation summary for my next patient.', 'consultation_preparation'),
    ('D-4', 'Show my pending prescription renewal requests.', 'renewal_queue'),
    ('D-5', 'How many consultations did I complete this month?', 'analytics'),
    ('D-6', 'heta mage appointments monawada?', 'schedule'),
    ('D-7', 'Who still needs a follow up from me in the coming days?', 'follow_ups'),
]
ADMIN = [
    ('A-1', 'Show me pending doctor verification applications.', 'pending_doctor_verifications'),
    ('A-2', 'Which refunds need attention?', 'refunds_attention'),
    ('A-3', 'How many successful payments were recorded this week?', 'payment_summary'),
    ('A-4', 'Show notification failures.', 'notification_failures'),
    ('A-5', 'Explain why this fraud assessment was generated.', 'fraud_explanation'),
    ('A-6', 'doctorlage applications kiyak approve karanna thiyenawada?', 'pending_doctor_verifications'),
    ('A-7', 'Are any messages failing to reach users?', 'notification_failures'),
    ('A-8', 'මේ සතියේ සාර්ථක ගෙවීම් කීයද?', 'payment_summary'),
    ('A-9', 'Is the system healthy?', 'system_health'),
]


def _last_assistant(d):
    d = d if isinstance(d, dict) else {}
    msgs = [m for m in d.get('messages', []) if m.get('sender', m.get('role')) == 'assistant']
    msg = msgs[-1] if msgs else {}
    return (msg.get('content') or str(d.get('detail', '')))[:400], (msg.get('metadata') or {}).get('type')


def chat_patient(tok, text, session=None):
    """Same endpoints as the Flutter app (/ai/conversations): a new chat per prompt unless a session is given."""
    if session is None:
        s, d = call('POST', '/ai/conversations', {'initialMessage': text}, tok=tok)
        reply, card = _last_assistant(d)
        return s, (d or {}).get('id'), reply, card
    s, d = call('POST', f'/ai/conversations/{session}/messages', {'message': text}, tok=tok)
    reply, card = _last_assistant(d)
    return s, session, reply, card


def main(out_path):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    out = {'backend': '127.0.0.1:8001', 'database': 'mediconnect_uat', 'rows': []}
    p_tok = login('uat.patient1')
    d_tok = login('uat.doctor.cardio')
    a_tok = login('uat.admin')
    session = None
    for rid, text, expected in PATIENT:
        status, session_used, reply, card = chat_patient(p_tok, text, session if rid == 'P-3' else None)
        if rid == 'P-1':
            session = session_used
        out['rows'].append({'id': rid, 'role': 'PATIENT', 'message': text, 'expectedIntent': expected,
                            'status': status, 'card': card, 'reply': reply})
    for rid, text, expected in DOCTOR:
        s, d = call('POST', '/doctor/workflow/assistant', {'message': text}, tok=d_tok)
        d = d if isinstance(d, dict) else {}
        out['rows'].append({'id': rid, 'role': 'DOCTOR', 'message': text, 'expectedIntent': expected, 'status': s,
                            'intent': d.get('intent'), 'tool': d.get('tool') or d.get('toolCalled'),
                            'reply': str(d.get('message') or d.get('reply'))[:400]})
    for rid, text, expected in ADMIN:
        s, d = call('POST', '/admin/workflow/assistant', {'message': text}, tok=a_tok)
        d = d if isinstance(d, dict) else {}
        out['rows'].append({'id': rid, 'role': 'ADMIN', 'message': text, 'expectedIntent': expected, 'status': s,
                            'intent': d.get('intent'), 'tool': d.get('toolCalled'), 'reply': str(d.get('reply'))[:400]})
    pathlib.Path(out_path).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    for r in out['rows']:
        print(r['id'], r['status'], r.get('tool') or r.get('card'), '|', r['reply'][:110].replace('\n', ' '))


if __name__ == '__main__':
    main(sys.argv[1])
