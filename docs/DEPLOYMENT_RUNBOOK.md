# MediConnect — Production Deployment Runbook

- **Version:** 1.0.0
- **Document Status:** Release Candidate Guide
- **Target Architecture:**
  - **Flutter Android (`mobile/`)**: Patient + Doctor mobile app
  - **React Admin Web (`admin-web/`)**: Administrator web portal
  - **FastAPI Backend (`backend/`)**: Unified REST API gateway
  - **MongoDB Atlas**: Managed multi-tenant cloud database

> [!CAUTION]
> **MANDATORY APPROVAL REQUIREMENT:**
> This runbook is a standard operating procedure guide. **DO NOT EXECUTE PRODUCTION DEPLOYMENT STEPS WITHOUT EXPLICIT WRITTEN APPROVAL FROM THE PROJECT OWNER AND LEAD DEPLOYMENT ENGINEER.**

---

## 1. System Architecture Overview

```mermaid
graph TD
    subgraph Clients
        P[Patient Android Client] -->|HTTPS REST| GW[FastAPI Backend :8000]
        D[Doctor Android Client] -->|HTTPS REST| GW
        A[React Web Admin :3000] -->|HTTPS REST| GW
    end

    subgraph Backend & Infrastructure
        GW --> DB[(MongoDB Atlas)]
        GW --> ST[Stripe Payment Gateway]
        GW --> FB[Firebase Cloud Messaging]
        GW --> AI[AI Recommendation Engine]
    end
```

---

## 2. Infrastructure Prerequisites

| Component | Target Runtime | Recommended Sizing | Minimum Version |
| :--- | :--- | :--- | :--- |
| **Backend** | Docker / Linux VM | 2 vCPU, 4 GB RAM | Python 3.12+ |
| **Database** | MongoDB Atlas (M10+) | Dedicated Cluster with Replica Set | MongoDB 7.0+ |
| **Admin Web** | Nginx / CDN Static Host | Serverless Edge / Alpine Container | Node 20 (Build) |
| **Mobile App** | Android 7.0+ (API 24+) | Minimum SDK 24, Target SDK 34 | Flutter 3.29+ |

---

## 3. Backend Deployment Procedure

### Option A: Containerized Deployment (Recommended)
1. Verify `backend/Dockerfile` and `backend/.dockerignore`.
2. Populate `/etc/mediconnect/backend.env` with production secrets (see Section 6).
3. Build and launch container:
   ```bash
   docker build -t mediconnect-backend:1.0.0 ./backend
   docker run -d \
     --name mediconnect-backend \
     --restart unless-stopped \
     -p 8000:8000 \
     --env-file /etc/mediconnect/backend.env \
     mediconnect-backend:1.0.0
   ```
4. Verify non-root execution (`appuser`), health probes:
   ```bash
   curl -f http://localhost:8000/health
   ```

### Option B: Systemd Direct Host Execution
1. Install Python 3.12 and dependencies:
   ```bash
   cd /opt/mediconnect/backend
   python3 -m venv venv
   ./venv/bin/pip install --no-cache-dir -r requirements.txt
   ```
2. Configure Systemd service `/etc/systemd/system/mediconnect-backend.service`:
   ```ini
   [Unit]
   Description=MediConnect FastAPI Gateway
   After=network.target

   [Service]
   Type=simple
   User=mediconnect
   Group=mediconnect
   WorkingDirectory=/opt/mediconnect/backend
   EnvironmentFile=/etc/mediconnect/backend.env
   ExecStart=/opt/mediconnect/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips "*"
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
3. Start and enable service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now mediconnect-backend
   sudo systemctl status mediconnect-backend
   ```

---

## 4. React Admin Web Hosting Procedure

### Option A: Static Web Server (Nginx / Apache)
1. Build distribution package:
   ```bash
   cd admin-web
   npm ci
   npm run build
   ```
2. Copy `dist/` artifacts to web server root:
   ```bash
   sudo cp -r dist/* /var/www/mediconnect-admin/
   ```
