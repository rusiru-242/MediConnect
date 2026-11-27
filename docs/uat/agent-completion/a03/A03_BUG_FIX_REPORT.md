# A03 — Bug Fix Report

For: engineers and reviewers. Agent Completion Phase A03 (Agent 01, AI Appointment Booking), 2026-11-27, branch `fix/agents-a03-booking-payments`.

IDs use the `A03-BUG-nnn` scheme, so they cannot collide with scenario IDs (`A03-A01`, `A03-P01`, …).

- Every defect was reproduced before it was fixed: by a failing test, live Stripe test mode, the live booking probe or the Android emulator.
- Each fix has an automated test. The agent tests were also run against the pre-fix code: 9 of 13 failed there, and the 4 that passed check behaviour that already worked.

## Summary

| Severity | Count | IDs |
|---|---|---|
| High | 7 | 001, 002, 005, 006, 007, 009, 010 |
| Medium | 6 | 003, 004, 011, 012, 015, 020 |
| Low | 7 | 008, 013, 014, 016, 017, 018, 019 |
| **Total** | **20** | all fixed |

**How they were found:**
- **Real Stripe objects or real Stripe test mode:** 002, 005, 006, 009.
  - 002 was masked by a test that mocked `construct_event` with a plain dict.
  - 006 was masked by test fixtures that inserted uppercase statuses.
- **Live AI booking probe:** 010, 011, 012, 013, 014.
- **Android emulator:** 015, 016, 018, 020.
- **Code reading, then a failing test:** 001, 003, 004, 007, 008, 017, 019.

## Defects

