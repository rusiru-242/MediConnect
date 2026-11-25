# Phase 04 — Security and Privacy Report (admin system)

For: the project owner, reviewers and the Phase 05 security team. 2026-11-26.

## 1. Database safety (P3-B1 follow-up)

**P04-N01: test guard hardened.**
- The Phase 03 prefix test was bypassable. Hosts are now parsed by `app/config/db_safety.py`, which is used by `tests/conftest.py`.
- Covered by 26 guard tests, including subprocess runs of the conftest with unsafe environments.

**Effective targets of every Phase 04 execution (printed redacted before running):**

| Execution | Target |
|---|---|
| Backend tests | host `127.0.0.1`, database `mediconnect_test` (also `mediconnect_cifresh_test`, `mediconnect_cienv_test` and `mediconnect_cinew_test` for the CI-like runs); Stripe `sk_test_mock_…` |
| UAT backend and scripts | host `127.0.0.1`, database `mediconnect_uat`, Stripe test key (launcher-checked) |
| Seeds | refuse non-local and non-`_uat` (verified with `cluster0.example.net`: refused) |

**`create_admin.py`:** refuses a remote database without `--allow-remote` (P04-N02).

**Incident:** not resolved; see `PHASE_04_DATABASE_INCIDENT_REVIEW.md`. The review found two risks not recorded in Phase 03:
- a test module that starts the app lifespan, and with it the background worker, against `mediconnect`;
- test modules that create and drop `mediconnect_phase{2,3,4}_test` on the configured cluster.

## 2. Authentication and role authorization

| Check | Result |
|---|---|
| Admin login, invalid password | 200 / 401 (A-01a/b) |
| Expired, forged (wrong secret) and missing admin tokens | 401 / 401 / 401 (A-01c) |
| Validly signed **patient** token claiming `role: ADMIN` | **403**: the role is read from the database account, not the token (A-01h) |
| Patient and doctor tokens on 10 admin endpoints | 403 on all; admin 200 on all (A-01d/e/g) |
| Logout | Refresh token revoked (refresh → 401) (A-01f). Access tokens are stateless JWTs and remain valid until expiry (60 min); account suspension is enforced on every request (A-03g) |
| Suspension | Takes effect on the next request with the same token (records 401, appointments 401); login refused; refresh tokens revoked (A-03g, `test_n08_…`) |
| Admin web route protection | Invalid session → `/login?expired=1`; a patient's login is refused by the admin app ("must hold the ADMIN role") and by the backend (A-01c2, A-01d2) |
| Token storage | `sessionStorage` (cleared when the tab closes). Tokens never appear in screenshots, logs or reports |
| Self-suspension, and activating PENDING accounts | 400 / 409 (A-04d, P04-N08) |
| **Unauthenticated worker heartbeat (P04-N13)** | Fixed: 401 anonymous, 403 patient |

## 3. Object-level authorization and sensitive data

| Check | Result |
|---|---|
| Admin access to patient clinical content (P3-B4) | **None** through the clinical API. `patientId` is ignored for non-doctors, and the content check found no patient record in six admin responses (A-14a, `test_a14_…`). The Phase 03 status-code reading is corrected in `PHASE_04_ADMIN_ACCESS_POLICY_MATRIX.md` |
| Remaining clinical-adjacent admin access | `GET /care-plans/{id}` (care plan content) and `patientNote` on appointments: **owner decisions** P4-B4a/b |
| Appointment detail | Admin 200 (operational); another patient 403 (A-14b) |
| Support tickets | Other patients 403, and tickets missing from their lists; linking another patient's booking 403 (A-09a/d, P04-N18) |
| Admin user and doctor lists | No `passwordHash`, `tokenHash`, refresh tokens or medical fields (A-04e) |
| Payments | No card data; monitored list masks patient names (A-14c); PaymentIntent IDs masked in evidence |
| Doctor verification documents | Admin only; patient 403; path traversal refused (404) (A-03c) |
| Monitoring endpoints | No connection strings, host names, stack traces or patient data. The database entry is "MongoDB" (was "MongoDB Atlas"). Public probes return only status |

