# MediConnect — Final Verification Matrix: All 38 AI Components

_Final consolidated copy of `phase-05/PHASE_05_ALL_38_AGENT_VERIFICATION_MATRIX.md` (state after all five phases)._

For: the project owner and reviewers. 2026-11-26, branch `fix/phase-05-final-ai-security-integration`.

## How to read this matrix

**Final status values:**
- **VERIFIED (local):** implemented and verified with automated tests and the live local UAT backend, or the emulator/browser where relevant. No external provider, clinician or physical device was involved.
- **PARTIAL:** implemented and locally verified, but part of the component depends on something unavailable (external delivery, live LLM, missing product scope).
- **BLOCKED:** the component's core purpose needs an external service that was not available.

**Other markers:**
- **Clinical review** / **pharmacist review** / **owner decision:** additional human gates. No component has clinical approval.
- **LLM-driven:**
  - "No" means rules, database queries and validated tools only.
  - "Bounded" means an LLM may propose labels, preferences or read-only tool calls that the server validates. Every LLM path was exercised only with test doubles in Phase 05 (providers disabled in UAT).

**Test references:** `P05` = Phase 05 backend test files. Earlier phases' tests are named by file. "Live" = the UAT backend on 127.0.0.1:8001 with `mediconnect_uat` (Phase 05 re-runs). "Emu" = Android emulator. "Browser" = admin web in Chrome.

## Patient components

| ID | Name | Role | Implemented | Deterministic | LLM-driven | Actual tests | Local integration | Live provider | Emulator/Browser | Safety | Remaining blockers | Final status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | Appointment Booking Agent | Patient | Yes | Search, ranking, holds, payment, confirmation | Bounded (provider may pick public read-only tools; final list always from the trusted search) | test_ai_booking_agent, test_phase2_booking, test_phase02_booking_payment, P05 `mem`, `arch` S-01 | Live: Phase 02 Stripe script (36 steps) re-run, intent probe P-1–P-3 | Not run (B13) | Emu (Phase 01–03); Phase 05 app launch | Explicit confirmation before hold and payment; no booking from AI text | Stripe webhook delivery (B3); live LLM (B13) | PARTIAL |
| 02 | Health Assistant | Patient | Yes | Triage pre-check, advice templates, refusals | Bounded (Gemini guidance text, provider disabled) | test_ai_health_chat, stab, P05 `emg` | Live: Phase 01 probe (45 turns) re-run, 0 unintended differences | Not run | Emu (Phase 01) | Emergency first; no diagnosis or dosing | Clinical review (B1); live LLM (B13) | PARTIAL · clinical review |
| 03 | Doctor Recommendation Agent | Patient | Yes | Ranking, fee/rating filters, explanations | Bounded preference proposal | test_ai_doctor_recommendations, Phase 01 tests | Live: probe P-1, P-2, P-3, P-8 | Not run | Emu (Phase 01) | Only verified doctors; real fees | Sinhala review (B12) | VERIFIED (local) |
| 04 | Medicine Image Analysis Agent | Patient | Yes | Refusal rules (no identity from loose tablets) | Vision provider (disabled) | stab image tests; P05 gateway tests | Disabled path only | Not run | — | Never invents an identity; photos encrypted at rest (B8) | Live vision + data agreement (B13) | BLOCKED |
| 05 | Medication Reminder Agent | Patient | Yes | Clinician-approved schedules only | No | test_phase3_care, test_medication_reminders, P05 `sch`, `int` (B16, medicine times) | Live: Phase 02 care script (71 steps) re-run; probe P-5, P-9 | — | Emu (Phase 02) | No AI schedule changes; B16 reply | FCM delivery (B4); pharmacist review (B2) | PARTIAL |
| 06 | Care Plan Assistant | Patient/Doctor | Yes | Tasks, progress | No | test_care_plans, test_phase3_care, P05 `mp` (lost update fixed) | Live care script | — | Emu (Phase 02/03) | Reads tasks only; clinician authors | Clinical review | VERIFIED (local) · clinical review |
| 07 | Appointment Reminder Agent | Patient | Yes | 24 h / 2 h reminders, Colombo time | No | test_notifications, P05 `sch` (boundary, exactly-once) | Live: W10b no duplicates | — | — | Private message text | Push/e-mail/SMS delivery (B4/B5) | PARTIAL |
| 08 | Follow-up Reminder Agent | Patient | Yes | Due / 1 day / 7 days | No | test_phase4_workflow, test_phase3_care | Live care script | — | — | — | Delivery (B4/B5) | PARTIAL |
| 09 | Medical Test Reminder Agent | Patient | Yes | Care-agenda `test` tasks | No | test_phase3_care, P05 `int` (medical tests intent) | Live probe P-6 (was clarification, now agenda) | — | — | — | Delivery (B4/B5) | PARTIAL |
| 10 | Health Tracking Agent | Patient | Yes | Validation, alerts, trends | No | test_phase6, P05 `meas` (B7 crash fixed) | Live care script | — | Emu (Phase 02) | Patient-reported provenance kept | Alert thresholds clinical review | VERIFIED (local) · clinical review |
| 11 | Prescription Renewal Agent | Patient/Doctor | Yes | Request → clinician decision | No (one mutating tool requires confirmation) | test_phase03_doctor_system, P05 `mp` (one prescription across processes), `arch` | Live Phase 03 workflow (44/45) | — | Emu (Phase 03) | Doctor approves; AI cannot | Pharmacist review | VERIFIED (local) · pharmacist review |
| 12 | Medical Records Assistant | Patient/Doctor | Yes | Records, summaries with sources | No | test_medical_records, P05 `enc`, `lists` | Live W08a–e (encrypted, access by content) | — | — | Encryption at rest; care-relationship checks; admin denied | Production key management | VERIFIED (local) |
| 13 | Notification Assistant | Patient | Yes | In-app store, preferences | No | test_notifications, notification_provider_test | Live monitoring (channels not configured) | — | — | Private content only | FCM (B4) | PARTIAL |

