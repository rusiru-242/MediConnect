# R02 — Git Integration Report

For: the project owner and reviewers. Pull-request, CI and merge facts are filled in from GitHub after the events.

## Starting point (verified before any change)

| Check | Result |
|---|---|
| `git fetch origin --prune` | `origin/main` = `93520da63bb5ca8312d7bbd583f221b8a8a3b3c5`, "Merge pull request #28 from rusiru-242/feat/mediconnect-branding" (2026-11-28 01:53 +0530) |
| A01–A05 in `origin/main` | `febd063`, `048ad48`, `2cb5569`, `51bdaa3`, `df9ca5d`, `f075b33`, and the A05 merge `96e6fe7` (PR #27): all ancestors |
| R01 in `origin/main` | `a3649b0` (code), `eb5010c` and `90292ee` (docs), merged as PR #28 |
| CI on the R01 merge commit `93520da` (push) | Mobile CI **success**, Admin Web CI **success** (Backend CI not triggered; no backend path) |
| CI on the R01 PR head `90292ee` (pull_request) | Admin Web CI **success** (finished 20:23:48Z); Mobile CI **success** (finished 20:24:54Z) |
| **R01 merge timing** | PR #28 was merged at **20:23:09Z, while Mobile CI on the PR head was still running** (it started at 20:23:03Z and succeeded at 20:24:54Z). The same code had already passed on the branch push (`eb5010c`), and `90292ee` changed documentation only. The check later succeeded, but merging with a pending check is what the owner asked to avoid; the same happened for A04 |
| Deployments | `/deployments`: 0 |
| Working tree | Clean (on `feat/mediconnect-branding`) |
| Local `main` | Fast-forwarded to `93520da` |
| R02 branch | `feat/profile-picture-management` from `origin/main` `93520da`; upstream link removed so nothing can be pushed to `main` by accident |

**Post-merge records:** the R01 integration report on `main` still says "PR pending owner". This table is the record of R01's merge; R02 does not edit R01 documents.

## Commits on the R02 branch

| Commit | Scope |
|---|---|
| `b284388` | feat(profile): pictures, truthful patient profile, navigation and dark-mode fixes, fraud sweep fix (tested code) |
| `b73e9ab` | docs(uat): R02 reports, evidence, results; master tracker |
| next docs commit | this CI and PR record |

Pushed as a new remote branch (no force push).

**Not committed:**
- `backend/uat.env` and any `.env`;
- `backend/uploads/` (the stored pictures; git-ignored);
- the debug APK and `admin-web/dist`;
- scratch logs.

The only images committed are synthetic evidence (screenshots and the stored synthetic pictures).

## Deployment check

| Check | Result |
|---|---|
| Workflows | `backend-ci.yml`, `mobile-ci.yml`, `admin-web-ci.yml`: path-filtered lint, test and build; no deploy step |
| GitHub deployments | None |
| Vercel | `admin-web/vercel.json` exists; no Vercel status or check on earlier merges |

R02 changes `backend/**`, `mobile/**` and `admin-web/**`, so **all three** CI workflows apply.

## PR, CI and merge

### CI on the branch push (public GitHub API)

| Workflow | Commit | Result | Run |
|---|---|---|---|
| Backend CI | `b73e9ab` (contains code `b284388`) | **success** | actions/runs/46104436990 |
| Mobile CI | `b73e9ab` | **success** | actions/runs/46104436890 |
| Admin Web CI | `b73e9ab` | **success** | actions/runs/46104436953 |

### Pull request

**Status when this report was written:** not opened. The GitHub CLI is not logged in on this machine, so the agent cannot open or merge the PR. The owner was given the compare URL, title and prepared description, with the instruction **to merge only after Backend CI, Mobile CI and Admin Web CI have succeeded on the PR's final head**.

| Item | Value |
|---|---|
| Compare URL | https://github.com/rusiru-242/MediConnect/compare/main...feat/profile-picture-management?expand=1 |
| Title | R02: Secure Patient and Doctor Profile Pictures and Profile Data Corrections |
| Description | `evidence/r02_pr_description.md` in the report package |
| PR number, CI on the PR head, merge commit | Not yet available |
| `origin/main` at the time of writing | `93520da` (unchanged) |

## Post-merge verification

Not yet performed. Steps once merged:

1. Fetch `origin/main` and record the merge commit.
2. Confirm that the R02, R01 and A01–A05 commits are ancestors.
3. Check all three CI workflows on `main`.
4. Run the focused smoke tests: backend `test_r02_profile.py` and `test_a05_fraud_support.py`; Flutter `r02_profile_test.dart` and `r01_branding_test.dart`; admin `r02DoctorAvatar` and `r01Branding`.
5. Fast-forward local `main`.
6. Keep all feature branches.
