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

### Pull request and merge

The owner opened and merged the PR (the GitHub CLI is not logged in on this machine, so the agent did neither).

| Item | Value |
|---|---|
| PR | **#29** https://github.com/rusiru-242/MediConnect/pull/29 (title on GitHub: "Feat/profile picture management", not the prepared title) |
| PR head | `e652c5e` |
| Merged | 2026-11-28 04:21:15Z (09:51 +0530), merge commit **`8ac5a411a1c9715ea70b17b234d6a4c656e7665b`**, parents `93520da` + `e652c5e` |
| Tree | Identical to `e652c5e` (no merge-time changes) |
| Deployments | `/deployments`: 0 after the merge |

### CI on the PR head and on `main`

| Workflow | PR head `e652c5e` (pull_request) | Merge `8ac5a41` (push) |
|---|---|---|
| Backend CI | **success** (run 46107133056, 04:21:09Z → 04:29:22Z) | **success** (46107145548, finished 04:27:28Z) |
| Mobile CI | **success** (46107132993, 04:21:09Z → 04:23:34Z) | **success** (46107145531, finished 04:23:34Z) |
| Admin Web CI | **success** (46107133039, 04:21:09Z → 04:21:41Z) | **success** (46107145530, finished 04:22:03Z) |

**Merge timing:** the PR was merged **6 seconds after its checks started**, while Backend, Mobile and Admin Web CI were all still running on the PR head. All three later succeeded, and the same code had already passed on the branch push (`b73e9ab`), but this is the third merge (A04, R01, R02) made with pending checks, which the R02 instructions prohibit.

## Post-merge verification

| Step | Result |
|---|---|
| Fetch `origin/main` | `8ac5a41` |
| Ancestry | `b284388`, `b73e9ab`, `e652c5e` (R02), `93520da`, `a3649b0` (R01), `96e6fe7`, `febd063`, `df9ca5d`, `f075b33` (A01–A05): all ancestors |
| CI on `main` | All three workflows **success** |
| Local `main` | Fast-forwarded to `8ac5a41` |
| Flutter smoke | `r02_profile_test.dart` + `r01_branding_test.dart`: **28 passed** |
| Admin smoke | `r02DoctorAvatar` + `r01Branding`: **7 passed** |
| Backend smoke | `test_r02_profile.py` + `test_a05_fraud_support.py`: **71 passed, 1 failed** (`test_s13`, 3 of 5 parallel uploads refused). Reproduced repeatedly; diagnosed as **R02-BUG-007** (Windows `resolve()` race), fixed on `fix/profile-image-path-race` (see the bug-fix report) |
| Branches | All feature branches kept |

R02-BUG-007 was not caught before the merge because it is intermittent: `test_s13` passed in both pre-merge full runs and in CI (Linux). The follow-up fix needs its own PR.