| ID | Sev. | Component | Defect (how it was found) | Root cause | Fix | Test / evidence |
|---|---|---|---|---|---|---|
| A03-BUG-001 | High | Stripe webhooks | A redelivery that arrived while the first delivery was still processing, or after its processing raised, got **200 "already_processed"**. Stripe then stops retrying, so the event was never applied (code reading, then a failing test) | `begin_event` treated any existing event id as a duplicate unless it was more than 5 minutes old; a crash left it "processing" | In-progress → **409** (Stripe retries); a processing exception marks the event `failed`, and the next delivery processes it; only `processed` events are duplicates | `test_a03_bug001_inflight_…`, `test_a03_bug001_event_whose_processing_crashed_…` |
| A03-BUG-002 | High | Stripe webhooks | **Every real `payment_intent.payment_failed` webhook returned 500** (a locally signed event verified by the real stripe library) | `data_object.get(...)` on a stripe-python 16 `StripeObject`, which is no longer a dict. Phase 02's test mocked `construct_event` with a plain dict | Attribute-safe access (`_intent_value`) | `test_a03_bug002_real_failed_event_is_recorded_once`; live: a CLI-delivered decline → `failed_recorded` |
| A03-BUG-003 | Medium | Stripe webhooks | A failure event delivered **after** the success sent the patient "Payment Failed. Please try again" for a paid booking | The notification was sent even when the conditional update changed nothing | Only an open payment (PENDING/FAILED) can fail; otherwise `ignored_out_of_order`, no notice | `test_a03_bug003_…`; live W04 |
| A03-BUG-004 | Medium | Payment status | After a recorded decline, a later success with another card (same intent) was confirmed only by its webhook; the status refresh never re-read Stripe. Its decline write was also unconditional, so it could overwrite a payment settled meanwhile | Fallback sync ran only for PENDING; `update_one` had no status filter | The sync also covers FAILED (payment and AI-session paths); the decline write is conditional on PENDING | `test_a03_bug004_…` (2 tests); live P04, emulator decline → success |
| A03-BUG-005 | High | Reservation holds | An **expired hold was released without cancelling its PaymentIntent**, so an open PaymentSheet could still charge for a booking that no longer existed. UAT had three such payable test-mode intents, one from an expired hold (`evidence/before_open_intents_on_cancelled_holds.json`) | `release_expired_holds` frees the slot without calling Stripe (correctly), and nothing cancelled the intent afterwards | New worker step `stop_intents_of_released_holds`: cancels open intents of released holds through the BUG-063 path. Expiry never waits for Stripe; an outage is retried next cycle; a late success is settled once into refund review | `test_a03_bug005_…` (3 tests); live P08 (pay after expiry → `payment_intent_unexpected_state`); the 3 old intents → `canceled`; emulator UI hold expired → intent cancelled |
| A03-BUG-006 | High | Refund reconciliation | Webhook and polling reconciliation **never matched a real refund request**. A real `refund.updated` (succeeded) would also overwrite `succeeded` with uppercase `SUCCEEDED`, hiding it from the admin filter and from the "already refunded" check | Refund requests store lowercase `RefundStatus` values; `stripe_webhook_service` compared and wrote uppercase names. Phase 05 fixtures inserted `"PROCESSING"` directly | Lowercase vocabulary (legacy uppercase normalised) | `test_a03_bug006_…` (2 tests, through the real approval service); live C10b |
| A03-BUG-007 | High | Refund execution | A network or 5xx error from `Refund.create` marked the request `failed` with no Stripe id, although Stripe may have created the refund. A webhook could not match it, and a re-approval after Stripe's 24-hour idempotency window could **refund twice** | Every `StripeError` was "failed"; refunds carried no MediConnect reference | Connection/5xx → stays `processing`, `stripeOutcome: uncertain`, 502 "do not approve again". Every refund carries `metadata.refundId`. Webhook, polling and a stale retry look the refund up by metadata before any create. "Not created" → `failed` for re-approval | `test_a03_bug007_…` (7 tests) |
| A03-BUG-008 | Low | Refund polling | The polling fallback always read the same first 20 processing refunds; refunds pending for days would starve newer ones | Unordered `find().limit(20)` | Least-recently-checked first; every check stamped | Covered by the BUG-007 polling tests (failed before) |
| A03-BUG-009 | High | Admin / reconciliation | A refund Stripe **failed after reporting success** (seen live with `pm_card_refundFail`) and a refund with an unknown outcome were visible to **no administrator**: not in the refund API, reconciliation or admin UI. The patient had been told "Refund issued" | `requiresReview` / `stripeOutcome` were stored but never returned or checked | Refund API returns `requiresReview`, `reviewReason`, `stripeOutcome`. Reconciliation adds `REFUND_FAILED_AFTER_SUCCESS`, `REFUND_OUTCOME_UNCERTAIN`, `REFUND_EVENT_NEEDS_REVIEW`. The Refunds page shows "Needs review" / "Outcome being checked" | `test_a03_bug009_…` (2), `a03RefundReview.test.tsx` (2); browser `a03_b04`, `a03_b05` |
| A03-BUG-010 | High | AI booking memory | After "Select the most experienced doctor", "Show me the available slots for **this doctor** tomorrow" asked "Which doctor do you mean?". "Book an appointment with this doctor next Monday morning" **proposed the other (cheaper) doctor** (live probe) | The auto-selection stored only `autoSelectedDoctorId`, which nothing read; the automatic proposal searched all matching doctors and ranked by fee | The selected doctor stays the doctor of later turns until the patient names another doctor, picks by position, asks for a new selection or changes a hard constraint. A slot request for one resolved doctor shows that doctor's real slots for the requested date | `test_a03_bug010_…` (2); probe before/after; emulator `a03_02`, `a03_03` |
| A03-BUG-011 | Medium | AI booking | "Show me another available time on the same date" asked for symptoms | No handler | Lists the same doctor's other open times on that date and keeps the current proposal (read-only) | `test_a03_bug010_selected_doctor_…` (alternative_times); probe |
| A03-BUG-012 | Medium | AI booking (read-only management) | "I want to cancel my appointment" answered **"Your booking selection has been reset"**; "I want to reschedule my appointment" asked for symptoms | Any "cancel" was treated as resetting the chat selection | Lists the patient's upcoming appointments and points to Cancel/Reschedule in My Appointments (refund preview first). The chat never cancels or moves a booking. Also applies after the chat's own booking is confirmed. The app shows an "Open My Appointments" card | `test_a03_bug012_…` (5), `a03_booking_chat_test.dart`; emulator |
| A03-BUG-013 | Low | NLP | Romanized Sinhala time words "udee/udeta" (morning), "dawal" (afternoon), "hawasa" (evening) were not understood ("heta udee slots pennanna" ignored the date and time) | Time-range patterns had Sinhala script only | Patterns added | `test_a03_bug013_…` (5) |
| A03-BUG-014 | Low | AI booking | "Yes, confirm it and charge my card" (no hold was ever created) got "share your symptoms…" | No reply for confirmation-by-chat | Explains that acceptance is the Accept button and payment happens only on the Stripe screen | `test_a03_a12_chat_text_never_confirms_or_charges` |
| A03-BUG-015 | Medium | Booking summary | The AI booking summary never stated the **visit type** (emulator) | Not in the summary schema or card | `visitType: IN_PERSON`; card row "Visit type: In-person at the clinic" | `test_a03_bug015_016_…`, Flutter `A03-BUG-015`; emulator `a03_04_booking_summary_in_person` |
| A03-BUG-016 | Low | AI booking | The assistant said "tap 'Confirm Booking'" while the card's button is "Accept & Continue" (emulator) | Stale text | Names the real button; says nothing is reserved or charged before that | `test_a03_bug015_016_…` |
| A03-BUG-017 | Low | Money display | The session response, the hold message and the Flutter summary model fell back to an **invented LKR 2,500** when the server fee was missing. Latent: the backend always sends it, but this breaks the BUG-028 rule | Defaults `2500.0` | Such a summary is not presented; the Pay label shows no amount | `test_a03_bug017_…`, Flutter `A03-BUG-017` |
| A03-BUG-018 | Low | App booking result | An e-mail provider that is not configured (`disabled`, the A02 vocabulary) was shown to the patient as **"Email: pending"** (emulator) | Label mapping predates `disabled` | "not sent (service not available)" | Flutter `A03-BUG-018` |
| A03-BUG-019 | Low | Admin reconciliation | The fixed rule-based recommendations were headed **"AI Recommendation"** | Mislabel | "Recommended action (rule-based)"; refund discrepancies show the refund id | Browser `A03-U03a` (`aiLabel: false`) |
| A03-BUG-020 | Medium | AI booking notices | A paid AI booking gave the patient **no in-app confirmation**, while a decline did. After a decline and a successful retry, the latest notice said "Payment Failed. Please try again" for a paid appointment (emulator; e-mail and SMS are unavailable in UAT) | Only the doctor channel was notified in-app on AI confirmation | Patient "Payment Successful" in-app notice exactly once (same idempotency key as the standard path) | `test_a03_bug020_…` |

