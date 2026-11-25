"""Phase 02 live verification of patient components 05-13 on the local UAT backend (127.0.0.1:8001).

Run from backend/:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\phase-02\\patient_care_uat.py OUT.json
Synthetic data only: P02 patient A/B, Dr. P02 Ortho (care relationship through one synthetic COMPLETED visit that this
script inserts as a fixture) and Dr. P02 Spine (no active relationship). The real background worker of the UAT
backend executes the reminders; FCM, SMTP and SMS are not configured in UAT, so only in-app delivery can succeed.
"""
import json
import os
import pathlib
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p02api import call, login, unwrap  # noqa: E402
from bson import ObjectId  # noqa: E402
from pymongo import MongoClient  # noqa: E402
import urllib.request, urllib.error  # noqa: E402,E401

DB = MongoClient('mongodb://127.0.0.1:27017')['mediconnect_uat']
COLOMBO = ZoneInfo('Asia/Colombo')
EV = {'backend': '127.0.0.1:8001', 'database': 'mediconnect_uat', 'components': {}}


def log(component, step, **data):
    EV['components'].setdefault(component, []).append({'step': step, **data})
    print(component, step, json.dumps(data, default=str)[:260])


def upload(tok, filename, content, ctype, fields):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                 f'Content-Type: {ctype}\r\n\r\n'.encode() + content + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    req = urllib.request.Request('http://127.0.0.1:8001/api/clinical/records/documents/upload', method='POST',
                                 data=b''.join(parts), headers={'Authorization': 'Bearer ' + tok,
                                                                'Content-Type': f'multipart/form-data; boundary={boundary}'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def wait_for(query, seconds=200):
    end = time.time() + seconds
    while time.time() < end:
        doc = DB.care_reminder_events.find_one(query)
        if doc and doc.get('state') in {'processed', 'cancelled', 'expired'}:
            return doc
        time.sleep(5)
    return DB.care_reminder_events.find_one(query)


def main(out):
    a, b = login('uat.p02.patienta'), login('uat.p02.patientb')
    ortho, spine = login('uat.p02.doctor.ortho'), login('uat.p02.doctor.spine')
    users = {u['email'].split('@')[0]: str(u['_id']) for u in DB.users.find({'email': {'$regex': r'^uat\.p02\.'}})}
    pa, pb, dortho = users['uat.p02.patienta'], users['uat.p02.patientb'], users['uat.p02.doctor.ortho']
    prof = DB.doctor_profiles.find_one({'userId': dortho})
    now = datetime.now(timezone.utc)
    local = now.astimezone(COLOMBO)
    yesterday = (local - timedelta(days=1)).date().isoformat()
    existing = DB.appointments.find_one({'uatFixture': 'phase02_completed_visit', 'patientUserId': pa})
    visit = existing['_id'] if existing else DB.appointments.insert_one({
        'patientUserId': pa, 'doctorUserId': dortho, 'doctorProfileId': str(prof['_id']), 'availabilityId': '',
        'appointmentDate': yesterday, 'startTime': '07:00', 'endTime': '07:30', 'status': 'COMPLETED',
        'paymentStatus': 'NOT_REQUIRED', 'consultationFee': 3000.0, 'createdAt': now, 'updatedAt': now,
        'uatFixture': 'phase02_completed_visit'}).inserted_id  # reused on re-runs (unique slot index)
    log('setup', 'synthetic_completed_visit', appointmentId=str(visit), note='fixture inserted directly (care relationship)')

    # ---------------------------------------------------------------- 05 Medication reminders
    s, rx = call('POST', '/clinical/prescriptions/sign', {'patientUserId': pa, 'appointmentId': str(visit), 'medicationItems': [{
        'medicationName': 'UAT Synthetic Tablet', 'strength': '10 mg', 'dose': '1 tablet', 'route': 'Oral',
        'frequency': 'Once daily', 'duration': '1 day', 'quantity': '1 tablet'}]}, tok=ortho)
    rx = unwrap(rx)
    log('05_medication', 'doctor_signs_prescription', http=s, status=rx.get('status'))
    rx_doc = DB.prescriptions.find_one({'prescriptionId': rx.get('prescriptionId')}) or {}
    due_local = (datetime.now(timezone.utc) + timedelta(minutes=1)).astimezone(COLOMBO)
    sched = {'medicationIndex': 0, 'times': [due_local.strftime('%H:%M')], 'startDate': due_local.date().isoformat(),
             'endDate': due_local.date().isoformat(), 'confirm': True}
    path = f"/care-automation/prescriptions/{rx_doc.get('_id')}/schedule"
    log('05_medication', 'patient_cannot_approve_schedule', http=call('PUT', path, sched, tok=a)[0])
    log('05_medication', 'other_doctor_cannot_approve', http=call('PUT', path, sched, tok=spine)[0])
    s, appr = call('PUT', path, sched, tok=ortho)
    s2, appr2 = call('PUT', path, sched, tok=ortho)
    schedule_id = unwrap(appr).get('scheduleId')
    log('05_medication', 'doctor_approves_schedule', http=s, scheduleTimes=sched['times'], timezone='Asia/Colombo',
        repeat_same_schedule=unwrap(appr2).get('scheduleId') == schedule_id)
    ev = wait_for({'sourceId': schedule_id})
    log('05_medication', 'worker_executed_reminder', found=bool(ev), state=(ev or {}).get('state'),
        channels={k: v.get('status') for k, v in ((ev or {}).get('channels') or {}).items()},
        due_colombo=(ev or {}).get('dueAt') and ev['dueAt'].replace(tzinfo=timezone.utc).astimezone(COLOMBO).isoformat())
    if ev:
        notice = DB.notifications.find_one({'relatedCareEventId': ev['_id']})
        log('05_medication', 'in_app_notification_private', exists=bool(notice),
            body_has_medicine_name='UAT Synthetic Tablet' in (notice or {}).get('body', ''))
        detail = f"/care-automation/events/{ev['_id']}"
        s, d = call('GET', detail, tok=a)
        log('05_medication', 'patient_reads_instructions', http=s, instructions=unwrap(d).get('instructions'))
        log('05_medication', 'other_patient_denied', http=call('GET', detail, tok=b)[0])
        for action in ('snooze', 'taken'):
            rid = uuid.uuid4().hex
            r1 = call('POST', f'{detail}/actions', {'action': action, 'requestId': rid}, tok=a)[0]
            r2 = call('POST', f'{detail}/actions', {'action': action, 'requestId': rid}, tok=a)[0]
            log('05_medication', f'action_{action}_idempotent', http=[r1, r2])
        log('05_medication', 'audit_entries', count=len(DB.care_reminder_events.find_one({'_id': ev['_id']}).get('audit', [])))
        log('05_medication', 'other_patient_cannot_act', http=call('POST', f'{detail}/actions', {'action': 'taken', 'requestId': uuid.uuid4().hex}, tok=b)[0])
    s, act = call('GET', f"/care-automation/prescriptions/{rx_doc.get('_id')}/activity", tok=ortho)
    log('05_medication', 'doctor_sees_patient_reported_activity', http=s, sources=sorted({x.get('source') for x in (act if isinstance(act, list) else [])}))
    before = DB.care_tracking_schedules.count_documents({}) , DB.prescriptions.find_one({'_id': rx_doc.get('_id')}, {'medicationItems': 1})
    cid = unwrap(call('POST', '/ai/conversations', {}, tok=a)[1])['id']
    st, chat = call('POST', f'/ai/conversations/{cid}/messages', {'message': 'Please increase my UAT Synthetic Tablet dose to 3 tablets', 'requestId': uuid.uuid4().hex[:20]}, tok=a)
    after = DB.prescriptions.find_one({'_id': rx_doc.get('_id')}, {'medicationItems': 1})
    log('05_medication', 'ai_cannot_change_dose', http=st, prescription_unchanged=before[1] == after,
        reply=(unwrap(chat).get('messages') or [{}])[-1].get('content', '')[:240])
    log('05_medication', 'doctor_cancels_schedule', http=call('DELETE', f"/care-automation/prescriptions/{rx_doc.get('_id')}/schedule/0", tok=ortho)[0])

    # ---------------------------------------------------------------- 06/08/09 Care plan, follow-up, medical test
    test_due = datetime.now(timezone.utc) + timedelta(minutes=1)
    plan_req = {'appointmentId': str(visit), 'followUpDate': (local + timedelta(days=7)).date().isoformat(),
                'reason': 'UAT follow-up review', 'instructions': 'Clinician-authored synthetic instructions.',
                'recommendedConsultationType': 'IN_PERSON',
                'tasks': [{'title': 'UAT fasting blood test', 'kind': 'test', 'dueAt': test_due.isoformat(),
                           'location': 'UAT Kandy Lab'}]}
    log('06_care_plan', 'patient_cannot_create', http=call('POST', '/care-plans', plan_req, tok=a)[0])
    log('06_care_plan', 'video_type_rejected', http=call('POST', '/care-plans', {**plan_req, 'recommendedConsultationType': 'VIDEO'}, tok=ortho)[0])
    s, plan = call('POST', '/care-plans', plan_req, tok=ortho)
    plan = unwrap(plan)
    plan_id, task_id = plan.get('id'), ((plan.get('tasks') or [{}])[0]).get('taskId')
    log('06_care_plan', 'doctor_creates', http=s, status=plan.get('status'), tasks=len(plan.get('tasks') or []))
    s, mine = call('GET', '/care-plans/patient', tok=a)
    log('06_care_plan', 'patient_receives', http=s, visible=bool(plan_id) and plan_id in json.dumps(mine, default=str))
    log('06_care_plan', 'other_patient_denied', http=call('GET', f'/care-plans/{plan_id}', tok=b)[0])
    log('06_care_plan', 'unrelated_doctor_denied', http=call('GET', f'/care-plans/{plan_id}', tok=spine)[0])
    ev = wait_for({'sourceId': plan_id, 'kind': 'test'})
    log('09_medical_test', 'worker_executed_test_reminder', found=bool(ev), state=(ev or {}).get('state'),
        channels={k: v.get('status') for k, v in ((ev or {}).get('channels') or {}).items()})
    st, chat = call('POST', f'/ai/conversations/{cid}/messages', {'message': 'Show my care tasks', 'requestId': uuid.uuid4().hex[:20]}, tok=a)
    log('06_care_plan', 'ai_reads_real_tasks_before_completion', http=st, reply=(unwrap(chat).get('messages') or [{}])[-1].get('content', '')[:300])
    s, agenda = call('GET', '/care-automation/agenda', tok=a)
    ag = unwrap(agenda)
    ag_items = ag if isinstance(ag, list) else ag.get('items', [])
    log('09_medical_test', 'agenda_shows_test', http=s, titles=[x.get('title') for x in ag_items][:6])
    s, upd = call('PATCH', f'/care-plans/{plan_id}/tasks/{task_id}', {'isCompleted': True}, tok=a)
    u = unwrap(upd)
    log('06_care_plan', 'patient_completes_task', http=s, task_completed=[t.get('isCompleted') for t in u.get('tasks', [])],
        progress={k: v for k, v in u.items() if 'progress' in k.lower() or 'complet' in k.lower()})
    log('06_care_plan', 'other_patient_cannot_complete', http=call('PATCH', f'/care-plans/{plan_id}/tasks/{task_id}', {'isCompleted': True}, tok=b)[0])
    s, fu = call('GET', '/doctor/workflow/follow-ups', tok=ortho)
    log('08_follow_up', 'doctor_follow_up_list', http=s, contains_plan=plan_id in json.dumps(fu, default=str))
    s, up = call('PUT', f'/care-plans/{plan_id}', {'instructions': 'Updated synthetic instructions.', 'reason': 'UAT follow-up review (updated)'}, tok=ortho)
    log('06_care_plan', 'doctor_updates', http=s, version=unwrap(up).get('version'))
    log('06_care_plan', 'patient_cannot_update', http=call('PUT', f'/care-plans/{plan_id}', {'instructions': 'patient edit'}, tok=a)[0])
    st, chat = call('POST', f'/ai/conversations/{cid}/messages', {'message': 'Show my care tasks', 'requestId': uuid.uuid4().hex[:20]}, tok=a)
    log('06_care_plan', 'ai_reads_real_tasks', http=st, reply=(unwrap(chat).get('messages') or [{}])[-1].get('content', '')[:300])
    s, cancel = call('POST', f'/care-plans/{plan_id}/cancel', {'reason': 'UAT cleanup'}, tok=ortho)
    log('08_follow_up', 'doctor_cancels_plan', http=s, status=unwrap(cancel).get('status'))

    # ---------------------------------------------------------------- 07 Appointment reminder
    at = (datetime.now(timezone.utc) + timedelta(hours=2, minutes=1)).astimezone(COLOMBO)
    appt = DB.appointments.insert_one({
        'patientUserId': pa, 'doctorUserId': dortho, 'doctorProfileId': str(prof['_id']), 'availabilityId': '',
        'appointmentDate': at.date().isoformat(), 'startTime': at.strftime('%H:%M'),
        'endTime': (at + timedelta(minutes=30)).strftime('%H:%M'), 'status': 'CONFIRMED', 'paymentStatus': 'NOT_REQUIRED',
        'consultationFee': 3000.0, 'appointmentVersion': 1, 'createdAt': now, 'updatedAt': now,
        'uatFixture': 'phase02_reminder_visit'}).inserted_id
    log('07_appointment_reminder', 'fixture_confirmed_appointment', starts_colombo=at.isoformat(), note='2h reminder due ~1 min later')
    ev = wait_for({'sourceId': str(appt), 'kind': 'appointment'})
    notice = DB.notifications.find_one({'relatedCareEventId': (ev or {}).get('_id')}) if ev else None
    log('07_appointment_reminder', 'worker_executed', found=bool(ev), state=(ev or {}).get('state'), recipient_is_patient=(ev or {}).get('patientUserId') == pa,
        channels={k: v.get('status') for k, v in ((ev or {}).get('channels') or {}).items()}, in_app=bool(notice))
    s, c = call('POST', f'/appointments/{appt}/cancel', {'reason': 'UAT reminder cleanup'}, tok=a)
    log('07_appointment_reminder', 'cancel_appointment', http=s,
        future_reminders=len([r for r in DB.care_reminder_events.find({'sourceId': str(appt), 'state': 'pending'})]))

    # ---------------------------------------------------------------- 10 Health tracking
    for label, path, body in (
        ('clinical_invalid_bp', '/clinical/measurements', {'metric': 'blood_pressure', 'value': 110, 'secondary': 120}),
        ('clinical_crisis_bp', '/clinical/measurements', {'metric': 'blood_pressure', 'value': 195, 'secondary': 125}),
        ('clinical_normal_glucose', '/clinical/measurements', {'metric': 'blood_glucose', 'value': 98}),
        ('agenda_invalid_unit', '/care-automation/measurements', {'metric': 'temperature', 'value': 98.6}),
        ('agenda_crisis_bp', '/care-automation/measurements', {'metric': 'blood_pressure', 'value': 195, 'secondary': 125}),
        ('agenda_weight', '/care-automation/measurements', {'metric': 'weight', 'value': 64.5}),
    ):
        s, d = call('POST', path, body, tok=a)
        d = unwrap(d)
        log('10_health_tracking', label, http=s, alert=d.get('criticalAlert'), unit=d.get('unit'), source=d.get('source'))
    s, tr = call('GET', '/clinical/measurements/trends', tok=a)
    log('10_health_tracking', 'trends', http=s, metrics=[t.get('metric') for t in unwrap(tr).get('trends', [])])
    s, other = call('GET', '/care-automation/measurements', tok=b)
    log('10_health_tracking', 'patient_b_sees_only_own', http=s, count=len(unwrap(other).get('items', [])))
    log('10_health_tracking', 'related_doctor_trends', http=call('GET', f'/clinical/measurements/trends?patientId={pa}', tok=ortho)[0])
    log('10_health_tracking', 'unrelated_doctor_trends', http=call('GET', f'/clinical/measurements/trends?patientId={pa}', tok=spine)[0])

    # ---------------------------------------------------------------- 11 Prescription renewal
    rq = {'originalPrescriptionId': rx.get('prescriptionId'), 'medicationName': 'UAT Synthetic Tablet',
          'patientReason': 'Synthetic renewal request for UAT.'}
    s, ren = call('POST', '/clinical/prescriptions/renewals', rq, tok=a)
    ren = unwrap(ren)
    log('11_renewal', 'patient_requests', http=s, status=ren.get('status'))
    log('11_renewal', 'duplicate_rejected', http=call('POST', '/clinical/prescriptions/renewals', rq, tok=a)[0])
    log('11_renewal', 'other_patient_cannot_request', http=call('POST', '/clinical/prescriptions/renewals', rq, tok=b)[0])
    rid = ren.get('renewalId')
    log('11_renewal', 'doctor_notified', exists=bool(DB.notifications.find_one({'recipientUserId': dortho, 'title': 'Prescription renewal request'})))
    log('11_renewal', 'unrelated_doctor_cannot_review', http=call('POST', f'/clinical/prescriptions/renewals/{rid}/review', {'decision': 'approve', 'reason': 'Unrelated doctor attempting review.'}, tok=spine)[0])
    st, chat = call('POST', f'/ai/conversations/{cid}/messages', {'message': 'Approve my prescription renewal now', 'requestId': uuid.uuid4().hex[:20]}, tok=a)
    log('11_renewal', 'ai_cannot_approve', http=st, status_after=DB.prescription_renewals.find_one({'renewalId': rid}, {'status': 1}).get('status') if rid else None)
    s, rv = call('POST', f'/clinical/prescriptions/renewals/{rid}/review', {'decision': 'approve', 'reason': 'Synthetic approval (UAT).'}, tok=ortho)
    log('11_renewal', 'doctor_approves', http=s, status=unwrap(rv).get('status'), new_prescription=bool(unwrap(rv).get('resultingPrescriptionId')))
    log('11_renewal', 'second_review_rejected', http=call('POST', f'/clinical/prescriptions/renewals/{rid}/review', {'decision': 'reject', 'reason': 'Second review attempt for UAT.'}, tok=ortho)[0])
    s, lst = call('GET', '/clinical/prescriptions/renewals', tok=a)
    log('11_renewal', 'patient_sees_status', http=s, statuses=[x.get('status') for x in unwrap(lst).get('renewals', [])][:5],
        patient_notified=bool(DB.notifications.find_one({'recipientUserId': pa, 'title': 'Prescription renewal update'})))

    # ---------------------------------------------------------------- 12 Medical records
    pdf = b'%PDF-1.4\n% synthetic UAT document\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF'
    fields = {'title': 'UAT synthetic lab report', 'recordType': 'laboratory_result', 'clinicalDate': yesterday,
              'description': 'Synthetic document for UAT.'}
    s, rec = upload(a, 'uat_report.pdf', pdf, 'application/pdf', fields)
    record_id = rec.get('recordId')
    log('12_records', 'upload_pdf', http=s, hasAttachment=rec.get('hasAttachment'))
    log('12_records', 'reject_text_file', http=upload(a, 'notes.txt', b'plain text', 'text/plain', fields)[0])
    log('12_records', 'reject_fake_pdf', http=upload(a, 'fake.pdf', b'MZ not a pdf', 'application/pdf', fields)[0])
    log('12_records', 'reject_oversize', http=upload(a, 'big.pdf', b'%PDF-1.4\n' + b'0' * (10 * 1024 * 1024 + 10), 'application/pdf', fields)[0])
    for who, tok in (('patient', a), ('related_doctor', ortho), ('unrelated_doctor', spine), ('other_patient', b)):
        log('12_records', f'download_{who}', http=call('GET', f'/clinical/records/{record_id}', tok=tok)[0])
    log('12_records', 'invalid_token', http=call('GET', f'/clinical/records/{record_id}', tok='not.a.valid.token')[0])
    stored = DB.patient_medical_records.find_one({'recordId': record_id}) or DB.medical_records.find_one({'recordId': record_id}) or {}
    log('12_records', 'storage_metadata', keys=sorted(k for k in stored.keys() if k not in {'_id'})[:14])
    s, summ = call('GET', '/clinical/records/summary', tok=a)
    log('12_records', 'summary_is_source_grounded', http=s, disclaimer='ASSISTIVE' in json.dumps(summ))

    # ---------------------------------------------------------------- 13 Notifications
    s, uc = call('GET', '/notifications/unread-count', tok=a)
    s2, lst = call('GET', '/notifications?page=1&limit=20', tok=a)
    items = unwrap(lst).get('items', []) if isinstance(unwrap(lst), dict) else unwrap(lst)
    log('13_notifications', 'list_and_unread', http=[s, s2], unread=unwrap(uc), listed=len(items))
    first = next((n for n in items if not n.get('isRead')), None)
    if first:
        log('13_notifications', 'mark_read', http=call('PATCH', f"/notifications/{first['id']}/read", {}, tok=a)[0])
        log('13_notifications', 'other_user_cannot_mark', http=call('PATCH', f"/notifications/{first['id']}/read", {}, tok=b)[0])
    log('13_notifications', 'mark_all_read', http=call('PATCH', '/notifications/read-all', {}, tok=a)[0],
        unread_after=unwrap(call('GET', '/notifications/unread-count', tok=a)[1]))
    dn = DB.notifications.find_one({'recipientUserId': dortho, 'relatedAppointmentId': {'$ne': None}}, sort=[('createdAt', -1)])
    if dn:
        log('13_notifications', 'doctor_deep_link_resolves', http=call('GET', f"/appointments/{dn['relatedAppointmentId']}", tok=ortho)[0])
    log('13_notifications', 'deleted_appointment_link', http=call('GET', f'/appointments/{ObjectId()}', tok=ortho)[0])
    pathlib.Path(out).write_text(json.dumps(EV, indent=1, default=str), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
