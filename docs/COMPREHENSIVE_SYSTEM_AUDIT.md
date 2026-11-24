# MediConnect — Comprehensive System Audit

Branch `fix/comprehensive-system-ai-stabilization` · Baseline `c3e0aac` (branched from `fix/backend-mobile-ci-stabilization`) · 2026-11-24

Related documents: [MASTER_BUG_TRACKER.md](MASTER_BUG_TRACKER.md) · [AI_AGENT_VERIFICATION_MATRIX.md](AI_AGENT_VERIFICATION_MATRIX.md) · [SECURITY_AND_CLINICAL_SAFETY_REPORT.md](SECURITY_AND_CLINICAL_SAFETY_REPORT.md) · [MANUAL_UAT_TEST_PLAN.md](MANUAL_UAT_TEST_PLAN.md) · [FINAL_SYSTEM_STABILIZATION_REPORT.md](FINAL_SYSTEM_STABILIZATION_REPORT.md)

## 1. Method and limits

- Read the routing, agent, service and screen code on the paths behind every reported issue. Each root cause is recorded only where the code demonstrates it.
- Ran the repository's own CI commands as a baseline: backend pytest (319 passed), Flutter analyze and test, and admin-web lint, typecheck, test and build.
- Reproduced issues by running the reported messages through the real API (FastAPI TestClient against a local MongoDB) and turning each into a regression test.
- **Not available:** emulator or device, staging database, live Gemini/OpenAI, Stripe, FCM, SMTP or SMS. The production Atlas database was deliberately **not** queried. Findings about real data (duplicates, fee types) rely on the new read-only `backend/scripts/audit_doctor_data.py`, which the owner should run on staging.

## 2. Architecture findings

| Area | Finding |
|---|---|
| Patient AI entry point | The mobile "AI Assistant" (`ai_care_assistant_screen.dart`) uses `/ai/conversations` (persistent chats), which calls `BookingSessionService` and then `BookingAgent.process_user_turn`. A second assistant, `/ai/health-chat` (`AiHealthAssistantScreen`), uses `HealthAssistantAgent`. Two older screens (`ai_booking_assistant_screen.dart`, `ai_doctor_recommendation_screen.dart`) are still reachable from Find Doctor. |
| Routing | Before this work: a single keyword classifier where the first match won, with emergency checks limited to English regexes and exact Sinhala phrases. Now: deterministic ordering of **emergency → prescription request → health advice → multi-topic or negated-medication wellness → patient care → image → medicine → food/exercise/wellness → search/booking**. |
| LLM usage | Gemini or OpenAI function calling is used only to choose read-only doctor-search tools. It is bounded and role-filtered, with server-owned filters. All language understanding is rule-based (see the matrix). |
| Slots | `DoctorService.get_doctor_patient_slots` is the single source for the doctor calendar, patient profile, AI booking and appointment creation. Collection `doctor_availabilities` is used consistently; the historical `doctor_availability` vs `doctor_availabilities` naming issue **no longer exists**. Cancellation methods `cancel_patient_appointment` and `cancel_doctor_appointment` exist and are wired; the historical issue is **not present**. |
| Background jobs | One in-process worker (`main.py::_run_reminder_worker`) runs the care scheduler, booking-confirmation outbox and doctor communications, with lease-based recovery. |
| Admin | React + Vite + TanStack Query, wired to `/admin`, `/admin/workflow` and `/admin/analytics`. Lint, types, 32 tests and build all pass. |

## 3. Implementation status of the eight AI phases

All eight phases have real code, endpoints and tests:
- Phase 1: orchestrator and tools
- Phase 2: booking
- Phase 3: patient care
- Phase 4: doctor workflow
- Phase 5: admin automation
- Phase 6: advanced healthcare (documentation, renewals, tracking)
- Phase 7: security, monitoring and reliability
- Phase 8: final integration

The phase test files (`test_phase1` to `test_phase8`) pass. Passing these tests did **not** catch the manual-testing failures: those tests used English, exact phrases and mocked providers, and some asserted placeholder behaviour (for example, filename-based medicine identification).

## 4. Integration problems found

