# A02 — External Integration Report (Firebase push, e-mail, SMS)

For: the project owner, who has to provide the external accounts, and engineers. 2026-11-26.

## Result in one table

| Channel | Code path | Configured here? | What was verified | External delivery | Status |
|---|---|---|---|---|---|
| **In-app notifications** | `notifications` collection, worker-written | Yes (local MongoDB) | Live on UAT 8001 with the real worker: creation, recipient, unread count, mark read, isolation, deep-link target | Not applicable (stored in the app) | **VERIFIED (local)** |
| **Device-local reminders (Android)** | `flutter_local_notifications` | Yes (no external service) | Emulator API 37: scheduled alarms, notification posted at 19:48 and 19:49, logout cleanup 8 → 0 | Not external; shown on the emulator | **VERIFIED (emulator)**; physical phone not tested |
| **Firebase Cloud Messaging (push)** | `NotificationService._send_fcm_push` (Admin SDK 7.7.0), `FcmService` (Flutter) | **No.** No Firebase project, `google-services.json`, Gradle plugin or service account; the app logs `Failed to load FirebaseOptions` on every start | Payload privacy, outcome tracking, token rules and cleanup with SDK test doubles; token API live on 8001 | **Not attempted.** FCM acceptance and device receipt both BLOCKED | **BLOCKED (B4, owner)** |
| **SMTP e-mail** | `EmailService._send_email` | Credentials exist in `backend/.env` (pending rotation, P4-B2) but are **not used**: the owner chose local-only testing | Real SMTP conversations with a local server on 127.0.0.1 (plain, STARTTLS with a self-signed certificate, refusals, drop after DATA, 451). Booking confirmation end to end through the outbox | **Not attempted** (owner decision 2026-11-26) | Integration **VERIFIED (local SMTP)**; external delivery **BLOCKED (owner)** |
| **SMS (Twilio)** | `booking_notifications.send_confirmation`, `care_scheduler.deliver` | **No.** No Twilio account; UAT blanks the variables | Normalisation, consent, disabled behaviour; Twilio responses with test doubles (Phase 02/05 tests) | **Not attempted** | **BLOCKED (B5, owner)** |

**"Accepted" is never "delivered".** In the database and in the admin monitoring page, `accepted`/`sent` means the provider accepted the request. `delivered` is used only for an in-app record or a provider delivery receipt (Twilio `delivered`). FCM does not report device receipt to the server, so device receipt can only be shown on a device.

## Firebase Cloud Messaging

### What exists

- **Backend:**
  - Initialises the Admin SDK only from `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_SERVICE_ACCOUNT_JSON`. Sends a multicast to the user's registered tokens (`android.priority=high`, channel `mediconnect_general`, APNs sound).
  - Lock-screen text is now generic (A02-BUG-006). The outcome is stored per notification (A02-BUG-009). Only permanent token errors remove tokens (A02-BUG-007).
- **Flutter:**
  - `firebase_core 4.x`, `firebase_messaging 16.x`.
  - Background handler, token refresh → `POST /notifications/devices`.
  - Handles foreground (snackbar), background tap (`onMessageOpenedApp`) and terminated-app tap (`getInitialMessage`).
  - Deep links: care reminder → care agenda; appointment → appointment detail (doctor view for doctors, BUG-060); payment → payments.
  - Logout removes the token at the backend and deletes it at FCM (A02-BUG-017).
- **Tokens:**
  - Multiple devices per account (≤ 10).
  - A token registered by a new account is removed from the previous account (same device).
  - A user cannot remove another user's token (verified live, A02-N08/N09).

### What is missing (owner)

1. A Firebase project (the FCM HTTP v1 API has no charge; no paid plan is needed for FCM).
2. **Android:**
   - Register app id `com.mediconnect.mediconnect`.
   - Either run `flutterfire configure` (creates `lib/firebase_options.dart`; then pass `options: DefaultFirebaseOptions.currentPlatform` to `Firebase.initializeApp`), or place `google-services.json` in `mobile/android/app/` (already git-ignored) and add the `com.google.gms.google-services` Gradle plugin.
3. **Backend:**
   - Create a service account with the *Firebase Cloud Messaging API Admin* role and keep the JSON **outside the repository** (`firebase-adminsdk*.json` is git-ignored).
   - Start UAT with `-EnablePush` and `FIREBASE_CREDENTIALS_PATH=<path>`. A02 added this switch; without it the launcher blanks Firebase.
4. **Emulator:** the available AVD (API 37) has Google Play services (`com.google.android.gms` present), so token generation and receipt can be verified once 1–3 are done.
5. **Verification steps once configured:**
   1. Sign in as a synthetic UAT patient on the emulator.
   2. Confirm `device_tokens` has one row.
   3. Approve a medication schedule two minutes ahead.
   4. Check `channels.push.status = accepted` (FCM acceptance).
   5. Observe the notification on the device with the app in the foreground, the background and terminated (device receipt), and tap each.

