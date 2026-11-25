# Phase 02 — Booking and Payment Verification

2026-11-25 · Local UAT backend `127.0.0.1:8001` (a second process on `8002` for the concurrency tests) · database `mediconnect_uat` · automated tests on `mediconnect_test` · **Stripe test mode only** (`sk_test_`, `livemode=false`). Port 8000 was never contacted. Synthetic fixtures: `uat.p02.patienta/b/c`, Dr. P02 Ortho (LKR 3,000) and Dr. P02 Spine (LKR 2,800), created with `backend/scripts/seed_phase02_fixtures.py` (insert-only).

**Method labels:**
- **Unit:** function-level test.
- **Local API:** a FastAPI TestClient test against real local MongoDB.
- **UAT API:** real HTTP calls to the running UAT backend.
- **Stripe test:** a real Stripe test-mode API.
- **Emulator:** the Android 17 emulator.

## 1. Owner's historical UAT evidence (read-only re-check)

| Owner booking | Found | Current state |
|---|---|---|
| UAT Patient One · Dr. UAT Neuro · 2026-11-26 10:00–10:30 · LKR 2,500 | Yes | CONFIRMED / PAID |
| UAT Patient Two · Dr. UAT Neuro · 2026-11-26 10:30–11:00 · LKR 2,500 | Yes | CONFIRMED / PAID; shown on the device with full payment details |
| UAT Patient Two · Dr. UAT Neuro · 2026-11-26 11:00–11:30 · LKR 2,500 | Yes | CONFIRMED / PAID |

- Patient Two also has two CANCELLED records: one expired or released hold at 11:00, and one at Dr. UAT General. Only one active booking exists per slot.
- No owner booking was modified, deleted or duplicated.
- The doctor list for Dr. UAT Neuro shows exactly the three confirmed bookings.

The owner's earlier UI-level results remain theirs. Phase 02 re-verified the underlying behaviour independently:

- **Booking, payment, decline-then-retry, cancellation, hold expiry and slot release:** Stripe S1–S5.
- **Booked slot hidden from another patient:** concurrency C1.
- **Doctor notifications:** the patient-care run and the emulator.

## 2. Booking lifecycle checks (request items 1–20)

| # | Check | Result | Method |
|---|---|---|---|
| 1 | Patient authentication | Patient role and active account enforced; other roles 403 | Local API |
| 2 | Doctor eligibility | Only APPROVED and ACTIVE doctors are bookable | Existing tests + code |
| 3–5 | Doctor selection, real availability, proposal | Proposals come from real slots; a typed time uses the requested date (P02-N01 fixed) | UAT API |
| 6 | Timezone | Asia/Colombo for slots, reminders and "today"; past-slot checks in Sri Lanka time | Unit + UAT |
| 7 | Exact doctor, date and time | Kept through alternatives; never swapped silently (BUG-061) | UAT API |
| 8–10 | Summary, masked contacts, patient note | Masked email and phone; note persisted (shown on the doctor screen) | Existing tests + device |
| 11 | Explicit confirmation | A hold is created only on Accept; PaymentSheet only after the hold | Emulator |
| 12 | Server-side fee | Client `amount: 1` ignored; 300000 minor units (LKR 3,000) charged | Stripe S1 |
| 13 | Atomic reservation | Partial unique index plus conditional updates; 5 × 6 concurrent attempts → exactly 1 | UAT API, 2 processes |
| 14 | PaymentIntent creation | Reused before payment and after a decline; one intent per booking (checked in Stripe) | Stripe S1/S2 |
| 15 | Payment verification | Amount, currency, intent ID, livemode, owner and hold validity all checked | Unit + Stripe |
| 16 | Confirmation | Exactly once (`already_processed` on repeats) | Stripe S1 |
| 17 | Patient and doctor retrieval | `GET /appointments/{id}` 200 for patient, doctor and admin (was 500) | UAT API + device |
| 18 | Notifications | Patient payment success, doctor confirmation; idempotency keys prevent duplicates | Stripe S1 (1 notification) |
| 19 | Audit events | `appointment_events`: PAYMENT_CONFIRMED, HOLD_RELEASED, HOLD_EXPIRED, APPOINTMENT_CANCELLED, APPOINTMENT_RESCHEDULED, REFUND_SUCCEEDED | UAT DB + tests |
| 20 | Hold expiry and release | Server-owned `holdExpiresAt` (10 min); expired holds swept by the worker; a payment after expiry is never confirmed | Stripe S4 + unit |

