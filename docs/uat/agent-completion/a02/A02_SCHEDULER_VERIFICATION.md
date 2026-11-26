# A02 — Durable Scheduler and Worker Verification

For: engineers and reviewers. 2026-11-26.

## How the scheduler works (verified, not assumed)

```mermaid
flowchart LR
  W[Worker loop in each backend process\nevery REMINDER_CHECK_INTERVAL_SECONDS = 60] --> M[materialize: upsert one event per\nsource occurrence, id = sha256 of source, kind,\ntime, version]
  M --> C[claim: find_one_and_update\npending → sending, attempts+1, lease 3 min]
  C --> R{source still valid?\ncurrent_source revalidation}
  R -- no --> X[cancelled]
  R -- yes --> D[per channel: mark sending → deliver → record\ninApp · push · email · sms]
  D --> P[processed, or pending with back-off\n2^attempts min, max 4 attempts]
  L[lease expired] --> RC[recover_interrupted:\ninApp sending → re-run (unique key)\nexternal sending → uncertain, never re-sent]
```

- **Sources:**
  - confirmed appointments (24 h and 2 h before, Asia/Colombo);
  - care plans (follow-up 7 days, 1 day and the due day at 09:00 Colombo; task due times);
  - clinician-approved medication schedules (approved times in the patient's zone, inside start/end, only while the prescription revision is unchanged);
  - patient measurement schedules.
- **Exactly once (logical):**
  - The event id is deterministic, so a restarted or concurrent worker materialises the same row.
  - The claim is atomic.
  - The in-app write has a unique `idempotencyKey` (`care_<event>_<snoozes>`).
  - Every state change is conditional on the claimed `attempts` value, so a stale worker cannot overwrite a newer result.
- **External providers:**
  - There is no exactly-once guarantee. A request whose result is unknown (timeout after sending, crash in flight, SMTP connection lost after DATA, 5xx from Twilio) is recorded as `uncertain` and is **never re-sent automatically**.
  - Only failures that happened *before* the request could have been accepted are retried: connection refused, connect timeout, SMTP 4xx, Twilio 429.

## Matrix A02-S01 to S08

| ID | Check | Automated (local MongoDB, real processes where stated) | Live (UAT 8001, real 60 s worker) | Status |
|---|---|---|---|---|
| A02-S01 | Actual job execution | P05 `test_s06h`, A02 `test_bug004_unconfigured_channels…` | A02-M03: medication reminder executed 47 s after the approved time (one worker cycle); A02-T03 test task; A02-A01 appointment 2 h reminder | **PASS** |
| A02-S02 | Worker restart | P05 `test_s06ab` (restarted worker does not re-deliver) | `a02_worker_uat.py`: backend restarted while two reminders were pending; see `evidence/a02_worker_restart_race.json` | see live file |
| A02-S03 | Multi-process claiming | P05 `test_s06de`: **3 real processes**, 12 reminders, each delivered by exactly one process | Two extra scheduler processes competed with the backend worker on `mediconnect_uat`; exactly one in-app attempt per occurrence | see live file |
| A02-S04 | Worker crash recovery | A02 `test_s04_real_worker_crash_mid_delivery…`: a real subprocess dies (`os._exit`) with the in-app channel `sending`. Not touched before the lease expires; then delivered **once** (`recoveries = 1`). P05 `test_s06c` (changed): push in flight → `uncertain`, not re-sent | — | **PASS** (fixed A02-BUG-005) |
| A02-S05 | Duplicate prevention | P05 `test_s06ab`, `test_s06de`; booking outbox runs twice and sends once | A02-S05 live: 0 duplicate groups across the run; A02-M04 repeated request id → one audit entry; A02-C05 batch approved twice → queued once | **PASS** |
| A02-S06 | Cancellation | P05 `test_s06f`; Phase 3 tests (prescription change → 410) | A02-M08 discontinued schedule leaves the agenda; A02-A03/A04 rescheduled-then-cancelled appointment created **no** reminder event; A02-F04 closed plan removes its tasks | **PASS** |
| A02-S07 | Timezone boundaries | P05 `test_s06h` (a reminder due on a different Colombo date than the appointment; independent of the machine zone); A02 `test_s07_colombo_midnight_boundary…` | A02-M03 / A02-A02: stored times equal the approved Colombo times | **PASS** |
| A02-S08 | Permanent failure | A02 `test_s08_permanent_failure_after_bounded_retries`: 4 attempts, then `failed` (bounded back-off 2, 4, 8 min) | — | **PASS** |

## Heartbeat and monitoring

- **Heartbeat:** each cycle records a `reminder_care_worker` heartbeat (duration, failures). The Phase 04/05 platform monitoring shows it; not changed in A02.
- **Monitoring counts:** the notification monitoring endpoint now counts care events per channel as delivered (in-app), accepted, disabled, skipped, failed and uncertain. Interrupted external sends appear as `uncertain` (verified in P05 `test_s06c`).

## Limits that remain

- **Deployment:** the worker runs inside every API process. Safe, because claims are atomic, but a dedicated worker deployment is an operations decision.
- **Late reminders:** an event is dropped as `expired` 4 hours after it was due (appointment reminders expire at the appointment time). A worker outage longer than that loses those reminders by design (no stale reminders), and the drop is visible in monitoring.
- **External outcomes:** an `uncertain` external delivery needs a human decision. The admin retry endpoint re-queues only `failed` or `disabled` booking confirmations.
