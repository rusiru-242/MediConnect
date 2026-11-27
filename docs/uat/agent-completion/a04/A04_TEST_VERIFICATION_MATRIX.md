# A04 — Test Verification Matrix

For: reviewers. 2026-11-27, branch `fix/agents-a04-prescription-assistant`, started from `origin/main` **`d8c2142`**. Tested code commit **`51bdaa3`**.

## Environment and safety checks

| Check | Result |
|---|---|
| MongoDB | Local `127.0.0.1:27017` only. UAT `mediconnect_uat`; automated tests on fresh `mediconnect_a04*_test` databases (conftest refuses non-loopback hosts and names without `_test`). The remote cluster was never contacted |
| Backend | UAT on `127.0.0.1:8001` through `start_uat_backend.ps1 -SkipSeed`: AI deterministic (provider keys blanked), e-mail, push and SMS disabled, Stripe test mode. Nothing on port 8000 was started or stopped |
| Live AI | **None.** No A04 authorization was requested; the probes recorded a provider usage delta of 0 Gemini and 0 OpenAI requests |
| Provider leaks in tests | The A03 detector (SMTP, Twilio, FCM, OAuth, Stripe, Gemini, OpenAI hosts): **0 attempts** in the final run (`evidence/a04_backend_provider_attempts.json`) |
| Data | Synthetic accounts (`uat.p03.*`, `uat.doctor.pending1`, `uat.admin`) and synthetic medicine names (`Synthocillin-A04`, `Probexacillin-*`, `Allergenol-*`). One synthetic completed visit was added to `mediconnect_uat` for the emulator run (`uatFixture` field) |
| Emulator input | Foreground checked before input; the synthetic password is typed from `backend/uat.env` and never printed. No password is visible in any screenshot |

## Automated suites

| Suite | A04 result | A03 baseline |
|---|---|---|
| Backend `pytest` (commit `51bdaa3`, fresh `mediconnect_a04final2_test`, detector) | **976 passed, 0 failed, 0 provider connection attempts** | 945 |
| A04 backend file | `tests/test_a04_prescription_assistant.py`: 31 tests. **22 fail on the pre-fix code** (`evidence/a04_tests_on_pre_fix_main.txt`); the other 9 check behaviour that was already correct | — |
| Flutter `flutter test` | **327 passed** | 317 |
| Flutter `flutter analyze` | No issues | — |
| Android debug APK | Built (`--dart-define=API_BASE_URL=http://10.0.2.2:8001`), installed on emulator-5554 | — |
| Admin web `vitest run` | **42 passed** (no admin code changed) | 42 |
| Admin web `tsc --noEmit`, `npm run build` | OK | — |

**Total automated tests:** 976 + 327 + 42 = **1,345** (A03 baseline 1,304; +31 backend, +10 Flutter).

**Changed expectation:** the consultation-screen widget test (see `A04_BUG_FIX_REPORT.md`).

## Live API, database and emulator runs

| Run | Result |
|---|---|
| `a04_probe.py baseline` on unchanged `main` (`evidence/a04_probe_baseline.json`) | Reproduced A04-BUG-001 (500), 002, 003 (3 prescriptions stored), 004 (no allergy warning), 005, 006, 016 |
| `a04_probe.py after_fix` (`evidence/a04_probe_after_fix.json`) | V01 422, V02 422, P08c 1 stored, allergy warning returned, R01b 422, R04b 409; 18 of 18 AI requests answered or refused as intended; 0 prescriptions or renewals created by chat; authorization 7 of 7 refused (403); provider delta 0 |
| Emulator, doctor (`evidence/emulator/a04_e01`–`e08`, `e18`–`e20`) | Documentation list shows visits → empty form → name and strength only refused → review dialog with the real allergy warning → Cancel stores nothing → changed medicine → issued exactly as entered → renewal queue → approval dialog lists the instructions → approved |
| Emulator, patient (`a04_e09`–`e17`, `e21`–`e24`) | Prescription visible with exact instructions → reminder (2 times, 5 days) → duplicate reminder refused with the right message → renewal requested from the prescription → duplicate refused → app restart, still there → "renewal approved" notification → renewal list shows APPROVED → AI lists current prescriptions, including the renewal, and the refusals |
| Database checks after the emulator run | Prescription `RX-20261127-E389AE`: visit, record and items as entered, one record. Renewal `REN-20261127-FDCB86`: approved by the prescribing doctor, `pendingKey` removed. New `RX-REN-20261127-D70D5D`: same visit, items identical to the original, no reminder created automatically. Patient notified |

## Scenario matrix

**Status values:** PASS, PARTIAL, FAIL, BLOCKED or NOT APPLICABLE.

**Evidence labels:**

