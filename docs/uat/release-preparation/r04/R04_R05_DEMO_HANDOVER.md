# R04 → R05 Demonstration Handover

For: whoever prepares and records the R05 automated demonstration video. 2026-11-28. Based on `R03_DEMO_READINESS_CHECKLIST.md`, updated with R04 checks. **No video was recorded in R04.**

## 1. Authorisations to obtain first (R05-specific)

| Item | Needed for | Default without authorisation |
|---|---|---|
| Live Gemini text (with a call cap) | Showing a live LLM rephrasing or intent proposal | Deterministic engine (already shows the full agentic flow) |
| Gemini Vision | Medicine package analysis live | Use the recorded A01 result screenshot, or skip |
| Stripe test-mode calls | Showing the PaymentSheet and a confirmed payment | Stop at the reservation hold, or show the recorded A03 screenshot |
| Recording the screen with synthetic accounts | The whole video | — |

**Earlier authorisations (A01 and A03) do not carry over to R05.**

## 2. Startup (verified in R03/R04)

```powershell
# 1. MongoDB running on 127.0.0.1:27017
# 2. Backend (UAT, deterministic, port 8001)
powershell -ExecutionPolicy Bypass -File backend\scripts\start_uat_backend.ps1 -SkipSeed
#    with authorisation only: -AiProvider gemini -AiDailyLimit 60 [-EnableVision]
# 3. Admin web, kept local
cd admin-web; npm run dev -- --host 127.0.0.1
# 4. Emulator (Pixel 7 Pro image used in R01-R04) + the R04 demonstration APK
adb install -r MediConnect-v1.0.0-academic\android\MediConnect-v1.0.0-academic-emulator-debug.apk
```

**Health check:** `http://127.0.0.1:8001/health` should show `isolatedTestData: true`.

## 3. Synthetic accounts and fixtures

All on `@uat.mediconnect.lk`, with the password from the git-ignored `backend/uat.env`. **Never show it on screen.**

| Account | Use | Fixture state (2026-11-28) |
|---|---|---|
| `uat.patient2` | Profile with a synthetic picture, health summary | Picture uploaded in R03; confirmed appointments with Dr. UAT Neuro |
| `uat.p02.patientc` | Booking flow (cardiology) | Doctors Dr. UAT Cardio One (LKR 2,000, rating 4.7 from 3 reviews) and Two (LKR 3,500) |
| `uat.p02.patientb` | Multilingual and payment demonstrations (A03) | — |
| `uat.p03.patienta` | Prescriptions, renewal, reminders | Renewed prescription `RX-REN-20261128-2DD56A` with a reminder; more pending renewals |
| `uat.doctor.neuro` | Doctor dashboard with picture | Picture uploaded in R03 |
| `uat.p03.doctor.alpha` | Renewal queue and clinical workflows | Pending renewal requests from P03 Patient A |
| `uat.admin` | Admin web | Fraud reviews, support tickets, payments from earlier phases |

**Notes:**
- UAT data has accumulated across phases (R03-O1). For a clean video, consider re-seeding with authorisation, or choose accounts carefully.
- Reserved slots expire; cancel test holds after recording.

## 4. Strongest verified agentic AI scenarios

| # | Scenario | Prompt(s) | Screen | Evidence |
|---|---|---|---|---|
| 1 | Multilingual doctor search | `mata Colombo walin hoda cardiologist kenek hoyala denna` (romanised Sinhala) → Sinhala reply with cards | MediConnect AI Assistant | R04 screenshot `04_multilingual_assistant` |
| 2 | Contextual search | `Find me a cardiologist in Colombo.` | AI Assistant, doctor cards | R03 Workflow A A01 |
| 3 | Budget refinement with memory | `Only doctors with a fee under 3000 rupees.` (specialty and city kept) | AI Assistant | A02 |
| 4 | Remembered doctor selection and real slots | `Select the first doctor.` → `Show me the available slots tomorrow.` | AI Assistant, slot chips | A03 |
| 5 | Explicit booking confirmation | `Book <date> at <time>.` → Booking Summary → **Accept & Continue** | Booking Summary card | A03–A06; screenshot `06_booking_summary` |
| 6 | Trusted tool execution and refusals | `Prescribe me amoxicillin 500 mg` (declined), `Approve my refund` (refused), `Book Dr. Gregory House in Colombo` (no invented doctor) | AI Assistant | R03 S04, S06, S09 |
| 7 | Emergency first | `I have crushing chest pain spreading to my left arm` | AI Assistant emergency card | S01 |
| 8 | Clinician-controlled prescriptions | Doctor: Prescription renewals → Approve (dialog shows original instructions); patient: prescription → Set Reminder (locked dose) | Prescription Renewal Queue, Digital Prescription, New Medication Reminder | R03 `r03_e18`–`r03_e25` |
| 9 | Admin human-in-the-loop | Fraud Risk Center → Review (no automatic action); Customer Support → Respond | Admin web | R04 `15_fraud_review`, `16_support_queue` |

## 5. Automation available

| Tool | Path | Notes |
|---|---|---|
| Emulator driver | `docs/uat/release-preparation/r03/emu.py` (`focus`, `dump`, `tap`, `tapt`, `type`, `password`, `key`, `shot`) | Refuses input unless MediConnect is in the foreground; reads a fresh UI dump every time |
| Login helper | `docs/uat/release-preparation/r03/login.sh <email> [patient\|doctor]` | Types the password from `uat.env` without printing it |
| Field filler | `docs/uat/release-preparation/r03/fill.py "<exact hint>" "<text>"` | ASCII only (adb input cannot type Sinhala script; use romanised Sinhala) |
| Admin browser | `docs/uat/release-preparation/r03/browser_admin_r03.mjs`, `r04/browser_capture_r04.mjs` | playwright-core with headless Chrome; aborts non-local requests |
| API probes | `r03/r03_workflow_probe.py`, `r03/r03_picture_probe.py` | Deterministic; record provider usage |

**Known automation pitfalls (R02–R04):**
- Back can leave the app; use the in-app Back button at `(98, 242)`.
- Text taps can match headings. Use `tap x y` from a fresh `dump`.
- Android's notification-permission dialog appears after clearing app data.
- The AI send button has no label; it's at `(1320, 2889)` on the 1440×3120 screen.

## 6. Recording restrictions

- **Data:** synthetic accounts and synthetic or abstract images only. No real faces, patient data or medicine photos of real people.
- **Never on screen:** `backend/uat.env`, `.env`, tokens, database URLs, Stripe dashboard keys, the terminal history with secrets.
- **Network:** keep the backend on `127.0.0.1` and the admin dev server on `127.0.0.1`.
- **Claims:** don't present clinical accuracy, SLMC registry verification, push/e-mail/SMS delivery, OpenAI generation or the dormant dedicated recommendation screen as working features.
- **Title card:** state "academic demonstration, synthetic data, not for clinical use".
