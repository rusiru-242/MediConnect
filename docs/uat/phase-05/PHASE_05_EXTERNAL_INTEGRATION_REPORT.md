# Phase 05 — External Integration Report

For: the project owner and whoever configures staging or production. 2026-11-26.

"Actually tested" below means a request reached the real external service in Phase 05. A passing local test with a test double is reported as "mocked", never as external verification.

## Summary

| Provider | Configured on this machine | State in UAT | Mocked tests | Actually tested in Phase 05 | Status | Owner action |
|---|---|---|---|---|---|---|
| Stripe API (test mode) | Yes, `sk_test_` key in `backend/.env` | Enabled (launcher refuses non-test keys) | Yes | **Yes**: Phase 02 Stripe script and Phase 04 admin refunds re-run against Stripe test mode (PaymentIntents, confirmations, refunds); `livemode=false` checked | Verified (test mode only) | None for UAT. Live keys only with `ENVIRONMENT=production` |
| Stripe webhooks → backend | Owner's dashboard endpoint secret present (not used) | Not delivered to localhost | Yes, with real HMAC signatures over the raw body (13 tests) | No | **BLOCKED (B3)** | Install the Stripe CLI (`stripe listen --forward-to 127.0.0.1:8001/api/payments/webhook`) or authorize a test endpoint; use the CLI's own `whsec_` for UAT |
| Firebase Cloud Messaging | No credentials | Disabled (launcher blanks variables) | Yes (push mocked in scheduler tests) | No | **BLOCKED (B4)** | Firebase project, service account JSON in a secret store, test device token |
| SMTP e-mail | Credentials in `.env` (pending rotation, P4-B2) | Disabled in UAT (`SMTP_HOST` blanked) | Yes | No (deliberately: no real recipients) | **BLOCKED (B5)** | Rotate SMTP credentials; provide a sandbox (e.g. a test inbox service) and a synthetic recipient |
| SMS (Twilio) | Not configured | Disabled | Yes | No | **BLOCKED (B5)** | Twilio test credentials, messaging service, verified test number |
| Gemini | Key in `.env` (pending rotation) | Disabled in UAT | Yes (provider gateway tests: auth failure, rate limit, timeout, invalid model, invalid JSON, usage limit, circuit breaker) | No | **BLOCKED (B13)** | Rotate key; authorize synthetic-data testing and cost; then run `start_uat_backend.ps1 -AiProvider gemini` |
| OpenAI | Key in `.env` (pending rotation) | Disabled in UAT | Yes | No | **BLOCKED (B13)** | Same as Gemini |
| Medicine image (vision) | Uses Gemini/OpenAI | `AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED=false` | Yes (existing image tests) | No | **BLOCKED (B13)** | Data-processing agreement for images; synthetic packaging photos only |
| Drug-interaction source | None | Not implemented | — | — | **NOT IMPLEMENTED (P3-B9)** | Choose a licensed, authoritative source; clinical/pharmacist review |
| MongoDB Atlas (remote) | URI in `.env` | Never used by tests or UAT | — | No (not authorized) | Incident open (P4-B1) + exposed credentials (P5-C1) | Rotate, inspect read-only |

## Stripe

Live test-mode evidence this phase:
- Phase 02 Stripe script re-run (`evidence/regression/p02-stripe.*`) and Phase 04 admin UAT refund steps (real test-mode refunds, 4 concurrent approvals → one Stripe refund) re-run (`evidence/regression/p04-admin-system-uat.*`).
- Webhook processing (new): event log and de-duplication, `payment_intent.canceled`, refund created/updated/failed and `charge.refunded`, ownership/currency/amount/PaymentIntent checks, no downgrade of final states, failure-after-success review, pending-refund polling fallback, reconcile-refund audit. Verified locally only.
- Idempotency: refund creation keeps its per-request idempotency key; reconcile refunds use `mediconnect_reconcile_<paymentId>`; webhook redelivery returns `already_processed`.

## Notifications

The scheduler and outbox still produce in-app notifications locally. A local scheduler run is **not** evidence of e-mail, SMS or push delivery. Monitoring reports these channels as `not_configured` with failures counted (re-verified live: S-08a; admin assistant A-4/A-7 report "email: 3 failed (not_configured)").

## AI providers

All provider calls now pass through the provider gateway (limits, circuit breaker, metrics, header-only credentials). With the keys blanked, the UAT provider status is `not_configured` (verified live). Model availability could not be checked without using the owner's credentials.

## Setup instructions for blocked items

1. **Stripe webhooks (UAT):** install the Stripe CLI, `stripe login` with the test account, run `stripe listen --forward-to http://127.0.0.1:8001/api/payments/webhook`, put the printed `whsec_…` into a UAT-only environment variable (not `backend/.env`), restart the UAT backend, then `stripe trigger payment_intent.succeeded` and `stripe trigger charge.refunded`. Expected: `stripe_webhook_events` rows with `status: processed`.
2. **FCM:** create a Firebase project, download a service account, set `FIREBASE_SERVICE_ACCOUNT_JSON` for UAT only, register the emulator's token by logging in, trigger a reminder; verify the device notification and the event's `channels.push.status`.
3. **E-mail:** after rotating SMTP credentials, configure a sandbox SMTP (catch-all inbox), start UAT with `-EnableEmail`, use only synthetic `@uat.mediconnect.lk` recipients that route to the sandbox.
4. **SMS:** Twilio test credentials and a verified test number; enable `careSms` for one synthetic patient only.
5. **Gemini/OpenAI:** rotate keys, set `AI_DAILY_REQUEST_LIMIT` to a small number (e.g. 50), start UAT with `-AiProvider gemini`, run `docs/uat/phase-05/intent_probe.py`; provider metrics will show real counts, latency and token usage.