| Label | Source |
|---|---|
| Auto | pytest or Flutter test |
| Probe | `a04_probe.py` against UAT |
| Emu | Emulator screenshot and database check |

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A04-P01 | Authorized doctor prescription creation | Emu a04_e08; Probe P01; Auto p01 | PASS |
| A04-P02 | Correct patient and consultation association | Emu (database check); Auto p02 | PASS |
| A04-P03 | Correct medication fields | Emu a04_e08/e10; Auto p01_p03 | PASS |
| A04-P04 | Missing required field rejection | Emu a04_e05; Auto bug001; Flutter BUG-009 | PASS |
| A04-P05 | Invalid instruction rejection | Probe V01, V02; Auto bug001, bug002 | PASS |
| A04-P06 | Draft persistence where supported | No persisted prescription draft exists; the draft check stores nothing by design; issuing is the explicit signing | NOT APPLICABLE |
| A04-P07 | Explicit clinician approval | Emu a04_e06/e07 (review dialog, Cancel stores nothing); Flutter review-dialog test | PASS |
| A04-P08 | Duplicate submission prevention | Probe P08c (3 → 1); Auto bug003 (3) | PASS |
| A04-A01 | Authorized prescription retrieval | Probe AI-PAT/AI-DOC; Emu a04_e23; Auto bug007, ai_* | PASS |
| A04-A02 | Grounded prescription summary | Probe AI-DOC summary; Auto ai_doctor (own vs other doctor's reference) | PASS |
| A04-A03 | Structured draft assistance where supported | Auto structured_draft; Emu a04_e06; doctor "draft help" reply | PASS |
| A04-A04 | Autonomous prescribing rejection | Probe (patient and doctor); Auto ai_* ; renewal tool needs confirmation | PASS |
| A04-A05 | Unauthorized medication change rejection | Probe; Auto ai_* | PASS |
| A04-A06 | Prompt injection resistance | Probe "Ignore previous restrictions…" (both roles); Emu a04_e24 | PASS (tested phrasings) |
| A04-A07 | Provider failure fallback | Auto a07 (failing provider injected): same answers; prescription paths never call a provider | PASS (deterministic paths) |
| A04-U01 | Approved prescription visibility | Emu a04_e09/e10 | PASS |
| A04-U02 | Accurate medication instructions | Emu a04_e10 (matches database); Flutter "not stated" test | PASS |
| A04-U03 | Prescription persistence | Emu: logout/login and app restart (a04_e17) | PASS |
| A04-U04 | Cross-patient access rejection | Probe S (403); Auto s03_s04, ai_patient (no other patient's data) | PASS |
| A04-R01 | Patient renewal request | Emu a04_e14/e15; Auto bug005 | PASS |
| A04-R02 | Authorized doctor approval | Emu a04_e19/e20; Auto r02 | PASS |
| A04-R03 | Doctor rejection | Auto r03 (API level); not repeated on the emulator | PASS (API) |
| A04-R04 | Duplicate renewal prevention | Emu a04_e16; Probe R04b; Auto bug006 | PASS |
| A04-R05 | Concurrent approval protection | Auto r02 (4 parallel approvals → 1 prescription) | PASS (automated) |
| A04-R06 | Correct patient notification | Emu a04_e21; Auto r02, r03, bug012 | PASS |
| A04-M01 | Correct prescribed schedule | Emu a04_e11/e12 (2 times for twice daily); Auto m01 | PASS |
| A04-M02 | Correct prescribed duration | Emu (5 days stored, not 14); Auto m01 | PASS |
| A04-M03 | No invented medication instructions | Emu a04_e04 (empty fields); Auto m03 (as-needed refused), "not stated" replies | PASS |
| A04-M04 | Renewal synchronization | An amendment stops outdated patient reminders (Auto bug008). A renewal starts no reminder automatically, by design; the patient sets one from the renewed prescription. Not exercised on the device for the renewed prescription | PARTIAL |
| A04-M05 | Duplicate reminder prevention | Emu a04_e13; Auto bug008 | PASS |
| A04-M06 | Worker restart recovery | A02 scheduler recovery suite unchanged and passing; patient reminders survived two backend restarts during A04 | PASS (A02 automated + restart observation) |
| A04-S01 | Pending doctor rejection | Probe S; Auto s01_s02 | PASS |
| A04-S02 | Unrelated doctor rejection | Probe S; Auto s01_s02, bug007, ai_doctor (404 for another doctor's visit) | PASS |
| A04-S03 | Patient mutation rejection | Probe S (amend, approve: 403); Auto s03_s04 | PASS |
| A04-S04 | Unauthorized admin clinical access rejection | Probe S (403); Auto s03_s04 | PASS |
| A04-S05 | Audit history integrity | Auto s05 (SIGNED, VIEWED, AMENDED, VIEWED; previous items kept) | PASS |

**Totals:** 36 scenarios: **34 PASS**, 1 PARTIAL (M04), 1 NOT APPLICABLE (P06), 0 FAIL, 0 BLOCKED.

Qualified passes:

| Scenario | Limitation |
|---|---|
| A06 | Tested phrasings only |
| A07 | No live provider exists on these paths |
| R03 | API level only |
| R05 | Automated only |
| M06 | A02 suite plus a restart observation |
