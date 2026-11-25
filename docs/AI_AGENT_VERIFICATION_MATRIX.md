# AI Agent & Component Verification Matrix (38 components)

Branch `fix/comprehensive-system-ai-stabilization` · 2026-11-24

## Status definitions

| Status | Meaning in this matrix |
|---|---|
| VERIFIED | Implemented, automated tests pass, **and** confirmed end-to-end on a device or live integration. |
| IMPLEMENTED BUT NOT FULLY VERIFIED | Real code paths with authorization and automated tests (mocked or local DB). Not yet confirmed on a device or with live providers. |
| PARTIALLY IMPLEMENTED | Some of the promised behaviour is missing. |
| MISSING / BROKEN | As named. |
| BLOCKED BY EXTERNAL DEPENDENCY | Final verification needs credentials, a provider or a device that was not available. |

**No component is marked VERIFIED.** This audit had no emulator or device, no live AI, Stripe, FCM, SMS or email credentials, and no staging database. All evidence below is automated: backend pytest against a local MongoDB, Flutter widget tests, and admin-web Vitest. Passing tests do not prove end-to-end behaviour on a phone.

## Addendum 2026-11-25: AI Assistant UI stabilization (`fix/uat-ai-assistant-ui-stabilization`)

The first emulator run of this project (Android 17 emulator, debug build, UAT backend on port 8001 with the deterministic provider) reproduced the UAT UI blockers and confirmed their shared root cause (BUG-043, see [UAT_UI_STABILIZATION_REPORT.md](UAT_UI_STABILIZATION_REPORT.md)). Statuses stay **IMPLEMENTED BUT NOT FULLY VERIFIED** until the manual UAT retest (P-17) on the owner's device. The emulator checklist was completed except for cancelling an upload mid-flight.

| # | Component | Change | Automated evidence | Emulator evidence (2026-11-25) |
|---|---|---|---|---|
| 1 | AI Doctor Booking Agent (assistant screen) | Layout crash fixed; one composer | `ai-ui2` (10), 37 assistant tests now run under the real app theme | 20/20 guarded cycles with 60 real messages (emergency, normal, Back while loading), 5 messages in one chat, rotation with and without the keyboard (a landscape overflow was found and fixed), image pick/remove/send: one composer throughout, 0 framework exceptions |
| 34 | Symptom Triage Engine (emergency UI) | Banner, dedicated 1990 action, confirmation dialog, dialer intent, routine chips hidden; en/si/ta strings | `ai-ui2` BUG-042 group (7) | English, Romanized Sinhala (typed) and Sinhala script (sent through the API) verified: banner, 1990, Call 1990, Cancel, dialer with no call placed. The banner language follows the reply. |
| 35 | AI Conversation Memory | Not changed | — | P-01f not tested |

## Architecture finding: how "intelligent" the agents actually are

- **Model-driven tool calling exists in one place only:** doctor search (`agents/orchestrator.py`, `agents/tool_provider.py`). It uses Gemini function calling or OpenAI tools.
  - It is bounded: 3 rounds and 4 calls per round.
  - Tools are filtered by role, arguments are validated with Pydantic, and `AISafetyGuard.validate_tool_call` runs before execution.
  - The model never sees patient identifiers; search filters are owned by the server.
  - The final list is the server's ranked search (this session's change). The model can only choose read-only lookups.
- **Everything else is deterministic and rule-based:** intent classification (`companion_intent.py`, plus the new `clinical_intent.py`), emergency detection (new `emergency_detector.py`), medicine information, wellness and symptom guidance. The LLM is not used for general language understanding, so Sinhala and Romanized Sinhala understanding covers only the vocabulary and phrasing that were tested.
- **Why this was not replaced with an LLM classifier in this pass:** the request requires that safety, permission and booking controls stay deterministic. A safe next step is an LLM-assisted intent layer that may only *propose* an intent, with the deterministic emergency, prescription and permission guards still running first. This is listed as an improvement, not done.
- **The LLM cannot run arbitrary queries, shell commands or unauthorized operations.** Tools are a fixed registry of read-only service calls, filtered by role (`tool_registry.py`). Writes such as booking holds and payments go through explicit REST endpoints that require patient confirmation.

## Matrix

Abbreviations: **Tests** = automated test files (count of test functions). **UI** = Flutter screen or admin-web page.

### Patient components

