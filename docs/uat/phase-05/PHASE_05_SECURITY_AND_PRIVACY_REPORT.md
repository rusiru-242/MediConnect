# Phase 05 — Security and Privacy Report

For: the project owner, reviewers and the team preparing any staging or production deployment. 2026-11-26.

## 0. Critical finding: live database credentials in public git history (P5-C1)

The history secret scan (`secret_history_scan.py`, 3,450 blobs, every ref) found that the **current `MONGODB_URI` from the git-ignored `backend/.env`, including its username and password, is committed in `backend/.env.example` at commit `a41b659`** (the file was first added in `0a80f83`, 2026-09-30). The current file no longer contains it, but the commit is reachable from `origin/main` and 45 remote branches, and the repository is public (the GitHub API answers without authentication).

Consequences: anyone could have read the credentials since that push. This widens the unresolved remote-database incident (P4-B1): unexpected changes in the remote database could come from third parties, not only from the November 25 test run.

Required owner action (not automated, by instruction):
1. In MongoDB Atlas, change the password of that database user (or delete the user and create a new least-privilege one) **now**; update `backend/.env` and any deployment secret.
2. Review Atlas access logs / activity feed since 2026-09-30 and the network access list (remove `0.0.0.0/0` if present).
3. Then run the P4-B1 read-only inspection (`PHASE_04_DATABASE_INCIDENT_REVIEW.md`).
4. Decide whether to rewrite history (needs your explicit authorization; it does not undo the exposure, rotation does).

The value is not reproduced in any report, log or package. Other scan hits were placeholders (`user:password@` in deployment docs), synthetic test fixtures (redaction tests, guard tests) or the common-word development JWT secret (see §3).

## 1. Database isolation and fail-closed configuration (P4-B5)

| Entry point | Phase 05 behaviour | Evidence |
|---|---|---|
| API start-up (lifespan) | `startup_errors()` refuses: unknown `ENVIRONMENT`; remote DB in `development` without `ALLOW_REMOTE_DATABASE=true`; `test` not local `*_test`; weak/default JWT secret; non-HMAC algorithm; access tokens > 60 min; refresh > 30 days; live Stripe key outside production; production without document-encryption keys | `test_phase05_security.py` N01/N04, subprocess test with the `.env` shape |
| Any code path reaching MongoDB through the app (worker, scripts importing the app) | `DatabaseManager.get_client()` applies the same rule before creating a client | `test_n01_database_manager_refuses_remote_in_development_before_connecting` (MongoClient never constructed) |
| pytest | `ENVIRONMENT=test`, local `*_test` database, random per-session JWT secret and document key; never inherits `.env` secrets | `tests/conftest.py`, 26 Phase 04 guard tests still pass |
| UAT launcher | local `mediconnect_uat`, `ENVIRONMENT=staging`, UAT JWT secret and UAT document key in git-ignored `uat.env`, Stripe test key enforced, providers and SMTP blanked | `start_uat_backend.ps1` |
| Seed / admin / migration scripts | local-only guards (host parsing); migration script now uses `is_local_mongodb_uri` instead of `urlsplit().hostname` | Phase 04 + this phase |
| CI | disposable `mongo:7.0` service, test keys | `backend-ci.yml` |

**Migration requirement for the owner:** a backend started with the current `backend/.env` (no `ENVIRONMENT`, remote URI, 11-character JWT secret) now **refuses to start**. For deliberate use of that database set `ENVIRONMENT=production` (or `staging`), a random JWT secret of at least 32 bytes and `DOCUMENT_ENCRYPTION_KEYS`; for local development use a local MongoDB. `backend/.env` was not modified.

## 2. Authentication, tokens and sessions

