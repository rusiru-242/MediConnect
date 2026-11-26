# A01 — Bug Fix Report

For: the project owner and the engineers maintaining Agents 02, 04 and 32. Branch `fix/agents-a01-ai-intelligence-vision`.

IDs are new and collision-free (A01-N01 to A01-N17). Each defect was reproduced first:
- with a live UAT probe on 127.0.0.1:8001 (`mediconnect_uat`),
- with a live provider call (owner-authorized, synthetic data), or
- with a failing test.

Each fix has an automated test. "Live" in the *Found by* column means the defect only showed up against a real provider.

## Defects

| ID | Severity | Component | Defect (before) | Root cause | Fix | Test | Found by |
|---|---|---|---|---|---|---|---|
| A01-N01 | **Critical (safety)** | Emergency triage (02, shared) | "My child swallowed a whole strip of my blood pressure tablets." was not detected as an emergency. The Health Chat returned the generic wellness paragraph. | The child-ingestion pattern allowed at most two words between "swallowed" and "tablets", and the medicine name made it six. | Wider child pattern. New patterns: "took/swallowed … whole/full strip/bottle/pack", "took all of my … tablets", Romanized and Sinhala variants. | `test_h13_emergencies_detected[poisoning]` | Live baseline probe H13e |
| A01-N02 | High | Provider gateway (32) | OpenAI `429 insufficient_quota` (no credits) was classified as `rate_limited`, retried, and shown as "rate_limited". | Every 429 was treated as transient. | New `quota_exhausted` category: not retried, status `unavailable`. | `test_p06_p07_p09_…[429-quota]`, `test_p13_…` | Live (OpenAI, 2026-11-26) |
| A01-N03 | High | Provider monitoring (32) | A 200 response whose JSON was unusable still counted as a success, so monitoring could show "available" while every answer was discarded. | Success was recorded at HTTP level before validation. | `record_output_rejected` turns it into a failure (`failure_invalid_output`, `outputRejected`) and feeds the circuit breaker. | `test_p10_…` (6 cases), `test_p15_…` | Code review + test |
| A01-N04 | Medium | Provider gateway (32) | The single retry happened immediately; `Retry-After` was ignored. | No back-off. | Bounded back-off (0.5 s, `Retry-After` honoured up to 2 s). | `test_p09_retry_after_is_honoured_but_capped` | Code review |
| A01-N05 | **High** | Health Assistant (02) | With no working provider, 11 of 26 probe messages got the same paragraph ("Balanced nutrition, adequate hydration…"): paracetamol, sleep, exercise, dose change, the injection attempt and others. "Prescribe me an antibiotic" got self-care advice instead of a refusal. | The deterministic path had three fixed templates and did not use the clinical, wellness or medicine knowledge the companion already had. | New `health_guidance.compose`: B16 dose-change rule, prescription refusal, medicine library, prevention, symptom advice with follow-up context, wellness tips, clarification. | `test_h01`–`test_h20` (API level) | Live baseline probe |
| A01-N06 | High (cost/privacy) | Test suite (32) | The suite inherited the real `GEMINI_API_KEY`/`OPENAI_API_KEY` from `backend/.env`, so tests that did not patch the network made **live provider calls**. Phase 05's comment said the opposite. | `load_dotenv()` filled the keys; conftest blanked only the JWT secret. | conftest sets both keys to empty (wins over `.env`). An autouse guard blocks any transport-level request to the provider hosts. | `test_live_requests_are_blocked_in_the_test_suite`; whole suite run with the guard | Usage metrics in `mediconnect_test` |
| A01-N07 | Medium | Provider gateway (32) | Gemini's free-tier **daily** quota 429 ("requests per day … retry in 21h") was retried as a per-minute rate limit. | Not distinguished from a per-minute limit; the classifier read only the first 400 characters and the detail is further in. | "Per day" quota → `quota_exhausted`, no retry; the classifier reads 4,000 characters. | `test_p06_p07_p09_…[429-RESOURCE_EXHAUSTED]` (live message structure) | **Live** (P13 row) |
| A01-N08 | Medium | Image upload (04) | Both image routes read the whole upload into memory before the 5 MB check. | `await file.read()` without a limit. | `file.read(MAX + 1)`. | `test_v10_oversized_file_rejected…` | Code review |
| A01-N09 | **High (safety)** | Medicine vision (04) | For the blurred fixture the live model returned exact label text ("Synthopar 500", "Paracetamol 500 mg", the storage line) while itself rating the photo `blurry`. That text was presented as read. | The pipeline trusted `readable=true` from the model. | A photo the model rates `blurry` or `dark` is never presented as read (asks for a clearer photo). The prompt forbids reconstructing text. | `test_v04_live_regression_…` + live re-test | **Live** (V04) |
| A01-N10 | High | Provider architecture (32) | No secondary provider anywhere: the Health Assistant called only Gemini, vision and the doctor-search parser never fell back to the other provider, and the provider order was not configurable. | Each feature talked to one provider directly. | `llm_client.generate_json` with `AI_PRIMARY_PROVIDER`/`AI_SECONDARY_PROVIDER`. `ChainedAIProvider` for parsing, intents and tool calling (which stays on one provider per run). | `test_p11_p12_…`, `test_p14_doctor_search_parser_chain…`, `test_tool_calling_sticks…`, live P11/P12 | Code review, then live |
| A01-N11 | High | Model selection (32) | `backend/.env` names `gemini-1.5-flash` (live: **404**, shut down). Phase 05 remapped it to the alias `gemini-flash-latest`, whose target is no longer documented. The OpenAI default `gpt-4o-mini` has an announced shutdown (2027-01-14), which was not reported. | Stale identifiers. | Defaults pinned to `gemini-3.8-flash` and `gpt-6-luna` (official pages, plus zero-token model lookups). Retired ids remapped and reported. `modelShutdownDate` in provider status. | `test_p01_p02_configuration_…` | Official docs + live lookups |
| A01-N12 | High | Health Assistant (02) | Provider output was accepted after `json.loads` with no schema, language check or grounding check. | No validation layer. | pydantic `HealthReply`. A rewrite is rejected if it drops a 1990/ETU instruction, adds numbers, contains dose-like text, lowers triage, or is in the wrong language. Authoritative answers are never sent to a provider. | `test_unsafe_or_off_language_rewrites_are_rejected` (4), `test_safety_answers_never_reach_the_provider` (4) | Code review |
| A01-N13 | Medium | Vision UI (04) | The image card repeated the field list already in the chat reply ("Detected Packaging Text"), and showed a "High Confidence" badge that the backend never supports. | UI and backend drifted. | The card shows the status badge, library match, unreadable fields, ignored-text notice and who read it. No confidence claim. | Flutter tests 11 (changed expectation, explained) and 12 (new) | Code review |
| A01-N14 | Medium (safety) | Medicine vision (04) | A photo with two packages was matched to one library card (the first name found). | Names were joined before the library lookup. | `package_count > 1` → status `multiple_packages`, no card, ask for one package at a time. | `test_v08_…` + live V08 | Code review, then live |
| A01-N15 | Medium | Health Assistant (02) | A 3-day headache was referred to a Neurologist and a cold to an ENT specialist. | The legacy keyword map overrode the clinical guide's first contact. | The guide's specialty (usually GP) wins; the map is used only for symptoms without a guide. | `test_h01_…` (General Practitioner), `test_h05_…` | Live baseline probe |
| A01-N16 | Medium | Shared NLU (02) | "mata dawas thunak thisse …" and "දවස් තුනක්" (three days) were not understood as durations. | Only digits and English number words were parsed. | Romanized and Sinhala number words. | `test_h02_h03_…` ("දින 3") | Live baseline probe |
| A01-N17 | Medium | Shared NLU (02) | "How many paracetamol tablets can I take at once…? Give me an exact number." was not recognised as a dose request (generic answer). | Only "how many … should I" matched. | Pattern for "how many/much … tablets/mg … can/should/may I", plus "maximum dose". | `test_h10_…` | Live baseline probe |

