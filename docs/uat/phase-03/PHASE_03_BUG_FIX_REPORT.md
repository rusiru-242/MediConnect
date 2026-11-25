# Phase 03 — Bug Fix Report (doctor system)

For: the project owner and independent reviewers. 2026-11-25 · branch `fix/phase-03-doctor-system-stabilization` (from `00a47a0`, the Phase 02 documentation commit on top of `56d6bc8`).

**Numbering:**
- New IDs are `P03-Nxx`; they do not collide with the owner's BUG-xxx IDs or Phase 01/02 IDs.
- P03-N18, N19 and N20 are **improvements**, not defects, and are not counted as defects.
- No historical ID was reopened or renumbered.

**Before/after method:**
- Each defect marked "live" was reproduced on the UAT backend (`127.0.0.1:8001`, `mediconnect_uat`) before the fix (`evidence/repro-before-fix.json`) and re-run after it (`evidence/repro-after-fix.json`), using `repro_doctor_defects.py`.
- Defects found by code review are covered by regression tests in `backend/tests/test_phase03_doctor_system.py` (20 tests) and `mobile/test/screens/phase03_doctor_ui_test.dart` (6 tests).

## 1. Defects

| Bug ID | Severity | Component | Defect (actual behaviour) | Confirmed root cause | Fix | Evidence | Status |
|---|---|---|---|---|---|---|---|
| P03-N01 | **Critical** | Appointments / 15 | "Start consultation" on an **unpaid** PENDING request turned it into CONFIRMED (payment still UNPAID). The patient could then no longer release it (409). | `start_consultation` "synchronised" PENDING → CONFIRMED with no payment check, bypassing the Phase 02 rule (confirm only after verified payment) | Start only on a CONFIRMED visit (409 otherwise); completion only from CONFIRMED (conditional), with an event and one patient notification. Mobile shows Start only for confirmed bookings | Live R1 before: 200, PENDING→CONFIRMED; after: 409, stays PENDING/UNPAID. Tests `test_n01_*`, UI test | **Fixed, verified** |
| P03-N02 | **High (privacy)** | Records access | A doctor kept access to a patient's records through a consultation session on a released/cancelled reservation. Pending or suspended doctors were not refused by the relationship check itself | `verify_doctor_patient_care_relationship` accepted any `consultation_sessions` row and did not check the doctor's approval | Relationship requires an APPROVED, ACTIVE doctor; sessions count only while their appointment is CONFIRMED/COMPLETED | Live R1b before: records 200 / trends 200; after: 403 / 403. `test_n02_*` | **Fixed, verified** |
| P03-N03 | **High** | Appointments / refunds | A doctor cancelling a **paid** booking opened no refund request, although the existing rule is "doctor cancellation: 100%". Same for leave with explicit conflict resolution | Doctor cancel and leave-conflict cancel set CANCELLED only | One shared path opens a refund request (existing policy, admin approval unchanged) and tells the patient | Live R2 before: no request; after: request, LKR 2,000 (100%). D-04f. `test_n03_*` (×2) | **Fixed, verified** |
| P03-N04 | **High** | Appointments / Stripe | A doctor cancelling an **unpaid** reservation left its Stripe PaymentIntent payable (`requires_payment_method`) | Doctor path did not reuse the BUG-063 intent-stopping logic | Shared `stop_open_payment_intents` (also used by Release Reservation); if the payment had already succeeded, the booking is handled as paid (refund request) | Live R3 before: intent `requires_payment_method`; after: `canceled`. `test_n04_*` | **Fixed, verified** |
| P03-N05 | Medium | Appointments | Doctor cancel/complete used unconditional updates (concurrent changes both "succeeded"); no audit events | Missing state conditions and `record_appointment_event` calls | Conditional updates (409 on a lost race); APPOINTMENT_CANCELLED / APPOINTMENT_COMPLETED events | `test_n05_*`: 6 concurrent cancels → one 200, one refund request; 6 completes → one 200 | **Fixed, verified** |
| P03-N06 | **High (clinical safety)** | Prescriptions / reminders (17) | Signing (or renewing) a prescription created an **ACTIVE reminder at 08:00 and 20:00 for 14 days** whatever was prescribed (e.g. "Once at bedtime, 30 days"). Patients saw it in Medicine Reminders, and it blocked their own correctly timed reminder | `_sync_to_medication_reminders` hard-coded times and duration | Removed; reminder times come only from the doctor's explicit schedule approval (validated against frequency and duration) or the patient's frequency-checked reminder | Live R4 before: ACTIVE, 08:00/20:00, 14 days; after: none. D-07c: explicit approval 200, mismatch 422 | **Fixed, verified** |
| P03-N07 | Medium | Prescriptions / notes | Prescriptions stored **generated ids** as `medicalRecordId` / `appointmentId` (pointing at nothing); `appointmentId` in requests was not validated; `/prescriptions` accepted another doctor's appointment | Placeholder `str(ObjectId())`; missing checks | References are real or absent; a cited visit must be this doctor's confirmed/completed visit with this patient; renewal cites the original visit | Live R4 (`medical_record_link_exists: false`), R8 before 201 → after 400. `test_n06_n07_*`, `test_n07_n13_*` | **Fixed, verified** |
| P03-N08 | Medium (clinical safety) | Renewal (17) | Renewal filled missing details with "Standard", "1 dose", "Once daily", "30 days" | Defaults in `_issue_renewal_prescription` | Copies the original item exactly; incomplete details → 409 and the review lock is released | `test_n08_*`; D-07e (copied item, linked visit) | **Fixed, verified** |
| P03-N09 | **High (clinical safety)** | Clinical notes (16) | AI-structured SOAP drafts invented "General condition satisfactory, vitals documented", a generic assessment, plan and follow-up; the draft could be signed unedited | `_format_raw_notes_to_soap` placeholders; sign had no completeness check | Only the doctor's words are placed; other sections are "Not documented. To be completed by the clinician."; signing refused until completed; sign/edit/amend conditional | Live R5 before: invented text, sign 200; after: "Not documented", sign 409. D-06a/b/c | **Fixed, verified** |
| P03-N10 | Medium | Notes / prescriptions | Signed notes stored **"SLMC-VERIFIED"** when no registration number; notes showed "Dr. Doctor" / "General Practitioner"; prescription notification said "Dr. Dr. …" | Placeholder fallbacks | Real registration number required to sign; real names; no invented specialty | `test_n09_*`, `test_n11_*`; D-06b/c (`SLMC-UAT-P03-ALPHA`) | **Fixed, verified** |
| P03-N11 | **High (privacy)** | Clinical notes (16) | Another doctor with a care relationship could list a colleague's **unsigned drafts** | `list_notes` queried all notes for the patient | Other clinicians see signed/amended notes only; own drafts stay visible to the author | Debug run before: Dr. Beta saw Dr. Alpha's draft; `test_n11_*`; D-06e | **Fixed, verified** |
| P03-N12 | Medium | Consultation records | Writing a consultation record on a **future** CONFIRMED visit marked it COMPLETED (and did so before the duplicate check) | Status change before validation, no time check | Duplicate check first; completes only once the visit has started; conditional + event | Live R7 before: 201, COMPLETED; after: 409, CONFIRMED. R7b (started visit): 201, COMPLETED | **Fixed, verified** |
| P03-N13 | Medium | Prescriptions (17) | An identical prescription submitted twice was issued twice; whitespace-only medicine names accepted | No idempotency/duplicate check; no whitespace stripping | Identical repeat → 409; `str_strip_whitespace` so blank fields → 422 | Live R9 before: 201, 201 (2 stored); after: 201, 409 (1 stored). D-07d | **Fixed, verified** |
| P03-N14 | Medium | Records summary (15) | `/clinical/records/summary` returned **500** whenever a signed note existed; it said "No documented drug or environmental allergies", which reads as "no allergies"; "Active Pharmacotherapy" listed every issued prescription | `createdAt[:10]` on a datetime; wording | Date formatted; "No allergies are recorded … This does not confirm that the patient has no allergies"; "Medicines prescribed on record (confirm current use)" | Authorization sweep before: 500 (doctor and patient); after: 200. `test_n14_*` | **Fixed, verified** |
| P03-N15 | Low | Schedule (14/20) | Doctor schedule/consultation responses invented **LKR 2,500** when an appointment had no fee; "next patient" could be an unpaid request | Default in `float(appt.get("consultationFee", 2500.0))`; filter included PENDING | Booked fee or null; next patient CONFIRMED only | `test_n15_*` | **Fixed, verified** |
| P03-N16 | Medium | Doctor dashboard (B14) | Doctor home showed a **"Cardiology Specialist"** fallback, a **"VERIFIED & ACTIVE"** fallback badge, a non-functional **On Duty** toggle and presence dot, and internal **"Phase 57" / "Phase 21"** badges. The Today panel counted unpaid requests and called the amount "Paid today" | Static UI | Removed; Today panel counts confirmed/completed visits, shows "N awaiting payment", labels "Paid for today's visits" (gross) | Emulator before/after screenshots; UI tests; dashboard reconciled with the database (D-02c) | **Fixed, verified** |
| P03-N17 | **High (privacy)** | Care plans (18) | A care plan could be created on an **unpaid or cancelled** appointment, and any care plan granted ongoing record access; care plans showed doctor name "Doctor" | No status check; relationship check counted any plan; name read from `doctor_profiles` (no `fullName`) | Plan needs a CONFIRMED/COMPLETED visit (409 otherwise); plans grant access only with a real visit; real doctor name | `test_n17_n18_*`; D-08a (unpaid 409, "Dr. P03 Alpha") | **Fixed, verified** |
| P03-N21 | Medium | Schedule (14) | Editing or removing an availability window could leave **paid bookings outside any window** silently | No booked-slot check | 409 listing the affected times; changing availability never cancels bookings (leave conflicts still require explicit `resolveConflicts`) | `test_n21_*`; D-03e (delete 409, shrink 409, leave 409, booking CONFIRMED) | **Fixed, verified** |
| P03-N22 | **High (safety process)** | Test infrastructure | `pytest` with no environment used `backend/.env`, which points at a **remote Atlas database `mediconnect`** and a real Stripe test key. A Phase 03 run started this way (see §3) | Settings load `.env`; there was no test-session guard | `backend/tests/conftest.py` pins tests to local `mediconnect_test` with mock Stripe keys and refuses non-local / non-`_test` targets | Guard refuses a remote URI (verified); `test_n22_*` | **Fixed, verified** (impact on the remote database **unknown**; see §3) |
| P03-N23 | Medium | Doctor UI (16/17) | The **prescription renewal queue** and the **SOAP notes** screen had no entry point. Doctors were notified to "open the renewal queue" but could not | Routes registered, never navigated to | "Prescription renewals" card on doctor home; "SOAP notes" link in consultation details for confirmed/completed visits | UI tests `P03-N23` (×2) | **Fixed, verified (widget tests)** |
| P03-N24 | Medium | Patient UI (doctor discovery) | Every Find a Doctor card showed an invented **"★ 4.9 (120+)"** rating, **"Nearby"** and **"Next Slot: Today, 2:00 PM"** (availability that may not exist). Patient home showed "120+ Specialists" and a **"(HIPAA Compliant)"** claim | Static UI (the list API has no rating, location or slot) | Removed; cards show "In-person visit" and "See available times"; home says "Browse specialists"; footers show only the real app version | `doctor_discovery_availability_test` TEST 20; emulator `p03n24-find-doctor-after.png` | **Fixed, verified** |

