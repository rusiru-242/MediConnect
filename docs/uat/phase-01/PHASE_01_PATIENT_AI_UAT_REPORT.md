# Phase 01 — Patient AI UAT Report

For: the project owner and independent reviewers. 2026-11-25 · branch `fix/phase-01-patient-ai-ui-stabilization`.

## 1. Environment

- **Backend:** isolated UAT backend on `127.0.0.1:8001`, `ENVIRONMENT=staging`, local MongoDB `mediconnect_uat`, synthetic UAT accounts and doctors, deterministic AI provider, external image processing disabled, Stripe test mode. Port 8000 (the production-like Atlas backend) was not used.
- **Device:** Android 17 (API 37) emulator, debug build with `--dart-define=API_BASE_URL=http://10.0.2.2:8001`.
- **Automated suites:**
  - Backend: pytest against `mongodb://127.0.0.1:27017/mediconnect_test` (the CI configuration).
  - Mobile: Flutter widget tests.

## 2. How the manual observations were reproduced

Every observation in the Phase 01 request was first reproduced against the running UAT API with `phase01_api_probe.py`, before any code change. The output is saved as `api-probe-before.json`. After the fixes, the same probe was re-run and saved as `api-probe-after.json`.

| Manual observation | Reproduced before the fix? | After |
|---|---|---|
| Heart-attack symptom question triggers the emergency banner | **Yes** in the AI Assistant. The Health Chat probe asked it right after a chest-pain message in the same session, so its escalation there was context (correct); the Health Chat fix is covered by a fresh-session API-local test | Information + conditional 1990 |
| "What causes a stroke?" | **Yes** (alarm) | Information |
| "How can I prevent heart disease?" | Not an alarm; gave "share your symptoms" | Prevention information |
| Self-harm detected but shown with the generic banner and 1990 | **Yes** (type `emergency`, no crisis type) | Dedicated mental-health experience |
| Cough guidance tier | **Yes** ("cough > 3 weeks" listed under "Call 1990 now") | Tiered |
| Scenario A context lost | **Yes** (specialty and budget lost) | Kept; Colombo searched |
| Scenario B budget increase | **Yes** (clarification, budget unchanged) | Re-searched with LKR 3000 |
| Scenario C returns two doctors | **Yes** | Exactly one, explained |
| "Select only one doctor…" worked in UAT | **Not reproduced** (it returned a clarification here) | Exactly one |
| Named-doctor slots asks the name again | **Yes** | Doctor with slots for the date |
| Paracetamol information duplicated | **Yes** | Concise intro + card |
| Fabricated "Dr. Alexander Wright" card, Join Call, video badges | **Yes** (in code) | Removed; real appointment or empty state |
| "Prescriptions" label for medication reminders | **Yes** | "Medicine Reminders" |
| Duplicated composer, red screen on Back, lag | Not reproduced with the current branch (fixed in the previous stabilization; re-verified) | 0 framework exceptions on the emulator |

**Newly discovered during reproduction:**
- An overdose ("I accidentally took 10 paracetamol tablets") was **not escalated** and showed the medicine card. This is critical.
- An unverified Sumithrayo hotline number was shown to people in crisis.
- Home SOS listed "911" and did not dial.
- Romanized Sinhala crisis phrases were answered in English.
- An explicit year in dates was ignored.
- A date follow-up created a booking proposal.
- Plural specialties were not recognised.
- The LLM parser was never used for logged-in patients.

## 3. Emulator walkthrough (Phase 01 build)

| Step | Result | Evidence |
|---|---|---|
| Dashboard | No "VITALS: NORMAL", no fabricated appointment, no "Synced 12m ago"; the real UAT booking (Dr. UAT Neuro, 26 Nov, in-person) is shown; Health Tracking card; "Medicine Reminders" | `dashboard-real-appointment-no-fabricated-content.png` |
| Emergency SOS | Dialog: 1990, "Police emergency: 119", no 911; Call → dialer pre-filled with 1990, 0 calls | `sos-dialog-119-police-no-911.png`, `sos-dialer-1990-prefilled-no-call.png` |
| Self-harm message | Purple supportive banner, supportive text, 1926 / 1333 / "In danger now? Call 1990"; keyboard dismissed after send; reply shown from its start | `mental-health-crisis-response.png`, `mental-health-actions-1926-1333-1990.png` |
| 1926 button | Confirmation dialog → dialer pre-filled with 1926, 0 calls | `mental-health-1926-confirmation.png`, `mental-health-dialer-1926-no-call.png` |
| Tap outside the composer | Keyboard dismissed (`mInputShown` true → false) | log |
| Informational heart-attack question | Information with conditional 1990; no banner | `informational-heart-attack-no-banner.png` |
| Scenario C typed on the device | Exactly one doctor, explanation, comparison | `scenario-c-single-doctor-selected.png` |
| Overdose message | Poisoning emergency with category-specific steps | `overdose-poisoning-escalation.png` |
| My Appointments / Find Doctor | "In-person visit" badges, no Join Call, no video filter | `my-appointments-in-person-no-join-call.png` |
| Framework errors during the session | 0 `EXCEPTION CAUGHT`, 0 `Another exception`, 0 overflow (494-line log) | log |

**Testing-process notes:**
- **Keyboard state:** the emulator's on-screen keyboard was in floating mode, so the layout did not resize. Two scripted sends initially tapped stale coordinates, and I first misattributed this to the app. It was a test-script issue. The resulting tap-group hardening is kept and tested.
- **Account:** the app was signed in as the synthetic `uat.patient2` from an earlier session.

## 4. Not covered here

See [PHASE_01_REMAINING_BLOCKERS.md](PHASE_01_REMAINING_BLOCKERS.md). In short:
- No physical phone was used.
- No live LLM or Vision provider was tested.
- Sinhala-script typing on the device was not tested.
- Clinical, pharmacist and native-speaker reviews are outstanding.
