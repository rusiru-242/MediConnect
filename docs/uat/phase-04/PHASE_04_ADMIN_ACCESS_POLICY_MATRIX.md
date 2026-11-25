# Phase 04 — Admin Access Policy Matrix (P3-B4)

For: the project owner (who makes the policy decision) and the Phase 05 security team. 2026-11-26.

## 1. Correction to the Phase 03 finding

Phase 03 recorded: "admins can read patients' clinical records, notes and trends (200 in the sweep)". **That was based on status codes only.**

In the clinical services, the `patientId` parameter is used only for doctors. Every other role, including ADMIN, gets **its own** data (`patient_id = current_user.id`), so an admin's 200 response contains the admin's own, empty, records.

Verified by content in Phase 04:
- **A-14a:** a synthetic patient record "P04 synthetic allergy record" was not present in any admin response from six clinical routes.
- **Backend test:** `test_a14_admin_clinical_routes_return_no_patient_clinical_content` checks the same with records and signed notes.

So there is **no admin path to patient medical records, clinical notes, measurements or prescriptions through the clinical API**. The remaining admin exposure of clinical-adjacent information is listed below, and is a policy decision.

## 2. Inventory of admin access to sensitive data

| Data | Admin route | Today | Purpose | Proposed (least privilege) | Decision needed |
|---|---|---|---|---|---|
| Medical records, uploaded medical documents | `/clinical/records*`, `/clinical/records/{id}/document` | **No access** to patients' data (own data only) | — | Keep: no admin access | No |
| Clinical (SOAP) notes | `/clinical/notes` | **No access** | — | Keep | No |
| Health measurements and trends | `/clinical/measurements*` | **No access** | — | Keep | No |
| Prescriptions and renewals | `/prescriptions/me`, `/clinical/prescriptions/renewals` | **No access** to patients' prescriptions (own list only) | — | Keep | No |
| Care plan content (tasks, instructions, diagnosis context) | `GET /care-plans/{id}` | **Allowed** for ADMIN (`care_plan_service`, `is_admin`) | Unclear; no admin screen uses it | Remove admin access, or allow only through an audited "break-glass" support flow | **Yes (owner)** |
| Appointment detail and the patient's booking note (reason for visit, patient-reported) | `GET /appointments/{id}`, `/admin/appointments` (`patientNote`) | **Allowed** | Operations: disputes, refunds, support | Show operational fields by default and hide `patientNote` behind an explicit "show reason" action that is audited | **Yes (owner)** |
| Appointment events (status history) | `/appointments/{id}` events | Allowed | Operations and disputes | Keep; contains no clinical content | No |
| Support ticket text (may include symptoms written by the patient) | `/admin/workflow/tickets*` | Allowed | Support | Keep, because admins must read tickets; the emergency flag already advises 1990 | Confirm |
| Refund reason and cancellation reason | `/admin/workflow/refunds*` | Allowed | Refund decisions | Keep | No |
| Doctor verification documents (doctor's own credentials) | `/admin/doctors/applications/{id}/documents/{doc}` | Allowed (admin only; traversal refused, A-03c) | Doctor verification | Keep; add an audit record for each document view | Recommended |
| Patient identity (name, email, phone) | `/admin/users`, `/admin/appointments`, `/admin/payments` | Allowed; no password hashes, tokens or medical fields (A-04e) | Account administration | Keep; mask phone numbers in lists (Phase 05) | Optional |
| Payment data | `/admin/payments`, `/admin/workflow/payments` | Allowed; no card data; monitored list masks names (A-14c) | Financial oversight | Keep | No |
| Audit logs | `/admin/workflow/audit-logs` | Admin read-only; **no write route** (A-14e) | Accountability | Keep; consider a separate "auditor" role | Optional |
| Admin AI assistants | `/admin/workflow/assistant`, `/security/ai-assistant/chat` | Admin only; read-only tools; no clinical tools in the admin registry | Operations | Keep | No |

## 3. Proposed access model (needs an owner decision; not implemented)

| Role | Clinical content | Operational metadata | Financial | Accounts | Audit |
|---|---|---|---|---|---|
| ADMIN (operations) | None | Read | Read; refund decisions | Suspend/reinstate; verify doctors | Read |
| Support agent (future role) | None; tickets only | Read (own queue) | Read refund status | None | None |
| Clinical safety officer (future role, break-glass) | Read only, with a reason, time-limited, every access audited | Read | None | None | Read |
| Auditor (future role) | None | None | Read | None | Read |

## 4. Decisions recorded

| Item | Status |
|---|---|
| General ADMIN role entitled to medical records, notes, measurements, prescriptions | **Not entitled** (current behaviour, verified). No change made |
| Admin access to care plan content (`GET /care-plans/{id}`) | **Open: owner decision (P4-B4a).** Not removed in Phase 04: no admin screen uses it, but its purpose is undocumented, so it is not silently changed |
| Admin visibility of `patientNote` | **Open: owner decision (P4-B4b)** |
| Audit record for doctor-document views | Recommended (Phase 05) |
| Encryption at rest for uploaded documents | Carried as **B8** (Phase 05) |
