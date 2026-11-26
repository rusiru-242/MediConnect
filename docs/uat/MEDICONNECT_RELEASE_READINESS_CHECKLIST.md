# MediConnect — Release Readiness Checklist

For: the project owner deciding what MediConnect can be used for. 2026-11-26, branch `fix/phase-05-final-ai-security-integration` (`74fc231`). No percentages: each target is ready only when every gate in its list is met. ✅ = met now, ❌ = not met.

## Academic demonstration — READY

| Gate | Status |
|---|---|
| Runs end-to-end on the isolated local stack (UAT backend 8001, local MongoDB, Stripe test mode) | ✅ |
| Automated suites green (backend 782, admin 39, Flutter 307; CI green) | ✅ |
| No fabricated data, figures or medical content shown | ✅ (Phases 01–05 scans and fixes) |
| Demonstrated with synthetic accounts only | ✅ |
| Presenter states that it is not clinically approved | required at every demo |

## Local UAT — READY

| Gate | Status |
|---|---|
| UAT launcher refuses non-test Stripe keys and remote databases | ✅ |
| Live UAT scripts pass (Phase 05 12/12; regressions without unintended differences) | ✅ |
| Browser and emulator checks | ✅ (browser 14/14; emulator spot checks) |

## Staging — NOT READY

| Gate | Status | Item |
|---|---|---|
| Exposed MongoDB credentials rotated; access reviewed | ❌ | P5-C1 |
| Remote incident inspected read-only and resolved | ❌ | P4-B1 |
| SMTP, Gemini, OpenAI credentials rotated; strong JWT secret | ❌ | P4-B2 |
| Secrets in a secrets manager; `ENVIRONMENT=staging`; document keys set | ❌ | P5-S1 |
| Stripe webhook delivery to the staging endpoint verified | ❌ | B3 |
| Separate staging database with least-privilege user; backups | ❌ | deployment |
| CI green on the release commit | ✅ (re-check on the final commit) |

## Clinical pilot — NOT READY

All staging gates, plus:

| Gate | Status | Item |
|---|---|---|
| Clinical review of triage, crisis flow, alerts, care plans, preparation wording | ❌ | B1 |
| Pharmacist review of medicine information, refusals, renewals, B16 wording | ❌ | B2 |
| Authoritative drug-interaction source | ❌ | P3-B9 |
| Native Sinhala and Tamil review | ❌ | B12 |
| Physical Android device test (and iPhone if in scope) | ❌ | B10 |
| Push / e-mail / SMS delivery verified with test recipients | ❌ | B4, B5 |
| Privacy decisions: admin clinical-adjacent access, retention | ❌ | P4-B4a/b, retention |
| Ethics and data-protection approvals for real patients | ❌ | owner |

## Production — NOT READY

All clinical-pilot gates, plus:

| Gate | Status | Item |
|---|---|---|
| Refund/rescheduling policy, payout/commission model, support scope decided | ❌ | B6, P4-B7, P4-B8 |
| Live Stripe keys only with `ENVIRONMENT=production`; webhooks live-verified | ❌ | B3 |
| Existing uploads encrypted; key backup and rotation procedure | ❌ | P5-S1 |
| Historical data decisions (B9, P3-B5, P4-B6) | ❌ | owner |
| Major dependency upgrades (react-router 7, zod 4, vite) | ❌ | P5-S2 |
| Load test on the deployment topology; monitoring and alerting | ❌ | — |
| Incident response and on-call | ❌ | — |
