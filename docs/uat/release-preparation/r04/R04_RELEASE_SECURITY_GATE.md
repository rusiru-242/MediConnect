# R04 — Release Security Gate

For: the project owner. 2026-11-28.

## Verdict

**Public release: NOT ELIGIBLE.** The release is prepared as a local package only. No tag, GitHub release or public APK was created.

| Condition for public release | Status |
|---|---|
| R04 integrated into `main` | Pending (PR not yet opened or merged) |
| Applicable CI checks successful | Pending on the R04 PR head |
| **Exposed MongoDB credential revoked or rotated** | **No evidence provided.** No owner statement or other record of rotation exists in the repository or this session |
| Deployment environment variables updated | No evidence |
| Other provider credentials rotated (P4-B2) | No evidence |
| Database network restrictions in place | No evidence |
| Incident investigation acknowledged | No evidence |
| Sanitised release artifacts | Yes (scans below) |
| Explicit owner approval for public release | Not given |

R04 did not retrieve, print, test or use the historical credential, did not contact any remote database, changed no credential and rewrote no history. **Clean current files do not resolve the historical exposure:** the credential remains in public Git history (`a41b659`) until it is rotated.

## Redacted secret scans (R04)

| Target | Method | Result |
|---|---|---|
| Tracked and staged files (1,488) | `r03/secret_scan.py` | 11 matches, all placeholders or test fixtures (as classified in R03); 0 tracked `.env` files; historical host and password absent (R03 comparison) |
| Release documentation and screenshots | Package scan + visual review | None |
| APK (1,498 entries) | Pattern scan + UAT password check | No secrets; one Stripe **test publishable** key (informational, see build report) |
| Admin build (`dist/`, 44 files) | Pattern scan | None |
| Release package (30 files, incl. APK and admin ZIP contents) | Pattern scan + UAT password check | None (publishable keys not counted as secrets) |
| R04 report package | Pattern scan + UAT password check | None |

## Required owner actions before any publication

1. Rotate or delete the exposed MongoDB user, review access logs, and restrict network access.
2. Rotate the Stripe test keys, including the hard-coded test publishable key, and the Gemini and OpenAI keys.
3. Update all deployment secrets from a secret store.
4. Merge R04 only after CI succeeds on the PR head.
5. Approve the public release explicitly, choosing whether to attach the emulator-only debug APK. A distributable APK needs your own signing configuration and a release build.

## Prepared GitHub release (draft text, not published)

Tag `v1.0.0-academic` (no existing tags). The description is in `evidence/r04_github_release_draft.md`.
