# R03 — Demonstration Readiness Checklist (for R05)

For: whoever records the R05 demonstration. 2026-11-28. Prepared only: no video was recorded or edited in R03.

## Common setup

- Local MongoDB with `mediconnect_uat` only.
- Backend: `powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1 -SkipSeed` (port 8001, deterministic AI by default).
- Android emulator with the debug APK from `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001`.
- Admin web: `npm run dev` in `admin-web` (`127.0.0.1:5174`).
- Synthetic accounts are on the `uat.mediconnect.lk` domain; the shared UAT password is in the git-ignored `backend/uat.env`. Never show it on screen.
- **Before recording:** keep the backend local (credential incident P5-C1), use synthetic images only, and do not show tokens, `uat.env` or database URLs.

## Features

| Feature | Synthetic account | Local data | Provider | Expected screen | Known limitations | Genuine evidence |
|---|---|---|---|---|---|---|
| Branding and splash | any | — | — | Launcher icon, splash, welcome | White native splash in both modes (R01-O4) | Yes: `r03_e00`–`r03_e02`, `r03_e14` |
| Multilingual AI Health Assistant | `uat.p02.patientb` | Health libraries | Deterministic (Gemini optional, needs authorisation and caps) | Assistant replies in English, Sinhala, romanised | Native-language review pending (B12) | Yes: A03 probe re-run (R03); live Gemini in A01 |
| Contextual doctor recommendations | `uat.p02.patientc` or `uat.patient2` | Approved doctors | Deterministic | Doctor cards with picture and fee; refinement keeps context | — | Yes: `r03_e08`, Workflow A A01–A02 |
| AI-assisted booking | `uat.p02.patientc` | Free slots | Deterministic | Proposal → explicit Accept → hold | — | Yes: Workflow A (API); A03 device |
| Stripe test-mode payment | `uat.p02.patientb` | Hold | **Stripe test mode: needs authorisation for R05** | PaymentSheet with a test card | Not run in R03 (no authorisation) | Yes, in A03 (test mode 43/43, emulator PaymentSheet) |
| Medicine image analysis | `uat.p02.patientb` | Synthetic packaging images (A01 fixtures) | **Gemini vision: needs `-EnableVision`, authorisation and quota** | Result card with refusal rules | Synthetic images only; physical camera untested | Yes, in A01 (live, synthetic); not live in R03 |
| Doctor clinical workflows | `uat.p03.doctor.alpha` | Confirmed appointments | — | Queue, preparation, notes, prescription | Clinical validation absent | Phase 03 / A04 device; R03 renewal flow |
| Clinician-approved prescriptions and renewals | `uat.p03.doctor.alpha`, `uat.p03.patienta` | Issued prescriptions, pending renewals | — | Approval dialog with original instructions; renewed prescription | Pharmacist review absent | Yes: `r03_e18`–`r03_e22` |
| Patient reminders | `uat.p03.patienta` | Renewed prescription | — (push not configured) | Locked dose/frequency; times chosen by the patient; My Medications | In-app and device reminders only | Yes: `r03_e23`–`r03_e25` |
| Patient and doctor profile pictures | `uat.patient2`, `uat.doctor.neuro` | Synthetic abstract images (uploaded in R03) | — | Profile, editor, doctor cards, admin avatar | Emulator camera only | Yes: `r03_e04`–`r03_e09`, `r03_e16`, `r03_b02` |
| Customer support | a patient + `uat.admin` | Tickets (A05) | — | Ticket → admin reply → follow-up | — | A05 device and browser; R03 API re-run |
| Admin dashboard | `uat.admin` | UAT data | — | Command centre, doctors, payments, audit | — | Yes: `r03_b01`–`r03_b13` |
| Fraud monitoring | `uat.admin` | Hoarding fixtures (A05) | — | Assessment with evidence and review history | Thresholds provisional; UAT data accumulates (R03-O1) | Yes: `r03_b08`, A05 browser |

**Do not demonstrate as real:**
- clinical accuracy;
- SLMC registry verification (none exists);
- push, e-mail or SMS delivery;
- OpenAI generation;
- the dormant dedicated recommendation screen.