## 2. Improvements (not counted as defects)

| ID | Component | Change | Evidence |
|---|---|---|---|
| P03-N18 | Care plans (18) | Server-side progress (`completedTasks`, `totalTasks`, `progressPercentage`, null without tasks) in plan responses and the doctor follow-up list; doctors now see progress | D-08b/c/d (doctor 1/2 = 50%); emulator `p03n18-doctor-followups-progress.png` |
| P03-N19 | Analytics (21) | Refund-aware financials: booked fees, captured payments, refunds, net collected per currency, awaiting payment, open refund requests; platform fee and doctor earnings left null (not configured) | D-12a/b/c reconciled with direct database queries |
| P03-N20 | Doctor assistant (14/21) | Date phrases (tomorrow, next Monday, this week, this month) and "how many / completed / attention / gaps" routing; numbers only from the analytics service | D-14a (8 example questions) |

## 3. Safety incident during this phase (disclosed)

While running the backend suite, my first `pytest` run had no database override. Settings load `backend/.env`, which points at the remote Atlas cluster, database **`mediconnect`**.

**What happened:**
- **Duration:** the run ran for about 20 minutes (from about 20:08 +05:30 on 2026-11-25) with very low CPU, consistent with remote round-trips or timeouts.
- **Stopped and replaced:** I stopped it, and every later run used the local test database.
- **Check blocked:** I attempted a read-only check of the remote database (a ping plus counts of documents created in that window). The permission system blocked it, and I did not try another route.
- **Unknown:** whether that run actually connected, and which tests ran before it was stopped.

