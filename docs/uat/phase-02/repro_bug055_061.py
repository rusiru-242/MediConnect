"""Phase 02 reproduction of BUG-055 and BUG-061 against the local UAT API (127.0.0.1:8001)."""
import json, sys, uuid
sys.path.insert(0, __import__('os').path.dirname(__file__))
from p02api import call, login, unwrap

out = {}
pc, pa = login('uat.p02.patientc'), login('uat.p02.patienta')
s, slots = call('GET', '/doctors/UAT-P02-ORTHO/availability?date=2026-11-27', tok=pa)
day = unwrap(slots)
ten = next((x for x in day.get('slots', []) if x['startTime'] == '10:00'), None)
out['slot_10_before'] = bool(ten)
if ten:  # patient C occupies 10:00 with a normal 10-minute hold
    s, d = call('POST', '/appointments', {'doctorId': 'UAT-P02-ORTHO', 'availabilityId': ten['availabilityId'],
                                          'date': '2026-11-27', 'startTime': '10:00'}, tok=pc)
    out['blocker_hold_http'] = s
    out['blocker_appointment_id'] = (unwrap(d).get('appointment') or {}).get('id')

def conv(tok, msgs):
    _, c = call('POST', '/ai/conversations', {}, tok)
    cid = unwrap(c)['id']
    res = []
    last = None
    for m in msgs:
        st, d = call('POST', f'/ai/conversations/{cid}/messages', {'message': m, 'requestId': uuid.uuid4().hex[:20]}, tok)
        d = unwrap(d)
        last = d
        bs = d.get('bookingSummary') or {}
        res.append({'user': m, 'http': st, 'state': d.get('state'),
                    'replies': [x['content'][:400] for x in d.get('messages', [])[-2:] if x['sender'] == 'assistant'],
                    'selectedDoctor': (d.get('selectedDoctor') or {}).get('fullName'),
                    'proposalSlot': (bs.get('acceptedSlot') or {}).get('startTime') or bs.get('startTime'),
                    'selectionReason': bs.get('selectionReason'),
                    'candidates': [(c.get('fullName'), [x['startTime'] for x in c.get('availableSlots', [])][:8]) for c in d.get('candidateDoctors') or []]})
    return cid, res, last

cid, out['bug061'], last = conv(pa, ['Book Dr. P02 Ortho on November 27, 2026 at 10:00'])
# BUG-055: requested 10:30 exactly, then the patient manually selects 15:00 in the slot picker.
cid2, out['bug055_request'], last2 = conv(pa, ['Book Dr. P02 Ortho on November 28, 2026 at 10:30'])
s, d = call('POST', f'/ai/booking/sessions/{cid2}/select-doctor', {'doctorId': 'UAT-P02-ORTHO', 'date': '2026-11-28'}, tok=pa)
slots = unwrap(d).get('candidateSlots', [])
pick = next(x for x in slots if x['startTime'] == '15:00')
s, d = call('POST', f'/ai/booking/sessions/{cid2}/select-slot', {**pick, 'prepareProposal': True}, tok=pa)
bs = unwrap(d).get('bookingSummary') or {}
out['bug055_manual_select'] = {'http': s, 'selected': bs.get('startTime'), 'requestedTime': bs.get('requestedTime'),
                               'selectionReason': bs.get('selectionReason')}
# release the blocker hold so the fixture is clean
if out.get('blocker_appointment_id'):
    s, _ = call('POST', f"/appointments/{out['blocker_appointment_id']}/cancel", {'reason': 'Phase 02 repro cleanup'}, tok=pc)
    out['blocker_released_http'] = s
print(json.dumps(out, indent=1))
