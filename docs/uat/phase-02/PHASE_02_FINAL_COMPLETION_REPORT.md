# MediConnect — Phase 02 Final Completion Report

**Phase 02: Appointment, Payment and Patient Care Automation Stabilization**
For: the project owner and independent reviewers (Phase 03 planning). Date 2026-11-25. Branch `fix/phase-02-booking-payment-patient-care`; baseline `877c08d` (Phase 01 final). Not merged and not deployed. **Not clinically approved and not production-ready.**

## 1. Executive summary

Phase 02 verified and fixed the patient booking and payment lifecycle and patient components 05–13 on an isolated local UAT stack:

- **Database:** `mediconnect_uat`.
- **Payments:** Stripe in test mode.
- **AI:** deterministic.
- **Safety:** port 8000 was never used.

**Most important outcomes**

**Owner bugs fixed: BUG-055, 058, 059, 060, 061 and 063, plus the rest of BUG-056.**
- BUG-060 ("Appointment not found" from a notification) had two causes. `GET /appointments/{id}` returned HTTP 500 for every user, and the app ignored the notification's appointment ID.
- BUG-063 now releases a hold safely: the Stripe PaymentIntent is cancelled first, and a payment that already succeeded always wins.

**17 new defects found and fixed.** The most serious:
- **Privacy (P02-N10):** a released or cancelled booking gave that doctor permanent access to the patient's medical records and vitals.
- **Payments (P02-N02/N04/N05):**
  - Non-AI payments confirmed bookings without checking amount, owner or hold validity.
  - A doctor could confirm an unpaid booking.
  - The refund service recorded fake successful refunds when Stripe was unavailable.
- **Wrong-date booking (P02-N01):** a time typed after choosing a doctor could produce a proposal on a different date.
- **Fabricated clinical alert (P02-N11):** the doctor dashboard showed a hard-coded "CRITICAL TELEMETRY ALERT" for a non-existent patient, plus invented figures.

**Verification**
- **Real Stripe test mode:** decline and retry, release, expiry, refunds, and one PaymentIntent per booking checked in Stripe.
- **Concurrency:** across two backend processes, exactly one winner per slot.
- **Scheduler:** the real background worker sent medication, test and appointment reminders.
- **Live API:** 71 steps covering every patient component.
- **Emulator:** a 14-step walkthrough.

**Readiness:** ready for Phase 03. Live webhook delivery, FCM, email and SMS are blocked by external configuration, and clinical approval is still outstanding.

## 2. Bug statistics (no double counting)

| Measure | Count |
|---|---|
| Distinct defects reviewed | **32**: 15 owner IDs (BUG-049 to BUG-063) + 17 new (P02-N01 to P02-N17) |
| Owner IDs already fixed in Phase 01 (aliases; regression-verified in Phase 02) | 8 (049, 050, 051, 052, 053, 054, 057, 062) |
| Fixed in Phase 02 | **24**: 7 owner (055, 056 completion, 058, 059, 060, 061, 063) + 17 new |
| Reproduced before the fix in Phase 02 | 24 of 24:<br>• 7 on the live UAT API (BUG-055, 060, 061; P02-N01, N06, N10, N12)<br>• 2 on the emulator (N11, N17)<br>• 2 by failing runs (N05 double count, N13 silent skip)<br>• 13 by code inspection confirmed by tests (BUG-056 remnants, 058, 059, 063; N02, N03, N04, N07, N08, N09, N14, N15, N16) |
| Newly discovered | 17 |
| Open defects in scope | 0 |
| Open decisions or technical items (not defects) | 4: refund and reschedule policies (B6), measurement stores (B7), encryption at rest (B8), dose-question wording (B16) |
| Blocked verifications | External webhook delivery, FCM, email and SMS, live LLM and Vision, clinical and pharmacist approval |
| Owner UAT items executed | P-05n, P-05o, P-05p, P-05q, P-05r: all PASS (test mode) |

## 3. Full bug tracking table

