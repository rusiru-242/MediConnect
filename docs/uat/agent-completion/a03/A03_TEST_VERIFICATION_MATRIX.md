# A03 — Test Verification Matrix

For: reviewers. 2026-11-27, branch `fix/agents-a03-booking-payments`, tested code commit **`e3722ba`** (mobile and admin code at `020f3b6`, unchanged since).

## Environment and safety checks

| Check | Result |
|---|---|
| MongoDB | Local `127.0.0.1:27017` only. UAT `mediconnect_uat`; automated tests on fresh `mediconnect_a03*_test` databases (conftest refuses non-loopback hosts and names without `_test`). The remote cluster was never contacted |
| Backend | UAT on `127.0.0.1:8001` (and `:8002` for the multi-process race) through `start_uat_backend.ps1`. Push, e-mail and SMS are disabled; Stripe test key enforced. Nothing on port 8000 was started or stopped |
| Stripe | Test mode only (`sk_test_`); every PaymentIntent and refund `livemode=false`. CLI forwarding with owner approval; no public tunnel |
| Live AI | Gemini `gemini-3.5-flash-lite`, owner cap 60: **44 calls** (44 successes), plus 4 refused locally by the daily limit. OpenAI not used |
| Provider leaks in tests | The detector (`a03_leak_detector.py`) covers SMTP, Twilio, FCM, OAuth, **Stripe, Gemini and OpenAI** hosts: baseline 0 attempts, final 0 attempts |
| Emulator input | Foreground checked before every input (`emu.py`). One Android system ANR on the first emulator boot (A03-O3): system dialogs closed with the standard broadcast, then the emulator was cold-booted |
| Data | Synthetic accounts, doctors and cards (Stripe test cards and PaymentMethods) |

## Automated suites

| Suite | Result | Baseline |
|---|---|---|
| Backend `pytest` (final code `e3722ba`, fresh `mediconnect_a03final2_test`, detector) | **945 passed, 0 failed, 0 provider connection attempts** | 907 (verified at the start of A03 on `048ad48`: 907 passed, 0 attempts) |
| A03 backend files | `tests/test_a03_booking_payments.py`, `tests/test_a03_booking_agent.py` | — |
| Flutter `flutter test` | **317 passed** | 313 |
| Flutter `flutter analyze` | No issues | — |
| Android debug APK | Built (`--dart-define=API_BASE_URL=http://10.0.2.2:8001`), installed on emulator-5554 | — |
| Admin web `vitest run` | **42 passed** | 40 |
| Admin web `npm run build` | OK | — |
| Admin web `tsc --noEmit` | OK | — |

**Changed expectations:** P04 `test_n10`, the P05 webhook fixtures and the `phase04Admin` retry text (reasons in `A03_BUG_FIX_REPORT.md`).

## Live, emulator and browser runs

| Run | Result |
|---|---|
| `a03_live_stripe_uat.py main` + restart (`evidence/a03_live_stripe_uat.json`) | **43/43 PASS** (2 recorded FAILs re-evaluated: a script check and timing; reasons in the JSON) |
| Stripe CLI forwarding (`evidence/stripe_cli_listen_redacted.log`) | 51 events forwarded: 46 × HTTP 200, 0 non-2xx, 5 not delivered while the backend was stopped (later resent) |
| AI booking probe: deterministic (after fixes), Gemini run 1, Gemini final | Deterministic 16 turns (5 threads); Gemini runs 19 turns (6 threads, incl. confirmation-by-chat and a real taken slot); 0 holds from conversation; 0 unverified doctor cards |
| Provider fallback (`evidence/a03_provider_fallback.json`) | PASS |
| Emulator (`evidence/emulator/a03_*`) | Search → select → this-doctor slots → summary (in-person) → accept → hold → in-sheet decline → in-sheet success → confirmed → cancel (preview) → refunded → notification deep link; app restart restores the hold; UI-created hold expires and its intent is cancelled |
| Browser (`evidence/a03_browser_admin_uat.json`, `evidence/browser/`) | **6/6 PASS**: refund approval (one POST), "Needs review", reconciliation, payment monitoring, appointments, 0 non-local requests, 0 page errors |

## Scenario matrix

**Status values:** PASS = executed and correct; PARTIAL = part executed; BLOCKED = needs an unavailable external service.

**Evidence labels:**

