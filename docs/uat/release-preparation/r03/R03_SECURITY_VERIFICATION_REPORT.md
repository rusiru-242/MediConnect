# R03 — Security Verification Report

For: the project owner and reviewers. 2026-11-28. A focused regression audit of the local build; not a penetration test and not a security certification.

## 1. Credential exposure (critical, unresolved)

| Item | Status |
|---|---|
| Historical exposure | A real MongoDB connection string with credentials is in public Git history (commit `a41b659`, Phase 05 finding P5-C1 / P4-B1). R03 did **not** print, retrieve, test or use it, and did not contact that database |
| Rotation evidence | **None available to R03.** Treat the credential as active until the owner confirms rotation |
| Current tracked files | Redacted scan of all 1,379 tracked files (`secret_scan.py`, `evidence/r03_secret_scan_tracked.json`): 12 pattern matches, all placeholders (`<username>:<password>`, `user:pass`) or test fixtures on `example.net` / `127.0.0.1`. **The historical host and password appear in 0 tracked files** (compared in code without printing). No tracked `.env` file |
| R03 changes | The R03 diff was checked for key and connection-string patterns before committing: none |
| Required owner action | 1) Rotate the MongoDB user's password, or delete the user, in the hosting provider. 2) Review the provider's access logs since the exposure for unknown clients. 3) Restrict network access (IP allow-list). 4) Update every deployment's `MONGODB_URI` from a secret store. 5) Optionally rewrite history after rotation; rewriting does not remove clones or caches. Also rotate provider keys (P4-B2) |
| Release consequence | **Until rotation is confirmed, release only as an isolated local demonstration with synthetic data.** This is a critical blocker, not a cosmetic limitation |

## 2. Safeguards verified in R03

| Safeguard | Evidence | Result |
|---|---|---|
| JWT authentication | `SEC`: no token 401; tampered token 401 | PASS |
| Refresh token rotation | `SEC`: refresh once 200; reuse of the old refresh token 401 | PASS |
| Logout | `SEC`: refresh after logout 401; access token after logout 401 (revocation) | PASS |
| Role-based access control | `SEC`: patient and doctor → `/api/admin/users` 403; patient account cannot enter the admin app (browser b14) | PASS |
| Object-level authorisation | Other patient: appointment 403, notification 403, picture 404, ticket 403 (A05), prescription 403 (A04); another patient's booking proposal 403 (Workflow A step A05); payment for another's hold 403 (step A08) | PASS |
| Administrative permissions | Admin cannot read clinical records (A04 `adminRead` 403) or patient pictures (404) | PASS |
| Clinical record access | Care relationship required (A04 `unrelatedDoctorRead` 403; picture probe: unrelated doctor 404, treating doctor 200) | PASS |
| Encrypted document storage | `document_crypto` AES-256-GCM (suite: tamper and missing-key tests); medicine photos sealed at upload; `/uploads/...` is not served (404) | PASS |
| Encrypted profile images | R02 design re-checked; R02-BUG-007 fix strict key format; restart persistence identical | PASS |
| File upload validation and metadata removal | Picture probe: synthetic EXIF GPS removed, 512×512 re-encode; R02 S06–S12 in the suite | PASS |
| Path traversal | `test_storage_keys_are_strictly_validated_and_never_leave_the_base` (10 malicious keys refused) | PASS |
| Rate limiting | Suite (login, AI 30/min, picture changes 20/h); probes pace AI calls | PASS |
| Prompt-injection resistance | S08: no data, no action; P05 `sec` suite | PASS |
| Input validation | A04 V01–V02 (422), A05 C03 (422), R02 P08 | PASS |
| Sensitive data logging | Suite (`test_production_security_audit`, A01 no-content logging); R03 found no tokens or paths in admin pages | PASS |
| Error response sanitisation | `SEC`: malformed id returns no traceback | PASS |
| Payment ownership | A08 (403 before any Stripe call) | PASS |
| Server-controlled payment amounts | A07 (proposal = stored fee) | PASS |
| Reservation concurrency | A06 (one active appointment per slot; repeated Accept idempotent); suite unique-slot tests | PASS |
| Refund idempotency | Suite (4 concurrent approvals → 1 refund) | PASS |
| Notification recipient isolation | `SEC` (403) | PASS |
| Private cache isolation | Pictures `Cache-Control: private`; account switching on the device showed only each account's data | PASS |

## 3. Integrity findings fixed in R03

- **R03-BUG-004:** prescriptions claimed SLMC register verification and tamper evidence that do not exist. Removed. Honest wording matters here: a patient or pharmacist could rely on those claims.
- **R03-BUG-005:** a release build could attach placeholder "verified" credential documents to a doctor application. Now debug builds only.

## 4. Dependency review

| Area | Tool | Result |
|---|---|---|
| Admin web | `npm audit` against the official registry (the configured mirror has no audit endpoint) | 9 advisories: 2 critical, 2 high, 5 moderate. **Shipped in the production bundle:** `react-router-dom` (moderate: open redirect via backslash in links; an SSR-only issue that does not apply to this client-side app) and `zod` (high: memory exhaustion on oversized collections, client-side). **Developer tooling only (not shipped):** `vitest` / `tinypool` (critical), `vite` (high), `esbuild`, `vite-node`, `@vitest/mocker` (moderate). Fixes exist for all. Not confirmed exploitable in MediConnect; no upgrade made in R03 (R03-O5) |
| Backend | `pip-audit` | Not installed; not run (no new tool added). Versions recorded: FastAPI 0.142.1, Starlette 1.7.0, PyJWT 2.15.1, cryptography 50.0.1, Pillow 13.0.0, pymongo 4.20.2, Stripe 16.0.0 |
| Mobile | `flutter pub outdated` | No discontinued or retracted packages reported; Dart has no local advisory database |

**Recommendation:** an owner-approved maintenance PR to upgrade `vitest`, `vite`, `react-router-dom` and `zod`, and a `pip-audit` run in CI.

## 5. Not verified

- TLS, network access lists, backups, disk/database encryption and secret storage: deployment responsibilities, not testable locally.
- Branch protection settings: the GitHub API requires authentication for them (gh is not logged in).
- No external penetration test.
