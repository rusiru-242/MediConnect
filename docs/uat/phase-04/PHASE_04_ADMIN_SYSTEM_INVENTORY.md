# Phase 04 — Admin System Inventory

For: reviewers and the Phase 05 team. Source: `admin-web/src` (React 18, TypeScript, React Query, Recharts) and `backend/app` at the Phase 04 branch. 2026-11-26.

## Key and scope

**Status key:**

| Status | Meaning |
|---|---|
| **Implemented** | Works end to end and was tested |
| **Implemented (fixed P04-Nxx)** | Was defective; fixed in Phase 04 |
| **Partial** | Works with stated limits |
| **Not implemented** | No code path exists |
| **Owner decision** | Behaviour depends on a policy that has not been decided |

**Endpoint counts:**
- **Admin-only endpoints:** 11 (`routes/admin.py`), 15 of 18 (`routes/admin_workflow.py`; the other 3 are ticket and refund-request endpoints for any signed-in user), 23 of 26 (`routes/security_monitoring.py`; the others are 2 public health probes and, before P04-N13, the heartbeat), 5 (`routes/analytics.py`), and admin content routes in `routes/health_content.py`.
- **Authorization:** every admin endpoint uses `require_admin`, which reads the role from the **database account**, not the token.
  - A validly signed patient token claiming `role: ADMIN` gets 403 (A-01h).
  - Suspension takes effect on the next request (A-03g).

## 1. Feature map

