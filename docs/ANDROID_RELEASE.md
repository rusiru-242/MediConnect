# MediConnect — Android Release Build Guide

- **Application ID:** `com.mediconnect.mediconnect`
- **Minimum SDK:** Flutter Minimum Supported SDK (`minSdkVersion` 21+)
- **Target SDK:** Android 34 (API Level 34)
- **Compilation JVM:** Java / Kotlin JVM 17
- **Build Tool:** Gradle Kotlin DSL (`build.gradle.kts`)

---

## 1. Overview & Architecture

MediConnect is packaged for Android as both an installable APK for internal QA testing and an Android App Bundle (AAB) for publication to the Google Play Store.

### Native Integrations Summary
- **Stripe Payments:** Requires `FlutterFragmentActivity` in `MainActivity.kt` for 3D Secure authentication sheets.
- **Push Notifications:** Firebase Cloud Messaging (`firebase_core`, `firebase_messaging`) and `flutter_local_notifications`.
- **Desugaring:** Modern `java.time` APIs enabled via `coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")`.
- **Network Security:** TLS enforced by default; cleartext allowed only for local loopback/emulators via `res/xml/network_security_config.xml`.

---

## 2. Release Signing Configuration

### 2.1 Generating a Production Keystore
Never use the default Android debug keystore for production releases. Generate a 2048-bit RSA release keystore:

```bash
keytool -genkey -v -keystore upload-keystore.jks \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias upload \
  -storetype JKS
```

Store `upload-keystore.jks` in a secure location (e.g. `mobile/android/upload-keystore.jks` or a hardware security module / CI secrets vault).

### 2.2 Configuring `key.properties`
Create `mobile/android/key.properties` based on `mobile/android/key.properties.example`:

```properties
storePassword=SECURE_KEYSTORE_PASSWORD
keyPassword=SECURE_KEY_PASSWORD
keyAlias=upload
storeFile=upload-keystore.jks
```

> [!CAUTION]
> **Git Safety Rule:** `key.properties`, `*.jks`, and `*.keystore` are strictly excluded in `.gitignore`. Never commit signing credentials, private keys, or passwords to Git.

### 2.3 Keystore Backup & Disaster Recovery
- Keep an encrypted backup of `upload-keystore.jks` in an offline vault (e.g. 1Password, Bitwarden, or encrypted USB stored in a company safe).
- If using Google Play App Signing, Google protects the app signing key in Google Cloud KMS, and you only use the upload key. If the upload key is lost, you can request a reset via the Google Play Console support team.

---

## 3. Build Commands

### 3.1 Pre-Build Validation
Before building release artifacts, verify that all dependencies and tests pass:

```bash
cd mobile
flutter pub get
flutter analyze
flutter test
```

### 3.2 Building a Production APK
To generate a release APK for internal QA or physical device testing:

```bash
# Default production build (defaults to https://api.mediconnect.lk in release mode)
flutter build apk --release

# Explicit production HTTPS API URL via --dart-define
flutter build apk --release --dart-define=API_BASE_URL=https://api.mediconnect.lk

# Staging build with custom backend URL
flutter build apk --release --dart-define=API_BASE_URL=https://staging-api.mediconnect.lk
```

**Artifact Output Location:**
`mobile/build/app/outputs/flutter-apk/app-release.apk`

### 3.3 Building an Android App Bundle (AAB) for Google Play
To generate the optimized AAB bundle for the Google Play Store:

```bash
flutter build appbundle --release --dart-define=API_BASE_URL=https://api.mediconnect.lk
```

**Artifact Output Location:**
`mobile/build/app/outputs/bundle/release/app-release.aab`

---

## 4. Android Network Security Configuration

Production builds prohibit unencrypted cleartext HTTP traffic to prevent credential interception or MITM attacks.

- **Production API:** Forced to use HTTPS with system CA trust anchors.
- **Local Dev / Testing Exception:** `res/xml/network_security_config.xml` allows cleartext traffic strictly for:
  - `localhost` & `127.0.0.1` (ADB reverse over USB)
  - `10.0.2.2` (Android emulator host loopback)
  - Private subnet developer IPs (`192.168.0.0/16`, `10.0.0.0/8`)

---

## 5. Firebase & Push Notifications Setup

1. Register `com.mediconnect.mediconnect` in the [Firebase Console](https://console.firebase.google.com/).
2. Download `google-services.json` and place it in `mobile/android/app/google-services.json`.
3. Add the production SHA-1 and SHA-256 fingerprints from your release keystore to Firebase Console (under Project Settings -> General -> Android apps).
4. Run `keytool -list -v -keystore upload-keystore.jks -alias upload` to view your SHA fingerprints.

---

## 6. Physical Device Testing Protocol

1. Connect the Android phone via USB and enable USB Debugging.
2. If connecting to a local backend instance:
   ```bash
   adb reverse tcp:8000 tcp:8000
   ```
3. Install and run release build:
   ```bash
   flutter install
   ```
4. Perform smoke test:
   - Launch app and verify branding.
   - Test login with verified credentials.
   - Verify appointment booking with Stripe test card `4242 4242 4242 4242`.
   - Verify push notification receipt upon booking confirmation.
