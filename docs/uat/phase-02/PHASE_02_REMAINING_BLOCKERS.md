# Phase 02 — Remaining Blockers and Untested Items

2026-11-25 · branch `fix/phase-02-booking-payment-patient-care`

| # | Item | Type | Status | What is needed | Blocks Phase 03? |
|---|---|---|---|---|---|
| B1 | Clinical approval of triage, crisis, cough, measurement thresholds and care-content wording (carried from Phase 01 B1) | Clinical approval | BLOCKED | Clinician and mental-health review with recorded sign-off | No (blocks pilot and production) |
| B2 | Pharmacist approval of medicine content (Phase 01 B2) | Clinical approval | BLOCKED | Pharmacist review | No |
| B3 | Stripe → backend **webhook delivery** | External configuration | BLOCKED | Install the Stripe CLI and run `stripe listen --forward-to 127.0.0.1:8001/api/payments/webhook` (test mode), or use a reachable staging URL. Signature checking and processing are verified with locally signed real test objects | No |
| B4 | Firebase FCM push delivery | External configuration | BLOCKED | FCM service account for a test project, a device token, and owner authorisation. In-app delivery and worker execution are verified | No |
| B5 | Email (SMTP) and SMS (Twilio) delivery | External configuration | BLOCKED | Approved test credentials and synthetic recipients. The UAT script disables SMTP so synthetic accounts are never emailed; statuses are reported truthfully | No |
| B6 | Product policies not defined in the repository: refund rule confirmation (100% at 24 hours or more, otherwise 80%, as currently coded); cancellation deadlines; fee differences when rescheduling; whether a released hold should notify the doctor for AI bookings | Owner decision | OPEN | Owner confirms or changes the rules. Phase 02 implemented only the existing rules | No |
| B7 | Two separate patient measurement stores (`/clinical/measurements` and `/care-automation/measurements`) | Owner decision / technical | OPEN | Decide whether to merge them (alerts now match; histories are still separate) | No |
| B8 | Encryption at rest for uploaded medical documents (plain files in `backend/uploads/medical_documents`) | Technical (Phase 05 security) | OPEN | Encrypted storage or a managed object store with server-side encryption | No |
| B9 | Running the in-person migration (`scripts/migrate_consultation_type_in_person.py`) on shared or production data | Owner approval | NOT RUN | A dry run on the target database, then owner approval. Tested and reversible on the test database; UAT has 0 records | No |
| B10 | Physical phone and small-screen testing | Device verification | NOT RUN | Manual UAT on a real Android phone (PaymentSheet, Release Reservation, notification taps) | No |
| B11 | Device re-run after the last two fixes (cleared hold note; released hold `UNPAID`) | Device verification | NOT RUN | Repeat emulator steps E8–E10. Both fixes are covered by automated tests | No |
| B12 | Native-speaker review of new Sinhala and Tamil strings (alternative-time replies, doctor "Today" panel) | Language review | NOT RUN | Native reviewer | No |
| B13 | Live LLM and Vision providers (carried from Phase 01 B4/B5) | External configuration / privacy | BLOCKED | Keys, budget and privacy approval | No |
| B14 | Wider doctor-dashboard and doctor-workflow review (other static widgets beyond those removed; doctor-side care-plan progress) | Phase 03 scope | OPEN | Phase 03 | — |
| B15 | Admin-web refund page against the stricter refund API (`processing` state, 409/503 responses) | Phase 04 scope | NOT RUN | Admin-web was not changed; check in Phase 04 | No |
| B16 | AI reply to "change my dose" | Improvement | OPEN | A clearer "only your doctor can change your dose" reply. No change is made, so safety holds | No |
| B17 | Backend reply language after a Sinhala emergency follow-up (Phase 01 B11) | Technical | OPEN | Language-aware follow-up texts | No |

**Phase 03 can start.** No item blocks doctor-system verification. B1, B2, B3, B4, B5, B8 and B10 block a clinical pilot and any production release.
