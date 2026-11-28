# MediConnect — Developer Setup (local, Windows-first)

For: developers and reviewers setting up MediConnect locally. Updated for v1.0.0-academic (R04, 2026-11-28). Every command below was checked against this repository.

> Use a **local MongoDB and synthetic data only**. Never point a local setup at a shared or remote database. A historical database credential exposure is still open (see the R03 security report).

## 1. Requirements

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ (CI uses 3.12; 3.13 also used locally) | `python --version` |
| Node.js | 20+ (CI uses 20) | `node --version` |
| Flutter SDK | Dart ≥ 3.7 (`mobile/pubspec.yaml`); verified with Flutter 3.47.5 stable | `flutter doctor` |
| Android SDK | Platform tools and an emulator image (Android 7.0+, minSdk 24) | Android Studio or command-line tools |
| MongoDB | Community server listening on `127.0.0.1:27017` | No authentication needed for local use |
| Git | any recent | |

## 2. Backend (FastAPI)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
```

**`backend/.env`:**
- Contains placeholders only; fill in your own values and never commit it.
- It needs a Stripe **test** key, because the UAT script refuses anything else. All other variables can stay empty for a local demonstration.

| Variable | Purpose | Local value |
|---|---|---|
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` | Stripe test mode | `sk_test_…` / `pk_test_…` from your own Stripe test account |
| `STRIPE_WEBHOOK_SECRET` | Webhook signature | optional locally (`stripe listen --print-secret`) |
| `GEMINI_API_KEY`, `OPENAI_API_KEY` | Optional AI providers | leave empty: the deterministic engine answers |
| `MONGODB_URI`, `DATABASE_NAME`, `JWT_SECRET` | Used by deployments | **ignored by the UAT script**, which forces the local database and its own secret |

### Isolated UAT backend (recommended)

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\start_uat_backend.ps1            # seeds synthetic data, then starts
powershell -ExecutionPolicy Bypass -File backend\scripts\start_uat_backend.ps1 -SkipSeed  # later runs
```

What the script guarantees:
- **Database:** always `mongodb://127.0.0.1:27017/mediconnect_uat`, never the URI in `.env`.
- **Port:** `127.0.0.1:8001`. Port 8000 is reserved for production-like use, so don't use it for UAT.
- **AI:** deterministic engine; image analysis is disabled.
- **Delivery:** e-mail, push and SMS are disabled.
- **Stripe:** test key required.
- **Secrets:** a random JWT secret and document-encryption key are generated once into the git-ignored `backend/uat.env`, along with the shared synthetic-account password (`UAT_PASSWORD`). The password is never printed.
- **Optional flags:** `-AiProvider gemini|openai|both`, `-AiDailyLimit N`, `-EnableVision`, `-StripeWebhookSecretFile <path>`. Use them only with explicit authorisation, and with synthetic data.

**Health check:** `http://127.0.0.1:8001/health` should report `"database": … "isolatedTestData": true`. The API docs are at `/docs`.

### Backend tests

```powershell
cd backend
.\venv\Scripts\python -m pytest -q
```

How the test setup protects you:
- **Database:** `tests/conftest.py` forces a local database whose name ends in `_test` (default `mediconnect_test`) and refuses anything else.
- **Fresh runs:** for a completely fresh run, set `MONGODB_URI=mongodb://127.0.0.1:27017/<name>_test` and `DATABASE_NAME=<name>_test`.
- **Providers:** keys are blanked; Stripe uses test doubles.

## 3. Admin web (React + Vite)

```powershell
cd admin-web
npm ci
Copy-Item .env.example .env.local   # VITE_API_BASE_URL=http://127.0.0.1:8001/api
npm run dev                         # http://localhost:5173 (Vite moves to 5174 if 5173 is busy)
```

`vite.config.ts` sets `host: true`, so the dev server also listens on your LAN interfaces. Use `npm run dev -- --host 127.0.0.1` to keep it local.

**Checks:**
- `npm run typecheck`
- `npm run lint`
- `npm test` (Vitest)
- `npm run build` (output: `admin-web/dist/`)

Without `VITE_API_BASE_URL`, development uses the UAT backend on port 8001, and a production build uses a relative `/api`.

**Admin sign-in:** `uat.admin@uat.mediconnect.lk`, using the shared UAT password from `backend/uat.env`.

## 4. Android app (Flutter)

```powershell
cd mobile
flutter pub get
flutter analyze
flutter test
```

### Emulator

`10.0.2.2` is the Android emulator's alias for the host computer's loopback:

```powershell
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001
adb install -r build\app\outputs\flutter-apk\app-debug.apk
# or: flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001
```

**This APK only works on the emulator.** `10.0.2.2` does not exist on a physical phone.

### Physical Android phone (not verified in this project)

A physical phone cannot reach `127.0.0.1:8001` on your computer. Either option below needs a rebuild with the matching `API_BASE_URL`:

- **USB, recommended:** `adb reverse tcp:8001 tcp:8001`, then build with `--dart-define=API_BASE_URL=http://127.0.0.1:8001`.
- **Same Wi-Fi:** the backend would have to listen on the LAN address rather than `127.0.0.1`. That exposes it to your network, so only do it on a trusted network with synthetic data. Build with `--dart-define=API_BASE_URL=http://<computer LAN IP>:8001`.

A release build without `API_BASE_URL` points to a production host and is not usable locally. No signing keystore is included (`android/key.properties` is absent), so release builds are unsigned unless you provide your own signing configuration.

## 5. Synthetic accounts

All on the domain `uat.mediconnect.lk`, with the shared password from `backend/uat.env`:

| Role | Examples |
|---|---|
| Patients | `uat.patient1`, `uat.patient2`, `uat.p02.patienta`/`b`/`c`, `uat.p03.patienta`/`b` |
| Doctors | `uat.doctor.gp`, `uat.doctor.neuro`, `uat.p02.doctor.ortho`, `uat.p03.doctor.alpha` |
| Admin | `uat.admin` |

Some fixtures come from the phase seeders: `backend/scripts/seed_phase02_fixtures.py`, `seed_phase03_fixtures.py` and `seed_phase04_fixtures.py`, run from `backend` with `python -m scripts.<name>`.

## 6. Optional providers (authorisation required)

| Provider | How | Notes |
|---|---|---|
| Gemini | `GEMINI_API_KEY` in `.env`, then `start_uat_backend.ps1 -AiProvider gemini -AiDailyLimit 60` | Capped by the provider gateway; synthetic data only |
| Gemini vision | Add `-EnableVision` | Synthetic packaging images only |
| OpenAI | `OPENAI_API_KEY`, `-AiProvider openai` or `both` | Not verified live (no account credits) |
| Stripe webhooks | `stripe listen --forward-to http://127.0.0.1:8001/api/payments/webhook --print-secret`, save the secret to a file outside the repository, pass it with `-StripeWebhookSecretFile` | Test mode only |

## 7. Not covered

- `docker-compose.yml` and the Dockerfiles exist, but they were not used or verified for v1.0.0-academic.
- No deployment is authorised.
- iOS builds were not run.
