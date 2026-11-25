# Phase 03 — Doctor UAT Report (live API, worker and emulator)

For: the project owner and independent reviewers. 2026-11-25 · branch `fix/phase-03-doctor-system-stabilization`.

## 1. Environment

**Backend:**
- UAT backend on `127.0.0.1:8001`, started with `backend/scripts/start_uat_backend.ps1 -SkipSeed`.
- `ENVIRONMENT=staging`; local MongoDB `mediconnect_uat`; `/health` reports `isolatedTestData: true`.
- Deterministic AI (providers disabled); Stripe test mode; SMTP disabled; FCM and SMS not configured.
- The backend's own background worker ran the reminders.
- Port 8000 was never used.

**Fixtures:** `backend/scripts/seed_phase03_fixtures.py`, insert-only, 70 records:
- Patients `uat.p03.patienta` and `uat.p03.patientb`.
- Approved doctors `uat.p03.doctor.alpha` (LKR 2,000) and `uat.p03.doctor.beta` (LKR 1,800), General Physician, Colombo.
- Availability today plus 14 days: 06:00–12:00 and 13:00–23:30 (synthetic extended hours with a 12:00–13:00 break).
- `uat.p03.doctor.rejected` (REJECTED) and `uat.p03.doctor.suspended` (account SUSPENDED).
- Existing `uat.doctor.pending1` (PENDING) and Dr. P02 Spine as an unrelated doctor.
- The owner's bookings and accounts were not touched.

**Automated tests:** local `mediconnect_test` only. This is now enforced by `backend/tests/conftest.py`; see the incident in the security report.

**Device:**
- Android 17 emulator (Pixel_7_Pro AVD), cold-booted.
- Debug APK with `--dart-define=API_BASE_URL=http://10.0.2.2:8001`. Final build is from `ab94ffc` (installed 22:04 +05:30); EM-01–11 ran on the `26c08b7` build.
- Every input checked that MediConnect owned window focus.

## 2. Live runs

