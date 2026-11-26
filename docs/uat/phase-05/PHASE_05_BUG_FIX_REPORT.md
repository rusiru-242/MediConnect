# Phase 05 — Bug Fix Report

For: the project owner and engineers. 2026-11-26. Every defect below was reproduced (failing test, live probe or failing run before the fix), fixed, and covered by a regression test that passes. IDs are new and collision-free (`P05-Nxx`); historical aliases are listed. Improvements, missing features and policy items are listed separately in §3.

Test file abbreviations (all under `backend/tests/` unless stated): `sec` = `test_phase05_security.py`, `enc` = `test_phase05_document_encryption.py`, `int` = `test_phase05_intents.py`, `arch` = `test_phase05_ai_architecture.py`, `emg` = `test_phase05_emergency.py`, `mem` = `test_phase05_memory.py`, `sch` = `test_phase05_scheduler.py`, `mp` = `test_phase05_doctor_multiprocess.py`, `meas` = `test_phase05_measurements.py`, `wh` = `test_phase05_stripe_webhooks.py`, `lists` = `test_phase05_lists.py`, `ses` = `admin-web/src/test/phase05Session.test.tsx`.

## 1. Defects

| ID | Alias | Sev. | Component | Reproduction → actual | Expected | Root cause | Fix (files) | Regression test | Status |
|---|---|---|---|---|---|---|---|---|---|
| P05-N01 | P4-B5 | High | Config / DB safety | Backend started with `backend/.env` and no `ENVIRONMENT` → used the remote cluster silently | Development refuses a remote DB unless deliberately allowed | `ENVIRONMENT` defaulted to development with no target rule | `config/runtime_safety.py`, `config/database.py`, `main.py` | `sec` N01 (11 cases, subprocess with the `.env` shape, MongoClient never built) | FIXED, VERIFIED (tests) |
| P05-N02 | — | High | Auth | 8 concurrent refreshes with one token → several 200s | exactly one rotation | unconditional `update_one` on rotation | `auth_service.py` (conditional claim, replay → family revoke) | `sec` N02 (1×200/7×401; replay); live SEC-a | FIXED, VERIFIED (live) |
| P05-N03 | — | Medium | Auth | refresh token of a deleted account → 500 (`NoneType.get`) | 401 | user read before None check | `auth_service.py` | `sec` N03 | FIXED |
| P05-N04 | P4-B2 (technical part) | High | Config / JWT | 11-character common-word secret accepted outside production | refuse weak/default secrets except in tests | strength checked only in production | `runtime_safety.py` | `sec` N04 (8 cases) | FIXED |
| P05-N05 | — | Medium | Auth | tokens without `iss`/`aud`/`jti` accepted | required claims | decode required only `exp, iat, sub, role` | `utils/security.py` | `sec` N05 (missing/wrong claims, `alg=none`, expiry) | FIXED |
| P05-N06 | — | Medium | Auth | logout → access token still worked for up to 60 min | revoked at logout | refresh-only revocation | `auth_service.py`, `middleware/auth.py`, `models/token.py` (TTL deny-list) | `sec` N06; live SEC-b | FIXED, VERIFIED (live) |
| P05-N07 | — | Medium | Auth | token issued before suspension worked again after reinstatement | stays invalid | no issue-time cut-off | `admin_service.py`, `auth_service.py` (`tokensValidAfter`) | `sec` N07; Phase 04 A-03g now 401 (intended) | FIXED |
| P05-N09 | BUG-038 | Medium | Rate limiting | limits multiplied by the number of processes; reset on restart | shared limits | in-process dicts | `utils/rate_limiter.py` (MongoDB counters, TTL, hashed keys) | `sec` N09 (two instances; 3 OS processes → exactly 10 rejections) | FIXED |
| P05-N10 | P4-O8 | Low | API | security router mounted at `/api` and root | API under `/api` only; probes at both | duplicate `include_router` | `main.py`, `routes/security_monitoring.py` (`probe_router`) | `sec` N10 | FIXED |
| P05-N11 | — | Medium | Medical records | upload with unknown `recordType` → 500 after the file was written (orphan file); admins could upload "patient" records for themselves | 422 before any write; 403 for non-patients/doctors | validation after the write | `patient_medical_record_service.py` | `enc` N11 | FIXED |
| P05-N12 | — | High | AI providers | Gemini parser and health assistant sent the API key as `?key=` | key only in headers | URL-based auth | `ai_provider.py`, `health_assistant_agent.py`, `provider_gateway.py` | `arch` S-02a (URL has no key) | FIXED |
| P05-N13 | — | Medium | AI monitoring | provider metrics and circuit breaker never changed | fed by every call | `record_*` never called | `provider_gateway.py` | `arch` S-02c–h, S-08a | FIXED |
| P05-N14 | — | Medium | AI providers | health assistant mapped model names to the retired `gemini-1.5-flash` | maintained alias, remap reported | inverted mapping | `provider_gateway.resolve_gemini_model` | `arch` S-02a | FIXED |
| P05-N15 | — | Medium | Conversation memory | "cardiologist in Atlantis" → "in Colombo then" → clarification, city lost | city refined, specialty kept | filler words defeated the city-only check | `booking_agent.py` | `mem` S-05c | FIXED |
| P05-N16 | — | Low | Scheduler | with an injected clock, live leases were judged expired and set to `uncertain` mid-delivery | one clock for lease and expiry | lease from wall clock, expiry from run clock | `care_scheduler.py` | `sch` S-06d/e (3 processes, exactly once) | FIXED |
| P05-N17 | — | Medium | Doctor schedule | 4 processes creating the same block → 4 identical blocks (sequential duplicates too) | one block, 409 for the rest | no uniqueness | `doctor_service.py`, `models/doctor_blocked_time.py` (sparse unique `blockKey`, post-insert booking re-check) | `mp` blocked time | FIXED |
| P05-N18 | B7 | High | Health tracking | after one Care Agenda reading, `GET /clinical/measurements` (patient and doctor) → unhandled ValidationError | both entry points listed in order | two document shapes in one collection; strict model; sort by `measuredAt` only | `health_tracking_service.py` (read-time normalization, server-side ordering), `care_automation.py` (new rows complete) | `meas` (2 tests) | FIXED |
| P05-N19 | — (introduced in Phase 05) | Medium | Admin assistant | "successful payments this week" said "39 (13 of them refunded)", but those 13 were not part of the 39 (fully refunded payments are counted separately) | captured = succeeded + refunded | `succeededTransactions` excludes refunded | `routes/admin_workflow.py` | `int` N19; live re-check matches MongoDB exactly (63 captured, 18 refunded, 3 failed; `evidence/p05-n19-live-reconciliation.json`) | FIXED before release |
| P05-N20 | — | High | Care plans | 4 concurrent updates all 200, version +3 (one update lost) | no silent lost update | unconditional write after reading the version | `care_plan_service.py` (version-conditional write, 409) | `mp` care plan (3 repeated races) | FIXED |
| P05-N21 | B17 | Medium | Emergency triage | Sinhala chest-pain emergency, then "ok" → English emergency text | Sinhala continues | emergency branch never stored the language | `booking_agent.py` (`emergencyLanguage`) | `emg` S-04e (fails without the fix) | FIXED |
| P05-N22 | B16 | High | Patient assistant | "change my dose to two tablets" → medicine-database lookup | explain that the prescriber decides; change nothing | no intent for dose changes | `intent_router.py`, `booking_agent.py` | `int` B16; live probe P-9 | FIXED; pharmacist review pending (B2) |
| P05-N23 | — | Medium | Patient assistant | "When should I take the medicine prescribed by my doctor?" → prescription refusal | the patient's approved schedule | prescription-request rule ran first | `intent_router.py`, `booking_agent.py`, `patient_care.py` | `int`; live probe P-5 | FIXED |
| P05-N24 | P4-O1 | Medium | Medical records | one malformed record → whole list 500 | other records shown; unreadable ones reported | per-row strict validation | `patient_medical_record_service.py`, schema | `lists` P4-O1 | FIXED |
| P05-N25 | P4-O7 | Medium | Payments | reconcile-refund (an admin financial action) not audited | audited | missing audit call | `routes/payment.py` | `wh` reconcile audit | FIXED |
| P05-N26 | — (exposed by the 15-min default) | Medium | Admin web | admins would be signed out on every access-token expiry; logout cleared the token before calling the API, so the access token was never revoked | refresh once, retry; revoke on logout | no refresh logic; wrong order | `admin-web/src/api/client.ts`, `context/AuthContext.tsx` | `ses` (2 tests); browser P05-REFRESH-ui | FIXED, VERIFIED (browser) |

