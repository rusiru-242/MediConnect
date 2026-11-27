# A03 — Stripe Webhook Verification

For: the project owner, reviewers and engineers. 2026-11-27. This closes the Phase 02 blocker B3 for **test mode with Stripe CLI forwarding**. Delivery to a public or production endpoint was not tested, and must not be.

## 1. Three kinds of evidence, kept apart

| Kind | What it proves | Where |
|---|---|---|
| 1. Locally signed test events | The signature check on the raw body, idempotency, ordering and retry logic, with events signed exactly as Stripe signs them and verified by the real `stripe` library | `tests/test_phase05_stripe_webhooks.py`, `tests/test_a03_booking_payments.py`, live W01–W04 (signed with the CLI secret against the running UAT backend) |
| 2. **Actual Stripe-generated test events forwarded by the Stripe CLI** | Stripe creates the event, signs it with the CLI endpoint secret, and the CLI POSTs it to 127.0.0.1:8001. The backend stores the exact Stripe event id | `evidence/a03_live_stripe_uat.json`, the CLI log (secret redacted), `stripe_webhook_events` |
| 3. Production / dashboard endpoint delivery | Stripe's own HTTPS delivery and its retry schedule (up to 3 days) | **Not tested** (forbidden; there is no public endpoint). Owner set-up steps are in `A03_REMAINING_BLOCKERS.md` |

**Set-up:**
- The Stripe CLI's login had expired on 2026-11-16. With owner approval it ran with `STRIPE_API_KEY` set to the backend's `sk_test_` key (environment only, never printed).
- `stripe listen --print-secret` wrote the endpoint secret to a scratch file. The UAT launcher read it with `-StripeWebhookSecretFile` and prints only "webhook secret=stripe-cli file".
- The CLI log is filtered through a redaction step (`whsec_<redacted>`).

## 2. Endpoint behaviour

- **Signature:** `POST /api/payments/webhook` reads the **raw body** and verifies `Stripe-Signature` with `stripe.Webhook.construct_event` (300 s tolerance).
- **Mode:** an event whose `livemode` does not match the key's mode is ignored.
- **Event log:** each event id is stored in `stripe_webhook_events` (id, type, livemode, created, status, outcome, attempts; never the payload) **before** any record changes.

## 3. Results

| ID | Scenario | Evidence | Kind | Status |
|---|---|---|---|---|
| A03-W01 | Valid locally signed event | Signed with the CLI secret → 200 (`ignored_unknown_payment` for an unknown intent) | 1 | PASS |
| A03-W02 | Invalid signature | Wrong secret → 400; body altered after signing → 400; old timestamp → 400 (P05) | 1 | PASS |
| A03-W03 | Duplicate event | Same event id again → 200 `already_processed`, no record touched | 1 | PASS |
| A03-W04 | Out-of-order event | `payment_failed` signed after the success → `ignored_out_of_order`, no "Payment Failed" notice (A03-BUG-003). Refund `pending` after `succeeded` → `ignored_out_of_order` (P05). Real ordering: decline then success on one intent delivered by the CLI → final state CONFIRMED | 1 + 2 | PASS |
| A03-W05 | Actual Stripe test webhook delivery | 51 Stripe-generated events forwarded by the CLI: 46 answered HTTP 200, 0 non-2xx, 5 not delivered while the backend was stopped (W08). Types: `payment_intent.succeeded` (`evt_3UgK…t4wg`, attempts 1, outcome `success`), `payment_intent.payment_failed` (outcome `failed_recorded`), `payment_intent.canceled`, `refund.created`, `refund.updated`, `refund.failed`, `charge.refunded`, `charge.refund.updated` | 2 | PASS (CLI forwarding) |
| A03-W06 | Payment success reconciliation | A booking confirmed by the CLI-delivered `payment_intent.succeeded` alone (before any status call): appointment CONFIRMED/PAID, payment SUCCEEDED/CONFIRMED, one success notice, one `PAYMENT_CONFIRMED` event | 2 | PASS |
| A03-W07 | Refund status reconciliation | Synchronous refunds: CLI refund events → `no_change` (already applied, never twice). Refund **failed after success** (`pm_card_refundFail`): resent `refund.failed` → `flagged_for_review`, `requiresReview` set, `REVIEW_REQUIRED` audit, money records unchanged, now shown to admins (A03-BUG-009). Before A03-BUG-006 none of these events could match a real request | 2 + 1 | PASS (after fixes) |
| A03-W08 | Webhook retry and recovery | Backend stopped: the CLI reported `connectex: … actively refused` for 5 events. After the restart `stripe events resend` re-delivered them: `refund.updated` → no_change, `refund.failed` → flagged_for_review, `payment_intent.succeeded` → already_processed (the status refresh had settled it). In-flight redelivery → 409 and crashed processing → reprocessed (A03-BUG-001, kind 1) | 1 + 2 | PASS (CLI resend; Stripe's own retry schedule not observable) |

**Other validations (kind 1, automated):**

| Validation | Covered by |
|---|---|
| Amount, currency, ownership, livemode mismatch → never confirmed, kept for review | P02 `test_payment_mismatch_never_confirms`, `test_payment_ownership_mismatch_is_not_applied`; P05 refund mismatch tests (intent, currency, amount) |
| Event persistence without payload | P05 `test_pending_refund_…` (`"data" not in logged`) |
| Audit history | `REFUND_RECONCILIATION` and `PAYMENT_RECONCILIATION_ACTION` audit entries (P05, A03 BUG-009 live) |

## 4. Defects found in the webhook path

| ID | Defect | Status |
|---|---|---|
| A03-BUG-001 | In-progress or crashed deliveries were acknowledged with 200 | Fixed |
| A03-BUG-002 | Every real `payment_intent.payment_failed` returned 500 | Fixed |
| A03-BUG-003 | Out-of-order failure notice | Fixed |
| A03-BUG-006 | Refund events never matched real refund requests | Fixed |
| A03-BUG-007 | Lost refund responses could not be matched | Fixed |
| A03-BUG-009 | Review states invisible | Fixed |

Details are in `A03_BUG_FIX_REPORT.md`.

**Observation A03-O2:** on the current API version, `charge.refunded` carries no refund list. A dashboard endpoint must subscribe to `refund.created`, `refund.updated` and `refund.failed` as well as the payment-intent events.