| Bug ID | Component | Severity | Description | Root cause | Fix | Evidence | Status |
|---|---|---|---|---|---|---|---|
| BUG-049 | Chat UI | Medium | Keyboard stays open / reopens | (Phase 01) | Phase 01 keyboard UX | Phase 01 tests re-run | FIXED (P01) |
| BUG-050 | Crisis UI | High | Cardiac-style UI for self-harm | (Phase 01) | Dedicated crisis UI | Probe 0 differences | FIXED (P01), clinical design pending |
| BUG-051 | Triage | Medium | Ambulance for prolonged cough | (Phase 01) | Tiered guidance | Probe | FIXED (P01), clinical review pending |
| BUG-052 | Triage | High | Educational question triggers emergency | (Phase 01) | Informational handling | Probe | FIXED (P01) |
| BUG-053 | Recommendation | Medium | Ranking transparency | (Phase 01) | Top 2, ratings, reasons | `bug053-recommendation-fields.json` | FIXED, verified live |
| BUG-054 | AI booking | High | Context lost | (Phase 01) | Memory fixes | Probe | FIXED (P01) |
| BUG-055 | AI booking | Low | Manual slot called "closest" | Reason logic ignored manual picks | "Selected by you." | before/after JSON | FIXED |
| BUG-056 | Video | Medium | Unsupported video | Care-plan types, doctor UI | In-person only; migration prepared | tests | FIXED (migration not run) |
| BUG-057 | Dashboard | High | Fabricated appointment | (Phase 01) | Real data | Device | FIXED (P01) |
| BUG-058 | Patient details | Medium | No payment facts or reference | API returned none | Payment facts + copyable reference | device PNG | FIXED |
| BUG-059 | Doctor details | Medium | "LKR" without amount | Literal `'LKR '` | Booked fee + amount paid | device PNG | FIXED |
| BUG-060 | Notifications | High | "Appointment not found" | HTTP 500 (TypeError) + ignored map arguments | Both fixed; doctor push routing | before/after JSON, device | FIXED |
| BUG-061 | AI booking | High | No same-doctor alternatives | Slots from a different date | Requested-date slots; nearest real times | before/after JSON | FIXED |
| BUG-062 | AI booking | Medium | Name asked again | (Phase 01) | — | Repro flow 2, probe | FIXED (P01) |
| BUG-063 | Hold | High | No hold release | No action or endpoint | Race-safe release endpoint + UI | Stripe S3, device | FIXED |
| P02-N01 | AI booking | High | Wrong-date proposal | As BUG-061 | As BUG-061 | before JSON | FIXED |
| P02-N02 | Payments | High | Unverified legacy settlement | Unconditional confirm | Verified exactly-once settlement | unit, Stripe | FIXED |
| P02-N03 | Payments | Medium | Charge used current fee | Wrong fee source | Reserved fee | unit | FIXED |
| P02-N04 | Appointments | High | Doctor confirms unpaid | No payment check | PAID required | unit | FIXED |
| P02-N05 | Refunds | High | Fake, uncapped, duplicate refunds | See bug fix report | Honest, capped, atomic | Stripe S5, unit | FIXED |
| P02-N06 | AI chats | Low | Booking chat reused as draft | Flag not cleared | Cleared | unit | FIXED |
| P02-N07 | Manual booking | Medium | Retry re-reserved own slot | New hold per tap | Reuse + release | widget | FIXED |
| P02-N08 | Reschedule | High | Any clock time; 500 | No slot check | Real slots; atomic | Stripe S6, unit | FIXED |
| P02-N09 | Health tracking | Medium | No alert from Care Agenda | Second endpoint | Same thresholds | UAT run | FIXED |
| P02-N10 | Privacy | High | Cancelled booking gave record access | No status filter | CONFIRMED/COMPLETED only | UAT before/after | FIXED |
| P02-N11 | Doctor dashboard | High | Fabricated KPIs and ECG alert | Hard-coded | Real figures; removed | device PNG | FIXED |
| P02-N12 | Renewals | Medium | No notification; any doctor; double review | Missing checks | Prescriber-only, atomic, notifications | UAT, unit | FIXED |
| P02-N13 | Test safety | Medium | Live suite on 8000 and silently skipped | Default URL; mocked probe | Explicit guarded target | 13/13 live | FIXED |
| P02-N14 | Mobile models | Medium | LKR 2500 invented | Defaults | Nullable | tests | FIXED |
| P02-N15 | Cancellation | Low | Concurrent cancellations | Unconditional update | Conditional | Stripe S5 | FIXED |
| P02-N16 | Appointments | Low | Latent `datetime` NameError | Import alias | Fixed | unit | FIXED |
| P02-N17 | Hold | Low | Released hold "Payment pending" | Status not reset | UNPAID | unit | FIXED (device re-run pending) |