(P05-N08 is an improvement, listed in §3.)

## 2. Defects found by the new multi-process and live checks

Four defects (N17, N19, N20 and the measurement crash N18) were not visible to single-process tests or earlier UAT. They were found by:
- the P3-B11 multi-process harness;
- the MongoDB reconciliation of the live probe;
- an explicit Care Agenda + Health Tracking scenario.

N20 passed once by timing and failed in a later full run, which is why the race tests are repeated three times after each fix.

## 3. Improvements and missing features delivered (not defects)

| ID | Item | Alias |
|---|---|---|
| P05-N08 | Privacy-preserving failed-login telemetry and brute-force signal (no lockout) | P4-B9, P4-O5 |
| P05-I01 | Application-level document encryption, key rotation, reversible migration script, document-view audit | B8 |
| P05-I02 | Shared role-specific intent router (patient, doctor, admin); admin intents for payments, notifications, fraud, health; doctor renewal queue | Component 33 |
| P05-I03 | Orchestrator bounds (total calls, duplicates, tool timeout, result validation, mutating-tool confirmation, loop detection, run records) | Component 31 |
| P05-I04 | Provider gateway (limits, circuit breaker, categories, metrics, truthful status) | Component 32 |
| P05-I05 | Stripe webhook event log, `payment_intent.canceled`, refund events, pending-refund polling fallback | B3, P4-B10 |
| P05-I06 | Consultation preparation with shared authorized sources and missing-information list | P3-B8 |
| P05-I07 | Readable labels in the doctor workflow screen | P3-B7 |
| P05-I08 | Admin CSP, no third-party fonts; dev API target 8001 | P4-O3, P4-B3 |
| P05-I09 | Admin list paging in MongoDB + two indexes | P4-O4 |
| P05-I10 | Dependency minimum versions raised; non-breaking npm fixes | — |
| P05-I11 | `CONVERSATION_RETENTION_DAYS` (default unchanged) | — |
| P05-I12 | Read-only P4-B6 reconciliation report (UAT) | P4-B6 |

