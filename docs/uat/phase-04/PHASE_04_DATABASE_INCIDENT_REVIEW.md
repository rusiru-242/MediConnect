# Phase 04 — Database Incident Review (P3-B1 / P03-N22)

For: the project owner, who holds the remote database credentials and is the only person who may inspect the remote
database. Date: 2026-11-26.

**Status: NOT RESOLVED. Whether the run connected to the remote database is still unknown.**
- **What is ready:** the read-only investigation is prepared below.
- **What is not done:** no remote connection was made in Phase 03 or Phase 04. A read-only check in Phase 03 was blocked by the permission system, and no other route was tried.
- **What this review changes:** reading the test source shows the possible impact is **wider than recorded in Phase 03**. See §3.

## 1. Known facts

| Item | Fact |
|---|---|
| When | 2026-11-25, about 20:08–20:30 Asia/Colombo (14:38–15:00 UTC). Investigate 20:05–20:35 (14:35–15:05 UTC); widen to 14:30–15:15 UTC for clock drift |
| What ran | The first Phase 03 `pytest` run. `MONGODB_URI` and `DATABASE_NAME` were not set in the shell |
| Configuration used | `app/config/settings.py` loads `backend/.env`, so the target was the remote Atlas cluster in `.env`, database `mediconnect`. `.env` also configures SMTP, a Stripe **test** key, and Gemini and OpenAI keys. Twilio and Firebase are not configured |
| Observed behaviour | About 20 minutes of very low CPU, consistent with remote round-trips or timeouts. The run was stopped by hand |
| Not known | Whether it connected, which test modules ran, and what was written |
| Code at the time | Commit `00a47a0` (Phase 02 docs) plus uncommitted Phase 03 work. The test files are those in `00a47a0:backend/tests` (40 files) |

## 2. Prevention now in place (verified)

| Control | Evidence |
|---|---|
| `backend/tests/conftest.py` defaults the session to local `mediconnect_test` and mock Stripe keys, and refuses anything else before any app module loads | Phase 03 |
| **P04-N01 (new):** the guard parses every host. The Phase 03 prefix test accepted `localhost.example.com`, `127.0.0.1.nip.io`, `user@remote` tricks and multi-host seed lists containing a remote server. All are now refused, as are `mongodb+srv://`, non-`_test` database names (in the URI or `DATABASE_NAME`) and live Stripe keys | `tests/test_database_safety_guard.py`: 26 tests, including real subprocess runs of the conftest |
| UAT seed scripts (`seed_uat_data`, `seed_phase02/03/04_fixtures`) refuse non-local hosts and non-`_uat` names | Phase 04 seed run against `cluster0.example.net`: refused, exit 1 |
| `scripts/create_admin.py` now prints a redacted target and refuses a remote database without `--allow-remote` | P04-N01 |
| UAT scripts (Phases 02–04) connect only to `mongodb://127.0.0.1:27017/mediconnect_uat`, and only to the API at `127.0.0.1:8001` (asserted) | Script headers |
| UAT backend launcher sets the local URI and database in the process environment and refuses a non-test Stripe key | `scripts/start_uat_backend.ps1` |
| Every Phase 04 run printed its redacted target first (host `127.0.0.1`, database `mediconnect_test` or `mediconnect_uat`) | §2 of the final report |

**Not guarded, by design:** starting the backend itself with no environment still uses `backend/.env`. That is the owner's normal development configuration, and changing it is an owner decision (Phase 05, see P4-B5).

## 3. What the incident-era tests would have done if they connected

Source: every file in `00a47a0:backend/tests`. Pytest runs files in alphabetical order. The first four are:
1. `test_admin_doctor_workflow.py`
2. `test_admin_web_endpoints.py`
3. `test_ai_booking_agent.py`
4. `test_ai_care_assistant_unified.py`

### 3.1 New records with recognisable markers (inserted into `mediconnect`)

| Collection | Markers |
|---|---|
| `users` | Emails `@mediconnect.lk` with prefixes such as:<br>• `patient_`, `doctor_`, `admin_`, `other_`<br>• `patient_a_`, `patient_b_`, `patient_care1_`<br>• `dr_silva_`, `rbac_patient_`, `rbac_pat_`, `rbac_dr_`, `rbac_admin_`<br>• `stab_patient_`, `stg_admin_`, `refund_admin_`<br>• `susp_`, `suspended_`, `rej_`, `unverified_`, `unauth_doc_`, `user_wrong_pw_`<br>• `sunethra_`, `samantha_`, `second_`<br><br>Emails `@example.com`:<br>• `person@example.com`<br>• `dr.sarath.*`, `sunil_*` |
| `doctor_profiles` | `doctorId` beginning `DOC-TEST-`, `DOC-AI-`, `STAB-`, `P01-`, `DOC-TIME-1-`, `DOC-1…`, `DOC-TEST-REJ-`, `DOC-TEST-PEND-` |
| `payments` | `stripePaymentIntentId` beginning `pi_test_`, `pi_mock_`, `pi_succ_`, `pi_fail_`, `pi_status_`, `pi_reuse_`, `pi_priv_`, `pi_idem_`, `pi_hist_`, `pi_fee_`, `pi_valid_`, `pi_p02_`, `pi_live_x` |
| `prescriptions` | `RX-…`, `RX-AUDIT-…` |
| `appointments`, `doctor_availabilities`, `notifications`, `refund_requests` (`REF-…`), `support_tickets` (`TCK-…`), `clinical_notes`, `medical_records`, `care_plans`, `appointment_events`, `security_events`, `fraud_risk_assessments`, `admin_audit_logs` | Linked to the fixture users above by `patientUserId`, `doctorUserId` or `actorId` |

