# MediConnect — Master Bug Tracker (reconciled, Phases 00–05 and Agent Completion A01–A02)

For: the project owner, reviewers and future maintainers. Generated 2026-11-26 by `docs/uat/phase-05/build_master_tracker.py` from the recorded sources only (nothing re-typed by hand).

## How to read it

- One row per **unique** issue. Owner IDs BUG-049 to BUG-063 that describe a Phase 01 item are listed once, under the Phase 01 ID, with the owner ID in **Aliases** (BUG-049, BUG-050, BUG-051, BUG-052, BUG-053, BUG-054, BUG-056, BUG-057, BUG-062).
- **Kind** separates defects from improvements/requirements, regression guards, observations and security incidents.
- Full reproduction, expected/actual behaviour, root cause, changed files, fix, regression test and evidence for each row are in the **Source** report (historical rows keep their original evidence there). This index does not change any historical record.
- "FIXED" means fixed with an automated regression test; device, clinical or external verification is stated where it is still pending. No defect is marked clinically approved.

## Counts

| Measure | Count |
|---|---|
| Unique tracked items | 231 |
| Confirmed defects | 198 |
| Defects fixed (automated regression) | 197 |
| Defects open | 1 (BUG-039) |
| …of the fixed: manual device retest still pending | 7 |
| …of the fixed: external verification blocked | 1 |
| Improvements / requirements delivered | 21 |
| Regression guards (not defects) | 1 |
| Observations (unconfirmed) | 10 |
| Security incidents (owner) | 1 |

| Source | Defects | Improvements |
|---|---|---|
| historical BUG-001..063 (unaliased) | 53 | 0 |
| Phase 01 | 21 | 5 |
| Phase 02 | 17 | 0 |
| Phase 03 | 21 | 3 |
| Phase 04 | 23 | 0 |
| Phase 05 | 25 | 13 |
| Agent Completion A01 | 17 | 0 |
| Agent Completion A02 | 21 | 0 |

Owner decisions and external blockers (B1–B17, P3-B*, P4-B*, P5-*) are not defects; see `PHASE_05_REMAINING_BLOCKERS.md`.

## Index

