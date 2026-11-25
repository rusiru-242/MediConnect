# Phase 02 — Patient Care Verification Matrix

2026-11-25 · Live runs on the UAT backend `127.0.0.1:8001` (`mediconnect_uat`). The backend's own background worker executed the reminders (60-second interval). Script: `patient_care_uat.py`; evidence: `evidence/patient-care-components-uat.json` (71 steps).

**Data used:**
- A synthetic COMPLETED visit between P02 Patient A and Dr. P02 Ortho, inserted as a fixture so a genuine care relationship exists.
- Dr. P02 Spine, who has no active relationship with patient A.

**Delivery channels in UAT:** FCM, SMTP and SMS are not configured. In-app delivery is real; push is truthfully recorded as `unavailable`, and email and SMS as `skipped`.

**Method labels:**
- **UAT API:** live HTTP plus the real worker.
- **Local API:** TestClient against real MongoDB.
- **Unit:** function-level test.
- **Emulator:** the Android emulator.
- **Mocked:** external channels mocked.

## 1. Test matrix

| Test ID | Agent | Scenario | Expected | Actual | Method | Status | Evidence |
|---|---|---|---|---|---|---|---|
| C05-01 | Medication Reminder | Doctor signs prescription; patient tries to approve the schedule | Patient 403; other doctor denied | 403; 404 | UAT API | PASS | care JSON `05_*` |
| C05-02 | Medication Reminder | Doctor approves the schedule (Colombo time); repeat approval | One schedule, same ID | Same ID | UAT API | PASS | ″ |
| C05-03 | Medication Reminder | Worker executes the due dose | In-app stored; push truthfully `unavailable`; email and SMS skipped; due time in Asia/Colombo | Exactly that; due 15:46 +05:30 | UAT API (real worker) | PASS | ″ |
| C05-04 | Medication Reminder | Notification privacy | No medicine name in the notification text | None | UAT API | PASS | ″ |
| C05-05 | Medication Reminder | Snooze and Taken, each sent twice; other patient acts | Idempotent; cross-patient 404 | 200/200 ×2; 404; audit 2 entries | UAT API | PASS | ″ |
| C05-06 | Medication Reminder | Doctor sees patient-reported adherence | Source `patient_reported` | Yes | UAT API | PASS | ″ |
| C05-07 | Medication Reminder | "Increase my dose to 3 tablets" in the AI chat | No change to the prescription | Unchanged (the reply is a generic "could not locate" message; a clearer "only your doctor can change your dose" reply is a proposed improvement) | UAT API | PASS (wording improvement noted) | ″ |
| C05-08 | Medication Reminder | Missed-dose history, adherence, modification, cancellation; schedule change after a prescription amendment returns 410 | As designed | Existing suites pass; doctor removal 200 live | Local API + UAT | PASS | `test_medication_reminders.py`, `test_phase3_care.py` |
| C06-01 | Care Plan | Patient creates; doctor creates (VIDEO rejected) | 403; 422; 201 ACTIVE | As expected | UAT API | PASS | care JSON `06_*` |
| C06-02 | Care Plan | Patient receives; other patient and unrelated doctor read | Visible; 403; 403 | As expected | UAT API | PASS | ″ |
| C06-03 | Care Plan | Patient completes a task; other patient tries | Completed; 403 | As expected | UAT API | PASS | ″ |
| C06-04 | Care Plan | Progress | Shown from task completion | Computed in the app from `tasks` (`progressPercentage`); the API has no progress field | Code + widget tests | PASS (client-side) | `patient_care_plans_test.dart` |
| C06-05 | Care Plan | Doctor update; patient update | Version 2; 403 | As expected | UAT API | PASS | ″ |
| C06-06 | Care Plan | AI reads the real care tasks | Lists the real task, in Colombo time | "25 Nov 15:58 · UAT fasting blood test. Times are in Asia/Colombo." | UAT API | PASS | ″ |
| C07-01 | Appointment Reminder | Confirmed visit: the 2-hour reminder becomes due | Patient receives in-app; correct recipient | Processed; in-app stored | UAT API (real worker) | PASS | care JSON `07_*` |
| C07-02 | Appointment Reminder | Cancel the visit | No pending reminders | 0 pending | UAT API | PASS | ″ |
| C07-03 | Appointment Reminder | Reschedule invalidates old reminders; new version is scheduled | Old cancelled, new processed | Pass | Local API (real scheduler) | PASS | `test_phase3_care.py`, `test_notifications.py` |
| C07-04 | Appointment Reminder | Four concurrent workers, then a later run (restart) | One reminder, one push, one notification | Exactly one each | Local API (real scheduler, 5 runs) | PASS | `test_scheduler_concurrent_workers_*` |
| C07-05 | Appointment Reminder | Deep link from a notification opens the appointment | Detail opens (BUG-060) | Patient and doctor screens open | Emulator | PASS | `bug060-*.png` |
| C08-01 | Follow-up Care | Follow-up date on the plan; doctor follow-up list | Listed | Listed | UAT API | PASS | care JSON `08_*` |
| C08-02 | Follow-up Care | Follow-up booking (link appointment); overdue marking; DUE/1D/7D reminders | As designed | Existing suites pass | Local API | PASS | `test_care_plans.py` |
| C08-03 | Follow-up Care | Doctor cancels the plan | CANCELLED; reminders dropped | CANCELLED | UAT API | PASS | ″ |
| C08-04 | Follow-up Care | AI-generated follow-up suggestions require clinician review | Only doctors create plans | Patient creation 403; no AI path creates plans | UAT API + code | PASS | ″ |
| C09-01 | Medical Test Reminder | Doctor-assigned test task: the worker delivers the reminder | Processed; in-app | Processed; in-app stored | UAT API (real worker) | PASS | care JSON `09_*` |
| C09-02 | Medical Test Reminder | Care Agenda shows the test with its date | Listed | "UAT fasting blood test" | UAT API | PASS | ″ |
| C09-03 | Medical Test Reminder | No invented results or interpretation | None | None produced | Code review | PASS | — |
| C10-01 | Health Tracking | Invalid blood pressure (110/120), invalid temperature (98.6 °C) | 422 | 422 ×2 | UAT API | PASS | care JSON `10_*` |
| C10-02 | Health Tracking | Crisis 195/125 via Health Tracking **and** via Care Agenda | Alert in both | Alert in both (Care Agenda fixed, P02-N09) | UAT API | PASS | ″ |
| C10-03 | Health Tracking | Units and provenance | mmHg, mg/dL, kg; `patient_reported` | Yes | UAT API | PASS | ″ |
| C10-04 | Health Tracking | Trends; other patient's list | Own data only | Trends returned; patient B sees 0 | UAT API | PASS | ″ |
| C10-05 | Health Tracking | Doctor trends: related vs unrelated | 200 / 403 | 200 / 403 (was 200 / **200** before P02-N10) | UAT API | PASS | ″ |
| C10-06 | Health Tracking | Truthful dashboard (no fabricated vitals) | Phase 01 behaviour kept | Phase 01 tests pass | Widget | PASS | `phase01_patient_ui_test.dart` |
| C11-01 | Prescription Renewal | Request; duplicate; other patient | 201 requested; 409; 404 | As expected | UAT API | PASS | care JSON `11_*` |
| C11-02 | Prescription Renewal | Prescriber notified | In-app notification | Yes (was missing, P02-N12) | UAT API | PASS | ″ |
| C11-03 | Prescription Renewal | Unrelated doctor reviews; AI asked to approve | 403; status unchanged | 403; still `requested` | UAT API | PASS | ″ |
| C11-04 | Prescription Renewal | Prescriber approves; second review; patient view | Approved + new prescription; 400; patient notified | As expected | UAT API | PASS | ″ |
| C11-05 | Prescription Renewal | Three concurrent approvals | One approval, one new prescription | Exactly one | Local API | PASS | `test_renewal_*` |
| C12-01 | Medical Records | Upload a synthetic PDF; text file; fake PDF; file over 10 MB | 201; 400; 400; 400 | As expected | UAT API | PASS | care JSON `12_*` |
| C12-02 | Medical Records | Access: patient, related doctor, unrelated doctor, other patient, invalid token | 200, 200, 403, 403, 401 | As expected (unrelated doctor was **200** before P02-N10) | UAT API | PASS | ″ |
| C12-03 | Medical Records | Metadata and audit; source-grounded summary | Audit log present; disclaimer | Yes | UAT API | PASS | ″ |
| C12-04 | Medical Records | Secure storage location and encryption at rest | Access-controlled storage | Files are written as plain files to `backend/uploads/medical_documents` (git-ignored) and served only through authorised endpoints. **No encryption at rest** (Phase 05 security item) | Code review | PARTIAL | `patient_medical_record_service.py:69,153` |
| C12-05 | Medical Records | No sensitive data in logs | No record titles, medicine names, emails, tokens or keys | 0 matches in the backend log | UAT log scan | PASS | — |
| C12-06 | Medical Records | No external AI for records | No external call | Deterministic summary; providers disabled | Code + config | PASS | — |
| C13-01 | Notifications | List; unread count; mark read; other user marks; mark all | 200; count; 200; 403; 0 unread | As expected | UAT API | PASS | care JSON `13_*` |
| C13-02 | Notifications | Doctor deep link; deleted appointment link | 200; 404 | 200; 404 | UAT API | PASS | ″ |
| C13-03 | Notifications | Duplicate prevention | Idempotency keys | One notification per event | UAT + Local API | PASS | Stripe S1; scheduler test |
| C13-04 | Notifications | Truthful channel status | Email disabled → "not sent"; SMS without consent → "not requested"; push unavailable | Backend: `failed: provider_not_configured`, `skipped`, `unavailable`; app labels updated | UAT + widget | PASS | — |
| C13-05 | Notifications | Actual FCM push delivery | — | Not configured in UAT | — | **BLOCKED** | — |
| C13-06 | Notifications | Actual email and SMS delivery | — | SMTP disabled; Twilio not configured | — | **BLOCKED** | — |

