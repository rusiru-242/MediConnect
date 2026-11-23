# MediConnect — REST API Specification & Endpoint Overview

- **Base URL**: `http://localhost:8000/api` (Local) / `https://api.mediconnect.lk/api` (Production)
- **Version**: 1.0.0
- **Authentication**: Bearer JWT token header (`Authorization: Bearer <token>`)

---

## 1. System Health & Probes (Public)

| Method | Path | Description | Access | Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | Root service status | Public | `{"app": "MediConnect", "status": "running"}` |
| `GET` | `/health` | API and MongoDB connectivity | Public | `{"status": "healthy", "database": {"connected": true}}` |
| `GET` | `/ready` | Orchestrator readiness check | Public | `{"status": "ready"}` (HTTP 200 or 503) |

---

## 2. Authentication & Identity Management (`/api/auth`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Public | Register a new Patient; sends 6-digit verification OTP. |
| `POST` | `/api/auth/register-doctor` | Public | Register Doctor applicant with SLMC credentials and PDF uploads. |
| `POST` | `/api/auth/verify-email` | Public | Verify email address using 6-digit OTP code. |
| `POST` | `/api/auth/resend-verification` | Public | Request a fresh verification OTP email. |
| `POST` | `/api/auth/login` | Public | Authenticate user; returns `accessToken`, `refreshToken`, and user metadata. |
| `GET` | `/api/auth/me` | Authenticated | Retrieve current user profile and session details. |
| `POST` | `/api/auth/refresh` | Public | Exchange valid refresh token for a fresh access token. |
| `POST` | `/api/auth/logout` | Authenticated | Terminate session and invalidate server-side refresh token. |
| `POST` | `/api/auth/forgot-password` | Public | Initiate password reset flow; sends reset OTP to email. |
| `POST` | `/api/auth/verify-reset-otp` | Public | Verify reset OTP before submitting new password. |
| `POST` | `/api/auth/reset-password` | Public | Complete password reset with new password. |
| `POST` | `/api/auth/google` | Public | Authenticate via Google OAuth token. |

---

## 3. Doctors & Availability (`/api/doctors`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/doctors` | Authenticated | Directory search with specialty, name, and availability filters. |
| `GET` | `/api/doctors/{doctorId}` | Authenticated | View public doctor profile, qualifications, and consultation fee. |
| `GET` | `/api/doctors/{doctorId}/availability` | Authenticated | View public 30-minute time slots for a given doctor on a date. |
| `GET` | `/api/doctors/me/application-status` | DOCTOR | Check SLMC application approval status (`PENDING`/`APPROVED`). |
| `GET` | `/api/doctors/me/availability` | Verified DOCTOR | List doctor's own configured availability slots. |
| `POST` | `/api/doctors/me/availability` | Verified DOCTOR | Create new availability schedule for a date range. |
| `PUT` | `/api/doctors/me/availability/{id}`| Verified DOCTOR | Update existing availability slot time or capacity. |
| `DELETE`| `/api/doctors/me/availability/{id}`| Verified DOCTOR | Disable or delete an availability schedule. |
| `GET` | `/api/doctors/me/appointments` | Verified DOCTOR | List all upcoming and completed doctor appointments. |
| `POST` | `/api/doctors/me/appointments/{id}/confirm` | Verified DOCTOR | Confirm a booked appointment. |
| `POST` | `/api/doctors/me/appointments/{id}/complete`| Verified DOCTOR | Mark appointment as COMPLETED. |
| `POST` | `/api/doctors/me/appointments/{id}/cancel` | Verified DOCTOR | Cancel appointment with cancellation reason. |

---

## 4. Appointments & Booking (`/api/appointments`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/appointments` | PATIENT | Reserve an appointment slot; initiates payment hold. |
| `GET` | `/api/appointments/me` | PATIENT | List patient's upcoming and historical appointments. |
| `GET` | `/api/appointments/{id}` | Patient or Doctor | View appointment details, doctor info, and payment status. |
| `POST` | `/api/appointments/{id}/cancel` | Patient or Doctor | Cancel active appointment. |
| `GET` | `/api/appointments/doctor/list`| Verified DOCTOR | List doctor's schedule appointments with status filter. |
| `PUT` | `/api/appointments/{id}/status`| Verified DOCTOR | Update appointment status. |

---

