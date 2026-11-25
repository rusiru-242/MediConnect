# Phase 03 — Doctor System Inventory

For: the project owner, reviewers and the Phase 04/05 teams. 2026-11-25 · branch `fix/phase-03-doctor-system-stabilization`.

**How this was built:**
- **Sources:** the running UAT backend's OpenAPI listing (`127.0.0.1:8001/openapi.json`), the route, service and model code, `mobile/lib/main.dart` routes, and the mobile services.
- **Labels:**
  - **Implemented** means code exists and was exercised in Phase 03.
  - **Placeholder** means UI with no data source.
  - **Not implemented** means requested but absent.
- **Classification:** no deterministic workflow is described as an autonomous LLM agent.

## 1. Feature map

Feature → Flutter screen → API endpoint → service → collection → permission rule → test coverage

| Feature | Flutter screen | API endpoint(s) | Service | Collection(s) | Permission rule | Tests (Phase 03 evidence) |
|---|---|---|---|---|---|---|
| Registration and application status | `doctor_registration_screen`, `doctor_application_status_screen`, `doctor_application_submitted_screen` | `POST /auth/register-doctor`, `GET /doctors/me/application-status` | `auth_service`, `doctor_service` | `users`, `doctor_profiles` | Any doctor account, including PENDING; rejected and suspended accounts cannot log in (403) | D-01b, D-01b2; sweep |
| Login, refresh, logout | Login screen | `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me` | `auth_service` | `users`, refresh tokens | JWT HS256; expired or forged tokens give 401 | D-01a, D-01a2, D-01d |
| Doctor home ("Today", operations) | `doctor_home_screen`, `widgets/doctor_today_overview` | `GET /doctors/me/appointments?date=` | `appointment_service.list_doctor_appointments` | `appointments`, `payments` | Approved, active doctor; own appointments only | D-02a/b/c/d; emulator EM-01/02 |
| Availability (date windows) | `manage_availability_screen`, `add_availability_screen` | `/doctors/me/availability` (GET, POST, PUT, DELETE) | `doctor_service` | `doctor_availabilities` | Owner only; edits and removal blocked while bookings would fall outside (P03-N21) | D-03a–g |
| Weekly schedule, leave, blocked time, calendar | `manage_availability_screen`, `doctor_schedule_screen` | `/doctors/me/weekly-schedule`, `/doctors/me/leave`, `/doctors/me/blocked-time`, `/doctors/me/calendar-overview`, `POST /doctor/workflow/blocked-time` | `doctor_service` | `doctor_weekly_schedules`, `doctor_leaves`, `doctor_blocked_times` | Approved doctor; leave that conflicts with bookings needs explicit `resolveConflicts` | D-03a, D-03e; existing suites |
| Patient-visible slots | (patient) doctor detail, AI booking | `GET /doctors/{id}/availability` | `doctor_service.get_doctor_patient_slots` | as above plus `appointments` | Authenticated; approved doctors only | D-03c, D-03f, D-03f2 |
| Appointment list and detail | `doctor_appointments_screen`, `doctor_appointment_detail_screen` | `GET /doctors/me/appointments`, `GET /appointments/doctor/list`, `GET /appointments/{id}` | `appointment_service` | `appointments`, `payments`, `refund_requests` | Own appointments; another doctor gets 403 | D-04a/b/c, D-01c |
| Confirm, complete, cancel | appointment detail | `POST /doctors/me/appointments/{id}/confirm`, `…/complete`, `…/cancel`, `PUT /appointments/{id}/status` | `appointment_service` | `appointments`, `appointment_events`, `refund_requests`, `payments` | Owner; confirm only when PAID or NOT_REQUIRED; complete only after the start time; conditional updates | D-04d/e/f; `test_n03/n04/n05` |
| Reschedule | (patient and doctor) | `POST /appointments/{id}/reschedule` | `appointment_service` | `appointments`, `appointment_events` | Patient, owning doctor or admin; real open slot only | D-04g |
| Daily schedule and consultations | `doctor_schedule_screen`, `consultation_details_screen`, `doctor_consultations_screen` | `/doctor/schedule`, `/doctor/schedule/today`, `/doctor/schedule/summary`, `/doctor/consultations/{id}` (+ `/start`, `/complete`) | `consultation_service` | `appointments`, `consultation_sessions` | Approved doctor and owner; start only on CONFIRMED (P03-N01) | D-04e, D-11e; `test_n01`, UI tests |
| Clinic queue | `doctor_workflow_screen` | `GET /doctor/workflow/queue`, `POST /doctor/workflow/queue/{id}` | `doctor_workflow` | `appointments.clinicQueue`, `clinicQueueAudit` | Owner; CONFIRMED today; versioned and idempotent (`requestId`); explicit `confirm: true` | D-11a–e |
| Consultation preparation | `doctor_workflow_screen` (Preparation) | `GET /doctor/workflow/preparation/{id}` | `doctor_workflow.preparation` | `medical_records`, `prescriptions`, `care_plans` (doctor's own) | Owner of a non-cancelled visit | D-05a/b/c |
| Clinical records (documents, entries, summary) | `medical_records_screen` (patient), doctor via API | `/clinical/records…` | `patient_medical_record_service` | `patient_medical_records`, files in `uploads/medical_documents` | Patient (own) or a doctor with a care relationship (P03-N02/N17); admin read (policy for Phase 04/05) | D-05d; sweep; `test_n02`, `test_n14` |
| SOAP clinical notes | `doctor_clinical_documentation_screen` (reachable since P03-N23) | `/clinical/notes/draft`, `/{id}/draft`, `/{id}/sign`, `/{id}/amend`, `GET /clinical/notes` | `clinical_documentation_service` | `clinical_notes` | Author only for edit, sign and amend; other related doctors see signed notes only (P03-N11) | D-06a–e |
| Consultation record + prescription (Phase 21 flow) | `create_consultation_record_screen` | `POST /medical-records`, `POST /prescriptions`, `PATCH …`, `GET /prescriptions/{id}/pdf` | `medical_record_service` | `medical_records`, `prescriptions` | Owning doctor; record only once the visit has started (P03-N12); prescription must match its record | R7/R7b/R8/R9; `test_n07_n13` |
| Signed prescription (clinical flow) and assistant review | `consultation_details_screen` → schedule approval | `POST /clinical/prescriptions/sign`, `POST /clinical/prescriptions/assistant-review` | `prescription_workflow_service`, `clinical_safety_service` | `prescriptions` | Approved doctor with a care relationship; cited visit validated | D-07a/b/d |
| Medication reminder schedule approval | `approve_medication_schedule_screen` | `PUT/DELETE /care-automation/prescriptions/{id}/schedule…`, `GET …/activity` | `routes/care_automation`, `care_scheduler` | `medication_reminders`, `care_reminder_events` | Prescriber only; times must match the prescribed frequency and duration | D-07c; Phase 02 C05 |
| Prescription renewals | `doctor_prescription_renewal_queue_screen` (reachable since P03-N23) | `/clinical/prescriptions/renewals` (GET, POST), `/{id}/review` | `prescription_workflow_service` | `prescription_renewals`, `prescriptions` | Patient requests; only the prescriber reviews; atomic review lock | D-07e/f |
| Care plans and follow-ups | `create_care_plan_screen`, `doctor_workflow_screen` (Follow-ups) | `/care-plans…`, `GET /doctor/workflow/follow-ups` | `care_plan_service`, `doctor_workflow` | `care_plans` | Approved doctor on a CONFIRMED/COMPLETED visit (P03-N17); patient completes tasks | D-08a–e, D-09b/c |
| Doctor reminder batch (communication) | `doctor_workflow_screen` (Tomorrow's reminders) | `GET/POST /doctor/workflow/reminders/{day}` | `doctor_communications` (worker) | `doctor_communication_events`, `notifications` | Own CONFIRMED visits; consented patients only; HMAC token; explicit confirm | D-10a–d |
| Analytics | `doctor_workflow_screen` (Analytics) | `GET /doctor/workflow/analytics` | `doctor_workflow.analytics`, `financials` | `appointments`, `payments`, `refund_requests`, `consultation_sessions` | Own data; up to 31 days | D-12a–d |
| Doctor assistant | `doctor_workflow_screen` (Ask) | `POST /doctor/workflow/assistant` | `routes/doctor_workflow.assistant` → `AIOrchestrator.execute` → `agents/tool_registry` | read-only, via tools | Approved doctor; restricted tool set; validated arguments | D-14a–c |
| Notifications | `notification_screen`, FCM routing (`fcm_service`) | `/notifications…` | `notification_service` | `notifications` | Recipient only | D-13a–d; Phase 02 BUG-060 |
| Reviews and ratings | `doctor_reviews` screens | `/doctors/{id}/reviews`, `/rating-summary` | `review_service` | `reviews` | Public read | Existing suites |

## 2. Status by kind

| Kind | Items |
|---|---|
| Implemented and exercised | Everything in §1 |
| Fixed placeholders (P03-N16, N24) | Specialty and status fallbacks, the On Duty toggle, "Phase 57/21" badges, the 4.9 (120+) rating, "Nearby", "120+ Specialists" |
| Remaining limited UI | The workflow screen's Analytics and Preparation results use a generic key/value renderer that shows raw field names (UX; P3-B7) |
| Duplicated paths (kept, now consistent) | Four appointment transition routes (doctor confirm/complete/cancel, `PUT /appointments/{id}/status`, consultation start/complete, queue). They now apply the same payment and state rules. Two prescription creation paths (`/prescriptions` with a consultation record; `/clinical/prescriptions/sign`). Two measurement stores (Phase 02 B7) |
| Orphan route | `/doctor/clinical-documentation` registered with an empty patient ID; unused (the screen now opens with patient context from consultation details) |
| Not implemented | AI drafting of patient messages (only fixed, non-clinical reminder text); live transcription; AI urgency or triage reordering of the queue (correctly absent); no-show only through the queue (no separate API); platform-fee and doctor-payout accounting; ratings on doctor list cards (the API has none) |
| Video / telemedicine | None in doctor screens (search for video, join call and telemed: 0 hits); care plans are IN_PERSON only (Phase 02) |

## 3. Background jobs relevant to doctors

| Job | Where | What it does | Phase 03 evidence |
|---|---|---|---|
| Care scheduler | `care_scheduler.run_scheduler` (worker every 60 s) | Appointment, medication, care-task, test and follow-up reminders; re-checks the source before sending | D-09c (test-task reminder processed, in-app stored, push `unavailable`) |
| Doctor communications | `doctor_communications.run_communications` | Delivers approved reminder batches in-app to consented patients | D-10b/d (3 delivered, all consented) |
| Hold expiry sweep | `AppointmentService.release_expired_holds` | Releases expired unpaid holds | Phase 02; full suite |
