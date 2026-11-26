# A01 — Remaining Blockers and Owner Actions

For: the project owner. 2026-11-26, branch `fix/agents-a01-ai-intelligence-vision`.

Engineering work for Agents 02, 04 and 32 is complete. What remains needs the owner, a reviewer, or an external service.

## Owner actions

| # | Action | Unblocks | Notes |
|---|---|---|---|
| 1 | **Rotate the MongoDB credentials (P5-C1)** and run the remote incident inspection (P4-B1) | Staging and anything beyond | Deferred by the owner. Still the top security blocker; A01 did not touch it. |
| 2 | Rotate the Gemini, OpenAI and SMTP keys (P4-B2) | Staging | The A01 live tests used the existing keys under authorization; rotation is still required. |
| 3 | **Add credits to the OpenAI account** (or decide not to use OpenAI) | A01-P04 OpenAI live text, OpenAI vision, a live secondary provider | Every OpenAI generation returns 429 `insufficient_quota`. I did not change billing. |
| 4 | Choose a **Gemini paid tier or quota** for any pilot | Reliable live AI | The free tier allows 20 generate requests/day on `gemini-3.8-flash` (used up during A01) and returned 503 "high demand" repeatedly. |
| 5 | Update `backend/.env`: `GEMINI_MODEL=gemini-3.8-flash` (or `gemini-3.5-flash-lite`), `OPENAI_MODEL=gpt-6-luna` | Removing the remap and shutdown warnings | `.env` still names `gemini-1.5-flash` (shut down) and `gpt-4o-mini` (shutdown 2027-01-14). The code remaps and reports them, so nothing breaks. |
| 6 | Data-processing agreement for sending patient medicine photos to an external vision provider (B13) | Agent 04 with real patients | Until then, keep `AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED=false` outside synthetic testing. |
| 7 | Provide non-patient photos of real packaging (own medicine boxes, no labels with names) if real-photo verification is wanted | Agent 04 beyond rendered fixtures | Only synthetic rendered images were used. |

## Human review gates (not engineering)

| Gate | Scope | Item |
|---|---|---|
| Clinical review | Symptom guides, danger signs, follow-up wording, emergency and crisis texts, the "prompt evaluation within 12–24 h" wording | B1 |
| Pharmacist review | Medicine library text, refusal wording, vision result wording, "do not repeat printed doses" rule | B2 |
| Native Sinhala review | Health Chat Sinhala replies, including LLM rewrites | B12 |
| Physical device | Health Chat and image flow on a real Android phone; camera capture is not implemented | B10 |

## Open observations from A01

- **A01-O1:** a foreign patient gets 403 (not 404) for another patient's conversation.
- **A01-O2:** the vision model sometimes lists absent fields as unreadable.
- **A01-O3:** "since yesterday" is not parsed as a duration.
- **A01-O4:** the free-tier quota is not suitable for any real use.

## Not done in A01 (and why)

- **Live OpenAI generation and vision:** no credits (action 3).
- **Live `gemini-3.8-flash` generation:** 503, then the daily quota; live evidence uses `gemini-3.5-flash-lite`.
- **Live tool-calling rounds (orchestrator, component 31):** outside A01's three targets. Covered by test doubles.
- **Admin web:** unchanged in A01; its suite was re-run (39 passed).

## Readiness

- **Academic demonstration and local UAT:** still ready. Agents 02 and 04 now also work with a live provider when one is configured.
- **Staging, clinical pilot, production:** not ready. Actions 1 and 2, the review gates, and the Phase 05 production gates remain.
- **Not claimed:** clinical approval and production readiness.