## Doctor components

| ID | Name | Role | Implemented | Deterministic | LLM-driven | Actual tests | Local integration | Live provider | Emulator/Browser | Safety | Remaining blockers | Final status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 14 | Doctor Schedule Assistant | Doctor | Yes | Availability, leave, blocks | No | test_doctor_schedule, test_doctor_availability_calendar, P05 `mp` (blocked time) | Live Phase 03 workflow | — | Emu (Phase 03) | Conflict checks; unique blocks | Device check (P3-B10) | VERIFIED (local) |
| 15 | Consultation Preparation Agent | Doctor | Yes | Source lists, missing-information list | No | test_phase03_doctor_system, P05 `meas` (P3-B8) | Live probe D-3 | — | **Emu (Phase 05): labelled preparation with shared sources** | Care relationship required; no diagnosis | Clinical review; scope of other clinicians' notes (owner) | VERIFIED (local) · clinical review |
| 16 | Clinical Notes Assistant | Doctor | Yes | Draft organization, NOT_DOCUMENTED placeholders | No | test_phase03_doctor_system, test_phase6, P05 `mp` (single signature) | Live Phase 03 workflow | — | Emu (Phase 03) | Draft until signed; no invented findings | Clinical review | VERIFIED (local) · clinical review |
| 17 | Prescription Assistant | Doctor | Yes | Allergy/active-medication checks against records | No | test_phase03_doctor_system, test_phase6 | Live Phase 03 workflow | — | Emu (Phase 03) | Clinician signs | Drug-interaction source (P3-B9); pharmacist review | PARTIAL |
| 18 | Follow-up Care Generator | Doctor | Yes | Interval parsing, proposed date | No | test_phase4_workflow, test_phase03 | Live probe D-2, D-7 | — | Emu (Phase 03) | Doctor reviews before saving | — | VERIFIED (local) |
| 19 | Patient Communication Assistant | Doctor | Yes | Reminder drafts, token-approved batches | No | test_phase4_workflow | Live Phase 03 workflow | — | — | Approval token | E-mail/SMS delivery (B5) | PARTIAL |
| 20 | Appointment Queue Manager | Doctor | Yes | Queue order, check-in | No | test_phase4_workflow, test_phase03 | Live Phase 03 workflow | — | Emu (Phase 05 queue screen) | Owned appointments only | — | VERIFIED (local) |
| 21 | Doctor Analytics Assistant | Doctor | Yes | Counts, refund-aware money | No | test_phase03, P05 `int` | Live probe D-5 | — | Emu (labels, P3-B7) | Numbers only from the service | — | VERIFIED (local) |

