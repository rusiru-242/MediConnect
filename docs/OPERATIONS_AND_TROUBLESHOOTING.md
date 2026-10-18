# MediConnect — Operations & Troubleshooting Guide

- **Version:** 1.0.0
- **Document Status:** Operational Runbook
- **Audience:** DevOps Engineers, System Administrators, SRE, On-Call Support

> [!CAUTION]
> **CRITICAL SECURITY DIRECTIVE:**
> **Never disable security controls to resolve operational issues.**
> Do not disable JWT verification, do not remove CORS origin allowlists, do not permit cleartext HTTP in production, do not bypass Stripe signature verification, and do not weaken database index constraints.

---

## 1. Backend Startup & Runtime Failures

### Issue 1.1: `RuntimeError: JWT_SECRET must be at least 32 bytes (256 bits) in production mode`
- **Symptom**: FastAPI server exits immediately upon launch in production (`ENVIRONMENT=production`).
- **Root Cause**: RFC 7518 compliance guard in `app/main.py:lifespan` requires HMAC SHA-256 secrets to have a minimum entropy of 256 bits (32 bytes).
- **Remediation**:
  1. Generate a compliant 32-byte cryptographic secret:
     ```bash
     openssl rand -hex 32
     ```
  2. Update `JWT_SECRET` in the production environment file (`/etc/mediconnect/backend.env` or container environment).
  3. Restart the service.

### Issue 1.2: `ConnectionError: MONGODB_URI environment variable is not configured`
- **Symptom**: Application fails during startup check or health probe reports `status: degraded`.
- **Root Cause**: `MONGODB_URI` is blank or unset in the runtime environment.
- **Remediation**:
  1. Verify the connection string in the environment file:
     ```bash
     grep MONGODB_URI /etc/mediconnect/backend.env
     ```
  2. Confirm the URI format is valid: `mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<dbname>?retryWrites=true&w=majority`.

### Issue 1.3: MongoDB DNS SRV Resolution Failures
- **Symptom**: `pymongo.errors.ConfigurationError: The resolution lifetime expired after...`
- **Root Cause**: Some local ISPs or corporate DNS servers block or timeout on DNS SRV records (`_mongodb._tcp...`).
- **Remediation**:
  The application includes an automatic fallback in `app/config/database.py` that configures Google (`8.8.8.8`) and Cloudflare (`1.1.1.1`) public resolvers:
  ```python
  import dns.resolver
  resolver = dns.resolver.get_default_resolver()
  resolver.nameservers = ["8.8.8.8", "1.1.1.1"] + resolver.nameservers
  ```
  Ensure outbound UDP port 53 is open to public DNS resolvers on the host firewall.

---

## 2. Client Connectivity & Networking

### Issue 2.1: Android Emulator Cannot Connect to Backend (`SocketException: Connection refused`)
- **Symptom**: Mobile app running in Android Studio emulator displays connection errors.
- **Root Cause**: Inside the Android emulator, `127.0.0.1` refers to the emulator's own loopback interface, not the host computer running FastAPI.
- **Remediation**:
  Launch the Flutter app with the special Android emulator loopback alias `10.0.2.2`:
  ```powershell
  flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
  ```

### Issue 2.2: Physical Android Device Cannot Reach Local Backend
- **Symptom**: Device connected via USB cable fails to load doctor directory.
- **Root Cause**: The physical smartphone cannot resolve `localhost` or private subnet IPs without routing.
- **Remediation**:
  Use ADB reverse port forwarding to forward host port 8000 to the device:
  ```powershell
  adb reverse tcp:8000 tcp:8000
  flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
  ```

### Issue 2.3: Cleartext HTTP Traffic Blocked on Android
- **Symptom**: `CLEARTEXT communication to ... not permitted by network security policy`.
- **Root Cause**: Android 9+ (API 28+) blocks unencrypted HTTP traffic by default.
- **Remediation**:
  - For local development: `mobile/android/app/src/main/res/xml/network_security_config.xml` explicitly permits cleartext only for `10.0.2.2`, `127.0.0.1`, and `localhost`.
  - For production: All non-local traffic must use HTTPS (`https://api.mediconnect.lk`). Never permit global cleartext traffic in release builds.

---

## 3. Web Admin Portal & CORS Troubleshooting

