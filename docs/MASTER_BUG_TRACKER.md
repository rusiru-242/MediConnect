# MediConnect — Master Bug Tracker

Branch: `fix/comprehensive-system-ai-stabilization` · Baseline commit: `c3e0aac` · Last updated: 2026-11-25 (Phase 01 section added on `fix/phase-01-patient-ai-ui-stabilization`)

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
| Fix applied, PENDING MANUAL RETEST on a device | 4 (BUG-004, BUG-014, BUG-015, BUG-025) as of 2026-11-24; BUG-014/015 reopened and re-fixed 2026-11-25 together with BUG-042/043/045 (see the UAT UI blockers section) |
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
- **Status (2026-11-24):** PENDING MANUAL RETEST (not reproduced on a device; UAT P-14)
- **REOPENED 2026-11-25** by manual UAT (two or three composers, composer missing). **Root cause found on the emulator and FIXED:** see BUG-043. The earlier navigation guard was not the cause. **Status:** FIXED, PENDING MANUAL RETEST (UAT P-17)

### BUG-015 — `_owner != null` assertion when pressing Back in the AI Assistant
- **Severity:** High · **Component:** Flutter AI Assistant
- **Investigation:** Not reproduced in widget tests. Likely triggers: post-frame scroll callbacks and the hold-countdown `setState` running while the route is being torn down, focus still on the text field, and a duplicated route (BUG-014).
- **Fix:** On pop: unfocus, cancel the timer and invalidate pending uploads. Every post-frame scroll is now guarded (disposed, mounted, `hasClients`, `hasContentDimensions`). The timer `setState` is guarded. Plus the BUG-014 navigation guard. No assertions were suppressed.
- **Regression test:** `ai-ui` "pressing Back with a focused input and pending reply does not throw"
- **Status (2026-11-24):** PENDING MANUAL RETEST (UAT P-15)
- **REOPENED 2026-11-25** by manual UAT (red error screen on Back). **Root cause found on the emulator and FIXED:** see BUG-043. **Status:** FIXED, PENDING MANUAL RETEST (UAT P-17)

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

## UAT UI blockers (2026-11-25, branch `fix/uat-ai-assistant-ui-stabilization`)

Full analysis: [UAT_UI_STABILIZATION_REPORT.md](UAT_UI_STABILIZATION_REPORT.md). Test file `ai-ui2` = `mobile/test/screens/ai_assistant_ui_stabilization_test.dart`.

**BUG-014, BUG-015, BUG-042, BUG-043 and BUG-045 share one root cause (BUG-043).** It was reproduced on the Android emulator on the first opening of the assistant. A second layout defect, the composer pushed off-screen in landscape with the keyboard open, was found during emulator testing and fixed under BUG-014. **Emulator (2026-11-25):** 20/20 guarded cycles, 60 messages sent and answered, 0 framework exceptions (see the report §5).

