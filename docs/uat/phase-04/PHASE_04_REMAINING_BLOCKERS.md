# Phase 04 — Remaining Blockers

For: the project owner and the Phase 05 team. Every earlier blocker is reconciled below; nothing was closed without evidence. 2026-11-26.

## 1. Closed in Phase 04

| ID | Item | Evidence |
|---|---|---|
| B15 | Admin refund page against the stricter refund API | Refunds page rebuilt (P04-N10/N23); A-10a–j, A-16f |
| P3-B2 | Admin `AppointmentsPage` crash on a null fee | P04-N03; crash reproduced on the original page (`evidence/p3-b2-null-fee-before.txt`), fixed (A-05c, A-05c-ui) |
| P3-B3 | Doctor-initiated refund requests in the admin UI | `source` stored and shown; doctor and leave requests reviewed and approved in the browser (A-10b/c, A-16f) |

## 2. New Phase 04 blockers and open items

| ID | Item | Type | Owner action | Blocks Phase 05 start? |
|---|---|---|---|---|
| **P4-B1** | **Remote database incident (was P3-B1): still unverified.** The review in `PHASE_04_DATABASE_INCIDENT_REVIEW.md` widens the possible impact:<br>• a background worker may have run against `mediconnect` (reminders, hold release, booking-confirmation **emails via `.env` SMTP**)<br>• `mediconnect_phase{2,3,4}_test` databases may have been created and dropped on the cluster | **Owner, urgent** | Run the read-only procedure (§4) and fill in the checklist (§5); remediate only with a reviewed plan (§6) | No, but it blocks any staging or production claim |
| **P4-B2** | Rotate SMTP, Gemini and OpenAI credentials. These were printed in part in Phase 02, and the incident run could have used them. **Also replace the development `JWT_SECRET` in `backend/.env`**: 11 characters and a common word, so tokens can be forged for any backend using it | Owner | Rotate in the providers' consoles; set a random 32+ byte JWT secret; update `backend/.env` | No |
| P4-B3 | Admin web `.env.example` and the development fallback point at port 8000 (P4-O2) | Configuration | Point the example at 8001 for UAT or document clearly | No |
| P4-B4a | Admin read access to care plan content (`GET /care-plans/{id}`) | **Policy (privacy)** | Decide: remove, or allow only through an audited break-glass flow | No |
| P4-B4b | Admins see the patient's booking note (reason for visit) | **Policy (privacy)** | Decide: hide by default with an audited reveal | No |
| P4-B5 | The backend started with no environment uses `backend/.env` (remote) | Owner decision | Decide whether development defaults should be local-only; the test and UAT paths are already guarded | No |
| P4-B6 | Historical paid doctor-cancellations without a refund request (1 found in UAT by reconciliation; production unknown) | Owner / admin | Review each through reconciliation; no automatic backfill (no historical migration) | No |
| P4-B7 | No platform fee or doctor payout model, so platform revenue and doctor earnings are shown as "not calculated" | Owner decision | Define the model before any revenue or earnings figure is displayed | No |
| P4-B8 | Support: users cannot reply to or reopen tickets; no mobile ticket screen | Product scope | Decide whether support is in scope for release | No |
| P4-B9 | Fraud: the slot-hoarding rule is not implemented; failed logins are not recorded as security events | Phase 05 | Add telemetry if the rules are wanted | No |
| P4-B10 | Stripe refunds that stay `pending` have no webhook follow-up; reconcile-refund is not audited (P4-O6/O7) | Phase 05 (needs B3) | Refund webhook handling, audit | No |
| P4-B11 | ~~Backend CI failure on `024f5cc`/`cb43142`~~ **Resolved.** The CI annotations added in `9764b26` named the test: `test_care_plans::test_11` used the machine-local date, which fails on UTC runners between 18:30 and 24:00 UTC (test fix `ee4f866`). Backend CI on `ee4f866`: **success** | CI | None | No |

## 3. Carried from Phase 02 and Phase 03 (unchanged unless stated)

| ID | Item | Status after Phase 04 |
|---|---|---|
| B1 | Clinical approval | **BLOCKED** (no clinician review) |
| B2 | Pharmacist approval | **BLOCKED** |
| B3 | Stripe → backend webhook delivery | **BLOCKED** (no Stripe CLI / public endpoint). Admin refunds work through the API; refund webhooks are not handled |
| B4 | FCM push delivery | **BLOCKED**. Monitoring now reports push as `not_configured`, with 0 delivered (previously counted as delivered) |
| B5 | Email and SMS delivery | **BLOCKED** in UAT (disabled); failures visible in monitoring |
| B6 | Refund and reschedule policy decisions | **OPEN – owner**. Existing policy preserved exactly |
| B7 | Two measurement stores | **OPEN – owner** |
| B8 | Encryption at rest for uploaded documents (now includes doctor verification documents) | **OPEN – Phase 05** |
| B9 | In-person migration on shared data | **NOT RUN** (owner approval; no historical migrations in Phase 04) |
| B10 | Physical phone testing | **NOT RUN** |
| B12 | Sinhala and Tamil review | **NOT RUN**; admin assistant suggestions in Romanized Sinhala also unreviewed |
| B13 | Live Gemini/OpenAI and Vision | **BLOCKED** (disabled in UAT); no admin component depends on them |
| B16 | AI reply to "change my dose" | **OPEN** (improvement) |
| B17 | Reply language after a Sinhala emergency follow-up | **OPEN** |
| P3-B4 | Admin read access to clinical content | **Corrected and narrowed**: no access to records, notes, measurements or prescriptions (verified by content). Remaining items are P4-B4a/b |
| P3-B5 | Old automatically created medication reminders | **OPEN – owner** (reversible cleanup needs approval) |
| P3-B6 | Rejected doctors: no appeal or re-application path | **OPEN – owner decision**. Supported behaviour verified: a clear 403 message at login (A-03f) |
| P3-B7 | Doctor workflow screen shows raw field names | **OPEN** (doctor UI, Phase 05) |
| P3-B8 | Consultation preparation scope | **OPEN** |
| P3-B9 | Drug-interaction source | **OPEN**; blocks a clinical pilot |
| P3-B10 | Doctor screens not tapped on a device | **OPEN** |
| P3-B11 | Multi-process doctor mutation testing | **OPEN** (admin refund concurrency was tested with 4 concurrent requests on one process, with database-level conditions) |
| P3-B12 | Emulator snapshot note | Environment note; not needed in Phase 04 (no mobile code changed) |

## 4. By type

| Type | Items |
|---|---|
| Technical | P4-B3, P4-B9, P4-B10, P3-B7, P3-B8, P3-B11, B8, B16, B17 |
| External integrations | B3, B4, B5, B13 |
| Owner decisions | P4-B1 (inspection), P4-B2, P4-B5, P4-B6, P4-B7, P4-B8, B6, B7, B9, P3-B5, P3-B6 |
| Clinical approvals | B1, B2, P3-B9 |
| Privacy approvals | P4-B4a, P4-B4b, B8 |
| Physical device | B10, P3-B10 |
| Language review | B12 |