## Changed test expectations

Each changed expectation encoded a defect fixed here; nothing was changed only to make a suite pass.

| Test | Old expectation | New expectation | Reason |
|---|---|---|---|
| `test_phase04_admin_system.py::test_n10_refund_failure_then_retry_after_external_success` | A lost refund response is `failed`; an immediate re-approval relies on Stripe's idempotency key | `processing` + `uncertain`; an immediate retry → 409 with no Stripe call; a stale retry **adopts** the refund Stripe already has. "No second refund" is still asserted | A03-BUG-007: the idempotency key expires after 24 h, so `failed` invited a double refund |
| `test_phase05_stripe_webhooks.py` (fixtures and 6 assertions) | Refund requests in `PROCESSING` / `SUCCEEDED` / `FAILED` | `processing` / `succeeded` / `failed`; the sync calls pass `limit=500` because the shared test DB holds other processing refunds | A03-BUG-006: the uppercase values never exist in real data; A03-BUG-008 rotation |
| `admin-web/src/test/phase04Admin.test.tsx` (retry text) | "retrying uses the same idempotency key" | "a retry first checks Stripe for an existing refund" | A03-BUG-007 |

## Test isolation fixes (not product defects)

- **Index order dependency:** `tests/conftest.py` now creates the application's indexes before the first test. Previously, a subset run could test double-booking protection without the unique slot index; seen as two winners, this was A02-O4.
- **Payment provider guard:** the provider guard now also blocks `api.stripe.com` and guards name resolution, because urllib3 bypasses `socket.create_connection`.
- **Detector result:** the provider-connection detector recorded **0** attempts to Stripe, Gemini, OpenAI, SMTP, Twilio or FCM in both the baseline and the final run.

## Observations (not confirmed as defects)

| ID | Observation |
|---|---|
| A03-O1 | My Appointments "Upcoming" lists 2026-12-04 before 2026-12-01 (not chronological). The data is correct; ordering is a UX question |
| A03-O2 | On current Stripe API versions `charge.refunded` events carry no refund list, so they reconcile nothing (`no_refunds`). Reconciliation relies on `refund.created/updated/failed`. A dashboard endpoint must subscribe to those events (owner set-up) |
| A03-O3 | On the emulator, Android raised a system ANR ("system using pending focus request") while the Stripe PaymentSheet opened. The sheet received no input, and after it closed `presentPaymentSheet()` never returned, so the hold card stayed in "processing" until the app was restarted. A cold-booted emulator worked normally. The cause is platform-side, but the app has no time-out or resume recovery for a sheet that never returns; check on a physical phone (B10) |
| A03-O4 | The payment-failure notice uses one idempotency key per payment, so a second decline on the same intent is not notified again (the first notice still stands) |
| A03-O5 | "Show me my upcoming appointments" (care agenda) lists times and "Confirmed appointment" without doctor names |
| A03-O6 | A payment that succeeds after `holdExpiresAt` but before the worker releases the hold goes to refund review, not confirmation (existing rule; owner decision B6 covers hold and refund policy) |
| A03-O7 | "most experienced kenawa select karanna" (Romanized) is not recognised as a selection request; with one candidate the result is the same |
