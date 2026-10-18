# MediConnect — Phase 34: Production Deployment Checklist

- **Document Version:** 1.0.0
- **Target Milestone:** Release Candidate Deployment Verification
- **Architecture:** Flutter Android (Patient + Doctor) | React Web (Admin) | FastAPI (Shared Backend) | MongoDB Atlas (Shared Database)

---

## 1. Environment & Infrastructure Prerequisites

### Backend (FastAPI / Uvicorn / Container)
- [ ] **Python Version:** 3.10+ (Verified on Python 3.13)
- [ ] **Environment Variables:**
  - `MONGODB_URI`: Production MongoDB Atlas cluster connection string with TLS and replica set configured.
  - `MONGODB_DB_NAME`: Production database name (e.g. `mediconnect_prod`).
  - `JWT_SECRET_KEY`: High-entropy 256-bit+ cryptographically secure secret (minimum 32 bytes to eliminate HMAC warnings).
  - `JWT_ALGORITHM`: `HS256`
  - `ACCESS_TOKEN_EXPIRE_MINUTES`: Recommended `30`
  - `REFRESH_TOKEN_EXPIRE_DAYS`: Recommended `7`
  - `STRIPE_SECRET_KEY`: Production Stripe secret key (`sk_live_...`)
  - `STRIPE_WEBHOOK_SECRET`: Production Stripe endpoint signing secret (`whsec_...`)
  - `STRIPE_PUBLISHABLE_KEY`: Production publishable key (`pk_live_...`)
  - `CORS_ORIGINS`: Explicit list of production origins (e.g. `https://admin.mediconnect.lk`, `https://mediconnect.lk`)
  - `FIREBASE_CREDENTIALS_PATH`: Path to production Firebase Service Account JSON.
- [ ] **Process Management:** Gunicorn / Uvicorn workers behind Nginx reverse proxy with TLS 1.3 termination.
- [ ] **Health Check Monitoring:** Uptime monitor pinging `/health` every 60 seconds.

### React Admin Web Portal (`admin-web/`)
- [ ] **Node.js & Build:** Built using `npm run build` yielding static assets in `dist/`.
- [ ] **Hosting:** Nginx, Cloudflare Pages, Netlify, AWS S3/CloudFront, or Docker.
- [ ] **Environment Variables:**
  - `VITE_API_BASE_URL`: Production FastAPI gateway (e.g., `https://api.mediconnect.lk/api`).
- [ ] **HTTP Headers & Security:**
  - Enforce `Content-Security-Policy` matching production backend and Google Fonts.
  - Enforce `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.
  - Cache policy: `/assets/*` cached 1 year (`immutable`), `index.html` configured with `no-cache, no-store`.
  - SPA Fallback routing configured via `_redirects` or Nginx `try_files $uri $uri/ /index.html;`.

### Flutter Android Mobile (`mobile/`)
- [ ] **Target SDK:** API 34+
- [ ] **Production API Gateway:** Verify `mobile/lib/core/constants/api_constants.dart` points to production domain with HTTPS.
- [ ] **Android App Signing:**
  - Configure `android/key.properties` with production keystore path, alias, and secure passwords.
  - Build Android App Bundle using `flutter build appbundle --release`.
- [ ] **Google Services:** Ensure production `google-services.json` is deployed in `android/app/`.

---

## 2. Security & Compliance Checklist

- [ ] **Zero Public Medical Records:** Consultation notes, diagnoses, and digital prescriptions require strict authenticated authorization.
- [ ] **Doctor Verification:** Identity documents and medical licenses accessible solely by verified administrators.
- [ ] **Payment Validation:** Stripe webhooks validated via cryptographic signatures. Idempotency guarantees prevent duplicate appointment confirmations.
- [ ] **RBAC Isolation:**
  - Patient cannot access Doctor or Admin endpoints.
  - Doctor cannot access Admin endpoints or unassigned patient records.
  - Admin Web requires multi-factor or strict authenticated admin credentials.
- [ ] **No Secret Exposure:** Zero secrets, private keys, or `.env` files committed to version control.

---

## 3. Database Indexes & Integrity Checklist

Run `ensure_indexes()` at application startup to verify:
- [ ] `users`: Unique index on `email`.
- [ ] `doctor_profiles`: Unique index on `doctorId` and `userId`.
- [ ] `doctor_availabilities`: Compound index on `doctorProfileId`, `date`, `startTime`.
- [ ] `appointments`: Unique compound index on `doctorId`, `appointmentDate`, `startTime` for active bookings.
- [ ] `payments`: Unique index on `stripePaymentIntentId` and `appointmentId`.
- [ ] `reviews`: Unique index on `appointmentId`.

---

## 4. Rollback & Emergency Plan

- [ ] **Backend Rollback:** In case of critical runtime defects, revert container image tag to previous release tag.
- [ ] **Database Migration Safety:** All schema additions are non-destructive and backward compatible.
- [ ] **Emergency Contact:** Incident response team alerted via monitoring webhooks.