### 3.2 Deletions

Each targets a fixture `_id`, a fixture user id, or one of the regex prefixes below. **No test deletes a whole `mediconnect` collection.**

Two kinds of deletion could touch a pre-existing record if its value happened to match:

| Deletion | Risk |
|---|---|
| `doctor_profiles` with `doctorId` matching `^DOC-AI-`, `^DOC-TEST-`, `^STAB-` or `^P01-` | Removes any pre-existing profile with that prefix |
| `appointments` with `{"doctorId": <test doctor number>}` and `device_tokens` with `{"fcmToken": <test token>}` | Removes matching records |

### 3.3 Whole-database jobs that could change pre-existing records (not recorded in Phase 03)

| Test code | What it does on the configured database | Possible effect on real data |
|---|---|---|
| `test_ai_care_assistant_unified.py` (4th file): `with TestClient(app)` | Runs the app **lifespan**:<br>• `ensure_indexes()` on `mediconnect`<br>• starts the background worker against `mediconnect` while the module runs | The worker loop (every `REMINDER_CHECK_INTERVAL_SECONDS`) runs:<br>• `run_scheduler`: sends due reminders to **real patients**<br>• `release_expired_holds`: cancels any expired HOLD<br>• `run_confirmation_outbox`: sends booking-confirmation **email through the SMTP server in `.env`**<br>• `run_communications`: sends doctor-approved reminder batches |
| `test_phase02_booking_payment.py` | `AppointmentService.release_expired_holds(db)`, `scheduler.run_scheduler(db, …)` | Same sweeps, called directly |
| `test_phase2_booking.py`, `test_phase3_care.py`, `test_phase4_workflow.py` | Use their **own** databases `mediconnect_phase2_test`, `mediconnect_phase3_test` and `mediconnect_phase4_test` on the configured cluster, and call `drop_database()` on them | These databases may have been **created and dropped on the remote cluster**. They are separate from `mediconnect` |
| `test_doctor_reviews.py`, `test_production_security_audit.py` | `ensure_indexes()` | Index builds on `mediconnect` (no data change) |

### 3.4 External services the run could reach (independent of the database)

| Service | Possible effect |
|---|---|
| **SMTP** (configured in `.env`) | Any code path that sends email (registration OTP, approval/rejection, booking confirmation) could have sent mail. Most recipients are synthetic `@mediconnect.lk` or `@example.com` addresses. The worker in §3.3 could have emailed **real patients** whose confirmations were pending |
| **Stripe** (test key) | Test-mode calls only; no real money. Tests mostly mock Stripe |
| **Gemini / OpenAI** | AI tests that do not mock the provider could have made paid API calls with synthetic text |
| **Twilio and Firebase** | Not configured, so no SMS or push could be sent |

## 4. Read-only investigation procedure (for the owner)

**Rules:**
- Use a **read-only** database user, or Atlas Data Explorer in read-only mode.
- Run nothing below that writes. Every query is `find` or `count` only.
- Export results to a private location. Do not share patient data in tickets or chats.

Window (UTC): `S = ISODate("2026-11-25T14:30:00Z")`, `E = ISODate("2026-11-25T15:15:00Z")`.

**Step 1: did a connection happen?**
- Check Atlas **Project → Activity Feed / Access Tracking / Database Access History** for logins between 14:30 and 15:15 UTC, from the developer machine's public IP and the database user named in `backend/.env`.
- **If there was no successful authentication in the window, the incident had no database impact.** Record that and stop at step 6.

**Step 2: new records with fixture markers (`mongosh`, read-only):**
```javascript
const S = ISODate("2026-11-25T14:30:00Z"), E = ISODate("2026-11-25T15:15:00Z");
const db_ = db.getSiblingDB("mediconnect");
db_.users.countDocuments({createdAt: {$gte: S, $lte: E}});
db_.users.find({createdAt: {$gte: S, $lte: E}}, {email: 1, role: 1, createdAt: 1}).limit(200);
db_.users.countDocuments({email: /^(patient|doctor|admin|other|rbac|stab|stg|refund|susp|suspended|rej|unverified|unauth|user_wrong|dr_silva|sunethra|samantha|second)[_a-z0-9]*@mediconnect\.lk$/});
db_.doctor_profiles.countDocuments({doctorId: /^(DOC-TEST-|DOC-AI-|STAB-|P01-|DOC-TIME-|DOC-1)/});
db_.payments.countDocuments({stripePaymentIntentId: /^pi_(test|mock|succ|fail|status|reuse|priv|idem|hist|fee|valid|p02|live_x)/});
["appointments","payments","notifications","refund_requests","support_tickets","prescriptions","clinical_notes",
 "medical_records","care_plans","appointment_events","security_events","fraud_risk_assessments","admin_audit_logs",
 "doctor_availabilities","care_reminder_events"].forEach(c =>
  print(c, db_[c].countDocuments({createdAt: {$gte: S, $lte: E}})));
```