| Run | Script | Result | Evidence |
|---|---|---|---|
| Defect reproduction, before | `repro_doctor_defects.py` | 9 defects reproduced (R1–R9); R6 confirmed with a direct check | `evidence/repro-before-fix.json` |
| Defect reproduction, after | same (`R1_DOCTOR=beta`, plus a labelled started-visit fixture) | All fixed: R1 409/PENDING, R1b 403/403, R2 refund 100%, R3 intent `canceled`, R4 no reminder, R5 "Not documented" and sign 409, R7 409, R7b 201/COMPLETED, R8 400, R9 201+409 | `evidence/repro-after-fix.json` |
| Authorization sweep, before and after | `doctor_authz_sweep.py` | 29 endpoints × 7 callers plus suspended and rejected logins. After the fix: no unauthorized access (4 flagged rows confirmed to return the caller's own data) | `evidence/authz-sweep-*.json`, `cross-patient-param-check.json` |
| Cross-role doctor UAT | `doctor_workflow_uat.py` | **45 / 45 PASS** (final run) | `evidence/doctor-workflow-uat.json`, `.log` |
| Worker delivery | `doctor_worker_check.py` | **2 / 2 PASS** (test-task reminder; approved reminder batch) | `evidence/doctor-worker-delivery.json` |
| Defect cleanup | inline | The before-run left one CONFIRMED/UNPAID appointment (caused by P03-N01); cancelled through the fixed doctor API | `evidence/n01-before-run-cleanup.json` |
| Dashboard reconciliation | inline | Screen 2 visits / LKR 4,000; database 2 COMPLETED (+2 CANCELLED), paid 4,000 | `evidence/d02c-dashboard-reconciliation.json` |

**Regression runs (Phase 01/02 scripts against the Phase 03 backend):**

| Run | Result | Evidence |
|---|---|---|
| Phase 02 Stripe test mode (36 steps) | No behavioural difference. Only the admin payment-list total grew, 7 → 29, from more test data | `regression-p02-stripe-test-mode.json` |
| Phase 02 patient care, components 05–13 (71 steps) | No behavioural difference. Changed: run times, a notification count, and the new server progress field | `regression-p02-patient-care.json` |
| Phase 01 AI probe (35 scenarios, 45 turns) | 0 differences in http, state, urgency, intent, type or category; the number of doctors shown is unchanged | `regression-p01-probe-comparison.json` |
| Flutter live API integration test | 13 / 13 on port 8001 | Command below |

```
RUN_LIVE_TESTS=true LIVE_API_BASE_URL=http://127.0.0.1:8001/api \
LIVE_API_EXISTING_EMAIL=uat.p03.patienta@uat.mediconnect.lk LIVE_API_LOGIN_EMAIL=uat.p03.patienta@uat.mediconnect.lk \
LIVE_API_LOGIN_PASSWORD=<from backend/uat.env> flutter test test/integration/live_api_test.dart
```

## 3. Emulator walkthrough

| # | Check | Result | Evidence |
|---|---|---|---|
| EM-01 | Doctor home without invented content (P03-N16) | PASS | `p03n16-doctor-home-before.png` / `-after.png` |
| EM-02 | Real "Today" figures, reconciled with the database (D-02a/c) | PASS | `d02a-doctor-home-real-data.png` |
| EM-03 | Follow-ups show server progress "1/2 tasks completed" (P03-N18) | PASS | `p03n18-doctor-followups-progress.png` |
| EM-04 | Refund-aware analytics (P03-N19) | PASS (raw field names; UX item P3-B7) | `p03n19-doctor-analytics.png` |
| EM-05 | B11 E6–E7: AI proposal Dr. P03 Beta 2026-11-30 09:30 LKR 1,800; Stripe TEST PaymentSheet inside MediConnect | PASS | `b11-e6-proposal.png`, `b11-e7-paymentsheet.png` |
| EM-06 | **B11 E8**: sheet closed → "Payment was cancelled. You have not been charged"; hold card and Release; database PENDING/PENDING | PASS | `b11-e8-sheet-closed.png` |
| EM-07 | **B11 E9**: release confirmation dialog | PASS | `b11-e9-release-dialog.png` |
| EM-08 | **B11 E10**: "released … No payment was taken"; the old "slot stays held" note is gone; CANCELLED/UNPAID; payment record CANCELLED; Stripe `canceled`; slot free for another patient; 0 active bookings | PASS | `b11-e10-released.png`, `b11-e8-e10-database-and-stripe.json` |
| EM-09 | **B11**: released booking detail shows "Not paid" (not "Payment pending") | PASS | `b11-released-detail-unpaid.png` |
| EM-10 | Login and logout (doctor and patient), keyboard, Back, chat restore after leaving the screen, app restart keeps the session | PASS | — |
| EM-11 | Flutter log: 0 exceptions, overflows or `setState` after dispose (134 lines); no port 8000 | PASS | — |
| EM-12 | Find a Doctor without invented rating, location or next slot (P03-N24) | PASS | `p03n24-find-doctor-after.png` |
| EM-13 | Renewal queue reachable from the doctor home and listing real renewals (P03-N23) | PASS | `p03n23-renewal-queue-*.png` |

**Environment events during the emulator run:**
- **Stalled install:** `flutter run` stalled after building; adb file transfer hung while shell commands worked.
- **Dialer focus:** the snapshot-restored emulator kept window focus on the system Dialer. Call state was IDLE, and the guard aborted input.
- **Fix:** a cold boot (`-no-snapshot-load`) fixed both.
- **Safety:** nothing was typed into another app, no call was placed, and the Emergency SOS tile was never tapped.

## 4. Not covered here

- **Not tapped on the device:** doctor note, prescription and care-plan screens (covered by the API and widget tests).
- **No device run:** notification deep links on the device this phase (Phase 02 E2/E11 passed; API checks in D-13).
- **Physical phone:** none (B10).
- **External delivery:** no push, email or SMS (B4/B5).
- **Webhooks:** no real Stripe webhook delivery (B3).
- **Language review:** no native Sinhala or Tamil review of the new strings (B12).
