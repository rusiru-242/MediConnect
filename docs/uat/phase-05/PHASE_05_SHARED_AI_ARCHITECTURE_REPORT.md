# Phase 05 — Shared AI Architecture Report

For: the project owner, reviewers and engineers continuing MediConnect. 2026-11-26. Branch `fix/phase-05-final-ai-security-integration`.

## 1. What "AI" means in MediConnect today

MediConnect has 38 named AI components. They are **not** 38 autonomous LLM agents. They fall into three groups:

| Group | Components | How they work |
|---|---|---|
| Deterministic services with assistant interfaces | Most patient, doctor and admin components (booking, reminders, analytics, refunds, monitoring, reports, triage) | Rules, database queries and validated tool calls. Every number, fee, date, clinical fact and financial total comes from the database. |
| LLM-assisted, bounded | Patient doctor search (provider tool calls over 3 public read-only tools), Phase 01 preference proposal, Phase 05 intent proposal for unclassified messages, health guidance text, medicine label vision | The LLM may *propose* a label, search preferences or tool calls. The server validates every proposal against a schema and runs only authorized read-only tools. |
| Not AI, deliberately | Payments, refunds, prescriptions, clinical notes, approvals, suspensions | Human-controlled backend workflows with explicit confirmation and audit. No AI path can trigger them. |

In UAT the providers are disabled (`GEMINI_API_KEY`/`OPENAI_API_KEY` blanked by the launcher), so the deterministic engine answers everything. LLM paths were exercised only with controlled test doubles in Phase 05; **no live provider call was made** (B13, owner authorization required).

## 2. Request flow (as implemented)

```
User request (Flutter / admin web)
  → JWT validation: signature, issuer, audience, type, jti, expiry; account status read from the database
  → Role dependency (require_patient / require_approved_doctor / require_admin)
  → Shared rate limit (MongoDB counters, per user)
  → Patient only: emergency triage FIRST (deterministic, multilingual, context-aware; B17 language memory)
  → Conversation context (owned by the user; ownership checked on every lookup)
  → Intent classification (app/agents/intent_router.py): role-specific schema, deterministic multilingual
      rules; optional LLM proposal restricted to the role's intent names; "ambiguous" asks the user
  → AIOrchestrator.execute(tool, args, allow-list)
      • tool must be in the allow-list AND allow the user's role, then AISafetyGuard re-checks
      • pydantic argument validation; per-tool timeout (5 s); MongoDB operation timeout (4 s)
      • max 8 tool calls per request; duplicate calls return the first result; loop detection
      • result must be a JSON object under 256 KB
      • tools marked `mutates=True` refuse to run without server-side confirmation
  → Grounded reply (formats tool results only; no invented figures)
  → Structured UI output (cards, metadata types)
  → Monitoring: ai_agent_runs (tool names, outcomes, durations; no content), provider usage metrics
```

## 3. Component 31 — Orchestrator (`app/agents/orchestrator.py`)

| Bound | Value | Test |
|---|---|---|
| Provider tool rounds | 3 (+1 final turn) | `test_phase1_orchestrator::test_round_limit…` (varied calls) |
| Calls per round | 4 | existing |
| Total tool calls per request | 8 → `tool_call_limit` | S-01g |
| Duplicate call (same tool, same canonical arguments) | first result returned, tool not re-run | S-01g |
| Repeated identical provider round | loop detected, stops | S-01h |
| Tool timeout | 5 s → `tool_timeout` | S-01h |
| Overall provider search timeout | 15 s | existing |
| Invalid arguments | `invalid_arguments`, tool not run | S-01e |
| Unknown / other-role tool | `tool_unavailable` | S-01f, S-01a–c |
| Mutating tool without confirmation | `confirmation_required` | `test_mutating_tool_requires_server_side_confirmation` |

Registry audit: 52 tools (24 admin, 15 doctor, 14 patient; one tool serves both patients and doctors); exactly one is state-changing (`prepare_renewal_request`, patient-only, now `mutates=True`). Every DOCTOR and ADMIN tool is read-only (asserted by `test_admin_and_doctor_tools_never_mutate`). The orchestrator never grants permissions: the allow-list is supplied by the server-side caller, and the role check uses the database account.

## 4. Component 32 — Provider management (`app/agents/provider_gateway.py`)

Every external LLM request (doctor-search tool calls, preference parser, intent proposal, health assistant, medicine vision) now goes through `send()`:

* credentials only in headers. **Defect fixed (P05-N12):** the Gemini parser and the health assistant sent the API key as a `?key=` URL parameter, where proxies and access logs can record it;
* daily request limit `AI_DAILY_REQUEST_LIMIT` (default 2000; 0 disables provider calls), counted atomically in MongoDB across processes;
* circuit breaker (3 consecutive failures, 60 s cool-down) — **defect fixed (P05-N13):** the monitoring counters and breaker existed but no call ever updated them;
* failure categories: `auth_failed`, `rate_limited`, `timeout`, `invalid_model`, `server_error`, `network`, `invalid_output`, `usage_limit`, `circuit_open`, `disabled`;
* one retry only for rate limits, 5xx and connection errors;
* durable per-day metrics (requests, successes, failures by category, fallbacks, latency, prompt/completion tokens, model id). No prompt, reply, patient identifier or key is stored;
* truthful status: `not_configured`, `disabled`, `configured_not_verified`, `available`, `rate_limited`, `degraded`, `unavailable`.