3. Deploy Nginx configuration from `admin-web/nginx.conf`. Key directives:
   - SPA route fallback: `try_files $uri $uri/ /index.html;`
   - Cache control: `add_header Cache-Control "no-cache, no-store, must-revalidate";` for `index.html`.
   - 1-year immutable cache for `/assets/*`.

### Option B: Cloudflare Pages / Netlify / Render
1. Build Command: `npm run build`
2. Publish Directory: `dist`
3. Environment Variable: `VITE_API_BASE_URL=https://api.mediconnect.lk/api`
4. Routing fallback is automatically handled via `dist/_redirects`.

---

## 5. Flutter Android Release Packaging

### Prerequisites:
1. Ensure release signing configuration is present in `mobile/android/key.properties`:
   ```properties
   storePassword=YOUR_SECURE_STORE_PASSWORD
   keyPassword=YOUR_SECURE_KEY_PASSWORD
   keyAlias=mediconnect-release
   storeFile=/path/to/secure/upload-keystore.jks
   ```
2. Build signed Android App Bundle (AAB):
   ```bash
   cd mobile
   flutter pub get
   flutter build appbundle --release --dart-define=API_BASE_URL=https://api.mediconnect.lk
   ```
3. Verify output artifact at `build/app/outputs/bundle/release/app-release.aab`.

---

## 6. Environment Variables & Secret Configuration

| Scope | Variable Name | Purpose | Example / Constraints |
| :--- | :--- | :--- | :--- |
| **Backend** | `MONGODB_URI` | Atlas connection string | `mongodb+srv://user:pass@cluster.mongodb.net/?tls=true` |
| **Backend** | `DATABASE_NAME` | Active MongoDB database | `mediconnect` |
| **Backend** | `JWT_SECRET` | Token signing secret | Cryptographically secure random (>= 32 chars) |
| **Backend** | `ALLOWED_ORIGINS` | CORS whitelist | `https://admin.mediconnect.lk,https://mediconnect.lk` |
| **Backend** | `STRIPE_SECRET_KEY` | Stripe secret key | `sk_test_...` (or `sk_live_...` for live) |
| **Backend** | `STRIPE_WEBHOOK_SECRET`| Webhook verification | `whsec_...` |
| **Admin Web** | `VITE_API_BASE_URL` | Public backend URL | `https://api.mediconnect.lk/api` |
| **Mobile** | `API_BASE_URL` | Compile-time define | `https://api.mediconnect.lk` |

---

## 7. Database Initialization & Verification

1. Verify connectivity:
   ```bash
   curl -f https://api.mediconnect.lk/health
   ```
2. The FastAPI backend automatically invokes `ensure_indexes()` on startup to enforce:
   - Unique constraints on user email, doctor registration, and profile references.
   - Unique compound indexes on active appointment slots preventing double bookings.
   - Idempotency indexes on Stripe webhook IDs and payments.

---

## 8. Post-Deployment Smoke Test Protocol

Perform immediate manual sanity checks post-deployment:
1. **Health Verification:** `GET /health` returns `{ "api": "healthy", "database": { "connected": true } }`.
2. **Admin Web Portal:** Navigate to `https://admin.mediconnect.lk/login`. Authenticate with administrative credentials. Verify dashboard metrics load real data.
3. **Mobile Client:** Launch Android app, log in as synthetic Patient, search doctor directory, view profile details, and verify availability slots.
4. **Stripe Test Hook:** Emit a test webhook and verify payment status transitions in admin payments table.

---

## 9. Rollback & Disaster Recovery Strategy

1. **Backend Rollback:**
   - Containerized: Redeploy previous release container tag (`docker run ... mediconnect-backend:previous-tag`).
   - Systemd: Switch symlink to previous release folder and restart service.
2. **Admin Web Rollback:**
   - Static: Rollback CDN deployment / restore previous `dist/` directory.
3. **Database Safeguard:**
   - MediConnect data structures use non-destructive, backward-compatible schemas.
   - Point-in-time recovery (PITR) is enabled on MongoDB Atlas for instantaneous recovery.
