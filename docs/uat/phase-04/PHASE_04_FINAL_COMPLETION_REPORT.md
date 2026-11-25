# Phase 04 — Final Completion Report: Admin System, Financial Integrity, Monitoring and Admin AI

For: the project owner, reviewers and the Phase 05 team. Branch `fix/phase-04-admin-system-stabilization`, created from Phase 03 `2078f11`. 2026-11-26.

## 1. Executive summary

**Objective.** Verify and fix the complete admin system and admin AI components 22–30, against the local UAT backend and isolated databases only. Then close B15, P3-B2 and P3-B3, investigate the Phase 03 database incident (read-only plan only), and report truthfully.

### Work completed
- **Database safety preflight:**
  - Found and fixed a bypass in the Phase 03 test guard (P04-N01).
  - Guarded the admin bootstrap script.
  - Verified every execution path printed a local, isolated target before running.
- **Inventory:** of the admin system: 23 features, every admin endpoint, the 9 AI components, and the not-implemented items.
- **Defects:** 23 new defects (P04-N01–N23) reproduced, fixed and verified. Historical B15, P3-B2 and P3-B3 closed.
- **Live API UAT:** **90/90**, including:
  - real Stripe **test-mode** refunds and 4-way concurrent approval;
  - reconciliation of **54** test PaymentIntents with Stripe: **0 mismatches**;
  - dashboard and report figures recomputed independently from MongoDB.
- **Real browser UAT** (local Chrome, admin web against UAT): **13/13** after one fix found by it (P04-N23).
- **Suites:**

  | Suite | Result |
  |---|---|
  | Backend | 615 passed (565 + 26 guard + 24 Phase 04) |
  | Admin web | 37 tests; typecheck, lint and production build clean |
  | Flutter | 304 passed; analyze clean (no mobile code changed) |

- **Regression:** Phase 01–03 live suites re-run with no behavioural differences (details in §9).
- **Database incident review:** written, with a read-only owner procedure. The impact analysis found **two risks not recorded in Phase 03**:
  - a lifespan worker run against `mediconnect`, with possible SMTP emails;
  - `mediconnect_phase*_test` databases created and dropped on the cluster.

### Most important findings
- **Money was wrong everywhere it was summarised (P04-N05).**
  - Refunds were subtracted twice and partial refunds ignored.
  - A non-existent "10% platform fee" was shown as revenue.
  - The payment success rate was 100% with no payments.
  - Every payment was labelled test mode (P04-N04).
- **Monitoring invented health.**
  - Unauthenticated heartbeat endpoint (P04-N13).
  - Missing worker shown as active; Stripe "healthy" because a key existed (P04-N14).
  - Push counted as delivered with FCM off (P04-N15).
  - Failed-payment checks that never matched (P04-N12/N16).
  - Security events and fraud assessments failing after the first insert (P04-N20).
- **Unsafe financial advice and actions.**
  - Reconciliation told admins to "confirm" cancelled paid bookings (P04-N11).
  - A refund rejection could overwrite a concurrent approval (P04-N09).
  - A double click sent two approve requests (P04-N23).
- **Missing accountability.** No audit for doctor approval, rejection, suspension or report exports (P04-N08/N19). Admins could activate PENDING accounts, skipping verification.
- **P3-B4 corrected.** Admins **cannot** read patient clinical records, notes, measurements or prescriptions (verified by content). Two narrower items remain owner decisions.

**Completion status.** All feasible Phase 04 engineering is done. What remains blocked needs an external provider, owner access or a decision (§12).

**Phase 05 readiness.** **Yes.** P4-B1 (owner database inspection) is urgent, but it does not block Phase 05 engineering.

## 2. Database safety incident (P3-B1 → P4-B1)

| Item | Status |
|---|---|
| Known facts | 2026-11-25, about 20:08–20:30 Asia/Colombo. The first Phase 03 `pytest` run had no database variables, so `backend/.env` (remote Atlas, database `mediconnect`) applied. Whether it connected is unknown |
| Investigation | **Not performed**: no owner authorization; remote access not attempted. A read-only procedure (`mongosh` queries, Atlas access history, provider logs), an assessment checklist and a backup-first remediation plan are in `PHASE_04_DATABASE_INCIDENT_REVIEW.md` |
| New evidence from the source of the tests that ran | • **Fixture patterns:** emails, `doctorId` prefixes and PaymentIntent prefixes are listed.<br>• **Deletions:** fixture IDs plus 4 `doctorId` regex prefixes; no collection-wide delete.<br>• **Worker run:** `test_ai_care_assistant_unified.py` (4th file) runs the app lifespan, so the **background worker** (reminders, hold release, confirmation outbox over the **`.env` SMTP**) could have run against `mediconnect`.<br>• **Other databases:** three test modules create and drop `mediconnect_phase{2,3,4}_test` on the configured cluster.<br>• **AI calls:** Gemini and OpenAI keys were available |
| Guard verification | 26 guard tests (P04-N01). Seeds refuse remote targets (verified). `create_admin.py` refuses remote without `--allow-remote`. Redacted targets of every Phase 04 run are listed in the security report §1 |
| Remaining owner actions | **P4-B1** (urgent): run §4 of the review, fill the §5 checklist, remediate only with the §6 plan. **P4-B2**: rotate SMTP, Gemini and OpenAI credentials, and replace the weak development `JWT_SECRET` in `backend/.env` (11 characters, a common word) |

**The incident is not resolved.**

## 3. Bug statistics

| Measure | Count |
|---|---|
| Historical defects and blockers reviewed (P3-B1–B12, B1–B17, P03-N01–N24) | 53 |
| New defects (P04-N01–N23) | 23 |
| Reproduced before the fix (failing test, live UAT or browser) | 23 |
| Fixed | 23 |
| Verified after the fix | 23 |
| Remaining open defects | 0 |
| Historical blockers closed | 3 (B15, P3-B2, P3-B3) |
| Blocked verification | 1 (A-17d: remote database inspection), plus carried external blockers (B3, B4, B5, B13) |
| Test-maintenance fixes (not product defects) | 3 date-dependent backend tests (one found only in CI) |
| Observations for Phase 05 (not defects) | P4-O1–O9 |

## 4. Bug table

