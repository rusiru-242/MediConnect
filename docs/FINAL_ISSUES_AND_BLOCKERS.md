# MediConnect — Final Issue Register & Outstanding Blockers

- **Milestone:** Phase 37 — Final Handover & Pre-Launch Review
- **Date:** 2026-10-18
- **Document Purpose:** Transparently account for all outstanding blockers, prerequisites, and operational issues prior to production launch.

---

## 1. Issue Register Overview

| Issue ID | Component | Severity | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| **ISSUE-01** | Mobile Build / CI | **HIGH** | Android Production Signing Keystore Omitted from Git | **BLOCKED (Documented)** |
| **ISSUE-02** | Mobile QA | **MEDIUM** | Physical Android Hardware Fleet Smoke Testing | **BLOCKED (0 Devices)** |
| **ISSUE-03** | Payments | **INFORMATIONAL**| Stripe Gateway Maintained in Test Mode | **PENDING BUSINESS SIGN-OFF** |
| **ISSUE-04** | Notifications | **MEDIUM** | Production Firebase Service Account Credential Provisioning | **PENDING DEPLOYMENT** |
| **ISSUE-05** | Admin Web | **LOW** | React Router v7 Future Flag Deprecation Notices | **INFORMATIONAL** |

---

## 2. Detailed Issue Reports

### ISSUE-01: Android Production Signing Keystore Omitted from Git
- **Component**: `mobile/android/app/build.gradle.kts`
- **Severity**: **HIGH**
- **Status**: **BLOCKED (Manual Prerequisite)**
- **Description**: The project's release signing configuration strictly requires `mobile/android/key.properties` to produce a signed APK or AAB. To prevent critical credential leakage, `key.properties` and `*.jks` are excluded by `.gitignore`. Consequently, automated builds produce unsigned release binaries (`app-release.apk` 66.8 MB, `app-release.aab` 68.5 MB).
- **Reproduction Steps**:
  1. Inspect `mobile/android/app/build.gradle.kts`.
  2. Observe `if (releaseSigning.storeFile != null && releaseSigning.storeFile!!.exists()) { signingConfig = releaseSigning } else { signingConfig = null }`.
  3. Run `flutter build appbundle --release` without `key.properties`.
  4. Output is generated as unsigned bundle.
- **Impact**: Google Play Store and Android Package Manager reject unsigned bundles for production installation.
- **Recommended Fix / Required Manual Action**:
  The Release Manager must securely inject the official organization keystore (`upload-keystore.jks`) onto the secure build runner and create `mobile/android/key.properties` with:
  ```properties
  storePassword=ORGANIZATION_STORE_PASSWORD
  keyPassword=ORGANIZATION_KEY_PASSWORD
  keyAlias=mediconnect-release
  storeFile=/secure/path/to/upload-keystore.jks
  ```
  Then re-run `flutter build appbundle --release`.

---

### ISSUE-02: Physical Android Hardware Fleet Smoke Testing
- **Component**: Mobile QA / Push Notifications
- **Severity**: **MEDIUM**
- **Status**: **BLOCKED (No Hardware Devices Connected)**
- **Description**: All 177 Flutter mobile unit, widget, and integration tests pass cleanly in headless mode. However, the automated CI/CD environment had 0 connected physical Android devices attached via ADB (`adb devices` returned 0 devices).
- **Reproduction Steps**:
  1. Open terminal on build machine.
  2. Run `adb devices`.
  3. Output: `List of devices attached` (empty).
- **Impact**: Real physical push notification presentation in the Android system tray, device vibration, and network transitions (WiFi to 4G/5G) were validated via software mocks rather than physical hardware.
- **Recommended Fix / Required Manual Action**:
  Before public store publishing, the QA lead must install the signed release APK onto at least two physical Android test devices (one on Android 10/11 and one on Android 14) and execute the smoke test protocol in [docs/DEPLOYMENT_RUNBOOK.md](file:///C:/Users/REDTECH/Downloads/MediConnect/docs/DEPLOYMENT_RUNBOOK.md).

---

### ISSUE-03: Stripe Gateway Maintained in Test Mode
- **Component**: `backend/app/routes/payment.py`
- **Severity**: **INFORMATIONAL**
- **Status**: **PENDING BUSINESS SIGN-OFF**
- **Description**: The MediConnect backend is strictly configured with Stripe test keys (`STRIPE_SECRET_KEY` starts with `sk_test_`). Live mode enablement is deliberately prohibited during development and dry run phases.
- **Impact**: Real financial transactions cannot be processed until live keys are provisioned.
- **Recommended Fix / Required Manual Action**:
  Following commercial launch approval, the project owner must update `/etc/mediconnect/backend.env` with the production Stripe live credentials (`sk_live_...` and live `whsec_...`) and verify live webhook delivery.

---

### ISSUE-04: Production Firebase Service Account Credential Provisioning
- **Component**: `backend/app/services/notification_service.py`
- **Severity**: **MEDIUM**
- **Status**: **PENDING DEPLOYMENT**
- **Description**: Real Firebase service account credentials (`service-account.json`) are intentionally omitted from version control to prevent credential exposure.
- **Impact**: Backend FCM push delivery falls back to logging/mock mode when running locally without credentials.
- **Recommended Fix / Required Manual Action**:
  DevOps must download the production Firebase Admin SDK private key JSON from the Firebase Console, place it in a secured directory on the backend server (e.g., `/etc/mediconnect/firebase-key.json`), and set `FIREBASE_CREDENTIALS_PATH` in `backend.env`.

---

### ISSUE-05: React Router v7 Future Flag Deprecation Notices
- **Component**: `admin-web`
- **Severity**: **LOW**
- **Status**: **INFORMATIONAL / NON-BLOCKING**
- **Description**: Vitest console output logs non-blocking deprecation warnings regarding React Router v7 future flags (`v7_startTransition` and `v7_relativeSplatPath`).
- **Impact**: Zero functional or performance impact. All 28 Vitest tests pass cleanly.
- **Recommended Fix**:
  Add `future={{ v7_startTransition: true, v7_relativeSplatPath: true }}` to the router configuration when upgrading dependencies to React Router v7 in future maintenance cycles.
