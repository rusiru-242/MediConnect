# A05 — Test Verification Matrix

For: reviewers. 2026-11-28, branch `fix/agents-a05-fraud-support`, started from `origin/main` **`18e8a32`**.

## Environment and safety checks

| Check | Result |
|---|---|
| MongoDB | Local `127.0.0.1:27017` only.<br>**UAT:** `mediconnect_uat`.<br>**Automated tests:** fresh `mediconnect_a05*_test` databases; conftest refuses hosts other than loopback and database names without `_test`.<br>The remote cluster was never contacted, and no credential was changed |
| Backend | UAT on `127.0.0.1:8001`, started by `start_uat_backend.ps1 -SkipSeed`.<br>Launcher line: database `mediconnect_uat` (local), AI deterministic, e-mail, push and SMS disabled, Stripe test mode.<br>Nothing on port 8000 was started or stopped |
| Admin web | Vite dev server `127.0.0.1:5174` pointed at `:8001`, in Chrome through `playwright-core`. Every request to any other host is aborted: **0 attempted** |
| Live AI | **None.** No A05 authorization exists. Probe provider usage delta: 0 Gemini, 0 OpenAI |
| Stripe | No PaymentIntent created in UAT. Automated tests mock `stripe.PaymentIntent.retrieve/cancel` |
| Provider leaks in tests | The A03 detector (`a03_leak_detector.py`) covers SMTP, Twilio, FCM, OAuth, Stripe API and files, Gemini and OpenAI hosts. Result in `evidence/a05_backend_provider_attempts.json` |
| Data | Synthetic accounts only:<br>• `uat.p02.patientc`: hoarding pattern<br>• `uat.p02.patientb`, `uat.patient2`: normal booking<br>• `uat.p03.patienta`, `uat.p03.patientb`: support<br>• `uat.p03.doctor.alpha`, `uat.admin`<br>One fixture step (documented in the probe): one hold's `holdExpiresAt` was moved into the past so the worker released it without a 10-minute wait |
| Emulator input | Foreground app checked before input. The synthetic password is typed from `backend/uat.env` and never printed. No password is visible in any screenshot |

## Automated suites

| Suite | A05 result | A04 baseline |
|---|---|---|
| Backend `pytest` (fresh `_test` database, provider detector) | **1,003 passed, 0 failed** | 976 |
| A05 backend file | `tests/test_a05_fraud_support.py`: **27 tests**. On unchanged `main`: 23 fail, 4 pass (see the bug report for which failures reproduce defects) | — |
| Flutter `flutter test` | **333 passed** (`test/screens/a05_support_test.dart`: 6 new) | 327 |
| Flutter `flutter analyze` | No issues | — |
| Android debug APK | Built (`--dart-define=API_BASE_URL=http://10.0.2.2:8001`), installed on emulator-5554 | — |
| Admin web `vitest run` | **44 passed** (`src/test/a05FraudSupport.test.tsx`: 2 new) | 42 |
| Admin web `tsc --noEmit`, `npm run build` | OK | — |

**Total automated tests:** 1,003 + 333 + 44 = **1,380** (A04 baseline 1,345; +27 backend, +6 Flutter, +2 admin).

**Changed expectations:** 3, listed in `A05_BUG_FIX_REPORT.md`. No assertion was removed.

## Live API, browser and emulator runs

