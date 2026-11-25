# Phase 02 — Bug Fix Report

For: the project owner and independent reviewers. 2026-11-25 · branch `fix/phase-02-booking-payment-patient-care` · baseline `877c08d`.

IDs follow [PHASE_02_BUG_ID_RECONCILIATION.md](PHASE_02_BUG_ID_RECONCILIATION.md). "Reproduced" means the defect was observed before the fix: on the UAT API, on the emulator, in a failing test, or by reading code (stated per row).

## 1. Owner defects fixed in Phase 02

| Bug ID | Component | Severity | Description | Root cause | Fix | Evidence | Status |
|---|---|---|---|---|---|---|---|
| BUG-060 | Notifications / appointments | High | Doctor taps View Appointment → "Appointment not found" | **Two causes.** (1) `GET /appointments/{id}` raised `TypeError` (wrong keyword `hospitalOrClinic=`) → HTTP 500 for patient, doctor and admin. (2) Notification, push and care-agenda links pass `{'appointmentId': id}`; both detail screens only read an `Appointment` or a `String`, so no request was made. Push taps also always opened the patient screen | Keyword fixed; detail screens accept the map; push taps route doctors to the doctor screen; deleted links show 404 | Before: `bug060-before-api.json` (500 ×3). After: `bug060-after-api.json` (200); device screenshots `bug060-*.png` | FIXED, verified on device |
| BUG-058 | Patient appointment details | Medium | No payment status, paid amount or full reference | The API returned no payment facts; the app showed an 8-character ID | API returns `bookingReference`, `visitType`, `consultationFeeAtBooking`, `amountPaid` and `paidAt` (from the verified payment record only), payment and refund status. The app adds a payment summary and a copyable full reference | `bug058-patient-detail-payment-and-reference.png`; tests | FIXED, verified on device |
| BUG-059 | Doctor appointment details | Medium | "LKR" with no amount | The UI literally rendered `'LKR '`; the model also defaulted the fee to 2500 | Shows the fee stored at booking (never the current profile fee) and the amount paid; a missing fee is "Not available" | `bug059-doctor-detail-fee-and-amount-paid.png`; tests | FIXED, verified on device |
| BUG-061 | AI booking | High | No nearby times for the same doctor | After picking a doctor card, a typed time was matched only against slots loaded for the first open date; a taken time then fell through (and see P02-N01) | Matches against the requested date's real slots. When taken: keeps the doctor, explains, and offers up to 4 nearest real times that day; another date only if that day is full. Never invents availability | `bug061-multi-before-api.json` vs `-after`; tests | FIXED |
| BUG-055 | AI booking summary | Low | "Closest available time…" on a slot the patient picked | `selectionReason` compared the slot with the earlier requested time even for manual picks | A manual pick is "Selected by you." "Closest" is used only for automatic proposals | `bug055-061-before-api.json` vs `-after` | FIXED |
| BUG-063 | Reservation hold | High | No way to release the hold after cancelling payment | No action or endpoint; the session cancel did not stop the Stripe PaymentIntent | `POST /appointments/{id}/release-hold`: cancels open PaymentIntents first; if Stripe says succeeded or processing, nothing is released (the payment wins); conditional cancel; paid bookings rejected (409); idempotent. App: Release Reservation with confirmation on the AI hold card, appointment details and manual booking. A released hold is `UNPAID` | Stripe S3; device `bug063-*.png` (PaymentIntent `canceled` in Stripe, slot free again) | FIXED, verified on device |
| BUG-056 | Video channelling | Medium | Unsupported video features | Remaining: care-plan form offered Video/Audio; the doctor dashboard showed "4 video" | Care plans accept in-person only (an unchanged historical value stays readable); doctor form shows in-person only; appointments report `visitType: IN_PERSON`. A reversible migration was prepared and tested on the test DB only. UAT has 0 historical video records | `test_bug056_*` | FIXED (migration not run on any shared DB) |

## 2. New defects found and fixed in Phase 02