| Control | Before Phase 05 | Now | Test |
|---|---|---|---|
| Access-token claims | `sub, role, type, iat, exp` | + `iss`, `aud`, `jti`; all required; single configured HMAC algorithm | N05 (missing/wrong `aud`, `iss`, `type`, `jti`, `alg=none`, expiry → 401) |
| Role from token | ignored (database role used) | unchanged; fully valid patient token claiming ADMIN → 403 | S-07a (`test_s07a…`) |
| Access-token lifetime | 60 min default | 15 min default, max 60 enforced | N04 |
| Logout | refresh token only | refresh token + access token (jti deny-list with TTL) | N06; live SEC-b |
| Suspension / password reset | per-request status check; old tokens valid again after reinstatement | `tokensValidAfter` makes earlier tokens invalid permanently | N07 |
| Refresh rotation | unconditional update — **two concurrent refreshes both succeeded (P05-N02)** | conditional claim: exactly one succeeds | N02 (8 concurrent → 1×200, 7×401) |
| Refresh replay | rejected only | rotated token reused → whole login family revoked + HIGH security event | N02 replay; live SEC-a |
| Refresh for removed account | **500 (P05-N03)** | 401 | N03 |
| Refresh rate limit | none | 30/min per IP (shared) | — |
| Failed-login telemetry (P4-B9/P4-O5) | none | keyed pseudonyms (HMAC) of e-mail and IP; same 401 body for unknown and wrong password; one BRUTE_FORCE signal per 15 min after 5 failures; no lockout | N08 |

Concurrency note: a mobile client that sends two refreshes in parallel with the same token now loses that session (by design of replay detection). The Flutter client already serializes refreshes (one in-flight refresh shared through `_refreshCompleter` in `lib/core/network/api_client.dart`); the admin web refreshes on 401 per request. Physical-device verification is pending (B10).

## 3. Secrets and credentials (P4-B2)

| Check | Result |
|---|---|
| Git history (all refs) | **P5-C1** above; no Stripe live/test secret, webhook secret, Google/OpenAI key, private key or GitHub token committed |
| Flutter debug APK (1,476 entries) | no secret values from `.env`/`uat.env`, no key patterns (`evidence/bundle-secret-scan.json`) |
| Admin production bundle (38 files) | none |
| Reports, evidence, logs | values never printed; packages scanned before delivery |
| Development `JWT_SECRET` in `backend/.env` | still the 11-character common word; now **refused** outside `test` |
| Rotation guide | `PHASE_05_OWNER_ACTION_CHECKLIST.md` §1 (MongoDB, SMTP, Gemini, OpenAI, JWT, Stripe webhook secret) |

## 4. Medical document encryption at rest (B8)

* AES-256-GCM via `cryptography` (no custom cryptography). File container: `MCENC1 | key id | 12-byte random nonce | ciphertext+tag`; the storage path is authenticated data, so a file copied to another patient's path fails.
* Covers patient medical documents, doctor verification documents and medicine photos.
* Keys: `DOCUMENT_ENCRYPTION_KEYS` (`id:base64`, newest first) from the environment only; separate random keys for tests (per session) and UAT (`uat.env`); production refuses to start without keys.
* Downloads decrypt in memory (no plaintext temp file), verify the stored SHA-256 for medical records, send `Cache-Control: no-store`; tampered/keyless files return a sanitized 500; legacy plaintext files remain readable.
* Rotation and migration: `scripts/encrypt_existing_documents.py` (dry-run default, `--apply`, `--rotate`, `--revert`, atomic replace, verify-before-swap, idempotent). Run in Phase 05 only on local test directories; **not** run on shared/remote storage.
* Every admin view of a verification document is audited (`DOCTOR_DOCUMENT_VIEWED`).
* Live (W08): an upload on the UAT server is stored as `MCENC1…` with no plaintext; patient gets identical bytes; another patient and the admin get 403.
* Distinctions: this is application-level encryption. Disk/volume encryption, MongoDB Atlas encryption at rest and encrypted backups are separate deployment responsibilities. Key storage in a secrets manager (not a `.env` file) is a production requirement.

## 5. Authorization and privacy