| Run | Result |
|---|---|
| `a05_probe.py uat` (`evidence/a05_probe_uat.json`) | **Fraud:** the hoarding account's 4 unpaid holds on distinct slots (2 released, 1 expired by the worker, 1 held) were raised by the backend worker sweep after 260 s as `SLOT_HOARDING_ATTEMPT`, MEDIUM, with all slots in the evidence. Re-evaluation returned the same assessment; there was no account, payment, refund, session or other booking change; non-admins got 403; the admin review was audited with `accountActionTaken: false`.<br>**Support:** 24 checks covering create, duplicate, invalid input, queue, draft, explicit send, de-duplication, notification, follow-up, cross-access, injection, emergency and chat.<br>**Provider delta:** 0 |
| `a05_negative.py` (`evidence/a05_negative.json`) | `uat.patient2` (0 bookings in 24 h): one hold released → evaluation `null`, 0 open assessments, ACTIVE |
| `a05_repro_fraud.py` on `main` and on the branch | 6 → 1 alerts; re-raise after dismissal true → false; payment retries flagged → not flagged; hoarding not detected → detected |
| Browser `fraud` (`evidence/a05_browser_admin_fraud.json`, b01–b02) | Worker-raised signal with rule, provisional threshold, observed count, slot evidence and review history; only human review decisions offered; modal closed without a decision |
| Browser `reply` (b03–b06) and `followup` (b07–b08) | Emulator ticket flagged "Requester replied". Reply box empty until "Insert suggested reply"; edited and sent explicitly. The patient's follow-up appears in the same ticket.<br>A double-click sent 2 POSTs (the server stored 1; A05-BUG-011); after the fix, 1 POST (`a05_browser_admin_reply_after_fix.json`) |
| Emulator (`evidence/emulator/a05_e01`–`e13`) | Profile → Help & Support → list → empty-form validation → ticket with "Appointment help" → admin reply in the browser → notification opens the ticket → follow-up → app restart (new process) → logout and login → emergency notice ticket → chat lists tickets → chat refuses refund approval |
| Database checks after the emulator run | `TCK-8B612CA6`: category `appointment_issue`; messages PATIENT, ADMIN (edited text), PATIENT; one notification to the requester with `relatedTicketId`, push `not_requested` |

## Scenario matrix

**Status values:** PASS, PARTIAL, FAIL, BLOCKED, NOT APPLICABLE.

**Evidence labels:**

