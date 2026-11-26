# A02 — Test Verification Matrix

For: reviewers. 2026-11-26, branch `fix/agents-a02-reminders-notifications`.

## Environment and safety checks (before any code ran)

| Check | Result |
|---|---|
| MongoDB | Local `127.0.0.1:27017` only. UAT `mediconnect_uat`; automated tests `mediconnect_a02*_test` (conftest refuses non-loopback hosts and names without `_test`). The remote cluster was never contacted |
| Backend | UAT on `127.0.0.1:8001` (launcher: deterministic AI, SMTP blank, Firebase blank, Twilio blank). The owner's port-8000 process was left untouched |
| External providers | No push, e-mail or SMS left the machine. The full test suite ran with a connection detector: **13** real SMTP attempts on the baseline (A02-BUG-002), **0** after the fix. Stripe calls in test mode only (`sk_test_`, as in Phases 02–05) |
| Accounts and data | Synthetic `@uat.mediconnect.lk` accounts, synthetic medicines (Synthomox, Synthocet, Synthoval, Synthopar, Synthoworker) and instructions |
| Emulator input | Foreground checked before every input. One guarded tap on the Android permission dialog after checking its identity |

## Automated suites

| Suite | Command | Result | Baseline |
|---|---|---|---|
| Backend (final code, `235cce4`) | `pytest -q` on fresh `mediconnect_a02final_test`, with the provider-connection detector | **907 passed, 0 failed** (372.8 s), 0 provider attempts | 865 |
| Backend (before the last 3 tests) | same, `mediconnect_a02full_test` | **904 passed, 0 failed**, 0 provider attempts | 865 |
| A02 backend tests | `tests/test_a02_reminders_notifications.py` | 42 tests (local SMTP server, real crash subprocess, injected-clock scheduler) | — |
| Flutter | `flutter test` | **313 passed** (309 + 4 planner tests) | 309 |
| Flutter analyze | `flutter analyze` | no issues | — |
| Android debug APK | `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001` | built and installed (3 builds: before, BUG-019, BUG-020) | — |
| Admin web | `vitest run` / `npm run build` | **40 passed** (39 + 1) / build OK | 39 |

Changed expectation: P05 `test_s06c` only (see `A02_BUG_FIX_REPORT.md`).

## Scenario matrix

**Status values:**

| Status | Meaning |
|---|---|
| PASS | Executed and correct |
| PARTIAL | Part executed; the rest is blocked or not observable |
| BLOCKED | Needs an unavailable external service |

**Evidence:**