## 4. Test verification matrix (summary)

The per-test matrix for components 05–13 (49 rows) is in [PHASE_02_PATIENT_CARE_VERIFICATION_MATRIX.md](PHASE_02_PATIENT_CARE_VERIFICATION_MATRIX.md). Booking and payment rows are in [PHASE_02_BOOKING_PAYMENT_VERIFICATION.md](PHASE_02_BOOKING_PAYMENT_VERIFICATION.md).

| Test ID | Agent | Scenario | Expected | Actual | Method | Status | Evidence |
|---|---|---|---|---|---|---|---|
| BP-01 | Booking | Server-owned fee | Client amount ignored | 300000 minor units of LKR (LKR 3,000) charged | Stripe test mode | PASS | S1 |
| BP-02 | Booking | Decline then retry | Same intent; confirmed once | Yes | Stripe test mode | PASS | S2 |
| BP-03 | Booking | Sheet closed, then release | Not confirmed; intent cancelled; slot free | Yes | Stripe + emulator | PASS | S3, E8–E10 |
| BP-04 | Booking | Payment after expiry | Not confirmed; admin refund | REVIEW_REQUIRED; 1 refund | Stripe test mode | PASS | S4 |
| BP-05 | Booking | Paid cancellation and refund | One request; admin-approved refund | succeeded (300000) | Stripe test mode | PASS | S5 |
| BP-06 | Booking | Reschedule | Real slot only; no second charge | Yes | Stripe + unit | PASS | S6 |
| BP-07 | Booking | Concurrency, 2 processes | One winner per slot | 5/5 | Real local MongoDB | PASS | concurrency JSON |
| BP-08 | Booking | Restart during payment | Settled once | Yes | Stripe test mode | PASS | restart JSON |
| BP-09 | Payments | Duplicate, delayed, invalid webhook | Idempotent; 400 on bad signature | Yes | Locally signed real objects | PASS | S1 |
| BP-10 | Payments | Real Stripe webhook delivery | — | Stripe CLI missing | — | BLOCKED | — |
| BP-11 | Booking | BUG-055/061/062 | See bug table | As expected | UAT API | PASS | repro JSON |
| BP-12 | Details | BUG-058/059/060 | See bug table | As expected | Emulator | PASS | E1–E12 |
| PC-05…13 | Care components | 49 scenarios | — | 46 PASS, 1 PARTIAL (encryption at rest), 2 BLOCKED (FCM push; email/SMS) | UAT API with real worker; local API | See matrix | care JSON |
| AI-REG | Phase 01 agents | 35 probe scenarios | Same as Phase 01 | 0 differences | UAT API | PASS | probe JSON |

## 5. All 13 patient components

