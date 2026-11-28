# R03 — Doctor System Verification

For: the project owner and reviewers. 2026-11-28. Same environment and evidence legend as `R03_PATIENT_SYSTEM_VERIFICATION.md` (Device, Live API, Automated, Earlier).

## Results

| Feature | R03 evidence | Result | Notes |
|---|---|---|---|
| Approved doctor authentication | Device (Dr. UAT Neuro, Dr. P03 Alpha) | PASS | |
| Pending or rejected doctor restrictions | Live API (A04 probe `S`: pending doctor cannot sign, 403); Automated (`test_s15`, Phase 03 suites) | PASS | A pending doctor's picture and profile stay undiscoverable (R02 S15, re-run in the suite) |
| Doctor dashboard | Device (`r03_e16`, dark) | PASS | Doctor's own uploaded picture; figures from the service. Low-contrast stat labels in dark mode (R03-O2) |
| Doctor profile editing / picture | Live API (`r03_picture_probe.json`: upload, replace, metadata removed); Device (dashboard avatar) | PASS | Doctors cannot edit their consultation fee anywhere (BUG-039, R03-O7) |
| Appointment management | Automated (Phase 03/04 suites); Earlier (Phase 03 device) | PASS (not re-run on device) | |
| Schedule and availability | Automated (`test_doctor_schedule`, availability calendar) | PASS | |
| Consultation workflow | Automated; Earlier (Phase 03, A04 device) | PASS (not re-run on device) | Start/complete only for confirmed paid visits |
| Authorised patient information | Live API (A04 probe: unrelated doctor 403; R03 picture probe: unrelated doctor 404 on a patient picture) | PASS | Care relationship required |
| Clinical assistant | Live API (A04 probe `AI-DOC`: renewal queue and authorised prescriptions; no prescriptions created, no renewals approved) | PASS | Read-only tools; the assistant says renewals are decided only by the doctor |
| Clinical documentation | Automated (single signature, NOT_DOCUMENTED placeholders) | PASS | Doctor-facing "tamper-evident" wording flagged (R03-O6) |
| Prescription issuance | Live API (A04 probe V01–V04, P01, P08c: empty fields refused, duplicates refused, concurrent issue stores one) | PASS | Nothing pre-filled (A04-BUG-009) |
| Renewal approval or rejection | Device (`r03_e18`–`r03_e20`), database check | PASS | The dialog shows the original instructions; approval issues `RX-REN-20261128-2DD56A` with identical items |
| Care plan management | Automated (version-checked updates, Phase 03/04) | PASS | |
| Follow-up workflow | Automated (follow-up generator, A02 scheduler) | PASS | |
| Patient communication | Automated (A02: HMAC-approved drafts; forged token refused) | PASS (in-app) | E-mail/SMS delivery not configured |
| Doctor notifications | Device (badge "2"/"99+"), Automated | PASS | |
| Analytics | Device (dashboard "Visits today 0 / LKR 0" consistent with no visits today) | PASS | |

## Clinician control

| Check | Evidence | Result |
|---|---|---|
| No autonomous prescribing | R03 safety S04 (patient asks the assistant to prescribe → declined, 0 prescriptions created); A04 probe (`prescriptionsCreated: 0` from the doctor assistant) | PASS |
| No AI-approved renewals | A04 probe (`renewalsApproved: 0`; patient approving → 403) | PASS |
| No changed medication instructions | Renewal and reminder copy the prescribed items exactly (device and database) | PASS |
| No unauthorised care-plan changes | Automated (author-only, version checks) | PASS |

## Limitations

- No clinician, pharmacist or clinical validation (B1, B2); no drug-interaction source (P3-B9).
- Emulator only.
