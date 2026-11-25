"""Phase 03 reproduction of doctor-side defects against the local UAT backend (127.0.0.1:8001 only).

Run from backend/:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\phase-03\\repro_doctor_defects.py OUT.json

Run once BEFORE the fixes (evidence of the defect) and again AFTER (evidence of the fix). Synthetic Phase 03
fixtures only (uat.p03.*). Stripe TEST mode only (refuses a non sk_test_ key). No secrets are printed or written:
PaymentIntent ids are masked and the UAT password is read from backend/uat.env by p03api.
"""
import json
import os
import sys
import uuid
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p03api import call, colombo_now, env_value, free_slots, book, login, unwrap  # noqa: E402

import stripe  # noqa: E402
from bson import ObjectId  # noqa: E402
from pymongo import MongoClient  # noqa: E402

KEY = env_value('STRIPE_SECRET_KEY')
assert KEY.startswith('sk_test_'), 'Refusing: not a Stripe test key'
stripe.api_key = KEY
DB = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000)['mediconnect_uat']
mask = lambda v: (v[:3] + '…' + v[-6:]) if isinstance(v, str) and len(v) > 12 else v  # noqa: E731
OUT = {'backend': '127.0.0.1:8001', 'database': 'mediconnect_uat', 'stripe': 'test_mode', 'steps': []}


def step(name, **data):
    OUT['steps'].append({'step': name, **data})
    print(name, json.dumps(data, default=str)[:400])


def pay(tok, appt_id):
    s, d = call('POST', '/payments/create-intent', {'appointmentId': appt_id, 'amount': 1}, tok=tok)
    pi = unwrap(d)
    intent_id = DB.payments.find_one({'_id': ObjectId(pi['paymentId'])})['stripePaymentIntentId']
    stripe.PaymentIntent.confirm(intent_id, payment_method='pm_card_visa', return_url='https://example.invalid/r')
    call('GET', f"/payments/{pi['paymentId']}/status", tok=tok)
    return pi['paymentId'], intent_id


def open_intent(tok, appt_id):
    s, d = call('POST', '/payments/create-intent', {'appointmentId': appt_id, 'amount': 1}, tok=tok)
    pi = unwrap(d)
    return DB.payments.find_one({'_id': ObjectId(pi['paymentId'])})['stripePaymentIntentId']


OUT_RUN_SLOT = __import__('time').time() // 60