| Bug ID | Component | Severity | Description | Root cause | Fix | Evidence | Status |
|---|---|---|---|---|---|---|---|
| P04-N01 | Test DB guard | High | Look-alike or multi-host URIs passed the guard | Prefix match | Host parsing (`db_safety.py`) | 26 guard tests | Fixed |
| P04-N02 | `create_admin.py` | Medium | Silent write to the `.env` target | No check | Redacted target; `--allow-remote` | Code review | Fixed |
| P04-N03 | Admin appointments (P3-B2) | High | Null fee crashed the page; API invented 0.00 and a specialty | `toLocaleString` on null; `or 0.0` | Null-safe display; fee null when unknown | before/after; A-05c | Fixed |
| P04-N04 | Admin payments | High | Always "test mode"; date filters ignored | `or True`; unused params | Real mode; Colombo dates; refunds shown | `test_n04`; A-07a | Fixed |
| P04-N05 | Financial figures | Critical | Refunds counted twice; partial refunds ignored; invented 10% fee; 100% success with no data; per-city counts always 0 | Four separate calculations | `financial_metrics.py` | `test_n05`; A-02c, A-06e, A-13b | Fixed |
| P04-N06 | Date ranges | High | UTC days; end day excluded; bad dates defaulted | UTC midnights | Asia/Colombo inclusive days; 400 | `test_n06`; A-06d | Fixed |
| P04-N07 | Doctor counts | Medium | Pending count missed `PENDING_ADMIN_APPROVAL`; suspended counted as verified | Single status | All pending statuses; active/suspended split | `test_n07`; A-02a | Fixed |
| P04-N08 | Approval and status changes | High | No audit; approval without registration number; PENDING could be activated; refresh tokens kept | Missing rules | Audit, transitions, revocation | `test_n08` ×2; A-03, A-04d | Fixed |
| P04-N09 | Refund service | High | Rejection could overwrite an approval; 500 on bad IDs; no patient notice | Unconditional update | Conditional update, 404, notifications | `test_n09` ×2; A-10e | Fixed |
| P04-N10 | Refund source and UI (B15, P3-B3) | High | No source; no retry, error state or validation | Missing field; old UI | `source` + rebuilt page | `test_n10` ×2; A-10a–j; A-16f | Fixed |
| P04-N11 | Reconciliation | High | "Confirm booking immediately" advice; no amount/currency check | One rule | Classified rules; new checks | `test_n11`; A-07e | Fixed |
| P04-N12 | Fraud | High | Failed-payment rule never fired; admin events counted; bad decisions accepted | Case mismatch | Fixed query; exclusions; 422; audit | `test_n12`; A-08 | Fixed |
| P04-N13 | Heartbeat endpoint | High | No authentication | Missing dependency | `require_admin` | `test_n13_n14`; A-11e | Fixed |
| P04-N14 | Platform monitoring | High | Invented healthy states and job counts | Optimistic defaults | Truthful status vocabulary | `test_n13_n14`; A-11 | Fixed |
| P04-N15 | Notification monitoring | High | Push counted delivered; retries went to an unprocessed state | Wrong sources | Real delivery records; correct retries | `test_n15`; A-12 | Fixed |
| P04-N16 | Monitoring assistant | Medium | "Operating normally" always; AI "healthy" | Case mismatch; defaults | Real counts; truthful states | `test_n16`; A-15e | Fixed |
| P04-N17 | Reports and CSV | High | Unknown type → refund report; zeros blank; incomplete escaping; requested amounts used as refunded | Default branch; falsy check | Literal types; safe CSV; real amounts | `test_n17`; A-13 | Fixed |
| P04-N18 | Support | Medium | Could link another patient's booking; no reply notice; false promise | No ownership check | Ownership check; notification; wording | `test_n18`; A-09 | Fixed |
| P04-N19 | Report audit | Medium | Exports not audited | No audit call | Two audit actions | A-13d, A-14d | Fixed |
| P04-N20 | Event inserts | High | Second insert onward failed (`_id: null`) | `model_dump(by_alias)` | `document_for_insert` | `test_n20` | Fixed |
| P04-N21 | Admin web labels | Medium | "Real-time", "Revenue", "Verified", fake 30 days, "Production API" | Static text | Truthful labels | A-16a1; screenshots | Fixed |
| P04-N22 | Fraud re-evaluation | Medium | Stale rules and explanation returned | Partial patch of the returned object | Return the stored document | UAT run 3; `test_n22` | Fixed |
| P04-N23 | Admin confirmations | Medium | Double click → two approve requests | Disable applied after render | Synchronous guard | browser run 1 → A-16f | Fixed |

Full details (reproduction, expected/actual, changed files, limitations): `PHASE_04_BUG_FIX_REPORT.md`.

## 5. Test verification matrix

Generated from the evidence by `build_matrix.py`. 113 rows:

| Status | Count |
|---|---|
| PASS | 110 |
| PARTIAL | 1 (X-08) |
| BLOCKED | 1 (A-17d) |
| NOT APPLICABLE | 1 (A-08b) |
| FAIL | 0 |