| Label | Source |
|---|---|
| Live | `a03_live_stripe_uat.json` |
| Probe | AI booking probe |
| Emu | Emulator |
| Browser | Admin browser run |
| Auto | pytest, Flutter test or Vitest |

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A03-A01 | English booking request | Probe (det. + Gemini); Emu a03_01 | PASS |
| A03-A02 | Sinhala booking request | Probe | PASS |
| A03-A03 | Romanized Sinhala booking request | Probe | PASS |
| A03-A04 | Mixed-language request | Probe; Auto bug013 | PASS |
| A03-A05 | Follow-up budget change | Probe (SI, ROM, MIX) | PASS |
| A03-A06 | Follow-up doctor selection | Probe; Auto bug010; Emu a03_02 | PASS |
| A03-A07 | Named-doctor availability | Probe; Emu a03_03 | PASS |
| A03-A08 | Unavailable slot alternatives | Probe CONFLICT (real taken slot); Auto bug011 | PASS |
| A03-A09 | Explicit booking confirmation | Emu a03_04_booking_summary_in_person, a03_06; Auto bug015_016 | PASS |
| A03-A10 | Gemini live booking request | Probe Gemini (44 live calls, 0 failures) | PASS |
| A03-A11 | Provider failure and deterministic fallback | Live fallback (cap reached) | PASS |
| A03-A12 | Unauthorized AI mutation rejection | Probe (0 holds); Auto a12, bug012 | PASS |
| A03-R01 | Atomic reservation | Live R01 | PASS |
| A03-R02 | Concurrent reservation | Live R02 (2 patients, 2 processes) | PASS |
| A03-R03 | Hold countdown | Live R03 (600 s); Emu a03_05/a03_09 | PASS |
| A03-R04 | Automatic expiry | Live R04; Emu a03_10 | PASS |
| A03-R05 | Manual release | Live R05 | PASS |
| A03-R06 | Released slot availability | Live R06 | PASS |
| A03-R07 | Backend restart recovery | Live restart1–3; Emu app restart | PASS |
| A03-R08 | Duplicate reservation request | Live R08 | PASS |
| A03-P01 | Stripe test payment success | Live P01; Emu a03_15 | PASS |
| A03-P02 | Declined payment | Live P02; Emu a03_13 | PASS |
| A03-P03 | Cancelled payment | Live P03 | PASS |
| A03-P04 | Payment retry | Live P04; Emu decline → success; Auto bug004 | PASS |
| A03-P05 | Duplicate charge prevention | Live P05 (re-evaluated) | PASS |
| A03-P06 | Amount and currency verification | Live P06; Auto P02 mismatch | PASS |
| A03-P07 | Payment ownership | Live P07 | PASS |
| A03-P08 | Expired-hold payment | Live P08; Auto bug005; Emu a03_10 | PASS |
| A03-P09 | Cancelled appointment payment | Live P09 | PASS |
| A03-P10 | Network failure recovery | Live restart (webhook lost, status refresh) | PASS |
| A03-W01 | Valid locally signed event | Live W01; Auto P05 | PASS |
| A03-W02 | Invalid signature | Live W02; Auto P05 | PASS |
| A03-W03 | Duplicate event | Live W03; Auto | PASS |
| A03-W04 | Out-of-order event | Live W04; Auto bug003 | PASS |
| A03-W05 | Actual Stripe test webhook delivery | Stripe CLI forwarding (kind 2); public endpoint not tested | PASS (CLI) |
| A03-W06 | Payment success reconciliation | Live W06 | PASS |
| A03-W07 | Refund status reconciliation | Live W07, C10b; Auto bug006/bug007 | PASS |
| A03-W08 | Webhook retry and recovery | Live W08 (CLI resend); Auto bug001 | PASS |
| A03-C01 | Patient cancellation | Live C01; Emu a03_20/a03_21 | PASS |
| A03-C02 | Doctor cancellation | Live C02 | PASS |
| A03-C03 | Rescheduling | Live C03 | PASS |
| A03-C04 | Failed rescheduling preserves booking | Live C04 | PASS |
| A03-C05 | Refund request | Live C05; Emu a03_21 | PASS |
| A03-C06 | Admin refund approval | Live C06; Browser A03-U04a | PASS |
| A03-C07 | Admin refund rejection | Live C07 | PASS |
| A03-C08 | Duplicate refund prevention | Live C08 | PASS |
| A03-C09 | Concurrent refund approval | Live C09 (4 parallel → 1 Stripe refund) | PASS |
| A03-C10 | Stripe test refund reconciliation | Live C10, C10b; Auto bug006/007/009 | PASS |
| A03-U01 | Patient appointment details | Emu a03_19, a03_22 | PASS |
| A03-U02 | Doctor appointment details | Doctor API (`a03_cross_role_refund.json`); doctor UI from Phase 02/03 widget tests | PASS (API) |
| A03-U03 | Admin payment monitoring | Browser U03a–c | PASS |
| A03-U04 | Admin refund monitoring | Browser U04a–b | PASS |
| A03-U05 | Notification deep link | Emu a03_24 | PASS |
| A03-U06 | Correct appointment reminder | Auto P05 s06/A02 suites (live delivery in A02) | PASS (automated) |
| A03-U07 | Obsolete reminder cancellation | Live C03 state; Auto P05 s06f/g | PASS (automated + live state) |
| A03-U08 | In-person appointment semantics | Emu a03_04 / a03_18 / a03_19; doctor API | PASS |

**Totals:** 56 scenarios: **56 PASS**, 0 PARTIAL, 0 BLOCKED, 0 FAIL. Qualified passes:

| Scenario | Limitation |
|---|---|
| W05 | Stripe CLI, not a public endpoint |
| U02 | Doctor view checked through the API |
| U06, U07 | Automated, plus live state |

No scenario was added beyond the required matrix. The 20 defects each have their own tests (see the bug report).