def main(out_path):
    pa, pb = login('uat.p03.patienta'), login('uat.p03.patientb')
    alpha, beta = login('uat.p03.doctor.alpha'), login('uat.p03.doctor.beta')
    pa_id = str(DB.users.find_one({'email': 'uat.p03.patienta@uat.mediconnect.lk'})['_id'])
    pb_id = str(DB.users.find_one({'email': 'uat.p03.patientb@uat.mediconnect.lk'})['_id'])
    # Use a day 3-9 days ahead so runs before and after the fixes use different free slots.
    run_offset = 3 + (int(colombo_now().strftime('%H')) % 7)
    day = (colombo_now().date() + timedelta(days=run_offset)).isoformat()
    slots = free_slots(pa, 'UAT-P03-ALPHA', day)
    step('fixture_slots', date=day, count=len(slots))
    # R1 uses a doctor with no other relationship with patient B. The BEFORE run used Alpha; its defect left a
    # CONFIRMED (unpaid) appointment between Alpha and B, so AFTER runs use Beta (R1_DOCTOR=beta).
    r1_key, r1_tok = (('UAT-P03-BETA', beta) if os.environ.get('R1_DOCTOR') == 'beta'
                                 else ('UAT-P03-ALPHA', alpha))
    step('R1_doctor', doctor=r1_key)

    # R1: consultation start on an UNPAID reservation (payment pending) -> CONFIRMED without payment?
    s, unpaid = book(pb, r1_key, day, free_slots(pb, r1_key, day)[0])
    before = DB.appointments.find_one({'_id': ObjectId(unpaid['id'])}, {'status': 1, 'paymentStatus': 1})
    st, sess = call('POST', f"/doctor/consultations/{unpaid['id']}/start", {}, tok=r1_tok)
    after = DB.appointments.find_one({'_id': ObjectId(unpaid['id'])}, {'status': 1, 'paymentStatus': 1})
    step('R1_start_consultation_on_unpaid_reservation', book_http=s, before=before.get('status'),
         payment=before.get('paymentStatus'), start_http=st, after=after.get('status'),
         payment_after=after.get('paymentStatus'))
    # R1b: does that consultation session grant record access after the patient releases the hold?
    rel = call('POST', f"/appointments/{unpaid['id']}/release-hold", {}, tok=pb)[0]
    rec = call('GET', f'/clinical/records?patientId={pb_id}', tok=r1_tok)[0]
    trend = call('GET', f'/clinical/measurements/trends?patientId={pb_id}', tok=r1_tok)[0]
    step('R1b_record_access_after_released_reservation', release_http=rel,
         status_after_release=DB.appointments.find_one({'_id': ObjectId(unpaid['id'])})['status'],
         records_http=rec, trends_http=trend, expected='403 / 403')

    # R2: doctor cancels a PAID appointment -> refund request? (existing policy: 100% on doctor cancellation)
    s, paid = book(pa, 'UAT-P03-ALPHA', day, slots[1])
    pay(pa, paid['id'])
    pstate = DB.appointments.find_one({'_id': ObjectId(paid['id'])}, {'status': 1, 'paymentStatus': 1})
    dc = call('POST', f"/doctors/me/appointments/{paid['id']}/cancel", {'reason': 'UAT doctor unavailable'}, tok=alpha)[0]
    refund = DB.refund_requests.find_one({'appointmentId': paid['id']})
    step('R2_doctor_cancels_paid_booking', before=pstate, cancel_http=dc,
         refund_request_opened=bool(refund), refund_amount=(refund or {}).get('policyEligibility', {}).get('eligibleAmount'),
         payment_after=DB.appointments.find_one({'_id': ObjectId(paid['id'])})['paymentStatus'])

    # R3: doctor cancels an UNPAID reservation that has an open Stripe PaymentIntent
    s, held = book(pb, 'UAT-P03-ALPHA', day, slots[2])
    intent_id = open_intent(pb, held['id'])
    dc = call('POST', f"/doctors/me/appointments/{held['id']}/cancel", {'reason': 'UAT'}, tok=alpha)[0]
    step('R3_doctor_cancels_unpaid_reservation_with_open_intent', cancel_http=dc,
         appointment=DB.appointments.find_one({'_id': ObjectId(held['id'])})['status'],
         stripe_intent_status=stripe.PaymentIntent.retrieve(intent_id).status, intent=mask(intent_id),
         expected_intent='canceled')

    # A confirmed, paid visit between Alpha and patient A (care relationship) for the clinical checks.
    s, visit = book(pa, 'UAT-P03-ALPHA', day, slots[3])
    pay(pa, visit['id'])
    step('fixture_confirmed_paid_visit', status=DB.appointments.find_one({'_id': ObjectId(visit['id'])})['status'])

    # R4: signing a prescription creates ACTIVE reminders with times that were never prescribed?
    st, rx = call('POST', '/clinical/prescriptions/sign', {'patientUserId': pa_id, 'appointmentId': visit['id'],
        'medicationItems': [{'medicationName': 'UAT Synthetic Med', 'strength': '10 mg', 'dose': '1 tablet',
                             'route': 'Oral', 'frequency': 'Once at bedtime', 'duration': '30 days', 'quantity': '30'}]},
        tok=alpha)
    rx = unwrap(rx)
    rem = DB.medication_reminders.find_one({'prescriptionId': rx.get('prescriptionId')}) or {}
    pr = call('GET', '/medication-reminders', tok=pa)
    rxdoc = DB.prescriptions.find_one({'prescriptionId': rx.get('prescriptionId')}) or {}
    step('R4_sign_prescription_auto_reminders', sign_http=st, prescribed_frequency='Once at bedtime',
         prescribed_duration='30 days', reminder_status=rem.get('status'), reminder_times=rem.get('scheduledTimes'),
         reminder_days=((rem['endDate'] - rem['startDate']).days if rem.get('endDate') else None),
         patient_list_http=pr[0],
         medical_record_link_exists=bool(rxdoc.get('medicalRecordId') and ObjectId.is_valid(rxdoc['medicalRecordId'])
                                         and DB.medical_records.find_one({'_id': ObjectId(rxdoc['medicalRecordId'])})))

    # R5: AI-structured note draft from raw notes: are findings invented, and can it be signed unedited?
    st, note = call('POST', '/clinical/notes/draft', {'patientUserId': pa_id, 'appointmentId': visit['id'],
                                                      'rawNotes': 'Patient reports mild headache for two days.'}, tok=alpha)
    note = unwrap(note)
    content = note.get('content') or {}
    sg = call('POST', f"/clinical/notes/{note.get('noteId')}/sign", {'confirmSign': True}, tok=alpha)
    signed = DB.clinical_notes.find_one({'noteId': note.get('noteId')}) or {}
    step('R5_ai_note_draft_fabrication', draft_http=st, raw='Patient reports mild headache for two days.',
         examinationFindings=content.get('examinationFindings'), assessment=content.get('assessment'),
         plan=content.get('plan'), sign_unedited_http=sg[0], status_after=signed.get('status'),
         slmc=signed.get('slmcRegistrationNumber'))

    # R6: Beta (who also has a confirmed visit with patient A) reads patient A's notes: sees Alpha's DRAFT?
    s, bvisit = book(pa, 'UAT-P03-BETA', day, free_slots(pa, 'UAT-P03-BETA', day)[0])
    pay(pa, bvisit['id'])
    st, draft2 = call('POST', '/clinical/notes/draft', {'patientUserId': pa_id, 'rawNotes': 'Alpha private draft'}, tok=alpha)
    st, lst = call('GET', f'/clinical/notes?patientId={pa_id}', tok=beta)
    notes = unwrap(lst).get('notes', []) if isinstance(unwrap(lst), dict) else []
    step('R6_other_doctor_sees_unsigned_drafts', http=st,
         other_doctor_drafts_visible=sum(1 for n in notes if n.get('doctorUserId') != str(DB.users.find_one(
             {'email': 'uat.p03.doctor.beta@uat.mediconnect.lk'})['_id']) and str(n.get('status')).upper() in ('DRAFT', 'UNDER_REVIEW')))

    # R7: consultation record on a FUTURE confirmed visit completes it before its time?
    st, mr = call('POST', '/medical-records', {'appointmentId': visit['id'], 'clinicalNotes': 'UAT', 'assessment': 'UAT',
                                               'treatmentPlan': 'UAT'}, tok=alpha)
    step('R7_record_on_future_visit', http=st, visit_date=day,
         status_after=DB.appointments.find_one({'_id': ObjectId(visit['id'])})['status'])

    # R7b/R8/R9 need a visit that has already started. Bookings cannot be made in the past, so a labelled synthetic
    # fixture is inserted: a CONFIRMED visit yesterday between Alpha and patient A (p03Fixture=True, no payment).
    alpha_id = str(DB.users.find_one({'email': 'uat.p03.doctor.alpha@uat.mediconnect.lk'})['_id'])
    yday = (colombo_now().date() - timedelta(days=1)).isoformat()
    past_id = DB.appointments.insert_one({'patientUserId': pa_id, 'doctorUserId': alpha_id,
        'doctorProfileId': str(DB.doctor_profiles.find_one({'userId': alpha_id})['_id']),
        'appointmentDate': yday, 'startTime': f"{6 + int(OUT_RUN_SLOT) % 6:02d}:00", 'endTime': '06:30',
        'status': 'CONFIRMED', 'paymentStatus': 'NOT_REQUIRED', 'consultationFee': 2000.0, 'appointmentVersion': 1,
        'p03Fixture': True, 'createdAt': colombo_now(), 'updatedAt': colombo_now()}).inserted_id
    st, mr = call('POST', '/medical-records', {'appointmentId': str(past_id), 'clinicalNotes': 'UAT', 'assessment': 'UAT',
                                               'treatmentPlan': 'UAT'}, tok=alpha)
    step('R7b_record_on_started_visit', http=st, status_after=DB.appointments.find_one({'_id': past_id})['status'])
    visit = {'id': str(past_id)}

    # R8: /prescriptions with an appointmentId that does not match the record
    mr = unwrap(mr)
    other = DB.appointments.find_one({'doctorUserId': {'$ne': str(DB.users.find_one(
        {'email': 'uat.p03.doctor.alpha@uat.mediconnect.lk'})['_id'])}}, {'_id': 1})
    st, rx2 = call('POST', '/prescriptions', {'medicalRecordId': mr.get('id') or mr.get('recordId') or 'x',
                                              'appointmentId': str(other['_id']),
                                              'medicationItems': [{'medicationName': 'UAT Med', 'strength': '5 mg',
                                                                   'dose': '1', 'frequency': 'Once daily',
                                                                   'duration': '5 days', 'quantity': '5'}]}, tok=alpha)
    step('R8_prescription_linked_to_unrelated_appointment', http=st,
         stored_appointment_is_other_doctors=(unwrap(rx2).get('appointmentId') == str(other['_id'])))

    # R9: an identical prescription submitted twice (double tap)
    body = {'medicalRecordId': mr.get('id') or 'x', 'appointmentId': visit['id'],
            'medicationItems': [{'medicationName': 'UAT Twice', 'strength': '5 mg', 'dose': '1',
                                 'frequency': 'Once daily', 'duration': '5 days', 'quantity': '5'}]}
    codes = [call('POST', '/prescriptions', body, tok=alpha)[0] for _ in range(2)]
    step('R9_duplicate_prescription_submission', codes=codes,
         stored=DB.prescriptions.count_documents({'appointmentId': visit['id'], 'medicationItems.medicationName': 'UAT Twice'}))

    OUT['runId'] = uuid.uuid4().hex[:8]
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(OUT, fh, indent=2, default=str)


if __name__ == '__main__':
    main(sys.argv[1])
