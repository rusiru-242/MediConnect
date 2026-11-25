# Phase 03 — Remaining Blockers and Untested Items

For: the project owner and the Phase 04/05 teams. 2026-11-25 · branch `fix/phase-03-doctor-system-stabilization`.

## 1. Phase 02 blockers reconciled

| # | Item | Phase 03 outcome | Status now |
|---|---|---|---|
| B1 | Clinical approval (triage, crisis, thresholds, care wording) | Not obtained; doctor-side clinical content (notes, preparation, reminder wording) added to the review scope | **BLOCKED** |
| B2 | Pharmacist approval of medicine content | Not obtained; renewal and prescription behaviour now copies only clinician-entered data | **BLOCKED** |
| B3 | Stripe → backend webhook delivery | Not available (no Stripe CLI); unchanged | **BLOCKED** |
| B4 | FCM push delivery | Not configured; reminders record push as `unavailable` truthfully | **BLOCKED** |
| B5 | Email (SMTP) and SMS delivery | Not configured; `skipped` recorded truthfully | **BLOCKED** |
| B6 | Product policies (refund rule, cancellation deadlines, reschedule fee difference, doctor notice for AI hold release) | Unchanged; Phase 03 applied only the existing rule (doctor cancellation 100%, admin approval) | **OPEN – owner decision** |
| B7 | Two measurement stores | Unchanged | **OPEN – owner decision** |
| B8 | Encryption at rest for uploaded documents | Unchanged | **OPEN – Phase 05** |
| B9 | Running the in-person migration on shared data | Not run; UAT data uses IN_PERSON | **NOT RUN – owner approval** |
| B10 | Physical phone and small screen | Not available | **NOT RUN** |
| B11 | Device re-run of E8–E10 after the Phase 02 fixes | **Done**: E8, E9 and E10 PASS on the emulator, including database and Stripe checks (EM-05–EM-09) | **CLOSED** |
| B12 | Native Sinhala and Tamil review | Not available; new strings added in Phase 03 (Today panel, renewal card, Browse specialists) | **NOT RUN** |
| B13 | Live LLM and Vision providers | Not configured; doctor components do not depend on them | **BLOCKED** |
| B14 | Doctor dashboard and workflow review | **Done**: dashboard cleaned (P03-N16), figures reconciled (D-02c), workflows reviewed (24 IDs; see the bug fix report) | **CLOSED** |
| B15 | Admin refund page against the stricter refund API | Not run (Phase 04). Doctor cancellations now also create refund requests | **NOT RUN – Phase 04** |
| B16 | AI reply to "change my dose" | Unchanged; no change is ever made | **OPEN – improvement** |
| B17 | Backend reply language after a Sinhala emergency follow-up | Unchanged | **OPEN** |

## 2. New Phase 03 items

| # | Item | Type | What is needed | Blocks Phase 04? |
|---|---|---|---|---|
| P3-B1 | **Possible test writes to the remote `mediconnect` database** during the first Phase 03 `pytest` run (20:08–20:30 +05:30; whether it connected is unknown; see the security report §1) | Owner check | Inspect the database for test-pattern records created in that window | No (urgent owner check) |
| P3-B2 | Admin web `AppointmentsPage` calls `consultationFee.toLocaleString()` without a null check; the fee has been nullable since Phase 02 | Phase 04 defect (admin) | Handle a null fee as "Not available" | No (Phase 04 work item) |
| P3-B3 | Doctor-initiated refund requests (P03-N03) appear in the admin refund queue; the admin UI has not been checked against them | Phase 04 | Admin review of the `requested` refunds from doctor cancellations and leave | No |
| P3-B4 | Admin read access to patient clinical records, notes and trends (200 in the sweep) | Policy | Decide whether admins may read clinical content; restrict if not | No |
| P3-B5 | ACTIVE medication reminders created at signing by the old code (before P03-N06) may still show in patients' lists (never delivered: no `prescriptionRevision`) | Data cleanup, owner approval | A reversible cleanup script for shared data; UAT/test data only otherwise | No |
| P3-B6 | Rejected doctors get a clear 403 message at login but no in-app appeal or re-application path | Owner decision | Confirm the intended support flow | No |
| P3-B7 | Doctor workflow screen renders analytics and preparation with raw field names (`bookedFees`, `netCollected`) | UX | Labelled layout | No |
| P3-B8 | Consultation preparation covers only this doctor's records (not measurements, uploaded documents, or other clinicians' signed notes) | Product limitation | Decide scope; add sources with access checks | No |
| P3-B9 | No drug-interaction or contraindication source; assistant review checks only recorded allergies and active medicines | Clinical scope | Licensed source plus pharmacist review | No (blocks a clinical pilot) |
| P3-B10 | Doctor note, prescription and care-plan screens were verified through the API and widget tests, not tapped on a device; doctor notification deep links not re-run on the device | Device verification | Manual device pass | No |
| P3-B11 | Two-process concurrency was not repeated for doctor mutations (one process plus database-level conditions; tests use thread pools) | Test depth | Optional second-process run | No |
| P3-B12 | Emulator snapshot left adb file transfer broken; cold boot was required | Environment note | Cold-boot the emulator if installs hang | No |

**Phase 04 can start.** No item blocks admin-system verification.

**Blocks a clinical pilot or production release:** B1, B2, B3, B4, B5, B8, B10, P3-B1, P3-B4 and P3-B9.