| # | Component | Status |
|---|---|---|
| 1 | AI Doctor Booking Agent | Implemented; tested (UAT API, Stripe test mode, emulator); live LLM blocked; not clinically relevant |
| 2 | AI Health Assistant | Implemented; Phase 01 tested; Phase 02 regression 0 differences; **clinical approval pending** |
| 3 | AI Doctor Recommendation | Implemented; fields verified live (BUG-053) |
| 4 | AI Medicine Image Recognition | Implemented; mocked only; **live Vision blocked**; pharmacist approval pending |
| 5 | Medication Reminder | Implemented; real worker executed; push blocked |
| 6 | Care Plan | Implemented; tested; progress computed client-side |
| 7 | Appointment Reminder | Implemented; real worker plus concurrent-worker test; push and email blocked |
| 8 | Follow-up Care | Implemented; tested; doctor-only creation |
| 9 | Medical Test Reminder | Implemented; real worker executed |
| 10 | Personal Health Tracking | Implemented; tested; **threshold clinical review pending**; two stores (owner decision) |
| 11 | Prescription Renewal | Implemented; tested; fixed (P02-N12) |
| 12 | Medical Records | Implemented; tested; privacy fixed (P02-N10); **partially verified** (no encryption at rest) |
| 13 | Notifications | Implemented; tested (in-app, deep links); push, email and SMS blocked |

## 6. Booking and payment integrity

**Records**
- **One active record per slot.** The owner's three historical bookings are intact.
- **Payment records:** one per paid booking, with the intent ID matching the appointment. Stripe search confirmed one PaymentIntent per paid booking.

**Reservations**
- Server-owned 10-minute holds.
- Expired holds are swept by the worker and never confirmed by a late payment.
- Released holds are `UNPAID`, with their PaymentIntent `canceled` in Stripe.

**Transactions (all test mode)**
- Successes: S1, S2, the restart test and S4.
- A decline: S2.
- Cancellations: S3 and the emulator.
- Refunds: S4 reconcile-refund and the S5 policy refund, both `succeeded`. Over-refund and duplicate approval were rejected.

**Idempotency**
- Repeated webhooks, status refreshes, double taps, releases, refund approvals and renewals each have exactly one effect.

**Audit**
- The `appointment_events` log, plus the admin audit log for refunds.

## 7. Patient automation verification

- **Medication reminders:**
  - Doctor-approved schedules only.
  - The real worker delivered in-app in Asia/Colombo time.
  - Taken and snooze actions are idempotent and patient-only.
  - The AI cannot change doses (a clearer reply is proposed).
  - Push is blocked.
- **Care plans:**
  - Doctor-authored only, with in-person type only.
  - The patient sees the plan and completes tasks; cross-account access is denied.
  - The AI lists the real tasks.
- **Follow-ups:** listed for the doctor, link to appointments, can be cancelled, and patients cannot create them.
- **Health tracking:**
  - Validation, units, provenance, trends and ownership work.
  - Crisis alerts now come from both entry points; the thresholds still need clinical review.
- **Medical test reminders:** executed by the worker and shown on the agenda; no invented results.
- **Prescription renewals:** request, duplicate block, prescriber notification, prescriber-only atomic review, patient notification; the AI cannot approve.
- **Medical records:**
  - PDF only (signature checked), 10 MB limit.
  - Access works for the patient and the treating doctor only.
  - Clean logs; source-grounded summary.
  - No encryption at rest.
- **Notifications:**
  - Recipients, unread count, mark read and mark all read work.
  - Deep links open the right appointment for patient and doctor; deleted links return 404.
  - Truthful channel statuses.

## 8. Test results

| Suite | Result | Notes |
|---|---|---|
| Backend pytest (full) | **545 passed, 0 failed** | Baseline 512; +33 in `test_phase02_booking_payment.py`; 6 existing fixtures updated (listed in the bug fix report) |
| Flutter test (full) | **298 passed, 0 failed** | Baseline 284; +14; 4 expectations updated for new truthful wording |
| Flutter analyze | No issues | |
| Flutter live API integration | 13/13 on `127.0.0.1:8001` | Separate run, not added to the 298 (the same file returns early in normal runs) |
| Stripe test-mode UAT | 36 steps, all as expected | Real Stripe test API |
| Concurrency (2 processes) | 5/5 rounds + AI race + double tap | Real local MongoDB |
| Scheduler | Real worker: 3 reminder types executed; concurrent workers 5/5 runs | |
| Patient care live UAT | 71 steps as expected | |
| Phase 01 AI probe | 35 scenarios, 0 differences | |
| Emulator | 14 checks PASS; 0 framework errors | |
| Admin web | Not run | Admin code unchanged; refund API contract to check in Phase 04 |
| Android debug APK | Built (`app-debug.apk`, UAT URL) | |