### Issue 3.1: Browser CORS Error in React Admin (`Cross-Origin Request Blocked`)
- **Symptom**: Admin browser console shows CORS policy rejection on `/api/admin/*` endpoints.
- **Root Cause**: The request origin is not listed in `settings.ALLOWED_ORIGINS` in the backend.
- **Remediation**:
  1. Check the allowed origins in `backend/.env`:
     ```dotenv
     ALLOWED_ORIGINS=https://admin.mediconnect.lk,http://localhost:5173,http://localhost:3000
     ```
  2. Confirm the scheme and port match exactly (no trailing slashes).
  3. Restart FastAPI.

### Issue 3.2: Admin Web Refresh Returns 404 Not Found on Static Host
- **Symptom**: Navigating to `https://admin.mediconnect.lk/doctors` works, but refreshing the browser returns a 404 error.
- **Root Cause**: The hosting provider is treating `/doctors` as a static file path instead of falling back to the SPA entrypoint (`index.html`).
- **Remediation**:
  - **Nginx**: Ensure `try_files $uri $uri/ /index.html;` is present in `nginx.conf`.
  - **Cloudflare Pages / Netlify**: Verify `dist/_redirects` contains `/* /index.html 200`.

### Issue 3.3: Doctor or Patient Login Blocked from Web Admin
- **Symptom**: User logs in but gets error: *"Access denied: You must hold the ADMIN role to access this portal."*
- **Root Cause**: This is intentional security behavior. Only accounts with `role: "ADMIN"` are authorized to access the React Admin portal.
- **Remediation**:
  Patients and Doctors must use the Flutter Mobile App. Administrators must log in with an administrative email account provisioned with `role: "ADMIN"`.

---

## 4. Payment & Stripe Webhook Issues

### Issue 4.1: Stripe Webhook Rejection (`HTTP 400: Invalid signature`)
- **Symptom**: Stripe Developer Dashboard reports webhook delivery failures with HTTP 400.
- **Root Cause**: Mismatch between the signing secret in Stripe (`whsec_...`) and `STRIPE_WEBHOOK_SECRET` in backend configuration, or clock drift on the server.
- **Remediation**:
  1. Retrieve the exact signing secret for your endpoint from `https://dashboard.stripe.com/webhooks`.
  2. Verify NTP clock synchronization on the server (`timedatectl status`). Clock drift > 5 minutes causes Stripe HMAC verification to fail.
  3. Update `STRIPE_WEBHOOK_SECRET` in `/etc/mediconnect/backend.env` and restart.

### Issue 4.2: Duplicate Webhook Events Causing Multiple Notifications
- **Symptom**: Patient receives duplicate confirmation notifications.
- **Root Cause**: Network retry from Stripe when the backend takes > 30 seconds to respond.
- **Remediation**:
  The payment webhook handler in `app/routes/payment.py` is fully idempotent. It checks the unique index on `paymentIntentId`. Confirm that database indexes are healthy by calling `ensure_indexes()`.

---

## 5. Firebase & Push Notifications

### Issue 5.1: Push Notifications Not Delivered
- **Symptom**: No push notification received on mobile client after booking confirmation.
- **Root Cause**:
  1. Firebase credentials missing or expired on backend (`FIREBASE_CREDENTIALS_PATH`).
  2. Device token not registered (e.g., notification permission denied by user).
- **Remediation**:
  1. Verify backend logs for: `Firebase initialization failed` or `Error sending FCM push`.
  2. Check `device_tokens` collection in MongoDB to verify the user has an active token.
  3. Re-request notification permission on the client.

---

## 6. AI Multi-Agent Service Timeouts

### Issue 6.1: AI Doctor Recommendations or Booking Assistant Hanging
- **Symptom**: Patient clicks "Find Doctors with AI" and the request takes > 10 seconds or fails.
- **Root Cause**: External OpenAI / Google Gemini API rate limiting or network latency.
- **Remediation**:
  1. The backend implements a strict timeout guard (`AI_TIMEOUT_SECONDS = 5`).
  2. If the external provider fails or times out, the service falls back to rule-based keyword specialty matching without crashing.
  3. Check API quotas in Google Cloud Console or OpenAI Dashboard.

---

## 7. Logging & Diagnostic Procedures

### Inspecting Production Logs:
```bash
# Docker Container Logs
docker logs -f --tail 200 mediconnect-backend

# Systemd Service Logs
sudo journalctl -u mediconnect-backend -f -n 100

# Nginx Access & Error Logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Checking Real-Time Health:
```bash
curl -i https://api.mediconnect.lk/health
curl -i https://api.mediconnect.lk/ready
```
