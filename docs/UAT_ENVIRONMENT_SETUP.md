# MediConnect — UAT Environment Setup

For: the project owner running manual UAT ([MANUAL_UAT_TEST_PLAN.md](MANUAL_UAT_TEST_PLAN.md)) on this Windows machine with an Android phone.
Branch: `fix/comprehensive-system-ai-stabilization`. Prepared 2026-11-24.

## 1. Read this first: two backends exist on this machine

| | Existing dev backend | **UAT backend (use this)** |
|---|---|---|
| Port | 8000 (`uvicorn --reload`, started by you earlier) | **8001** |
| Database | Atlas cluster from `backend/.env`, database `mediconnect` (production-like; **do not use for UAT**) | **local MongoDB, database `mediconnect_uat`** (synthetic data only) |
| Admin web | `http://localhost:5173` (calls port 8000) | **`http://127.0.0.1:5174`** (calls port 8001) |

Do not run `adb reverse tcp:8000 tcp:8000` during UAT. The phone must only reach port 8001.

## 2. What the UAT backend enforces

`backend/scripts/start_uat_backend.ps1` sets these for the backend process only; `backend/.env` is **not** modified.

| Setting | UAT value | Why |
|---|---|---|
| Database | `mongodb://127.0.0.1:27017/mediconnect_uat` | Isolated from Atlas |
| Stripe | refuses to start unless keys are `sk_test_` / `pk_test_` | Never live payments (verified: `livemode: false`) |
| `AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED` | `false` | No medicine photos leave the machine until privacy approval |
| AI provider | deterministic engine (default) | Gemini and OpenAI both currently unusable (see §6) |
| `GEMINI_MODEL` | `gemini-flash-latest` | `.env` names the retired `gemini-1.5-flash` |
| SMTP | disabled | Synthetic accounts are never emailed |
| Firebase | not configured | Push cannot be tested yet (see §6) |
| JWT secret | random 64-character secret in git-ignored `backend/uat.env` | `.env` has an 11-character secret |
| CORS | adds `http://localhost:5174`, `http://127.0.0.1:5174` | UAT admin web |
| `ENVIRONMENT` | `staging` | |

## 3. Start everything (exact commands)

Open three PowerShell windows in `C:\Users\REDTECH\Downloads\MediConnect`.

**Window 1: UAT backend.** It seeds missing synthetic data, then serves on 127.0.0.1:8001.
```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1
# options: -SkipSeed   -SeedOnly   -AiProvider gemini|openai   -EnableEmail
```
Check: open `http://127.0.0.1:8001/health/ready`. Expect `"database":"connected"`; `/health` should report `"environment":"staging"`.

**Window 2: UAT admin dashboard**
```powershell
cd admin-web
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8001/api'
npx vite --port 5174 --strictPort --host 127.0.0.1
```
Open `http://127.0.0.1:5174` and sign in as `uat.admin@uat.mediconnect.lk`.

**Window 3: Android phone over USB**
```powershell
adb devices                                # phone must be listed (enable USB debugging)
adb uninstall com.mediconnect.mediconnect  # removes any saved server URL from earlier installs
adb reverse tcp:8001 tcp:8001              # phone 127.0.0.1:8001 -> this PC
adb install mobile\build\app\outputs\flutter-apk\app-debug.apk
```
The APK at `mobile/build/app/outputs/flutter-apk/app-debug.apk` was built with `--dart-define=API_BASE_URL=http://127.0.0.1:8001`. To rebuild:
```powershell
cd mobile
flutter build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8001
```
Or run directly with hot reload:
```powershell
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8001
```
- **Emulator instead of a phone:** use `--dart-define=API_BASE_URL=http://10.0.2.2:8001` and skip `adb reverse`.
- **Why uninstall first:** the app keeps a previously saved server URL and prefers it over the build-time URL. A reinstall over an older install could still talk to port 8000.
- **Wi-Fi without USB is not recommended:** the Android network-security config lists IP ranges such as `192.168.0.0/16` as *domain names*, which Android does not treat as ranges, so plain-HTTP calls to a LAN IP are likely blocked. Use USB with `adb reverse`.

## 4. Synthetic test accounts (database `mediconnect_uat`)

- All accounts share one password, stored as `UAT_PASSWORD` in `backend/uat.env` (git-ignored; open it locally).
- All emails end with `@uat.mediconnect.lk`. Email sending is disabled, so password reset and OTP flows cannot be tested in UAT.
- Re-running the seed never changes or deletes existing records; it only adds what is missing.

| Email (prefix) | Role | Data |
|---|---|---|
| `uat.patient1` | Patient | main test patient |
| `uat.patient2` | Patient | isolation and second-booker tests |
| `uat.admin` | Admin | admin web |
| `uat.doctor.cardio` | Doctor (approved) | Cardiology, Colombo, LKR 2,000, 12 years, rating 4.7 (3 reviews) |
| `uat.doctor.cardio2` | Doctor (approved) | Cardiology, Colombo, LKR 3,500, 20 years |
| `uat.doctor.derm1` | Doctor (approved) | Dermatology, Colombo, LKR 3,000, 22 years, rating 4.7 |
| `uat.doctor.derm2` | Doctor (approved) | Dermatology, Colombo, LKR 2,500, 6 years, rating 4.7 |
| `uat.doctor.derm3` | Doctor (approved) | Dermatology, Colombo, LKR 2,000, 30 years, rating 3.7 (below 4.5) |
| `uat.doctor.neuro` | Doctor (approved) | Neurology, Colombo, LKR 2,500; extra window **2026-12-05 15:00–18:00** |
| `uat.doctor.gp` | Doctor (approved) | General Practice, Colombo, LKR 1,500 |
| `uat.doctor.pending1`, `uat.doctor.pending2` | Doctor (**pending**) | For admin approve and reject (A-02) |
| `uat.reviewer1` to `uat.reviewer3` | Patient | Authors of the seeded reviews; not needed for testing |

