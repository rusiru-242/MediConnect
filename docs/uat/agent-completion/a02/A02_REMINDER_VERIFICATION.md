# A02 — Reminder Verification (Agents 05, 07, 08, 09)

For: the project owner, clinical reviewers and engineers. 2026-11-26, UAT backend 127.0.0.1:8001 (`mediconnect_uat`, local MongoDB) with its real 60-second worker.

## Terms used in the tables

| Term | Meaning |
|---|---|
| **Live** | Real HTTP calls to the UAT backend. The backend's own worker executed the reminder; MongoDB was read to confirm persistence (`evidence/a02_live_uat.json`). |
| **Automated** | pytest on a dedicated local `*_test` database, with an injected clock where a reminder would otherwise need hours. |
| **Emulator** | The Flutter debug APK on emulator-5554, Android API 37. |

Push, e-mail and SMS were never delivered; every reminder recorded `push: disabled` (Firebase not configured) and `email`/`sms: skipped` (no consent).

## How reminders are created (no AI)

| Agent | Source of the schedule | Who can change it | AI role |
|---|---|---|---|
| 05 Medication | A clinician-approved schedule (`PUT /care-automation/prescriptions/{id}/schedule`, `confirm: true`), with the exact times chosen by the prescribing doctor. Validated against the prescription: dose count = frequency, dates ≤ duration. Re-validated at every delivery against the prescription revision. Patient-created reminders (legacy screen) are now limited to prescriptions with a fixed daily frequency and duration (A02-BUG-011) | Prescribing doctor only (re-approve / discontinue); the patient records taken, skipped or snooze | Read-only answers; a dose-change request is refused with "the doctor who prescribed it decides" |
| 07 Appointment | Product rule in `care_scheduler.occurrences`: **24 h and 2 h before** a `CONFIRMED` appointment, Asia/Colombo, patient preferences `reminder24h` / `reminder2h` | Rescheduling creates a new version; cancellation invalidates | None |
| 08 Follow-up | Doctor-authored care plan: **7 days, 1 day and the due day, at 09:00** Asia/Colombo; also the doctor-approved reminder batch (agent 19) | Plan author only (other doctors 403) | None; follow-up proposals in the doctor assistant only suggest a date for the doctor to save |
| 09 Medical test | Care-plan task `kind: test` with the clinician's due time, instructions and location (`remindMinutesBefore`, default 0) | Plan author only | None; no result or interpretation is ever generated |

## Agent 05 — Medication reminders

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A02-M01 | Clinician-approved schedule | Live: sign 201, approve 200. Unrelated doctor 404, patient 403, pending doctor 403, 1 time for a twice-daily medicine 422, 10 days for a 5-day course 422. PRN medicine: doctor schedule 422, patient reminder **422 (was 201 before A02)**, patient 60-day end date 422 | **PASS** |
| A02-M02 | Correct medicine and dosage | Live: stored name, strength, dose, frequency and duration equal the prescription; times as approved; `approvedBy` = prescriber. The patient-facing reminder text is private ("It's time for your scheduled medication. Open MediConnect for details."); the details appear only inside the app | **PASS** |
| A02-M03 | Correct reminder time | Live: approved 19:32 Asia/Colombo → event `scheduledAt` 19:32, in-app stored **47 s** later (one worker cycle) | **PASS** |
| A02-M04 | Taken | Live: 200; the same request id repeated → still one audit entry; patient B → 404 | **PASS** |
| A02-M05 | Snooze | Live: snooze 5 min → the same occurrence re-delivered once (2 in-app notifications, distinct keys) 6.0 min later | **PASS** |
| A02-M06 | Skip and missed history | Live: skip 200. The prescribing doctor's activity shows taken and skipped (`patient_reported`); an unrelated doctor gets 404. The assistant ("Show my missed medicine reminders.") listed this run's un-acted once-daily dose and not the taken or skipped ones; it says "no action recorded", never "missed" as a fact | **PASS** (see note 1) |
| A02-M07 | Schedule update | Live: re-approval with new times → `scheduleVersion` 2; today's agenda shows only the new times 21:10 and 21:40 | **PASS** |
| A02-M08 | Schedule cancellation | Live: discontinued → gone from the agenda; an unrelated doctor's discontinue → 404 | **PASS** |
| A02-M09 | App restart | Emulator: after reinstall and relaunch, the restored session re-planned device reminders from the server (A02-BUG-018); alarms present. Server-side reminders do not depend on the app | **PASS (emulator)** |
| A02-M10 | Actual push receipt | Firebase not configured; no push sent. Device-local reminder shown on the emulator instead (19:48 and 19:49, privacy text), which is not push | **BLOCKED** (push); device-local PASS |