## Admin components

| ID | Name | Role | Implemented | Deterministic | LLM-driven | Actual tests | Local integration | Live provider | Emulator/Browser | Safety | Remaining blockers | Final status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 22 | Doctor Verification Assistant | Admin | Yes | Document completeness, registration format | No | test_admin_doctor_workflow, test_phase04_admin_system, P05 `enc` (view audit) | Live Phase 04 admin (88/90, 2 intended changes); probe A-1, A-6 | — | Browser 14/14 | Human decision; document views audited | Official registry check (manual) | VERIFIED (local) |
| 23 | Platform Analytics Assistant | Admin | Yes | Refund-aware aggregates, Colombo ranges | No | test_phase5, test_phase04, P05 `int` (N19) | Live probe A-3, A-8; MongoDB match (63/18/3) | — | Browser | Figures from tools only | Revenue model (P4-B7) | VERIFIED (local) |
| 24 | Payment Monitoring Agent | Admin | Yes | Reconciliation rules | No | test_payment, test_phase04, P05 `wh`, `lists` | Live Phase 04 admin; Stripe test mode | — | Browser | Review, never auto-confirm | Webhook delivery (B3) | VERIFIED (local) |
| 25 | Fraud Detection Agent | Admin | Yes | Rule-based signals; failed-login signal (new) | No | test_phase7, test_phase04, P05 `sec` N08, `int` | Live probe A-5 | — | Browser | Signals, never account action | Slot-hoarding rule not implemented | PARTIAL |
| 26 | Customer Support Assistant | Admin | Yes | Template drafts | No | test_phase5, test_phase04 | Live Phase 04 admin | — | Browser | Admin sends | Patient replies/mobile UI (P4-B8 scope) | PARTIAL |
| 27 | Refund Management Agent | Admin | Yes | Policy amounts, atomic claims, webhook states | No | test_phase04, P05 `wh` | Live: 4 concurrent approvals → 1 Stripe test refund | — | Browser A-16f | Human approval; idempotency | Webhook delivery (B3); policy (B6) | VERIFIED (local) |
| 28 | System Monitoring Agent | Admin | Yes | Measured statuses, AI run counts | No | test_phase7, P05 `arch` S-08a | Live S-08a, S-08c, probe A-9 | — | Browser A-11-ui | No invented "healthy" | — | VERIFIED (local) |
| 29 | Notification Monitoring Agent | Admin | Yes | Outbox/reminder state counts | No | test_phase04, P05 `sch` (uncertain visible) | Live probe A-4, A-7 | — | Browser | Unconfigured ≠ delivered | Delivery providers (B4/B5) | VERIFIED (local) |
| 30 | Report Generation Agent | Admin | Yes | Report metrics, safe CSV | No | test_phase5, test_phase04 | Live Phase 04 admin (A-13) | — | Browser A-13-ui | Exports audited; CSV injection escaped | — | VERIFIED (local) |

## Shared components

