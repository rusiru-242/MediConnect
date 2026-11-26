# A02 — Notification and Patient Communication Verification (Agents 13, 19)

For: the project owner and engineers. 2026-11-26.

## Delivery-state vocabulary

The prompt's states map to stored values as follows. A disabled provider is never shown as delivered.

| Required state | Stored value(s) | Where |
|---|---|---|
| Created | notification document exists | `notifications` |
| Queued | `pending`, `retry` | outbox entries, `care_reminder_events.state`, channels |
| Processing | `sending` (with a lease) | events, channels, outbox |
| Provider accepted | `accepted` (FCM, Twilio, SMTP for care e-mail), `sent` (SMTP for booking e-mail) | channels, outbox; monitoring column "Provider accepted" |
| Delivered (with evidence) | `stored` (in-app record written), `delivered` (Twilio receipt only) | monitoring column "Delivered / stored" |
| Failed | `failed`, `dead_lettered` | — |
| Skipped | `skipped` (preference or consent), `no_device`, `cancelled`, `expired` | — |
| Disabled | `disabled` (provider not configured; Firebase, SMTP or Twilio missing) | **new in A02** (A02-BUG-004) |
| Unknown | `uncertain` (result unknown; never re-sent automatically) | — |

FCM never reports device receipt to the server. "Push accepted" therefore means FCM accepted the message; receipt can only be shown on a device.

## Agent 13 — Notification lifecycle

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A02-N01 | In-app notification | Live: every reminder and change notice was stored for the right recipient. The list endpoint returns them newest first | **PASS** |
| A02-N02 | Foreground push | `FcmService` shows a snackbar with a "View" action (code inspected). No push can be sent: Firebase not configured | **BLOCKED** |
| A02-N03 | Background push | `onMessageOpenedApp` routing (code); not executable without Firebase | **BLOCKED** |
| A02-N04 | Terminated-app push | `getInitialMessage` routing after the first frame (code); not executable without Firebase | **BLOCKED** |
| A02-N05 | Deep-link navigation | Emulator: tapping a care-reminder notification opened the exact occurrence (Synthoworker1, 8:07 PM Sri Lanka, clinician dose). Tapping an appointment notification opened that appointment's **current** state (CANCELLED), not the stale text. Live: event detail → booked appointment (A02-A06) | **PASS** (in-app list); push-tap BLOCKED |
| A02-N06 | Unread count | Live: the count grew from the baseline; exactly one less after marking one read | **PASS** |
| A02-N07 | Mark as read | Live: mark one (200, count −1); mark all (count 0). Patient B marking A's notification → 403 | **PASS** |
| A02-N08 | Device token refresh | Live: register, refresh (new token) and account switch on the same device token (only B owns it afterwards); bad device type 422; at most 10 devices (automated) | **PASS** (backend); FCM token generation BLOCKED |
| A02-N09 | Logout and token removal | Live: DELETE removes the user's own token (1) but never another user's (0). Emulator: logout cancelled 8 device reminder alarms → 0. The app also deletes the FCM token at FCM when Firebase is configured (code; not executable here) | **PASS** (backend + device reminders) |
| A02-N10 | Cross-account isolation | Live: B cannot see, mark or act on A's notifications or reminder events (403/404); the assistant's unread list contains only the asker's own notifications (automated) | **PASS** |

**Other required checks:**
- **Category and entity:** every notification has a `type` and the related appointment, payment or care-event id. The mobile app routes by those ids. A care reminder opens the care agenda event, and a deleted or changed source returns 410 "no longer scheduled" instead of stale details (Phase 3 tests).
- **Consent and channel preferences:**
  - `pushNotifications`, `reminder24h`, `reminder2h` and `careReminders` are honoured (automated P05/A02).
  - `careEmail` needs a verified e-mail; `careSms` needs a valid mobile number, and the fingerprint is stored.
- **Duplicate prevention:** unique `idempotencyKey` on notifications; 0 duplicates in the live run.
- **Privacy:** reminder texts are private. Push previews are generic (A02-BUG-006); e-mail and SMS texts contain no diagnosis, clinical note or prescription content. Booking e-mail/SMS include doctor, date and clinic, which is the purpose of the confirmation.

