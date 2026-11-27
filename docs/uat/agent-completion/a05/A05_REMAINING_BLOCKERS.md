# A05 — Remaining Blockers, Owner Actions and Decisions

For: the project owner. 2026-11-28, after Agent Completion A05 (Agents 25 and 26), the last agent-completion phase. Every unresolved earlier blocker is carried forward; nothing is marked resolved without evidence.

## Owner actions (in priority order)

| # | Action | Unblocks | Notes |
|---|---|---|---|
| 1 | **Rotate the MongoDB credentials (P5-C1)** and run the remote incident inspection (P4-B1) | Staging and anything beyond | Still the top security blocker. A05 did not connect to the remote cluster or touch credentials |
| 2 | Rotate the SMTP, Gemini, OpenAI and Stripe test credentials (P4-B2); check the SMTP Sent and bounce folders (A02 2a) | Staging | Unchanged |
| 3 | **Fix the hard-coded patient Profile data (A05-O1)** in the profile phase: fabricated height, weight, BMI, "Allergies: Penicillin" and emergency contact | Release | Not A05 scope; a fabricated allergy on a patient screen must not ship |
| 4 | Pharmacist review (B2) and clinical validation (B1), including Agent 17 | Agent 17 sign-off | Unchanged from A04 |
| 5 | Drug-interaction source decision (P3-B9) | Interaction checking | Unchanged |
| 6 | **Fraud thresholds: decide the starting values and a review process** (A05) | Agent 25 in production | The defaults (4 distinct unpaid slots in 24 h; existing rule thresholds) are provisional. Calibrating them needs real, consented data and a measured false-positive rate. Decide how QA and demo accounts are treated (A05-O2) |
| 7 | Stripe webhook endpoint for staging (A03 action 3) | Agent 01 staging | Unchanged |
| 8 | Refund and cancellation policy confirmation (B6) | Agent 01 policy sign-off | Support templates now avoid stating refund outcomes until the policy is approved |
| 9 | Physical Android phone test (B10) | Device sign-off | Now also covers Help & Support |
| 10 | Native Sinhala and Tamil review (B12) | Language sign-off | Plus the support screens, templates and chat answers (English only, A05-O7) |
| 11 | Firebase, iOS/APNs, e-mail sandbox, SMS provider (A02 actions 3–6) | External delivery | Unchanged. Support replies are verified in-app only |
| 12 | OpenAI credits; Gemini paid tier for any pilot | AI providers | Unchanged. Agents 25 and 26 do not call a provider |
| 13 | A04 renewed-prescription reminder on the device (A04 M04 PARTIAL) | Agent 17 | Unchanged |
| 14 | Product decisions: admin notification for support follow-ups (A05-O5), a doctor support screen (A05-O6), admin queue paging (A05-O8) | — | Optional |

## Human review gates

| Gate | Item |
|---|---|
| Clinical review | B1 |
| Pharmacist review | B2 |
| Physical device | B10 |
| Native Sinhala/Tamil review | B12 |
| Fraud review process | Who reviews signals, how quickly, and what a "confirmed finding" leads to (all actions stay manual) |

## A03 webhook figures (carried forward unchanged)

| Count | Value |
|---|---|
| Forwarded deliveries | 51 (48 distinct events + 3 resends) |
| HTTP 200 | 46 |
| Refused during the deliberate outage | 5 |
| Resent after the restart | 3 |
| Never redelivered | 2 `charge.refund.updated` |

The final refund state was reportedly reconciled through other accepted events (A04 clarification, A04-O8).

## Open observations

| Item | Status |
|---|---|
| A05-O1 to A05-O10 | In `A05_BUG_FIX_REPORT.md` |
| A04-O1 to O8, A03-O1 to O7, A02-O1 to O3 and O5, A01-O1 to O4 | Unchanged |

## Not done in A05 (and why)

| Item | Why |
|---|---|
| Live Gemini or OpenAI tests | Neither agent calls a provider; no A05 authorization exists |
| Live Stripe requests | Not needed: no payment was created; Stripe calls in tests are mocked |
| Push, e-mail or SMS delivery of support replies | Providers disabled in UAT; in-app delivery only |
| Fraud threshold calibration | No real fraud data; local synthetic data cannot calibrate |
| Physical phone | Gate B10 |
| Scope freeze | Logo, branding, splash screen, profile pictures, profile redesign, new agents, demo video, launch assets and deployment were not touched |
