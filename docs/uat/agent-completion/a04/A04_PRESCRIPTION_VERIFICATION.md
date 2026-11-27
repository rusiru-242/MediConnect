# A04 — Prescription Workflow Verification

For: reviewers and the project owner. Covers the doctor workflow, the patient view, renewals and the reminder link for Agent 17. Evidence paths are relative to this folder.

## What exists (audit)

There are two issuing paths, and both store into `prescriptions`. A04 completed them rather than adding a new subsystem.

| Path | Used by | Flow |
|---|---|---|
| Consultation path | Mobile doctor app ("Consultations & Prescriptions") | `POST /medical-records`, then `POST /prescriptions` (record-linked). Amend: `PATCH /prescriptions/{id}` (issuing doctor, mandatory reason, amendment history) |
| Clinical workflow path | API (and the P03 doctor workflow UAT) | `POST /clinical/prescriptions/sign` (optional visit) |

**Renewals:**
- Patient request: `POST /clinical/prescriptions/renewals`.
- Doctor decision: `POST /clinical/prescriptions/renewals/{id}/review`, approve, reject or needs consultation. Only the prescribing doctor decides, with an atomic review lock.
- Approval issues a new prescription that copies the original item exactly.

**Reminders:**
- Patients create reminders against a prescription item (count and duration checked against the prescription).
- Doctors can approve server-side schedules (`/care-automation/prescriptions/{id}/schedule`).
- Nothing is scheduled at signing.

**Drafts:** there is no persisted prescription draft; the doctor's form holds the entries until Confirm & Issue. A04 added a structural draft check that stores nothing. P06 is therefore NOT APPLICABLE.

## Doctor workflow (emulator, synthetic doctor "Dr. P03 Alpha")

| Step | Before A04 | After A04 (evidence) |
|---|---|---|
| Open documentation list | Always "No Consultations Pending Documentation" (A04-BUG-011) | Completed and confirmed visits listed (`a04_e02`) |
| New medication item | Dose, frequency, duration, quantity and instructions pre-filled; no quantity field (A04-BUG-009) | All empty; examples as hints; quantity field (`a04_e04`) |
| Submit with name and strength only | Issued with the pre-filled dosing | Refused: "enter the dose, frequency, duration, quantity. Nothing is filled in for you." (`a04_e05`) |
| Review before issuing | Generic "are you sure" | Lists exactly what was entered, the documented-allergy match for `Allergenol-95EF8` from the backend, and "Drug-interaction checking is not available" (`a04_e06`). Cancel stored nothing (database: 0 records, 0 prescriptions) |
| Issue | — | Changed medicine, review shows "No match…" (`a04_e07`), Confirm & Issue → `RX-20261127-E389AE`, items exactly as entered, linked to the visit and its record (`a04_e08`) |
| Retry after a failed prescription | Record recreated → "already exists", prescription impossible (A04-BUG-010) | Record reused (widget test) |
| Renewal queue | Blank on a phone; Approve cut off (A04-BUG-014) | Requests listed (`a04_e18`); approval dialog shows strength, dose, route, frequency, duration, quantity (`a04_e19`); approved (`a04_e20`) |

## Patient workflow (emulator, synthetic "P03 Patient A")

| Step | Evidence | Result |
|---|---|---|
| Prescription list and detail | `a04_e09`, `a04_e10` | Medicine, strength, route, dose, frequency, duration, quantity, instructions, prescriber, SLMC number, date and status match the database |
| Persistence | Logout and login; app restart (`a04_e17`) | Still visible |
| Set reminder | `a04_e11`, `a04_e12` | 2 times for "Twice daily"; 5-day course stored (not 14) |
| Duplicate reminder | `a04_e13` | Refused with "An active reminder already exists…" (was the account message, A04-BUG-013) |
| Request renewal | `a04_e14`, `a04_e15` | From the medicine on the prescription; exact id and name sent; the prescribing doctor is notified |
| Duplicate renewal | `a04_e16` | "already pending clinician review" |
| Decision | `a04_e21`, `a04_e22` | Notification "Your prescription renewal was approved by your doctor."; renewal list shows APPROVED (the list was unreachable before, A04-BUG-015) |

## API and database checks

| Check | Result |
|---|---|
| Whitespace field, repeated medicine, empty list | 422, 422, 400 |
| 4 simultaneous identical signs | 1 stored (was 3) |
| Renewal for a medicine not on the prescription | 422 (was 201) |
| Case-variant duplicate renewal | 409 (was 201) |
| Renewal approval | New prescription items identical to the original, same visit, `RENEWAL_APPROVED` audit, no automatic reminder |
| Amendment | Status AMENDED, previous items in `amendmentHistory`, `AMENDED` audit, outdated patient reminders cancelled with a notice |
| Notifications | Lock-screen text names no medicine or prescription id (prescription issued, record available, renewal requested, renewal decided, prescription updated) |

## Not done

| Item | Reason |
|---|---|
| Doctor rejection on the emulator | Covered at API level and by an automated test only |
| A device reminder set on the renewed prescription | Not exercised |
| Physical phone | Gate B10 |
