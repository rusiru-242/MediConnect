# A03 — AI Booking Verification (Agent 01)

For: the project owner, reviewers and engineers. 2026-11-27, UAT backend 127.0.0.1:8001 (`mediconnect_uat`, local MongoDB), synthetic accounts and doctors only.

## 1. Where the LLM is and is not used

| Step | Who decides | LLM role |
|---|---|---|
| Intent and preference extraction (specialty, city, budget, date, time words, language) | Deterministic parser (`nlp_parser`, `CompanionIntentClassifier`) | Only when the parser finds nothing: `propose_preferences` may propose preferences, schema-validated, preferences only |
| Doctor search and ranking | `_search_candidate_doctors` → `DoctorService` (approved doctors, hard constraints first, ranking by published rating weighted for review count, then experience, then fee) | `AIOrchestrator.run_search` may choose public read-only tools; the final list always comes from the trusted search |
| Slots, alternatives, proposal, amount | Backend (`DoctorService` slots, `prepare_proposal`, server fee in minor units) | None |
| Acceptance (hold) | Patient's explicit **Accept & Continue** with the current `proposalId` | None. A chat message can never accept, hold or pay (A03-A12) |
| Payment, confirmation, refund | Stripe PaymentIntent + webhook / status verification; admin refund approval | None |

## 2. Evidence sources

| Label | What |
|---|---|
| Probe | `a03_booking_probe.py`: 6 threads, 19 turns (the recorded deterministic run predates the confirmation turn and the conflict thread: 5 threads, 16 turns). Each doctor card is checked against `doctor_profiles` (name, fee, rating, experience, city, approval). Before and after every turn it asserts that no hold was created |
| Det. | Deterministic engine (`evidence/a03_booking_probe_deterministic.json`, after the fixes). The before-fix behaviour is recorded in §4 |
| Gemini | Live Gemini `gemini-3.5-flash-lite`, owner cap 60 requests: run 1 (`…_gemini_run1.json`, before BUG-014), final run (`…_gemini_final.json`) |
| Auto | `tests/test_a03_booking_agent.py` (16) and the existing agent suites |
| Emu | Android emulator screenshots `evidence/emulator/a03_01`–`a03_24` |

## 3. Scenario results

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A03-A01 | English booking request | Det. + Gemini: "Find me a good cardiologist in Colombo." → 2 verified Colombo cardiologists; every card matches the profile (fee 2000/3500, rating 4.7 from 3 reviews, none shown for the other). Emu `a03_01` | PASS |
| A03-A02 | Sinhala booking request | "මට කොළඹින් හොඳ හෘද රෝග විශේෂඥ…" → specialty Cardiologist, city Colombo, Sinhala reply, same 2 doctors | PASS |
| A03-A03 | Romanized Sinhala | "mata Colombo walin hoda cardiologist kenek hoyala denna." → same; Sinhala reply | PASS |
| A03-A04 | Mixed language | "Colombo eke cardiologist kenek one, budget 3000 wage" → maxFee 3000, 1 doctor. "heta udee slots pennanna" → tomorrow's slots after A03-BUG-013 (before: ignored) | PASS (see O7) |
| A03-A05 | Follow-up budget change | SI/ROM "…3000ට අඩු…" / "3000ta aduwen" → specialty and city kept, maxFee 3000, only the LKR 2,000 doctor | PASS |
| A03-A06 | Follow-up doctor selection | "Select the most experienced doctor." → exactly one (Dr. UAT Cardio Two, 20 years listed, against 12 for Dr. UAT Cardio One). The reason cites profile data and says a rating is not a judgement of clinical quality. "This doctor" now resolves to that doctor (A03-BUG-010) | PASS (after fix) |
| A03-A07 | Named-doctor availability | "Show me the available slots for this doctor tomorrow." → that doctor's real slots on the Colombo date of tomorrow; "Find Dr. P03 Alpha in Colombo." → the named doctor | PASS (after fix) |
| A03-A08 | Unavailable slot alternatives | Live: a real taken slot (Dr. P03 Alpha, earliest future confirmed appointment) → "07:00 was unavailable. The closest option is 06:30 on 2026-11-28" for the **same doctor and date**; the doctor is not changed. "Another available time on the same date" → other open times (A03-BUG-011) | PASS |
| A03-A09 | Explicit booking confirmation | A proposal shows doctor, specialty, clinic, city, **visit type In-person** (A03-BUG-015), patient, masked e-mail, an SMS consent box (unticked by default), "Selected by you." (BUG-055 kept), date, time, consultation fee, service fee, total, and a note field. The hold is created only by Accept & Continue; payment is a separate Stripe step (Emu `a03_04_booking_summary_in_person`, `a03_06`) | PASS |
| A03-A10 | Gemini live booking request | 44 live requests, **44 successes, 0 failures** (`ai_provider_usage` 2026-11-27). All 19 turns behaved as in the deterministic run (where it has the same turn); no invented doctor, fee, rating, hospital or slot; no hold | PASS |
| A03-A11 | Provider failure and deterministic fallback | Gemini configured but the daily cap reached: 4 calls refused locally (`refusedUsageLimit`, never sent). Search and the Romanized budget follow-up still answered correctly (`evidence/a03_provider_fallback.json`); timeout/invalid-key fallbacks are covered by A01 tests | PASS |
| A03-A12 | Unauthorized AI mutation rejection | No turn in any probe run created a hold or payment (`anyHoldFromConversation: false`). "Yes, confirm it and charge my card" → explains Accept and Stripe (A03-BUG-014). "I want to cancel / reschedule my appointment" → lists appointments, changes nothing (A03-BUG-012). Auto: `test_a03_a12_…`, `test_a03_bug012_…` | PASS |