| Label | Source |
|---|---|
| Auto | pytest, Flutter test or vitest |
| Probe | `a05_probe.py` or `a05_negative.py` against UAT |
| Repro | `a05_repro_fraud.py` |
| Browser | Admin web in Chrome |
| Emu | Emulator screenshot and database check |

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A05-F01 | Existing failed-login signal detection | Auto f01 (5 real failed logins → AUTH_FAILURE events, BRUTE_FORCE event, `UNAUTHORIZED_ACCESS_BURST` signal via the sweep) | PASS (automated) |
| A05-F02 | Normal login activity does not create a signal | Auto f02 (one typo, then a successful login) | PASS (automated) |
| A05-F03 | Synthetic reservation hoarding generates a review signal | Probe F03a/F03b (worker-raised); Auto f03; Repro; Browser b02 | PASS |
| A05-F04 | Normal booking does not generate a signal | Probe negative (`uat.patient2`); Auto f04. The probe's first "normal" account had earlier A03 test holds and was correctly flagged (A05-O2) | PASS |
| A05-F05 | Ordinary failed-payment recovery handled appropriately | Auto f05 (4 attempts on one slot, 2 failed payments → no signal); Repro (BUG-010) | PASS (automated) |
| A05-F06 | Configurable thresholds | Auto f06 (`FRAUD_SLOT_HOARDING_MIN_SLOTS`, `..._WINDOW_HOURS`); sweep interval in f09 | PASS (automated) |
| A05-F07 | Duplicate alert prevention | Auto f07; Probe F07 (same id, 1 open); Repro (dismissal) | PASS |
| A05-F08 | Concurrent detection execution | Auto f08 (6 threads in lockstep → 1); Repro 6 → 1 | PASS (automated) |
| A05-F09 | Backend restart behaviour | Auto f09 (restart state reset → still 1 assessment; throttle; off switch). In UAT the signal was raised by the worker of a freshly restarted backend | PASS |
| A05-F10 | Administrator alert visibility | Browser b01; Auto f10 | PASS |
| A05-F11 | Accurate alert evidence and explanation | Browser b02 (threshold, observed count, slots in Asia/Colombo, outcomes); Auto f03 | PASS |
| A05-F12 | Authorized administrator review | Probe F12 (INVESTIGATING, audited); Auto f07, f10 (dismiss, investigate, invalid decision 422) | PASS |
| A05-F13 | Unauthorized alert access rejected | Probe F13 (patient and doctor 403); Auto f13 (+ evaluate 403, unauthenticated 401) | PASS |
| A05-F14 | No autonomous account suspension | Probe F14-F15 (ACTIVE, no revoked sessions); Auto f01, f03, f10; no such code path exists | PASS |
| A05-F15 | No unauthorized financial mutation | Probe F14-F15 (payments and refunds unchanged; other bookings unchanged); Auto f03 snapshot | PASS |
| A05-F16 | No regression of reservation and payment integrity | Auto f16 plus the full suite (A03 booking and payment tests unchanged and passing); probe holds expired and released through the normal paths | PASS |
| A05-C01 | Patient opens support UI | Emu a05_e01–e02; Flutter profile-entry test | PASS |
| A05-C02 | Patient creates a valid ticket | Emu a05_e04–e05; Probe C02; Auto c02 | PASS |
| A05-C03 | Invalid submission rejected | Emu a05_e03 (form validation); Probe C03 (422 × 3); Auto c03 (5 cases) | PASS |
| A05-C04 | Patient views own ticket list | Emu a05_e02, e10; Auto c02 | PASS |
| A05-C05 | Patient views ticket details | Emu a05_e05, e07; Auto c02 (no internal draft) | PASS |
| A05-C06 | Administrator receives the correct ticket | Browser b03 ("Requester replied" on the emulator ticket); Probe C06 | PASS |
| A05-C07 | Support response draft preparation | Browser b04–b05 ("Insert suggested reply"; template label); Probe C07-C08 | PASS |
| A05-C08 | Administrator edits the suggested response | Browser b05; DB: stored text is the edited text; Auto c06; admin test | PASS |
| A05-C09 | Explicit administrator response submission | Browser b06; nothing stored before the send (Probe C07-C08: 1 message) | PASS |
| A05-C10 | Patient receives and views the reply | Emu a05_e06–e07; Probe C10 | PASS |
| A05-C11 | Patient sends a follow-up | Emu a05_e08; Probe C11-C13 | PASS |
| A05-C12 | Administrator views the follow-up | Browser b07–b08; Probe C11-C13 | PASS |
| A05-C13 | Ticket status consistency | open → waiting_for_user ("Support replied") → open; Emu e05, e07, e08; Auto c06 | PASS |
| A05-C14 | Resolved or closed ticket behaviour | Auto c14 (resolved reopens; closed → 409; closed allows a new ticket); Flutter closed-ticket test. Not exercised on the device | PASS (API and widget) |
| A05-C15 | Duplicate message prevention | Probe C15a, C09-C15b, C11-C13; Auto c15 (5 concurrent → 1); Browser double-click | PASS |
| A05-C16 | Cross-patient access rejection | Probe C16-C17; Auto c16 (ticket id and ObjectId; other patient and doctor 403; not listed) | PASS |
| A05-C17 | Unauthorized administrator operation rejected | Probe C16-C17 (patient → reply, draft, status 403; admin → requester path 403); Auto c16 | PASS |
| A05-C18 | Prompt injection and unsafe action rejection | Probe C18-C19, C18c; Emu a05_e13; Auto c18, c18c | PASS (tested phrasings) |
| A05-C19 | No fabricated financial or clinical information | Auto c18 (refund template disclaims; no amount); Probe C18-C19; emergency → 1990 notice, no advice (C18b, Emu e11) | PASS |
| A05-C20 | Notification recipient and deep link | Emu a05_e06 → e07; Flutter deep-link test; Probe (recipient = requester, in-app, push not requested) | PASS (in-app; remote push not verified) |
| A05-C21 | Logout, login and restart persistence | Emu a05_e09 (new process), e10 (after logout and login); Auto c21 | PASS |
| A05-C22 | Provider failure or deterministic fallback | Auto c18c (failing provider injected: same answers); Probe provider delta 0. Support paths never call a provider | PASS (deterministic paths) |

**Totals:** 38 scenarios: **38 PASS**, 0 PARTIAL, 0 FAIL, 0 BLOCKED.

Qualified passes:

| Scenario | Limitation |
|---|---|
| F01, F02, F05, F06, F08 | Automated (UAT did not repeat failed logins or concurrency) |
| C14 | API and widget level |
| C18 | Tested phrasings only |
| C20 | In-app only |
| C22 | No live provider exists on these paths |
