# Phase 02 — Patient UAT Report (emulator and live API)

For: the project owner and independent reviewers. 2026-11-25 · branch `fix/phase-02-booking-payment-patient-care`.

## 1. Environment

- **Backend:** UAT backend on `127.0.0.1:8001`:
  - `ENVIRONMENT=staging` and local MongoDB `mediconnect_uat`; `/health` reports `isolatedTestData: true`.
  - Deterministic AI; external image processing disabled.
  - Stripe in test mode; SMTP, FCM and SMS not configured.
  - A second process on `8002` was used only for the concurrency tests.
- **Device:** Android 17 emulator. Debug build with `--dart-define=API_BASE_URL=http://10.0.2.2:8001` (`mobile/build/app/outputs/flutter-apk/app-debug.apk`, built 2026-11-25 16:26).
- **Accounts:**
  - The owner's `uat.patient2`, for read-only viewing only.
  - Synthetic `uat.p02.patientb` and `uat.p02.doctor.ortho`.
  - The UAT password was typed from `backend/uat.env` and never displayed.
- **Input safety:** every injected input first checked that MediConnect was the foreground app and aborted otherwise. No third-party app received input, nothing was shared externally, and no telephone call was placed.

## 2. Emulator walkthrough

| # | Step | Result | Status | Evidence |
|---|---|---|---|---|
| E1 | Owner's booking (read-only), My Appointments → View Details | In-person visit; fee LKR 2,500; Paid; amount paid LKR 2,500; paid on 2026-11-25 12:50; full 24-character reference with copy | PASS (BUG-058) | `bug058-patient-detail-payment-and-reference.png` |
| E2 | P02 patient: Notifications → "Appointment Rescheduled" | Appointment details open, where "Appointment not found." used to appear | PASS (BUG-060) | `bug060-patient-notification-opens-detail.png` |
| E3 | Copy booking reference | "Booking reference copied." | PASS | — |
| E4 | Cancel Appointment on a paid booking, then Keep Appointment | Dialog shows "Refund under the cancellation policy: LKR 3,000 … reviewed and approved by MediConnect"; after Keep, the database still says CONFIRMED/PAID | PASS (P-05o) | `p05o-paid-cancel-shows-refund-policy.png` |
| E5 | Restored chat from the concurrency test | Real conflict message with alternative times | PASS (P-05n) | `p05n-ai-conflict-real-alternatives.png` |
| E6 | New Chat: "Book Dr. P02 Spine on December 6, 2026 at 10:00" | Proposal for that doctor, date and time | PASS (BUG-061/062 regression) | `bug061-ai-proposal-same-doctor.png` |
| E7 | Accept & Continue | Hold created; Stripe test PaymentSheet opens (inside the MediConnect package) | PASS | `bug063-stripe-test-paymentsheet-open.png` |
| E8 | Close PaymentSheet (Back, no card entered) | "Payment was cancelled. You have not been charged…"; appointment PENDING, payment PENDING, not confirmed; hold card shows 09:31 left and Release Reservation | PASS | `bug063-sheet-closed-hold-card-release-action.png` |
| E9 | Release Reservation | Confirmation dialog ("Release this reservation? … You have not been charged.") | PASS (BUG-063) | `bug063-release-confirmation-dialog.png` |
| E10 | Confirm Release | "Your reservation was released … No payment was taken."; database CANCELLED; Stripe PaymentIntent `canceled`; 10:00 bookable again by another patient; audit event HOLD_RELEASED | PASS (BUG-063) | `bug063-reservation-released.png` |
| E11 | Doctor: Notifications → "New Booking Request" | Manage Appointment opens with data | PASS (BUG-060) | `bug060-doctor-notification-opens-manage-appointment.png` |
| E12 | Doctor: Confirmed → P02 Patient B | Payment status Paid; consultation fee LKR 3,000; amount paid LKR 3,000 | PASS (BUG-059) | `bug059-doctor-detail-fee-and-amount-paid.png` |
| E13 | Doctor home before and after the fix | Before: fake "CRITICAL TELEMETRY ALERT" and "National Hospital Center". After: "Today" panel with real figures only | PASS (P02-N11) | `p02n11-doctor-home-*.png` |
| E14 | Framework errors (two sessions, 491 + later log) | 0 `EXCEPTION CAUGHT`, 0 `Another exception`, 0 overflow, 0 `setState() after dispose` | PASS | log scan |

**Observed on the device and fixed afterwards:**
- After E10, the earlier "Payment was cancelled … slot stays held" note stayed on screen.
- The released hold kept `paymentStatus: PENDING`.

Both are fixed in `56d6bc8` and covered by tests. The device walkthrough was **not** repeated after that fix.

## 3. Live API UAT runs

| Run | Script / evidence | Result |
|---|---|---|
| Before and after reproductions | `repro_bug055_061.py`, `repro_bug061_multi.py`, `evidence/bug0*.json` | BUG-055, 060 and 061 and P02-N01 reproduced before the fix and resolved after |
| Stripe test mode, 36 steps | `stripe_test_mode_uat.py`, `evidence/stripe-test-mode-uat.json` | All steps as expected (see the booking and payment verification report) |
| Two-process concurrency | `concurrency_uat.py`, `evidence/concurrency-two-processes.json` | 5/5 rounds with exactly one winner; AI race and double-tap safe |
| Backend restart during payment | `evidence/backend-restart-during-payment.json` | Settled once through the other process |
| Patient care components 05–13, 71 steps | `patient_care_uat.py`, `evidence/patient-care-components-uat.json` | All as expected after the P02-N09, N10 and N12 fixes |
| Phase 01 AI probe regression | `evidence/phase01-probe-regression.json` | 35 scenarios, 45 turns, **0 differences** from the Phase 01 results |
| Flutter live API integration | `mobile/test/integration/live_api_test.dart` | 13/13 on 8001; port 8000 refused by the guard |

**Command used for the live integration test:**

```
RUN_LIVE_TESTS=true LIVE_API_BASE_URL=http://127.0.0.1:8001/api \
LIVE_API_EXISTING_EMAIL=uat.p02.patientc@uat.mediconnect.lk LIVE_API_LOGIN_PASSWORD=<from backend/uat.env> \
flutter test test/integration/live_api_test.dart
```

## 4. Not covered here

- **No physical phone.**
- **No real push, email or SMS:** none are configured in UAT.
- **No real Stripe-to-backend webhook delivery:** the Stripe CLI is unavailable.
- **No Sinhala or Tamil review** of the new strings.

See [PHASE_02_REMAINING_BLOCKERS.md](PHASE_02_REMAINING_BLOCKERS.md).