## 9. Git information

- **Baseline:** `877c08d`.
- **Branch:** `fix/phase-02-booking-payment-patient-care`, pushed.
- **Implementation commits:**
  - `c4423e1`: booking, holds, payments, refunds, reschedule.
  - `2528673`: care relationship, renewals, measurement alerts, in-person.
  - `07b1bb0`: mobile.
  - `0858d86`: live integration guard.
  - `56d6bc8`: UNPAID release; doctor dashboard fabrication removed.
- **Documentation commit:** the commit that adds `docs/uat/phase-02/` (see the push log for its hash).
- **CI on `56d6bc8`:**
  - Backend CI: **success** (run 45600419462).
  - Mobile CI: **success** (run 45600419628).
- **Working tree:** clean after the documentation commit. Not merged to `main`; nothing deployed.

## 10. Blockers and handover

Full list: [PHASE_02_REMAINING_BLOCKERS.md](PHASE_02_REMAINING_BLOCKERS.md).

- **Technical:**
  - Encryption at rest for medical documents (B8).
  - Two measurement stores (B7).
  - Wording of the AI reply to dose-change requests (B16).
  - Language memory after Sinhala emergency follow-ups (B17).
- **External configuration:**
  - Stripe CLI webhook forwarding (B3).
  - FCM (B4).
  - SMTP and SMS (B5).
  - LLM and Vision (B13).
- **Owner decisions:**
  - Refund, cancellation-deadline and reschedule-fee policies (B6).
  - Approval to run the in-person migration on shared data (B9).
- **Clinical approval:** triage, crisis, thresholds and care wording (B1); pharmacist review (B2).
- **Physical device:**
  - Real-phone UAT (B10).
  - Re-run of emulator steps E8–E10 after the last fix (B11).
  - Native-speaker review (B12).
- **Next phases:**
  - **Phase 03:** remaining doctor-dashboard widgets and doctor workflows (B14).
  - **Phase 04:** admin refund page against the stricter API (B15).

## 11. Release readiness

| Target | Assessment |
|---|---|
| Academic demonstration | **Ready**: booking, payment (test mode), release, refund and patient care work end to end locally |
| Local UAT | **Ready for owner retest**: re-run P-05 items on a phone; optionally set up the Stripe CLI |
| Staging | **Not ready**: needs webhook delivery, FCM and email configuration, encrypted document storage, and policy decisions |
| Clinical pilot | **Not ready**: no clinical or pharmacist approval |
| Production | **Not ready** |

**Reports:**
- [PHASE_02_BUG_FIX_REPORT.md](PHASE_02_BUG_FIX_REPORT.md)
- [PHASE_02_PATIENT_UAT_REPORT.md](PHASE_02_PATIENT_UAT_REPORT.md)
- [PHASE_02_BOOKING_PAYMENT_VERIFICATION.md](PHASE_02_BOOKING_PAYMENT_VERIFICATION.md)
- [PHASE_02_PATIENT_CARE_VERIFICATION_MATRIX.md](PHASE_02_PATIENT_CARE_VERIFICATION_MATRIX.md)
- [PHASE_02_BUG_ID_RECONCILIATION.md](PHASE_02_BUG_ID_RECONCILIATION.md)
- [PHASE_02_REMAINING_BLOCKERS.md](PHASE_02_REMAINING_BLOCKERS.md)
- [PHASE_02_RESULTS.json](PHASE_02_RESULTS.json)
