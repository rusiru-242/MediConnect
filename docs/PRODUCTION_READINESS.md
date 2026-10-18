# MediConnect — Production Readiness & Deployment Runbook

**Version:** 1.0.0 (Phase 25 Stabilization)
**Target Environments:** Cloud Run / AWS ECS / Ubuntu Linux + MongoDB Atlas + Android Play Store

---

## 1. Executive Summary & Production-Readiness Assessment

MediConnect has completed comprehensive testing and hardening across its FastAPI backend, MongoDB data tier, and Flutter cross-platform mobile client.

| Component | Status | Verification Summary |
| :--- | :--- | :--- |
| **Backend API Core** | **PASS** | 157 passing pytest unit and integration tests. Clean compilation (`python -m compileall app`). |
| **Mobile Client** | **PASS** | 165 passing Flutter tests (models, network, providers, screens). 0 warnings on `flutter analyze`. |
| **MongoDB Indexes** | **RESOLVED** | Identified and fixed duplicate index conflict (`IndexKeySpecsConflict` on `idx_appt_doctor_slot_unique_active` and patient/doctor indices). All collections create indexes cleanly without warnings or failures. |
| **Authentication & RBAC** | **PASS** | Bcrypt salted hashing, short-lived JWT access tokens, cryptographically secure opaque refresh tokens hashed with SHA-256 in DB, rate-limited auth endpoints. |
| **Stripe Payments** | **PASS** | Server-side calculation of consultation fees, atomic webhook idempotency check, signature verification, non-reliance on mobile callbacks. |
| **AI Assistants** | **PASS** | Deterministic emergency triage bypass (1990 ambulance), prompt-injection safeguards, 5-second provider timeouts with bilingual fallback. |
| **Medical Records & Prescriptions** | **PASS** | Strict patient/doctor ownership verification, immutable amendment audit history, authenticated non-public PDF streaming. |
| **Secrets & Credentials** | **PASS** | Zero `.env` or credential files tracked in Git; expanded `.gitignore` prevents leaks. |

---

## 2. Architecture & Deployment Infrastructure

### 2.1 Backend Production Runtime
Deploy the FastAPI backend behind an ASGI application server managed by a process manager:
```bash
# Recommended production execution command (4 worker processes)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips='*'
```
Or with Gunicorn managing Uvicorn workers:
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

### 2.2 Reverse Proxy & TLS/HTTPS (Nginx Example)
Always terminate SSL/TLS at a secure reverse proxy (Nginx, AWS ALB, or Cloudflare):
```nginx
server {
    listen 443 ssl http2;
    server_name api.mediconnect.lk;

    ssl_certificate /etc/letsencrypt/live/api.mediconnect.lk/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.mediconnect.lk/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2.3 CORS & Security Headers
- Set `ENVIRONMENT=production` in the production environment.
- Configure `ALLOWED_ORIGINS` to allow only trusted frontend origins:
  ```env
  ALLOWED_ORIGINS=https://app.mediconnect.lk,https://admin.mediconnect.lk
  ```
- MediConnect automatically applies defensive security headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (in production)

---

## 3. Database Management & Backup / Restore Plan

### 3.1 MongoDB Atlas Recommended Setup
- Deploy an M10+ replica set across 3 availability zones.
- Enable **Continuous Cloud Backups** (point-in-time recovery up to 7 days, daily snapshots for 30 days).
- Enable encryption at rest and TLS 1.2+ in transit (`tls=true` in connection string).

### 3.2 Automated Backup Script (`mongodump`)
```bash
#!/usr/bin/env bash
set -euo pipefail

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/var/backups/mediconnect/mongo_${TIMESTAMP}"

mkdir -p "${BACKUP_DIR}"

mongodump \
  --uri="${MONGODB_URI}" \
  --out="${BACKUP_DIR}" \
  --gzip

# Encrypt backup archive with GPG
tar -czf "${BACKUP_DIR}.tar.gz" -C "/var/backups/mediconnect" "mongo_${TIMESTAMP}"
gpg --symmetric --cipher-algo AES256 "${BACKUP_DIR}.tar.gz"
rm -rf "${BACKUP_DIR}" "${BACKUP_DIR}.tar.gz"

echo "Backup complete: ${BACKUP_DIR}.tar.gz.gpg"
```

### 3.3 Database Restoration Procedure (`mongorestore`)
```bash
# Decrypt archive
gpg --decrypt "${BACKUP_DIR}.tar.gz.gpg" > "${BACKUP_DIR}.tar.gz"
tar -xzf "${BACKUP_DIR}.tar.gz"

# Restore database idempotently without dropping unrelated collections
mongorestore \
  --uri="${MONGODB_URI}" \
  --nsInclude="mediconnect.*" \
  --gzip \
  "mongo_${TIMESTAMP}/mediconnect"