| ID | Name | Role | Implemented | Deterministic | LLM-driven | Actual tests | Local integration | Live provider | Emulator/Browser | Safety | Remaining blockers | Final status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 31 | Agent Orchestrator | All | Yes | Bounds, validation, role allow-lists | Bounded tool rounds | test_phase1_orchestrator, P05 `arch` S-01a–h | Live: `ai_agent_runs` counted (S-08c) | Not run | — | Never grants permissions; mutating tools need confirmation | Live LLM loop (B13) | VERIFIED (local) |
| 32 | Provider Management | All | Yes | Gateway, limits, breaker, categories, status | Provider adapters | P05 `arch` S-02a–h (test doubles) | Live: status `not_configured` (correct for UAT) | **Not run** | — | Header-only keys; no content logged | Rotated keys + authorization (B13, P4-B2) | BLOCKED (live) · mocked verification complete |
| 33 | Intent Classification | All | Yes | Multilingual role schemas | Bounded proposal (test double) | P05 `int` (45) | Live probe: patient 9/9, doctor 6/7 (D-3 needs a selection), admin 9/9 | Not run | — | Labels only; emergency first | Native-language review (B12) | VERIFIED (local) · language review |
| 34 | Emergency Triage | Patient | Yes | Multilingual detection, context, crisis lines | No | stab, Phase 01 tests, P05 `emg` (12) | Live Phase 01 probe re-run (B17 change intended) | — | Emu (Phase 01); dialer confirmation widget tests | Verified numbers only (1990, 1926, 1333); dialer never calls | Clinical approval (B1) | VERIFIED (local) · clinical review |
| 35 | Conversation Memory | Patient | Yes | Structured preferences, ownership | No | stab, P05 `mem` (9) | Live probe P-3 (context) | — | Emu (Phase 01) | Cross-account 404; no permission from history | Retention decision (owner) | VERIFIED (local) |
| 36 | Scheduler | All | Yes | Leases, deterministic ids, Colombo dates | No | test_phase3_care, P05 `sch` (6, incl. 3 OS processes) | Live W10a/b | — | — | At-most-once external delivery; `uncertain` visible | Delivery providers (B4/B5); P05-O1 observation | VERIFIED (local) |
| 37 | Safety and Permission Guard | All | Yes | AISafetyGuard, role checks, prompt-injection handling | No | test_phase7, test_production_security_audit, P05 `sec`, `arch`, `mem` | Live authz sweep identical to Phase 04; SEC-a/b | — | Browser A-01c/d | Tool and HTTP authorization both enforced | — | VERIFIED (local) |
| 38 | Workflow Monitoring and Recovery | Admin | Yes | Stuck workflows, run records, pending-refund recovery | No | test_phase7, test_phase8, P05 `wh`, `arch` | Live S-08a/c | — | Browser | Bounded retries; no blind financial retries | Webhook delivery (B3) | VERIFIED (local) |

## Totals

| Final status | Count | Components |
|---|---|---|
| VERIFIED (local) | 25 | 03, 06, 10, 11, 12, 14, 15, 16, 18, 20, 21, 22, 23, 24, 27, 28, 29, 30, 31, 33, 34, 35, 36, 37, 38 |
| PARTIAL | 11 | 01, 02, 05, 07, 08, 09, 13, 17, 19, 25, 26 |
| BLOCKED | 2 | 04 (vision), 32 (live provider) |
| **Total** | **38** | |

Of the 25 VERIFIED (local) components, seven carry an additional human gate: clinical, pharmacist or language review (06, 10, 11, 15, 16, 33, 34).

**No component is verified against a live LLM, a clinician, a pharmacist or a physical device.** Seven components have a bounded, optional LLM path (01, 02, 03, 04, 31, 32, 33); the other 31 are deterministic. Critical clinical and financial operations (booking confirmation, payment, refund, prescription, note signing, approvals, suspensions) stay deterministic and human-controlled: an LLM error there would mean wrong money or wrong care, and every such action already has a clear rule and an accountable human.
