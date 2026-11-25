# Phase 03 — Security and Privacy Report (doctor system)

For: the project owner, reviewers and the Phase 05 security team. 2026-11-25.

## 1. Incident: test run against the database configured in `backend/.env` (P03-N22)

| Item | Detail |
|---|---|
| What happened | The first Phase 03 `pytest` run was started without `MONGODB_URI` / `DATABASE_NAME`. `app/config/settings.py` loads `backend/.env`, which points at a **remote Atlas cluster, database `mediconnect`**, and a real Stripe **test** key |
| When | About 20:08–20:30 +05:30 on 2026-11-25. Stopped by me after about 20 minutes of very low CPU, consistent with remote round-trips or timeouts |
| What is known | No test drops or empties a collection. Cleanups delete only records the test created (fixture IDs, `patient_…@mediconnect.lk` and `doctor_…@mediconnect.lk` emails, `DOC-TEST-…`, `STAB-…`, `DOC-AI-…`). Some tests run sweeps (hold expiry, reminder scheduler) |
| What is not known | Whether the run actually connected, and which tests ran. A read-only check (ping and counts of documents created in that window) was **blocked by the permission system**, and I did not try another route |
| Owner action | Check `mediconnect` for documents created 20:05–20:35 +05:30 with the patterns above |
| Prevention | `backend/tests/conftest.py` defaults the session to local `mediconnect_test` and mock Stripe keys, and **refuses** any non-local or non-`_test` target (verified). Recorded as a standing rule in the assistant's project memory |

## 2. Authorization sweep (live, 29 doctor-facing endpoints)

**Script:** `doctor_authz_sweep.py`. **Before and after:** `evidence/authz-sweep-before-fix.json` and `evidence/authz-sweep-after-fix.json`.

**Callers tested on every endpoint:**
- The approved doctor (Alpha).
- The pending doctor (`uat.doctor.pending1`).
- Patient A, who owns the test data.
- Patient B, who does not.
- An admin.
- An invalid token, and no token.

**Logins:** rejected and suspended doctors cannot log in (403).

| Finding | Result |
|---|---|
| Pending doctor | 403 on all schedule, appointment, workflow, clinical and care endpoints; 200 only on the application status page and their own empty `/me` lists |
| Invalid or no token | 401 everywhere |
| Patient B with `patientId` = patient A | 200, but **only B's own data** is returned: the parameter is ignored for patients. Verified by content in `evidence/cross-patient-param-check.json` |
| Unrelated approved doctor (Dr. P02 Spine) on patient A | 403 on records, summary, notes and trends (D-05d); 403 on signing a prescription for A; 403 on reading A's prescription (D-07d) |
| Another doctor on Alpha's appointment | 403 detail, 403 cancel, 404 preparation (D-01c) |
| `/clinical/records/summary` | 500 before the fix (P03-N14), 200 after |
| Expired and forged JWTs | 401 / 401 (D-01d) |
| Refresh after logout | 401 (D-01a2) |

## 3. Privacy defects fixed

| ID | Issue | Fix |
|---|---|---|
| P03-N01 / N02 | An unpaid reservation could be turned into a "consultation" whose session granted ongoing record access, even after release | Start only on CONFIRMED visits; sessions count only for CONFIRMED/COMPLETED visits; doctor must be APPROVED and ACTIVE |
| P03-N11 | Unsigned drafts visible to other related doctors | Other doctors see signed or amended notes only |
| P03-N17 | Care plans on unpaid or cancelled appointments granted record access | Plans require a real visit; plans grant access only with one |

**Preserved from Phase 02:** P02-N10 (released holds and cancelled bookings give no access) still holds. Verified live in R1b after the fix: 403/403.

## 4. Data exposure review

**Notification payloads:**
- Doctor reminder batches use fixed, non-clinical text.
- Care and test reminders carry no test or medicine names.
- Renewal notifications carry no medicine name.
- No notification about Dr. Alpha's patients reached Dr. Beta (D-13d).

**Prompt-injection text to the doctor assistant** reaches only read-only tools, scoped to the authenticated doctor (D-14b/c).

**Uploaded medical documents** are still plain files on disk, served only through authorized endpoints. Encryption at rest is still required (B8).

**Admin read access** to patient clinical records, notes and trends (200 in the sweep) is existing behaviour. Whether admins should read clinical content is a **policy decision** for Phase 04/05 (P3-B4).

## 5. Secrets and evidence

**No secret appears in code, reports or evidence:**
- The UAT password and JWT secret are read from git-ignored `backend/uat.env`.
- The Stripe test key is read from `backend/.env` inside the scripts and never printed.
- PaymentIntent IDs are masked.

**One script signs data with the UAT JWT secret:** the expired-token check signs a token with it, inside the script only.

**Device and network safety:**
- The emulator foreground guard aborted once, when the Dialer held window focus. Call state was IDLE, no call was placed, and nothing was typed into another app.
- The Emergency SOS tile was never tapped.
- Port 8000 was never contacted. The Flutter widget-test log lines naming `127.0.0.1:8000` come from the test binding's mocked HTTP client (HTTP 400), not real traffic.

## 6. Open security items carried forward

| Item | Owner / phase |
|---|---|
| Check the remote `mediconnect` database for test records (§1) | Owner, now |
| Rotate the SMTP password and Gemini key partly printed in Phase 02 (Phase 02 disclosure) | Owner |
| Encryption at rest for uploaded documents (B8) | Phase 05 |
| Admin access to clinical content (policy) | Phase 04/05 |
| Rejected doctors cannot log in (403, "Your doctor registration application was not approved. Please contact MediConnect support…"); there is no in-app appeal or re-application flow; confirm this is intended | Owner (P3-B6) |
