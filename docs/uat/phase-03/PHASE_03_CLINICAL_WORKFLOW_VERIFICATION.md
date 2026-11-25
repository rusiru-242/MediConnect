# Phase 03 — Clinical Workflow and Cross-Role Verification

For: the project owner, clinical reviewers and reviewers. 2026-11-25.

**How it was tested:**
- **Live runs:** on the UAT backend `127.0.0.1:8001` (`mediconnect_uat`) with synthetic Phase 03 fixtures. Doctors: Dr. P03 Alpha and Dr. P03 Beta (approved), `uat.doctor.pending1` (pending), and P03 rejected and suspended accounts. Patients: P03 Patient A and B. Unrelated doctor: Dr. P02 Spine.
- **Scripts and evidence:** `doctor_workflow_uat.py` (45 steps, final run all PASS) and `doctor_worker_check.py` (2 steps PASS).
- **Payments:** Stripe test mode only (`pm_card_visa`).
- **Background jobs:** the backend's own worker sent the reminders.

**Not clinically approved:** this report shows the software behaves as designed. It does **not** show that the clinical content, thresholds or wording are approved. Clinician and pharmacist review are still required (B1, B2).

## 1. Doctor action → patient-visible outcome

| Workflow | Doctor action | Patient-side result | Database / financial check | Status | Evidence |
|---|---|---|---|---|---|
| Appointment management | Lists today's paid visits; opens detail | — | Fee LKR 2,000 = amount paid = payment record; booking reference = appointment id; IN_PERSON | PASS | D-04a, D-04b/c |
| Unpaid request | Tries confirm, start and the generic status route | Request stays an unpaid request | 409 on all three; PENDING/UNPAID | PASS | D-04e |
| Reschedule | Moves a paid visit to another real slot | Patient sees the new date and time and a notification | Version 1→2; still one SUCCEEDED payment (no second charge) | PASS | D-04g |
| Queue | Check-in → consultation → completed | Patient sees COMPLETED | PAID unchanged; no refund created; one audit entry per request ID | PASS | D-11b, D-11c |
| Doctor cancellation | Cancels a paid visit | Patient sees CANCELLED; notification mentions the refund request | Refund request `requested`, eligible LKR 2,000 (100%, existing policy); 0 pending reminders | PASS | D-04f |
| Clinical notes | Draft from raw notes → edit → sign → amend | Patient sees the signed note | Real SLMC number; audit DRAFT_CREATED → DRAFT_EDITED → SIGNED → AMENDED; other doctor 403 ×3; patient B cannot see it | PASS | D-06a–e |
| Prescriptions | Signs for own visit | Patient sees it in My Prescriptions | Linked to the visit; **no reminder created automatically** | PASS | D-07a/b |
| Medication reminders | Approves 08:00 and 20:00 for a "Twice daily, 5 days" item | Reminder in the patient's list | A 1-time schedule is refused (422) | PASS | D-07c |
| Renewal approval | Patient requests; 3 concurrent approvals by the prescriber | Patient notified | Exactly one new prescription, copying the original item and visit link; no reminder | PASS | D-07e |
| Renewal rejection | Prescriber rejects | Patient notified | Status `rejected`; nothing issued | PASS | D-07f |
| Care plan | Creates a plan with a test task on a completed visit | Patient sees the plan and completes a task | Doctor sees 1/2 tasks (50%), the same server figure the patient gets; another patient 403; unrelated doctor cannot edit | PASS | D-08a–e |
| Medical test reminder | Test task due 3 minutes later | In-app reminder "You have an upcoming care task…" (no test name in the notification) | Event `processed`; push `unavailable` (FCM not configured); email and SMS `skipped` | PASS | D-09c |
| Follow-up reminders and cancellation | Plan follow-up date; plan cancellation | — | Phase 02 patient-care run repeated: 71 steps, no behavioural difference (follow-up listing, cancellation, reminders dropped) | PASS (regression) | `regression-p02-patient-care.json` |
| Communication | Previews tomorrow's reminder batch, approves with token + confirm | Consented patients get in-app reminders | 3 delivered `stored_in_app`, all to consented patients; no external channel claimed | PASS | D-10a–d |
| Notifications | Receives booking notifications; marks one read; opens the linked appointment | — | Another doctor cannot mark it (403); no notification about Alpha's patients reaches Beta | PASS | D-13a–d |
| Record authorization | Related doctor reads; unrelated doctor tries | — | Unrelated doctor 403 on records, summary, notes and trends; released-reservation session grants nothing (403) | PASS | D-05d; R1b after |

## 2. Clinical safety checks

| Check | Result |
|---|---|
| No invented examination findings, assessment, plan, vital signs or diagnosis in AI drafts | "Not documented. To be completed by the clinician."; signing blocked until written (P03-N09) |
| Patient-reported vs clinician-authored separated | Preparation lists `patientReportedReason` separately from clinician records; drafts keep only the doctor's own text |
| Missing allergies are not reported as "no allergies" | Summary wording fixed (P03-N14); preparation says allergies need verification |
| No invented dosage, frequency or duration | Reminder auto-creation removed (P03-N06); renewal defaults removed (P03-N08) |
| AI never prescribes, signs, renews, approves plans or alters appointments | The assistant's tools are read-only; injection test changed nothing (D-14b/c, D-14c2) |
| No AI reordering of the queue by urgency | Queue ordering is doctor position, then check-in, then scheduled time |
| Notification privacy | Care and test reminders carry no test or medicine name; doctor batch text is fixed and non-clinical |

## 3. Limitations

- **Clinical and pharmacist sign-off:** content, thresholds and wording are still pending sign-off (B1, B2).
- **Preparation view scope:** it uses only the doctor's own records, not measurements or other clinicians' signed notes (P3-B8).
- **Drug safety:** there is no drug-interaction or contraindication source (P3-B9).
- **Device testing:** the doctor flows ran on the emulator for the dashboard, follow-ups, analytics and patient release. Doctor note, prescription and renewal screens were verified through the API and widget tests, not by tapping on the device (P3-B10).
