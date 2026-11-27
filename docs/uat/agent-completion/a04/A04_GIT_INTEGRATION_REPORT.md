# A04 — Git Integration Report

For: the project owner and reviewers. Records how A04 was branched, verified, proposed and integrated. Pull-request, CI and merge results are filled in from GitHub after the events, in the **PR, CI and merge** section.

## Starting point (verified before any change)

| Check | Result |
|---|---|
| Working tree | On `main`; one untracked user file `docs/uat/agent-completion.zip` (left untouched; not committed) |
| `git fetch origin --prune` | `origin/main` = `d8c2142dd497971947fa24d395b8c157b25b3eee` (Merge pull request #25) |
| Local `main` | Already at `d8c2142` (`git merge --ff-only origin/main` → "Already up to date") |
| A01, A02, A03 in `origin/main` | `febd063` (A01 tip), `048ad48` (A02 tip), `2cb5569` (A03 tip), `e3722ba` (last A03 code commit): all ancestors of `d8c2142` |
| PR #25 | Merged 2026-11-27 13:32:48 UTC, merge commit `d8c2142` (GitHub public API) |
| Earlier stabilization fixes | Present: the full backend suite on `main` code had 945 passing tests (A03 baseline), and every A01–A03 test file is unchanged and passing in A04 |
| A04 branch | `fix/agents-a04-prescription-assistant` created from `origin/main` `d8c2142` (not from a stale local `main`) |

## Commits on the A04 branch

| Commit | Scope |
|---|---|
| `3002dfa` | fix(prescriptions): validation, race-safe issuing and renewals, allergy warnings, amendment and notification fixes (A04-BUG-001..006, 008, 012) |
| `94bbd71` | feat(ai-prescription): grounded prescription answers and explicit refusals (Agent 17, A04-BUG-007, 016) |
| `51bdaa3` | fix(mobile): prescription entry without pre-filled dosing, reachable documentation and renewals, draft review (A04-BUG-009..011, 013..015) |
| docs commit | A04 reports, evidence, results; master tracker and 38-component matrix |

**Tested code commit:** `51bdaa3`.

**Not committed:**
- The user's `docs/uat/agent-completion.zip`.
- Three Flutter plugin-registrant files whose only change is line endings from local builds.
- `backend/uat.env` and any `.env`, which are git-ignored.

## Deployment check before merging

| Check | Result |
|---|---|
| Workflows | `backend-ci.yml`, `mobile-ci.yml`, `admin-web-ci.yml`: path-filtered lint, test and build only. No deploy step, no secrets used |
| GitHub deployments and environments | None (`/deployments` and `/environments` empty) |
| Vercel | `admin-web/vercel.json` exists, but no Vercel status or check appears on the last `main` merges (`d8c2142`, `c300aa7`), so no connected Vercel integration was observed |
| Conclusion | Merging to `main` triggers CI only; no production deployment was observed to be wired to `main` |

## PR, CI and merge

(Filled in after the events; see the final completion report for the final values.)