### Found during A01 development and fixed before commit (not baseline defects)

| Finding | Fix |
|---|---|
| Live: a provider attached "General Practitioner" to a sleep-hygiene answer. | A provider may refine a specialty only when the grounded answer already recommends one (`test_provider_cannot_add_a_specialty_to_a_wellness_answer`). |
| Live: the Sinhala-script rewrite timed out at 12 s and fell back correctly. | Sinhala budget raised to 20 s per attempt. Live re-test: rewritten. |
| Gemini answers an invalid key with **400** `API_KEY_INVALID`. | Classified `auth_failed` (live P06 confirms). |
| The prompt-care lead sentence ("prompt medical evaluation within 12–24 hours") was missing from the new composer; caught by the existing `test_prompt_care_escalation`. | Restored. That test was **not** changed. |

## Improvements (not defects)

- **Provider layer:**
  - JSON-schema structured output on both adapters (`responseJsonSchema` / `json_schema strict`).
  - Reasoning-model parameters for OpenAI (no custom temperature, `reasoning_effort`).
  - Gemini thinking budget.
  - Provider status now reports `role`, `visionModel`, `liveVerified` and `outputRejected`.
- **Vision:**
  - Brand and generic names are separated.
  - Also extracted: manufacturer, printed storage directions, and fields that could not be read.
  - Printed dosing directions are detected and *not repeated*.
  - Text in the image that addresses the assistant is ignored and flagged.
