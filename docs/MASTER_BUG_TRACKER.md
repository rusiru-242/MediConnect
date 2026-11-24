# MediConnect — Master Bug Tracker

Branch: `fix/comprehensive-system-ai-stabilization` · Baseline commit: `c3e0aac` · Last updated: 2026-11-24

## How to read this tracker

- **Statuses:** OPEN · INVESTIGATING · FIXED (code changed + automated regression test) · VERIFIED (fixed and confirmed on a real device / live integration) · BLOCKED · PENDING MANUAL RETEST · NOT REPRODUCED.
- No bug is marked **VERIFIED**: none of the fixes have yet been confirmed on a physical device or against live Gemini, Stripe, FCM, email or SMS. "FIXED" means the root cause was confirmed in code and an automated regression test now passes.
- **About BUG-001 to BUG-009:** the repository has no earlier bug report with these IDs. Only **BUG-004** (unnatural Sinhala) and **BUG-007** (duplicate doctor cards) were named in the request. The other Section A issues received **provisional** IDs in this session (BUG-001, 002, 003, 005, 006, 008, 009). If your original list used different descriptions, re-map these IDs. The test names and commit messages use the provisional IDs.
- Severity: **Critical** (patient safety or money) · **High** (core feature broken) · **Medium** · **Low**.
- Test file abbreviations: `stab` = `backend/tests/test_comprehensive_stabilization.py`, `cons` = `backend/tests/test_availability_consistency.py`, `ai-ui` = `mobile/test/screens/ai_assistant_stabilization_test.dart`, `avail-ui` = `mobile/test/screens/availability_stabilization_test.dart`, `money` = `mobile/test/utils/money_test.dart`.

## Summary

| Category | Count |
|---|---|
| Known issues from manual testing (BUG-001 to BUG-026) | 26 |
| New issues found during this audit (BUG-027 to BUG-039) | 13 |
| FIXED (root cause confirmed in code, regression test passing) | 31 |
| Fix applied, PENDING MANUAL RETEST on a device | 4 (BUG-004, BUG-014, BUG-015, BUG-025) |
| BLOCKED for final verification (external dependency) | 1 (BUG-023, live Vision provider) |
| OPEN | 2 (BUG-038, BUG-039) |
| Not a defect / regression guard | 1 (BUG-009) |
| **Total tracked** | **39** |

---

## Known issues (manual testing)

