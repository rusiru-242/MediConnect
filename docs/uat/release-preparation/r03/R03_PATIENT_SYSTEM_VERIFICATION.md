# R03 — Patient System Verification

For: the project owner and reviewers. 2026-11-28. Local only: Android emulator (Pixel 7 Pro image, debug APK built with `API_BASE_URL=http://10.0.2.2:8001`), UAT backend `127.0.0.1:8001` on `mediconnect_uat` with the deterministic AI engine, synthetic accounts and synthetic images.

**How to read the "R03 evidence" column:**
- **Device** — exercised on the emulator in R03, with a screenshot.
- **Live API** — exercised against the running UAT backend in R03 (probe JSON).
- **Automated** — covered by the final automated suites run in R03.
- **Earlier** — verified in an earlier phase and not repeated on the device in R03; the automated suites still cover it.

## Results

| Feature | R03 evidence | Result | Notes |
|---|---|---|---|
| Registration and authentication | Automated; Earlier (Phase 01–02 UAT) | PASS (not re-run on device) | Login used throughout R03 on the device for four accounts |
| Login and logout | Device (`r03_e03`, `r03_e14`), Live API (`SEC`) | PASS | Logout invalidates the refresh token and the access token (`refreshAfterLogout` 401, `accessAfterLogout` 401) |
| Session restoration | Device | PASS | App force-stopped and relaunched three times; each time it returned to the signed-in dashboard. Picture persistence across a backend restart was checked through the API (identical SHA-256) |
| Patient dashboard | Device (`r03_e03`, dark `r03_e12`) | PASS | Greeting, AI entry, quick actions, real upcoming appointments |
| Profile data | Device (`r03_e04`, dark `r03_e13`) | PASS | Only stored values; BMI with "not a diagnosis"; "Reported by you" labels (R02) |
| Profile picture management | Device (`r03_e04`, `r03_e05`), Live API (`r03_picture_probe.json`) | PASS | Upload, replace, metadata removal, privacy matrix, restart persistence (identical SHA-256) |
| Multilingual AI Health Assistant | Live API (A03 probe re-run: EN, Sinhala, romanised, mixed) | PASS (deterministic engine) | Live Gemini not used in R03 (not authorised); A01 holds the live-provider evidence |
| Doctor search | Device (`r03_e06`), Live API | PASS | Real fee, real picture, approved doctors only |
| Intelligent doctor recommendations | Device (`r03_e08`), Live API (A01–A02 of the R03 probe) | PASS | Cards match `doctor_profiles`; picture from the doctor's record |
| Context-aware follow-up | Live API (A02) | PASS | Adding a fee limit kept specialty and city |
| Appointment availability | Live API (A03), Device (`r03_e07` slots) | PASS | Proposal from a real free slot |
| AI-assisted booking | Live API (A03–A09) | PASS | Hold only after explicit Accept by the owner; one hold; second Accept idempotent |
| Booking confirmation and payment status | Automated (A03 suites, Stripe test doubles); Earlier (A03: Stripe test mode, PaymentSheet on the emulator) | PASS (no new Stripe request in R03) | R03 had no Stripe authorisation; the hold was released |
| My Appointments | Device (`r03_e09`) | PASS | Doctor picture and real states |
| Cancellation and rescheduling | Automated; Earlier (A03 device: cancel → refund) | PASS (not re-run on device) | The assistant refuses to cancel from chat and points to the screen |
| Prescription viewing | Device (`r03_e21`, `r03_e22`) | PASS | Exact clinician instructions; truthful footer after R03-BUG-004 |
| Prescription renewal requests | Live API (A04 probe re-run R01–R04), Device (doctor side) | PASS | Duplicate request refused (409); only prescribed medicines |
| Medicine image analysis | Automated (A01 vision suite with test doubles) | PASS (provider path not live in R03) | Image analysis is disabled in the UAT backend; A01 holds live synthetic-image evidence; physical camera untested |
| Medication reminders | Device (`r03_e23`–`r03_e25`, empty state `r03_e10`) | PASS | Reminder locked to the prescribed dose, frequency and 5-day duration |
| Appointment, follow-up and medical-test reminders | Automated (A02 suites, real scheduler with injected clock) | PASS (in-app) | Push, e-mail and SMS not configured (unchanged blockers) |
| Notifications | Live API (`SEC`: another patient's notification refused, 403) | PASS | In-app store; external channels blocked |
| Help and Support | Device (`r03_e11`), Live API (A05 C-steps) | PASS | Ticket, admin reply, follow-up, ownership checks |
| Emergency SOS | Device (`r03_e10_emergency_sos_dialog`) | PASS | Confirmation dialog before the dialer; verified number 1990 |

## Trusted-data checks

| Data | Source verified | Result |
|---|---|---|
| Doctors in search and AI cards | `doctor_profiles` (approved), compared field by field (A01, A03 probe) | Match |
| Fees | Stored `consultationFee`; proposal amount = stored fee (A07: 2000 = 2000) | Match |
| Doctor photos | `users.profileImage` of the doctor (picture probe: search and appointments use the same URL) | Match |
| Ratings | Doctor details showed an invented 4.9 — **fixed** (R03-BUG-003); now "No reviews" when none exist | Fixed |
| Health profile | Only stored values (R02); verified again on the device | Match |
| Prescriptions and reminders | Stored prescription items; reminder inherits them unchanged | Match |

## R02-O2 — dedicated recommendation screen

- **What exists:** `AiDoctorRecommendationScreen` (`/patient/ai-recommendations`), which calls `/ai/recommendations` (`recommendation_engine.py`).
- **History:** commit `509bca2` (2026-11-09, "unify all healthcare AI features under single assistant entry point") pointed Find Doctor's "AI Doctor Finder" button at the unified AI assistant on purpose; no screen has navigated to the dedicated screen since.
- **Decision:** dormant legacy screen. The supported path is Find Doctor → AI Doctor Finder (or the dashboard's Start AI Consultation) → the unified assistant, which uses the trusted doctor search. No navigation was added, so no second recommendation path exists for users.
- **Verification status:** the `/ai/recommendations` endpoint is covered by automated tests (`test_ai_doctor_recommendations`, `test_i12`). The dedicated screen was **not** opened in R03 and is not reported as UI-verified.

## Limitations

- Emulator only: no physical phone, no iOS, no physical camera.
- No live LLM or Stripe request in R03 (not authorised); earlier phases hold that evidence.
- Push, e-mail and SMS delivery not configured.
- Sinhala and Tamil responses need native-speaker review.