### iOS (not verifiable here)

- Missing:
  - `GoogleService-Info.plist`;
  - the `remote-notification` background mode in `Info.plist`;
  - a `Runner.entitlements` file with `aps-environment`;
  - Firebase/`UNUserNotificationCenter` set-up in `AppDelegate.swift`.
- Required from the owner: an Apple Developer account, an APNs authentication key uploaded to Firebase, the Push Notifications capability, and a **physical iPhone** (the simulator does not receive remote pushes for this set-up).
- **No iPhone verification is claimed.**

## E-mail (SMTP)

- **Authorisation:** on 2026-11-26 the owner chose **local SMTP only**, so no message was sent through the Gmail account in `backend/.env`.
- **TLS (A02-BUG-001):** certificate and host-name verification are now on. The local test showed that an untrusted self-signed certificate is refused (`retry`, `tls_failed`) and that the same server is accepted once its CA is trusted via `SMTP_CA_FILE`.
- **Outcomes (A02-BUG-003):**

  | Case | Result |
  |---|---|
  | accepted | `sent` |
  | invalid recipient (550) | `failed`, `recipient_refused` |
  | connection refused | `pending`, `connection_failed`, retried with back-off, at most 5 attempts |
  | 451 | `pending` |
  | connection lost after DATA | `uncertain` (never re-sent automatically) |
  | not configured | `disabled` |

- **Templates:** the booking confirmation (doctor, specialty, Asia/Colombo time, clinic, payment state, reference) was rendered and received by the local server. It is UTF-8 MIME (multipart/alternative, HTML escaped). OTP, password reset and doctor approval/rejection templates are unchanged.
- **Duplicate prevention:** the booking outbox runs twice and sends once (attempts = 1).
- **Not done:**
  - refund e-mail: there is no refund e-mail template; refunds notify in-app only;
  - external delivery, SPF/DKIM/DMARC and spam placement.
- **Owner requirements for external e-mail:**
  1. Rotate the SMTP credentials (P4-B2).
  2. Use a sandbox inbox service, or a transactional provider with a verified sending domain (SPF, DKIM).
  3. Start UAT with `-EnableEmail`.
  4. Map synthetic `@uat.mediconnect.lk` recipients to the sandbox.
  5. Confirm receipt in the sandbox; only receipt there is evidence of delivery.

## SMS

- **Adapter:** Twilio Messages API with a Messaging Service SID; status polling (`accepted`/`sent`/`delivered`/`failed`); 429 retried, 5xx `uncertain`, other 4xx `failed`.
- **Consent:**
  - booking SMS requires `smsConsent` and a SHA-256 fingerprint of the consented number;
  - care SMS requires `careSms` and a matching `careSmsPhoneHash`;
  - medication reminders never go by SMS.
- **Numbers:** `0771234567`, `077 123 4567` and `+94771234567` → `+94771234567`. Landlines (`011…`) are refused, as are `94…`/`0094…` without the plus sign (observation A02-O3).
- **Templates:** English only and private. A booking SMS of about 120–150 characters can take 2 segments. Sinhala/Tamil SMS (UCS-2, 70 characters per segment) is not implemented.
- **Not configured:** the result is `disabled` (was `failed`); verified with automated tests (`test_i06_i07_…`).
- **Owner requirements:**
  1. Approve a (paid) SMS provider; Twilio needs a Messaging Service, and Sri Lanka sender-ID rules apply.
  2. Provide test credentials and one verified synthetic test number.
  3. Only then enable `careSms` for one synthetic patient.
- **No SMS was sent and none is claimed.**

## Provider dependency matrix (A02 components)

| Component | In-app | Push (FCM) | E-mail | SMS | Device-local |
|---|---|---|---|---|---|
| 05 Medication Reminder | ✔ worker | optional (blocked) | never | never | patient-created reminders (✔ emulator) |
| 07 Appointment Reminder | ✔ worker (24 h / 2 h) | optional (blocked) | if `careEmail` + verified e-mail (disabled) | if `careSms` + consented number (blocked) | — |
| 08 Follow-up Reminder | ✔ worker (7 d / 1 d / due, 09:00 Colombo) | optional (blocked) | as above | as above | — |
| 09 Medical Test Reminder | ✔ worker (task due time) | optional (blocked) | as above | as above | — |
| 13 Notification Assistant | ✔ list, count, read state, preferences | blocked | booking confirmations (local SMTP ✔, external blocked) | booking confirmations (blocked) | — |
| 19 Patient Communication | ✔ doctor-approved batch, plan change notices | blocked (generic preview ready) | — | — | — |