| Bug ID | Component | Severity | Description | Root cause | Fix | Evidence | Status |
|---|---|---|---|---|---|---|---|
| P02-N01 | AI booking | High | Wrong-date proposal: "Book November 29 at 10:00" after picking a doctor proposed 2026-11-26 | Same as BUG-061 | Same as BUG-061 | `bug061-multi-before-api.json` (flow 1) | FIXED |
| P02-N02 | Payments | High | Legacy (non-AI) settlement confirmed any succeeded intent | The webhook, status refresh and create-intent paths set CONFIRMED/PAID unconditionally | `settle_legacy_payment`: intent id, received amount, currency, livemode, patient and an unexpired hold must all match. Otherwise `REVIEW_REQUIRED` for an authorised refund. Exactly once; live-mode events ignored on a test key | Unit tests; Stripe S1 and S4 | FIXED |
| P02-N03 | Payments | Medium | Charge used the current profile fee | `create_payment_intent` read `doctor_profiles.consultationFee` | Uses the fee stored on the reservation | `test_intent_amount_uses_fee_stored_at_reservation` | FIXED |
| P02-N04 | Appointments | High | A doctor could confirm an unpaid booking | No payment check in `confirm_doctor_appointment` | Requires PAID or NOT_REQUIRED; conditional update | `test_doctor_cannot_confirm_unpaid_appointment` | FIXED |
| P02-N05 | Refunds | High | Fake success without Stripe, assumed success, no cap, duplicates, refund while keeping the booking, double counting | See description | Cancelled or completed (dispute) bookings only; one open request; atomic claim; amount ≤ captured − refunded; real Stripe status (pending → processing); no fabricated IDs; refunded amount added once per request; partial refunds do not mark REFUNDED | Stripe S5; `test_p05p_*` | FIXED |
| P02-N06 | AI chats | Low | New Chat reopened a booking conversation | `draft` stayed true after booking actions | Booking state clears `draft` | `test_p02n06_*` | FIXED |
| P02-N07 | Manual booking | Medium | Retry after a cancelled payment hit a 409 against the patient's own hold | Every Pay tap called `createAppointment` | Reuses the valid hold; Release Reservation added | Code; widget tests | FIXED |
| P02-N08 | Reschedule | High | Any clock time accepted (for example 03:00); availability not updated; a taken slot gave a 500 | No check against real slots; unhandled DuplicateKey | Real open slot required (admin excepted); availability, version and history updated; DuplicateKey → 409, original unchanged | Stripe S6; `test_p05q_*` | FIXED |
| P02-N09 | Health tracking | Medium | Care Agenda readings had no safety alert | Two measurement endpoints; only one evaluated thresholds | The same existing thresholds now apply to both (still pending clinical review) | Care run step `agenda_crisis_bp` | FIXED (stores not merged; owner decision) |
| P02-N10 | Clinical privacy | High | A released or cancelled booking gave a doctor permanent record access | The care-relationship query had no status filter | Only CONFIRMED or COMPLETED visits (plus existing care plans, notes and records) count | Before: unrelated doctor 200; after: 403 (`patient-care-components-uat.json`); `test_p02n10_*` | FIXED |
| P02-N11 | Doctor dashboard | High | Fabricated KPIs ("12 Patients · 4 video", "LKR 18,500"), fake critical ECG alert, fake hospital | Hard-coded UI | Today's real appointments and verified payments; the alert and hospital label removed | `p02n11-*-before/after.png`; widget tests | FIXED (wider doctor-dashboard review is Phase 03) |
| P02-N12 | Prescription renewal | Medium | No doctor notification; any related doctor could review; double review possible | Missing notification; reassignment branch; check-then-update | Prescriber notified; prescriber-only review; atomic lock; patient notified of the decision | Care run 11_*; `test_renewal_*` | FIXED |
| P02-N13 | Test safety | Medium | Live API test hard-wired to 8000 and silently skipped | Default URL; the health probe ran under the test binding's mocked HttpClient | An explicit local `LIVE_API_BASE_URL` is required; 8000 refused; the backend must report `isolatedTestData`; real HTTP only after the guard | 13/13 live on 8001; guard test | FIXED |
| P02-N14 | Mobile models | Medium | LKR 2500 invented for missing fees | Model defaults | Nullable; "Not available" | Widget and unit tests | FIXED |
| P02-N15 | Cancellation | Low | Concurrent cancellations both applied | Unconditional update | Conditional on the read status | Stripe S5 (second cancel 400) | FIXED |
| P02-N16 | Appointments | Low | `datetime` NameError for records without timestamps | Import alias | Uses `_dt` | `test_appointment_without_fee_*` | FIXED |
| P02-N17 | Reservation hold | Low | Released hold shown "Payment pending" | Status not reset | Release and expiry set UNPAID | `test_bug063_release_hold_*` | FIXED (device re-run not repeated) |

## 3. Requirements and improvements implemented (not defects)

