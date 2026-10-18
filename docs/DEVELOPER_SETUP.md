# MediConnect — Local Developer Setup Guide

This guide provides end-to-end instructions for configuring a local Windows development workstation for the MediConnect platform using Windows PowerShell.

---

## 1. System Prerequisites

Install the following runtimes and toolchains on your Windows workstation:
1. **Python**: Version 3.12 or 3.13 ([python.org](https://www.python.org/downloads/))
2. **Node.js**: Version 20 LTS or higher with npm ([nodejs.org](https://nodejs.org/))
3. **Flutter SDK**: Version 3.29.0 or higher ([flutter.dev](https://docs.flutter.dev/get-started/install/windows))
4. **Android Studio**: With Android SDK (API 34/35), Android SDK Platform-Tools (`adb`), and Android Emulator
5. **Git**: Version 2.40+ ([git-scm.com](https://git-scm.com/))
6. **MongoDB**: Local MongoDB community server or a free MongoDB Atlas M0 cluster ([mongodb.com/atlas](https://www.mongodb.com/atlas))

---

## 2. Repository Cloning & Structure

```powershell
# Clone the repository
git clone https://github.com/rusiru-242/MediConnect.git
cd MediConnect
```

The workspace consists of three core subprojects:
- `backend/` — FastAPI REST application
- `mobile/` — Flutter Android application (Patient + Doctor)
- `admin-web/` — React + TypeScript Web Admin application

---

## 3. Backend Setup (FastAPI & MongoDB)

### Step 1: Initialize Virtual Environment
Open Windows PowerShell in `C:\Users\REDTECH\Downloads\MediConnect\backend`:

```powershell
cd C:\Users\REDTECH\Downloads\MediConnect\backend

# Create virtual environment named 'venv'
python -m venv venv

# Enable execution policy for current process if script execution is restricted
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

### Step 2: Install Python Dependencies
```powershell
# Upgrade pip and install pinned dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Open `.env` in your editor and configure:
```dotenv
APP_NAME=MediConnect
ENVIRONMENT=development
PORT=8000
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=mediconnect
JWT_SECRET=your_super_secret_local_dev_jwt_key_at_least_32_bytes_long_1234
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000
STRIPE_SECRET_KEY=sk_test_mock_secret_key_or_real_test_key
STRIPE_WEBHOOK_SECRET=whsec_mock_webhook_secret
STRIPE_CURRENCY=lkr
```

### Step 4: Run FastAPI Development Server
```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- API Base: `http://127.0.0.1:8000`
- Health Probe: `http://127.0.0.1:8000/health`
- Swagger Documentation: `http://127.0.0.1:8000/docs`

### Step 5: Execute Automated Test Suite
```powershell
# Run the 190 automated pytest integration tests
python -m compileall app
pytest -q
```

---

## 4. Flutter Mobile Setup (Android Client)

The Flutter mobile application supports **Patients** and **Doctors**.

### Step 1: Install Dependencies
Open PowerShell in `C:\Users\REDTECH\Downloads\MediConnect\mobile`:

```powershell
cd C:\Users\REDTECH\Downloads\MediConnect\mobile

# Get Flutter dependencies
flutter pub get
```

### Step 2: Verify Toolchain
```powershell
flutter doctor -v
flutter analyze
```

### Step 3: Running on Android Emulator
When running on the official Android Emulator, use `10.0.2.2` to refer to the host computer's `localhost`:

```powershell
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

### Step 4: Running on Physical Android Device
When running on a physical Android smartphone connected via USB:
1. Enable **Developer Options** and **USB Debugging** on the device.
2. Confirm device connection via ADB:
   ```powershell
   adb devices
   ```
3. Use reverse port forwarding so the device can access the host backend:
   ```powershell
   adb reverse tcp:8000 tcp:8000
   flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
   ```
   *(Alternatively, provide your local LAN IP: `--dart-define=API_BASE_URL=http://192.168.1.X:8000`)*

### Step 5: Run Automated Flutter Tests
```powershell
flutter test
```

### Step 6: Build Release Binaries
```powershell
# Build unsigned release APK
flutter build apk --release

# Build unsigned release App Bundle
flutter build appbundle --release
```

---

## 5. React Admin Web Setup (Admin Portal)

The React web console is strictly for **Administrators**.

### Step 1: Install Node Dependencies
Open PowerShell in `C:\Users\REDTECH\Downloads\MediConnect\admin-web`:

```powershell
cd C:\Users\REDTECH\Downloads\MediConnect\admin-web

# Install pinned packages
npm ci
```

### Step 2: Configure Environment
Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Ensure `.env` contains:
```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

### Step 3: Launch Local Vite Development Server
```powershell
npm run dev
```
Open your browser to `http://localhost:5173`.

### Step 4: Run Linting, Typechecking & Unit Tests
```powershell
# Run ESLint
npm run lint

# Run TypeScript compiler typecheck
npm run typecheck

# Run Vitest unit tests (28 tests)
npm run test
```

### Step 5: Build Production Distribution
```powershell
npm run build
```
The compiled, minified bundle will be generated in `admin-web/dist/`.

---

## 6. Docker Compose Orchestration (Optional)

To start both the FastAPI backend and React Admin portal in local Docker containers:

```powershell
cd C:\Users\REDTECH\Downloads\MediConnect

# Build and start services in the background
docker-compose up -d --build

# Check container status
docker-compose ps

# View service logs
docker-compose logs -f
```
- Backend will be accessible at: `http://localhost:8000`
- Web Admin will be accessible at: `http://localhost:3000`