| Feature | React page / component | API endpoint(s) | Service | Collections | Authorization | Tests | Status |
|---|---|---|---|---|---|---|---|
| Login, session, logout | `LoginPage`, `AuthContext`, `api/client.ts` (sessionStorage token; 401 → `/login?expired=1`) | `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me` | `auth_service` | `users`, `refresh_tokens` | Admin web refuses non-ADMIN roles in the UI; the backend enforces per endpoint | `auth.test.tsx`; A-01a–h; A-01c-ui, A-01d-ui | Implemented |
| Dashboard KPIs | `DashboardPage`, `StatCard` | `/admin/analytics/overview`, `/admin/analytics/appointments` (last 30 Colombo days) | `analytics_service`, `financial_metrics` | `users`, `doctor_profiles`, `appointments`, `payments`, `refund_requests` | `require_admin` | `dashboard.test.tsx`; A-02a–d; A-16a1 | Implemented (fixed P04-N05/N07/N21) |
| Admin assistant (dashboard) | `DashboardPage` assistant box | `/admin/workflow/assistant` | keyword router → `AIOrchestrator.execute` (read-only registry) | as the tools read | `require_admin`; tool roles `ADMIN_ROLES` | A-15a–d | Implemented (deterministic) |
| Doctor verification | `DoctorVerificationPage`, `ConfirmDialog` | `/admin/doctors/applications`, `/applications/{id}`, `/applications/{id}/documents/{doc}`, `/admin/doctors/{id}/approve`, `/reject`, `/admin/workflow/doctor-verification/{id}/ai-review` | `admin_service`, `doctor_verification_assistant`, `document_storage_service` | `doctor_profiles`, `users`, `notifications`, `admin_audit_logs`, files under `uploads/doctor_verification` | `require_admin`; traversal-safe file path | `doctorVerification.test.tsx`; `test_n08_…`; A-03a–i | Implemented (fixed P04-N08/N21) |
| Doctor directory | `DoctorsPage` | `/admin/doctors` | `admin_service.list_doctors` | `doctor_profiles`, `users`, `doctor_reviews` | `require_admin` | A-04b | Implemented |
| Users and account status | `UsersPage`, `ConfirmDialog` | `/admin/users`, `PATCH /admin/users/{id}/status` | `admin_service` | `users`, `refresh_tokens`, `admin_audit_logs` | `require_admin`; no self-change; suspend/reinstate only | `management.test.tsx`; `test_n08_…`; A-04a–e; A-16b/d | Implemented (fixed P04-N08) |
| Appointments | `AppointmentsPage` | `/admin/appointments` (read-only) | `admin_service.list_appointments` | `appointments`, `users`, `doctor_profiles`, `refund_requests` | `require_admin`; no admin status-change route (the status PUT is doctor-only, 403 for admin, A-07f) | `phase04Admin.test.tsx`; `test_n03_…`; A-05a–f | Implemented (fixed P3-B2 / P04-N03) |
| Payments oversight | `PaymentsPage` | `/admin/payments`, `/admin/workflow/payments` (masked monitored list) | `admin_service.list_payments`, `payment_monitoring_service` | `payments`, `appointments` | `require_admin` | `test_n04_…`; A-07a/b/c | Implemented (fixed P04-N04) |
| Reconciliation | `ReconciliationPage` | `/admin/workflow/reconciliation/run`, `/issues`; `POST /payments/{id}/reconcile-refund` | `payment_monitoring_service`; payment route | `payments`, `appointments`, `refund_requests` | `require_admin` | `test_n11_…`; A-07d/e | Implemented (fixed P04-N11); reconcile-refund not audited (P4-O7) |
| Refund review | `RefundsPage`, `utils/refunds.ts` | `/admin/workflow/refunds` (`status`, `source`), `/refunds/{id}`, `/approve`, `/reject`; `POST /admin/workflow/refunds` (patient's own appointment) | `refund_service` (Stripe test mode) | `refund_requests`, `payments`, `appointments`, `appointment_events`, `notifications`, `admin_audit_logs` | `require_admin` for review; creation requires appointment ownership | `phase04Admin.test.tsx`; Phase 02 refund tests; `test_n09_…`, `test_n10_…`; A-10a–j; A-16f | Implemented (fixed B15, P3-B3, P04-N09/N10/N23) |
| Support tickets | `SupportTicketsPage` | `/admin/workflow/tickets` (list/create/get), `/{id}/ai-draft`, `/{id}/reply` | `support_ticket_service` | `support_tickets`, `notifications`, `admin_audit_logs` | List/get: owner or admin; create: any signed-in user (own appointment only); draft/reply: admin | `test_n18_…`; A-09a–e | Partial: **no user reply or reopen endpoint, and no mobile screen** (Not implemented) |
| Reports and CSV | `ReportsPage` | `/admin/workflow/reports/generate`, `/export-csv` | `admin_report_service`, `financial_metrics` | appointments, payments, refunds, doctor profiles, tickets | `require_admin`; generation and export audited | `test_n17_…`; A-13a–e | Implemented (fixed P04-N05/N17/N19) |
| Audit logs | `AuditLogsPage` | `/admin/workflow/audit-logs` (GET only) | `admin_audit_service` | `admin_audit_logs` | `require_admin`; no write route | `test_a14_…`; A-14d/e | Implemented |
| Platform monitoring | `MonitoringPage` (health tab) | `/security/monitoring/platform`, `/workers/heartbeat` (admin), `/health/live`, `/health/ready` (public, no secrets) | `platform_monitoring_service` | `worker_heartbeats`, `operational_incidents`, `fraud_risk_assessments` | `require_admin` (probes public) | `test_n13_n14_…`; A-11a–e; A-11-ui | Implemented (fixed P04-N13/N14) |
| Notification monitoring | `MonitoringPage` (outbox tab) | `/security/monitoring/notifications`, `/process-retries`, `/dead-letters`, `/dead-letters/{id}/retry` | `notification_monitoring_service` | `appointments.confirmationOutbox`, `care_reminder_events`, `notifications`, `notification_dead_letters` | `require_admin` | `test_n15_…`; Phase 7 tests; A-12a–e | Implemented (fixed P04-N15) |
| Fraud signals | `MonitoringPage` (fraud tab) | `/security/fraud/assessments`, `/evaluate`, `/{id}/review`; `/security/events` | `fraud_detection_service`, `security_event_service` | `fraud_risk_assessments`, `security_events`, `payments`, `appointments`, `refund_requests` | `require_admin` | `test_n12_…`, `test_n22_…`; A-08a–d | Partial (see §2) |
| Incidents and workflows | `MonitoringPage` (incidents, workflows) | `/security/incidents*`, `/security/monitoring/workflows*` | `incident_management_service`, `workflow_monitoring_service` | `operational_incidents`, `workflow_monitoring_events` | `require_admin` | Phase 7 tests; `test_n20_…` | Implemented (fixed P04-N20) |
| Monitoring assistant | `MonitoringPage` (assistant) | `/security/ai-assistant/chat` | `admin_monitoring_assistant` (keyword router) | as read | `require_admin` | Phase 7 tests; `test_n16_…`; A-15e | Implemented (deterministic; fixed P04-N16) |
| AI provider metrics | `MonitoringPage` (AI tab) | `/security/monitoring/ai-providers` | `ai_provider_monitoring_service` (in-memory) | none (process memory) | `require_admin` | A-15e | Partial: resets on restart |
| Platform analytics | `AnalyticsPage` | `/admin/analytics/overview`, `/appointments`, `/payments`, `/doctors`, `/content` | `analytics_service`, `financial_metrics` | as above | `require_admin` | A-06a–e | Implemented (fixed P04-N05/N06/N07) |
| Reviews moderation | `ReviewsPage` | `/admin/reviews`, review moderation routes | `review_service` | `doctor_reviews` | `require_admin` | `management.test.tsx` | Implemented (not in Phase 04 scope beyond regression) |
| Health content | `ContentPage` | `/admin/content/*` | `health_content_service` | `health_content`, `content_bookmarks` | `require_admin` | `management.test.tsx` | Implemented (regression only) |
| Settings / profile | `SettingsPage` | `/auth/me` | — | `users` | signed-in admin | navigation test | Implemented (display only) |

**UI behaviours verified in a real browser** (Chrome against the UAT backend):
- **Every page:** all 16 pages load without an error boundary.
- **States and safeguards:**
  - loading states
  - error state (refunds)
  - empty states
  - confirmation dialogs (suspend; refund approve/reject)
  - repeated-click protection (P04-N23)
- **Layout:** 390 px responsive layout (no page-level horizontal scroll).
- **Consultation type:** in-person only. No video consultation UI exists in the admin web app, and the API reports `consultationType: IN_PERSON` (A-05d).

## 2. The nine admin AI components

In this table, "AI" means a component that the specification calls an AI agent. **None of the nine calls an LLM.** All are deterministic rules or read-only database tools.

| # | Component | Entry point | Behaviour | Tools | State changes | Status |
|---|---|---|---|---|---|---|
| 22 | Doctor Verification Assistant | `GET /admin/workflow/doctor-verification/{id}/ai-review`; tools `get_doctor_verification_review`, `prepare_doctor_verification_decision` | Rule checklist: fields, documents, registration format, experience bounds, degree keywords, completeness %. `registrationOfficiallyVerified=false` and `humanDecisionRequired=true` | read-only | None (approval is a separate admin endpoint) | Implemented |
| 23 | Platform Analytics Assistant | `/admin/workflow/assistant` (keyword router), tool `get_admin_dashboard_metrics` | Shared refund-aware figures; Asia/Colombo ranges | read-only | None | Implemented (fixed P04-N05) |
| 24 | Payment Monitoring Agent | `/admin/workflow/payments`, `/reconciliation/*`; tools `get_payment_transactions`, `get_payment_reconciliation_issues` | Deterministic reconciliation rules | read-only | None | Implemented (fixed P04-N11) |
| 25 | Fraud Detection Agent | `/security/fraud/*`; tools `get_fraud_alerts`, `get_fraud_review_details` | Six evaluated rules:<br>• failed payments<br>• booking burst<br>• cancellations<br>• refund requests<br>• auth-failure burst<br>• shared PaymentIntent<br>One declared rule (slot hoarding) is **not implemented**. Rule-weight sum, not a probability | read-only (evaluation stores an assessment; review is an admin action) | Never suspends or restricts an account | Partial |
| 26 | Customer Support Assistant | `/admin/workflow/tickets/{id}/ai-draft`; tool `draft_support_response` | Keyword category/priority and **fixed template** drafts; emergency keywords produce a 1990 advisory | read-only (draft is returned, not stored or sent) | Sending is a separate admin reply | Partial (template, not generative; no user reply flow) |
| 27 | Refund Management Agent | tools `get_refund_request_details`, `prepare_refund_review`; refund policy calculation | Existing policy:<br>• doctor cancellation: 100%<br>• cancelled 24 h or more before the visit: 100%<br>• cancelled less than 24 h before: 80%<br>• visit time passed or completed: dispute | read-only | Approval and rejection only through admin endpoints | Implemented |
| 28 | System Monitoring Agent | `/security/ai-assistant/chat`; tools `get_platform_health`, `get_worker_status`, `get_ai_provider_metrics`, `get_stuck_workflows`, `get_open_incidents` | Keyword router over real health data | read-only | None | Implemented (fixed P04-N13/N14/N16) |
| 29 | Notification Monitoring Agent | tools `get_notification_queue_status`, `get_notification_failures`; `/security/monitoring/notifications*` | Counts from outbox and reminder events; provider status | read-only (retry processing is an admin endpoint) | Re-queue only by explicit admin action | Implemented (fixed P04-N15) |
| 30 | Report Generation Agent | `/admin/workflow/reports/*`; tools `get_admin_report_data`, `prepare_admin_report` | Five report types; summary sentence built from the same metrics | read-only (generation is audited) | None | Implemented (fixed P04-N17) |

Details and evidence: `PHASE_04_AI_AGENT_VERIFICATION_MATRIX.md`.

## 3. Not implemented or unsupported (reported, not invented)

**Support:**
- No user reply or reopen of support tickets.
- No support ticket screen in the mobile app.
- No ticket assignment UI beyond "assigned to the replying admin".

**Doctor lifecycle:**
- No in-app appeal or re-application for rejected doctors (P3-B6, owner decision).
- No separate "revoke approval" action: suspension (account status) is the supported revocation and takes effect immediately (A-03g).

**Integrations:**
- No external registry check of SLMC registration numbers.
- No refund webhook handling (`charge.refunded` / `refund.updated`).
- No Stripe call from monitoring. This is deliberate: monitoring triggers no paid or external operation.
- No email, SMS or push delivery; providers are not configured in UAT.

**Roles and reports:**
- No platform fee or doctor payout model, so platform revenue and doctor earnings are reported as not calculated.
- No "weekly booking" report (removed from the UI).
- No admin roles beyond ADMIN (support agent, auditor and clinical safety officer are proposals in the access matrix).
