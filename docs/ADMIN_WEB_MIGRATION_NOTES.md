# MediConnect — Admin Web Portal (React + TypeScript) Migration Architecture Guide

**Document Version:** 1.0.0 (Phase 30 Release Candidate Preparation)
**Target Next Phase:** Post-Phase 30 Web Admin Migration
**Target Tech Stack:** React 19, TypeScript 5, Vite / Next.js, TailwindCSS / Shadcn UI, TanStack Query, Axios

---

## 1. Executive Summary & Purpose

In post-Phase 30 development, administrative operations will transition from the existing mobile Flutter screens to a dedicated, responsive React + TypeScript web application.

> [!IMPORTANT]
> **Phase 30 Constraint Compliance:**
> - Flutter admin screens remain fully intact and operational during Phase 30.
> - The backend API is already structured as a stateless, RESTful, JSON-first platform, allowing the future React web app to seamlessly consume existing `/api/admin/*` endpoints without breaking mobile clients.

---

## 2. Reusable Backend Admin APIs & Endpoints

The MediConnect FastAPI backend exposes complete administrative endpoints secured by `require_admin` middleware. All responses are standard JSON or binary streams (`FileResponse`).

### 2.1 Doctor Verification Pipeline (`/api/admin/doctors`)
| Method | Endpoint | Description | Request Body / Query | Response Model |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/doctors/applications` | List applications by verification status | `status=PENDING\|APPROVED\|REJECTED\|ALL` | `List[AdminDoctorApplicationSummary]` |
| `GET` | `/api/admin/doctors/applications/{id}` | Complete application profile details | URL parameter `doctorProfileId` | `AdminDoctorApplicationDetail` |
| `GET` | `/api/admin/doctors/applications/{id}/documents/{docId}` | Secure document stream (PDF/JPEG/PNG) | URL params `doctorProfileId`, `documentId` | Binary file stream (`inline`) |
| `POST` | `/api/admin/doctors/{id}/approve` | Approve application and activate doctor | URL parameter `doctorProfileId` | `AdminActionResponse` |
| `POST` | `/api/admin/doctors/{id}/reject` | Reject application with explanation | `{"reason": string}` | `AdminActionResponse` |

### 2.2 Health & Wellness Content Management (`/api/admin/content`)
| Method | Endpoint | Description | Request Body / Query | Response Model |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/content` | List all articles (drafts, published, archived) | `status`, `category`, `page`, `pageSize` | `HealthContentListResponse` |
| `GET` | `/api/admin/content/{articleId}` | Fetch article including unpublished draft | URL parameter `articleId` | `HealthContentDetailResponse` |
| `POST` | `/api/admin/content` | Create new clinical health article | `CreateArticleRequest` | `HealthContentDetailResponse` |
| `PUT` | `/api/admin/content/{articleId}` | Update article copy, tags, category | `UpdateArticleRequest` | `HealthContentDetailResponse` |
| `DELETE` | `/api/admin/content/{articleId}` | Soft-delete / unpublish article | URL parameter `articleId` | `{"success": true, "message": string}` |
| `POST` | `/api/admin/content/{articleId}/publish` | Immediate publishing trigger | URL parameter `articleId` | `HealthContentDetailResponse` |

### 2.3 Doctor Review Moderation (`/api/admin/reviews` & `/api/reviews`)
| Method | Endpoint | Description | Request Body / Query | Response Model |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/reviews/reported` | List flagged reviews awaiting decision | `page`, `pageSize` | `List[AdminReportedReviewItem]` |
| `PATCH` | `/api/reviews/{review_id}/moderate` | Moderate review (`HIDE` or `RESTORE`) | `{"action": "HIDE"\|"RESTORE", "reason": string}` | `{"success": true, "message": string}` |
| `DELETE` | `/api/reviews/{review_id}` | Administrative permanent review deletion | URL parameter `review_id` | `{"success": true, "message": string}` |

### 2.4 Platform Analytics & Reporting (`/api/admin/analytics`)
| Method | Endpoint | Description | Request Body / Query | Response Model |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/analytics/overview` | Platform KPI cards (users, revenue, appts) | `startDate`, `endDate` (YYYY-MM-DD) | `AnalyticsOverviewResponse` |
| `GET` | `/api/admin/analytics/appointments` | Appointment status distribution & daily trends | `startDate`, `endDate` (YYYY-MM-DD) | `AppointmentAnalyticsResponse` |
| `GET` | `/api/admin/analytics/payments` | Revenue grouped by currency, refunds, test mode | `startDate`, `endDate` (YYYY-MM-DD) | `PaymentAnalyticsResponse` |
| `GET` | `/api/admin/analytics/doctors` | Verification pipeline stats & specialty breakdown | None | `DoctorAnalyticsResponse` |
| `GET` | `/api/admin/analytics/content` | Readership metrics, categories, bookmarks | None | `ContentAnalyticsResponse` |