## 2. All 13 patient components

| # | Component | Implemented | Actually tested (Phase 01 + 02) | Partially verified | Failed | Blocked | Not run | Clinical approval |
|---|---|---|---|---|---|---|---|---|
| 1 | AI Doctor Booking Agent | Yes | Phase 01 probe (35) + Phase 02 booking, alternatives, Stripe, emulator | — | — | LLM provider live (B4) | — | No |
| 2 | AI Health Assistant | Yes | Phase 01 (UAT API, emulator); Phase 02 probe re-run (0 differences) | — | — | LLM provider live | — | **Pending** (B1) |
| 3 | AI Doctor Recommendation | Yes | Phase 01 + Phase 02 BUG-053 live field check | — | — | — | — | No |
| 4 | AI Medicine Image Recognition | Yes | Mocked pipeline only (Phase 01) | Mocked | — | Live Vision (privacy approval) | Live run | Pharmacist pending (B2) |
| 5 | Medication Reminder | Yes | UAT API with real worker; Local API | Push delivery | — | FCM | — | Dose wording pending |
| 6 | Care Plan | Yes | UAT API; Local API; widget | Progress is client-side | — | — | — | Clinician-authored content only |
| 7 | Appointment Reminder | Yes | UAT real worker; concurrent workers; deep link on device | Push and email | — | FCM, SMTP | — | — |
| 8 | Follow-up Care | Yes | UAT API; Local API | — | — | — | — | — |
| 9 | Medical Test Reminder | Yes | UAT real worker; agenda | Push | — | FCM | — | — |
| 10 | Personal Health Tracking | Yes | UAT API (both endpoints); widget | Two separate stores (owner decision) | — | — | — | **Thresholds pending** (B1) |
| 11 | Prescription Renewal | Yes | UAT API; concurrency | — | — | — | — | Clinician process |
| 12 | Medical Records | Yes | UAT API (upload, access control, logs) | Encryption at rest | — | — | — | — |
| 13 | Notifications | Yes | UAT API; device deep links | Channel delivery | — | FCM, email, SMS | — | — |

**Reading the table:** "Implemented" means the code exists and works locally. No component is clinically approved. "Blocked" items depend on external configuration or authorisation that is not present in UAT.
