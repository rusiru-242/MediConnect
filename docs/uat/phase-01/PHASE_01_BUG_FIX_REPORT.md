# Phase 01 — Bug Fix Report (Patient AI, Clinical Safety, Flutter UI/UX)

Branch `fix/phase-01-patient-ai-ui-stabilization` · baseline `cd3e5ee` · 2026-11-25

## How IDs were assigned

- **Existing IDs** (BUG-001 to BUG-048) come from [MASTER_BUG_TRACKER.md](../../MASTER_BUG_TRACKER.md) and are reused where a Phase 01 item matches one (BUG-014/015/042/043/044/045/046/047/048).
- The request says manual UAT expanded the working count to **63**. The repository only documents BUG-001 to BUG-048, so the descriptions of the other 15 working items **could not be established** and none were invented.
- Every Phase 01 observation without an established ID gets a **provisional ID `P01-nn`**. If the owner's list uses different IDs, re-map them.

**Evidence types used below:**
- **Unit:** pure function tests.
- **API-local:** FastAPI TestClient against a local MongoDB test database, deterministic AI provider.
- **UAT-API:** the probe against the running UAT backend on port 8001 (`mediconnect_uat`, synthetic data), saved as `api-probe-before.json` / `api-probe-after.json`.
- **Widget:** Flutter widget tests.
- **Emulator:** Android 17 emulator, debug build, UAT backend.

**Test files:**
- `b01` = `backend/tests/test_phase01_patient_ai.py`
- `f01` = `mobile/test/screens/phase01_patient_ui_test.dart`

---

## Emergency detection and clinical safety

### P01-01 — Educational questions raised an emergency alarm
- **Reproduction:** in a new chat, ask "What are the common symptoms of a heart attack?" or "What causes a stroke?" (AI Assistant **and** Health Chat).
- **Expected:** information, plus "if this is happening now, call 1990"; no alarm banner.
- **Actual (UAT-API, before):** AI Assistant `isUrgent: true`, type `emergency`, cardiac/stroke guidance. The Health Chat shares the same detector code path; its probe run was not a clean reproduction (asked after a chest-pain message in the same session), so the Health Chat fix is evidenced by a fresh-session API-local test.
- **Root cause:**
  - The `INFORMATIONAL` pattern only matched the exact form "what are the (signs|symptoms)", so "what are the **common** symptoms" and "what causes" did not match.
  - The personal-pronoun veto (`PERSONAL`) rejected any question containing "I" or "my".
- **Fix:** `emergency_detector.py`
  - Broad informational patterns: signs, symptoms, causes, risk factors, prevention, "is X dangerous", "what does X feel like".
  - A narrow `PERSONAL_EXPERIENCE` check ("I have / I'm having / my chest / my father… / right now") replaces the pronoun veto.
  - Suppressed questions now return their `category`. Both entry points answer them with `informational_message()` (type `emergency_information`, `conditionalEmergency: true`).
- **Safety constraints kept:**
  - Present-tense personal experience still escalates ("what are the symptoms of a heart attack, I have chest pain right now").
  - Context escalation still applies ("My chest is very tight" → "What are the symptoms of a heart attack?" stays an emergency).
- **Tests:** `b01::test_p01_informational_negated_historical_not_alarmed`, `test_p01_emergency_positive`, `test_p01_context_keeps_emergency_including_informational_follow_up`, `test_p01_informational_question_api_no_alarm`, `test_p01_health_chat_entry_point`; `f01` "informational heart-attack question shows no emergency banner".
- **Results:** PASS (unit, API-local, UAT-API, widget, emulator screenshot `informational-heart-attack-no-banner.png`).
- **Limitations:** deterministic patterns. New phrasings may need additions. Clinical review is required.

### P01-02 — Hypothetical question escalated
- **Reproduction:** "What should I do if someone has chest pain?"
- **Expected:** conditional first-aid information without an alarm.
- **Actual:** a full emergency alarm.
- **Root cause:** no hypothetical handling. The phrase "someone has" counted as a present-tense report.
- **Fix:** a `HYPOTHETICAL` pattern ("if someone / what if / in case / suppose"), suppressed only when there is no current or personal marker. "Someone" counts as present-tense only when not preceded by "if". "What if someone collapses **right now**" still escalates.
- **Tests:** `b01` parametrized cases. **Result:** PASS (unit, UAT-API).
- **Limitations:** a clinical reviewer should confirm that hypothetical questions should not show the banner.

