# MediConnect — Phase 36: Final Pre-Launch Approval Checklist

- **Release Candidate:** MediConnect v1.0.0 (Build 1)
- **Target Branch:** `feature/phase36-deployment-dry-run`
- **Document Purpose:** Mandatory operational sign-off gate prior to production deployment.
- **Authority Requirement:** All sections must be reviewed and signed off by designated stakeholders before initiating any live deployment actions.

> [!CAUTION]
> **NO AUTOMATIC DEPLOYMENT AUTHORIZATION:**
> Passing all automated tests and completing Phase 36 does **NOT** authorize production deployment. Production launch requires explicit manual execution following this sign-off.

---

## 1. Launch Gate Sign-Off Matrix

| Category | Gate Item | Verification Standard | Sign-Off Status | Verified By |
| :--- | :--- | :--- | :--- | :--- |
| **Backend** | Entrypoint & Probes | `/health` returns 200; `/ready` returns 200; zero secret leakage | **READY** | Automated CI / Pytest |
| **Backend** | Test Coverage | 190 tests passed across 19 modules (`pytest -q`) | **READY** | Automated CI / Pytest |
| **Backend** | Hardened Container | Python 3.12-slim, non-root user `appuser` (UID 10001) | **READY** | Dockerfile Inspection |
| **Admin Web**| Build & Static Bundle | Vite production bundle generated cleanly without errors | **READY** | Vite & Vitest (28 passed) |
| **Admin Web**| Route Fallback | SPA fallback (`_redirects` & `nginx.conf`) verified | **READY** | Rehearsal Verification |
| **Admin Web**| Security & Isolation | Non-admin users (Patient, Doctor) rejected; zero secrets in JS | **READY** | Vitest & Auth Guard |
| **Mobile** | Analyzers & Unit Tests | `flutter analyze` 0 issues; `flutter test` 177/177 passed | **READY** | Flutter Test Runner |
| **Mobile** | Release Artifacts | `app-release.apk` (66.8 MB) and `app-release.aab` (68.5 MB) built | **READY** | Gradle Build |
| **Mobile** | Release Signing | Production upload keystore configured in `key.properties` | **PENDING** | Release Manager Action |
| **Mobile** | Physical Hardware QA | Smoke test on minimum 2 physical devices (Android 10 & 14) | **PENDING** | QA Device Lab |
| **Database** | Idempotent Indexes | `ensure_indexes()` runs cleanly on startup without conflicts | **READY** | Pytest Idempotency Test |
| **Database** | Backup & PITR | MongoDB Atlas Point-In-Time-Recovery (PITR) enabled & verified | **PENDING** | Database Administrator |
| **Security** | Secrets Management | Production environment file provisioned via secure secret store | **PENDING** | DevOps / SecOps |
| **Security** | HTTPS & HSTS | TLS 1.3 enforced; HSTS header enabled with 1-year max-age | **READY** | Security Header Audit |
| **Security** | CORS Origins | Allowed origins configured to production domains only | **READY** | Middleware Inspection |
| **Security** | RBAC Independence | Backend enforces authorization independently of frontend | **READY** | Automated RBAC Suite |
| **Payments** | Stripe Live Keys | Transition from `sk_test_` to `sk_live_` and live webhook secret | **PENDING** | Finance / Project Owner |
| **Push** | Firebase Production | Production Firebase service account JSON injected into backend | **PENDING** | Release Manager |
| **AI Engine** | AI Provider Quotas | Valid OpenAI / Gemini API keys configured with safety limits | **PENDING** | Technical Lead |
| **Monitoring**| Logs & Metrics | Centralized logging and error tracking (e.g., Sentry) active | **PENDING** | DevOps Engineer |
| **Disaster** | Rollback Readiness | Container tags, static assets, and restore runbooks verified | **READY** | Deployment Runbook |

---

## 2. Pre-Deployment Manual Prerequisites (Required Before Launch)