| # | Component | Status | Source | API | UI | DB collections | Tests | Known limitations / manual verification |
|---|---|---|---|---|---|---|---|---|
| 1 | AI Doctor Booking Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `agents/booking_agent.py`, `services/booking_session_service.py`, `services/ai_booking_proposal.py` | `/ai/conversations/*`, `/ai/booking/sessions/*` | `ai_care_assistant_screen.dart` | `ai_booking_sessions`, `appointments`, `payments` | test_ai_booking_agent (18), test_phase2_booking (6), stab (93 collected) | Stripe test-mode payment and the webhook to confirmation must be run manually (UAT P-05). Fixed: BUG-001/002/007/010/011/022/030 |
| 2 | AI Health Assistant Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `agents/health_assistant_agent.py`, `agents/clinical_intent.py`, `services/health_chat_service.py` | `/ai/health-chat/*` | `ai_health_assistant_screen.dart`, AI Assistant | `health_chat_sessions` | test_ai_health_chat (13), test_ai_health_companion_unified (17), stab | The Gemini-generated guidance path was not run live. Guidance text needs clinical review. Fixed: BUG-012/013/018/019/020 |
| 3 | AI Doctor Recommendation Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `agents/recommendation_engine.py`, `agents/doctor_ranking.py` | `/ai/recommendations` | `ai_doctor_recommendation_screen.dart` | `doctor_profiles`, `doctor_reviews` | test_ai_doctor_recommendations (12), stab | Fixed: BUG-021/022/028 (default fee). The recommendation engine keeps its own 0–100 score (separate screen). |
| 4 | AI Medicine Image Recognition Agent | **BLOCKED BY EXTERNAL DEPENDENCY** (code fixed) | `agents/medicine_image_agent.py` | `POST /ai/booking/sessions/{id}/image` | AI Assistant camera button | none (images are no longer stored) | stab (8 image tests), test_ai_health_companion_unified | Needs a live Gemini Vision call with the real omeprazole photo (UAT P-09) and a privacy-approved provider configuration. Fixed: BUG-023/026/035 |
| 5 | Medication Reminder Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/medication_reminder_service.py`, `services/care_scheduler.py` | `/medication-reminders/*`, `/care-automation/*` | `medication_reminders_screen.dart`, `approve_medication_schedule_screen.dart` | `medication_reminders`, care jobs | test_medication_reminders (12), test_phase3_care (5) | App-closed delivery needs FCM and a device (UAT P-07). Reminders activate only after clinician approval. |
| 6 | Patient Care Plan Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/care_plan_service.py`, `agents/patient_care.py` | `/care-plans/*` | `patient_care_plans_screen.dart`, `create_care_plan_screen.dart` | `care_plans` | test_care_plans (11) | The AI cannot change treatment; it only reads tasks. |
| 7 | Appointment Reminder Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/booking_notifications.py`, `services/notification_service.py`, worker in `main.py` | `/notifications/*` | `notifications_screen.dart` | `notifications`, outbox | test_notifications (11) | Delivery depends on FCM, email and SMS providers (BLOCKED live). |
| 8 | Follow-up Care Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/care_scheduler.py` (overdue follow-ups), `services/doctor_workflow.py` | `/doctor/workflow/*`, `/care-automation/*` | `care_agenda_screen.dart` | `care_plans`, follow-ups | test_phase4_workflow (2), test_phase3_care | Only 2 dedicated tests; more coverage recommended. |
| 9 | Medical Test Reminder Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `agents/patient_care.py` (`test` category), care agenda tool | `/care-automation/*` | `care_agenda_screen.dart` | care jobs | test_phase3_care | Runs on the shared care scheduler. |
| 10 | Personal Health Tracking Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/health_tracking_service.py` | `/clinical/measurements*` | `patient_health_tracking_screen.dart` | `health_measurements` | test_phase6_advanced_healthcare_ai (10) | Patient-reported values only; critical alerts are tested. |
| 11 | Prescription Renewal Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/prescription_workflow_service.py` | `/clinical/prescriptions/renewals*` | `prescription_renewals_screen.dart`, `doctor_prescription_renewal_queue_screen.dart` | `prescription_renewals` | test_phase6 | A renewal is only a request; a doctor must approve. |
| 12 | Patient Medical Records Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/medical_record_service.py`, `services/patient_medical_record_service.py` | `/medical-records/*`, `/clinical/records/*` | `medical_records_screen.dart`, `patient_medical_records_screen.dart` | `medical_records`, `patient_medical_records` | test_medical_records (14) | Cross-account isolation is tested. |
| 13 | Patient Notification Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/notification_service.py`, `mobile/lib/services/fcm_service.dart` | `/notifications/*` | `notifications_screen.dart` | `notifications` | test_notifications, notification_provider_test | Push delivery BLOCKED without Firebase project credentials and a device. |

### Doctor components

| # | Component | Status | Source | API | UI | DB | Tests | Notes |
|---|---|---|---|---|---|---|---|---|
| 14 | Doctor Schedule Management Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/doctor_service.py` (availability, weekly, leave, blocks, calendar) | `/doctors/me/availability`, `/doctors/me/calendar-overview`, `/doctor/*` | `manage_availability_screen.dart`, `doctor_schedule_screen.dart` | `doctor_availabilities`, `doctor_weekly_schedules`, `doctor_leaves`, `doctor_blocked_times` | test_doctor_availability_calendar (8), test_doctor_schedule (9), cons (10), avail-ui (3) | Fixed: BUG-005/006/027. Month navigation must be checked on a device (UAT D-02). |
| 15 | Consultation Preparation Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/consultation_service.py`, tool `doctor_preparation` | `/doctor/workflow/*` | `doctor_workflow_screen.dart` | `consultations` | test_phase4_workflow, test_phase6 | Read-only summary of authorized patients only. |
| 16 | Clinical Documentation Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/clinical_documentation_service.py` | `/clinical/notes/*` | `doctor_clinical_documentation_screen.dart` | `clinical_notes` | test_phase6 | AI notes are drafts until a clinician approves; versioning is in the service. |
| 17 | Prescription Assistant Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/prescription_workflow_service.py` | `/prescriptions/*`, `/clinical/*` | `create_consultation_record_screen.dart` | `prescriptions` | test_phase6 | Draft-only; a clinician signs. |
| 18 | Doctor Follow-up Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | tool `doctor_follow_ups`, `services/doctor_workflow.py` | `/doctor/workflow/follow-ups` | `doctor_workflow_screen.dart` | follow-ups | test_phase4_workflow | Limited test depth. |
| 19 | Doctor Communication Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/doctor_communications.py` (worker) | `/doctor/workflow/*` | doctor workflow | communications outbox | test_phase4_workflow | Email and SMS delivery BLOCKED live. |
| 20 | Queue Management Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | tools `doctor_queue` / `doctor_next`, `services/doctor_workflow.py` | `/doctor/workflow/queue` | `doctor_workflow_screen.dart` | `appointments` | test_phase4_workflow | |
| 21 | Doctor Analytics Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/analytics_service.py` | `/doctor/workflow/*` (doctor), `/admin/analytics/*` (admin) | `doctor_home_screen.dart` | aggregates over `appointments`, `payments` | test_health_content_and_analytics (6) | Computed from real collections, not hard-coded. |

**Phase 03 update (2026-11-25):** components 14–21 were verified live on the UAT backend and emulator. All eight are deterministic services, with no LLM; the doctor assistant routes to read-only tools only.

**Phase 04 update (2026-11-26):** admin components 22–30 were verified live:
- **Implementation:** all nine are deterministic, with no LLM, and their tools are read-only and restricted to ADMIN.
- **Fixes:** Phase 04 fixed invented figures and states in 23, 24, 25, 28, 29 and 30 (P04-N05/N11/N12/N14/N15/N16/N17).
- **Partial:** components 25 and 26 are PARTIAL:
  - 25: slot-hoarding rule not implemented; login failures not recorded.
  - 26: template drafts; no user reply.
- **Details:** see [uat/phase-04/PHASE_04_AI_AGENT_VERIFICATION_MATRIX.md](uat/phase-04/PHASE_04_AI_AGENT_VERIFICATION_MATRIX.md).
- **14, 16, 18, 19, 20, 21:** PASS.
- **15 and 17:** PASS with documented limitations.
- **Fixes:** defects P03-N01 to N24 fixed.
- **Details:** see [docs/uat/phase-03/PHASE_03_AI_AGENT_VERIFICATION_MATRIX.md](uat/phase-03/PHASE_03_AI_AGENT_VERIFICATION_MATRIX.md). Clinical approval is still pending.

### Admin components (React admin web)

| # | Component | Status | Source | API | UI page | Tests | Notes |
|---|---|---|---|---|---|---|---|
| 22 | Doctor Verification Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/doctor_verification_assistant.py`, `services/admin_service.py` | `/admin/doctors/*` | `DoctorVerificationPage.tsx` | test_admin_doctor_workflow, admin-web doctorVerification.test | A human admin approves or rejects; the AI only summarizes. |
| 23 | Admin Analytics Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/admin_analytics_assistant.py`, `analytics_service.py` | `/admin/analytics/*` | `AnalyticsPage.tsx`, `DashboardPage.tsx` | test_phase5 (11) | Real aggregates. |
| 24 | Payment Monitoring Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/payment_monitoring_service.py` | `/admin/workflow/payments/*` | `PaymentsPage.tsx`, `ReconciliationPage.tsx` | test_payment (18), test_phase5 | Live Stripe reconciliation BLOCKED (test mode only). |
| 25 | Fraud Detection Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/fraud_detection_service.py` | `/security/*` | `MonitoringPage.tsx` | test_phase7 (10) | Rule-based signals; humans decide. |
| 26 | Customer Support Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/support_ticket_service.py` | `/admin/workflow/tickets*` | `SupportTicketsPage.tsx` | test_phase5 | Drafted replies require admin send. |
| 27 | Refund Assistance Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/refund_service.py` | `/admin/workflow/refunds/*` | `RefundsPage.tsx` | test_phase5, test_payment | Stripe refunds BLOCKED live; needs a test-mode run. |
| 28 | Platform Monitoring Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/platform_monitoring_service.py` | `/security/*`, `/health/live`, `/health/ready` | `MonitoringPage.tsx` | test_phase7 | Worker heartbeat recorded by the reminder worker. |
| 29 | Notification Monitoring Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/notification_monitoring_service.py` | `/security/*`, `/admin/workflow/*` | `MonitoringPage.tsx` | test_phase7 | |
| 30 | Admin Report Generator Agent | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/admin_report_service.py`, `pdf_service.py` | `/admin/workflow/reports/*` (generate, export-csv) | `ReportsPage.tsx` | test_phase5, test_phase8 | CSV export to be checked manually (UAT A-09). |

### Shared AI and infrastructure

| # | Component | Status | Source | Tests | Notes |
|---|---|---|---|---|---|
| 31 | Central AI Orchestrator | IMPLEMENTED BUT NOT FULLY VERIFIED | `agents/orchestrator.py`, routing in `booking_agent.py` | test_phase1_orchestrator (8), stab | Routing order: emergency → prescription → health advice → multi-wellness → care → search/booking. Model tool calling only for search (see the architecture finding). |
| 32 | Gemini/OpenAI Provider | **BLOCKED BY EXTERNAL DEPENDENCY** | `agents/ai_provider.py`, `agents/tool_provider.py`, Vision in `medicine_image_agent.py` | mocked only | `.env` still names the retired `gemini-1.5-flash`; the code maps it to `gemini-flash-latest`. Live calls not made. |
| 33 | Intent Classification Engine | IMPLEMENTED BUT NOT FULLY VERIFIED | `agents/companion_intent.py`, `agents/clinical_intent.py`, `agents/nlp_parser.py` | stab (93 collected), companion tests | Rule-based; multilingual coverage limited to tested vocabulary (BUG-003/004). |
| 34 | Symptom Triage Engine | IMPLEMENTED BUT NOT FULLY VERIFIED | `agents/emergency_detector.py`, `agents/symptom_triage.py` | stab (26 positive, 12 negative, context, API) | **Clinical validation required before real patients.** |
| 35 | AI Conversation Memory | IMPLEMENTED BUT NOT FULLY VERIFIED | persistent `ai_booking_sessions.messages`, `preferences`, `routes/ai_conversations.py` | stab::bug001, test_ai_booking_agent | Memory is structured preferences plus recent turns; raw medical text is not sent to the model. |
| 36 | Notification Scheduler | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/care_scheduler.py` (lease-based jobs), worker in `main.py` | test_phase3_care, test_phase8 | Runs inside the API process. Leases prevent duplicate sends across processes; restart recovery uses `leaseUntil`. Multi-instance behaviour not load-tested. |
| 37 | Safety & Permission Guard | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/ai_safety_guard.py`, role filter in `orchestrator.py`, `middleware/auth.py`, post-generation filter in `symptom_triage.py` | test_phase7, test_production_security_audit (18), isolation tests | |
| 38 | Workflow Monitoring & Recovery | IMPLEMENTED BUT NOT FULLY VERIFIED | `services/workflow_monitoring_service.py`, `incident_management_service.py` | test_phase7, test_phase8 | |

## Placeholder and fake-functionality scan

Fabricated or misleading production behaviour was found and removed:

- "Generic Medicine Label", filename-based medicine identification, and fake PNG analysis (BUG-023).
- Fake weekly schedule fallback (BUG-027).
- Default LKR 2,500 fee charged or displayed (BUG-028/029).
- Invented 4.8 rating and "Colombo" city (BUG-029).
- Hard-coded "nearby city (e.g. Colombo)" (BUG-011).
- Opaque "% Match" score in the AI assistant (BUG-022).

No `NotImplementedError`, `UnimplementedError` or TODO/FIXME was found in production code. Mocks exist only under `tests/` (`mock_db.py`, fakes in Flutter tests).