### P01-03 — Overdose was not escalated (critical, new)
- **Reproduction:** "I accidentally took 10 paracetamol tablets"
- **Expected:** emergency (poisoning), 1990, "go even if you feel well".
- **Actual (UAT-API, before):** the ordinary paracetamol medicine card.
- **Root cause:** poisoning patterns only covered "took too many pills/tablets", "overdose" and "poison".
- **Fix:** quantity-based patterns ("took/swallowed/ate … 10+ / ten / many / a whole strip … tablets/pills/capsules"), accidental intake, and a child swallowing tablets or chemicals. "I took 2 paracetamol tablets for headache" does not escalate.
- **Tests:** `b01::test_p01_emergency_positive`, `test_p01_no_false_alarm`, `test_p01_overdose_api_escalates`.
- **Result:** PASS (unit, API-local, UAT-API, emulator `overdose-poisoning-escalation.png`).

### BUG-044 — Identical guidance for every emergency (existing ID, previously deferred)
- **Expected:** category-specific guidance.
- **Actual:** one cardiac-style text for all categories.
- **Fix:** `CATEGORY_GUIDANCE_EN/SI` for all 11 categories (cardiac, respiratory, stroke, unconscious, bleeding, seizure, anaphylaxis, poisoning, head, snakebite, plus a generic fallback). Each starts with 1990/ETU.
- **Tests:** `b01::test_p01_guidance_is_category_specific`, `test_p01_categories_do_not_share_identical_guidance`. **Result:** PASS.
- **Limitations:** first-aid wording and Sinhala translations are **PENDING CLINICAL REVIEW** and native-speaker review.

### P01-04 — Self-harm shown with the generic cardiac-style alarm
- **Reproduction:** "mata marenna hithenawa" / "I want to kill myself"
- **Expected:** a dedicated supportive mental-health experience.
- **Actual:** detected correctly, but shown with the red medical banner and a prominent 1990 button.
- **Root cause:** the app had a single emergency UI; the backend did not label the crisis type.
- **Fix:**
  - **Backend:** a new supportive text that is compassionate, asks "Are you safe right now?", advises contacting a trusted person, not being alone and moving away from means of harm, says it is an automated assistant, and gives verified lines. Metadata carries `crisisType: "mental_health"` and `supportLines` (Assistant and Health Chat).
  - **App:** a calm purple banner, "You don't have to face this alone", **1926** as the primary button, 1333, and "In danger now? Call 1990". Every number goes through the confirmation dialog.
- **Tests:** `b01::test_p01_self_harm_*`; `f01` mental-health group (UI, plus 1926/1333/1990 confirm and cancel).
- **Result:** PASS (unit, API-local, UAT-API, widget, emulator: banner, actions, 1926 dialog and dialer pre-filled with 1926, 0 calls).
- **Limitations:** content needs mental-health clinician review.

### P01-05 — Unverified hotline number in crisis guidance (new)
- **Actual:** the self-harm text showed "Sumithrayo 011 2 696 666".
- **Root cause:** a hard-coded number with no verified source. A web check on 2026-11-25 found other Sumithrayo numbers with limited hours (UNHCR, Find A Helpline) and no source for 011 2 696 666.
- **Fix:** removed. The text now uses **1926** (NIMH, 24 hours) and **1333** (CCCline, 24/7, toll free), both verified, plus **1990** (official 1990.lk).
- **Test:** `b01::test_p01_self_harm_response_is_supportive_and_verified` asserts the number is absent. **Result:** PASS.

### P01-06 — Romanized Sinhala crisis phrases answered in English (new)
- **Reproduction:** "mata marenna hithenawa", "thaththa sihiya nathi wuna"
- **Root cause:** none of these words were in the Romanized Sinhala keyword list.
- **Fix:** added distinctly Sinhala words to `SINGLISH_HEALTH_KEYWORDS`. English controls stay English.
- **Tests:** `b01::test_p01_romanized_crisis_language_detected`, `test_p01_english_not_misdetected`. **Result:** PASS.

### P01-07 — A cough lasting 3 weeks was listed under "Call 1990 now"
- **Reproduction:** "I have had a cough for three weeks"
- **Root cause:** a single red-flag tier.
- **Fix:** three tiers:
  - Self-care.
  - **See a doctor within a day or two:** a cough of 3 weeks or more, prolonged fever, night sweats or weight loss, wheezing, blood-streaked phlegm.
  - **Call 1990:** severe breathlessness, blue lips, chest pain, more than a streak of blood.
  
  Plus the explicit line "not an ambulance emergency on its own" (English and Sinhala).
