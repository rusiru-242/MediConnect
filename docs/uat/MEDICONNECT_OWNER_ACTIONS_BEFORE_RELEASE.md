# MediConnect — Owner Actions Before Release

For: the project owner. 2026-11-28 (after R03). Consolidates the open owner actions from Phases 01–05, A01–A05 and R01–R03. It supersedes `MEDICONNECT_OWNER_ACTION_CHECKLIST.md` for anything after R03; that earlier checklist is kept unchanged for history.

## 1. Critical: before anything leaves your local machine

| # | Action | Why |
|---|---|---|
| 1 | **Rotate (or delete) the MongoDB database user** whose connection string is in public Git history (`a41b659`). Review the provider's access logs since then, restrict network access, and put the new URI only in a secret store | P5-C1 / P4-B1: critical. R03 has no evidence of rotation |
| 2 | Rotate Gemini, OpenAI and Stripe test keys used during development | P4-B2 |
| 3 | Until 1–2 are done, use MediConnect **only as a local demonstration with synthetic data** | Release restriction |

## 2. Before merging any future PR

| # | Action |
|---|---|
| 4 | Merge only after every applicable check shows success on the PR's final head. A04, R01, R02 (PR #29) and the R02 follow-up (PR #30) were all merged with checks still pending |
| 5 | Consider branch protection: required checks for Backend, Mobile and Admin Web CI (path-filtered), and no direct pushes to `main` |
| 6 | Log in the GitHub CLI (`gh auth login --web`) if you want the agent to open PRs and read check states |

## 3. Decisions only you can make

| # | Decision | Current behaviour |
|---|---|---|
| 7 | **BUG-039, consultation fee:** should doctors enter their fee at registration, edit it later, and must an admin confirm it? | No fee field and no edit path; every app-registered doctor charges LKR 2,500 |
| 8 | **B6, refund and cancellation policy:** confirm cutoffs, percentages and who bears payment fees | Policy amounts from earlier phases, unconfirmed |
| 9 | Fraud review process and thresholds | Provisional engineering defaults |
| 10 | Production storage for documents and profile pictures (shared or object storage, encryption, backups) | Local encrypted disk, single server |
| 11 | Whether to remove the dormant dedicated recommendation screen or keep it as legacy | Superseded by the unified assistant (R02-O2) |
| 12 | Whether free-text doctor–patient messaging is in scope | Not implemented |

## 4. Clinical and language reviews (required before real patients)

13. Clinical validation of triage, health-assistant content, thresholds and timings (B1). Include the R03-BUG-002 triage change.
14. Pharmacist review of medicine information, reminders and prescription presentation (B2).
15. A clinically validated drug-interaction source (P3-B9).
16. Native Sinhala and Tamil review (B12).
17. A data-processing agreement before any real patient image is sent to an AI provider; testing on real packaging.

## 5. External services and devices

18. Firebase push, external e-mail and SMS providers (B4, B5).
19. OpenAI credits or a decision to run Gemini only; a paid Gemini tier for any pilot.
20. Stripe staging webhook endpoint.
21. Physical Android phone run (including the PaymentSheet and camera); an iOS build and run.

## 6. Recommended engineering maintenance

22. Admin dependency upgrades (`vitest`, `vite`, `react-router-dom`, `zod`; R03-O5) in a separate PR.
23. Add `pip-audit` to Backend CI.
24. Minor items R03-O2, O4 and O6, and R01-O3 to O7.
25. Reset the local UAT database between phases, or use per-phase synthetic accounts (R03-O1).

## 7. Authorisations needed for R05 (demonstration)

- **Stripe test-mode payments:** confirm whether test-mode payments may be shown live.
- **Live Gemini:** decide whether to enable it, including vision, with a call cap.

R03 made no Stripe and no AI provider request.
