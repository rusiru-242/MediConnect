# MediConnect — React + TypeScript Web Admin Panel

Welcome to the **MediConnect Web Admin Portal**, a secure, responsive, production-quality clinical operations console built for managing the MediConnect telemedicine platform in Sri Lanka.

---

## 1. Architecture & Tech Stack

- **Framework:** React 18 + TypeScript + Vite
- **Styling:** Tailwind CSS (Curated medical color palette: Teal primary accents `#0d9488`, slate/neutral surfaces, accessible contrast)
- **Routing:** React Router v6 with strict `ProtectedRoute` guards and unauthorized redirects
- **State & Server Cache:** TanStack Query v5 (`@tanstack/react-query`) with automatic background invalidation
- **HTTP Client:** Axios with centralized Bearer token interceptor, 401 session expiration handler, and least-privilege normalization
- **Form Management:** React Hook Form + Zod schema validation
- **Data Visualizations:** Recharts (responsive area charts, daily transaction bar charts, and appointment status distribution pie charts)
- **Iconography:** Lucide React
- **Testing:** Vitest + React Testing Library + JSDOM

---

## 2. Directory Structure

```
admin-web/
├── src/
│   ├── api/                     # Typed Axios client & service modules
│   │   ├── client.ts            # Base Axios instance & auth interceptor
│   │   ├── authApi.ts           # Admin authentication & connectivity check
│   │   ├── analyticsApi.ts      # Aggregated metrics & trends
│   │   ├── doctorVerificationApi.ts # Doctor credentials review & document streaming
│   │   ├── doctorsApi.ts        # Doctors directory
│   │   ├── usersApi.ts          # Privacy-safe user administration
│   │   ├── appointmentsApi.ts   # Appointment monitoring & detail inspection
│   │   ├── paymentsApi.ts       # Stripe webhook transactions & financial oversight
│   │   ├── reviewsApi.ts        # Moderation queue & reported feedback
│   │   └── contentApi.ts        # Health articles CMS
│   ├── components/
│   │   ├── common/              # Reusable UI system (Button, Input, Select, Modal, etc.)
│   │   └── layout/              # Responsive Sidebar, TopNav, Breadcrumbs, AdminLayout
│   ├── context/
│   │   └── AuthContext.tsx      # Admin authentication context & session persistence
│   ├── pages/                   # Operational pages
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── DoctorVerificationPage.tsx
│   │   ├── DoctorsPage.tsx
│   │   ├── UsersPage.tsx
│   │   ├── AppointmentsPage.tsx
│   │   ├── PaymentsPage.tsx
│   │   ├── ReviewsPage.tsx
│   │   ├── ContentPage.tsx
│   │   ├── AnalyticsPage.tsx
│   │   ├── SettingsPage.tsx
│   │   └── UnauthorizedPage.tsx
│   ├── test/                    # Vitest automated test suites
│   ├── types/                   # Strict TypeScript domain interfaces
│   ├── App.tsx                  # Application root & routing configuration
│   ├── main.tsx                 # DOM Entrypoint
│   └── index.css                # Tailwind CSS base styles & typography
├── .env.example                 # Safe environment template
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

---

## 3. Setup & Development Instructions

### Prerequisites
- Node.js `v20+` or `v24+`
- npm `v10+` or `v11+`
- Running MediConnect FastAPI backend (`http://localhost:8000`)

### Installation
```bash
cd admin-web
npm install
```

### Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default configuration:
```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_APP_TITLE=MediConnect Admin
```
> **Security Notice:** Never store JWT signing secrets, database credentials, or Stripe secret keys in client-side `VITE_` variables.

### Development Server
```bash
npm run dev
```
Access the admin portal at `http://localhost:5173`.

### Quality & Testing Commands
```bash
# Type checking
npm run typecheck

# Code linting
npm run lint

# Automated test suite
npm run test

# Production bundle build
npm run build
```

---

## 4. Security Architecture

1. **Role-Based Authorization Enforcement:**
   - Client routes check for `ADMIN` role.
   - The FastAPI backend validates `require_admin` on every single protected endpoint. Frontend route guards are never solely trusted.
2. **Least-Privilege API Projections:**
   - Password hashes, password salts, and raw authentication secrets are stripped at the database projection layer.
   - Private patient medical records, diagnostic attachments, and sensitive prescriptions are inaccessible from admin user lists.
3. **Document Streaming:**
   - Verification documents are securely served through authenticated streaming routes (`/api/admin/doctors/applications/{id}/documents/{key}`), mitigating directory traversal vulnerabilities and avoiding public URL leakage.
4. **Session Isolation:**
   - Tokens are persisted in tab-isolated `sessionStorage`, ensuring they are automatically discarded when the administrator closes their browser tab.
5. **Double-Action & Concurrency Safeguards:**
   - Status transitions (such as doctor approval/rejection) verify current database state atomically, preventing race conditions or conflicting administrative approvals.
   - Administrators cannot suspend or deactivate their own active accounts.

---

## 5. Phase 32 Migration Prerequisites

During Phase 31, all Flutter mobile admin screens were retained to guarantee zero disruption to existing patient and doctor workflows. In Phase 32, the following Flutter screens can be safely deprecated:
- `mobile/lib/screens/admin/admin_dashboard_screen.dart`
- `mobile/lib/screens/admin/doctor_applications_screen.dart`
- `mobile/lib/screens/admin/doctor_application_detail_screen.dart`
- `mobile/lib/screens/admin/document_viewer_screen.dart`
- `mobile/lib/screens/admin/admin_articles_screen.dart`
- `mobile/lib/screens/admin/admin_article_editor_screen.dart`
- `mobile/lib/screens/admin/admin_reviews_screen.dart`