## 3. Reservation hold management

- **Duration and countdown:** 10 minutes, owned by the server. The app counts down from `holdExpiresAt`, and the device showed `09:31` remaining.
- **Duplicate holds:** none possible; the unique index enforces one active hold per slot.
- **Retry during a valid hold:** the same PaymentIntent is reused (Stripe S2).
- **Expired holds:** create-intent rejects them; the expiry sweep cancels them with SYSTEM as the actor and records them `UNPAID`.
- **Recovery after restart:**
  - **Backend:** process 8002 created the hold and PaymentIntent and was stopped; the payment was completed in Stripe and settled through 8001 (`backend-restart-during-payment.json`).
  - **App:** the AI chat restores the session with its hold from the server.
- **Closing PaymentSheet:** the appointment stays PENDING and the payment PENDING. There is no charge and no confirmation (emulator and Stripe S3).
- **Release Reservation (BUG-063):** confirmation dialog, then the Stripe PaymentIntent is `canceled`, the appointment CANCELLED/UNPAID, and the slot is visible to another patient again (emulator and S3).
- **Race between release and payment:** if Stripe reports `succeeded`, the release is refused (409) and the payment is settled. If it reports `processing`, the release is refused. A paid booking is never cancelled through this path (unit tests).

## 4. Concurrency (P-05n)

**Method:** two separate UAT backend processes (ports 8001 and 8002) shared `mediconnect_uat`. A thread barrier released 6 requests at once (3 patients × 2 processes), for 5 different slots. Evidence: `evidence/concurrency-two-processes.json`.

**REST reservation**
- Each round returned exactly 201 ×1 and 409 ×5.
- One active record per slot.
- The losers got 403 when they tried to read the winner's appointment.

**AI proposal acceptance (two patients, two processes)**
- Results: 200 and 409.
- The loser's message gave real alternatives ("Open times with Dr. P02 Spine that day: 11:00, 10:30, 10:00, 09:30") and did not name the other patient.

**Double-tapped PaymentIntent creation (one request per process)**
- 201 and 201, returning the same payment ID.
- One payment record and one Stripe PaymentIntent.

**In-process repeats**
- 5 rounds × 8 threads: exactly one winner each.
- Concurrent expiry sweeps release each hold exactly once.
- Concurrent refund approvals make exactly one Stripe call.

**Mechanism**
- Database-level: a partial unique index on (doctor, date, time) for active statuses, plus conditional `find_one_and_update` claims.
- No in-memory locks.

## 5. Stripe test-mode verification

Real Stripe test-mode API calls with Stripe's test PaymentMethods (`pm_card_visa`, `pm_card_chargeDeclined`). The script is `stripe_test_mode_uat.py`; the output is `evidence/stripe-test-mode-uat.json` (36 steps, with masked IDs).