## 5. Payments & Stripe Integration (`/api/payments`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/payments/create-intent` | PATIENT | Generate Stripe `PaymentIntent` for appointment fee. |
| `POST` | `/api/payments/webhook` | Stripe System | Stripe HMAC SHA-256 webhook handler (`payment_intent.succeeded`). |
| `GET` | `/api/payments/me` | PATIENT | View patient payment receipts and transaction history. |
| `GET` | `/api/payments/{id}/status` | PATIENT | Check real-time payment reconciliation status. |

---

## 6. Medical Records & Consultations (`/api/medical-records`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/medical-records` | Verified DOCTOR | Record clinical notes, assessment, and treatment plan for a completed visit. |
| `GET` | `/api/medical-records/me` | PATIENT | List all consultation records for the authenticated patient. |
| `GET` | `/api/medical-records/{id}` | Patient or Doctor | View single medical record (Enforces strict IDOR protection). |
| `PATCH`| `/api/medical-records/{id}` | Treating DOCTOR | Add addendum to medical record with audit log trail. |

---

## 7. Digital Prescriptions (`/api/prescriptions`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/prescriptions` | Verified DOCTOR | Issue structured digital prescription linked to consultation. |
| `GET` | `/api/prescriptions/me` | PATIENT | List all digital prescriptions issued to the authenticated patient. |
| `GET` | `/api/prescriptions/{id}` | Patient or Doctor | View structured medication items, dosages, and instructions. |
| `PATCH`| `/api/prescriptions/{id}` | Treating DOCTOR | Amend prescription details with recorded amendment history. |
| `GET` | `/api/prescriptions/{id}/pdf` | Patient or Doctor | Generate and download cryptographically signed prescription PDF. |

---

## 8. Smart Medication Reminders (`/api/medication-reminders`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/medication-reminders` | PATIENT | Create daily medication reminder schedule from prescription. |
| `GET` | `/api/medication-reminders` | PATIENT | List active medication reminders. |
| `GET` | `/api/medication-reminders/today`| PATIENT | View today's due doses with taken/missed statuses. |
| `GET` | `/api/medication-reminders/history`| PATIENT | View dose logging history. |
| `GET` | `/api/medication-reminders/adherence`| PATIENT | Calculate percentage medication adherence score. |
| `GET` | `/api/medication-reminders/{id}`| PATIENT | Get specific medication reminder details. |
| `PATCH`| `/api/medication-reminders/{id}`| PATIENT | Update reminder times or dosages. |
| `DELETE`| `/api/medication-reminders/{id}`| PATIENT | Archive or stop a medication reminder. |
| `POST` | `/api/medication-reminders/{id}/events` | PATIENT | Log dose action (`TAKEN`, `SKIPPED`, `MISSED`). |

---

## 9. Doctor Reviews & Ratings (`/api/reviews`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/reviews` | PATIENT | Submit star rating (1-5) and review for a completed appointment. |
| `GET` | `/api/doctors/{id}/reviews` | Authenticated | List published reviews for a doctor. |
| `GET` | `/api/doctors/{id}/rating-summary`| Authenticated | Get average rating and score distribution breakdown. |
| `GET` | `/api/reviews/me` | PATIENT | View patient's own submitted reviews. |
| `PATCH`| `/api/reviews/{id}` | PATIENT | Edit submitted review text or rating. |
| `DELETE`| `/api/reviews/{id}` | PATIENT | Delete patient review. |
| `POST` | `/api/reviews/{id}/report` | Authenticated | Flag inappropriate review for administrative moderation. |
| `GET` | `/api/admin/reviews/reported` | ADMIN | List flagged reviews awaiting moderation review. |
| `PATCH`| `/api/reviews/{id}/moderate` | ADMIN | Approve, hide, or dismiss reported review with reason. |

---

## 10. Health Content & Education (`/api/content`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/content` | Public / Patient | Public health article feed with category and tag filters. |
| `GET` | `/api/content/{identifier}` | Public / Patient | View full health article with medical disclaimer. |
| `GET` | `/api/content/categories` | Public / Patient | List health wellness topic categories. |
| `GET` | `/api/content/bookmarks` | PATIENT | List saved articles bookmarked by the patient. |
| `POST` | `/api/content/bookmarks/{id}`| PATIENT | Bookmark an article for offline reading. |
| `DELETE`| `/api/content/bookmarks/{id}`| PATIENT | Remove article from bookmarks. |

---