Before running deployment commands in [docs/DEPLOYMENT_RUNBOOK.md](file:///C:/Users/REDTECH/Downloads/MediConnect/docs/DEPLOYMENT_RUNBOOK.md), the deployment team must complete:

1. **Android Signing Keystore Injection**:
   - Obtain the official organization upload keystore (`upload-keystore.jks`).
   - Create `mobile/android/key.properties` on the secure build runner with:
     ```properties
     storePassword=SECURE_STORE_PASSWORD
     keyPassword=SECURE_KEY_PASSWORD
     keyAlias=mediconnect-release
     storeFile=/path/to/upload-keystore.jks
     ```
   - Re-run `flutter build appbundle --release` to produce the cryptographically signed release bundle for Google Play Console upload.

2. **Database Backup Snapshot**:
   - Log in to MongoDB Atlas management portal.
   - Trigger an immediate on-demand cluster snapshot prior to production backend startup.
   - Confirm Point-In-Time-Recovery (PITR) window is active.

3. **Production Secrets Provisioning**:
   - Generate a cryptographically secure random string (>= 32 bytes) for `JWT_SECRET`:
     ```bash
     openssl rand -hex 32
     ```
   - Populate production environment file `/etc/mediconnect/backend.env` with:
     - `MONGODB_URI`: Production Atlas connection string
     - `DATABASE_NAME`: `mediconnect_prod`
     - `JWT_SECRET`: The 32+ byte key generated above
     - `ALLOWED_ORIGINS`: `https://admin.mediconnect.lk,https://mediconnect.lk`
     - `STRIPE_SECRET_KEY`: `sk_live_...`
     - `STRIPE_WEBHOOK_SECRET`: `whsec_...`
     - `FIREBASE_CREDENTIALS_PATH`: Path to production Firebase service account JSON

4. **Web Admin CDN / Domain Setup**:
   - Provision DNS records: `admin.mediconnect.lk` -> CDN / Nginx endpoint.
   - Configure TLS certificate (Let's Encrypt / Cloudflare Edge).
   - Set build environment variable `VITE_API_BASE_URL=https://api.mediconnect.lk/api`.

---

## 3. Post-Deployment Smoke Test Protocol

Immediately after deployment to production:
1. **Health Probes**:
   - Run: `curl -f https://api.mediconnect.lk/health`
   - Verify `{"status": "healthy", "database": {"connected": true}}`.
2. **Web Admin Sign-In**:
   - Navigate to `https://admin.mediconnect.lk`.
   - Log in with provisioned administrative credentials.
   - Verify dashboard KPI cards render real metrics without console errors.
3. **Doctor Verification Workflow**:
   - Verify pending doctor list renders and documents are viewable.
4. **Mobile Client Verification**:
   - Launch signed build on physical Android test device.
   - Log in as test patient; search verified doctors; view available slots.
5. **Stripe Live Hook Sanity Test**:
   - Trigger a Stripe test event or verify webhook endpoint status in Stripe Developer Dashboard (`https://dashboard.stripe.com/webhooks`).

---

## 4. Rollback Plan

If critical defects or service degradation occur within the 2-hour post-launch window:
1. **Backend Rollback**:
   - Redeploy the previous known-stable container tag:
     ```bash
     docker stop mediconnect-backend
     docker run -d --name mediconnect-backend --restart unless-stopped -p 8000:8000 --env-file /etc/mediconnect/backend.env mediconnect-backend:previous-tag
     ```
2. **Web Admin Rollback**:
   - Point CDN / Nginx root to the prior release distribution directory.
3. **Mobile Rollback**:
   - Google Play Console: Halt staged rollout or deactivate the release track.
4. **Database Rollback**:
   - If data corruption occurred, restore MongoDB Atlas cluster to the pre-deployment snapshot timestamp.

---

## 5. Stakeholder Sign-Off

| Stakeholder Role | Name | Decision | Date | Signature |
| :--- | :--- | :--- | :--- | :--- |
| **Lead Deployment Engineer** | ____________________ | [ ] APPROVED  [ ] REJECTED | __________ | ____________________ |
| **Lead Security Engineer** | ____________________ | [ ] APPROVED  [ ] REJECTED | __________ | ____________________ |
| **QA / Release Manager** | ____________________ | [ ] APPROVED  [ ] REJECTED | __________ | ____________________ |
| **Project Owner** | ____________________ | [ ] APPROVED  [ ] REJECTED | __________ | ____________________ |
