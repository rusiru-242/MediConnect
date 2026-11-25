# Phase 02 — Bug ID Reconciliation

2026-11-25 · branch `fix/phase-02-booking-payment-patient-care`

## How IDs are counted

The owner's working list ends at **BUG-063**. The repository's tracker described BUG-001 to BUG-048. Phase 01 used provisional IDs **P01-01 to P01-26** because BUG-049 to BUG-063 had no descriptions in the repository at that time. This file records the owner's original descriptions of BUG-049 to BUG-063 (as supplied in the Phase 02 request) and maps them onto the Phase 01 IDs.

**Counting rules:**
- An owner ID and a Phase 01 alias that describe the same issue count as **one** defect.
- Issues first found in Phase 02 get collision-free IDs **P02-N01 to P02-N17**.
- The owner's open UAT items P-05n to P-05r are **test items**, not bugs. They are reported in [PHASE_02_BOOKING_PAYMENT_VERIFICATION.md](PHASE_02_BOOKING_PAYMENT_VERIFICATION.md).

## Owner IDs BUG-049 to BUG-063

| Owner ID | Owner's description (abridged, original wording preserved in the request) | Phase 01 alias | Phase 01 result | Phase 02 action | Phase 02 status |
|---|---|---|---|---|---|
| BUG-049 | Keyboard does not dismiss on tap outside; should dismiss on send and not reopen on reply | P01-21 | Implemented | Phase 01 Flutter suites re-run | FIXED (Phase 01), regression PASS |
| BUG-050 | Generic cardiac-style emergency UI for self-harm; dedicated supportive crisis flow required | P01-04 (+ P01-05 hotline) | Initial dedicated experience | Phase 01 probe: 0 differences | FIXED (initial). Clinical follow-up design pending (B10) |
| BUG-051 | Ambulance-level escalation for prolonged cough alone | P01-07 | Tiered guidance | Probe: 0 differences | FIXED. Clinical review pending |
| BUG-052 | Educational heart-attack questions trigger emergency mode | P01-01 (+ P01-02 hypothetical) | Fixed tested scenarios | Probe: 0 differences | FIXED |
| BUG-053 | Ranking: top 1–2, verified ratings, review count, experience, background, transparent reasons | P01-16, P01-17 | Ranking changes | Live check of every requested field | FIXED, VERIFIED (`evidence/bug053-recommendation-fields.json`) |
| BUG-054 | Context lost after unsupported-location or no-results replies | P01-09 | Fixed tested scenarios | Probe: 0 differences | FIXED |
| BUG-055 | Summary says "Closest available time…" when the patient picked the exact slot | — (new to the tracker) | — | Reproduced on UAT API; fixed | **FIXED** |
| BUG-056 | Unwanted video channelling; product is in-person only | P01-26 (patient UI) | Patient UI removed | Backend, doctor and data checked | **FIXED** (backend, doctor UI, care plans); migration prepared |
| BUG-057 | Fabricated "Dr. Alexander Wright" dashboard appointment | P01-23 (+ P01-24 vitals) | Fixed | Device: dashboard shows real data | FIXED (Phase 01) |
| BUG-058 | Patient details lack payment status, paid amount and the full reference | — | — | Fixed (API and app) | **FIXED** |
| BUG-059 | Doctor details show "LKR" without the fee | — | — | Fixed | **FIXED** |
| BUG-060 | Doctor's notification "View Appointment" opens "Appointment not found" | — | — | Two root causes fixed | **FIXED** |
| BUG-061 | No nearby times for the same doctor when the requested slot is unavailable | — | — | Reproduced; fixed | **FIXED** |
| BUG-062 | Named-doctor availability asks for the name again | P01-13 | Fixed tested scenarios | Re-tested (repro flow 2 and probe) | FIXED (Phase 01), regression PASS |
| BUG-063 | No manual way to release the hold after cancelling payment | — | — | Implemented end to end | **FIXED** |

**De-duplicated totals:**
- BUG-049 to BUG-063 are **15 owner defects**.
- Nine had Phase 01 aliases: 049, 050, 051, 052, 053, 054, 057 and 062 were fixed in Phase 01; 056 was partly fixed there and completed here.
- Six were first fixed in Phase 02: 055, 058, 059, 060, 061 and 063.

## Phase 01 provisional IDs not covered by BUG-049 to BUG-063

These keep their P01 IDs and are not owner IDs:

- **Emergency and crisis:** P01-03 (overdose), P01-05 (hotline, grouped under BUG-050 above), P01-06 (Romanized crisis phrases).
- **Booking assistant:** P01-08 (prevention), P01-10 to P01-12, P01-14, P01-15 and P01-18.
- **Medicine information:** P01-19 and P01-20.
- **App:** P01-22, P01-24 (grouped under BUG-057), P01-25, and BUG-044 and BUG-046 (from the BUG-001 to BUG-048 range).

Phase 02 re-ran their regression suites; none regressed.

## New in Phase 02 (P02-Nxx)

| ID | Defect | Severity |
|---|---|---|
| P02-N01 | Time typed after picking a doctor matched a slot on a **different date** (wrong-date proposal) | High |
| P02-N02 | Legacy payment settlement confirmed without checking amount, currency, owner or hold validity; could revive a cancelled or expired booking | High |
| P02-N03 | Legacy charge used the doctor's **current** profile fee instead of the reserved fee | Medium |
| P02-N04 | A doctor could confirm an **unpaid** appointment | High |
| P02-N05 | Refunds: fake success without Stripe; Stripe status assumed; no amount cap; duplicate requests; refund without cancellation; refunded amount could be counted twice | High |
| P02-N06 | A new chat used for a booking action stayed a "draft" and was reopened by New Chat | Low |
| P02-N07 | Manual booking: a retry after a cancelled payment tried to reserve the same slot again (409 against the patient's own hold) | Medium |
| P02-N08 | Reschedule accepted any clock time; availability link not updated; a taken slot caused a 500 | High |
| P02-N09 | Care Agenda measurements stored concerning readings without the safety alert Health Tracking shows | Medium |
| P02-N10 | **Privacy:** a released hold or cancelled booking granted a doctor access to the patient's records and vitals | High |
| P02-N11 | Doctor dashboard: fabricated KPIs (including "video" counts), a fake "CRITICAL TELEMETRY ALERT" for "Patient #9401", and a fake hospital | High |
| P02-N12 | Renewals: doctor not notified; any related doctor could review; review not atomic | Medium |
| P02-N13 | `live_api_test.dart` defaulted to port 8000 and its mocked health probe **silently skipped every test** | Medium |
| P02-N14 | Mobile models invented LKR 2500 when a fee was missing (appointment, consultation, timeline) | Medium |
| P02-N15 | Patient cancellation was not conditional (concurrent cancellations) | Low |
| P02-N16 | Endpoint `GET /appointments/{id}` could also crash on records without timestamps (`datetime` NameError, latent) | Low |
| P02-N17 | A released hold kept `paymentStatus: PENDING` (shown as "Payment pending" on a cancelled booking) | Low |

**Totals:** 17 new defects. Combined with the 15 owner IDs, Phase 02 reviewed **32 distinct defects** with no double counting. Details are in [PHASE_02_BUG_FIX_REPORT.md](PHASE_02_BUG_FIX_REPORT.md).