## Agent 19 — Patient communication

| ID | Scenario | Evidence | Status |
|---|---|---|---|
| A02-C01 | Authorized doctor message | Live: the doctor previews today's reminder batch (fixed text, only consenting patients with confirmed future appointments) and approves it with the HMAC token. The message is stored in-app for the patient | **PASS** |
| A02-C02 | AI draft review where supported | Live: the doctor assistant ("Draft reminders for my appointments today") returns "Draft ready for 1 eligible appointments. Review it before approving." Nothing is sent without the explicit approve call. The "AI" draft is a fixed template, not LLM text (A02-O5) | **PASS** (fixed-template draft) |
| A02-C03 | Correct recipient | Live: recipients are derived server-side from the doctor's own confirmed appointments; the stored notice is for patient A only | **PASS** |
| A02-C04 | Unauthorized communication rejection | Live: patient 403, pending doctor 403, `confirm:false` 422, forged token 409. Other doctors only ever see their own appointments | **PASS** |
| A02-C05 | Duplicate message prevention | Live: approving the same batch twice queued it once (event id = appointment and version) | **PASS** |

**Communication types:**

| Communication | Behaviour |
|---|---|
| Appointment confirmation | In-app plus outbox e-mail/SMS (A02-I04 local SMTP) |
| Cancellation and rescheduling | In-app only; no e-mail or SMS template exists |
| Follow-up instructions and care plan updates | In-app, generic, once per version (A02-BUG-014) |
| Medical test assignments | Part of the plan notice; details only in the app |
| Prescription availability | In-app "New prescription available" for the clinical workflow (A02-BUG-021; the live run found none was sent before) and "Digital Prescription Issued" for the consultation path |
| Renewal decisions | In-app |

Free-text doctor-to-patient clinical messaging does **not** exist and was not added (owner product decision, blockers action 8).

## Emulator (Android API 37, debug APK built from this branch)

Before any input I checked that `com.mediconnect.mediconnect` was in the foreground (`emu.py`). The only non-MediConnect window was the Android permission dialog. I checked its identity (`permissioncontroller/GrantPermissionsActivity`) and made one guarded tap on Allow.

| Step | Observation | Screenshot (`evidence/emulator/`) |
|---|---|---|
| Sign in (synthetic Patient A) | Dashboard with unread badge; the restored session re-planned device reminders (alarms 0 → 8 after A02-BUG-018) | `a02_01`, `a02_07` |
| Medicine reminders | Today shows the patient-created reminder; My Medications syncs the device | `a02_02`, `a02_03` |
| Permission | Before A02-BUG-020, `POST_NOTIFICATIONS granted=false` and the app had importance NONE (an alarm fired, nothing was shown). After the fix the system prompt appeared and was granted | `a02_04` |
| Device reminder shown | Notifications posted at 19:48 and 19:49 with the app in the background: "Medication Schedule Reminder / It's time to check your medication schedule." (no medicine name) | `a02_05` |
| Logout | Device reminder alarms 8 → **0** | `a02_06` |
| Notification list | Newest first, private texts, unread filter 3 | `a02_08` |
| Tap care reminder | Opens the exact occurrence with the clinician dose (in-app only) | `a02_09` |
| Mark as Taken on the device | "Status: taken (patient-reported)"; DB `action: taken`, 1 audit entry | `a02_10` |
| Tap appointment notification | Current appointment state (CANCELLED), doctor and clinic | `a02_11` |
| Mark all read | Unread 0; dashboard badge gone | `a02_12` |
| Assistant in the app | "Show my missed medicine reminders." → doses with no recorded action from the patient's records; "Show my unread notifications." → "You have no unread notifications." | `a02_13`, `a02_14` |

**Not possible on the emulator:**
- Foreground, background and terminated **push** (no Firebase).
- Behaviour on a physical phone (Doze, OEM battery restrictions).
- iOS.