## 4. Audit integrity

| Action | Audit record |
|---|---|
| Doctor approve / reject | `DOCTOR_VERIFICATION_DECISION`: actor, target profile, previous and new state, reason; `registrationNumberOfficiallyVerified: false` (P04-N08) |
| Suspend / reinstate | `USER_STATUS_CHANGE`: previous and new state, reason (P04-N08) |
| Refund approve / reject / Stripe failure | `REFUND_APPROVAL`, `REFUND_REJECTION`, `REFUND_EXECUTION` (`status: FAILED`) |
| Fraud review | `FRAUD_REVIEW_DECISION`, `accountActionTaken: false` (P04-N12) |
| Support reply / resolve | `SUPPORT_RESPONSE_SENT`, `SUPPORT_TICKET_RESOLVED` |
| Report generate / export | `REPORT_GENERATED`, `REPORT_EXPORTED` (no report content) (P04-N19) |
| Dead-letter requeue | `NOTIFICATION_REQUEUE` |
| Fields | `auditId`, `actorId`, `actorRole`, `actionType`, `targetId`, `targetType`, `previousState`, `newState`, `reason`, `status`, `metadata` (secrets redacted by `_sanitize_metadata`), `timestamp`, `correlationId` |
| Tamper resistance | No PUT, PATCH or DELETE route exists for audit logs (404/405, A-14e; route scan in `test_a14_…`); patients 403 on read |
| Attempted vs completed | Failed Stripe executions are recorded with `status: FAILED`; refused actions (400/403/409) are not audited as completed |
| Not audited (open) | Reconcile-refund (P4-O7); doctor document views (recommended) |

## 5. Export safety

**CSV export (P04-N17):**
- Numbers are written as numbers; 0 stays 0.
- Text beginning with `= + - @ tab CR | %` (also after leading spaces) is prefixed with `'`.

**Live API check (A-13e):** with `=HYPERLINK(…)` and `+cmd|calc` subjects, no exported cell starts with a formula character.

**Exports are audited.** Reports contain no medical content. Support subjects are included because the requester wrote them.

## 6. Admin AI safety

- **No state changes from AI:** all admin AI tools are read-only and restricted to `ADMIN_ROLES`. AI cannot approve doctors, approve refunds, suspend users, change payments, disclose medical records, send messages, export data or change settings.
- **Prompt injection (A-15c):** the injection attempt changed nothing.
- **Role checks (A-15a):** patients and doctors get 403 on both assistants.
- **Fraud signals (A-08):** they never restrict accounts. Explanations say they are signals, not findings.

## 7. Carried security work (Phase 05)

| Item | Reference |
|---|---|
| Encryption at rest for uploaded medical and verification documents | B8 |
| Remote database incident: owner inspection | P4-B1 |
| Rotate SMTP, Gemini and OpenAI credentials (Phase 02 disclosure; the incident run could have used them) | P4-B2 |
| **The development `JWT_SECRET` in `backend/.env` is weak**: 11 characters and a common word, found while scanning the report package (the value is not reproduced anywhere). Anyone who knows it can forge tokens for any backend started with that file. The backend enforces 32 bytes only when `ENVIRONMENT=production`. UAT uses a separate random 64-character secret (`uat.env`) | **P4-B2 (owner, urgent if that `.env` is used by any reachable backend)**; Phase 05: enforce the minimum length in every non-test environment |
| Failed logins are not recorded as security events | P4-O5 |
| Google Fonts request from the admin `index.html` (CSP / privacy) | P4-O3 |
| Duplicate mount of the security router (`/api` and root) | P4-O8 |
| Access-token revocation on logout (short TTL or deny-list) | Phase 05 |
| Admin roles (support, auditor, break-glass clinical) | Access matrix §3 |
