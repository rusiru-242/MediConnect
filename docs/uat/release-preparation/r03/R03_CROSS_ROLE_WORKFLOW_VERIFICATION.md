# R03 — Cross-Role Workflow Verification

For: the project owner and reviewers. 2026-11-28. Local synthetic workflows on the UAT backend (`127.0.0.1:8001`, `mediconnect_uat`, deterministic AI), the Android emulator and the admin browser. **Provider usage delta in every R03 probe: Gemini 0, OpenAI 0. Stripe requests made by R03: 0.**

| Workflow | Outcome |
|---|---|
| A — AI-assisted booking | **PASS** to the explicit hold; payment confirmation covered by automated tests and A03's test-mode evidence |
| B — Consultation and prescription | **PASS** (live API + device viewing) |
| C — Prescription renewal | **PASS**, including the device-level renewed-prescription reminder that A04 left open |
| D — Customer support | **PASS** (live API) |
| E — Fraud monitoring | **PASS** (automated at scale + live worker), with one qualified UAT check (R03-O1) |
| F — Profile pictures | **PASS** (live API, device, browser, backend restart) |

## Workflow A — AI-assisted appointment booking

`r03_workflow_probe.py`, `evidence/r03_workflow_probe.json` (second run, after the probe's renewal counter was corrected).

| Step | Result | Evidence |
|---|---|---|
| A01 "Find me a cardiologist in Colombo" → only approved Colombo cardiologists, every card matching `doctor_profiles` | PASS | Dr. UAT Cardio One and Two, 0 field mismatches |
| A02 "Only doctors with a fee under 3000" → specialty and city kept, fee limit added | PASS | preferences `{specialty, city, maxFee 3000}`; only Cardio One (LKR 2,000) |
| A03 Select, list tomorrow's slots, pick a listed slot → proposal; **no hold yet** | PASS | proposal 2026-11-29 09:00, LKR 2,000; holds unchanged |
| A04 Accept with an unknown proposal id | PASS | 409; nothing created |
| A05 Another patient accepts this proposal | PASS | 403 |
| A06 Explicit Accept by the owner; a second Accept | PASS | 200/200; exactly one hold (`PENDING`), one active appointment in the slot, no payment record |
| A07 Amount is server-controlled | PASS | proposal 2000 = stored fee 2000 |
| A08 Another patient starts payment for the hold | PASS | 403 before any Stripe call (ownership check precedes `PaymentIntent.create`) |
| A09 Cancel the session | PASS | hold released (`CANCELLED`) |

**Payment confirmation path:** not exercised live in R03, because no R03-specific Stripe authorisation exists. Covered by the final automated suites (A03 booking/payment tests with Stripe test doubles, webhook signature and idempotency tests) and by A03's recorded Stripe test-mode run (43/43, webhooks through the Stripe CLI).

## Workflow B — Doctor consultation and prescription

| Step | Result | Evidence |
|---|---|---|
| Doctor issues a synthetic prescription only with complete, explicit fields | PASS | A04 probe re-run V01–V04 (empty strength 422, duplicate medicine 422, valid 201) |
| Concurrent issue stores one prescription | PASS | P08c: 201, 409, 409, 409 → 1 stored |
| Allergy record is checked | PASS | A03a |
| Patient views the approved prescription with exact instructions | PASS | device `r03_e21`, `r03_e22` |
| Patient sets a reminder: instructions, ownership and duration kept | PASS | device `r03_e23`–`r03_e25`; database: dose 1 tablet, twice daily, 5-day window, owner's prescription |
| Unrelated doctor, other patient and admin cannot read it | PASS | A04 probe `S`: 403 ×3 |

## Workflow C — Prescription renewal

| Step | Result | Evidence |
|---|---|---|
| Patient requests a renewal (only for a prescribed medicine; duplicates refused) | PASS | A04 probe R01b (422 for an unprescribed medicine), R04b (201 then 409) |
| Patient cannot approve; unrelated doctor cannot approve | PASS | A04 probe `S` |
| Dr. P03 Alpha approves on the device; dialog shows the original instructions | PASS | `r03_e18`–`r03_e20` |
| New prescription issued with identical items | PASS | `RX-REN-20261128-2DD56A`: Probexacillin-29330 500 mg, 1 tablet, twice daily, 5 days |
| Patient sees it and sets a reminder on it (A04 device limitation) | **PASS — now verified on the emulator** | `r03_e22`–`r03_e25`; `medication_reminders` row for `RX-REN-20261128-2DD56A` |
| Doctor rejection on the device | Not run on the device | Covered by API/automated tests (A04) |

## Workflow D — Patient customer support

A05 probe re-run (`evidence/r03_rerun_a05_probe.json`):

| Step | Result |
|---|---|
| Patient creates a ticket; duplicate refused (409); invalid input refused (422) | PASS (C02, C15a, C03) |
| Admin receives a template draft and sends an edited reply explicitly; duplicate send idempotent | PASS (C06–C15b) |
| Patient is notified, sees the reply and follows up | PASS (C10, C11–C13) |
| Other patient, doctor and patient-as-admin refused | PASS (C16–C17: 403) |
| Medical-emergency wording gets a safety notice; no refund request is created from a ticket | PASS (C18–C19, C18b) |

Device: `r03_e11` (Help & Support empty state for a patient without tickets). The full ticket conversation was verified on the device in A05.

## Workflow E — Fraud monitoring

| Check | Result | Evidence |
|---|---|---|
| Real sweep over 231 recently active accounts (230 ordinary, 1 hoarder whose id sorts last) | PASS | `test_real_fraud_sweep_over_230_normal_accounts_flags_only_the_newest_hoarder`: every candidate evaluated, 0 deferred; only the hoarder flagged; no payment, refund, user or booking change |
| Worker raises or refreshes the signal in UAT | PASS (qualified) | The hoarding account already had an open review, so the probe's "new review" check could not pass; the worker updated that review with the four new holds (R03-O1) |
| Normal account | Qualified | Correctly flagged because repeated probe runs left 5 unpaid holds in 24 hours (R03-O1) |
| No automatic punitive or financial action | PASS | F14–F15: account ACTIVE, payments, refunds, sessions and bookings unchanged |
| Patient and doctor cannot see fraud data | PASS | F13: 403 / 403 |

## Workflow F — Profile pictures

`r03_picture_probe.py`, `evidence/r03_picture_probe.json`:

| Check | Result |
|---|---|
| Synthetic patient and doctor pictures uploaded; doctor replaced | PASS |
| Privacy matrix: owner 200; other patient 404; unrelated doctor 404; treating doctor 200; admin → patient 404; everyone signed in → approved doctor 200 | PASS |
| Metadata removed (synthetic EXIF GPS block → 0 EXIF tags, 512×512 JPEG); `Cache-Control: private, max-age=86400` | PASS |
| Search results and appointments carry the doctor's trusted URL | PASS |
| Backend restart: both pictures byte-identical (SHA-256) | PASS |
| Device: patient profile, editor, search card, details, AI card, My Appointments, doctor dashboard | PASS (`r03_e04`–`r03_e09`, `r03_e16`) |
| Admin browser: doctor avatar; patient picture never requested | PASS (`r03_b02`) |
| Account switching: patient → doctor → doctor → patient on one device, each showing only their own data and picture | PASS |