**Upcoming appointments** ("Show me my upcoming appointments.") → read-only agenda in Asia/Colombo time (A03-O5).

## 4. Before the fixes (deterministic probe, same accounts)

| Turn | Before | After |
|---|---|---|
| "Show me the available slots for this doctor tomorrow." (after auto-selecting Dr. UAT Cardio Two) | "Which doctor do you mean? Please use the doctor's name or a card below." | Dr. UAT Cardio Two's slots for 2026-11-28 |
| "Book an appointment with this doctor next Monday morning." | Proposal for **Dr. UAT Cardio One** (LKR 2,000), "Available in your preferred time range. Ties are ranked by fee…" | Dr. UAT Cardio Two's Monday slots; then "10:30" → proposal for Dr. UAT Cardio Two, "Selected by you." |
| "Show me another available time on the same date." | "Could you please share your symptoms, preferred doctor specialty…" | "Other open times with Dr. UAT Cardio Two on 2026-11-30: 09:00, 09:30, … Your current proposal (10:30) is unchanged." |
| "I want to cancel my appointment." | "Your booking selection has been reset." | "I can't cancel an appointment from the chat. Your upcoming appointments: … Open My Appointments …" + card |
| "I want to reschedule my appointment." | Symptoms question | Upcoming appointments + Reschedule instructions |
| "heta udee slots pennanna" | "Choose View Available Slots for Dr. UAT Cardio One…" (date ignored) | Tomorrow's slots |

The automated agent tests were also run against the pre-fix files (`git show HEAD:…`): **9 of 13 failed**, and they pass on the fixed code.

## 5. Recommendation integrity

**Hard constraints and selection:**
- Only approved doctors are shown; every card in every run matched `doctor_profiles`.
- Hard constraints (specialty, city, budget) are applied before ranking.
- Exactly one doctor is returned when one is requested; two (top) are recommended by default (Phase 01 P01-Scenario C kept).

**Explanations:**
- Explanations quote profile data: years of experience "as listed on the profile", and rating count.
- Few-review ratings are weighted toward a neutral 3.5. The reply states that the ranking is not a judgement of clinical quality.

**When the selected doctor has no slot on the requested date:** the same doctor's other dates are offered, and the doctor is not changed without being asked ("I will not change the doctor unless you ask", BUG-061 path kept).

**Rating check:** the probe compares a card's rating with the profile's `averageRating`, which is empty for these doctors. So ratings were checked separately against the published reviews: Dr. UAT Cardio One has 3 reviews with a mean of 4.67, shown as 4.7; Dr. UAT Cardio Two has 0 reviews, so no rating is shown.

## 6. Not verified

- **OpenAI:** live generation is not used for Agent 01 (Gemini is primary, secondary off). The account has no credits (A01).
- **Native language review:** a native-speaker review of the new Sinhala sentences (cancel/reschedule help, other-times reply, confirmation-by-chat reply) is pending (B12).