## 4. Changed test expectations (justified)

| Test | Old → new | Reason |
|---|---|---|
| `test_phase1_orchestrator::test_round_limit_and_provider_failure` | identical call repeated 3 rounds → round limit now exercised with varied calls; identical repeats stop after 1 execution | loop detection and duplicate prevention (component 31) |
| `admin-web/src/test/auth.test.tsx` | dev default `localhost:8000` → `127.0.0.1:8001` | P4-B3 |
| `mobile/test/screens/doctor_workflow_screen_test.dart` | `pending: 1` → `Pending: 1` | P3-B7 labels |
| Phase 04 live A-01h (expects 403) | forged token without the new claims → 401 | stronger claim validation; a fully valid forged role token still gets 403 (`sec` S-07a) |
| Phase 04 live A-03g (expects 200 after reinstatement) | 401 | intended: tokens issued before suspension stay invalid (N07) |
| Phase 04 browser A-01c-ui | invalid access token → login | now refreshes when the refresh token is valid; Phase 05 copy tests both cases |

## 5. Observation (not resolved)

P05-O1: `test_phase3_care::test_medication_approval_delivery…` failed once in a full run with 6 reminder rows for one schedule (expected 1). It passed in 8 consecutive targeted runs and in 4 later full runs. The new multi-process scheduler tests did not reproduce duplicates, and a duplicate check on the UAT database found 0. The cause is not established; possibly the module's reused `mediconnect_phase3_test` database. It is left open, with the diagnostic message added to the assertion.
