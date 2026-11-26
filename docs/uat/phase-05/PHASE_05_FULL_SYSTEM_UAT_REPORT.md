# Phase 05 — Full System UAT Report

For: the project owner and reviewers. 2026-11-26.

## 1. Environment

| Item | Value |
|---|---|
| UAT backend | 127.0.0.1:8001, `ENVIRONMENT=staging`, local `mediconnect_uat`, Phase 05 code (restarted after the last backend change) |
| Automated tests | local MongoDB, fresh `*_test` databases per full run |
| Stripe | test mode only (`sk_test_`; `livemode=false` checked) |
| AI providers | disabled (deterministic engine); LLM paths only with test doubles |
| E-mail / SMS / push | disabled / not configured |
| Admin web | Vite dev server 127.0.0.1:5174 → 8001; Chrome via playwright-core; all non-local requests blocked (none attempted) |
| Mobile | debug APK built with `--dart-define=API_BASE_URL=http://10.0.2.2:8001`, Android emulator `emulator-5554` (Pixel 7 Pro image) |
| Port 8000 | not used |

## 2. Shared-component matrix (S-01 to S-08)

Status values: PASS, FAIL, PARTIAL, BLOCKED, NOT RUN, NOT IMPLEMENTED, NOT APPLICABLE. "Mocked" means a controlled test double was used for an external provider.