- **Audit trail:** an append-only `appointment_events` log records hold release, hold expiry, payment confirmation, cancellation, rescheduling and refund success. It stores IDs, roles and states only.
- **Expired-hold sweep:** runs in the durable background worker, uses an atomic claim per hold, and is safe across processes.
- **Real alternatives after a lost race:** when two patients accept the same AI proposal, the loser is offered real alternative times and nothing about the winner is revealed.
- **Cancellation preview:** `GET /appointments/{id}/cancellation-preview` shows the refund under the configured policy before the patient confirms.
- **Paid-cancellation refunds:** cancelling a paid booking opens one refund request; money moves only after admin approval.
- **Truthful delivery wording:** "accepted by provider", "not requested", "not sent" and "delivery unconfirmed".
- **Integration-test safety flag:** `/health` reports `database.isolatedTestData` outside production. It is a boolean only, with no database names.

## 4. Changed files

**Backend**
- `app/services/appointment_service.py`: detail fix, payment facts, release, preview, sweep, doctor confirmation, reschedule, cancellation.
- `app/services/payment_service.py`: settlement, livemode, fee source, notifications.
- `app/services/refund_service.py`.
- `app/services/booking_session_service.py`: proposal for typed slots, release, conflict alternatives, draft.
- `app/agents/booking_agent.py`: requested-date slots and same-doctor alternatives.
- `app/services/ai_booking_proposal.py`: `selectionReason`.
- `app/services/appointment_events.py` (new).
- `app/services/clinical_safety_service.py`.
- `app/services/prescription_workflow_service.py`.
- `app/services/care_plan_service.py`.
- `app/routes/appointment.py`.
- `app/routes/care_automation.py`.
- `app/schemas/appointment.py`.
- `app/schemas/care_plan.py`, `app/models/care_plan.py`.
- `app/config/database.py`.
- `app/main.py`.
- `scripts/seed_phase02_fixtures.py` (new).
- `scripts/migrate_consultation_type_in_person.py` (new).

**Mobile**
- `lib/models/appointment.dart`, `consultation.dart`, `timeline.dart`.
- `lib/widgets/appointment_payment_summary.dart` (new), `doctor_today_overview.dart` (new).
- `lib/screens/patient/appointment_detail_screen.dart`, `ai_care_assistant_screen.dart`, `booking_confirmation_screen.dart`, `care_agenda_screen.dart`, `patient_visit_detail_screen.dart`.
- `lib/screens/doctor/doctor_appointment_detail_screen.dart`, `doctor_home_screen.dart`, `create_care_plan_screen.dart`.
- `lib/services/appointment_service.dart`, `fcm_service.dart`.
- `lib/core/constants/api_constants.dart`.
- `test/integration/live_api_test.dart`, `live_target.dart` (new).

## 5. Regression tests

**New tests**
- **Backend:** `tests/test_phase02_booking_payment.py`, 33 tests against real local MongoDB. Stripe is mocked there; real Stripe test-mode runs are in the scripts.
- **Mobile:** `test/screens/phase02_booking_payment_ui_test.dart` (10) and `test/integration/live_target_test.dart` (4).

**Existing tests updated for stricter, intended behaviour** (each change is commented in the file):
- **Doctor confirmation now needs a verified payment:**
  - `tests/test_appointment.py`: 2 fixtures mark a verified payment before the doctor confirms.
  - `tests/test_appointment_booking.py`: 4 fixtures do the same.
- **Reschedule needs a real slot:** `tests/test_notifications.py`, where the reschedule test now has a real availability window.
- **Webhook verification:** `tests/test_payment.py`, where the duplicate-webhook mock is now a realistic PaymentIntent (amount and currency are verified).
- **Refund requires a cancelled booking:** `tests/test_phase5_admin_ai_automation.py`, where the booking is cancelled before the refund request and the Stripe mock returns a status.
- **Test double:** `tests/mock_db.py` gains `find_one_and_update`.
- **New truthful wording:**
  - `test/screens/ai_care_assistant_screen_test.dart`: "accepted by provider".
  - `payment_flow_test.dart`: the longer cancelled-payment message.
  - `doctor_home_render_test.dart`: the real "Today" heading; asserts there is no fabricated hospital or telemetry alert.
- **Unpaid holds are now released:** `appointment_flow_test.dart` cancels the confirmed booking instead; release is covered in the new suite.

## 6. Process notes

- **First Stripe run:** it stopped on a script error after the payment succeeded. That left patient A with one paid, confirmed test-mode booking (2 Dec, 09:00), which is kept as synthetic data.
- **Fixture correction:** the first P02 fixtures used the specialty "Orthopedics". The system's canonical name is "Orthopedic Surgeon", so I corrected my own two fixture profiles.
- **Configuration check:** printed the first 8 characters of several `backend/.env` values to my local tool output, including part of the SMTP password and part of the Gemini key. Nothing was sent anywhere, and no secret appears in any report, evidence file or commit. Rotating those two values is advisable as a precaution.