**Extra checks:**
- Multiple workers and a worker restart: see `A02_SCHEDULER_VERIFICATION.md`.
- Prescription change → reminder detail 410 and no delivery (Phase 3 test kept).
- **Duplicate prevention:** 0 duplicates across the live run.

## Agent 07 — Appointment reminders

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A02-A01 | Confirmed appointment reminder | Live: a booked and paid (Stripe test mode) 22:00 appointment produced the 2-hour reminder for patient A only (in-app stored; push `disabled`). Doctor and hospital are shown in the appointment detail the reminder opens (emulator `a02_11`); the reminder text itself is private | **PASS** |
| A02-A02 | Timezone correctness | Live: `scheduledAt` = 22:00 Asia/Colombo (the slot), `dueAt` exactly 2.0 h earlier. Automated P05 `test_s06h`: a reminder that falls on a different Colombo date | **PASS** |
| A02-A03 | Rescheduling | Live: reschedule 200 (new version). Automated P05 `test_s06g`: an already materialised old reminder is cancelled and the new one delivered once | **PASS** |
| A02-A04 | Cancellation | Live: the rescheduled-then-cancelled appointment produced **no** reminder event at all. Automated P05 `test_s06f` | **PASS** |
| A02-A05 | Unpaid appointment exclusion | Live: patient B's unpaid reservation (`PENDING`) is not in B's agenda and produces no reminder | **PASS** |
| A02-A06 | Notification navigation | Live: the reminder's event detail returns the booked `appointmentId`; patient B 404. Emulator: notification → exact care occurrence (`a02_09`) and → current appointment state (`a02_11`). BUG-060 doctor route kept (widget tests) | **PASS** |

## Agent 08 — Follow-up reminders

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A02-F01 | Doctor-approved follow-up | Live: plan on a completed visit 201; the patient is notified with generic text; patient B cannot read the plan (403) | **PASS** |
| A02-F02 | Scheduled delivery | Automated, real scheduler with an injected clock (`test_f02_follow_up_reminders_7d_1d_due_at_0900_colombo_once_each`): nothing at 08:59, delivered at 09:01 Colombo, once each; a moved date makes the old due-day reminder obsolete. Live: the plan's task reminder (A02-T03) and the doctor-approved batch were delivered in-app. The 09:00 follow-up reminders were not observed live (the run was in the evening) | **PARTIAL** (live 09:00 delivery not observed) |
| A02-F03 | Date update | Live: follow-up date and test date changed → 200; one "Care plan updated" notice; an unchanged re-save adds none (A02-BUG-015); unrelated doctor 403 | **PASS** |
| A02-F04 | Cancellation and completion | Live: test task completed (200); plan closed → its tasks leave the agenda and one "Care plan closed" notice is stored | **PASS** (see note 2) |

## Agent 09 — Medical test reminders

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A02-T01 | Doctor-assigned test | Live: a `test` task appears in patient A's agenda only | **PASS** |
| A02-T02 | Correct instructions | Live: instructions and location shown **verbatim** as the doctor entered them (synthetic text). No result or interpretation is generated anywhere | **PASS** |
| A02-T03 | Reminder execution | Live: delivered in-app at the due time; private body ("You have an upcoming care task") | **PASS** |
| A02-T04 | Completion and cancellation | Live: completed 200; date change moved the second test to the new time; plan closure removed it | **PASS** |

## Notes on the live run

1. **Two checks first recorded FAIL and were re-evaluated (both were defects in my script, not in the product):**
   - **A02-M06b:** the reply also listed un-acted doses from an earlier, aborted run (`2342f2`). That is correct behaviour; the check wrongly rejected any "Synthomox" in the reply instead of this run's taken and skipped medicine.
   - **A02-F04:** the "remaining" filter matched this run's still-active *medication schedule* (its name contains the run id) instead of only the plan's tasks.

   Both checks are corrected in `a02_live_uat.py`. The JSON keeps the original output with a `reevaluated` note.
2. **Leftover data:** the aborted first run left two synthetic schedules for patient A (`…2342f2`). They are synthetic and expire with their 5-day course.