### BUG-001 — A follow-up message replaced the previous search instead of refining it *(provisional ID)*
- **Severity:** High · **Component:** AI Conversation Memory (#35), AI Doctor Booking Agent (#1)
- **Reproduction:** "Find a cardiologist in Colombo" → "mata 3000ta aduwen kenek hoyala denna".
- **Expected:** Specialty and city stay the same; only the budget changes.
- **Actual:** The budget was not understood, so the follow-up got a generic clarification. An English "find…" follow-up also reset every earlier preference.
- **Confirmed root cause:** (1) `extract_max_fee` had no Romanized Sinhala patterns. (2) `booking_agent.process_user_turn` cleared all preferences whenever the message contained "find", "search for" or "recommend", even if it only changed the budget.
- **Fix:** Romanized budget patterns added. Preferences are reset only for a *new* search, meaning one that names a specialty, city, doctor or hospital. Budget, rating and ordering messages refine the current search.
- **Files:** `backend/app/agents/nlp_parser.py`, `backend/app/agents/booking_agent.py`
- **Regression test:** `stab::test_bug001_followup_updates_only_budget`
- **Status:** FIXED

### BUG-002 — Romanized Sinhala budget ignored (LKR 3500 doctor returned for "3000ta aduwen") *(provisional ID)*
- **Severity:** High · **Component:** #1, #3, Intent Classification (#33)
- **Reproduction:** "mata Colombo walin LKR 3000ta aduwen cardiologist kenek hoyala denna"
- **Actual:** A doctor charging LKR 3,500 was shown.
- **Confirmed root cause:** No `maxFee` was extracted (same parser gap as BUG-001), so no budget filter was applied.
- **Fix:** Parser now handles `3000ta aduwen`, `3000 ta adu`, `3000kata wada adu`, `wenakan`, `rupiyal …`, `3k` (only when next to a budget word), and Sinhala `3000ට අඩු`. The budget is always enforced on the server.
- **Regression tests:** `stab::test_bug002_budget_parsing_romanized_and_english[*]` (7 cases), `stab::test_bug002_romanized_budget_enforced`, `stab::test_english_budget_filter_still_works`
- **Status:** FIXED

### BUG-003 — Romanized Sinhala doctor search and preference understanding *(provisional ID)*
- **Severity:** High · **Component:** #33
- **Root cause:** The vocabulary was missing common Romanized forms: city names (`kolamba`, `galla`, `mahanuwara`), specialty words (`hrudaya`/`hadawatha`, `snayu`, `lamaya`, `same rog`) and search verbs (`hoyala denna`).
- **Fix:** Vocabulary added to `nlp_parser.py` and `clinical_intent.py`.
- **Regression tests:** `stab::test_bug011_unsupported_location_detected` (kolamba), `stab::test_bug002_*`
- **Status:** FIXED. Coverage is still limited to the phrasing that was tested; see the limitation in AI_AGENT_VERIFICATION_MATRIX #33.

### BUG-004 — Unnatural or unclear Sinhala responses
- **Severity:** Medium · **Component:** All patient AI responses
- **Fix:** All new Sinhala text (emergency guidance, symptom guidance, prescription refusal, unsupported location, image analysis, auto-selection) was written in plain conversational Sinhala. The older Sinhala strings in the wellness and booking templates were **not** rewritten.
- **Status:** PENDING MANUAL RETEST. Requires review by a native Sinhala speaker; see the UAT plan section P-12.

### BUG-005 — Calendar connection error when changing months *(provisional ID)*
- **Severity:** High · **Component:** Doctor Schedule Management (#14)
- **Confirmed root causes:**
  1. `get_doctor_calendar_overview` ran the full slot generator once per day of the month: about 30 runs of roughly 6 queries each, plus one user lookup per appointment. Against Atlas this can exceed the app's 15-second request timeout, which the app shows as "Unable to connect".
  2. A month such as `2026-13` caused an unhandled `ValueError` (HTTP 500).
  3. The Flutter screen replaced a failed calendar response with an empty month, and a slow response from a previous month could overwrite the current one.
- **Fix:** The month's slots are now computed in **one** batched pass (`get_doctor_patient_slots(date_list=…, return_map=True)`). Patient names are fetched in one query. Invalid months return 400. The Flutter screen shows a calendar error with Retry and ignores stale responses.
- **Files:** `backend/app/services/doctor_service.py`, `mobile/lib/screens/doctor/manage_availability_screen.dart`
- **Regression tests:** `cons::test_bug005_*` (invalid months, past and future navigation, single batched generator call), `avail-ui` (calendar error, month reload)
- **Status:** FIXED (device check: UAT D-02)

### BUG-006 — New availability windows not shown in the calendar *(provisional ID)*
- **Severity:** High · **Component:** #14
- **Investigation:** The doctor calendar, patient profile slots and AI booking slots all use `get_doctor_patient_slots`. With the BUG-005 timeout fixed, a new window appears in all three. The app had also been hiding calendar failures by showing an empty month (BUG-005, cause 3).
- **Regression tests:** `cons::test_bug006_new_window_appears_in_calendar_patient_profile_and_ai`, `cons::test_bug006_booked_slot_removed_everywhere`
- **Status:** FIXED (device check: UAT D-03)

### BUG-007 — Duplicate doctor recommendation cards and wrong unique-doctor counts
- **Severity:** Medium · **Component:** #1, #3
- **Investigation:** Nothing removed duplicates by doctor identity, either in the AI search or in `list_approved_doctors`. The unique indexes on `userId`, `doctorId` and registration number exist in code. The production database **was not inspected**; `backend/scripts/audit_doctor_data.py` (read-only) reports duplicates and missing indexes.
- **Fix:** Results are de-duplicated by doctor user ID, then doctor ID, then profile ID, in the AI search and in doctor listing.
- **Regression tests:** `stab::test_bug007_dedupe_by_canonical_identity`, `stab::test_bug022_rating_filter_and_experience_ranking` (no duplicate IDs)
- **Status:** FIXED. Run the audit script on staging to confirm whether duplicate *records* exist.

### BUG-008 — Consultation fees shown as "Fee unavailable" *(provisional ID)*
- **Severity:** Medium · **Component:** #1, #3
- **Confirmed root cause:** The AI tool path filtered fees with `{"$type": "number"}`, so fees stored as strings ("3,500") or Decimal128 were dropped or shown as unavailable. The AI search compared raw values (a string fee could crash the comparison). Missing fees were genuinely missing and must stay unavailable.
- **Fix:** `coerce_fee()` normalizes number, numeric-string and Decimal128 fees. It returns `None` for anything else; no fee is ever invented. Used in the AI search, doctor listing, doctor detail, booking and payment.
- **Regression tests:** `stab::test_bug008_*`, `cons::test_bug028_string_fee_is_charged_as_listed`, `money`
- **Status:** FIXED

### BUG-009 — English budget filtering works (preserve) *(provisional ID; regression guard)*
- **Status:** Not a defect. Guarded by `stab::test_english_budget_filter_still_works`.

### BUG-010 — Automatic doctor selection not working
- **Severity:** Medium · **Component:** #1, #3
- **Confirmed root cause:** No logic existed to detect "select only one doctor for me".
- **Fix:** `wants_auto_selection()` detects the request (English and Romanized Sinhala). The top-ranked doctor that meets every hard constraint is selected. The explanation uses only real profile data and says the choice is "not a judgement of clinical quality". No booking or payment is made.
- **Regression test:** `stab::test_bug010_automatic_selection_selects_exactly_one`
- **Status:** FIXED

### BUG-011 — "Antarctica" search suggested Colombo as a nearby city
- **Severity:** Medium · **Component:** #1
- **Confirmed root cause:** The no-results message always said "search a nearby city (e.g. Colombo)", and unknown places were silently ignored.
- **Fix:** `extract_unsupported_location()` recognizes places outside the supported Sri Lankan list and replies with the coverage area. The no-results message no longer claims anything is nearby.
- **Regression tests:** `stab::test_bug011_*`
- **Status:** FIXED

### BUG-012 — Health questions routed to doctor search
- **Severity:** High · **Component:** Intent Classification (#33), AI Health Assistant (#2)
- **Confirmed root cause:** In English, any symptom word fell through to `FIND_DOCTOR`, and "headache" mapped to Neurologist cards. "oluwa ridenawa" was not recognized at all, which led to a generic clarification.
- **Fix:** `is_health_advice_request()` (symptoms plus a "what should I do", a duration or a first-person statement, with no explicit doctor request) now produces general guidance: self-care, red flags, when to see a doctor, follow-up questions and no prescriptions. It runs before doctor routing.
- **Regression tests:** `stab::test_bug012_*`
- **Status:** FIXED

### BUG-013 — Multilingual emergency detection failure (CRITICAL release blocker)
- **Severity:** Critical · **Component:** Symptom Triage Engine (#34), all patient assistants
- **Confirmed root cause:** Emergency patterns were English regexes plus a few *exact* Sinhala phrases. "මගේ පපුව **ගොඩක්** රිදෙනවා" does not contain "පපුව රිදෙනවා", "හුස්ම ගන්න**ත්** අමාරුයි" does not contain "හුස්ම ගන්න අමාරුයි", and there were no Romanized Sinhala patterns at all.
- **Fix:** New deterministic `emergency_detector.py`:
  - Detection is concept-based (body part plus distress, within one clause) across English, Sinhala script (inflection-tolerant) and Romanized Sinhala.
  - Covers 11 categories: cardiac, respiratory, stroke, unconsciousness, bleeding, seizure, anaphylaxis, poisoning, self-harm, head injury and snakebite.
  - Handles negation scope, historical mentions and informational questions.
  - Considers the last three user messages, and keeps the escalation on follow-ups after an alert.
  - Runs **before** all routing in the AI Assistant and the Health Chat. The older keyword checks are kept as an extra safety net.
  - Needs no AI provider.
  - Self-harm messages get Sri Lankan helpline guidance (1926, Sumithrayo).
- **Regression tests:** `stab::test_bug013_*`: 26 positive cases, 12 false-positive controls, context tests, and API tests for both assistants.
- **Status:** FIXED in software. **Clinical validation has not been done**; it is still a release requirement (see SECURITY_AND_CLINICAL_SAFETY_REPORT.md).

### BUG-014 — Duplicate chat input fields
- **Severity:** High · **Component:** Flutter AI Assistant
- **Investigation:** The screen itself builds exactly one composer, and the tests confirm this. The most plausible cause is that the assistant route was pushed twice: a fast double tap on the home button or a hero chip stacks two assistant screens.
- **Fix:** `AssistantNavigation.open()` ignores repeat requests until the route closes. Hero-chip prompts now reach the screen (they were previously dropped).
- **Regression tests:** `ai-ui` "exactly one composer…", "keyboard inset…", "double tap opens the assistant only once…"
- **Status:** PENDING MANUAL RETEST (not reproduced on a device; UAT P-14)

### BUG-015 — `_owner != null` assertion when pressing Back in the AI Assistant
- **Severity:** High · **Component:** Flutter AI Assistant
- **Investigation:** Not reproduced in widget tests. Likely triggers: post-frame scroll callbacks and the hold-countdown `setState` running while the route is being torn down, focus still on the text field, and a duplicated route (BUG-014).
- **Fix:** On pop: unfocus, cancel the timer and invalidate pending uploads. Every post-frame scroll is now guarded (disposed, mounted, `hasClients`, `hasContentDimensions`). The timer `setState` is guarded. Plus the BUG-014 navigation guard. No assertions were suppressed.
- **Regression test:** `ai-ui` "pressing Back with a focused input and pending reply does not throw"
- **Status:** PENDING MANUAL RETEST (UAT P-15)

### BUG-016 — Ambiguous medicine strength display (`500mg / 120mg/5ml`)
- **Severity:** Medium · **Component:** Medicine information (#2)
- **Fix:** Each medicine now has `formulations: [{form, strength}]`, for example "Tablet: 500 mg per tablet" and "Oral liquid: 120 mg in each 5 mL". The app shows one line per formulation with the note "Strengths are not dose recommendations".
- **Regression tests:** `stab::test_bug016_*`, `ai-ui` formulations
- **Status:** FIXED

### BUG-017 — Universal paracetamol dose statement ("8 tablets / 4000 mg") without context
- **Severity:** Critical (medication safety) · **Component:** Medicine information
- **Fix:** Universal daily maximums were removed in English and Sinhala and replaced with "a maximum exists; it depends on age, weight, liver health, alcohol and other medicines; ask a pharmacist". Added: "If too much was taken, call 1990 or go to the ETU **even without symptoms**". Every card is flagged `contentReviewStatus: PENDING_PHARMACIST_REVIEW`.
- **Regression tests:** `stab::test_bug017_*`
- **Status:** FIXED. All medicine content still needs pharmacist review.

### BUG-018 — Antibiotic prescription request answered with "medicine not found"
- **Severity:** Critical · **Component:** #2, Safety Guard (#37)
- **Confirmed root cause:** "antibiotic" matched the medicine-lookup pattern.
- **Fix:** `is_prescription_request()` runs first and returns a refusal: no prescription, dose or duration. It explains why an assessment is needed and the risks of using antibiotics for viral infections, then gives symptom guidance.
- **Regression tests:** `stab::test_bug018_*`
- **Status:** FIXED

### BUG-019 — Multi-topic wellness question answered only for diet
- **Severity:** Medium · **Component:** #2
- **Confirmed root cause:** The classifier returned the first match (food patterns are checked before sleep). The message text was only a one-line lead-in, with the details in a single card.
- **Fix:** `wellness_topics()` detects every topic. Two or more topics produce one combined answer with a section for each.
- **Regression tests:** `stab::test_bug019_*`
- **Status:** FIXED

### BUG-020 — "Without sleeping pills" routed to medicine search
- **Severity:** Medium · **Component:** #33
- **Confirmed root cause:** The word "pills" matched the medicine pattern before the sleep pattern was checked; negation was ignored.
- **Fix:** Negated medication ("without pills", "naturally", "beheth nathuwa") together with a wellness topic now goes to wellness guidance.
- **Regression tests:** `stab::test_bug020_*`
- **Status:** FIXED

### BUG-021 — No explanation of why a specialty suits the symptoms
- **Severity:** Low · **Component:** #3
- **Fix:** When the specialty was inferred from symptoms, the reply adds what that specialist treats and "this is a suggestion of the right type of doctor, not a diagnosis" (English and Sinhala).
- **Regression test:** `stab::test_bug021_symptom_specialty_is_explained`
- **Status:** FIXED

### BUG-022 — Preference ranking (experience) not applied or explained; opaque match score
- **Severity:** Medium · **Component:** #3
- **Confirmed root causes:** The AI search read `doctor_profiles.rating`, a field that does not exist, so every rating was 0. There was no experience ordering. The "% Match" score was mostly a constant.
- **Fix:** Ratings now come from **published reviews**. `minRating` is a hard filter. `sortBy` is applied (`experience_desc`, `rating_desc`, `fee_asc`). Each card carries `rankPosition` and `rankingExplanation`, and the opaque `matchScore` was removed.
- **Regression tests:** `stab::test_bug022_*`
- **Status:** FIXED

### BUG-023 — Medicine photo always analysed as "Generic Medicine Label"
- **Severity:** Critical (fabricated output) · **Component:** Medicine Image Recognition Agent (#4)
- **Confirmed root causes:**
  1. The Vision call used the retired model `gemini-1.5-flash` with a hard-coded URL, so it failed.
  2. On failure the code returned the literal string "Generic Medicine Label", which was shown as "Extracted Text".
  3. Medicines were "identified" from the **file name** or prompt, never from the image.
  4. Text-only requests analysed fabricated PNG bytes.
  5. The call was synchronous inside the event loop, with the API key in the URL and a 6-second timeout.
- **Fix:**
  - Structured JSON extraction from the real image bytes, using the configured model (retired names are mapped), the key in a header, and `asyncio.to_thread` with a 25-second timeout. OpenAI is the fallback provider.
  - Truthful statuses: `analyzed`, `unreadable`, `not_medicine`, `provider_unavailable`, `invalid_file`.
  - The reply separates "Text read from your photo (not verified)" from reference-library information.
  - Loose tablets are never identified.
  - Text-only requests now ask for a photo. The filename shortcut was removed.
  - Uploaded photos are no longer saved to disk.
- **Regression tests:** `stab::test_bug023_*` (8 tests, provider stubbed). Two older tests that asserted the placeholder behaviour were rewritten to stub the provider.
- **Status:** BLOCKED for final verification. The code path is FIXED, but a live Gemini Vision call with the real omeprazole photo has not been run (it needs staging credentials and approval to send images to the provider). See UAT P-09.

### BUG-024 — Raw Markdown shown (`**Medicine Packaging Analysis**`)
- **Severity:** Medium · **Component:** Flutter AI Assistant
- **Fix:** `SafeMarkdownText` renders headings, bold, italic, bullets and numbered lists. It has no HTML, link or image handling.
- **Regression tests:** `ai-ui` BUG-024 group
- **Status:** FIXED

### BUG-025 — "Incorrect email or password" shown during image upload
- **Severity:** High · **Component:** Flutter networking, Authentication
- **Confirmed root causes:**
  1. `ApiClient.postMultipart` had no 401 → refresh → retry path (JSON requests have one), so an expired access token failed the upload while the next JSON call refreshed silently. This explains why the error did not repeat.
  2. `ApiErrorMapper` turned **every** 401 into "Incorrect email or password."
- **Fix:** Multipart uploads buffer their files, refresh the token on 401 and retry once, sharing the existing single-flight refresh lock. A generic 401 now reads "Your session has expired. Please sign in again." Real login rejections keep their message. Authentication was not weakened.
- **Regression tests:** `ai-ui` BUG-025 group, `stab::test_bug025_image_endpoint_requires_authentication`
- **Status:** PENDING MANUAL RETEST (needs an expired-token scenario on a device; UAT P-10)

### BUG-026 — No upload progress or feedback
- **Severity:** Medium · **Component:** Flutter AI Assistant
- **Fix:** The user message shows a photo thumbnail. A "Uploading and analysing your photo…" panel with a progress bar and **Cancel** stays above the composer. On failure the photo is kept and a **Retry** button appears. The analysis badge reflects the real status (for example "Not analysed"). Uploads have a 60-second timeout.
- **Regression tests:** `ai-ui` BUG-026 group, `stab::test_bug026_image_endpoint_records_attachment_and_status`
- **Status:** FIXED (device check: UAT P-09)

---

## New issues found during this audit

| ID | Title | Severity | Root cause | Files | Test | Status |
|---|---|---|---|---|---|---|
| BUG-027 | Availability screen showed a **fabricated weekly schedule** when loading failed, and saving would persist it | High | `_fallbackWeeklySchedule()` returned hard-coded Mon/Tue/Thu/Fri sessions | `manage_availability_screen.dart` | `avail-ui` BUG-027 | FIXED |
| BUG-028 | Patients **charged a default LKR 2,500** when the doctor had no listed fee; string fees crashed booking | Critical | `float(profile.get("consultationFee", 2500.0))` in appointment, payment and recommendation code | `appointment_service.py`, `payment_service.py`, `recommendation_engine.py` | `cons::test_bug028_*` | FIXED |
| BUG-029 | Invented values shown to patients: **4.8 rating**, LKR 2,500 fee, city "Colombo" | High | Defaults in `health_assistant_agent.py` and in the Flutter models `doctor.dart`, `doctor_recommendation.dart`, `health_chat.dart` | backend + `mobile/lib/models/*`, `utils/money.dart` | `money` | FIXED |
| BUG-030 | AI search applied an unsorted 200-row cap **before** name filtering and ranking, so named or best doctors could be dropped | Medium | `.find(...).limit(200)` | `booking_agent.py` | `test_ai_booking_agent::test_persistent_doctor_follow_up…` | FIXED |
| BUG-031 | Sinhala substring rules mis-assigned specialties ("සම" in "සමඟ" meant Dermatology; "හම" in "හමුවන්න"; "කන" in "කන්න") | Medium | Substring matching on very short words | `nlp_parser.py` | `stab::test_new_bug_sinhala_substring_specialty_false_match` | FIXED |
| BUG-032 | Image upload rejected in a persistent chat that had once completed a booking | Low | State check copied from short-lived sessions | `booking_session_service.py` | covered by `stab::test_bug026_*` | FIXED |
| BUG-033 | Image-analysis confidence badge always "Uncertain" | Low | App checked `MEDIUM`; backend sends `moderate` | `ai_care_assistant_screen.dart` | manual (UAT P-09) | FIXED |
| BUG-034 | Backend CI could run the test suite against a **real Atlas database** when a `MONGODB_URI` secret exists | High | `${{ secrets.MONGODB_URI || … }}` | `.github/workflows/backend-ci.yml` | CI run | FIXED |
| BUG-035 | Uploaded medicine photos written permanently to `uploads/companion_images` although never served | Medium (privacy) | Unneeded write in `send_session_image` | `routes/ai_booking.py` | `stab::test_bug026_*` | FIXED |
| BUG-036 | Home-screen hero prompt chips lost their prompt | Low | Route arguments ignored by the `routes:` table | `main.dart`, `assistant_navigation.dart` | `ai-ui` double-tap test | FIXED |
| BUG-037 | An undecodable image crashed the preview widget | Low | `Image.memory` without `errorBuilder` | `ai_care_assistant_screen.dart` | `ai-ui` BUG-026 | FIXED |
| BUG-038 | The AI rate limiter is in-memory per process (not shared across workers or instances) | Medium | `_RATE_LIMIT_BUCKET` dict | `routes/ai_booking.py` | — | OPEN (needs a shared store such as Redis; see security report) |
| BUG-040 | After an emergency message, later messages in the same chat (even a doctor search) were re-escalated for up to three turns | Medium | The BUG-013 context rule re-evaluated earlier messages on every turn | `emergency_detector.py` | `stab::test_bug040_*` | FIXED (found during UAT preparation) |
| BUG-041 | Admin → Refunds page always failed with HTTP 500 | High | `RefundService.list_refund_requests` was a `@classmethod` without `cls` (an AST scan found no other occurrence) | `refund_service.py` | `stab::test_bug041_admin_refund_list_does_not_crash` | FIXED (found during UAT preparation) |
| BUG-039 | Doctor registration silently defaults a missing fee to LKR 2,500 | Low | `schemas/doctor.py` default | — | — | OPEN (product decision; the admin should confirm fees during verification) |

## Suspected or unconfirmed issues

- **Admin web:** no defect was reproduced. Lint, typecheck, 32 unit tests and build pass. The pages were not exercised in a browser against live data (UAT A-01 to A-10).
- **Stripe webhooks, refunds, FCM push, email and SMS:** the code paths have mocked tests. Live delivery is unverified (BLOCKED, see the final report).
