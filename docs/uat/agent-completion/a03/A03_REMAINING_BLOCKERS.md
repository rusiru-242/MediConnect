# A03 — Remaining Blockers, Owner Actions and Decisions

For: the project owner. 2026-11-27, after Agent Completion A03 (Agent 01, AI Appointment Booking). Every unresolved earlier blocker is carried forward; nothing here is marked resolved without evidence.

## Owner actions (in priority order)

| # | Action | Unblocks | Notes |
|---|---|---|---|
| 1 | **Rotate the MongoDB credentials (P5-C1)** and run the remote incident inspection (P4-B1) | Staging and anything beyond | Still the top security blocker. A03 did not connect to the remote cluster or touch credentials |
| 2 | Rotate the SMTP, Gemini, OpenAI **and Stripe test** credentials (P4-B2) | Staging | The Stripe test key in `backend/.env` was used by the A03 live runs and the CLI (test mode only). The Stripe CLI's own login expired on 2026-11-16 |
| 2a | Check the SMTP account's Sent and bounce folders (A02 action 2a) | Knowing whether earlier test runs e-mailed a third party | Unchanged from A02 |
| 3 | **Stripe webhook endpoint for staging** (when a staging URL exists): Dashboard → Developers → Webhooks → add `https://<staging-host>/api/payments/webhook`. Subscribe to `payment_intent.succeeded`, `payment_intent.payment_failed`, `payment_intent.canceled`, `refund.created`, `refund.updated` and `refund.failed` (`charge.refunded` alone is not enough, A03-O2). Put its `whsec_…` secret in the staging environment, never in the repository | Stripe's own HTTPS delivery and retry schedule (only CLI forwarding was verified) | Test mode only. Do not expose the local machine through a tunnel |
| 4 | Confirm or change the refund and cancellation policy (B6) | Agent 01 policy sign-off | As coded and used unchanged in A03: 100% when cancelled 24 h or more ahead or by the doctor, 80% within 24 h, nothing after the start. Also open: rescheduling fee differences; payment after hold expiry goes to refund review (A03-O6) |
| 5 | Physical Android phone test of the booking payment (B10) | Device sign-off for Agent 01 | Card entry, decline, retry and confirmation were completed on the emulator. One emulator run hit an Android system ANR in the PaymentSheet (A03-O3); repeat on a real phone, including Doze/background return |
| 6 | Native-speaker review of new Sinhala texts (B12) | Language sign-off | A03 cancel/reschedule help, other-times reply, confirmation-by-chat reply and summary prompt |
| 7 | Firebase (A02 action 3), iOS/APNs (A02 action 4), e-mail sandbox (A02 action 5), SMS provider (A02 action 6) | Push, external e-mail and SMS for booking confirmations | Unchanged. Booking confirmations are in-app only; e-mail shows "not sent (service not available)" |
| 8 | OpenAI credits (owner) | A secondary AI provider | Not needed for Agent 01 (Gemini primary). Gemini free tier only; a paid tier is needed for any pilot (A01) |
| 9 | Exact alarms (A02 action 7), doctor messaging scope (A02 action 8) | A02 items | Unchanged |

## Human review gates (unchanged)

| Gate | Item |
|---|---|
| Clinical review | B1 (triage, reminder timing and care wording) |
| Pharmacist review | B2 |
| Physical device | B10 (now also covers the Agent 01 PaymentSheet) |
| Native Sinhala/Tamil review | B12 |

## Open observations

- **A03-O1 to A03-O7** are in `A03_BUG_FIX_REPORT.md`:
  - non-chronological Upcoming list;
  - `charge.refunded` without a refund list;
  - PaymentSheet stuck after an emulator system ANR;
  - one failure notice per payment;
  - agenda without doctor names;
  - payment after hold expiry goes to review;
  - one Romanized selection phrase.
- **Resolved by A03:** A02-O4 (index-dependent tests in isolation). `tests/conftest.py` now creates the indexes before the first test.
- A01-O1 to O4 and A02-O1 to O3, O5 remain open.

## Not done in A03 (and why)

| Item | Why |
|---|---|
| Delivery to a public or production webhook endpoint (W05 kind 3) | Forbidden in this phase; no public endpoint. Actual Stripe-generated test events were delivered with the Stripe CLI (owner approved) |
| Stripe's automatic retry schedule | Only a dashboard endpoint is retried by Stripe; recovery was verified with `stripe events resend` and the patient status refresh |
| OpenAI live booking | No credits |
| Doctor appointment-detail **UI** on the emulator in A03 | Checked through the doctor API (`a03_cross_role_refund.json`); the doctor UI was verified in Phases 02–03 (BUG-059/060 widget tests pass) |
| Live delivery of a 24 h / 2 h reminder for an A03 booking | The A03 bookings are 4–7 days ahead; reminder delivery is covered by automated tests and A02's live run |
| Production deployment, merge to `main`, live payments, MongoDB credential changes | Forbidden |

**Environment note:** the owner's port-8000 process (pid 12876 in A02) was no longer listening when this session resumed on 2026-11-27. A03 did not start or stop anything on port 8000.