1. The AI tool path filtered fees with `$type: number`, while other paths used raw values, so the same doctor appeared differently in different places (BUG-008).
2. The doctor calendar ran 30 separate slot computations per month and timed out on the client (BUG-005).
3. Multipart uploads skipped token refresh, and the error mapper turned every 401 into a password error (BUG-025).
4. The Vision call used a retired model name and fell back to a placeholder (BUG-023).
5. Home hero prompts were dropped because route arguments were ignored (BUG-036).
6. The image-analysis badge never matched the backend's confidence value (BUG-033).

## 5. Missing or misleading functionality (removed)

- Fabricated outputs removed: "Generic Medicine Label"; filename-based identification; fake PNG analysis; fake weekly schedule; default LKR 2,500 charge and display; invented 4.8 rating; default "Colombo" city; "nearby Colombo" suggestion; opaque "% Match".
- Missing behaviours implemented:
  - auto-selection
  - unsupported-location handling
  - ranking by rating, experience or fee, with a minimum-rating filter
  - multi-topic wellness
  - prescription-request refusal
  - symptom guidance
  - upload progress, cancel and retry
  - Markdown rendering

## 6. Security findings

See [SECURITY_AND_CLINICAL_SAFETY_REPORT.md](SECURITY_AND_CLINICAL_SAFETY_REPORT.md). Fixed in this pass:
- Charging an invented fee (BUG-028)
- CI tests able to write to a real Atlas database (BUG-034)
- Unneeded storage of medicine photos (BUG-035)
- Gemini key sent in a URL query string
- 401 handling on uploads (BUG-025)

Still open: an in-memory rate limiter (BUG-038), the `ALLOWED_ORIGINS` default, dependency and secrets scanning, and external-provider privacy approval.

## 7. Clinical safety findings

- Emergency triage failed for Sinhala and Romanized Sinhala (BUG-013): fixed with deterministic multilingual detection that runs first in both assistants. **Clinical validation is still required.**
- Universal paracetamol dose statement (BUG-017): fixed. Formulations made explicit (BUG-016). **Pharmacist review is required.**
- Unauthorized antibiotic prescription request (BUG-018): now refused safely.
- Health questions turned into doctor search (BUG-012): general guidance with red flags is now given.

## 8. Newly discovered bugs

BUG-027 to BUG-039 (13 issues). See the tracker. The most important are BUG-028 (patients charged an invented LKR 2,500), BUG-027 (fake schedule could be saved), BUG-034 (CI against a real database) and BUG-029 (invented rating).

## 9. Data remediation plan (no automatic changes made)

The production database was not modified or read. Recommended steps:

1. **Back up** the database: an Atlas snapshot, or `mongodump` of `users`, `doctor_profiles`, `doctor_availabilities`, `appointments`, `payments`, `doctor_reviews`.
2. Run `python -m scripts.audit_doctor_data --details` against **staging restored from that backup**. It is read-only.
3. **Doctors without a usable fee:** after BUG-028 they cannot be booked (HTTP 409 with a clear message). An admin should contact each doctor and set the fee through the normal profile flow. Do not bulk-assign 2,500.
4. **Fees stored as strings:** they now work at runtime. Optionally normalize them with a reviewed one-off migration (`$set consultationFee: <number>` for each listed `_id`), keeping the old value in `consultationFeeLegacy` so it can be rolled back.
5. **Possible duplicate people** (same name and specialty on different accounts): an admin reviews each pair. Merging affects appointments, payments and reviews, so suspend the duplicate account instead of deleting it.
6. **Orphaned availability rows** (unknown `doctorProfileId`): these are already ignored by slot generation. Archive them after review.
7. **Missing unique indexes**, if the audit shows any: create them only after duplicates are resolved, otherwise index creation fails.

## 10. Evidence

| Evidence | Location |
|---|---|
| Regression tests (backend) | `backend/tests/test_comprehensive_stabilization.py` (93 tests), `backend/tests/test_availability_consistency.py` (10 tests) |
| Regression tests (Flutter) | `mobile/test/screens/ai_assistant_stabilization_test.dart` (13), `mobile/test/screens/availability_stabilization_test.dart` (3), `mobile/test/utils/money_test.dart` (3) |
| Test commands and counts | [FINAL_SYSTEM_STABILIZATION_REPORT.md](FINAL_SYSTEM_STABILIZATION_REPORT.md) |
| Commits | `git log c3e0aac..fix/comprehensive-system-ai-stabilization` |
