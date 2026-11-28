# R03 — Clinical Safety Limitations

For: the project owner, academic reviewers and any future clinical partner. 2026-11-28.

**MediConnect is not clinically validated.** No clinician, pharmacist or regulator has reviewed or approved any component. R03 is engineering verification with synthetic data; it does not establish medical accuracy, and no accuracy percentage is claimed anywhere.

## What the software enforces (engineering, verified)

| Safeguard | Evidence |
|---|---|
| Emergency triage runs first on every patient message, with verified Sri Lankan numbers (1990, 1926, 1333); the dialer opens only after confirmation | R03 S01, HC, device SOS dialog; P05 `emg` |
| Educational questions are no longer escalated because of "I'm curious"-type phrases; symptoms and self-harm still escalate | R03-BUG-002, before/after evidence |
| No AI dosing, dose changes or prescribing | S03, S04; A04 suites |
| Prescriptions, renewals and reminders carry the clinician's exact instructions; nothing is pre-filled | A04 probe; R03 device renewal and reminder |
| Clinician approval for prescriptions, renewals, note signing and care plans | A04, Phase 03 suites; R03 device approval |
| No invented clinical or doctor information | R02-BUG-001 (profile), R03-BUG-003 (rating/banner), R03-BUG-004 (verification claims) |
| BMI shown only from patient-entered values, labelled "not a diagnosis" | R02, R03 device |

## Open clinical requirements (unchanged by R03)

| ID | Requirement | Affects |
|---|---|---|
| B1 | Clinical validation of triage rules, health-assistant content, alert thresholds, follow-up timings | 02, 06, 08, 10, 15, 16, 34 |
| B2 | Pharmacist review of medicine information, reminder logic and prescription presentation | 04, 05, 11, 17 |
| P3-B9 | A clinically validated drug-interaction data source (current checks are allergy and active-medicine matching only) | 17 |
| B12 | Native-speaker review of Sinhala and Tamil responses, including emergency wording | 01, 02, 33, 34 |
| — | Medicine image analysis on real photographed packaging, and a data-processing agreement before any real patient image is sent to a provider | 04 |
| — | A clinician workflow to confirm patient-reported height, weight and allergies | Profile (R02) |
| — | The R03-BUG-002 triage change narrows a false positive; it should be included in the clinical review of Component 34 | 34 |

## Product-policy decisions (not defects)

| Item | Current behaviour | Decision needed |
|---|---|---|
| BUG-039 (consultation fee) | Doctor registration has no fee field and no screen or API lets a doctor or admin change the fee; every doctor registered through the app charges the LKR 2,500 default | Should doctors enter their own fee at registration? May they change it later, and must an admin confirm it? Is LKR 2,500 an acceptable default or should a missing fee block approval? |
| B6 (refund and cancellation policy) | Implemented policy amounts from earlier phases; not confirmed by the owner | Confirm cutoffs, percentages and who bears payment fees |

R03 did not invent or change any fee, commission, refund percentage or deadline.
