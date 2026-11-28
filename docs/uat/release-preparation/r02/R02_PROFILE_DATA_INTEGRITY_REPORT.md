# R02 — Profile Data Integrity Report (resolves A05-O1)

For: the project owner and clinical/product reviewers. Records what invented data the patient Profile screen showed, what replaced it, and the P01–P10 results.

## What the screen showed before

Captured on the R01 build (`evidence/emulator/r02_before_e01–e03`), for every patient regardless of their records:

| Shown | Source |
|---|---|
| Height 5'7" / 170 cm, weight 134 lbs "(Stable)", BMI 21.0 "Normal" | Literals in the screen |
| Allergies: **Penicillin**, "Moderate", styled as a clinical alert | Literal |
| "Emergency Contact: Spouse", showing the **patient's own** phone number; the call button only showed "Calling …" | Literal label + `user.phone` |
| Patient number "#MC-88392"; "28 yrs • Female • Blood Type: O+"; a verified badge | Literals |
| "MediConnect Pass / Digital Health ID", insurance "BlueCross MediConnect", policy "#9482-108", "Fast Track Check-in" QR, "ACTIVE TIER 1" | Literals (no such feature exists) |
| "Updated 3 days ago • Full history", "2 current medications", "Metabolic panel, lipid test PDFs" | Literals |
| Fallback e-mail `patient@example.com`, fallback phone `+94 77 123 4567` | Literals |
| "Edit Profile" → "Profile information updated successfully." without saving | Placeholder handler |

No such value was ever stored: they existed only in the screen code. No database clean-up is needed (R02-O5); no migration was run.

## What replaced it

| Data | Now |
|---|---|
| Name, e-mail, phone | The account's real values; a missing value shows "Not provided" |
| Height, weight | Patient-reported, optional, validated (50–250 cm, 2–350 kg), labelled "Entered by you". Missing values show "Not provided" |
| BMI | Calculated on the server only when both values exist (`kg / m²`, one decimal), with "Calculated from the height and weight you entered. It is not a diagnosis." No category such as "Normal" is shown |
| Allergies | Three explicit, separate choices: **Not provided** (default, nothing assumed), **No known allergies** (an explicit statement by the patient), **I have allergies** (1–20 named items, each up to 80 characters). The server rejects inconsistent combinations. Shown as "Reported by you: …" |
| Recorded allergies | Active `allergy` entries from the patient's medical record, with their provenance ("Recorded by a clinician", "From your uploaded records", …). Shown read-only, never copied into the self-report, never deleted |
| Emergency contact | Optional name, relationship and phone (validated) entered by the patient; otherwise "Not provided" with an "Add" button. No call action is faked |
| While loading or after a failed load | A spinner or a retryable error; no value is claimed |
| Records section | Navigation tiles with neutral descriptions; no invented counts or dates |

**Clinician verification:** health measurements and allergy records already carry provenance (`patient_reported` / `clinician_reviewed`, `sourceType`). The profile keeps self-reported values separate from recorded ones and labels both. Clinician confirmation of self-reported values is outside R02.

**AI:** no profile value is created or changed by an AI model.

## API

- `GET /api/profile/me`: patients only (403 for doctors and admins); always the authenticated patient's own data.
- `PATCH /api/profile/me`: patients only. Unknown fields are rejected (`extra="forbid"`; so `role` or `email` → 422), and an explicit `null` clears a value. It changes only `fullName` and `users.healthProfile`.

## Verification matrix

| ID | Scenario | Evidence | Result |
|---|---|---|---|
| R02-P01 | No hard-coded height | `test_p01_p06`; widget `P01-P06`; device `r02_after_e01` ("Not provided") | PASS |
| R02-P02 | No hard-coded weight | Same | PASS |
| R02-P03 | BMI only from valid actual values | `test_p03_p07_p09` (height alone → no BMI; 170/65 → 22.5; clearing height → no BMI); device 165 cm / 58.5 kg → 21.5 with the note (`r02_after_e14`) | PASS |
| R02-P04 | No fabricated allergy; genuine records kept | `test_p01_p06` (no "penicillin" anywhere in the response), `test_p04` (a clinician-recorded allergy is shown with provenance and is not copied), widget P03/P04; device: "Reported by you: Not provided", then "No known allergies" after the explicit choice. **The fabricated Penicillin allergy is no longer shown** | PASS |
| R02-P05 | No fabricated emergency contact | Widget `P01-P06` (`emergency_not_provided`); device "Not provided" + "Add" (`r02_after_e02`) | PASS |
| R02-P06 | Appropriate missing-data display | Widget tests (including the loading and failed-load states); device | PASS |
| R02-P07 | Valid authorised updates | `test_p03_p07_p09`; widget P07/P08 (only changed fields sent); device edit form (`r02_after_e13/e14`) | PASS |
| R02-P08 | Invalid updates rejected | `test_p08` (15 cases: out-of-range height/weight, unknown status, inconsistent allergy lists, over-long or too many items, bad phone, empty contact name, `role`, `email`, one-character name, control characters) → 422, stored data unchanged; client validation in the widget test | PASS |
| R02-P09 | Correct persistence | `test_p03_p07_p09` (re-read); device after app restart (`r02_after_e15`, new process 27364 → 29513) and after logout/login | PASS |
| R02-P10 | Cross-patient access rejected | `test_p10` (doctor/admin → 403; another patient's update not visible; unauthenticated → 401/403); `test_p04` (no record leakage); the endpoint has no id parameter | PASS |