**Availability:** every approved doctor has windows 09:00–12:00 and 14:00–17:00 (Sri Lanka time) for the next 10 days, plus the neurology window above.

**Not seeded** (create them during UAT through the doctor flows in D-05 to D-08): care plans, medication schedules, prescriptions, medical records and appointments.

## 5. Pre-UAT verification performed (2026-11-24)

| Check | Result |
|---|---|
| Branch / working tree | `fix/comprehensive-system-ai-stabilization`, clean, in sync with origin |
| UAT backend health | `/health/ready` ready, `/health/live` live, `/health` environment = staging |
| Logins | patient, doctor and admin all 200 |
| Emergency (Romanized Sinhala) | escalated with 1990 guidance |
| Romanized budget search | only LKR 2,000 cardiologist returned (3,500 excluded) |
| Rating + experience ranking | derm1 (22 years) before derm2 (6 years); derm3 (3.7) excluded |
| Neurologist Dec 5, 4 pm | booking proposal prepared |
| Doctor calendar Dec 2026 | Dec 5 AVAILABLE, 6 slots |
| Patient and doctor GET endpoints (34) | no server errors |
| Admin endpoints used by admin web (15) | all 200 after fixing BUG-041 |
| Cross-patient isolation | patient2 gets 404 for patient1's chat |
| Stripe | test mode; LKR 1,500 hold created; LKR PaymentIntent created; test publishable key; hold cancelled |
| Admin web 5174 | serves, CORS allowed |
| `flutter analyze` | no issues |
| `flutter build apk --debug` | built |
| Backend tests (after BUG-040/041 fixes) | 425 passed, 0 failed, 0 skipped |

**Defects found and fixed during preparation:**
- **BUG-040:** after an emergency message, the next messages in the same chat (even a doctor search) were re-escalated. The context rule now applies only to short follow-ups and symptom updates.
- **BUG-041:** Admin → Refunds always returned HTTP 500, because a `@classmethod` was missing `cls`.

## 6. Blockers and configuration problems

| # | Item | Impact | Action needed by owner |
|---|---|---|---|
| 1 | **No dedicated staging database.** `.env` points to Atlas `mediconnect`, which looks like the real data. | UAT runs on the isolated local `mediconnect_uat` instead. | Provide a separate staging cluster or database if UAT must run off this PC. |
| 2 | **Gemini free-tier daily quota exhausted** (20 requests/day; reset in about 15 h). `gemini-1.5-flash` is retired. `gemini-2.5-flash` and `gemini-2.5-flash-lite` return 404 for this key. Only `gemini-flash-latest` works. | Live Gemini tests are blocked today. UAT uses the deterministic engine, which covers all stabilization fixes. | Enable billing or wait for the quota reset. Set `GEMINI_MODEL=gemini-flash-latest` in `.env`. |
| 3 | **OpenAI: `credit_balance_exhausted`.** | OpenAI fallback unusable. | Add credit, or keep it disabled. |
| 4 | **External image processing disabled** (pending privacy approval). | UAT P-09 can only check upload, progress, retry and the truthful "not analysed" result. Real label reading cannot be checked. | After privacy approval and with provider quota, start with `-AiProvider gemini` and set `AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED=true` (edit the script variable). Use synthetic packaging photos only. |
| 5 | **Stripe CLI not installed**, so webhooks cannot reach the local backend. | Payments still confirm, because the app's status check verifies the PaymentIntent with Stripe on the server. The webhook handler itself is not exercised. | Optional: install the Stripe CLI and run `stripe listen --forward-to 127.0.0.1:8001/api/payments/webhook`, then put the printed `whsec_…` in the process environment. |
| 6 | **Firebase not configured** (no `google-services.json`, no service-account credentials). | Push notifications (P-07 app closed, P-16) are blocked; in-app notification lists still work. | Add a Firebase project, `mobile/android/app/google-services.json` and backend credentials. |
| 7 | **Email disabled for UAT**; `.env` has real SMTP credentials. | OTP, password reset and email confirmations cannot be tested. | Run with `-EnableEmail` only with accounts using your own inbox. |
| 8 | **SMS provider not configured.** | SMS confirmations are blocked. | Configure an SMS provider for staging. |
| 9 | `.env` `JWT_SECRET` is 11 characters. | The production start-up check would reject it. UAT uses its own 64-character secret. | Use a 32-byte or longer secret in every real environment. |
| 10 | No Android device or emulator was connected during preparation. | The APK was built but not installed or launched. | Connect the phone and follow §3. |
| 11 | Android cleartext config uses CIDR ranges as domain names (§3). | LAN-IP access is likely blocked. | Use USB with `adb reverse` for UAT; fix the config before any Wi-Fi testing. |
| 12 | Gradle warns that some plugins need migrating to built-in Kotlin. | The build succeeds today. | Track for a future Flutter or Android Gradle Plugin upgrade. |

## 7. Stopping and resetting

- Stop the UAT backend and admin web with Ctrl+C in their windows.
- To start over with clean UAT data, run the following in a Mongo shell; it affects only the UAT database:
  ```
  use mediconnect_uat
  db.dropDatabase()
  ```
  Then start the backend again; it reseeds automatically.
