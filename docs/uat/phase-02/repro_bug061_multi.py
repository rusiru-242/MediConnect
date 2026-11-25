"""BUG-061 multi-doctor reproduction: the requested time is taken for the chosen doctor but free for another."""
import json, sys, uuid, os
sys.path.insert(0, os.path.dirname(__file__))
from p02api import call, login, unwrap

DATE = sys.argv[1] if len(sys.argv) > 1 else '2026-11-29'
out = {}
pc, pa = login('uat.p02.patientc'), login('uat.p02.patienta')
day = unwrap(call('GET', f'/doctors/UAT-P02-ORTHO/availability?date={DATE}', tok=pa)[1])
ten = next(x for x in day['slots'] if x['startTime'] == '10:00')
s, d = call('POST', '/appointments', {'doctorId': 'UAT-P02-ORTHO', 'availabilityId': ten['availabilityId'],
                                      'date': DATE, 'startTime': '10:00'}, tok=pc)
blocker = (unwrap(d).get('appointment') or {}).get('id')
out['blocker_hold_http'] = s

def turn(cid, m):
    st, d = call('POST', f'/ai/conversations/{cid}/messages', {'message': m, 'requestId': uuid.uuid4().hex[:20]}, pa)
    d = unwrap(d); bs = d.get('bookingSummary') or {}
    return {'user': m, 'http': st, 'state': d.get('state'),
            'replies': [x['content'][:300] for x in d.get('messages', [])[-2:] if x['sender'] == 'assistant'],
            'selectedDoctor': (d.get('selectedDoctor') or {}).get('fullName'),
            'proposal': bs.get('doctorName') and f"{bs.get('doctorName')} {bs.get('startTime')}",
            'selectionReason': bs.get('selectionReason'),
            'candidates': [(c.get('fullName'), [x['startTime'] for x in c.get('availableSlots', [])][:6]) for c in d.get('candidateDoctors') or []]}

try:
    # Flow 1: patient chooses Dr. P02 Ortho from search results, then asks for a time that is taken for him.
    _, c = call('POST', '/ai/conversations', {}, pa); cid = unwrap(c)['id']
    out['flow1'] = [turn(cid, 'Find an orthopedic doctor in Kandy')]
    s, d = call('POST', f'/ai/booking/sessions/{cid}/select-doctor', {'doctorId': 'UAT-P02-ORTHO'}, tok=pa)
    out['flow1'].append({'select_doctor_http': s, 'selectedDoctor': (unwrap(d).get('selectedDoctor') or {}).get('fullName')})
    nice = __import__('datetime').date.fromisoformat(DATE).strftime('%B %d, %Y').replace(' 0', ' ')
    out['flow1'].append(turn(cid, f'Book {nice} at 10:00'))
    # Flow 2: named doctor in the same message, specialty also mentioned.
    _, c = call('POST', '/ai/conversations', {}, pa); cid2 = unwrap(c)['id']
    out['flow2'] = [turn(cid2, f'Book orthopedic Dr. P02 Ortho in Kandy on {nice} at 10:00')]
finally:
    if blocker:
        out['blocker_released_http'] = call('POST', f'/appointments/{blocker}/cancel', {'reason': 'Phase 02 repro cleanup'}, tok=pc)[0]
print(json.dumps(out, indent=1))