| ID | Aliases | Kind | Severity | Component | Title | Status | Source |
|---|---|---|---|---|---|---|---|
| BUG-001 |  | defect | — | — | A follow-up message replaced the previous search instead of refining it | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-002 |  | defect | — | — | Romanized Sinhala budget ignored (LKR 3500 doctor returned for "3000ta aduwen") | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-003 |  | defect | — | — | Romanized Sinhala doctor search and preference understanding | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-004 |  | defect | — | — | Unnatural or unclear Sinhala responses | FIXED; manual device retest pending | docs/MASTER_BUG_TRACKER.md |
| BUG-005 |  | defect | — | — | Calendar connection error when changing months | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-006 |  | defect | — | — | New availability windows not shown in the calendar | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-007 |  | defect | — | — | Duplicate doctor recommendation cards and wrong unique-doctor counts | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-008 |  | defect | — | — | Consultation fees shown as "Fee unavailable" | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-009 |  | regression guard | — | — | English budget filtering works (preserve) *(provisional ID; regression guard)* | NOT A DEFECT | docs/MASTER_BUG_TRACKER.md |
| BUG-010 |  | defect | — | — | Automatic doctor selection not working | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-011 |  | defect | — | — | "Antarctica" search suggested Colombo as a nearby city | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-012 |  | defect | — | — | Health questions routed to doctor search | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-013 |  | defect | — | — | Multilingual emergency detection failure (CRITICAL release blocker) | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-014 |  | defect | — | — | Duplicate chat input fields | FIXED; manual device retest pending | docs/MASTER_BUG_TRACKER.md |
| BUG-015 |  | defect | — | — | `_owner != null` assertion when pressing Back in the AI Assistant | FIXED; manual device retest pending | docs/MASTER_BUG_TRACKER.md |
| BUG-016 |  | defect | — | — | Ambiguous medicine strength display (`500mg / 120mg/5ml`) | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-017 |  | defect | — | — | Universal paracetamol dose statement ("8 tablets / 4000 mg") without context | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-018 |  | defect | — | — | Antibiotic prescription request answered with "medicine not found" | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-019 |  | defect | — | — | Multi-topic wellness question answered only for diet | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-020 |  | defect | — | — | "Without sleeping pills" routed to medicine search | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-021 |  | defect | — | — | No explanation of why a specialty suits the symptoms | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-022 |  | defect | — | — | Preference ranking (experience) not applied or explained; opaque match score | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-023 |  | defect | — | — | Medicine photo always analysed as "Generic Medicine Label" | FIXED in code; live vision BLOCKED (B13) | docs/MASTER_BUG_TRACKER.md |
| BUG-024 |  | defect | — | — | Raw Markdown shown (`**Medicine Packaging Analysis**`) | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-025 |  | defect | — | — | "Incorrect email or password" shown during image upload | FIXED; manual device retest pending | docs/MASTER_BUG_TRACKER.md |
| BUG-026 |  | defect | — | — | No upload progress or feedback | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-027 |  | defect | High | — | Availability screen showed a **fabricated weekly schedule** when loading failed, and saving would persist it | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-028 |  | defect | Critical | — | Patients **charged a default LKR 2,500** when the doctor had no listed fee; string fees crashed booking | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-029 |  | defect | High | — | Invented values shown to patients: **4.8 rating**, LKR 2,500 fee, city "Colombo" | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-030 |  | defect | Medium | — | AI search applied an unsorted 200-row cap **before** name filtering and ranking, so named or best doctors could be dropped | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-031 |  | defect | Medium | — | Sinhala substring rules mis-assigned specialties ("සම" in "සමඟ" meant Dermatology; "හම" in "හමුවන්න"; "කන" in "කන්න") | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-032 |  | defect | Low | — | Image upload rejected in a persistent chat that had once completed a booking | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-033 |  | defect | Low | — | Image-analysis confidence badge always "Uncertain" | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-034 |  | defect | High | — | Backend CI could run the test suite against a **real Atlas database** when a `MONGODB_URI` secret exists | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-035 |  | defect | Medium (privacy) | — | Uploaded medicine photos written permanently to `uploads/companion_images` although never served | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-036 |  | defect | Low | — | Home-screen hero prompt chips lost their prompt | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-037 |  | defect | Low | — | An undecodable image crashed the preview widget | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-038 |  | defect | Medium | — | The AI rate limiter is in-memory per process (not shared across workers or instances) | FIXED (Phase 05, P05-N09) | docs/MASTER_BUG_TRACKER.md |
| BUG-039 |  | defect | Low | — | Doctor registration silently defaults a missing fee to LKR 2,500 | OPEN (product decision: profile response default fee) | docs/MASTER_BUG_TRACKER.md |
| BUG-040 |  | defect | Medium | — | After an emergency message, later messages in the same chat (even a doctor search) were re-escalated for up to three turns | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-041 |  | defect | High | — | Admin → Refunds page always failed with HTTP 500 | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-042 |  | defect | Critical (patient safety) | — | Emergency UI missing: no red banner, no 1990 button, routine booking chips still shown | FIXED; manual device retest pending | docs/MASTER_BUG_TRACKER.md |
| BUG-043 |  | defect | Critical (blocks UAT) | — | Flutter lifecycle and rendering assertions in the AI Assistant (`_owner != null`, `attached`, `!debugNeedsLayout`, `child._parent == this`, …) | FIXED; manual device retest pending | docs/MASTER_BUG_TRACKER.md |
| BUG-044 |  | defect | Medium | — | Category-specific emergency guidance | FIXED (Phase 01) | docs/MASTER_BUG_TRACKER.md |
| BUG-045 |  | defect | High | — | Chat becomes laggy, then unresponsive | FIXED; manual device retest pending | docs/MASTER_BUG_TRACKER.md |
| BUG-046 |  | defect | High (patient safety: misleading) | — | Home-screen **Emergency SOS** shows "Calling National Ambulance Service (1990)…" but never opens the dialer or places a call | FIXED (Phase 01) | docs/MASTER_BUG_TRACKER.md |
| BUG-047 |  | defect | High | — | Composer pushed off-screen in landscape with the keyboard open (part of the "composer disappears" report) | FIXED | docs/MASTER_BUG_TRACKER.md |
| BUG-048 |  | defect | Medium | — | Emergency banner in English while the reply was Sinhala (Romanized Sinhala input) | FIXED | docs/MASTER_BUG_TRACKER.md |
| P01-01 | BUG-052 | defect | High | Patient AI / UI | Educational emergency questions raised alarm | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-02 |  | defect | Medium | Patient AI / UI | Hypothetical question raised alarm | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-03 |  | defect | Critical | Patient AI / UI | Overdose not escalated | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-04 | BUG-050 | defect | High | Patient AI / UI | Self-harm shown with cardiac-style alarm | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-05 |  | defect | High | Patient AI / UI | Unverified crisis hotline number | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-06 |  | defect | Medium | Patient AI / UI | Romanized crisis phrases answered in English | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-07 | BUG-051 | defect | Medium | Patient AI / UI | Cough tiering | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-08 |  | defect | Low | Patient AI / UI | Prevention question unanswered | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-09 | BUG-054 | defect | High | Patient AI / UI | Scenario A context lost | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-10 |  | defect | High | Patient AI / UI | Scenario B budget change not parsed | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-11 |  | defect | High | Patient AI / UI | Scenario C selection not exactly one | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-12 |  | defect | Medium | Patient AI / UI | Plural specialty not recognised | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-13 | BUG-062 | defect | Medium | Patient AI / UI | Named-doctor slots asked name again | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-14 |  | defect | Medium | Patient AI / UI | Explicit year ignored | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-15 |  | defect | Medium | Patient AI / UI | Date follow-up created booking proposal | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-16 | BUG-053 | improvement | Requirement | Patient AI / UI | Top 1-2 recommendations | IMPLEMENTED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-17 | BUG-053 | improvement | Improvement | Patient AI / UI | Few-review rating handling | IMPLEMENTED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-18 |  | improvement | Finding | Patient AI / UI | Bounded LLM intent layer | IMPLEMENTED LIVE BLOCKED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-19 |  | defect | Medium | Patient AI / UI | Duplicated medicine information | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-20 |  | improvement | Improvement | Patient AI / UI | Medicine situation notes | IMPLEMENTED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-21 | BUG-049 | improvement | Requirement | Patient AI / UI | Keyboard UX | IMPLEMENTED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-22 |  | defect | Medium | Patient AI / UI | Long replies jumped to end | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-23 | BUG-057 | defect | High | Patient AI / UI | Fabricated dashboard appointment | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-24 |  | defect | High | Patient AI / UI | Fabricated vitals | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-25 |  | defect | Low | Patient AI / UI | Medicine Reminders label | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| P01-26 | BUG-056 | defect | Medium | Patient AI / UI | Unsupported video UI | FIXED | phase-01/PHASE_01_BUG_FIX_REPORT.md |
| BUG-055 |  | defect | Low | Booking / patient care | Manual slot described as closest | FIXED | phase-02/PHASE_02_BUG_ID_RECONCILIATION.md |
| BUG-058 |  | defect | Medium | Booking / patient care | Patient payment details and reference | FIXED DEVICE VERIFIED | phase-02/PHASE_02_BUG_ID_RECONCILIATION.md |
| BUG-059 |  | defect | Medium | Booking / patient care | Doctor fee display | FIXED DEVICE VERIFIED | phase-02/PHASE_02_BUG_ID_RECONCILIATION.md |
| BUG-060 |  | defect | High | Booking / patient care | Notification link Appointment not found | FIXED DEVICE VERIFIED | phase-02/PHASE_02_BUG_ID_RECONCILIATION.md |
| BUG-061 |  | defect | High | Booking / patient care | Same-doctor nearby times | FIXED | phase-02/PHASE_02_BUG_ID_RECONCILIATION.md |
| BUG-063 |  | defect | High | Booking / patient care | Manual reservation release | FIXED DEVICE VERIFIED | phase-02/PHASE_02_BUG_ID_RECONCILIATION.md |
| P02-N01 |  | defect | High | Booking / payment / care | Wrong-date proposal after choosing a doctor | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N02 |  | defect | High | Booking / payment / care | Unverified legacy payment settlement | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N03 |  | defect | Medium | Booking / payment / care | Charge used current profile fee | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N04 |  | defect | High | Booking / payment / care | Doctor could confirm unpaid appointment | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N05 |  | defect | High | Booking / payment / care | Refund integrity (fake success, caps, duplicates, double count) | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N06 |  | defect | Low | Booking / payment / care | Booking chat reused as draft | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N07 |  | defect | Medium | Booking / payment / care | Manual booking retry re-reserved own slot | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N08 |  | defect | High | Booking / payment / care | Reschedule to arbitrary time; 500 on conflict | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N09 |  | defect | Medium | Booking / payment / care | Care Agenda measurements without safety alert | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N10 |  | defect | High | Booking / payment / care | Cancelled booking granted record access (privacy) | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N11 |  | defect | High | Booking / payment / care | Fabricated doctor dashboard KPIs and ECG alert | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N12 |  | defect | Medium | Booking / payment / care | Renewal notification, prescriber-only, atomic review | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N13 |  | defect | Medium | Booking / payment / care | Live API test on port 8000 and silently skipped | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N14 |  | defect | Medium | Booking / payment / care | Mobile models invented LKR 2500 | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N15 |  | defect | Low | Booking / payment / care | Non-conditional cancellation | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N16 |  | defect | Low | Booking / payment / care | Latent datetime NameError in appointment response | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P02-N17 |  | defect | Low | Booking / payment / care | Released hold shown as payment pending | FIXED | phase-02/PHASE_02_BUG_FIX_REPORT.md |
| P03-N01 |  | defect | Critical | Appointments / consultation | Consultation start confirmed unpaid bookings | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N02 |  | defect | High | Records access | Session on a released reservation and unapproved doctors gave record access | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N03 |  | defect | High | Cancellation / refunds | Doctor cancellation of a paid booking opened no refund (also leave) | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N04 |  | defect | High | Cancellation / Stripe | Doctor cancellation left the intent payable | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N05 |  | defect | Medium | Appointments | Unconditional cancel/complete; no events | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N06 |  | defect | High | Prescriptions / reminders | Invented 08:00/20:00 14-day reminders at signing or renewal | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N07 |  | defect | Medium | Prescriptions / notes | Generated or unvalidated record and visit references | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N08 |  | defect | Medium | Renewal | Invented strength, dose, frequency and duration defaults | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N09 |  | defect | High | Clinical notes | AI drafts invented findings, assessment and plan; signable unedited | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N10 |  | defect | Medium | Notes / prescriptions | "SLMC-VERIFIED", "Dr. Doctor", "Dr. Dr." | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N11 |  | defect | High | Clinical notes | Colleagues saw unsigned drafts | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N12 |  | defect | Medium | Consultation records | Record on a future visit completed it | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N13 |  | defect | Medium | Prescriptions | Duplicates issued; blank fields accepted | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N14 |  | defect | Medium | Record summary | 500 with a signed note; "no allergies" wording | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N15 |  | defect | Low | Schedule | Invented LKR 2,500 fee; unpaid next patient | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N16 |  | defect | Medium | Doctor dashboard | Invented specialty and status, On Duty toggle, Phase badges; misleading Today figures | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N17 |  | defect | High | Care plans | Plans on unpaid or cancelled bookings gave access; name "Doctor" | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N21 |  | defect | Medium | Availability | Edits or removal orphaned booked patients | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N22 |  | defect | High | Test infrastructure | Tests could use the remote database in `.env` | Fixed, verified (remote impact unknown) | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N23 |  | defect | Medium | Doctor UI | Renewal queue and SOAP notes unreachable | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N24 |  | defect | Medium | Patient UI | Invented rating, "Nearby", next slot, "120+ Specialists", HIPAA claim | Fixed, verified | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N18 |  | improvement | — | — | Server-side care plan progress, shown to doctors | IMPLEMENTED | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N19 |  | improvement | — | — | Refund-aware doctor analytics | IMPLEMENTED | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P03-N20 |  | improvement | — | — | Doctor assistant date phrases and question routing | IMPLEMENTED | phase-03/PHASE_03_BUG_FIX_REPORT.md |
| P04-N01 |  | defect | High | Test DB guard | Look-alike or multi-host URIs passed the guard | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N02 |  | defect | Medium | `create_admin.py` | Silent write to the `.env` target | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N03 |  | defect | High | Admin appointments (P3-B2) | Null fee crashed the page; API invented 0.00 and a specialty | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N04 |  | defect | High | Admin payments | Always "test mode"; date filters ignored | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N05 |  | defect | Critical | Financial figures | Refunds counted twice; partial refunds ignored; invented 10% fee; 100% success with no data; per-city counts always 0 | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N06 |  | defect | High | Date ranges | UTC days; end day excluded; bad dates defaulted | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N07 |  | defect | Medium | Doctor counts | Pending count missed `PENDING_ADMIN_APPROVAL`; suspended counted as verified | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N08 |  | defect | High | Approval and status changes | No audit; approval without registration number; PENDING could be activated; refresh tokens kept | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N09 |  | defect | High | Refund service | Rejection could overwrite an approval; 500 on bad IDs; no patient notice | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N10 |  | defect | High | Refund source and UI (B15, P3-B3) | No source; no retry, error state or validation | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N11 |  | defect | High | Reconciliation | "Confirm booking immediately" advice; no amount/currency check | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N12 |  | defect | High | Fraud | Failed-payment rule never fired; admin events counted; bad decisions accepted | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N13 |  | defect | High | Heartbeat endpoint | No authentication | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N14 |  | defect | High | Platform monitoring | Invented healthy states and job counts | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N15 |  | defect | High | Notification monitoring | Push counted delivered; retries went to an unprocessed state | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N16 |  | defect | Medium | Monitoring assistant | "Operating normally" always; AI "healthy" | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N17 |  | defect | High | Reports and CSV | Unknown type → refund report; zeros blank; incomplete escaping; requested amounts used as refunded | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N18 |  | defect | Medium | Support | Could link another patient's booking; no reply notice; false promise | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N19 |  | defect | Medium | Report audit | Exports not audited | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N20 |  | defect | High | Event inserts | Second insert onward failed (`_id: null`) | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N21 |  | defect | Medium | Admin web labels | "Real-time", "Revenue", "Verified", fake 30 days, "Production API" | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N22 |  | defect | Medium | Fraud re-evaluation | Stale rules and explanation returned | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P04-N23 |  | defect | Medium | Admin confirmations | Double click → two approve requests | Fixed | phase-04/PHASE_04_BUG_FIX_REPORT.md |
| P05-N01 | P4-B5 | defect | High | Config / DB safety | Backend started with `backend/.env` and no `ENVIRONMENT` → used the remote cluster silently | FIXED, VERIFIED (tests) | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N02 |  | defect | High | Auth | 8 concurrent refreshes with one token → several 200s | FIXED, VERIFIED (live) | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N03 |  | defect | Medium | Auth | refresh token of a deleted account → 500 (`NoneType.get`) | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N04 | P4-B2 (technical part) | defect | High | Config / JWT | 11-character common-word secret accepted outside production | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N05 |  | defect | Medium | Auth | tokens without `iss`/`aud`/`jti` accepted | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N06 |  | defect | Medium | Auth | logout → access token still worked for up to 60 min | FIXED, VERIFIED (live) | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N07 |  | defect | Medium | Auth | token issued before suspension worked again after reinstatement | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N09 | BUG-038 | defect | Medium | Rate limiting | limits multiplied by the number of processes; reset on restart | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N10 | P4-O8 | defect | Low | API | security router mounted at `/api` and root | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N11 |  | defect | Medium | Medical records | upload with unknown `recordType` → 500 after the file was written (orphan file); admins could upload "patient" records for themselves | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N12 |  | defect | High | AI providers | Gemini parser and health assistant sent the API key as `?key=` | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N13 |  | defect | Medium | AI monitoring | provider metrics and circuit breaker never changed | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N14 |  | defect | Medium | AI providers | health assistant mapped model names to the retired `gemini-1.5-flash` | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N15 |  | defect | Medium | Conversation memory | "cardiologist in Atlantis" → "in Colombo then" → clarification, city lost | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N16 |  | defect | Low | Scheduler | with an injected clock, live leases were judged expired and set to `uncertain` mid-delivery | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N17 |  | defect | Medium | Doctor schedule | 4 processes creating the same block → 4 identical blocks (sequential duplicates too) | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N18 | B7 | defect | High | Health tracking | after one Care Agenda reading, `GET /clinical/measurements` (patient and doctor) → unhandled ValidationError | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N19 |  | defect | Medium | Admin assistant | "successful payments this week" said "39 (13 of them refunded)", but those 13 were not part of the 39 (fully refunded payments are counted separately) | FIXED before release | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N20 |  | defect | High | Care plans | 4 concurrent updates all 200, version +3 (one update lost) | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N21 | B17 | defect | Medium | Emergency triage | Sinhala chest-pain emergency, then "ok" → English emergency text | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N22 | B16 | defect | High | Patient assistant | "change my dose to two tablets" → medicine-database lookup | FIXED; pharmacist review pending (B2) | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N23 |  | defect | Medium | Patient assistant | "When should I take the medicine prescribed by my doctor?" → prescription refusal | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N24 | P4-O1 | defect | Medium | Medical records | one malformed record → whole list 500 | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N25 | P4-O7 | defect | Medium | Payments | reconcile-refund (an admin financial action) not audited | FIXED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N26 |  | defect | Medium | Admin web | admins would be signed out on every access-token expiry; logout cleared the token before calling the API, so the access token was never revoked | FIXED, VERIFIED (browser) | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-N08 | P4-B9, P4-O5 | improvement | — | — | Privacy-preserving failed-login telemetry and brute-force signal (no lockout) | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I01 | B8 | improvement | — | — | Application-level document encryption, key rotation, reversible migration script, document-view audit | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I02 | Component 33 | improvement | — | — | Shared role-specific intent router (patient, doctor, admin); admin intents for payments, notifications, fraud, health; doctor renewal queue | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I03 | Component 31 | improvement | — | — | Orchestrator bounds (total calls, duplicates, tool timeout, result validation, mutating-tool confirmation, loop detection, run records) | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I04 | Component 32 | improvement | — | — | Provider gateway (limits, circuit breaker, categories, metrics, truthful status) | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I05 | B3, P4-B10 | improvement | — | — | Stripe webhook event log, `payment_intent.canceled`, refund events, pending-refund polling fallback | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I06 | P3-B8 | improvement | — | — | Consultation preparation with shared authorized sources and missing-information list | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I07 | P3-B7 | improvement | — | — | Readable labels in the doctor workflow screen | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I08 | P4-O3, P4-B3 | improvement | — | — | Admin CSP, no third-party fonts; dev API target 8001 | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I09 | P4-O4 | improvement | — | — | Admin list paging in MongoDB + two indexes | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I10 |  | improvement | — | — | Dependency minimum versions raised; non-breaking npm fixes | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I11 |  | improvement | — | — | `CONVERSATION_RETENTION_DAYS` (default unchanged) | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-I12 | P4-B6 | improvement | — | — | Read-only P4-B6 reconciliation report (UAT) | IMPLEMENTED | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P05-O1 |  | observation | Low | Tests | Intermittent test_phase3_care failure (6 reminder rows once) | OPEN (not reproduced) | phase-05/PHASE_05_BUG_FIX_REPORT.md |
| P5-C1 |  | security incident | Critical | Repository / credentials | Live MongoDB URI with credentials in public git history (a41b659) | OPEN — owner rotation required | phase-05/PHASE_05_SECURITY_AND_PRIVACY_REPORT.md |
| A01-N01 |  | defect | Critical (safety) | Emergency triage (02, shared) | "My child swallowed a whole strip of my blood pressure tablets." was not detected as an emergency. | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N02 |  | defect | High | Provider gateway (32) | OpenAI 429 insufficient_quota (no credits) | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N03 |  | defect | High | Provider monitoring (32) | A 200 response whose JSON was unusable still counted as a success, so monitoring could show "available" while every answer was discarded. | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N04 |  | defect | Medium | Provider gateway (32) | The single retry happened immediately; Retry-After was ignored. | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N05 |  | defect | High | Health Assistant (02) | With no working provider, 11 of 26 probe messages got the same paragraph ("Balanced nutrition, adequate hydration…"): paracetamol, sleep, ex | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N06 |  | defect | High (cost/privacy) | Test suite (32) | The suite inherited the real GEMINI_API_KEY/OPENAI_API_KEY from backend/.env, so tests that did not patch the network made live provider cal | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N07 |  | defect | Medium | Provider gateway (32) | Gemini's free-tier daily quota 429 ("requests per day … retry in 21h") | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N08 |  | defect | Medium | Image upload (04) | Both image routes read the whole upload into memory before the 5 MB check. | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N09 |  | defect | High (safety) | Medicine vision (04) | For the blurred fixture the live model returned exact label text ("Synthopar 500", "Paracetamol 500 mg", the storage line) | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N10 |  | defect | High | Provider architecture (32) | No secondary provider anywhere: the Health Assistant called only Gemini, vision and the doctor-search parser never fell back to the other pr | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N11 |  | defect | High | Model selection (32) | backend/.env names gemini-1.5-flash (live: 404, shut down). | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N12 |  | defect | High | Health Assistant (02) | Provider output was accepted after json.loads with no schema, language check or grounding check. | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N13 |  | defect | Medium | Vision UI (04) | The image card repeated the field list already in the chat reply ("Detected Packaging Text"), and showed a "High Confidence" badge that the  | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N14 |  | defect | Medium (safety) | Medicine vision (04) | A photo with two packages was matched to one library card (the first name found). | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N15 |  | defect | Medium | Health Assistant (02) | A 3-day headache was referred to a Neurologist and a cold to an ENT specialist. | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N16 |  | defect | Medium | Shared NLU (02) | "mata dawas thunak thisse …" and "දවස් තුනක්" (three days) | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-N17 |  | defect | Medium | Shared NLU (02) | "How many paracetamol tablets can I take at once…? Give me an exact number." was not recognised as a dose request (generic answer). | FIXED (A01) | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-O1 |  | observation | Low | A01 | A foreign patient gets **403** (not 404) for another patient's conversation | OPEN | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-O2 |  | observation | Low | A01 | Live V17: the model listed fields that are simply absent (expiry, manufacturer) as "not readable" | OPEN | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-O3 |  | observation | Low | A01 | "since yesterday" is not parsed as a duration (H04) | OPEN | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A01-O4 |  | observation | Low | A01 | The Gemini free tier allows 20 generation requests per day for `gemini-3.8-flash`; that quota ran out during A01 | OPEN | agent-completion/a01/A01_BUG_FIX_REPORT.md |
| A02-BUG-001 |  | defect | High | E-mail (13) | SMTP over STARTTLS/SMTPS accepted any certificate (found by reading the code; confirmed with a self-signed local server) | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-002 |  | defect | High | Tests | The backend test suite sent real e-mail through the owner's SMTP account on every local run. | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-003 |  | defect | Medium | E-mail | Every SMTP exception became uncertain and was never retried, including "connection refused" (nothing sent). | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-004 |  | defect | Medium | Monitoring (13) | An unconfigured provider was reported as failed, and provider acceptance (sent/accepted) | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-005 |  | defect | High | Scheduler | A worker crash after claiming a reminder but before the in-app write meant the patient never received it (whole event → uncertain) | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-006 |  | defect | High | Push (13) | Push notifications put the full in-app text on the lock screen: doctor and patient names, dates and specialty (for example "Your appointment | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-007 |  | defect | Medium | Push | A quota, server or bad-payload FCM error could delete every device token of the user | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-008 |  | defect | Low | Device tokens | Unbounded device list per user, unchecked deviceType, and the first 10 characters of a raw token logged | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-009 |  | defect | Medium | Delivery tracking | No transactional notification (booking, cancellation, payment, renewal) | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-010 |  | defect | Low | Monitoring | cleanup_invalid_device_tokens never removed anything | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-011 |  | defect | High | Medication reminder (05) | A patient could create reminders for an as-needed (PRN) | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-012 |  | defect | Medium | Assistant (05/13) | "Show my medicine reminders for today" got a medicine-library lookup ("could not locate … medication name"). | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-013 |  | defect | Low | Assistant | "What medical tests do I have this week?" read only today, and "When is my next appointment?" listed one that had already started | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-014 |  | defect | Medium | Patient communication (19) | A doctor changing a follow-up date, instructions or test tasks, or closing the plan, did not tell the patient | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-015 |  | defect | Medium | Follow-up (08) | Re-saving a care plan with the same follow-up date was treated as a change: remindersSent was reset (date-based reminders could repeat) | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-016 |  | defect | High | Mobile medication reminders | Device-local reminders were open-ended daily repeats. | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-017 |  | defect | High | Mobile logout | After logout, the previous account's device reminders kept firing for the next user. | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-018 |  | defect | Medium | Mobile sync | The device was never synchronised after a reinstall, a new phone or a sign-in. | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-019 |  | defect | High | Mobile Android manifest | Scheduled device reminders were never shown and were lost on reboot | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-020 |  | defect | High | Mobile Android 13+ permission | The notification permission was never requested while Firebase is unconfigured, so Android suppressed every device reminder (POST_NOTIFICATI | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-BUG-021 |  | defect | Medium | Patient communication (19) | A prescription issued from the clinical workflow (POST /clinical/prescriptions/sign) | FIXED (A02) | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-O1 |  | observation | Low | A02 | NotificationService.check_and_send_appointment_reminders (24 h / 1 h) is legacy code that no worker calls | OPEN | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-O2 |  | observation | Low | A02 | Device-local reminders use Android inexact alarms (inexactAllowWhileIdle) | OPEN | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-O3 |  | observation | Low | A02 | normalize_phone accepts only 07XXXXXXXX and +947XXXXXXXX; 94…/0094… forms are refused (safe, but strict) | OPEN | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-O4 |  | observation | Low | A02 | Two test_phase02_booking_payment / test_production_security_audit tests fail when run **alone on an empty database**, because they depend on | OPEN | agent-completion/a02/A02_BUG_FIX_REPORT.md |
| A02-O5 |  | observation | Low | A02 | The "AI" patient-communication drafting is a fixed template (appointment reminder batch) with an HMAC approval token | OPEN | agent-completion/a02/A02_BUG_FIX_REPORT.md |