---

## 3. Backend Authorization & Security Protocol

### 3.1 Authentication Flow
1. **Admin Login:** The web application submits credentials to `POST /api/auth/login`.
2. **Access Token Generation:** Backend returns an `accessToken` (1-hour lifespan) and an HTTP-only or secure opaque `refreshToken` (7-day lifespan).
3. **Role Enforcement:** In `app/middleware/auth.py`, `require_admin` decodes the JWT, verifies `payload.get("role") == "ADMIN"`, and ensures the user's `accountStatus == "ACTIVE"` and `emailVerified == True`.
4. **Token Refresh:** Web client intercepts HTTP 401 and posts `{"refreshToken": storedRefreshToken}` to `POST /api/auth/refresh` to rotate tokens silently.

### 3.2 CORS Configuration for React Web Portal
In `backend/app/config/settings.py` and `backend/app/main.py`, update `ALLOWED_ORIGINS` to include the React development and production domains:
```bash
# Example .env entry for React Admin Web App
ALLOWED_ORIGINS="http://localhost:3000,http://localhost:5173,https://admin.mediconnect.lk"
```

---

## 4. Current Flutter Admin Screens Reference

These existing screens serve as the authoritative UI/UX reference when developing the React equivalent:

| Flutter Screen File | Screen Title | Key Functional Capabilities |
| :--- | :--- | :--- |
| `admin_dashboard_screen.dart` | Admin Overview & Analytics | Displays KPI summary cards, revenue charts, appointment metrics, and navigation hub. |
| `doctor_applications_screen.dart` | Doctor Verification Queue | Filter tab chips (PENDING, APPROVED, REJECTED), doctor application summary cards. |
| `doctor_application_detail_screen.dart` | Application Review | Full clinical bio, SLMC registration number, document review buttons, Approve/Reject modal. |
| `document_viewer_screen.dart` | Verification Document Viewer | Interactive document renderer for identity proofs, degrees, and medical licenses. |
| `admin_articles_screen.dart` | Health Content Management | Article list, status chips (PUBLISHED, DRAFT), search bar, add article FAB, delete action. |
| `admin_article_editor_screen.dart` | Article Authoring & Editing | Multi-field form for title, read time, category dropdown, rich markdown body, tag editor. |
| `admin_reviews_screen.dart` | Patient Review Moderation | Reported reviews queue, reason display, action buttons to Hide from public view or Restore. |

---

## 5. Recommended React + TypeScript Architecture

```
mediconnect-admin-web/
├── src/
│   ├── api/
│   │   ├── client.ts             # Axios instance with interceptors & JWT refresh
│   │   ├── authApi.ts            # Login, refresh, logout
│   │   ├── doctorAdminApi.ts     # Application listing, review, approve, reject
│   │   ├── contentAdminApi.ts    # Article CRUD and publishing
│   │   ├── reviewAdminApi.ts     # Moderation and report queue
│   │   └── analyticsApi.ts       # Overview, trends, revenue data hooks
│   ├── components/
│   │   ├── layout/               # AdminSidebar, AdminHeader, PageWrapper
│   │   ├── ui/                   # Button, Card, Badge, Modal, DataTable, Input
│   │   └── charts/               # Recharts / Chart.js for analytics graphs
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── DoctorApplicationsPage.tsx
│   │   ├── ApplicationDetailPage.tsx
│   │   ├── ContentManagementPage.tsx
│   │   ├── ArticleEditorPage.tsx
│   │   └── ReviewModerationPage.tsx
│   ├── types/
│   │   ├── auth.types.ts
│   │   ├── doctor.types.ts
│   │   ├── content.types.ts
│   │   └── analytics.types.ts
│   └── App.tsx
```

---

## 6. Planned Backend Extensions for Future Web Admin

The following optional enhancements can be added to the backend during the React migration phase:
1. **User Management Endpoints:** `GET /api/admin/users` (search, pagination, role filter) and `PATCH /api/admin/users/{userId}/status` (suspend/reactivate).
2. **Audit Log Exporter:** `GET /api/admin/audit-logs` (CSV or JSON export of administrative actions).
3. **Live System Metrics:** `GET /api/admin/system-health` (MongoDB ping latency, background reminder worker status).

---

## 7. Migration Safety & Invariants

- **Zero Breaking Changes to Existing Clients:** Existing mobile clients will continue using the shared API without modification.
- **Flutter Admin Deprecation Plan:** Keep mobile admin screens active through initial React rollout. Once the web portal passes end-to-end acceptance testing in production, mobile admin entry points can be removed in a subsequent release.