| ID | Scenario | Status | Evidence |
|---|---|---|---|
| S-01a | Patient role routing | PASS | `arch` S-01abc; live probe P-1–P-9 |
| S-01b | Doctor role routing | PASS | `arch` S-01abc; live probe D-1–D-7 |
| S-01c | Admin role routing | PASS | `arch` S-01abc; live probe A-1–A-9 |
| S-01d | Valid structured tool call | PASS | `arch` S-01d |
| S-01e | Invalid tool arguments | PASS | `arch` S-01d/e |
| S-01f | Unauthorized tool rejection | PASS | `arch` S-01f; admin assistant 403 for patients (`int`) |
| S-01g | Maximum tool-call enforcement | PASS | `arch` S-01g (8 calls, duplicate prevention, run record) |
| S-01h | Loop detection and timeout | PASS | `arch` S-01h; `test_phase1_orchestrator` (loop after 2 identical rounds) |
| S-02a | Gemini adapter | PASS (mocked) | `arch` S-02a: key in header, retired model remapped, tokens recorded |
| S-02b | OpenAI adapter | PASS (mocked) | `arch` S-02b |
| S-02c | Provider authentication failure | PASS (mocked) | `arch` S-02cde (401/403 → `auth_failed`, fallback) |
| S-02d | Provider timeout | PASS (mocked) | `arch` S-02d (no retry) |
| S-02e | Rate-limit response | PASS (mocked) | `arch` (429 retried once, then fallback) |
| S-02f | Invalid structured output | PASS (mocked) | `arch` S-02f |
| S-02g | Deterministic fallback | PASS | all S-02 failure tests; UAT runs entirely on the deterministic engine |
| S-02h | Usage limits and metrics | PASS (mocked) | `arch` S-02h (daily limit, disabled, circuit breaker, status vocabulary) |
| S-02 live | Live provider calls | BLOCKED | B13: owner authorization and rotated keys required |
| S-03a | English requests | PASS | `int` (31 cases), live probe |
| S-03b | Sinhala requests | PASS | `int`; live A-8 |
| S-03c | Romanized Sinhala | PASS | `int`; live P-1, P-2, A-6, D-6 |
| S-03d | Mixed language | PASS | `int` ("me week eke successful payments keeyada?") |
| S-03e | Semantic paraphrases | PASS | `int`; live A-7, D-7 |
| S-03f | Multiple constraints | PASS | `int` (payments + revenue + timeframe); live P-8 |
| S-03g | Role-specific intent | PASS | `int` (no leakage between roles) |
| S-03h | Ambiguous requests | PASS | `int` (asks which topic; unknown → help) |
| S-04a | Actual emergency symptoms | PASS | `emg` (5 cases incl. Sinhala); Phase 01 probe re-run |
| S-04b | Negated symptoms | PASS | `emg` |
| S-04c | Educational question | PASS | `emg` |
| S-04d | Emergency context follow-up | PASS | `emg` |
| S-04e | Sinhala language continuity (B17) | PASS | `emg` S-04e (fails without the fix) |
| S-04f | Self-harm crisis flow | PASS | `emg` (1926/1333 only; context kept) |
| S-04g | Medicine overdose | PASS | `emg` |
| S-04h | Safe dialer confirmation | PASS | Flutter widget tests (`ai_assistant_ui_stabilization_test`: confirm/cancel, dialer without a call); 307/307 Flutter tests |
| S-05a | Successful-search context | PASS | `mem` |
| S-05b | No-results context | PASS | `mem` |
| S-05c | Unsupported-location context | PASS | `mem` (P05-N15 fixed) |
| S-05d | Doctor selection context | PASS | live probe P-3 (auto-selection in the same chat); Phase 01 tests |
| S-05e | Date and time context | PASS | `mem` |
| S-05f | New Chat reset | PASS | `mem` |
| S-05g | Cross-account isolation | PASS | `mem` (404 / 403 / 400) |
| S-05h | Concurrent sessions | PASS | `mem` |
| S-06a | Scheduled job execution | PASS | `sch`; live W10a |
| S-06b | Worker restart | PASS | `sch`; live W10b after two restarts |
| S-06c | Worker crash recovery | PASS | `sch` (expired claim → `uncertain`, not re-sent, visible) |
| S-06d | Multi-process job claims | PASS | `sch` (3 OS processes, 12 reminders, each delivered once) |
| S-06e | Duplicate delivery prevention | PASS | `sch`; live W10b (0 duplicates) |
| S-06f | Job cancellation | PASS | `sch` |
| S-06g | Schedule updates | PASS | `sch` |
| S-06h | Timezone boundaries | PASS | `sch` (Colombo date differs from appointment date); CI on UTC green |
| S-07a | Role enforcement | PASS | `sec` S-07a; authz sweep identical to Phase 04 |
| S-07b | Object-level authorization | PASS | `enc`, `meas`, `mem`; live W08d/e |
| S-07c | Prompt injection | PASS | `mem` (role claims in history), Phase 04 A-15c, `arch` (provider sees only public fields); intent prompt returns a label only |
| S-07d | Clinical confirmation | PASS | `arch` (mutating tool requires confirmation); notes/renewals signed by doctors only (`mp`) |
| S-07e | Financial confirmation | PASS | Phase 04 refund approvals (human, atomic); no AI financial tool exists |
| S-07f | Secret leakage prevention | PASS with critical exception | APK/bundle scans clean; logs/reports clean; **history contains the live MongoDB credential (P5-C1, owner)** |
| S-07g | Cross-account AI memory isolation | PASS | `mem` S-05g |
| S-07h | Medical document encryption | PASS | `enc` (13); live W08a |
| S-08a | Actual provider status | PASS | `arch` S-02h, S-08a; live S-08a/S-08a2 |
| S-08b | Worker heartbeat | PASS | live W10a; Phase 04 tests (admin-only endpoint) |
| S-08c | Failed workflow visibility | PASS | live S-08c (`aiAgentRuns24h`); `uncertain` reminders visible |
| S-08d | Idempotent retry | PASS | `wh` (redelivery `already_processed`); `sch` |
| S-08e | Stuck payment recovery | PASS (local) | settle-on-status-check (Phase 02); late payment → `REVIEW_REQUIRED`; `wh` canceled intent |
| S-08f | Stuck refund recovery | PASS (local) | `wh` polling fallback (network error, then success) |
| S-08g | Notification failure reporting | PASS | live A-4/A-7; Phase 04 A-12 |
| S-08h | Security event monitoring | PASS | `sec` N08 (failed logins, brute-force signal), refresh replay event |

Totals: 65 rows (the 64 required scenarios plus a separate live-provider row): 63 PASS (7 of them with test doubles only, marked "mocked", and 2 verified locally only), 1 PASS with a critical exception (S-07f, P5-C1), 1 BLOCKED (live provider).

## 3. Cross-role workflows