| Test ID | Area / Agent | Scenario | Expected | Actual | Method | Status | Evidence |
|---|---|---|---|---|---|---|---|
| A-01a | Authentication / Platform (auth) | Admin login | 200 with tokens | {"http": 200, "access": true, "refresh": true} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-01a |
| A-01b | Authentication / Platform (auth) | Invalid credentials | 401, no token | {"http": 401} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-01b |
| A-01c | Authentication / Platform (auth) | Expired, forged and missing admin tokens | 401 for all | {"expired": 401, "forged": 401, "none": 401} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-01c |
| A-01d | Authentication / Platform (auth) | Patient access to admin endpoints | 403 on every admin endpoint | {"/admin/users": 403, "/admin/doctors/applications": 403, "/admin/appointments": 403, "/admin/payments": 403, "/admin/analytics/overview": 403, "/admin/workflow/refunds": 403, "/admin/workflow/audit-logs": 403, "/security/monitoring/platform": 403, "/security/… | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-01d |
| A-01e | Authentication / Platform (auth) | Doctor access to admin endpoints | 403 on every admin endpoint | {"/admin/users": 403, "/admin/doctors/applications": 403, "/admin/appointments": 403, "/admin/payments": 403, "/admin/analytics/overview": 403, "/admin/workflow/refunds": 403, "/admin/workflow/audit-logs": 403, "/security/monitoring/platform": 403, "/security/… | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-01e |
| A-01f | Authentication / Platform (auth) | Logout invalidates the refresh token | logout 200; refresh with the old token 401 | {"logout": 200, "refreshAfterLogout": 401} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-01f |
| A-01g | Authentication / Platform (auth) | Admin access to the same endpoints | 200 on every admin endpoint | {"/admin/users": 200, "/admin/doctors/applications": 200, "/admin/appointments": 200, "/admin/payments": 200, "/admin/analytics/overview": 200, "/admin/workflow/refunds": 200, "/admin/workflow/audit-logs": 200, "/security/monitoring/platform": 200, "/security/… | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-01g |
| A-01h | Authentication / Platform (auth) | Role claim manipulation: validly signed patient token claiming role ADMIN | 403 (role read from the account, not the token) | {"http": 403} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-01h |
| A-02a | Dashboard / 23 Platform Analytics | Dashboard counts equal MongoDB counts | every count matches an independent query | {"api": {"totalPatients": 27, "totalDoctors": 19, "verifiedDoctors": 13, "pendingDoctorApprovals": 5, "rejectedDoctorApplications": 1, "totalAppointments": 79, "confirmedAppointments": 17, "completedAppointments": 7, "cancelledAppointments": 55}, "db": {"total… | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-02a |
| A-02b | Dashboard / 23 Platform Analytics | Empty range shows no invented figures | zero counts and success rate null | {"succeeded": 0, "paymentSuccessRate": null, "revenue": [{"currency": "lkr", "grossAmount": 0.0, "refundedAmount": 0.0, "netAmount": 0.0, "paymentCount": 0, "partiallyRefundedCount": 0, "fullyRefundedCount": 0, "pendingRefundAmount": 15500.0, "pendingRefundCou… | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-02b |
| A-02c | Dashboard / 23 Platform Analytics | Dashboard money equals an independent recomputation (gross, refunded incl. partial, net) | identical per currency; platform revenue null | {"api": {"LKR": {"gross": 89500.0, "refunded": 20800.0, "net": 68700.0}}, "db": {"LKR": {"gross": 89500.0, "refunded": 20800.0, "net": 68700.0}}, "platformRevenue": null} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-02c |
| A-02d | Dashboard / 23 Platform Analytics | API error handling for invalid input | 400 with a readable message | {"http": 400, "detail": "Invalid startDate value. Expected a valid YYYY-MM-DD calendar date."} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-02d |
| A-03a | Doctor verification / 22 Doctor Verification | Pending applications listed | P04 applicant, reject and no-registration applications listed | ["Dr. P04 Applicant", "Dr. P04 No Registration", "Dr. P04 Reject"] | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-03a |
| A-03b | Doctor verification / 22 Doctor Verification | Application details | registration number, specialty, qualifications, clinic, experience; no password hash | {"medicalRegistrationNumber": "UAT-P04-APPLICANT", "specialty": "Dermatology", "qualifications": "MBBS (synthetic UAT profile)", "hospitalOrClinic": "UAT P04 Clinic", "experienceYears": 6, "emailVerified": true} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-03b |
| A-03c | Doctor verification / 22 Doctor Verification | Verification documents | admin receives the stored file; patient 403; path traversal refused | {"bytes": 186, "type": "application/pdf", "synthetic": true, "patient": 403, "traversal": 404} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-03c |
| A-03d | Doctor verification / 22 Doctor Verification | Registration number required; checklist is not a registry check | missing number flagged and approval 400; registrationOfficiallyVerified false; human decision required | {"applicantRecommended": "APPROVE", "officiallyVerified": false, "humanDecisionRequired": true, "noRegFlags": ["Missing medical registration number."], "noRegApprove": 400, "detail": "Cannot approve an application without a medical registration number."} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-03d |
| A-03e | Doctor verification / 22 Doctor Verification | Doctor approval by an administrator | approve 200 once (second 400); audit actor/target/state; doctor notified; account ACTIVE | {"approve": 200, "again": 400, "audit": {"actorId": "6b05c3fc88a1403facad0202", "previousState": "PENDING_ADMIN_APPROVAL", "newState": "APPROVED"}, "notified": true, "account": "ACTIVE"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-03e |
| A-03f | Doctor verification / 22 Doctor Verification | Doctor rejection | reject 200 with reason; audited; rejected doctor login 403 (no appeal flow: P3-B6) | {"reject": 200, "audited": 4, "login": 403, "detail": "Your doctor registration application was not approved. Please contact MediConnect support for further information."} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-03f |
| A-03g | Doctor verification / 22 Doctor Verification | Suspension revokes clinical access immediately | records 200 before; suspend 200; same token 403 on records and appointments; login refused; reinstate restores access | {"before": 200, "suspend": 200, "recordsAfter": 401, "appointmentsAfter": 401, "login": 403, "reinstate": 200, "recordsAfterReinstate": 200} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-03g |
| A-03h | Doctor verification / 22 Doctor Verification | Approved doctor visible in patient search | Dr. P04 Applicant listed | ["Dr. P04 Applicant"] | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-03h |
| A-03i | Doctor verification / 22 Doctor Verification | Pending doctor restrictions | not in patient search; cannot be booked | {"inSearch": false, "bookHttp": 404} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-03i |
| A-04a | User management / Platform (admin) | Patient list with search | only P04 patients; total matches | {"total": 2, "emails": ["uat.p04.patienta@uat.mediconnect.lk", "uat.p04.patientb@uat.mediconnect.lk"]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-04a |
| A-04b | User management / Platform (admin) | Doctor directory | P04 doctors listed with verification and account status | [["Dr. P04 Applicant", "APPROVED", "ACTIVE"], ["Dr. P04 No Registration", "PENDING_ADMIN_APPROVAL", "PENDING"], ["Dr. P04 Reject", "REJECTED", "PENDING"], ["Dr. P04 Revoke", "APPROVED", "ACTIVE"]] | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-04b |
| A-04c | User management / Platform (admin) | Pagination and status filter | page 2 has at most 5 rows; SUSPENDED filter returns only suspended accounts | {"page2": 5, "suspended": ["SUSPENDED"]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-04c |
| A-04d | User management / Platform (admin) | Account status management | PENDING cannot be activated by admin (409); self-suspension 400; patient cannot change status (403); changes audited | {"pendingToActive": 409, "self": 400, "byPatient": 403, "audits": 8} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-04d |
| A-04e | User management / Platform (admin) | Sensitive data not exposed | no password hashes, refresh tokens or medical fields in admin user/doctor lists | {"passwordHash": false, "tokenHash": false, "refreshToken": false, "allergies": false, "diagnosis": false} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-04e |
| A-05a | Appointments / Platform (admin) | Appointment list | total equals MongoDB count | {"api": 79, "db": 79} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-05a |
| A-05b | Appointments / Platform (admin) | Appointment details | detail modal shows fee (or "Not available"), in-person, cancellation and refund state | Browser: detail fee "Not available" for the null-fee record; unit test checks the modal | Browser + React test | **PASS** | browser-admin-uat.json#A-05c-ui; phase04Admin.test.tsx |
| A-05c | Appointments / Platform (admin) | Null-fee historical appointment (P3-B2) | consultationFee null (not 0.0); API 200 | {"fee": null, "type": "IN_PERSON"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-05c |
| A-05d | Appointments / Platform (admin) | In-person semantics | every item IN_PERSON; no video fields | {"types": ["IN_PERSON"], "videoFields": []} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-05d |
| A-05e | Appointments / Platform (admin) | Status and date filtering | same count as MongoDB | {"api": 3, "db": 3} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-05e |
| A-05f | Appointments / Platform (admin) | Payment bypass prevention | no admin route confirms an unpaid booking; the status route is doctor-only and payment-checked | {"adminPut": 403} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-05f |
| A-06a | Platform analytics / 23 Platform Analytics | User/doctor analytics | approved/pending/rejected equal MongoDB; no invented specialty | {"api": {"approvedDoctors": 14, "pendingDoctors": 3, "rejectedDoctors": 2}, "db": {"approvedDoctors": 13}} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-06a |
| A-06b | Platform analytics / 23 Platform Analytics | Appointment analytics | total equals MongoDB for the same appointment dates | {"api": 16, "db": 16} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-06b |
| A-06c | Platform analytics / 23 Platform Analytics | Financial analytics for the last 30 days | counts equal MongoDB (Asia/Colombo days); success rate from real attempts; no platform revenue | {"api": {"succeeded": 36, "failed": 3, "refunded": 9, "successRate": 93.8, "platformRevenue": null}, "db": {"succeeded": 36, "failed": 3, "refunded": 9}} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-06c |
| A-06d | Platform analytics / 23 Platform Analytics | Date boundaries use Asia/Colombo days | today (Colombo) count equals MongoDB with +05:30 bounds | {"api": 9, "db": 9, "day": "2026-11-26"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-06d |
| A-06e | Platform analytics / 23 Platform Analytics | Refund-aware totals | net = gross - refunded per currency; refunded includes the Stripe test refund above | {"LKR": [97200.0, 22800.0, 74400.0]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-06e |
| A-07a | Payments / 24 Payment Monitoring | Successful payment retrieval | admin list shows the SUCCEEDED/REFUNDED payment with booking reference and test mode | {"row": {"appointmentId": "6b074f365fccdb84c84c32a5", "status": "SUCCEEDED", "isTestMode": true}} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-07a |
| A-07b | Payments / 24 Payment Monitoring | Declined payment (Stripe test card) is not recorded as paid | Stripe requires_payment_method; local payment not SUCCEEDED; booking not CONFIRMED | {"stripe": "requires_payment_method", "local": "FAILED", "appointment": ["PENDING", "PENDING"]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-07b |
| A-07c | Payments / 24 Payment Monitoring | Stripe test-mode reconciliation of every real test PaymentIntent | status, amount, currency and refunded amount agree; livemode false | {"checked": 54, "mismatches": [], "mismatchCount": 0} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-07c |
| A-07d | Payments / 24 Payment Monitoring | Duplicate PaymentIntent reference | database unique index rejects a second record for the same PI | {"insert": "DuplicateKeyError"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-07d |
| A-07e | Payments / 24 Payment Monitoring | Reconciliation: amount/currency checks and no confirm-the-booking advice | no recommendation to confirm a booking; doctor-cancelled refunds classified as awaiting decision | {"byType": {"CANCELLED_AWAITING_REFUND_DECISION": 11, "CANCELLED_PAID_WITHOUT_REFUND_REQUEST": 1, "MISSING_PAYMENT_EVIDENCE": 1, "DELAYED_PENDING": 3}, "unsafeAdvice": 0} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-07e |
| A-07f | Payments / 24 Payment Monitoring | Unauthorized payment and booking mutation | patients/doctors cannot reconcile or approve refunds (403); admin cannot set a booking status (403) | {"patientReconcile": 403, "doctorReconcile": 403, "patientApproveRefund": 403, "doctorApproveRefund": 403, "adminStatusChange": 403} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-07f |
| A-08a | Fraud monitoring / 25 Fraud Detection | Supported risk signals fire only on real evidence | triggered rules equal the rules whose thresholds are met in MongoDB (UAT runs create cancellations for patient A); no account action | {"fired": ["EXCESSIVE_BOOKING_RATE", "EXCESSIVE_REFUND_REQUESTS", "RAPID_CANCELLATION_PATTERN"], "evidenceMet": ["EXCESSIVE_BOOKING_RATE", "EXCESSIVE_REFUND_REQUESTS", "RAPID_CANCELLATION_PATTERN"], "account": "ACTIVE"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-08a |
| A-08b | Fraud monitoring / 25 Fraud Detection | Duplicate payment reference signal | not reachable through the application: the unique PaymentIntent index blocks the data (A-07d) | {"uniqueIndex": "idx_payments_stripe_pi_unique"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **NOT APPLICABLE** | admin-system-uat.json#A-08b |
| A-08c | Fraud monitoring / 25 Fraud Detection | Repeated failed payments signal | MULTIPLE_FAILED_PAYMENTS triggered from 3 FAILED payments; explanation says it is not proof; account untouched | {"http": 200, "rules": ["MULTIPLE_FAILED_PAYMENTS", "EXCESSIVE_BOOKING_RATE", "RAPID_CANCELLATION_PATTERN", "EXCESSIVE_REFUND_REQUESTS"], "explanation": "Rule weight total 100.0/100 (CRITICAL). Triggered 4 deterministic rule(s): MULTIPLE_FAILED_PAYMENTS, EXCES… | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-08c |
| A-08d | Fraud monitoring / 25 Fraud Detection | False-positive handling | admin dismisses; decision audited; no account action | {"http": 200, "reviewStatus": "DISMISSED", "audited": 1} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-08d |
| A-09a | Customer support / 26 Customer Support | Support ticket creation and retrieval | patient creates (201); admin lists it; linking another patient's booking 403 | {"create": 201, "adminSees": true, "otherLink": 403} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-09a |
| A-09b | Customer support / 26 Customer Support | Ticket response | reply 200; message stored; requester notified in-app | {"reply": 200, "notified": 5} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-09b |
| A-09c | Customer support / 26 Customer Support | Ticket resolution | status resolved; audited | {"status": "resolved", "audit": 2} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-09c |
| A-09d | Customer support / 26 Customer Support | User isolation | another patient gets 403 and does not see it in their list | {"otherPatient": 403, "otherList": false} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-09d |
| A-09e | Customer support / 26 Customer Support | Draft review (template, not sent) | draft returned to the admin only; no message added; no refund promised | {"draftType": "template", "messages": 1, "promisesRefund": false, "excerpt": "Dear P04 Patient A,\n\nThank you for reaching out regarding your refund request for ticket #TCK-40016048.\n\nOur administrative team has receive"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-09e |
| A-10a | Refunds / 27 Refund Management | Patient cancellation refund request | source patient; existing policy (more than 24 h ahead: 100%) | {"cancel": 200, "source": "patient", "rule": "Cancelled with more than 24 hours notice; 100% full refund eligible.", "eligible": 2000.0} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10a |
| A-10b | Refunds / 27 Refund Management | Doctor cancellation opens a refund request in the admin queue (P3-B3) | source doctor; 100% policy; visible with source filter; status requested | {"cancel": 200, "source": "doctor", "eligible": 2000.0, "paid": 2000.0, "inQueue": true} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10b |
| A-10c | Refunds / 27 Refund Management | Leave-related refund request | leave cancels the paid booking; refund request source leave, 100% | {"leave": 201, "appointment": "CANCELLED", "source": "leave", "eligible": 1800.0, "paid": 1800.0} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10c |
| A-10d | Refunds / 27 Refund Management | Admin approval | approval moved money only after the admin action; audit REFUND_APPROVAL recorded | {"audit": 1} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10d |
| A-10e | Refunds / 27 Refund Management | Admin rejection | reject 200; second reject 409; approval after rejection 409; no Stripe refund; patient notified | {"reject": 200, "again": 409, "approveAfter": 409, "stripeRefunds": 0, "notified": 1} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10e |
| A-10f | Refunds / 27 Refund Management | Stripe test-mode refund | Stripe refund succeeded on a livemode=false PaymentIntent; amount = captured amount | {"stripeStatus": "succeeded", "piLivemode": false, "amountMinor": 200000, "captured": 2000.0} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10f |
| A-10g | Refunds / 27 Refund Management | Duplicate refund prevention | re-approval 400; a second request for the same appointment 400; still one Stripe refund | {"reapprove": 400, "secondRequest": 400, "stripeRefunds": 1} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10g |
| A-10h | Refunds / 27 Refund Management | Concurrent admin approvals (4 at once) | exactly one 200; one Stripe test refund; others 400/409 | {"codes": [200, 400, 400, 400], "stripeRefunds": 1, "status": "succeeded"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10h |
| A-10i | Refunds / 27 Refund Management | External refund failure (Stripe rejects the request) | 502; request failed with the error type; payment not marked refunded; retry fails the same way, nothing invented | {"approve": 502, "detail": "Stripe refund processing failed. The request can be retried.", "status": "failed", "failureReason": "InvalidRequestError", "payment": ["SUCCEEDED", null], "retry": 502} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10i |
| A-10j0 | Refunds / 27 Refund Management | Refund cannot exceed the captured amount | 400; nothing sent to Stripe | {"http": 400, "detail": "The refund cannot exceed the captured amount still refundable.", "stripeRefunds": 0} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10j0 |
| A-10j | Refunds / 27 Refund Management | Cross-role financial reconciliation after refund | Stripe, payment, appointment, patient view and notification agree | {"payment": ["REFUNDED", 2000.0], "appointmentPayment": "REFUNDED", "patientView": {"paymentStatus": "REFUNDED", "refundStatus": "succeeded", "refundedAmount": 2000.0}, "notified": true} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-10j |
| A-11a | System monitoring / 28 System Monitoring | Backend health | readiness ready; uptime reported as process uptime only | {"ready": "ready", "uptimeSeconds": 370.9} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-11a |
| A-11b | System monitoring / 28 System Monitoring | Database health | MongoDB healthy with measured latency | {"MongoDB": "healthy"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-11b |
| A-11c | System monitoring / 28 System Monitoring | Worker status from real heartbeats | reminder_care_worker active with a recent heartbeat recorded by the worker itself | {"reminder_care_worker": ["active", "2026-11-25T21:12:56.678000Z"]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-11c |
| A-11d | System monitoring / 28 System Monitoring | Disabled/unconfigured providers reported truthfully | Stripe configured-not-verified; email/SMS/push not configured; AI disabled | {"MongoDB": "healthy", "Stripe Payments": "configured_not_verified", "Email (SMTP)": "not_configured", "SMS (Twilio)": "not_configured", "Push (FCM)": "not_configured", "AI Providers": "disabled"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-11d |
| A-11e | System monitoring / 28 System Monitoring | Heartbeat spoofing / failed-job monitoring | anonymous heartbeat 401; worker errors recorded as status error (unit-tested) | {"anonymous": 401} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-11e |
| A-12a | Notification monitoring / 29 Notification Monitoring | In-app delivery counted from stored records | in-app delivered > 0; equals stored outbox/reminder records | {"inApp": {"delivered": 15, "pending": 0, "providerStatus": "in_app_store"}, "inAppStored": 289} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-12a |
| A-12b | Notification monitoring / 29 Notification Monitoring | Failed delivery visible | email outbox failures (provider_not_configured) counted as failed with a note | {"emailFailed": 3, "notes": ["email: provider not configured; 3 failed and 12 skipped. Nothing was sent on this channel.", "sms: provider not configured; 0 failed and 15 skipped. Nothing was sent on this channel.", "push: provider not configured; 0 failed and … | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-12b |
| A-12c | Notification monitoring / 29 Notification Monitoring | Disabled channels reported, nothing claimed as sent | push/email/SMS provider not_configured and 0 delivered | {"push": ["not_configured", 0, 0, 12], "email": ["not_configured", 0, 3, 12], "sms": ["not_configured", 0, 0, 15]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-12c |
| A-12d | Notification monitoring / 29 Notification Monitoring | Retry handling | permanent failures (provider not configured) are not re-queued | {"first": {"retriedCount": 0, "deadLetteredCount": 0, "cancelledObsoleteCount": 0, "notRetryableCount": 3}, "second": {"retriedCount": 0, "deadLetteredCount": 0, "cancelledObsoleteCount": 0, "notRetryableCount": 3}} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-12d |
| A-12e | Notification monitoring / 29 Notification Monitoring | Duplicate prevention | no idempotency key is stored twice | {"duplicates": 0} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-12e |
| A-13a | Reports / 30 Report Generation | Appointment report | total equals MongoDB for the same dates | {"report": 16, "db": 16} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-13a |
| A-13b | Reports / 30 Report Generation | Financial report reconciles with analytics | captured/refunded/net LKR equal the analytics figures; platform revenue null; no platform fee | {"report": {"capturedAmountLKR": 97200.0, "refundedAmountLKR": 22800.0, "netCollectedLKR": 74400.0, "platformRevenue": null}, "analytics": [97200.0, 22800.0, 74400.0]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-13b |
| A-13c | Reports / 30 Report Generation | Doctor verification report | counts equal MongoDB | {"report": {"approvedCount": 14, "rejectedCount": 2}, "db": [14, 2]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-13c |
| A-13d | Reports / 30 Report Generation | Export accuracy | metric rows and record header present; counts equal the generated report; export audited | {"header": ["ticketId", "category", "priority", "status", "subject", "createdAt"], "audit": 3} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-13d |
| A-13e | Reports / 30 Report Generation | Formula injection prevention | formula-like subjects exported with a leading quote; no cell starts with = + - @ tab CR | {"dangerousCells": [], "quoted": ["'=HYPERLINK(\"http://example.invalid\",\"x\")", "'=HYPERLINK(\"http://example.invalid\",\"x\")"]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-13e |
| A-14a | Privacy and audit / Platform (privacy) | Clinical data access inventory (P3-B4) | admin gets no patient clinical content from clinical routes (patientId ignored for non-doctors) | {"/clinical/records?patientId=6b074bbf2dc2c96d9c6ec87e": {"http": 200, "containsPatientRecord": false}, "/clinical/records/summary?patientId=6b074bbf2dc2c96d9c6ec87e": {"http": 200, "containsPatientRecord": false}, "/clinical/notes?patientId=6b074bbf2dc2c96d9c… | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-14a |
| A-14b | Privacy and audit / Platform (privacy) | Object-level authorization | admin appointment detail allowed (operational); other patient 403; unrelated doctor 403 | {"admin": 200, "otherPatient": 403, "unrelatedDoctor": 403} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-14b |
| A-14c | Privacy and audit / Platform (privacy) | Sensitive-data redaction | monitored payments mask patient names; no card data | {"cardFields": []} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-14c |
| A-14d | Privacy and audit / Platform (privacy) | Admin action audit | approvals, rejections, status changes, refunds, fraud reviews, report exports audited with actor/target/time/result | {"actionTypes": ["DOCTOR_VERIFICATION_DECISION", "FRAUD_REVIEW_DECISION", "REFUND_APPROVAL", "REFUND_EXECUTION", "REFUND_REJECTION", "REPORT_EXPORTED", "REPORT_GENERATED", "SUPPORT_RESPONSE_SENT", "SUPPORT_TICKET_RESOLVED", "USER_STATUS_CHANGE"], "sampleFields… | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-14d |
| A-14e | Privacy and audit / Platform (privacy) | Unauthorized audit modification | no write route exists (404/405); patients cannot read audit logs (403) | {"PUT": 404, "PATCH": 404, "DELETE": 404, "patientRead": 403} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-14e |
| A-15a | AI safety / Admin assistants | Admin AI role validation | patients and doctors 403 on admin assistants | {"patient": 403, "doctor": 403, "monitorPatient": 403} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-15a |
| A-15b | AI safety / Admin assistants | Answers use authorized tools only; no invented revenue | tool get_admin_dashboard_metrics; reply states gross/refunded/net and that platform revenue is not calculated | {"tool": "get_admin_dashboard_metrics", "reply": "LKR: gross collections 25,100.00, refunded 8,000.00, net collections 17,100.00 for 2026-11-26 to 2026-11-26 (Asia/Colombo). Gross collections are patient payments, not platform profit. No platform fee or doctor… | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-15b |
| A-15c | AI safety / Admin assistants | Prompt injection resistance | only a read-only tool runs; no refund or doctor state changes | {"tool": "get_pending_doctor_verifications", "refundsBefore": {"requested": 9, "succeeded": 7, "rejected": 3, "failed": 2}, "refundsAfter": {"requested": 9, "succeeded": 7, "rejected": 3, "failed": 2}, "pendingDoctorsUnchanged": true} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-15c |
| A-15d | AI safety / Admin assistants | Human confirmation requirement | no admin AI tool changes state; approvals happen only through explicit admin endpoints | {"assistantTools": "read-only registry (ADMIN_ROLES)", "refundsChangedByAssistant": false} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-15d |
| A-15e | AI safety / Admin assistants | AI provider failure / disabled handling | provider status reported as not configured, not healthy | {"reply": "AI Provider Status: NOT_CONFIGURED (Circuit Breaker: CLOSED).\n• Total Requests: 0\n• Average Latency: 0.0 ms\n• Fallback Activations: 0\nWhen no provider answers, "} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-15e |
| A-17a | Environment safety / Platform (safety) | Local UAT backend and isolated database | backend ready on 127.0.0.1:8001; database mediconnect_uat (local) | {"ready": "ready", "dbName": "mediconnect_uat", "mongoHost": "127.0.0.1"} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-17a |
| A-17c | Environment safety / Platform (safety) | Stripe test mode only | sk_test_ key; every Stripe object has livemode=false | {"keyMode": "test", "sampleLivemode": [false]} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#A-17c |
| X-03 | Cross-role / 24/27 | Patient books and pays -> doctor sees it -> admin sees the payment | CONFIRMED/PAID; admin row SUCCEEDED with the same PI, amount and test mode | {"appointment": ["CONFIRMED", "PAID"], "admin": {"status": "SUCCEEDED", "amount": 2000.0, "currency": "LKR", "isTestMode": true}, "pi": "pi_3Uf…VXrT", "doctorSees": true} | Live API (UAT 8001, MongoDB, Stripe test mode) | **PASS** | admin-system-uat.json#X-03 |
| A-05c-ui | Appointments / Platform (admin) | Null-fee appointment in the browser (P3-B2) | page renders; fee cell "Not available"; no LKR 0.00 | {"feeCells": ["Not available"], "pageErrors": 0} | Browser (Chrome) | **PASS** | browser-admin-uat.json#A-05c-ui; p3-b2-null-fee-before.txt |
| A-16a | Browser UI / Admin web | Navigate all 16 admin pages | no uncaught page error and no error boundary on any page | {"dashboard": {"errors": 0, "errorBoundary": 0}, "doctor-approvals": {"errors": 0, "errorBoundary": 0}, "reconciliation": {"errors": 0, "errorBoundary": 0}, "refunds": {"errors": 0, "errorBoundary": 0}, "support-tickets": {"errors": 0, "errorBoundary": 0}, "re… | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-16a |
| A-16a1 | Browser UI / Admin web | Dashboard in a real browser against the UAT backend | net collections, gross/refunded line, no "Revenue" or "Real-time" claims | {"hasNet": true, "hasGross": true, "revenueWord": false, "realtime": false} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-16a1 |
| A-16b | Browser UI / Admin web | Table search and filters (users) | only the two P04 patients | {"rows": 2, "sample": ["P04 Patient A", "P04 Patient B"]} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-16b |
| A-16c | Browser UI / Admin web | Responsive layout at 390 px | no page-level horizontal scroll (tables scroll inside their container) | {"dashboard": 0, "refunds": 0, "appointments": 0} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-16c |
| A-16d | Browser UI / Admin web | Confirmation before suspending an account | dialog shown; cancelled without change | {"dialog": "Suspend User Account\nAre you sure you want to change the status of P04 Patient A (uat.p04.patienta@uat.mediconnect.lk) t"} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-16d |
| A-16e | Browser UI / Admin web | Error state instead of a misleading empty list | "Failed to load refund requests" with retry; no "No refund requests" | {"emptyShown": 0} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-16e |
| A-16f | Browser UI / Admin web | Refund approval from the browser: validation, single submission, Stripe result shown | over-limit amount disabled; one approve request for repeated clicks; toast states Stripe result | {"leaveRows": 2, "source": true, "overLimitDisabled": true, "alert": "The refund cannot exceed the captured payment (LKR 1,800.00).", "approvePosts": 1} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-16f |
| A-11f | System monitoring / 28 System Monitoring | Monitoring page states | Stripe "configured, not verified"; providers "not configured"; AI "disabled"; no availability % | {"configuredNotVerified": true, "notConfigured": true, "disabled": true, "uptimePct": false} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-11-ui |
| A-13f | Reports / 30 Report Generation | Report types offered | implemented reports listed; no "Weekly Booking" (not implemented) | {"offered": ["Daily Appointment Operations", "Payments & Collections (gross, refunded, net)", "Doctor Verification & Credentialing Backlog", "Customer Support Ticket Resolution", "Refund Status & Cancellation Settlements"]} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-13-ui |
| A-01c2 | Authentication / Platform (auth) | Invalid/expired session in the browser | redirected to /login (expired=1) | {"url": "/login?expired=1"} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-01c-ui |
| A-01d2 | Authentication / Platform (auth) | Patient login to the admin app | not admitted to the dashboard | {"url": "/login", "message": "MediConnect Admin\n\nSecure clinical administration and operations console\n\nAccess denied: You must hold the ADMIN role to access this portal."} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-01d-ui |
| A-17e | Environment safety / Platform (safety) | Browser network stayed local | no request left 127.0.0.1:5174/8001 | {"blockedHosts": ["fonts.googleapis.com"]} | Browser (Chrome, admin web 5174 → UAT 8001) | **PASS** | browser-admin-uat.json#A-17b-ui |
| A-17b | Environment safety / Platform (safety) | Remote database refusal (tests, seeds, admin bootstrap) | localhost look-alikes, multi-host, +srv, non-_test/_uat names and live Stripe keys refused before connecting | 26 guard tests pass (subprocess runs of conftest refuse); seed against cluster0.example.net refused (exit 1); create_admin requires --allow-remote | Automated tests + live command | **PASS** | test_database_safety_guard.py; final report §2 |
| A-17d | Environment safety / Platform (safety) | Phase 03 database incident review | facts, impact analysis from test source, read-only procedure, checklist, remediation plan | Review written; remote inspection not performed (no owner authorization; permission system blocked the Phase 03 attempt) | Document review | **BLOCKED (owner action)** | PHASE_04_DATABASE_INCIDENT_REVIEW.md |
| X-01 | Cross-role / — | Doctor applies → admin reviews → approves → patient finds doctor | end-to-end consistency | A-03a/b/c/d/e/h all PASS | Live API + browser | **PASS** | admin-system-uat.json |
| X-02 | Cross-role / — | Admin suspends (revokes) a doctor → clinical access removed | end-to-end consistency | A-03g: records 200 → 401 with the same token; login 403; reinstate restores | Live API + browser | **PASS** | admin-system-uat.json |
| X-04 | Cross-role / — | Doctor cancels → refund request in admin queue | end-to-end consistency | A-10b: source doctor, 100%, visible with source filter | Live API + browser | **PASS** | admin-system-uat.json |
| X-05 | Cross-role / — | Admin approves refund → Stripe test refund → patient/doctor/admin figures update | end-to-end consistency | A-10f/h/j + A-02c/A-06e/A-13b (net figures include the refund) | Live API + browser | **PASS** | admin-system-uat.json |
| X-06 | Cross-role / — | Doctor completes consultations → admin analytics reflect completion | end-to-end consistency | A-02a: completed count = MongoDB after the Phase 03 workflow regression completed visits (D-11 PASS) | Live API + browser | **PASS** | admin-system-uat.json |
| X-07 | Cross-role / — | Worker delivers reminders → notification monitoring reflects delivery | end-to-end consistency | A-11c worker heartbeat active; A-12a in-app deliveries counted from care_reminder_events written by the worker | Live API + browser | **PASS** | admin-system-uat.json |
| X-08 | Cross-role / — | Patient creates support ticket → admin responds → user notified | end-to-end consistency | A-09a/b/c; doctor-created tickets not exercised; users cannot reply (not implemented) | Live API + browser | **PARTIAL** | admin-system-uat.json |

## 6. The nine admin AI components

All nine are **deterministic**: none calls an LLM. Every tool is read-only and restricted to `ADMIN_ROLES`, and every state change is an explicit, audited admin endpoint. Details: `PHASE_04_AI_AGENT_VERIFICATION_MATRIX.md`.

| # | Component | Actual functionality | Tested | Human approval | Known limitations | Evidence | Status |
|---|---|---|---|---|---|---|---|
| 22 | Doctor Verification Assistant | Checklist of fields and documents, format and plausibility checks | Live A-03a–i | Approve/reject by an admin only; `humanDecisionRequired`; registration never "officially verified" | No SLMC registry integration | A-03, `test_n08` | PASS |
| 23 | Platform Analytics Assistant | Keyword router + shared refund-aware figures | A-02, A-06, A-15b | n/a (read-only) | Keyword routing only | A-15b | PASS |
| 24 | Payment Monitoring Agent | Monitored payments; deterministic reconciliation | A-07a–f, Stripe check of 54 PaymentIntents | Refund/reconcile by an admin | No refund webhook (B3) | A-07c/e | PASS |
| 25 | Fraud Detection Agent | Six evaluated rules; weight sum; template explanation | A-08a–d | Review by an admin; no automatic account action | Slot-hoarding rule not implemented; login failures not recorded; shared-PaymentIntent rule unreachable (unique index) | A-08, `test_n12/n22` | PARTIAL |
| 26 | Customer Support Assistant | Keyword category/priority; fixed template drafts; 1990 emergency advisory | A-09a–e | Drafts never sent automatically | No user reply/reopen; no mobile UI; not generative | A-09 | PARTIAL |
| 27 | Refund Management Agent | Existing policy calculation; review summary | A-10a–j, A-16f | Every refund needs an admin approval; Stripe test mode | Pending refunds have no webhook follow-up | A-10 | PASS |
| 28 | System Monitoring Agent | Measured health; truthful provider states | A-11a–f | Incident actions by an admin | AI metrics reset on restart | A-11 | PASS |
| 29 | Notification Monitoring Agent | Delivery counts from outbox and reminder events | A-12a–e | Retries by an admin | External providers not configured (B4, B5) | A-12 | PASS |
| 30 | Report Generation Agent | Five report types; summary built from metrics; safe CSV | A-13a–f | n/a | No weekly report (removed from the UI) | A-13 | PASS |

**Admin AI safety (A-15).** Results:
- **Role checks:** patients and doctors get 403.
- **Prompt injection:** it changed nothing.
- **Invented figures:** none.
- **Disabled providers:** reported truthfully.

## 7. Financial integrity (Stripe test mode)

| Area | Result |
|---|---|
| **Payments** | • Dashboard equals the MongoDB recomputation (LKR gross 89,500 / refunded 20,800 / net 68,700 at run time).<br>• 30-day analytics counts equal MongoDB.<br>• Report equals analytics.<br>• **54 PaymentIntents reconciled with Stripe: 0 mismatches**, all `livemode=false`.<br>• A declined card is never recorded as paid |
| **Refunds** | • Patient (100% when cancelled more than 24 h ahead), doctor (100%) and leave (100%) requests carry their source.<br>• Over-capture refused.<br>• Rejection is final and notified.<br>• A real Stripe API failure is recorded as `failed` with nothing refunded.<br>• Lost-response retry returns the same refund (idempotency key) |
| **Duplicate prevention** | Re-approval 400; a second request 400; unique PaymentIntent index; one Stripe refund per request |
| **Concurrency** | 4 simultaneous live approvals → 1×200 and exactly 1 Stripe refund. An approve/reject race leaves the approval in place (unit test). A browser double click now sends 1 request |
| **Cross-role** | After the doctor-cancellation refund, the following agree: Stripe refund `succeeded`, payment REFUNDED (2,000), appointment REFUNDED, patient view `succeeded`, patient notification, admin figures |

Full report: `PHASE_04_FINANCIAL_INTEGRITY_REPORT.md`.

## 8. Admin security and privacy

| Area | Result |
|---|---|
| **Role authorization** | Every admin endpoint uses `require_admin`, with the role read from the account. A validly signed patient token claiming ADMIN gets 403. Patients and doctors get 403 on all 10 sampled admin endpoints |
| **Object-level authorization** | Tickets, appointment details and verification documents are checked. Path traversal refused. Another patient's booking cannot be linked to a ticket |
| **Sensitive data** | No password hashes, tokens or card data in admin responses. Patient names masked in the monitored payments list. Monitoring exposes no connection strings or hosts |
| **Clinical access (P3-B4)** | No admin access to patient records, notes, measurements or prescriptions (content-verified). Open owner decisions: care-plan content (P4-B4a), booking note (P4-B4b). See `PHASE_04_ADMIN_ACCESS_POLICY_MATRIX.md` |
| **Audit integrity** | The following are audited with actor, target, states and time:<br>• doctor decisions<br>• status changes<br>• refunds (including failed Stripe executions)<br>• fraud reviews<br>• ticket replies<br>• report generation and export<br>• notification requeues<br>No write route exists for audit logs; patients get 403 |
| **Export safety** | Formula escaping, zeros kept, exports audited, no medical content |

Full report: `PHASE_04_SECURITY_AND_PRIVACY_REPORT.md`.

## 9. Test statistics (exact, no double counting)

| Suite | Executed | Passed | Failed | Notes |
|---|---|---|---|---|
| Backend pytest (local MongoDB `mediconnect_test`) | 615 | 615 | 0 | Baseline 565 + 26 guard tests + 24 Phase 04 tests. Also run on fresh databases with `.env` variables blanked, and with the newest packages plus `pytest-asyncio`: 615/615 each |
| Admin web (Vitest) | 37 | 37 | 0 | Baseline 32 + 5 Phase 04. `tsc --noEmit` clean; ESLint 0 warnings; `npm run build` OK |
| Flutter | 304 | 304 | 0 | `flutter analyze`: no issues. No mobile code changed; the debug APK was not rebuilt, because no mobile code or contract it uses changed |
| Live admin API UAT (UAT 8001, MongoDB, Stripe test mode) | 90 | 90 | 0 | Includes authorization (10 endpoints × 3 roles), Stripe refunds, concurrency and MongoDB reconciliation |
| Real browser UAT (Chrome → 5174 → 8001) | 13 | 13 | 0 | 16 pages; 390 px layout; confirmation, error and repeat-submission checks |
| Stripe test-mode reconciliation | 54 PaymentIntents | 54 agree | 0 | Part of A-07c |
| Regression: Phase 03 doctor workflow | 45 | 44 | 1 | D-03c: a Phase 03 test-data collision. The check uses "today + 12" (2026-12-08); an earlier Phase 03 run's D-03b deliberately created a 12:15–12:45 window on that date. Not a product change |
| Regression: Phase 03 authorization sweep | 29 endpoints × 7 callers | identical to Phase 03 | 0 differences | Its 4 status-only flags are the same as Phase 03 (patients see their own data; content-verified in Phase 03 and in A-14a) |
| Regression: Phase 02 Stripe test mode | 36 steps | no behavioural difference | — | The only difference is the admin payment total (29 → 41, more data) |
| Regression: Phase 02 patient care | 71 steps | no behavioural difference | — | One more approved renewal accumulated |
| Regression: Phase 01 AI probe | 35 scenarios / 45 turns | 0 safety-field differences (268 values) | — | Fields: isUrgent, intent, metaType, category, medicine card, state |

Overlaps not double-counted: the matrix rows (§5) are drawn from the API and browser UAT runs above; they are not additional executions.

## 10. Before and after evidence

| Item | Before | After |
|---|---|---|
| P3-B2 null fee | `evidence/p3-b2-null-fee-before.txt`: `TypeError … reading 'toLocaleString'` on the original `AppointmentsPage` | `p3-b2-null-fee-after.txt`; browser A-05c-ui shows "Not available"; screenshot `a05c-null-fee-appointments.png` |
| Refund double click (P04-N23) | `browser-run1-observations.txt`: `approvePosts: 2` (Stripe still had one refund) | A-16f `approvePosts: 1` |
| Fraud re-evaluation (P04-N22) | `admin-system-uat-run3.log`: fired rules ≠ evidence | Final run A-08a PASS; `test_n22` |
| Financial double counting (P04-N05) | `test_n05`: the overview gave gross 4,000 / net 2,000 for data worth 6,000 / 3,800 | A-02c/A-06e/A-13b reconcile with MongoDB |
| Screenshots (synthetic data only) | — | dashboard, null-fee appointments, refund leave queue, amount validation, refund-succeeded toast, error state, monitoring, suspend confirmation, 390 px dashboard, patient blocked |
| Database reconciliation | — | A-02a/c, A-05a/e, A-06a–e, A-13a–c; `regression-comparison.json` |

## 11. Git and CI

| Item | Value |
|---|---|
| Baseline | `2078f11` (Phase 03 documentation commit, head of `fix/phase-03-doctor-system-stabilization`) |
| Working branch | `fix/phase-04-admin-system-stabilization` (pushed; **not merged, not deployed**) |
| Implementation commits | **Backend guard and finance:**<br>• `276e02c`: database guard (N01/N02)<br>• `3ed394d`: financial calculation and dates (N05/N06/N07/N17)<br>• `995b7a4`: admin finance, refunds, audit and support (N03/N04/N08–N11/N18)<br>**Backend monitoring:**<br>• `1901a70`: monitoring, fraud and notifications (N12–N16/N20)<br>• `33fdeee`: fraud re-evaluation (N22)<br>**Tests:**<br>• `485e87f`: Phase 04 tests and two date fixes<br>• `ee4f866`: care-plan test clock<br>**Admin web:**<br>• `bb0716d`: null fee, refunds, dashboard<br>• `024f5cc`: double click, labels (N23/N21)<br>**UAT and CI:**<br>• `cb43142`: UAT scripts and fixtures<br>• `9764b26`: CI failure annotations |
| Latest tested implementation commit | `ee4f866` (backend suite, CI). Admin web last changed in `024f5cc` |
| Documentation commit | The commit that adds `docs/uat/phase-04` reports (after `ee4f866`; see `git log`) |
| CI: Backend | `024f5cc` **failure**; `cb43142` **failure** (same test). The failing test was found by the annotations added in `9764b26` (that run also failed: `test_care_plans::test_11`). Fixed in `ee4f866`: **run 45707115443 success** |
| CI: Admin Web | Run 45703090846 on `024f5cc`: **success** (typecheck, lint, tests, build). Later commits do not touch `admin-web` |
| CI: Mobile | Not triggered: no mobile changes in Phase 04. Local `flutter test` 304/304; `flutter analyze` clean |
| Working tree | Clean after the documentation commit, except the owner's pre-existing untracked `docs/uat/phase-03.zip`, left untouched |

## 12. Remaining blockers

Full reconciliation: `PHASE_04_REMAINING_BLOCKERS.md`.

| Type | Items |
|---|---|
| Urgent owner action | **P4-B1:** remote database inspection. **P4-B2:** credential rotation |
| Technical | P4-B3 (8000 default), P4-B9 (fraud telemetry), P4-B10 (refund webhooks, reconcile audit), P3-B7, P3-B8, P3-B11, B16, B17 |
| External integrations | B3 (Stripe webhooks), B4 (FCM), B5 (email/SMS), B13 (LLM/Vision) |
| Owner decisions | B6 refund/reschedule policy, B7 measurement stores, B9 in-person migration, P3-B5 old reminders cleanup, P3-B6 rejected-doctor appeal, P4-B5 development defaults, P4-B6 historical doctor cancellations without a refund request, P4-B7 platform fee model, P4-B8 support scope |
| Clinical approvals | B1, B2, P3-B9 (drug interactions) |
| Privacy approvals | P4-B4a (care plan content), P4-B4b (booking note), B8 (encryption at rest) |
| Physical device | B10, P3-B10 |
| Language review | B12 |

## 13. Phase 05 handover: prioritised checklist

1. **Owner:** complete the incident review (P4-B1) and rotate credentials (P4-B2) before any staging deployment.
2. **CI:** Backend CI is green on `ee4f866`. Keep the failure annotations (`9764b26`). Run the suite once on a UTC machine after 18:30 UTC to catch other local-time assumptions.
3. **Configuration safety:** decide development defaults (P4-B5); point the admin `.env.example` away from 8000 (P4-B3); deny-list or short-lived access tokens.
4. **Security hardening:**
   - encryption at rest for medical and verification documents (B8)
   - CSP and no third-party fonts (P4-O3)
   - single mount of the security router (P4-O8)
   - failed-login telemetry (P4-O5)
   - audit reconcile-refund and verification-document views (P4-O7)
5. **Privacy decisions:** P4-B4a/b. Optional admin sub-roles (support, auditor, break-glass).
6. **Payments:**
   - Stripe webhook delivery and refund webhooks (B3, P4-O6)
   - define the fee/payout model before showing revenue (P4-B7)
   - review historical doctor cancellations (P4-B6)
7. **Shared AI architecture:** one orchestrator for the patient, doctor and admin assistants, with schema-validated tools. If LLMs are enabled (B13), keep the read-only admin registry and human approval for every state change.
8. **Robustness and performance:**
   - list endpoints should not fail on one malformed record (P4-O1)
   - paginate in MongoDB, not in memory (P4-O4)
   - multi-process mutation tests (P3-B11)
9. **External delivery:** FCM, SMTP and SMS with test credentials (B4, B5), then monitoring re-verification.
10. **Approvals and devices:**
    - clinical and pharmacist sign-off (B1, B2, P3-B9)
    - Sinhala/Tamil review (B12)
    - physical device pass (B10, P3-B10)
11. **Product decisions:** B6, B7, B9, P3-B5, P3-B6, P4-B8.

## 14. Release readiness

| Target | Assessment |
|---|---|
| Academic demonstration | **Ready.** All admin pages work against real data with truthful figures; Stripe test mode end to end |
| Local UAT | **Ready.** Isolated database, guarded scripts, seeded fixtures |
| Staging | **Not ready.** P4-B1 is unresolved; credentials not rotated (P4-B2); no webhook, push, email or SMS delivery (B3–B5); encryption at rest missing (B8) |
| Clinical pilot | **Not ready.** No clinical or pharmacist approval (B1, B2); no drug-interaction source (P3-B9); privacy decisions open |
| Production | **Not ready.** All of the above, plus live payments not verified (test mode only by design) |

No clinical approval or production readiness is claimed.