- **Health Assistant:**
  - Each reply records `responseSource`, `provider`, `model`, `answerKind` and `providerFallbackReason`.
  - A repeated identical question gets a short pointer instead of the same long answer.
  - Wellness answers show the actual tips (they were a one-line header).
- **UAT launcher:** `-AiProvider both`, `-EnableVision`, `-AiDailyLimit`, `-GeminiModel`. `.env.example` documents the new settings.

## Changed test expectations (explained)

| Test | Change | Why it is not weakening a valid expectation |
|---|---|---|
| `test_phase05_ai_architecture::test_s02a…` | Retired Gemini id now maps to `gemini-3.8-flash` (was `gemini-flash-latest`). | The alias target is no longer documented. The pinned id is the documented stable model, confirmed with a live lookup. The test still checks that the remap happens and the key stays out of the URL. |
| `test_comprehensive_stabilization::test_bug023_retired_model_names_are_mapped` | Same change. | Same reason. The medicine agent now uses the shared resolver instead of its own copy. |
| Flutter `ai_care_assistant_screen_test` #11 | Expects **no** "High Confidence" badge, and expects the reply text not to be repeated on the card. | The backend never produces "high", and a photo reading cannot establish a medicine's identity. Showing that claim was itself A01-N13. |

Two existing tests failed against my first draft and were kept unchanged, with the code fixed instead:
- `test_bug023_reads_actual_label_fields`
- `test_02_known_medicine_label_image`

## Observations (not fixed)

- **O1:** A foreign patient gets **403** (not 404) for another patient's conversation. Access is denied either way, but a 403 confirms the conversation exists.
- **O2:** Live V17: the model listed fields that are simply absent (expiry, manufacturer) as "not readable". The prompt was tightened; not re-tested live, to stay within the cap.
- **O3:** "since yesterday" is not parsed as a duration (H04). The answer is still correct guidance, just without the duration phrase.
- **O4:** The Gemini free tier allows 20 generation requests per day for `gemini-3.8-flash`; that quota ran out during A01. Any pilot needs a paid tier or a higher quota (owner decision).