## 11. Admin Web Management (`/api/admin`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/doctors/applications` | ADMIN | List doctor onboarding applications with status filter. |
| `GET` | `/api/admin/doctors/applications/{id}` | ADMIN | View doctor credentials, SLMC details, and submitted documents. |
| `GET` | `/api/admin/doctors/applications/{id}/documents/{docId}` | ADMIN | Securely stream doctor verification document. |
| `POST` | `/api/admin/doctors/{id}/approve` | ADMIN | Approve doctor application; activates account immediately. |
| `POST` | `/api/admin/doctors/{id}/reject` | ADMIN | Reject application with mandatory audit reason. |
| `GET` | `/api/admin/users` | ADMIN | Privacy-conscious user directory table with role search. |
| `PATCH`| `/api/admin/users/{userId}/status` | ADMIN | Suspend (`SUSPENDED`) or activate (`ACTIVE`) user account. |
| `GET` | `/api/admin/doctors` | ADMIN | Directory of approved and verified practicing doctors. |
| `GET` | `/api/admin/appointments` | ADMIN | Platform-wide appointment monitoring table. |
| `GET` | `/api/admin/payments` | ADMIN | Centralized financial audit and payment reconciliation table. |
| `GET` | `/api/admin/reviews` | ADMIN | Global review oversight list. |
| `GET` | `/api/admin/content` | ADMIN | List administrative health content drafts and published posts. |
| `POST` | `/api/admin/content` | ADMIN | Draft a new health and wellness article. |
| `PATCH`| `/api/admin/content/{id}` | ADMIN | Edit existing article content, tags, or category. |
| `POST` | `/api/admin/content/{id}/publish` | ADMIN | Publish draft article to public feed. |
| `POST` | `/api/admin/content/{id}/archive` | ADMIN | Remove published article from public discovery. |

---

## 12. Admin Analytics (`/api/admin/analytics`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/analytics/overview` | ADMIN | High-level platform KPIs (patients, doctors, revenue, appointments). |
| `GET` | `/api/admin/analytics/appointments` | ADMIN | Appointment volume trends grouped by day/week/month. |
| `GET` | `/api/admin/analytics/payments` | ADMIN | Revenue analysis and transaction settlement totals. |
| `GET` | `/api/admin/analytics/doctors` | ADMIN | Doctor specialty distribution and performance metrics. |
| `GET` | `/api/admin/analytics/content` | ADMIN | Article reading metrics, engagement, and bookmarks. |

---

## 13. AI Multi-Agent Services (`/api/ai`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/ai/doctor-recommendations`| PATIENT | Suggests doctors based on natural language symptoms. |
| `POST` | `/api/ai/booking/sessions` | PATIENT | Start a multi-turn conversational booking assistant session. |
| `GET` | `/api/ai/booking/sessions/{id}`| PATIENT | Retrieve conversational state and candidate selections. |
| `POST` | `/api/ai/booking/sessions/{id}/messages` | PATIENT | Send message to booking assistant. |
| `POST` | `/api/ai/booking/sessions/{id}/select-doctor` | PATIENT | Confirm doctor selection within AI session. |
| `POST` | `/api/ai/booking/sessions/{id}/select-slot` | PATIENT | Confirm time slot within AI session. |
| `POST` | `/api/ai/booking/sessions/{id}/confirm` | PATIENT | Finalize reservation with mandatory patient confirmation. |
| `POST` | `/api/ai/booking/sessions/{id}/cancel` | PATIENT | Cancel active booking assistant session. |
| `GET` | `/api/ai/booking/sessions/{id}/payment-status` | PATIENT | Check payment state of assistant-initiated booking. |
| `POST` | `/api/ai/health-chat/sessions` | PATIENT | Initiate general wellness AI health chat. |
| `GET` | `/api/ai/health-chat/sessions/{id}` | PATIENT | Fetch health chat message history. |
| `POST` | `/api/ai/health-chat/sessions/{id}/messages` | PATIENT | Query health assistant (Includes medical disclaimer). |
| `DELETE`| `/api/ai/health-chat/sessions/{id}` | PATIENT | Clear and delete health chat conversation history. |

---

## 14. Notifications & Device Tokens (`/api/notifications`)

| Method | Path | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/notifications` | Authenticated | List in-app notifications for authenticated user. |
| `GET` | `/api/notifications/unread-count`| Authenticated | Get count of unread notification items. |
| `PATCH`| `/api/notifications/{id}/read` | Authenticated | Mark single notification as read. |
| `PATCH`| `/api/notifications/read-all` | Authenticated | Mark all notifications as read. |
| `POST` | `/api/notifications/devices` | Authenticated | Register FCM device token with cross-account isolation. |
| `DELETE`| `/api/notifications/devices` | Authenticated | De-register FCM device token upon user logout. |