- **Test:** `b01::test_p01_long_cough_is_doctor_soon_not_ambulance`. **Result:** PASS (unit, UAT-API). Clinical review pending.

### P01-08 — Prevention questions got "share your symptoms or city"
- **Reproduction:** "How can I prevent heart disease?"
- **Fix:** `clinical_intent.general_health_information()` covers heart disease, stroke, diabetes and high blood pressure.
- **Test:** `b01::test_p01_prevention_question_gets_information`. **Result:** PASS (unit, UAT-API).
- **Limitation:** Sinhala replies currently show the English tips with a Sinhala note.

### BUG-046 — Home "Emergency SOS" did not dial (existing ID, was OPEN)
- **Actual:**
  - A "Calling National Ambulance Service (1990)…" snackbar with no dialler.
  - The dialog listed "**General Emergency: 911 / 119**". 911 is not a Sri Lankan number, and 119 is the **police** emergency line (police.lk).
- **Fix:** the dialog's Call button opens the dialer with 1990 (`ACTION_DIAL`, never places a call). The text now reads "Police emergency: 119" and the 911 reference is removed, in all three languages.
- **Test:** `f01` "Emergency SOS opens the dialer with 1990 only after confirmation".
- **Result:** PASS (widget, emulator: dialer pre-filled with 1990, 0 calls).

## Conversation memory and recommendations

### P01-09 — Scenario A: context lost after an unsupported location
- **Reproduction:** "Find me a cardiologist in Antarctica with a consultation fee below LKR 100." → "Search in Colombo instead."
- **Actual (before):** clarification; specialty and budget empty.
- **Root cause:**
  1. The unsupported-location reply restored the *previous* preferences, discarding those parsed in that turn.
  2. Any message naming a city counted as a "fresh search" and wiped all preferences.
  3. A location-only message did not trigger a search.
- **Fix:**
  - The unsupported reply keeps specialty and budget (drops the city).
  - A city-only change refines an existing search.
  - A city plus a change cue ("search / instead / what about / try…") re-runs the search.
  - "What is the weather in Colombo?" is not treated as a search.
- **Tests:** `b01::test_p01_scenario_a_*`, `test_p01_unrelated_city_question_is_not_search`.
- **Result:** PASS (API-local; UAT-API: cardiology + LKR 100 kept, Colombo searched, correct "no match ≤ LKR 100").

### P01-10 — Scenario B: "Increase my budget to LKR 3000" not understood
- **Root cause:** the fee parser only knew "budget is/LKR N", not "budget **to**" or change verbs.
- **Fix:** new patterns for "increase/raise/change/set/lower … budget/limit/max fee … to N" and "budget to/of/at N".
- **Tests:** `b01::test_p01_budget_change_parsed`, `test_p01_scenario_b_*`. **Result:** PASS (unit, API-local, UAT-API: 1 cardiologist ≤ LKR 3000).

### P01-11 — Scenario C: selection returned two doctors / clarification
- **Reproduction:** dermatologist search → "Select the most experienced doctor from these two doctors and explain why…"
- **Actual (before):** two doctors. "Select only one doctor…" gave a clarification.
- **Root cause:**
  - Selection worked only through a short exact-phrase list.
  - It worked only inside a turn that was already a search. A selection message without new filters fell into "need more details", which also reset the preferences.
- **Fix:**
  - Semantically broader cues: "select/choose/pick the most|best|cheapest|top…", "which one should I choose", "only/just/exactly one", "single doctor". "Show all" is excluded.
  - Any selection request with an existing search context re-runs the stored search and selects exactly one.
  - The explanation now also lists the other eligible doctors on the ranking criterion and states it is not a clinical-quality judgement.
- **Tests:** `b01::test_p01_selection_requests_recognised`, `test_p01_not_selection`, `test_p01_scenario_c_selects_exactly_one` (3 phrasings).
- **Result:** PASS (unit, API-local, UAT-API, emulator `scenario-c-single-doctor-selected.png`).

