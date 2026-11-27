# A03 — Stripe Payment, Reservation and Refund Verification (Agent 01)

For: the project owner, reviewers and engineers. 2026-11-27. Stripe **test mode only**: the `sk_test_` key from `backend/.env` (never printed), and every object `livemode=false`. No real card, no real money, no real person.

## 1. Set-up

| Item | Value |
|---|---|
| Backend | UAT 127.0.0.1:8001 (`mediconnect_uat`, local MongoDB); a second process on 127.0.0.1:8002 (same DB) for the multi-process race |
| Webhooks | `stripe listen --forward-to http://127.0.0.1:8001/api/payments/webhook` (Stripe CLI 1.50.1, owner approved, test key), signing secret passed through a file (`-StripeWebhookSecretFile`) |
| Dates | Relative to the Asia/Colombo date (2026-11-27): doctors' real availability 5–7 days ahead |
| Accounts | `uat.p02.patienta/b/c`, `uat.p03.patienta` (emulator), `uat.admin`, `uat.p02.doctor.ortho`, `uat.doctor.cardio2` (synthetic) |
| Scripts | `a03_live_stripe_uat.py` (`main`, `restart1-3`), `browser_admin_uat_a03.mjs`, emulator helper `emu.py` |
| Evidence | `evidence/a03_live_stripe_uat.json` (43 steps), `a03_backend_restart_during_payment.json`, `before_open_intents_on_cancelled_holds.json`, `a03_cross_role_refund.json`, `a03_browser_admin_uat.json`, `emulator/`, `browser/` |

**Live run:** 43 of 43 steps PASS. Two steps first recorded FAIL and were re-evaluated, with the reasons kept in the JSON:

- **P05 (a script-check defect):** Stripe's search index is eventually consistent and returned 0 intents seconds after creation. Direct retrieval found 1 intent and 1 charge, and the script now uses direct retrieval.
- **C10b (timing):** Stripe failed the `pm_card_refundFail` refund after the 90-second wait, while the backend was down for the restart test. Its events were resent and processed (see the webhook report).

## 2. Reservation management

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A03-R01 | Atomic reservation | `POST /appointments` 201, PENDING hold; unique index `idx_appt_doctor_slot_unique_active` present in UAT and now always in tests | PASS |
| A03-R02 | Concurrent reservation | 6 slots × 4 simultaneous requests from **2 patients via 2 backend processes** (8001, 8002) → exactly **1 winner** per slot, the rest 409; automated P05 race repeated | PASS |
| A03-R03 | Hold countdown | `holdExpiresAt − createdAt = 600 s` (server-owned). Emulator: countdown 09:46 → restored as 00:43 after an app restart (`a03_05`, `a03_09`) | PASS |
| A03-R04 | Automatic expiry | Live: hold expired by the backend worker (`cancelledBy: SYSTEM`). Emulator: a hold created in the app expired and showed "Reservation Hold Expired" (`a03_10`) | PASS |
| A03-R05 | Manual release | `release-hold` 200 → CANCELLED, UNPAID; its intent cancelled at Stripe | PASS |
| A03-R06 | Released slot availability | The released 11:00 slot is in the doctor's availability again | PASS |
| A03-R07 | Backend restart recovery | Payment succeeded while 8001 was down (the CLI delivery failed); after the restart the appointment was still PENDING, and the patient's status refresh confirmed it once. Emulator: app force-stop and relaunch restored the hold card | PASS |
| A03-R08 | Duplicate reservation request | Same patient, same slot twice → 201 then 409; one active appointment | PASS |

## 3. Payment integrity

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A03-P01 | Stripe test payment success | API: `pm_card_visa` → CONFIRMED by the CLI-delivered webhook before any status call. **Emulator:** card 4242 4242 4242 4242 entered in the PaymentSheet (TEST badge, "Pay LKR3,500.00") → "Payment confirmed!" shown only after backend confirmation (`a03_14`, `a03_15`) | PASS |
| A03-P02 | Declined payment | API `pm_card_chargeDeclined` → payment FAILED, appointment not confirmed, exactly one "Payment failed" notice. **Emulator:** 4000 0000 0000 0002 → "Your payment method was declined." in the sheet (`a03_13`) | PASS |
| A03-P03 | Cancelled payment | Release → intent `canceled`; a later payment attempt → `payment_intent_unexpected_state`; the CLI-delivered `payment_intent.canceled` → no change | PASS |
| A03-P04 | Payment retry | After a decline, `create-intent` reuses the same intent; `pm_card_visa` → CONFIRMED. Emulator: decline then success in the same sheet (A03-BUG-004 path) | PASS |
| A03-P05 | Duplicate charge prevention | A second `create-intent` before payment reuses the intent; after success → 400 "already paid"; exactly 1 intent and 1 succeeded charge (re-evaluated, see §1) | PASS |
| A03-P06 | Amount and currency verification | The client sent `amount: 1`; the PaymentIntent is 300000 minor units LKR = the server fee 3,000.00, `livemode=false`. Mismatch handling: P02 tests (amount, currency, livemode → review, never confirmed) | PASS |
| A03-P07 | Payment ownership | Another patient: status 403, create-intent 403 | PASS |
| A03-P08 | Expired-hold payment | Hold expired → worker released it **and cancelled its intent** (A03-BUG-005) → paying the old intent fails (`payment_intent_unexpected_state`); a new intent → 400. The 3 pre-existing payable intents on cancelled holds → `canceled` | PASS (after fix) |
| A03-P09 | Cancelled appointment payment | Patient cancels an unpaid hold → paying its intent fails | PASS |
| A03-P10 | Network failure recovery | See R07 (webhook lost; status refresh recovers; the resent event → `already_processed`) | PASS |

