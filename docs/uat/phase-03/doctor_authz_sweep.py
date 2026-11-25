"""Phase 03 doctor-endpoint authorization sweep against the local UAT backend (127.0.0.1:8001 only).

Run from backend/:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\phase-03\\doctor_authz_sweep.py OUT.json

For every doctor-facing endpoint, calls it as: approved doctor (Alpha), PENDING doctor, REJECTED doctor,
patient, admin, and with no / an invalid token. A SUSPENDED doctor's login is attempted first. State-changing
calls send bodies that would be valid for an approved doctor but target synthetic Phase 03 data only, so a
mistaken 2xx from an unauthorized role is detectable and harmless. No secrets are printed.
"""
import json
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p03api import DOMAIN, _PW, call, colombo_now, login, unwrap  # noqa: E402

from pymongo import MongoClient  # noqa: E402

DB = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000)['mediconnect_uat']


def uid(key):
    return str(DB.users.find_one({'email': f'{key}@{DOMAIN}'})['_id'])


def main(out_path):
    tomorrow = (colombo_now().date() + timedelta(days=1)).isoformat()
    far = (colombo_now().date() + timedelta(days=20)).isoformat()
    pa = uid('uat.p03.patienta')
    alpha_appt = DB.appointments.find_one({'doctorUserId': uid('uat.p03.doctor.alpha'), 'patientUserId': pa,
                                           'status': 'CONFIRMED'}, {'_id': 1})
    aid = str(alpha_appt['_id']) if alpha_appt else '000000000000000000000000'
    endpoints = [
        ('GET', '/doctors/me/application-status', None, 'support'),
        ('GET', '/doctors/me/availability', None, 'schedule'),
        ('POST', '/doctors/me/availability', {'date': far, 'startTime': '10:00', 'endTime': '11:00', 'slotDurationMinutes': 30}, 'schedule'),
        ('GET', '/doctors/me/weekly-schedule', None, 'schedule'),
        ('GET', '/doctors/me/leave', None, 'schedule'),
        ('POST', '/doctors/me/blocked-time', {'date': far, 'startTime': '10:00', 'endTime': '10:30'}, 'schedule'),
        ('GET', '/doctors/me/calendar-overview', None, 'schedule'),
        ('GET', '/doctors/me/appointments', None, 'appointments'),
        ('GET', '/appointments/doctor/list', None, 'appointments'),
        ('GET', f'/appointments/{aid}', None, 'appointments'),
        ('GET', '/doctor/schedule/today', None, 'appointments'),
        ('GET', f'/doctor/consultations/{aid}', None, 'appointments'),
        ('GET', '/doctor/workflow/queue', None, 'workflow'),
        ('GET', f'/doctor/workflow/preparation/{aid}', None, 'clinical'),
        ('GET', '/doctor/workflow/follow-ups', None, 'workflow'),
        ('GET', '/doctor/workflow/analytics', None, 'workflow'),
        ('POST', '/doctor/workflow/assistant', {'message': 'show my schedule'}, 'ai'),
        ('GET', f'/clinical/records?patientId={pa}', None, 'clinical'),
        ('GET', f'/clinical/records/summary?patientId={pa}', None, 'clinical'),
        ('GET', f'/clinical/notes?patientId={pa}', None, 'clinical'),
        ('GET', f'/clinical/measurements/trends?patientId={pa}', None, 'clinical'),
        ('POST', '/clinical/notes/draft', {'patientUserId': pa, 'rawNotes': 'authz sweep'}, 'clinical'),
        ('POST', '/clinical/prescriptions/assistant-review', {'patientUserId': pa, 'medicationNames': ['UAT']}, 'clinical'),
        ('POST', '/clinical/prescriptions/sign', {'patientUserId': pa, 'medicationItems': [{'medicationName': 'UAT Sweep',
            'strength': '1 mg', 'dose': '1', 'route': 'Oral', 'frequency': 'Once daily', 'duration': '1 day', 'quantity': '1'}]}, 'clinical'),
        ('GET', '/clinical/prescriptions/renewals', None, 'clinical'),
        ('GET', '/care-plans/doctor', None, 'care'),
        ('POST', '/care-plans', {'appointmentId': aid, 'patientUserId': pa, 'reason': 'authz sweep',
                                 'instructions': 'authz sweep', 'tasks': []}, 'care'),
        ('GET', '/medical-records/me', None, 'clinical'),
        ('GET', '/prescriptions/me', None, 'clinical'),
    ]
    # 'patient' = patient A, who owns {patientA} and {alphaAppointment}; 'otherPatient' = patient B (not the owner).
    tokens = {'approved': login('uat.p03.doctor.alpha'), 'pending': login('uat.doctor.pending1'),
              'patient': login('uat.p03.patienta'), 'otherPatient': login('uat.p03.patientb'), 'admin': login('uat.admin'), 'invalid': 'not-a-token', 'none': None}
    sus = call('POST', '/auth/login', {'email': f'uat.p03.doctor.suspended@{DOMAIN}', 'password': _PW})
    rej = call('POST', '/auth/login', {'email': f'uat.p03.doctor.rejected@{DOMAIN}', 'password': _PW})
    if rej[0] == 200:
        tokens['rejected'] = rej[1].get('access_token') or rej[1].get('accessToken')
    rows = []
    for method, path, body, area in endpoints:
        row = {'method': method, 'path': path.replace(pa, '{patientA}').replace(aid, '{alphaAppointment}'), 'area': area}
        for role, tok in tokens.items():
            if role == 'approved' and method == 'POST':
                row[role] = 'not called'  # writes by the approved doctor are exercised in the workflow UAT
                continue
            row[role] = call(method, path, body, tok=tok)[0]
        rows.append(row)
        print(json.dumps(row))
    def unauthorized(row):
        """2xx for a caller who must not see the resource. Own-data rows are legitimate:
        patient A on {patientA}/{alphaAppointment}, and any caller's own /me lists (empty for a pending doctor)."""
        own_list = row['path'].endswith('/me') or row['path'] == '/clinical/prescriptions/renewals'
        bad = []
        for k in ('pending', 'rejected', 'otherPatient', 'invalid', 'none'):
            code = row.get(k)
            if isinstance(code, int) and 200 <= code < 300 and row['area'] != 'support' and not (own_list and k not in ('invalid', 'none')):
                bad.append(k)
        if isinstance(row.get('patient'), int) and 200 <= row['patient'] < 300 and row['area'] not in ('appointments', 'clinical') and not own_list:
            bad.append('patient')
        return bad
    leaked = [{**r, 'unauthorizedRoles': unauthorized(r)} for r in rows if unauthorized(r)]
    result = {'suspendedLoginHttp': sus[0], 'suspendedLoginDetail': sus[1].get('detail'),
              'rejectedLoginHttp': rej[0], 'rejectedLoginDetail': rej[1].get('detail'), 'rows': rows,
              'unauthorizedSuccesses': leaked}
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(result, fh, indent=2)
    print('suspended login', sus[0], 'rejected login', rej[0], '| unauthorized successes:', len(leaked))


if __name__ == '__main__':
    main(sys.argv[1])