| ID | Title | Severity | Confirmed root cause | Files | Regression tests | Status |
|---|---|---|---|---|---|---|
| BUG-043 | Flutter lifecycle and rendering assertions in the AI Assistant (`_owner != null`, `attached`, `!debugNeedsLayout`, `child._parent == this`, …) | Critical (blocks UAT) | **First exception:** `BoxConstraints forces an infinite width` at `ai_care_assistant_screen.dart:1041`. The app theme gives every `ElevatedButton` `minimumSize: Size(double.infinity, 52)`. The emergency banner put its 1990 `ElevatedButton` directly in a `Row`, so layout threw part-way through a frame. The screen was left with render objects that were never laid out ("RenderBox was not laid out"). Every later frame, keyboard change, rebuild or route removal then hit that inconsistent tree, which produced the listed assertions. Older tests did not use the app theme or an urgent session, so they could not see it. | `ai_care_assistant_screen.dart` | `ai-ui2` (14 tests; the original 10 fail without the fix), `ai_care_assistant_screen_test` #8 now under the app theme | FIXED; emulator verified (20/20 cycles, 0 exceptions); PENDING MANUAL RETEST (P-17) |
| BUG-042 | Emergency UI missing: no red banner, no 1990 button, routine booking chips still shown | Critical (patient safety) | (1) The banner was built but its layout threw (BUG-043), so it never painted. (2) The backend keeps `state = COLLECTING_PREFERENCES` during an emergency, so the routine quick-prompt chips (Find Doctor, Book Slot, …) stayed visible. The backend contract itself was correct (`isUrgent`, `urgencyReason`, `activeIntent: EMERGENCY_GUIDANCE`, metadata `type: emergency`, `ambulanceCall: 1990`). | `ai_care_assistant_screen.dart`, `utils/emergency_dialer.dart`, `MainActivity.kt`, `AndroidManifest.xml` | `ai-ui2` BUG-042 group (banner, dedicated action, chips hidden, normal reply, confirm/cancel, dialer failure, Sinhala) | FIXED; emulator verified for English, Romanized Sinhala (typed) and Sinhala script (sent through the API): banner, 1990, dedicated action, Cancel, dialer without a call. The banner language now follows the reply's script. PENDING MANUAL RETEST (P-01 re-run, P-17) |
| BUG-045 | Chat becomes laggy, then unresponsive | High | Consequence of BUG-043: in debug mode each failed layout logs a full error with stack traces, and the half-laid-out subtree is laid out again (and fails again) on later frames. No separate performance defect was found in code review. The hold-countdown timer rebuilds the whole screen once a second while a booking hold is active; this is minor and was left unchanged. | (as BUG-043) | (as BUG-043) | FIXED as a consequence; emulator: 20 identical sending cycles took 38.1–39.5 s, with no growth and 0 errors. A DevTools frame-timing profile was **not** captured. PENDING MANUAL RETEST |
| BUG-044 | Category-specific emergency guidance | Medium | Recorded by the owner for a later batch | — | — | OPEN (deferred, not in this batch) |
| BUG-047 | Composer pushed off-screen in landscape with the keyboard open (part of the "composer disappears" report) | High | Fixed-height disclaimer and emergency banner overflowed the about 64 px body by 106 px (`RenderFlex overflowed`) | `ai_care_assistant_screen.dart` (height-aware body) | `ai-ui2` landscape tests (fail without the fix: overflow by 141 px) | FIXED; emulator verified |
| BUG-048 | Emergency banner in English while the reply was Sinhala (Romanized Sinhala input) | Medium | Backend keeps `preferences.language = en` and an English `urgencyReason` | `ai_care_assistant_screen.dart` (language follows the reply's script) | `ai-ui2` Romanized Sinhala test | FIXED in app; emulator verified. Backend language memory recorded for BUG-004 / P-01f |
| BUG-046 | Home-screen **Emergency SOS** shows "Calling National Ambulance Service (1990)…" but never opens the dialer or places a call | High (patient safety: misleading) | `patient_home_screen.dart` only shows a SnackBar | `patient_home_screen.dart` | — | OPEN (found during this work; not changed because it is outside the AI Assistant scope. `EmergencyDialer` can be reused for the fix.) |

## Phase 01 — Patient AI, clinical safety and UI/UX (2026-11-25, branch `fix/phase-01-patient-ai-ui-stabilization`)

Details, reproduction steps and evidence: [uat/phase-01/PHASE_01_BUG_FIX_REPORT.md](uat/phase-01/PHASE_01_BUG_FIX_REPORT.md).

**ID reconciliation:**
- The owner reports a working count of 63. This tracker documents BUG-001 to BUG-048; descriptions for the remaining 15 are not in the repository and were **not invented**.
- Phase 01 items without an established ID use **provisional `P01-nn` IDs** (re-map if the owner's list differs).
- Status updates to existing IDs are added below; the history above is kept.

| ID | Title | Severity | Root cause (short) | Status |
|---|---|---|---|---|
| BUG-044 | Category-specific emergency guidance | Medium | One cardiac-style text for all categories | FIXED in Phase 01 (11 categories, en/si). Clinical review pending |
| BUG-046 | Home Emergency SOS did not dial; listed "911" | High | Snackbar only; wrong number | FIXED in Phase 01 (dialer with 1990, police 119); emulator-verified |
| P01-01 | Educational heart-attack/stroke questions raised an alarm (Assistant and Health Chat) | High | Narrow informational pattern; pronoun veto | FIXED; UAT-API + emulator verified |
| P01-02 | Hypothetical "if someone has chest pain" raised an alarm | Medium | No hypothetical handling | FIXED; clinical review of design pending |
| P01-03 | Overdose ("took 10 paracetamol tablets") not escalated | **Critical** | Poisoning patterns too narrow | FIXED; UAT-API + emulator verified |
| P01-04 | Self-harm shown with the generic cardiac-style alarm | High | Single emergency UI; no crisis type | FIXED (dedicated UI + crisisType); emulator verified |
| P01-05 | Unverified Sumithrayo number shown in crisis guidance | High | Hard-coded, no source | FIXED (removed; 1926/1333 verified) |
| P01-06 | Romanized Sinhala crisis phrases answered in English | Medium | Missing Singlish keywords | FIXED |
| P01-07 | 3-week cough listed under "Call 1990 now" | Medium | Single red-flag tier | FIXED (3 tiers); clinical review pending |
| P01-08 | Prevention question got "share your symptoms" | Low | No information handler | FIXED |
| P01-09 | Scenario A: context lost after an unsupported location | High | Preferences restored/reset | FIXED |
| P01-10 | Scenario B: "Increase my budget to LKR 3000" not parsed | High | Fee patterns | FIXED |
| P01-11 | Scenario C: selection returned 2 doctors / clarification | High | Exact-phrase cues; selection only in search turns | FIXED |
| P01-12 | Plural specialty ("cardiologists") not recognised | Medium | `(?:ist|y)\b` patterns | FIXED |
| P01-13 | Named-doctor slot request asked for the name again | Medium | Follow-up handler ran first; name regex | FIXED |
| P01-14 | Explicit year in a date ignored | Medium | Month-day pattern | FIXED |
| P01-15 | Date follow-up created a booking proposal | Medium | Any date + time became a booking | FIXED (Phase 02 should review booking semantics) |
| P01-16 | Recommendations showed a list instead of the top 1–2 | Requirement | — | IMPLEMENTED |
| P01-17 | Few-review ratings outranked established ratings | Improvement | Raw average ordering | IMPLEMENTED |
| P01-18 | LLM understanding never used for logged-in patients | Finding | Provider only called without a patient | IMPLEMENTED (bounded layer); live provider BLOCKED |
| P01-19 | Medicine information duplicated text and card | Medium | Text repeated card fields | FIXED |
| P01-20 | No child/pregnancy/liver/combination medicine notes | Improvement | — | IMPLEMENTED; pharmacist review pending |
| P01-21 | Keyboard UX requirements | Requirement | — | IMPLEMENTED; emulator verified |
| P01-22 | Long replies jumped to their end | Medium | Scroll to max extent | FIXED |
| P01-23 | Fabricated "Dr. Alexander Wright" video appointment | High | Hard-coded UI | FIXED; emulator verified |
| P01-24 | Fabricated vitals, "VITALS: NORMAL", "Synced 12m ago" | High | Hard-coded UI | FIXED; emulator verified |
| P01-25 | "Prescriptions" quick action opened medication reminders | Low | Label | FIXED |
| P01-26 | Unsupported video UI (default-video picker, fake filter, badges, Join Call) | Medium | Cosmetic UI | FIXED; emulator verified |

## Suspected or unconfirmed issues

- **Admin web:** no defect was reproduced. Lint, typecheck, 32 unit tests and build pass. The pages were not exercised in a browser against live data (UAT A-01 to A-10).
- **Stripe webhooks, refunds, FCM push, email and SMS:** the code paths have mocked tests. Live delivery is unverified (BLOCKED, see the final report).

## Phase 02 (2026-11-25, branch `fix/phase-02-booking-payment-patient-care`)

The owner's BUG-049 to BUG-063 descriptions are now recorded and mapped to the Phase 01 provisional IDs in [docs/uat/phase-02/PHASE_02_BUG_ID_RECONCILIATION.md](uat/phase-02/PHASE_02_BUG_ID_RECONCILIATION.md).

- **Fixed in Phase 02:**
  - Owner IDs: BUG-055, BUG-056 (completed), BUG-058, BUG-059, BUG-060, BUG-061, BUG-063.
  - New defects: P02-N01 to P02-N17, including the privacy defect P02-N10 and the payment and refund integrity defects P02-N02, N04 and N05.
- **Already fixed in Phase 01 (re-verified):** BUG-049 to 054, 057, 062.
- **Live verification:** Stripe test-mode refunds and payments were verified live. Real webhook delivery, FCM, email and SMS remain **BLOCKED**. See [docs/uat/phase-02/PHASE_02_FINAL_COMPLETION_REPORT.md](uat/phase-02/PHASE_02_FINAL_COMPLETION_REPORT.md).

## Phase 03 (2026-11-25, branch `fix/phase-03-doctor-system-stabilization`)

- **New defects fixed and verified:** P03-N01 to N17 and N21 to N24 (21 defects). The most serious:
  - P03-N01: consultation start confirmed unpaid bookings.
  - P03-N02, N11, N17: record access through released reservations, unsigned colleague drafts, and care plans on unpaid bookings.
  - P03-N06: invented 08:00/20:00 medication reminders.
  - P03-N09: AI note drafts with invented findings.
  - P03-N03, N04: doctor cancellation without a refund request, or with a payable Stripe intent.
  - P03-N16, N24: invented dashboard and doctor-card content.
  - P03-N22: the test suite could use the database in `backend/.env`.
- **Improvements (not defects):** P03-N18 (server-side care-plan progress), N19 (refund-aware doctor analytics), N20 (assistant date phrases).
- **Phase 02 blockers:** B11 (device re-run of E8 to E10) and B14 (doctor dashboard review) are closed.
- **Owner check needed:** a test run may have written test records to the remote database configured in `backend/.env` (P3-B1).
- **Details:** [docs/uat/phase-03/PHASE_03_BUG_FIX_REPORT.md](uat/phase-03/PHASE_03_BUG_FIX_REPORT.md) and [PHASE_03_FINAL_COMPLETION_REPORT.md](uat/phase-03/PHASE_03_FINAL_COMPLETION_REPORT.md).

## Phase 04 (2026-11-26, branch `fix/phase-04-admin-system-stabilization`)

- **New defects fixed and verified:** P04-N01 to N23 (23 defects). The most serious:
  - P04-N05: dashboard, analytics, assistant and reports counted refunds twice, ignored partial refunds, and showed an invented 10% "platform revenue".
  - P04-N01: the Phase 03 test-database guard could be bypassed by look-alike or multi-host URIs.
  - P04-N13: the worker heartbeat endpoint required no authentication.
  - P04-N11: reconciliation advised "confirm the booking immediately" for cancelled paid bookings.
  - P04-N09: a refund rejection could overwrite a concurrent approval.
  - P04-N15: push notifications were counted as delivered with FCM not configured.
  - P04-N20: security events and fraud assessments failed after the first insert (`_id: null`).
  - P04-N12/N16: the failed-payment rule and the failed-payment query never matched (lower case).
  - P04-N04: every payment was shown as test mode.
- **Closed blockers:** B15 (admin refund page), P3-B2 (null-fee crash), P3-B3 (doctor-initiated refund requests).
- **Corrected finding:** P3-B4. Admins cannot read patient clinical records, notes, measurements or prescriptions (verified by content). Care-plan content and booking notes remain owner decisions (P4-B4a/b).
- **Still urgent (owner):** P4-B1, the remote database incident, is unverified, and its possible impact is wider than first recorded (worker sweeps and SMTP).
- **Details:** [docs/uat/phase-04/PHASE_04_BUG_FIX_REPORT.md](uat/phase-04/PHASE_04_BUG_FIX_REPORT.md) and [PHASE_04_FINAL_COMPLETION_REPORT.md](uat/phase-04/PHASE_04_FINAL_COMPLETION_REPORT.md).

## Phase 05 (2026-11-26, branch `fix/phase-05-final-ai-security-integration`)

- **New defects fixed and verified:** P05-N01 to N07 and N09 to N26 (25 defects). The most serious:
  - P05-N01: the backend silently used the remote database when started without configuration (P4-B5).
  - P05-N02: two concurrent refreshes of one token created two sessions.
  - P05-N12: the Gemini key was sent in URLs.
  - P05-N18: one Care Agenda reading made the measurement list fail (B7).
  - P05-N20: concurrent care-plan updates lost an update.
  - P05-N17: duplicate blocked times.
  - P05-N22: B16, dose-change requests answered with a medicine lookup.
  - P05-N21: B17, Sinhala emergency follow-ups answered in English.
- **Historical items closed:** BUG-038 (shared rate limiting), P4-O1, P4-O3, P4-O4, P4-O7, P4-O8, B7, B8, B16, B17, P3-B7, P3-B8, P3-B11.
- **Critical owner item:** P5-C1. The live MongoDB credentials are in public git history (commit `a41b659`); rotate them.
- **Reconciled tracker for all phases:** [uat/MEDICONNECT_MASTER_BUG_TRACKER.md](uat/MEDICONNECT_MASTER_BUG_TRACKER.md). It lists 160 unique confirmed defects (159 fixed, 1 open: BUG-039).
- **Details:** [uat/phase-05/PHASE_05_BUG_FIX_REPORT.md](uat/phase-05/PHASE_05_BUG_FIX_REPORT.md).

## Agent Completion A01 (2026-11-26, branch `fix/agents-a01-ai-intelligence-vision`)

17 new defects (A01-N01 to N17), all fixed with automated tests. The most serious:
- **A01-N01:** a child swallowing a whole strip of tablets was not detected as an emergency.
- **A01-N09:** text a live model reconstructed from a blurry photo was presented as read.
- **A01-N06:** the test suite inherited the real provider keys and made live calls.
- **A01-N05:** the Health Assistant answered medicine, sleep, dose-change and injection messages with one generic paragraph.
- **A01-N10 / N11:** no secondary provider; retired or shutting-down model ids.

Reconciled index: [uat/MEDICONNECT_MASTER_BUG_TRACKER.md](uat/MEDICONNECT_MASTER_BUG_TRACKER.md) (177 confirmed defects: 176 fixed, 1 open, BUG-039). Details: [uat/agent-completion/a01/A01_BUG_FIX_REPORT.md](uat/agent-completion/a01/A01_BUG_FIX_REPORT.md).

## Agent Completion A02 (2026-11-26, branch `fix/agents-a02-reminders-notifications`)

21 new defects (A02-BUG-001 to 021), all fixed with automated tests or emulator evidence. The most serious:
- **A02-BUG-001:** SMTP TLS certificates were never verified.
- **A02-BUG-002:** the backend test suite submitted real e-mail through the SMTP account in `backend/.env` (13 attempts per local run).
- **A02-BUG-011:** patient-set reminders for as-needed medicines and an invented 7-day course.
- **A02-BUG-016/017/019/020:** device reminders never shown on Android 13+, endless after the course, and still firing after logout.
- **A02-BUG-005:** a worker crash before the in-app write lost the reminder.
- **A02-BUG-006:** push previews exposed names, dates and specialties on the lock screen.

Reconciled index: [uat/MEDICONNECT_MASTER_BUG_TRACKER.md](uat/MEDICONNECT_MASTER_BUG_TRACKER.md). Details: [uat/agent-completion/a02/A02_BUG_FIX_REPORT.md](uat/agent-completion/a02/A02_BUG_FIX_REPORT.md).

## Agent Completion A03 (2026-11-27, branch `fix/agents-a03-booking-payments`)

20 new defects (A03-BUG-001 to 020) in AI booking, Stripe payments, webhooks and refunds, all fixed with automated tests. Several were found only with real Stripe test-mode objects or on the emulator. The most serious:
- **A03-BUG-002:** every real `payment_intent.payment_failed` webhook returned 500. The stripe-python 16 objects are not dicts, and the old test mocked the event as a dict.
- **A03-BUG-006:** refund webhooks and the polling fallback never matched a real refund request (uppercase and lowercase status mismatch).
- **A03-BUG-007:** a lost refund response was marked failed with no Stripe id; a later re-approval could refund twice.
- **A03-BUG-005:** an expired hold's PaymentIntent stayed payable; three such test-mode intents were open in UAT.
- **A03-BUG-001:** in-progress or crashed webhook deliveries were acknowledged with 200, so Stripe stopped retrying.
- **A03-BUG-009:** a refund Stripe failed after success was invisible to administrators.
- **A03-BUG-010:** after "select the most experienced doctor", the agent proposed a different (cheaper) doctor for "this doctor".

Reconciled index: [uat/MEDICONNECT_MASTER_BUG_TRACKER.md](uat/MEDICONNECT_MASTER_BUG_TRACKER.md) (218 confirmed defects: 217 fixed, 1 open, BUG-039). Details: [uat/agent-completion/a03/A03_BUG_FIX_REPORT.md](uat/agent-completion/a03/A03_BUG_FIX_REPORT.md).
