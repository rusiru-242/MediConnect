# A02 — Remaining Blockers and Owner Actions

For: the project owner. 2026-11-26, branch `fix/agents-a02-reminders-notifications`.

Engineering work for Agents 05, 07, 08, 09, 13 and 19 is complete for everything that can run locally:

- in-app notifications;
- the scheduler and worker;
- device-local reminders on the emulator;
- local SMTP;
- authorization.

What remains needs external accounts, an owner decision, a reviewer or a physical device. No external delivery is claimed.

## Owner actions

| # | Action | Unblocks | Notes |
|---|---|---|---|
| 1 | **Rotate the MongoDB credentials (P5-C1)** and run the remote incident inspection (P4-B1) | Staging and anything beyond | Still the top security blocker. A02 did not touch it, did not connect to the remote cluster and did not change credentials. |
| 2 | Rotate the SMTP, Gemini and OpenAI credentials (P4-B2) | Any external e-mail; staging | The SMTP credentials in `backend/.env` were also used by the test suite until A02-BUG-002. Before A02, every local run of the backend suite tried to submit doctor-approval e-mails through that account (13 connection attempts per run). |
| 2a | **Check the SMTP account's Sent and bounce folders** for test messages | Knowing whether earlier test runs e-mailed a third party | The recipients were synthetic addresses at `@mediconnect.lk`. Unless the project controls that domain, earlier runs may have delivered synthetic doctor-approval messages (fake names, no patient data) to, or been bounced by, another organisation's mail server. CI was not affected (CI has no `.env`). I could not check this: I did not log in to the mailbox. |
| 3 | **Create a Firebase project and configure Android** (see `A02_EXTERNAL_INTEGRATION_REPORT.md`) | A02-N02, N03, N04, I02, I03 and M10 (FCM acceptance and device receipt) | FCM itself has no charge. A service-account JSON stays outside the repository; start UAT with `-EnablePush`. The emulator has Google Play services. |
| 4 | iOS push: Apple Developer account, APNs key in Firebase, Push Notifications capability, `remote-notification` background mode, `GoogleService-Info.plist`, **physical iPhone** | iOS push | None of these exist in the repository. No iPhone verification is claimed. |
| 5 | E-mail sandbox or a transactional provider with a verified domain (SPF/DKIM), plus a decision to send synthetic test mail | A02-I05 external e-mail delivery | On 2026-11-26 the owner chose local SMTP only. |
| 6 | Approve and provide an SMS provider (Twilio test credentials, Messaging Service, one verified synthetic test number) | A02-I07 SMS delivery | A paid service; not enabled. |
| 7 | Decide on exact alarms for device-local reminders (`SCHEDULE_EXACT_ALARM` / `USE_EXACT_ALARM`, Play policy) | Minute-exact device reminders | Inexact alarms can be late (Android window; observation A02-O2). |
| 8 | Product decision on doctor-to-patient messaging beyond fixed templates | Agent 19 free-text instructions, prescription-availability and renewal messages by e-mail/SMS | Only fixed, private templates exist: doctor-approved reminder batch, care-plan change notices, renewal decision in-app. No free-text clinical messaging was added (deliberately). |

## Human review gates

| Gate | Scope | Item |
|---|---|---|
| Clinical review | Reminder timing rules (24 h / 2 h appointment, 7 d / 1 d / due-day follow-up at 09:00), the "missed dose" wording ("ask your pharmacist or the prescribing doctor"), follow-up notice wording | B1 |
| Pharmacist review | Which prescription frequency phrases may produce patient-set reminders (`prescribed_doses_per_day`), PRN/weekly exclusion | B2 |
| Physical device | Device-local reminders and (once configured) push on a real Android phone: Doze, battery optimisation, OEM restrictions, reboot | B10 |
| Native Sinhala/Tamil review | Notification and SMS texts are English only | B12 |

## Open observations

- **A02-O1 to O5:** see `A02_BUG_FIX_REPORT.md`. They cover the legacy 24 h / 1 h reminder method, inexact device alarms, strict phone normalisation with English-only SMS, two index-dependent tests in isolation, and the fixed-template communication.
- Previous observations A01-O1 to O4 remain open.

## Not done in A02 (and why)

| Item | Why |
|---|---|
| FCM acceptance and device receipt (N02–N04, I02, I03, M10) | Firebase not configured (action 3). Push payload, outcome tracking and token handling are verified with SDK test doubles only. |
| External e-mail (I05) | Owner decision: local SMTP only (action 5). |
| SMS (I06 live, I07) | No provider (action 6). |
| Booking-cancellation, refund and reschedule **e-mails** | Not implemented: these events notify in-app (and by push once configured) only. Reported as missing functionality, not added in A02. |
| Follow-up 7 d / 1 d / due-day reminders **live** | They fire at 09:00 Asia/Colombo, and the live run was in the evening. Verified with automated tests on local MongoDB with an injected clock; the live run verified the plan's test-task reminder and change notices instead. |
| iPhone | No device, account or configuration (action 4). |