* HTTP and AI tool authorization are both enforced (S-07a/b, S-01a–f). Phase 03 authorization sweep re-run: identical to Phase 04 (29 rows, 0 differences). The sweep's four "otherPatient" flags are its known false positive: non-doctors' `patientId` is ignored and they receive only their own data (content-verified in Phase 04).
* Medical document access: patient, treating doctor (confirmed/completed visit) only; unrelated doctor, other patient, admin → 403 (tests + live W08).
* Admin clinical access policy (P4-B4a/b) unchanged and still an owner decision. Consultation preparation (P3-B8) adds shared sources only behind the existing care-relationship check; other clinicians' note text is excluded pending a decision.
* Records list robustness (P4-O1): one malformed record no longer hides the list; it is reported by reference.
* Conversation retention: unchanged default; owner may set `CONVERSATION_RETENTION_DAYS`.

## 6. Rate limiting and API hardening

* Shared rate limiter (BUG-038): MongoDB counters, sliding-window estimate, TTL expiry, hashed keys; in-process fallback if MongoDB is down. Verified across separate OS processes (3 processes × 10 attempts against a limit of 20 → exactly 10 rejections). Limits: login 20/min, registration 15, OTP 10, password reset 10, refresh 30, payment intent 30, AI booking/health 30 per user, recommendations 20. The health-chat 429 message keeps the 1990 emergency guidance.
* `X-Forwarded-For` is trusted for client IP; a direct (non-proxied) deployment must strip it at the edge.
* Security router mounted once (P4-O8); probes remain at `/health/*` and `/api/health/*`.
* Admin web (P4-O3): no third-party font request; production builds carry a CSP (`default-src 'self'`, `connect-src` = API origin, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`). `X-Frame-Options: DENY` and other headers are set by `vercel.json`/backend.
* Admin web development default API is the local UAT backend (`127.0.0.1:8001`), not port 8000 (P4-B3).

## 7. Stripe webhook integrity (B3/P4-B10)

Signature verified by the Stripe library on the raw body (tampered body, wrong secret and stale timestamps rejected in tests with real HMAC signatures). Events are logged by id and de-duplicated; `payment_intent.canceled` and refund events are handled with ownership, currency, amount and PaymentIntent checks; final refund states are never downgraded; failure-after-success is flagged for review. Reconcile-refund is audited (P4-O7). External delivery from Stripe to this backend: **BLOCKED** (no Stripe CLI or authorized endpoint; the configured `STRIPE_WEBHOOK_SECRET` belongs to the owner's dashboard endpoint and was not used).

## 8. Dependency and static scans

| Scan | Result | Action |
|---|---|---|
| pip-audit, `requirements.txt` resolution | 0 known vulnerabilities | — |
| pip-audit, this machine's venv | 11 advisories in 5 packages (certifi, dnspython, opentelemetry-api, pyasn1, pymongo) | minimum versions raised in `requirements.txt`; venv upgraded; re-audit 0 |
| bandit (backend/app) | 17 low (try/except pass/continue), 0 medium/high | accepted (monitoring code must not fail requests) |
| npm audit (admin web, all deps) | 17 before; non-breaking fixes applied (follow-redirects high and others) | — |
| npm audit, production deps after fixes | react-router (moderate ×2), zod (high) — fixes require major upgrades | not exploitable in current use: all navigation targets are constants; zod validates two login strings, no collections. Upgrade recommended (Phase 06 / owner) |
| npm audit, dev-only | vite/vitest/esbuild (incl. critical in tinypool via vitest) — dev server/test runner only, major upgrades | recommended; not in the production bundle |

Tool limitations: advisory databases are only as current as their feeds; bandit does not understand FastAPI authorization; no DAST was run against a deployed environment.

## 9. Open security items

| ID | Item | Owner |
|---|---|---|
| P5-C1 | Rotate the exposed MongoDB credentials; review access | Owner — urgent |
| P4-B1 | Remote incident read-only inspection (now including third-party access) | Owner — urgent |
| P4-B2 | Rotate SMTP, Gemini, OpenAI; replace the development JWT secret | Owner |
| P5-S1 | Production key management for `DOCUMENT_ENCRYPTION_KEYS` and JWT secret (secrets manager) | Owner / deployment |
| P5-S2 | Major upgrades: react-router 7, zod 4, vite/vitest | Engineering |
| P4-B4a/b | Admin clinical-adjacent access policy | Owner / privacy |
