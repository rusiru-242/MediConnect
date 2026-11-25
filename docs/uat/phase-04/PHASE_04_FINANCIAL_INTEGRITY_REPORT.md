# Phase 04 — Financial Integrity Report

For: the project owner and reviewers of payments and refunds. All money below is Stripe **test mode** on synthetic UAT data. No real transaction was created. 2026-11-26.

## 1. Definitions now used everywhere (P04-N05)

One module, `backend/app/services/financial_metrics.py`, is used by:
- the dashboard
- payment analytics
- the admin assistant
- the payments report
- doctor financials

| Term | Definition |
|---|---|
| Gross collections (`capturedAmount`, `grossAmount`) | Payments actually captured: status SUCCEEDED or REFUNDED, per currency |
| Refunded | Money returned on those payments. `refundedAmount` when recorded (partial refunds included); otherwise the full amount for a REFUNDED payment. Never more than captured |
| Net collections | Gross minus refunded. **Not platform profit** |
| Pending refunds | Open refund requests (requested, under review, approved, processing, failed and retryable) and the amount the policy or the admin set for them. Not yet returned |
| Platform revenue, doctor earnings | **Not calculated (null).** MediConnect has no configured platform fee or payout model. The invented "10% platform fee" was removed |
| Payment success rate | (succeeded + refunded) ÷ (succeeded + refunded + failed). **Null** when nothing was attempted (was 100%) |
| Date ranges | Asia/Colombo calendar days, end day inclusive. Payments are placed by `paidAt`, or `createdAt` if never paid |

**Before Phase 04:** gross excluded refunded payments and refunds were then subtracted again. For a data set of 3,000 paid + 2,000 refunded + 1,000 with 200 partially refunded, the dashboard showed gross 4,000 / net 2,000. The correct figures are **6,000 / 2,200 / 3,800** (`test_n05_…`).

## 2. Reconciliation results (live UAT, run `6e232e`)

| Check | Result |
|---|---|
| Dashboard money vs. an independent MongoDB recomputation (A-02c) | LKR gross 89,500.00 / refunded 20,800.00 / net 68,700.00: **identical**; platform revenue null |
| Last-30-days analytics vs. MongoDB counts (A-06c) | Succeeded 36, failed 3, refunded 9: **identical**; success rate 93.8% |
| Payments report vs. analytics (A-13b) | Captured 97,200.00 / refunded 22,800.00 / net 74,400.00 LKR: **identical**; no platform fee field |
| **Stripe test mode vs. MongoDB (A-07c)** | **54** real test PaymentIntents retrieved from Stripe. Status, amount, currency and refunded amount agree, and `livemode=false` on all. **0 mismatches** |
| Reconciliation rules (A-07e) | Discrepancies found:<br>• `CANCELLED_AWAITING_REFUND_DECISION` ×11<br>• `CANCELLED_PAID_WITHOUT_REFUND_REQUEST` ×1<br>• `MISSING_PAYMENT_EVIDENCE` ×1<br>• `DELAYED_PENDING` ×3<br>No recommendation to confirm a booking (was the advice for every cancelled paid booking) |

Explanation of the two notable discrepancies (both genuine, and both correctly reported):
- `CANCELLED_PAID_WITHOUT_REFUND_REQUEST`: a Phase 03 booking created on 2026-11-25 at 14:30 UTC. This was the **before-fix** reproduction of P03-N03: the doctor cancelled a paid visit and no refund request was opened. Phase 03 fixed the cause. Historical records like this now surface in reconciliation, and an administrator decides each one; no automatic backfill was run (P4-B6).
- `MISSING_PAYMENT_EVIDENCE`: the Phase 04 synthetic completed visit, deliberately stored as PAID without a payment record.

## 3. Refunds (Stripe test mode)

| Scenario | Result | Evidence |
|---|---|---|
| Patient cancellation → refund request | Source `patient`. Existing policy: cancelled more than 24 h ahead → 100% (LKR 2,000) | A-10a |
| Doctor cancellation → refund request (P3-B3) | Source `doctor`, 100%, visible with the doctor filter | A-10b |
| Doctor leave → refund request | Source `leave`, 100% (LKR 1,800); the booking was cancelled by the leave | A-10c |
| Approval above the captured amount | 400; nothing sent to Stripe | A-10j0 |
| 4 concurrent approvals | One 200 (others 400/409); **one** Stripe refund | A-10h |
| Stripe result | Refund `succeeded`; PaymentIntent `livemode=false`; 200,000 minor units = LKR 2,000.00 | A-10f |
| Cross-role consistency | Payment REFUNDED (2,000); appointment REFUNDED; patient view `refundStatus succeeded`, refunded 2,000; patient notified | A-10j |
| Duplicate prevention | Re-approval 400; second request 400; still one Stripe refund | A-10g |
| Rejection | 200, then 409 on a second reject; approval after rejection 409; no Stripe refund; patient notified | A-10e |
| Stripe rejects the request (unknown PaymentIntent) | 502; request `failed` with `InvalidRequestError`; payment not marked refunded; retry fails the same way | A-10i |
| Network fails **after** Stripe succeeded | Request `failed`; the retry uses the same idempotency key, Stripe returns the same refund, and it is recorded once | `test_n10_refund_failure_then_retry_after_external_success` (mocked Stripe) |
| Approval racing a rejection | The rejection gets 400/409; the approval completes; status `succeeded` (rejection is conditional, P04-N09) | `test_n09_…` |
| Partial refund | Payment stays SUCCEEDED with `refundedAmount`, appointment stays PAID; counted in refunded totals | Phase 02 `test_p05p_…`; `test_n05_…` |
| Browser approval with double click | One request; toast states Stripe's result | A-16f (P04-N23) |

**Policy unchanged:**
- **Doctor cancellation:** 100%.
- **Patient cancellation:**
  - 24 hours or more before the visit: 100%
  - less than 24 hours before: 80%, after a 20% fee
  - after the visit time, or once the visit is completed: dispute (eligible amount 0)

  Reschedule rules are unchanged as well. Any change is an owner decision (**B6**).

## 4. Payment monitoring safety

| Check | Result |
|---|---|
| A declined card (`pm_card_chargeDeclined`) is never recorded as paid | Stripe `requires_payment_method`; local FAILED; booking stays PENDING (A-07b) |
| Duplicate PaymentIntent record | Rejected by the unique index `idx_payments_stripe_pi_unique` (A-07d) |
| Patient, doctor or admin forcing payment or booking state | Patient/doctor reconcile or approve → 403. The booking status PUT is doctor-only and payment-checked; admin gets 403. No admin route confirms a booking (A-07f, A-05f) |
| Test or live mode shown truthfully | From the configured key or the stored `livemode` (was always "TEST MODE") (P04-N04) |

## 5. Limitations and open items

| Item | Owner / phase |
|---|---|
| Stripe refunds returned as `pending` remain `processing` until an admin retries after 2 minutes; there is no refund webhook (needs live webhook delivery, B3) | Phase 05 |
| `POST /payments/{id}/reconcile-refund` refunds in full and writes no admin audit record (P4-O7) | Phase 05 |
| Historical paid doctor-cancellations without a refund request (found by reconciliation) | Owner/admin review; no automatic backfill (P4-B6) |
| Refund and reschedule policy | Owner decision (B6) |
| Platform fee and doctor payout model | Not configured; owner decision before any "revenue" or "earnings" figure is shown (P4-B7) |
