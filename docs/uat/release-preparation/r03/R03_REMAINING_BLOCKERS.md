# R03 — Remaining Blockers

For: the project owner. 2026-11-28. Nothing earlier is removed unless it says "resolved" with evidence. Owner actions are consolidated in `docs/uat/MEDICONNECT_OWNER_ACTIONS_BEFORE_RELEASE.md`.

## Resolved or settled in R03

| Item | How |
|---|---|
| A04: reminder on a renewed prescription not verified on a device | Verified on the emulator (Workflow C) |
| R02-O2: dedicated recommendation screen unreachable | Documented as dormant legacy, superseded by the unified assistant; no duplicate path added |
| R03-BUG-001 to 006 | Fixed with regression tests (`R03_BUG_FIX_REPORT.md`) |
| Contradictory "27 VERIFIED" sentence in the 38-component matrix | Corrected to 29 in the final matrix |

## Critical

| ID | Blocker | Owner action |
|---|---|---|
| P5-C1 / P4-B1 | MongoDB credentials in public Git history (`a41b659`); no rotation evidence | Rotate or delete the database user, review access logs, restrict network access, update deployments from a secret store |
| P4-B2 | Provider keys (Gemini, OpenAI, Stripe test) used during development | Rotate before any shared or public deployment |

## Clinical

B1 clinical validation · B2 pharmacist review · P3-B9 drug-interaction source · real-packaging image testing and a data-processing agreement (04) · clinician confirmation of self-reported profile values · clinical review of the R03-BUG-002 triage change.

## Product policy

| Item | Decision needed |
|---|---|
| BUG-039 | Consultation fee: there's no fee field at registration and no edit path; every app-registered doctor charges LKR 2,500 (R03-O7) |
| B6 | Refund and cancellation policy confirmation |
| Fraud thresholds | Provisional; set a review process and thresholds before real use |
| Free-text doctor–patient messaging | Not implemented (owner decision) |

## External services

FCM push, external e-mail, SMS (B4, B5) · OpenAI credits and Gemini paid tier (32) · Stripe staging webhook endpoint · production picture/document storage (shared or object storage, R02).

## Devices and language

Physical Android phone (B10) · iOS build and run · physical camera · native Sinhala and Tamil review (B12).

## Engineering follow-ups (non-blocking for a local demonstration)

- Admin dependency upgrades (R03-O5).
- `pip-audit` in CI.
- Dark-mode stat-label contrast (R03-O2).
- Doctor-facing "tamper-evident" wording (R03-O6).
- Explicit refusal wording for cross-patient and injection requests (R03-O4).
- UAT data reset between phases (R03-O1).
- R01-O3 to O7.
