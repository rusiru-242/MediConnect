# MediConnect — Final Pre-Launch Approval & Governance Checklist

- **System Version:** 1.0.0 (Build 1)
- **Target Branch:** `feature/phase37-final-handover`
- **Document Authority:** Mandatory operational approval gate. Production deployment must NOT proceed without written sign-off from all designated role owners.

> [!CAUTION]
> **NO AUTOMATIC LAUNCH PERMISSION:**
> Completion of automated verification phases does **NOT** constitute permission to deploy to production, enable live Stripe payments, or publish to the Google Play Store. This checklist governs the manual execution gate.

---

## 1. Technical Readiness Criteria

| System Domain | Verification Standard | Automated Result | Manual Verification Required | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Backend API** | Syntax compilation clean; 190 tests pass (`pytest -q`) | **PASS (190/190)** | Review `/health` probe post-deploy | **READY** |
| **Backend Container** | Hardened Dockerfile; non-root user `appuser` (UID 10001) | **PASS** | Verify runtime container UID | **READY** |
| **Admin Web Portal** | ESLint 0 warnings; TypeScript 0 errors; Vitest 28/28 | **PASS (28/28)** | Verify production CDN asset loading | **READY** |
| **Admin Web Bundle** | SPA fallback configured (`_redirects` / `nginx.conf`) | **PASS** | Verify direct route browser refresh | **READY** |
| **Mobile Client** | `flutter analyze` 0 issues; `flutter test` 177/177 passed | **PASS (177/177)** | Execute smoke test on physical device | **READY** |
| **Android Packaging** | `app-release.apk` (66.8 MB) and `app-release.aab` (68.5 MB) built | **PASS** | Inject `key.properties` for signed bundle | **PENDING SIGNING** |
| **Database Indexes** | `ensure_indexes()` executes idempotently on startup | **PASS** | Verify Atlas index build status | **READY** |
| **Database Recovery** | Automated Atlas daily snapshots & PITR active | **PASS (Design)** | Trigger pre-launch cluster snapshot | **PENDING ACTION** |
| **Secrets Security** | Zero `.env` files or credentials staged in Git | **PASS** | Populate production `/etc/mediconnect/backend.env` | **PENDING PROVISION** |
| **Network & Transport**| TLS 1.3 enforced; HSTS max-age 31536000 | **PASS (Config)** | Verify SSL Labs A+ rating on domain | **PENDING DNS** |
| **CORS Origins** | Explicit allowlist on backend; zero wildcard origins | **PASS** | Verify `ALLOWED_ORIGINS` in production | **READY** |
| **RBAC Independence**| Backend enforces role checks on every endpoint | **PASS** | Verify non-admin blocked from admin endpoints | **READY** |
| **Stripe Payments** | Test mode verified; live mode disabled | **PASS** | Transition to live keys (`sk_live_...`) | **PENDING APPROVAL** |
| **Push Notifications**| Privacy-safe payloads; zero medical data in push | **PASS** | Place production Firebase JSON on server | **PENDING PROVISION** |
| **AI Safeguards** | Prominent medical disclaimers on AI responses | **PASS** | Verify production quota & rate limits | **READY** |
| **Disaster Recovery** | Container tag rollback & static restore documented | **PASS** | Confirm team has runbook access | **READY** |

---

## 2. Required Manual Pre-Launch Actions

Before initiating production deployment:
1. **Android Production Keystore Setup**:
   - Release Manager must supply the official production upload keystore (`upload-keystore.jks`).
   - Create `mobile/android/key.properties` with keystore credentials on the dedicated build runner.
   - Re-run `flutter build appbundle --release` to generate the cryptographically signed `.aab` for Google Play Console.
2. **MongoDB Atlas Backup Snapshot**:
   - Log in to MongoDB Atlas cloud console.
   - Execute an on-demand cluster snapshot labeled `pre-launch-v1.0.0`.
   - Verify Point-In-Time-Recovery (PITR) window is active (minimum 7-day retention).
3. **Production Secrets Provisioning**:
   - Generate a 32+ byte cryptographic key for `JWT_SECRET`:
     ```bash
     openssl rand -hex 32
     ```
   - Inject production credentials into `/etc/mediconnect/backend.env` via a secure secrets manager (AWS Secrets Manager / Vault / secure system file).
4. **Stripe Live Mode Activation**:
   - Obtain production live API keys (`sk_live_...` and live `whsec_...`) from Stripe Dashboard.
   - Configure live webhook endpoint URL: `https://api.mediconnect.lk/api/payments/webhook`.
5. **Firebase Service Account Injection**:
   - Download Firebase Admin private key JSON.
   - Save to `/etc/mediconnect/firebase-service-account.json` with permissions `chmod 600`.

---

## 3. Post-Deployment Verification Gate (Smoke Testing)

Immediately following production deployment, the deployment team must perform the following smoke tests:
1. **Backend Health Check**:
   ```bash
   curl -i https://api.mediconnect.lk/health
   ```
   *Expected: HTTP 200 `{"status": "healthy", "database": {"connected": true}}`.*
2. **Admin Web Sign-In**:
   - Access `https://admin.mediconnect.lk`.
   - Log in with provisioned administrative account.
   - Confirm dashboard metrics render without browser console errors.
3. **Doctor Verification Test**:
   - In Web Admin, open Doctor Verification queue.
   - Inspect submitted credentials and verify document rendering.
4. **Mobile Patient Flow**:
   - Install signed release APK on physical test device.
   - Log in as test patient.
   - Search doctor directory; verify specialty filters and available slots.
5. **Stripe Webhook Ping**:
   - Send test event from Stripe Dashboard to verify live webhook endpoint response (HTTP 200).

---

## 4. Stakeholder Sign-Off Authorization

By signing below, each stakeholder certifies that the technical gates have been inspected, risks are documented and accepted, and the system is authorized for production deployment in accordance with [docs/DEPLOYMENT_RUNBOOK.md](file:///C:/Users/REDTECH/Downloads/MediConnect/docs/DEPLOYMENT_RUNBOOK.md):

| Role | Stakeholder Name | Decision | Date | Signature |
| :--- | :--- | :--- | :--- | :--- |
| **Lead Deployment Engineer** | _______________________ | [ ] APPROVED  [ ] REJECTED | __________ | _______________________ |
| **Lead Security Engineer** | _______________________ | [ ] APPROVED  [ ] REJECTED | __________ | _______________________ |
| **QA & Release Manager** | _______________________ | [ ] APPROVED  [ ] REJECTED | __________ | _______________________ |
| **Project Owner** | _______________________ | [ ] APPROVED  [ ] REJECTED | __________ | _______________________ |
