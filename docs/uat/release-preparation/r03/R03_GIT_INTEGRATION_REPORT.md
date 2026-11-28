# R03 — Git Integration Report

For: the project owner and reviewers. Pull-request, CI and merge facts are added from GitHub after the events.

## Starting point (verified before any change)

| Check | Result |
|---|---|
| `git fetch origin --prune` | `origin/main` = `b20e683` "Merge pull request #30 from rusiru-242/fix/profile-image-path-race" |
| A01–A03 | PR #25 (`fix/agents-a03-booking-payments`) merged 2026-11-27 13:32:48Z, merge `d8c2142`; commits `febd063`, `048ad48`, `2cb5569` are ancestors |
| A04 | PR #26 (`fix/agents-a04-prescription-assistant`, head `c36b705`): merged; `51bdaa3`, `df9ca5d` ancestors |
| A05 | PR #27, merge `96e6fe7`: ancestor |
| R01 | PR #28, merge `93520da`: ancestor |
| R02 | **PR #29**, merge `8ac5a41` (2026-11-28 04:21:15Z), head `e652c5e`; `b284388`, `b73e9ab`, `e652c5e` ancestors |
| R02 follow-up | **PR #30**, merge `b20e683` (04:35:56Z), head `e58cec3`: the R02-BUG-007 fix written by the agent after the R02 merge and committed by the owner |
| CI on `main` `8ac5a41` | Backend, Mobile, Admin Web: success |
| CI on PR #29 head `e652c5e` | Backend, Mobile, Admin Web: success (all finished after the merge) |
| CI on PR #30 head `e58cec3` and `main` `b20e683` | Backend CI: success (only backend paths changed) |
| Deployments | `/deployments`: 0 |
| Local `main` | Fast-forwarded to `b20e683` |
| R03 branch | `fix/final-release-verification` from `b20e683`; upstream unset |

**Premature merges:**
- PR #29 was merged 6 seconds after its checks started, and PR #30 10 seconds after it was opened, both with checks pending.
- This is now the fourth and fifth such merge (A04, R01, R02, R02 follow-up). Every check later succeeded, but merging with pending checks is what the R03 instructions prohibit.
- PR #30 also committed a generated test-output file (`backend/a03_leak_attempts.json`, zero counts), removed in R03 (R03-BUG-006).

## R03 commits

| Commit | Scope |
|---|---|
| `4f64295` | fix(r03): tested code: R03-BUG-001 to 006 and the new regression tests |
| next | docs(uat): R03 reports, evidence, scripts, consolidated final documents, master tracker |

**Not committed:**
- `backend/uat.env` and any `.env`;
- `backend/uploads/`;
- the APK and `admin-web/dist`;
- scratch logs;
- the provider-detector output.

The images committed are synthetic evidence only: emulator and browser screenshots.

## Deployment check

- Workflows `backend-ci.yml`, `mobile-ci.yml` and `admin-web-ci.yml` are path-filtered lint/test/build workflows with no deploy step.
- No GitHub deployments.
- `admin-web/vercel.json` exists, but no Vercel status has appeared on earlier merges.
- R03 changes `backend/**` and `mobile/**`, so Backend CI and Mobile CI apply. Admin Web CI applies only if an `admin-web/**` path changes; it does not in R03.

## PR, CI and merge

To be completed after the events.