**Step 3: changes to pre-existing records.** These are records created before the window but updated inside it:
```javascript
const changed = {createdAt: {$lt: S}, updatedAt: {$gte: S, $lte: E}};
["appointments","payments","users","doctor_profiles","refund_requests","care_reminder_events","medication_reminders",
 "care_plans","notifications"].forEach(c => print(c, db_[c].countDocuments(changed)));
// Holds released by the sweep:
db_.appointments.find({...changed, status: "CANCELLED"}, {status: 1, paymentStatus: 1, cancellationReason: 1, updatedAt: 1});
// Booking-confirmation outbox entries attempted in the window (possible real emails):
db_.appointments.find({"confirmationOutbox.email.leaseUntil": {$gte: S, $lte: E}},
                      {"confirmationOutbox.email": 1, patientUserId: 1});
// Care reminders processed in the window:
db_.care_reminder_events.find({"deliveryAttempts.at": {$gte: S, $lte: E}}, {kind: 1, state: 1, channels: 1, patientUserId: 1});
// Notifications created for pre-existing users:
db_.notifications.countDocuments({createdAt: {$gte: S, $lte: E}});
// Pre-existing doctor profiles whose doctorId matches the deleted prefixes (should be none in real data):
db_.doctor_profiles.countDocuments({doctorId: /^(DOC-AI-|DOC-TEST-|STAB-|P01-)/});
```

**Step 4: other databases on the cluster:**
```javascript
db.adminCommand({listDatabases: 1}).databases.map(d => d.name);
// Look for mediconnect_phase2_test / mediconnect_phase3_test / mediconnect_phase4_test (created or dropped by tests).
```

**Step 5: indexes.** Compare `db_.<collection>.getIndexes()` with the list in `app/models/*` and `ensure_indexes()`. New indexes are harmless, but a failed unique-index build would be logged in the Atlas logs.

**Step 6: external providers in the window:**
- SMTP provider sent-mail log, filtered to 14:30–15:15 UTC.
- Stripe Dashboard (test mode) → Developers → Logs. These are test mode only.
- Google AI Studio / Gemini and OpenAI usage pages, for request counts in the window.

## 5. Assessment checklist

| # | Question | Answer (owner) |
|---|---|---|
| 1 | Successful authentication from the developer IP in the window? | |
| 2 | Records with fixture markers created in the window (count per collection)? | |
| 3 | Pre-existing records updated in the window (count per collection)? | |
| 4 | Holds released or appointments cancelled by the sweep? | |
| 5 | Real patients emailed by the outbox or reminder worker (SMTP log)? | |
| 6 | Pre-existing doctor profiles matching the deleted prefixes? | |
| 7 | `mediconnect_phase*_test` databases present or recently dropped? | |
| 8 | Paid AI provider calls in the window? | |
| 9 | Overall: no impact / test data only / pre-existing data changed / patients contacted | |

## 6. If remediation is needed (separate, reviewed plan; nothing is run without owner approval)

1. **Backup first.** Take an Atlas on-demand snapshot of the cluster and note its id. Also export the affected documents with `mongoexport`, using the exact queries from §4.
2. **Identify by evidence, never by pattern alone.** Build an `_id` list from the exports. A record is removed only when it was created in the window **and** carries a fixture marker. Pre-existing records that were modified are **restored field by field** from the snapshot, not deleted.
3. **Review.** The owner and a second reviewer sign off the `_id` list and the restore plan.
4. **Apply in a transaction or in small batches.** Use `deleteMany({_id: {$in: [...]}})`, and `updateOne` with the snapshot values, each logged.
5. **Verify.** Re-run the §4 counts; expect 0 fixture records and no unexpected `updatedAt` values in the window.
6. **Rollback.** Restore the exported documents with `mongoimport --mode=upsert`, or restore the snapshot.
7. **Patients contacted.** If real patients received messages, the owner decides on communication. The likely content was standard booking confirmations or reminders, not clinical content.
8. **Credentials.** Rotate the SMTP password and the Gemini and OpenAI keys. This was already recommended after the Phase 02 disclosure. Rotate the database user password if the access logs show any unexpected use.

## 7. What Phase 04 did not do

- No connection to the remote database, no change to `backend/.env`, no deletion or migration anywhere outside `mediconnect_test` and `mediconnect_uat`.
- **The incident is not closed.** It stays **P4-B1 (owner action, urgent)** until §5 is answered.