| Label | Source |
|---|---|
| Live | `evidence/a02_live_uat.json` (26 steps) |
| Worker | `evidence/a02_worker_restart_race.json` |
| Emu | `evidence/emulator/*.png` |
| Auto | pytest or Flutter test |

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A02-M01 | Clinician-approved schedule | Live M01, M01b; Auto bug011 | PASS |
| A02-M02 | Correct medicine and dosage | Live M02 | PASS |
| A02-M03 | Correct reminder time | Live M03 (47 s after 19:32 Colombo) | PASS |
| A02-M04 | Taken | Live M04; Emu a02_10 | PASS |
| A02-M05 | Snooze | Live M05 (redelivered after 6.0 min, once) | PASS |
| A02-M06 | Skip and missed history | Live M06, M06b (re-evaluated, see the reminder report); Emu a02_13 | PASS |
| A02-M07 | Schedule update | Live M07 | PASS |
| A02-M08 | Schedule cancellation | Live M08 | PASS |
| A02-M09 | App restart | Emu: relaunch and sign-in re-planned device reminders (0 → 8 alarms) | PASS |
| A02-M10 | Actual push receipt | Firebase not configured | BLOCKED |
| A02-A01 | Confirmed appointment reminder | Live A01/A02 (22:00 slot, 2 h reminder) | PASS |
| A02-A02 | Timezone correctness | Live (scheduledAt = 22:00 Colombo, due −2 h); Auto P05 s06h | PASS |
| A02-A03 | Rescheduling | Live A03/A04; Auto P05 s06g | PASS |
| A02-A04 | Cancellation | Live A03/A04 (0 events); Auto P05 s06f | PASS |
| A02-A05 | Unpaid appointment exclusion | Live A05 | PASS |
| A02-A06 | Notification navigation | Live A06; Emu a02_11 | PASS |
| A02-F01 | Doctor-approved follow-up | Live F01 | PASS |
| A02-F02 | Scheduled delivery | Auto `test_f02` (real scheduler, 09:00 Colombo); not observed live | PARTIAL |
| A02-F03 | Date update | Live T04/F03 | PASS |
| A02-F04 | Cancellation and completion | Live F04 (re-evaluated) | PASS |
| A02-T01 | Doctor-assigned test | Live T01/T02 | PASS |
| A02-T02 | Correct instructions | Live T01/T02 (verbatim) | PASS |
| A02-T03 | Reminder execution | Live T03 | PASS |
| A02-T04 | Completion and cancellation | Live T04/F03, F04 | PASS |
| A02-N01 | In-app notification | Live N01; Emu a02_08 | PASS |
| A02-N02 | Foreground push | Firebase not configured | BLOCKED |
| A02-N03 | Background push | Firebase not configured | BLOCKED |
| A02-N04 | Terminated-app push | Firebase not configured | BLOCKED |
| A02-N05 | Deep-link navigation | Emu a02_09, a02_11 (from the in-app list); push tap not possible | PASS (in-app) |
| A02-N06 | Unread count | Live N06; Emu a02_07, a02_12 | PASS |
| A02-N07 | Mark as read | Live N07, N07b; Emu a02_12 | PASS |
| A02-N08 | Device token refresh | Live N08/N09 (backend registration, refresh, account switch); no FCM token can be generated | PARTIAL |
| A02-N09 | Logout and token removal | Live N08/N09; Emu a02_06 (alarms 8 → 0) | PASS |
| A02-N10 | Cross-account isolation | Live N10, M04, A06, T01; Auto bug012 | PASS |
| A02-C01 | Authorized doctor message | Live C01 | PASS |
| A02-C02 | AI draft review where supported | Live C02 (fixed-template draft; approval required) | PASS |
| A02-C03 | Correct recipient | Live C01/C03 | PASS |
| A02-C04 | Unauthorized communication rejection | Live C04 | PASS |
| A02-C05 | Duplicate message prevention | Live C05 | PASS |
| A02-I01 | Firebase configuration | Inspected: no Firebase project or config; the app logs `Failed to load FirebaseOptions` | BLOCKED |
| A02-I02 | Actual FCM acceptance | Not configured | BLOCKED |
| A02-I03 | Actual device receipt | Not configured (push). Device-local reminders were received: Emu a02_05 | BLOCKED (push) |
| A02-I04 | SMTP integration | Auto: local SMTP server (accept, TLS verify, refusals, drop, 451, booking confirmation, doctor e-mails) | PASS (local) |
| A02-I05 | Actual external e-mail delivery | Owner decision: local only | BLOCKED |
| A02-I06 | SMS provider integration | Auto with Twilio test doubles (P02/P05) and the A02 disabled test; no account | PARTIAL |
| A02-I07 | Actual SMS delivery | No provider | BLOCKED |
| A02-I08 | Disabled provider handling | Live I08; Auto bug004 | PASS |
| A02-I09 | Provider failure and retry | Auto bug003 (retry, uncertain, rejected), outbox retry | PASS |
| A02-S01 | Actual job execution | Live M03, T03, A01 | PASS |
| A02-S02 | Worker restart | Worker: backend down 20:01:43–20:05:31 across a due time; exactly once | PASS |
| A02-S03 | Multi-process job claiming | Worker: 3 competing workers; Auto P05 s06de (3 processes) | PASS |
| A02-S04 | Worker crash recovery | Auto: a real subprocess crash, recovered once | PASS |
| A02-S05 | Duplicate prevention | Live S05 (0 duplicate groups) | PASS |
| A02-S06 | Cancellation | Live M08, A03/A04, F04 | PASS |
| A02-S07 | Timezone boundaries | Auto P05 s06h, A02 s07 | PASS |
| A02-S08 | Permanent failure recovery | Auto s08 (4 attempts → failed) | PASS |

**Totals:** 56 scenarios: **44 PASS, 3 PARTIAL, 9 BLOCKED**, 0 FAIL, 0 NOT RUN.

Live-run integrity: 26 steps; 24 passed as recorded, and 2 recorded FAILs were script-check mistakes, re-evaluated with stated reasons (`reevaluated` field in the JSON).

## Assistant probe (section 15, read-only)

The seven brief examples plus four paraphrases (`a02_assistant_probe.py`, before and after):

| | Before | After |
|---|---|---|
| Handled correctly (answer from the user's own records, or the correct refusal) | 3 of 11 (Q-5, Q-6, Q-10) | **11 of 11** |
| Wrong scope | 2 (Q-2 listed an appointment that had already started; Q-3 "this week" read only today) | 0 |
| Misrouted to the medicine library | 2 ("Show my medicine reminders for today", "Show my missed medicine reminders") | 0 |
| Misrouted to a doctor-search clarification | 4 | 0 |
| "Mark all my notifications as read" | clarification | refused; no state change |