```

---

## 4. Stripe Live-Mode Migration Checklist

Before switching Stripe from test mode to live mode:

1. **Stripe Dashboard Account Activation:**
   - Complete business verification, bank account linkage, and identity verification in Stripe Dashboard.
2. **Obtain Live API Keys:**
   - Copy `pk_live_...` and `sk_live_...` from the Stripe Developer Dashboard.
   - Do NOT mix test and live keys in the same environment.
3. **Configure Live Webhook Endpoint:**
   - Register endpoint: `https://api.mediconnect.lk/api/payments/webhook`
   - Select events:
     - `payment_intent.succeeded`
     - `payment_intent.payment_failed`
     - `payment_intent.canceled`
   - Retrieve webhook signing secret `whsec_...` and populate `STRIPE_WEBHOOK_SECRET`.
4. **Currency & Fee Verification:**
   - Verify that doctor consultation fees are formatted correctly in smallest currency units (cents for USD, cents for LKR).
   - Ensure `STRIPE_CURRENCY=lkr` (or target platform currency).
5. **Zero Trust on Flutter Callbacks:**
   - MediConnect confirms appointment booking solely upon receiving verified Stripe webhook signatures or backend-authoritative status polling.

---

## 5. Firebase Cloud Messaging (FCM) Production Setup

1. **Service Account Key Generation:**
   - Navigate to Google Cloud / Firebase Console -> Project Settings -> Service Accounts.
   - Generate a private key for the Firebase Admin SDK.
   - Store the key on the production server under `/etc/mediconnect/secrets/firebase-service-account.json` (chmod 600, owned by the app process).
2. **Device Token Management:**
   - Stale and invalid FCM device tokens (`registration-token-not-registered`) are automatically pruned from patient and doctor profiles upon delivery failure.
3. **Notification Privacy Protection:**
   - Push notifications must contain non-sensitive summaries (e.g. "Appointment Confirmed with Dr. Kasun", "Prescription Issued") and exclude sensitive clinical diagnoses or medication dosage details in notification pop-ups.

---

## 6. Android Release Build & Distribution Guide

### 6.1 Keystore Generation (Manual Step)
Generate a private release keystore if not already created:
```bash
keytool -genkey -v -keystore mediconnect-release-key.jks \
  -keyalg RSA -keysize 2048 -validity 10000 -alias mediconnect
```
Store `mediconnect-release-key.jks` securely in a password manager. Never commit it to Git.

### 6.2 Key Properties Configuration
Create `mobile/android/key.properties`:
```properties
storePassword=<STORE_PASSWORD>
keyPassword=<KEY_PASSWORD>
keyAlias=mediconnect
storeFile=/absolute/path/to/mediconnect-release-key.jks
```

### 6.3 Build Production App Bundle (AAB)
```bash
cd mobile

# Install dependencies
flutter pub get

# Compile release Android App Bundle with compile-time HTTPS API URL
flutter build appbundle --release --dart-define=API_BASE_URL=https://api.mediconnect.lk
```
The output file will be generated at: `mobile/build/app/outputs/bundle/release/app-release.aab`.

---

## 7. Monitoring, Logging & Error Reporting

1. **Structured Logging:**
   - Backend logs are configured with timestamps, log levels, and request context without printing plain-text passwords, JWT tokens, or Stripe secret keys.
2. **Application Performance Monitoring (Sentry / Datadog):**
   - Integrate Sentry Python SDK into `app/main.py` for real-time error tracking and alerting.
3. **Health Check Endpoints:**
   - `GET /health`: Returns `{ "api": "healthy", "database": { "connected": true, "status": "connected" } }`.
   - Use this endpoint for load balancer health probes (AWS Route 53 / ALB target group health checks).

---

## 8. Manual Pre-Launch Steps Requiring Human Approval

The following critical actions require explicit stakeholder/administrator sign-off prior to opening public registration:

- [ ] **Stripe Live Mode Activation:** Admin must verify business tax details and activate live payments.
- [ ] **DNS & TLS Provisioning:** Point domain records (`api.mediconnect.lk`) to the production load balancer and issue valid Let's Encrypt / DigiCert certificates.
- [ ] **SMTP Mail Delivery Warmup:** Verify domain DNS records (`SPF`, `DKIM`, and `DMARC`) with the transactional email provider to prevent verification emails from landing in spam folders.
- [ ] **Initial Admin Account Provisioning:** Run initial database setup script to seed the first verified administrator user with strong multi-factor credentials.
- [ ] **Google OAuth Verification:** Submit Google Cloud OAuth Consent Screen for production verification to remove unverified app warnings for patient Google Sign-In.
- [ ] **SLMC Doctor License Verification Verification:** Establish internal clinical verification procedures for verifying doctor credentials with the Sri Lanka Medical Council (SLMC) before approving doctors.