| WF | Workflow | Status | Evidence | External parts |
|---|---|---|---|---|
| 01 | Doctor onboarding → approval → search → availability | PASS | Phase 04 admin UAT re-run (A-03 approval/rejection; search in Phase 01/02 scripts) | — |
| 02 | AI request → recommendation → availability → explicit confirmation → Stripe test payment → confirmed → doctor notification → admin monitoring | PASS (test mode) | Phase 02 Stripe script re-run (36 steps, 0 behavioural differences), probe P-1/P-3, Phase 04 payments | Webhook delivery BLOCKED (status check settles payments instead) |
| 03 | Two patients, one slot → one wins, alternatives, no duplicate charge | PASS | Phase 02 `concurrency_uat.py` re-run against **two backend processes (8001 and 8002)** on Phase 05 code: 5 slots × 6 concurrent attempts → exactly 1 booking each; the AI loser gets real alternatives without the other patient's details; duplicate payment intents → 1 payment (`evidence/regression/p02-concurrency-two-processes.json`) | — |
| 04 | Paid appointment → cancellation → refund request → admin approval → Stripe test refund → consistent states | PASS (test mode) | Phase 04 admin UAT re-run (A-10a–j: 4 concurrent approvals → one refund); browser A-16f | Refund webhooks BLOCKED; polling fallback tested locally |
| 05 | Confirmed appointment → consultation → note review → prescription → reminders | PASS | Phase 03 workflow re-run (44/45; D-03c test-data collision), `mp` | — |
| 06 | Care plan → test reminder → follow-up reminder → task completion → doctor progress | PASS | Phase 02 care script re-run (71 steps, 0 behavioural differences) | Push/e-mail delivery BLOCKED |
| 07 | Renewal request → doctor review → decision → notification → prescription state | PASS | Phase 03 workflow, Phase 02 care (11_renewal), `mp` | — |
| 08 | Upload → encrypted storage → treating doctor reads → unrelated doctor denied → admin denied | PASS | live W08a–e | — |
| 09 | Patient, doctor and admin natural-language requests → role tools → grounded results → no mutations | PASS | live intent probe (`evidence/intent-probe-phase05.json`), MongoDB reconciliation (63/18/3) | Live LLM BLOCKED |
| 10 | Provider failure → fallback → worker restart → persistence → no duplicate side effects | PASS (provider failure mocked) | `arch` S-02c–g, live W10a/b after two backend restarts | Live provider BLOCKED |

## 4. Regression runs on Phase 05 code (live UAT)

| Script | Result | Differences from Phase 04 |
|---|---|---|
| Phase 04 admin system (90 steps) | 88 PASS, 2 FAIL | A-01h (401 instead of 403: forged token lacks new required claims) and A-03g (401 after reinstatement): both intended Phase 05 changes; S-07a re-checks the role rule with a fully valid token |
| Phase 04 browser (Phase 05 copy) | 14/14 | session step updated for refresh (both cases tested) |
| Phase 03 doctor workflow (45) | 44/45 | D-03c, the same test-data date collision as in Phase 04 |
| Phase 03 authorization sweep (29 rows) | identical | 0 row differences |
| Phase 02 Stripe (36 steps) | completed | 0 behavioural differences (1 data difference: payment total grows) |
| Phase 02 patient care (71 steps) | completed | 0 behavioural differences (timestamps, one extra renewal from earlier runs) |
| Phase 01 probe (45 turns, 609 values) | completed | only `prefs.language` en → si on 5 Sinhala/Romanized emergency turns: intended B17 change |
| Phase 02 two-process booking race | 5/5 slots single winner; alternatives; 1 payment | same as Phase 02 |
| Phase 05 live UAT (12) | 12/12 | new |
| Intent probe (25 prompts) | see §2 S-03 / WF09 | before/after evidence |

Comparison method: `compare_regression.py` (behavioural fields compared exactly; ids, dates and counts reported separately) → `evidence/regression-comparison.json`.

## 5. Emulator (Phase 05)

The debug APK was installed on `emulator-5554` and the foreground app verified before any input (`topResumedActivity=com.mediconnect.mediconnect/.MainActivity`):
- the existing doctor session refreshed under the new token format, and the dashboard loaded live UAT data (`emu-01-launch.png`);
- Clinic workflow queue (`emu-02-clinic-workflow.png`);
- consultation preparation with readable labels and the P3-B8 shared-source summary (`emu-03-preparation.png`). Timestamps are still shown in raw ISO format, a cosmetic item left open.

Not repeated in Phase 05: the patient booking/PaymentSheet and emergency screens (no mobile code changed in those flows; verified in Phases 01–03, Flutter tests 307/307). No emergency call was placed.

## 6. Not run

Physical Android device and iPhone (B10, P3-B10); live LLM and vision (B13); Stripe webhook delivery (B3); FCM, e-mail and SMS delivery (B4, B5); clinical, pharmacist and native-language review (B1, B2, B12).