## 4. Cancellation and refunds (existing rules only)

The policy is not changed: 100% when cancelled 24 h or more ahead or when the doctor cancels, 80% within 24 h (owner decision B6 still open).

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A03-C01 | Patient cancellation | Preview 200 → cancel 200 → CANCELLED; emulator preview "Refund under the cancellation policy: LKR 3,500 … reviewed and approved by MediConnect" (`a03_20`) | PASS |
| A03-C02 | Doctor cancellation | Doctor cancel 200 → refund request `source: doctor`, "100% full refund guaranteed" | PASS |
| A03-C03 | Rescheduling | Paid appointment moved to a real open slot 7 days ahead → 200, version 2, still PAID, `remindersSent` reset | PASS |
| A03-C04 | Failed rescheduling preserves booking | Target slot booked by another patient → 409; original date, time, CONFIRMED and PAID unchanged | PASS |
| A03-C05 | Refund request | Created on cancellation: `requested`, source patient, eligible = paid (more than 24 h ahead) | PASS |
| A03-C06 | Admin refund approval | API approval → Stripe test refund `succeeded`, `metadata.refundId` set (A03-BUG-007). **Browser:** approval of the emulator patient's refund, one POST for a double click, toast "succeeded in Stripe" (`a03_b03`) | PASS |
| A03-C07 | Admin refund rejection | Reject 200 → `rejected`, no Stripe refund exists | PASS |
| A03-C08 | Duplicate refund prevention | Re-approve → 400; second cancel → 400; one Stripe refund | PASS |
| A03-C09 | Concurrent refund approval | 4 parallel admin approvals → one 200, three 400; **one** Stripe refund | PASS |
| A03-C10 | Stripe test refund reconciliation | Payment REFUNDED, refundedAmount = captured, appointment `paymentStatus` REFUNDED, request `succeeded`. Refund failure after success (`pm_card_refundFail`) → `flagged_for_review`; visible to admins (A03-BUG-009) | PASS (after fixes) |

**Cross-role consistency** (`a03_cross_role_refund.json`, emulator `a03_21`/`a03_22`, browser `a03_b06`/`a03_b07`): the same appointment showed the same facts in every view:

| View | Status | Payment | Amount | Refund | Other |
|---|---|---|---|---|---|
| Patient app | CANCELLED | Refunded | LKR 3,500 paid | Refunded (LKR 3,500) | Full reference shown |
| Doctor API | CANCELLED | REFUNDED | amountPaid 3500 | succeeded | IN_PERSON, cancelled by patient |
| Admin web | Cancelled booking listed | Payments: LKR 3,500 marked Refunded | — | — | — |

## 5. A02 reminders and notifications preserved

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A03-U05 | Notification deep link | Emulator: "Refund issued" notification → the exact appointment detail in its current state (`a03_24`) | PASS |
| A03-U06 | Correct appointment reminder | Unchanged scheduler code; automated P05 s06 and A02 suites pass in the final run (24 h / 2 h, Asia/Colombo, CONFIRMED only). Live delivery was evidenced in A02; the A03 bookings are 4–7 days ahead, so none fell due during the run | PASS (automated; live in A02) |
| A03-U07 | Obsolete reminder cancellation | Reschedule bumps `appointmentVersion` and resets `remindersSent` (live C03); P05 s06f/s06g (cancel/reschedule invalidate materialised reminders) pass | PASS (automated + live state) |
| A03-U08 | In-person semantics | Summary "Visit type: In-person at the clinic" (A03-BUG-015), list and detail "In-person visit", doctor API `IN_PERSON`; no video control anywhere in the flow | PASS |

**Notification accuracy:**
- The confirmation outbox for the emulator booking recorded e-mail `disabled` (provider not configured), SMS `skipped` (no consent) and doctor `delivered`. The app now says "not sent (service not available)" instead of "pending" (A03-BUG-018).
- The patient now gets an in-app "Payment Successful" for AI bookings (A03-BUG-020).

## 6. What these tests do not show

- **Physical phone:** emulator only. One emulator run hit an Android system ANR during the PaymentSheet (A03-O3). Physical-device PaymentSheet testing is still B10.
- **Real money and live mode:** never used.
- **Refund policy:** the current coded rule is an unconfirmed owner decision (B6).