**What the tests would have done if connected:**
- **Fixtures and sweeps:** they insert their own fixtures and run sweeps, such as hold expiry and the reminder scheduler.
- **Deletes:** no test drops or empties a collection. Each cleanup deletes only the IDs, emails or prefixes the test created, for example `patient_<suffix>_…@mediconnect.lk`, `doctor_…@mediconnect.lk`, `DOC-TEST-…`, `STAB-…` and `DOC-AI-…`.

**Owner action:** check the `mediconnect` database for records created between 20:05 and 20:35 +05:30 on 2026-11-25 with those test patterns.

**Prevention:** P03-N22 makes a repeat impossible: the test session now refuses non-local and non-`_test` databases.

## 4. Modified test expectations (each change explained)

| Test | Change | Reason |
|---|---|---|
| `test_phase6_advanced_healthcare_ai.py::test_doctor_prescription_assistant_and_signing` | Asserted an ACTIVE reminder after signing → now asserts no reminder | The asserted behaviour was P03-N06 (08:00/20:00 for a "Once at bedtime, 30 days" prescription) |
| `test_phase8_final_integration.py::test_prescription_allergy_screening_and_care_sync` | Same as above | P03-N06 |
| `test_phase6_advanced_healthcare_ai.py::test_clinical_note_draft_organize_and_signing_workflow` | The doctor now also writes the examination and plan (taken from the raw notes); added an assertion that signing an incomplete draft returns 409 | The test previously signed text the assistant had invented (P03-N09) |
| `mobile/test/screens/doctor_discovery_availability_test.dart` TEST 20 | Added assertions that no invented rating or "Nearby" is shown | P03-N24 |