Models: identifiers are configuration (`GEMINI_MODEL`, `OPENAI_MODEL`). Retired Gemini ids are mapped in one place (`RETIRED_GEMINI_MODELS`) and the remap is reported in provider status. **Defect fixed (P05-N14):** the health assistant mapped model names *to* the retired `gemini-1.5-flash`. The default is Google's maintained alias `gemini-flash-latest` (the low-cost tier). Current model availability could not be verified: listing models needs the owner's provider credentials, which are pending rotation (P4-B2). No paid tier is selected automatically.

## 5. Component 33 — Intent classification (`app/agents/intent_router.py`)

* Role schemas: 11 admin intents, 9 doctor intents, 4 patient care intents (doctor search remains the Phase 01 parser).
* Languages: English, Sinhala script, Romanized Sinhala, basic Tamil keywords; language detection reported with each result.
* Paraphrases and multiple constraints (S-03e/f), role separation (S-03g), ambiguity (S-03h) — 31 parametrized cases plus API tests.
* LLM proposal (test double only): the provider receives the redacted text and the role's intent names; anything outside the schema is discarded; failures fall back.

Live effect (UAT probe, same prompts before and after, `evidence/intent-probe-*.json`):

| Role | Section 8 prompts answered with the right tool | Before | After |
|---|---|---|---|
| Patient (9) | next appointment, medicine times, medical tests, B16 dose change, searches | 5 | 9 |
| Doctor (7) | schedule, follow-ups, preparation, renewals, analytics | 5 | 6 (D-3 correctly asks for a checked-in patient) |
| Admin (9) | verifications, refunds, payments, notifications, fraud, health, Sinhala | 2 (+1 misrouted) | 9 |

The live probe also caught **P05-N19**: my new payment-total reply understated captured payments (it excluded fully refunded ones). Reconciled against MongoDB and fixed.

## 6. Component 34 — Emergency triage

Emergency detection still runs before every other patient route (asserted again in `test_emergency_still_wins_over_medication_intents`). **B17 fixed:** the language of an emergency conversation is stored, so "ok", "1990?" or Romanized Sinhala after a Sinhala emergency stay in Sinhala (reproduced before the fix: "ok" received the English text). S-04 tests cover chest pain, collapse, stroke signs, anaphylaxis, Sinhala, negation, educational questions, contextual follow-ups, self-harm (verified lines 1926 and 1333 only), overdose and unrelated follow-ups. The dialer always asks for confirmation and never places a call (Flutter widget tests). Clinical approval is still required (B1).

## 7. Component 35 — Conversation memory

Conversations are owned by the patient (`patientUserId` + `persistent` in every query); another account gets 404, a doctor 403. S-05 tests cover context after success, no results, unsupported location, date changes, New Chat, cross-account isolation, concurrent sessions and permission claims in earlier messages. **Defect fixed (P05-N15):** "in Colombo then" after an unsupported city kept the specialty but lost the city. Retention: saved chats are kept until the patient deletes them (unchanged); `CONVERSATION_RETENTION_DAYS` lets the owner choose a period (privacy decision).

## 8. Component 36 — Scheduler

Database-backed occurrences with deterministic ids, atomic claim with a lease, expired claims become `uncertain` (never blindly re-sent), Asia/Colombo dates. S-06 tests now include three real OS processes delivering each reminder exactly once, restart, crash after claim, cancellation, rescheduling and a Colombo day boundary run with a fixed clock. **Defect fixed (P05-N16):** the lease used the wall clock while expiry used the run clock. B16: "change my dose" never changes a schedule and explains that the prescriber decides.

## 9. Component 37 — Safety and permission guard

See `PHASE_05_SECURITY_AND_PRIVACY_REPORT.md`. AI-specific: tool authorization is separate from HTTP authorization (both checked); retrieved content and tool output never become instructions (provider sees only public doctor fields; the intent prompt says to ignore embedded instructions and its output is a label from a fixed list); state changes require backend confirmation.

## 10. Component 38 — Workflow monitoring and recovery

Measured, not assumed: `ai_agent_runs` (24-hour runs, runs with tool errors, outcome counts) in the platform snapshot; provider status from observed calls; scheduler states including `uncertain`; Stripe webhook events logged; pending refunds re-read from Stripe by the worker until webhooks can be delivered. Phase 04's monitoring integrity fixes are unchanged (no invented healthy states; unconfigured channels reported as such — re-verified live, S-08a).

## 11. What remains

| Item | Why it is not done |
|---|---|
| Live Gemini/OpenAI verification, vision on real image bytes | Requires owner authorization, rotated keys and cost approval (B13, P4-B2) |
| LLM-written replies for doctor/admin assistants | Deliberately not added: replies are templated from tool results so figures cannot drift |
| Native-speaker review of Sinhala/Tamil patterns and replies | B12 |
| Clinical review of triage rules and wording | B1 |
