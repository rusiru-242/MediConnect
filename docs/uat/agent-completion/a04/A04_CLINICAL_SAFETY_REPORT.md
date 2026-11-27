# A04 — Clinical Safety Report (Agent 17)

For: the project owner, a clinical reviewer and a pharmacist. This report says what the software checks and what it does not. It is not a clinical validation, and MediConnect is not clinically approved.

## Safeguards in place after A04

| Safeguard | Where | Verified by |
|---|---|---|
| Only an approved doctor with a care relationship can issue, review or check a prescription; pending or rejected doctors, patients and administrators cannot | `PrescriptionWorkflowService._assert_approved_doctor`, `ClinicalSafetyService.verify_doctor_patient_care_relationship`, `require_doctor` | Probe S; tests s01–s04 |
| Every dosing field is entered by the doctor; nothing is pre-filled or defaulted in the app | Mobile form (A04-BUG-009) | Widget test; emulator |
| The doctor reviews the exact items before issuing | Confirm dialog with the draft-check findings | Widget test; emulator |
| Required fields are present and non-blank; no medicine is listed twice | Request schemas | Tests bug001, bug002 |
| One prescription per submission, also under concurrency | Claim document (database-level) | Tests bug003; probe |
| Documented-allergy and active-prescription matches are shown | `check_prescription_safety` | Test bug004; emulator |
| A renewal copies the original instructions exactly; the prescribing doctor decides; one decision under concurrency | `_issue_renewal_prescription`, review lock | Test r02 |
| No reminder is created by signing or renewal; reminders follow the prescribed count and duration; ambiguous frequencies ("when required") are refused | Reminder service, schedule approval | Tests m01–m03 |
| Reminders built on superseded instructions stop when a prescription is amended | A04-BUG-008 | Test bug008 |
| The assistant never prescribes, approves, signs, renews or changes anything, and reads only authorised records | Prescription assistant and tools | Tests ai_*; probe |
| Audit: SIGNED, ISSUED, VIEWED, AMENDED and RENEWAL_APPROVED entries are appended; previous items kept on amendment | Prescription documents | Test s05 |

## Structural versus clinical validation

| Structural checks (implemented) | Clinical checks (not implemented and not claimed) |
|---|---|
| Field present and non-blank; medicine not repeated; frequency and duration readable for reminders; strength has a recognised unit (warning only); prescription current; medicine on the prescription | Dose ranges by age, weight, renal or hepatic function; maximum daily doses; contraindications; pregnancy and breastfeeding; drug–drug and drug–disease interactions; formulary or brand substitution |

No dosage limits or contraindication rules were invented. Free-text clinical fields (for example "as needed", "until review") are accepted, because there is no authoritative vocabulary to judge them. The draft check only notes when reminders cannot be scheduled from them.

## Known limitations

| Limitation | Detail |
|---|---|
| Drug-interaction checking | Unavailable (P3-B9). The review states "Drug-interaction checking is not available … No interaction result is implied." A clinically validated source would need owner approval and a licence decision |
| Allergy matching | A case-insensitive substring match of the medicine name against documented allergen titles. It does not know drug classes (for example a penicillin allergy against amoxicillin) and misses allergies recorded under other names. A match is a prompt, and no match is not evidence of safety |
| Active-medication list | Only MediConnect prescriptions. Medicines from other clinics are not known |
| Renewal and original | Both remain current after a renewal (A04-O3); supersession is a clinical policy decision |
| Route default | API clients that omit the route get "Oral" (A04-O2); the app always sends an explicit route |

## Release gates (unchanged by A04)

| Gate | Requirement |
|---|---|
| Pharmacist review | The prescription content, wording and the allergy-check behaviour |
| Clinical validation | Of Agent 17 as a whole, by a qualified clinician |
| Drug-interaction source | Decision on a validated source (P3-B9) |
| Native-language review | Of patient-facing text (B12) |