No other existing expectation was changed. Phase 01 and Phase 02 regression tests are unchanged and pass.

## 5. Changed files

**Backend services:**
- `consultation_service.py`, `appointment_service.py`, `doctor_service.py`
- `clinical_documentation_service.py`, `prescription_workflow_service.py`, `medical_record_service.py`
- `clinical_safety_service.py`, `patient_medical_record_service.py`, `care_plan_service.py`
- `doctor_workflow.py`

**Backend routes, models and schemas:**
- `routes/doctor_workflow.py`
- `models/prescription.py`
- `schemas/consultation.py`, `schemas/prescription.py`, `schemas/clinical_workflow.py`, `schemas/care_plan.py`

**Backend scripts and tests:**
- `scripts/seed_phase03_fixtures.py`
- `tests/conftest.py`, `tests/test_phase03_doctor_system.py`, plus the three tests in §4.

**Mobile doctor screens:**
- `doctor_home_screen.dart`, `doctor_schedule_screen.dart`, `consultation_details_screen.dart`, `doctor_workflow_screen.dart`

**Mobile patient screens, widgets and models:**
- `patient/find_doctor_screen.dart`, `patient/patient_home_screen.dart`
- `widgets/doctor_today_overview.dart`
- `models/consultation.dart`

**Mobile tests:** `phase03_doctor_ui_test.dart` and `doctor_discovery_availability_test.dart`.

## 6. Remaining limitations of the fixes

- **N06:** existing ACTIVE reminders created by the old code at signing (they have no `prescriptionRevision`) are not removed. The worker never delivered them, but patients may still see them in their list. A cleanup needs owner approval (blocker P3-B5).
- **N03:** a refund request opened by a doctor cancellation still needs administrator approval, which is the existing policy. The admin UI's handling of these requests is Phase 04 (B15).
- **N24:** verified ratings exist per doctor (reviews page), but the list API does not return them. Showing real ratings on cards would need an API change; it is not invented here.