| Requirement | Result | Method |
|---|---|---|
| Amount and currency | 300000 minor units of LKR (LKR 3,000) in Stripe; matches the reserved fee | Stripe test |
| Server-owned fee / no default fee | Client value ignored; a missing fee → 409; mobile shows "Not available" | Stripe + unit |
| Success | `succeeded` → CONFIRMED/PAID; 1 payment record; 1 notification | Stripe test |
| Decline | `card_declined` → payment FAILED, appointment PENDING | Stripe test |
| Cancelled payment | PaymentSheet closed → nothing confirmed; release cancels the intent in Stripe | Stripe + emulator |
| Retry after decline | Same intent; visa succeeded → CONFIRMED | Stripe test |
| Duplicate client submissions | Before payment: same intent. After payment: 400 "already paid" | Stripe test |
| Duplicate status refresh | Two refreshes → same state; no second confirmation | Stripe test |
| Network failure / backend restart after success | Settled on the next status call through another process | Stripe test |
| Delayed webhook | Webhook arriving after the status sync → `already_processed` | Stripe test (locally signed) |
| Duplicate webhook events | `already_processed` twice | Stripe test (locally signed) + unit |
| Out-of-order events | `payment_failed` after success leaves SUCCEEDED/PAID | Local API |
| Invalid signature | 400 "Invalid Stripe webhook signature." | Stripe test (locally signed) |
| Amount / currency mismatch | `REVIEW_REQUIRED`, not confirmed | Unit |
| Ownership mismatch | Not applied | Unit |
| Live-mode event on a test key | Ignored (`livemode_mismatch`) | Local API |
| Expired reservation payment | Payment after expiry → REVIEW_REQUIRED, not confirmed; admin reconcile-refund created exactly 1 real test refund (`succeeded`); a repeat is refused | Stripe test |
| Exactly-once confirmation and financial effects | 1 confirmation, 1 notification, 1 refund per request; Stripe search shows 1 PaymentIntent per paid booking | Stripe test |
| **Actual Stripe → backend webhook delivery** | **BLOCKED**: the Stripe CLI is not installed, so Stripe cannot reach this local backend. The steps above sign the *real* test-mode PaymentIntent object locally with the configured secret; they prove signature checking and idempotent processing, **not** external delivery | — |

**Reconciliation:**
- **Successful payments:** each paid booking has one MongoDB payment record, one Stripe PaymentIntent, and an appointment CONFIRMED/PAID with the same intent ID.
- **Cancelled payment (S3):** the PaymentIntent is `canceled` and the payment record CANCELLED.
- **Refunds (S4/S5):** Stripe refunds are `succeeded`, and the payment records are REFUNDED with `refundedAmount` set.

## 6. Cancellation, refunds and rescheduling (P-05o, P-05p, P-05q)

**Policy used:**
- **Refund rules:** the **existing configured rules** in `refund_service.py`, unchanged:
  - **24 hours or more before the visit:** 100%.
  - **Less than 24 hours:** 80% (a 20% fee).
  - **Doctor cancellation:** 100%.
  - **Visit already passed or completed:** dispute review.
- **Approval:** an administrator approves every refund.
- **Not invented:** no cancellation deadline and no extra fees. These rules still need owner confirmation (blocker B6).

| Item | Result | Method |
|---|---|---|
| P-05o cancellation | Ownership checked; preview shows the refund before confirmation (device: "Refund under the cancellation policy: LKR 3,000 … reviewed and approved by MediConnect"); conditional cancel; a second cancel is rejected (400); the slot frees up; reminders are cancelled (the scheduler drops cancelled sources: 0 pending reminders after cancel) | Stripe S5 + emulator + UAT |
| P-05p refunds | A paid cancellation opens 1 refund request; admin approval → real test refund `succeeded` (300000); over-refund 400; duplicate approval 400; no Stripe key → 503 with no fabricated refund; Stripe `pending` → `processing`; partial refund keeps SUCCEEDED with `refundedAmount`; refund only for cancelled or completed (dispute) bookings; audit log entries | Stripe + unit |
| P-05q reschedule | Must be a real open slot (03:00 → 409); the move is atomic and the original stays unchanged on failure; same doctor and patient; version bumped; history recorded; old reminders invalidated; 2 notifications; still 1 payment (no second charge) | Stripe S6 + unit |
| Fee differences on reschedule | **Not implemented.** No approved policy exists; the booking keeps its original paid amount. Owner decision required (B6) | — |
| P-05r admin payment verification | Admin payments list (200), reconciliation run (200), reconcile-refund for a payment that could not be confirmed (real test refund) | UAT API + Stripe |
