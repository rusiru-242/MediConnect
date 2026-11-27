# A04 — Remaining Blockers, Owner Actions and Decisions

For: the project owner. 2026-11-27, after Agent Completion A04 (Agent 17, AI Prescription Assistant). Every unresolved earlier blocker is carried forward; nothing is marked resolved without evidence.

## Owner actions (in priority order)

| # | Action | Unblocks | Notes |
|---|---|---|---|
| 1 | **Rotate the MongoDB credentials (P5-C1)** and run the remote incident inspection (P4-B1) | Staging and anything beyond | Still the top security blocker. A04 did not connect to the remote cluster or touch credentials |
| 2 | Rotate the SMTP, Gemini, OpenAI and Stripe test credentials (P4-B2); check the SMTP Sent and bounce folders (A02 2a) | Staging | Unchanged |
| 3 | **Pharmacist review (B2)** of prescription content, wording and the allergy-check behaviour | Agent 17 sign-off | See `A04_CLINICAL_SAFETY_REPORT.md` |
| 4 | **Clinical validation (B1)** of Agent 17 | Agent 17 sign-off | Includes the decision on renewal supersession (A04-O3) |
| 5 | **Drug-interaction source decision (P3-B9)** | Interaction checking | Unavailable and stated as such. A validated source needs a licence decision; none was integrated |
| 6 | Stripe webhook endpoint for staging (A03 action 3) | Agent 01 staging | Unchanged |
| 7 | Refund and cancellation policy confirmation (B6) | Agent 01 policy sign-off | Unchanged |
| 8 | Physical Android phone test (B10) | Device sign-off | Now also covers the A04 prescription screens |
| 9 | Native Sinhala and Tamil review (B12) | Language sign-off | Plus the new prescription replies, which are English only (A04-O4) |
| 10 | Firebase, iOS/APNs, e-mail sandbox, SMS provider (A02 actions 3–6) | External delivery | Unchanged. Prescription and renewal notifications are verified in-app only |
| 11 | OpenAI credits; Gemini paid tier for any pilot | AI providers | Unchanged. Agent 17 does not call a provider |
| 12 | Product decisions: reminder pickers' starting times (A04-O1); API route default (A04-O2) | — | Optional |

## Human review gates

| Gate | Item |
|---|---|
| Clinical review | B1, now including Agent 17 |
| Pharmacist review | B2, now including Agent 17 |
| Physical device | B10 |
| Native Sinhala/Tamil review | B12 |

## A03 webhook figures (clarified from A03 evidence)

The A03 summary said 5 events were lost during the deliberate outage and resent, while `A03_RESULTS.json` says 3 were resent. The CLI log `a03/evidence/stripe_cli_listen_redacted.log` settles it:

| Count | Value |
|---|---|
| Forwarded deliveries | 51 = 48 distinct events + 3 resends |
| HTTP 200 | 46 |
| Non-2xx | 0 |
| Refused while the backend was stopped | 5 |
| Resent after the restart | 3 (`refund.updated`, `refund.failed`, `payment_intent.succeeded`), each then HTTP 200 |
| Never redelivered | 2 `charge.refund.updated` |

Both unresent events belonged to the same test refund. That refund reached its final state through the resent `refund.updated` and `refund.failed`, so no stored state was lost, but strictly 2 events were not redelivered. **The JSON figure (3) is correct; the wording "5 … resent" overstated it.** The A03 reports were not rewritten. This correction is recorded here and in the master tracker (A04-O8).

## Open observations

| Item | Status |
|---|---|
| A04-O1 to A04-O8 | In `A04_BUG_FIX_REPORT.md` |
| A03-O1 to O7, A02-O1 to O3 and O5, A01-O1 to O4 | Unchanged |

## Not done in A04 (and why)

| Item | Why |
|---|---|
| Live Gemini or OpenAI tests | The prescription paths do not call a provider; no A04 authorization was requested |
| External delivery of prescription notifications (push, e-mail, SMS) | Providers disabled in UAT; external delivery remains a separate blocker |
| Doctor rejection and a reminder on a renewed prescription, on the device | Covered by API and automated tests only |
| Physical phone | Gate B10 |
| A04 scope freeze | Fraud detection, support expansion, logo, branding, profile pictures, demo video and launch assets were not touched |
