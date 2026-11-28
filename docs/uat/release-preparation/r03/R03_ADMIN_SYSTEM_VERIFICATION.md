# R03 — Admin System Verification

For: the project owner and reviewers. 2026-11-28. Real admin web app (Vite dev server `127.0.0.1:5174`) against the UAT backend, headless Chrome through `playwright-core`, script `browser_admin_r03.mjs`, results `evidence/r03_browser_admin.json`. Requests to any other host are aborted: **0 attempted**.

## Browser results (13 pages + role check)

For each page the script recorded the heading, page errors, error-boundary text, and whether a storage path, token, database URL or key prefix was visible.

| ID | Page | Heading seen | Result |
|---|---|---|---|
| b01 | Dashboard | Platform Command Center | PASS |
| b02 | Doctor management | Doctors Directory: Dr. UAT Neuro row with the real picture (32×32, blob from the admin session) | PASS |
| b03 | Doctor verification | Doctor Verification Management (3 fallback avatars) | PASS |
| b04 | Appointment monitoring | Appointment Monitoring | PASS |
| b05 | Payment monitoring | Payment & Financial Monitoring | PASS |
| b06 | Refund review | Refund Review | PASS |
| b07 | Reconciliation | Payment Reconciliation | PASS |
| b08 | Fraud monitoring | Platform Security & Health Command Center | PASS |
| b09 | Support tickets | Customer Support & Ticketing | PASS |
| b10 | System and notification monitoring | Platform Security & Health Command Center | PASS |
| b11 | Audit logs | Administrative Audit Trail | PASS |
| b12 | Analytics | Platform Analytics & Reporting | PASS |
| b13 | Reports | Operational & Audit Reports | PASS |
| b14 | Patient account at the admin login | Stays on `/login`; no doctor table reachable | PASS |

All 13 pages: 0 page errors, no error boundary, no storage path, token, database URL or key prefix in the page.

**Picture privacy:** the only picture the admin app requested was the doctor's (`6b05c3fc…`). The patient's picture was never requested, and the API refuses it to admins (404, picture probe).

## Restricted actions

| Check | Evidence | Result |
|---|---|---|
| Fraud signals cause no account, booking, payment or refund action | A05 probe re-run F14–F15 (account ACTIVE, payments/refunds/sessions/bookings unchanged); new 231-account sweep test | PASS |
| Support replies only by explicit admin send | A05 probe C06–C15b (template draft, edited text stored once, duplicate send idempotent) | PASS |
| Refund approval human-only, idempotent | Automated (Phase 04/05 suites: 4 concurrent approvals → 1 refund); R03 safety S06 (chat refuses refund approval, 0 refunds created) | PASS |
| Admin cannot read clinical records or patient pictures | A04 probe `adminRead` 403; picture probe admin → patient 404 | PASS |
| Admin endpoints refuse patients and doctors | R03 probe `SEC`: 403 / 403 | PASS |

## Limitations

- Browser checks are page-level (load, content, privacy) plus the earlier phases' interaction tests (Phase 04 browser 14/14, A03 refund and reconciliation, A05 fraud and support flows). R03 did not repeat every button flow in the browser.
- Admin web dependency advisories: see `R03_SECURITY_VERIFICATION_REPORT.md` (R03-O5).