### P01-12 — "Show me all cardiologists in Colombo" asked for clarification
- **Root cause:** specialty patterns used `(?:ist|y)\b`, so the plural "cardiologists" did not match. An explicit show/find request with a specialty was not treated as a search.
- **Fix:** plural forms are accepted for all 12 specialty patterns. Show/find/list plus a specialty is a search.
- **Tests:** `b01::test_p01_plural_specialty_parsed`, `test_p01_show_me_all_with_plural_specialty_searches`. **Result:** PASS.

### P01-13 — Named-doctor slot request asked for the name again
- **Reproduction:** "Show me all available appointment slots for Dr. UAT Neuro on November 26, 2026."
- **Root cause:**
  1. The slot follow-up handler (matching the word "slots") ran before the search, with no candidates, so it asked "Which doctor should I look up?".
  2. The name pattern ran on into "on November 26".
- **Fix:** a message naming a doctor who isn't already a candidate goes to the search. The name stops at "on/for/tomorrow/month names/digits".
- **Test:** `b01::test_p01_named_doctor_slots_request_searches`. **Result:** PASS (API-local, UAT-API: Dr. UAT Neuro with that date's slots).

### P01-14 — An explicit year in a date was ignored (new)
- **Actual:** "November 26, 2030" parsed as 2026-11-26.
- **Fix:** an explicit year is honoured; past dates return none.
- **Test:** within `test_p01_named_doctor_slots_request_searches`. **Result:** PASS.

### P01-15 — "What about tomorrow morning?" created a booking proposal (new)
- **Root cause:** any message with a date and time after a search was converted into a booking request.
- **Fix:** "what/how about…, instead, any slots, available" without a booking verb refines the search with the date.
- **Evidence:** UAT-API (type `doctor_options` with the date instead of `booking_proposal`). **Result:** PASS.
- **Limitation:** booking-flow semantics are Phase 02 territory.

### P01-16 — Recommendations returned a list instead of the top 1–2 (requirement)
- **Fix:**
  - Recommendation requests ("recommend / good / best / suitable…") show the **top 2** by default, with the ranking basis and "say show all".
  - All matches stay available, and "show all" shows every match.
  - Exactly one is shown when one is asked for.
  - Unverified doctors are never included (server-side verification filter).
- **Tests:** `b01::test_p01_recommendation_defaults_to_top_two_and_show_all`. **Result:** PASS (API-local, UAT-API: 2 of 3 dermatologists, then 3).

### P01-17 — Few-review ratings outranked established ratings (improvement)
- **Fix:** a Bayesian adjusted rating (prior 3.5, weight 3) for ordering only. Doctors with no reviews rank after reviewed doctors and never get an invented rating. The `minRating` hard constraint still uses the raw published average. Missing experience is reported as "not listed".
- **Test:** `b01::test_p01_small_review_count_does_not_outrank_established_rating`. **Result:** PASS.

### P01-18 — Bounded LLM understanding was never used for logged-in patients (finding)
- **Root cause:** `booking_agent` called the provider's `parse_request` only when there was **no** patient, so real patients always got the deterministic parser.
- **Fix:** a new `intent_proposal.py`, called only when the deterministic parser found nothing searchable and only after emergency, prescription and health-advice routing.
  - Input is redacted (email, phone, NIC, "my name is").
  - Output passes a strict Pydantic schema: supported specialty and city, fee 100–100000, rating 1–5, sort enum, future ISO date, extra fields forbidden. Invalid fields are dropped.
  - Proposals can only fill search preferences; there is no tool execution.
  - Failures and timeouts fall back to deterministic.
- **Tests:** `b01::test_p01_llm_*` (mocked providers). **Result:** PASS (mocked).
- **Live provider:** **BLOCKED.** No working Gemini/OpenAI key is configured in UAT (see blockers).

## Medicine and images

### P01-19 — Medicine information shown twice
- **Reproduction:** "What is paracetamol used for?"
- **Actual:** the text repeated the name ("Paracetamol (Paracetamol (Acetaminophen))"), the uses and the strengths, all shown again in the card.
- **Fix:** a concise introduction ("…also known as Acetaminophen — commonly used for… The card below lists…") plus the safety line. The details live only in the card.
- **Test:** `b01::test_p01_medicine_text_does_not_repeat_card`. **Result:** PASS (unit, UAT-API).

### P01-20 — No situation-specific medicine safety notes (improvement)
- **Fix:** notes for children, pregnancy and breastfeeding, liver or kidney disease or regular alcohol use, and combining medicines. No doses or drug-specific claims; pending pharmacist review.
- **Tests:** `b01::test_p01_medicine_situation_notes` (4). **Result:** PASS.

### Image pipeline (no new defect found)
- Added tests: a blurry image gives `unreadable`; a provider timeout gives `provider_unavailable`; "disabled by configuration" makes no network call; a PNG name with GIF content, an unsupported extension, a file over 5 MB and an empty file are rejected without a provider call.
- These complement the existing BUG-023/026 tests, which cover real bytes reaching the provider, non-medicine images, loose tablets and expired authentication.
- **Result:** PASS (stubbed). **Live Vision: BLOCKED** (external processing disabled by configuration; privacy approval needed).

## Flutter UI and UX

### BUG-014/015/043 regression check (existing IDs)
- **Re-verified** on the emulator with the Phase 01 build: dashboard, SOS, assistant, crisis flow, scenario C, overdose, appointments, Find Doctor.
- **Result:** 0 `EXCEPTION CAUGHT`, 0 overflow in the session log; one composer throughout.
- Prior evidence: [UAT_UI_STABILIZATION_REPORT.md](../../UAT_UI_STABILIZATION_REPORT.md) (20/20 sending cycles).

### P01-21 — Keyboard behaviour (requirement)
- **Fix:**
  - A composer `FocusNode` owned and disposed by the screen.
  - Sending dismisses the keyboard.
  - Tapping outside dismisses it (`onTapOutside`); dragging the list dismisses it.
  - A reply never requests focus.
  - If the user refocuses while a reply is pending, focus and the draft are kept.
  - The attach, field and send controls share one `TapRegion` group, so taps on them are not "outside".
- **Tests:** `f01` keyboard group (5 tests, including rapid repeated taps sending one request).
- **Result:** PASS (widget; emulator: `mInputShown` true → false after send and after tapping the conversation).
- **Note:** during emulator testing I first misattributed a missed send to the tap-outside handler. The real cause was my test script tapping a stale coordinate while the emulator keyboard was in floating mode. The tap-group change was kept as hardening and has its own regression test.

### P01-22 — Long replies jumped to their end
- **Fix:** the newest reply's bubble scrolls itself into view top-first once (`Scrollable.ensureVisible`, own context, no GlobalKey, mounted-guarded). It is skipped if the user has scrolled up to read history.
- **Test:** `f01` "a long reply is shown from its beginning". **Result:** PASS (widget, emulator screenshots).

### P01-23 — Fabricated "Dr. Alexander Wright" video appointment on the dashboard
- **Fix:** `UpcomingAppointmentCard` loads the patient's real appointments and shows the next confirmed or pending one as an in-person visit. Otherwise it shows a truthful empty state with Find a Doctor, or an error state.
- **Tests:** `f01` dashboard group (empty, real, error). **Result:** PASS (widget; emulator shows the real UAT booking).

### P01-24 — Fabricated vitals on the dashboard
- **Actual:** "VITALS: NORMAL" badge, invented readings, "Synced 12m ago".
- **Fix:** removed. A Health Tracking card links to the real records with no values.
- **Tests:** `f01` (asserts absence); localization test updated. **Result:** PASS (widget, emulator).

### P01-25 — "Prescriptions" quick action opened medication reminders
- **Fix:** renamed "Medicine Reminders" (si/ta translated). Medical Records → "Prescriptions & PDFs" is unchanged.
- **Result:** PASS (widget, emulator).

### P01-26 — Unsupported video channelling UI
- **Actual:**
  - A cosmetic video/in-person picker on booking confirmation that **defaulted to video** and was never sent.
  - A "Video Visit" filter in Find Doctor that filtered nothing.
  - A camera icon that only opened the profile.
  - A "Video Visit" badge on every appointment.
  - A "Join Call" button that showed a snackbar.
- **Fix:**
  - Picker replaced by an "In-person consultation" note; the fake filter removed.
  - The camera icon became "View profile".
  - The badge now reads "In-person visit"; Join Call removed.
  - In-person flows (View Details, booking) are unchanged.
- **Result:** PASS (analyze, full Flutter suite, emulator UI scan found no video text).

## Localization test change (not a defect)

`test/localization/localization_test.dart` asserted the fabricated "Reschedule", "Today's Vitals" and "Heart Rate" content. It now asserts the truthful Health Tracking and Medicine Reminders sections in English, Sinhala and Tamil.
