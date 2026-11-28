# R03 — UI and UX Verification

For: the project owner and reviewers. 2026-11-28. Android emulator (1440×3120, debug APK for `10.0.2.2:8001`) and the admin web in headless Chrome (1440×950). All screenshots are genuine captures with synthetic accounts and synthetic images, under `evidence/emulator/` and `evidence/browser/`. Before every input, `emu.py` checks that MediConnect is in the foreground; R03 also made it delete the previous UI dump before reading a new one, after a stale dump misreported the screen once.

## Mobile

| Screen | Screenshot | Theme | Result |
|---|---|---|---|
| Launcher icon | `r03_e00_launcher_icon` | — | PASS (R01 icon) |
| Splash | `r03_e01_splash` | Light (native white splash, R01 design) | PASS |
| Welcome | `r03_e02_welcome_light`, `r03_e14_welcome_dark` | Light, dark | PASS |
| Login | `r03_e15_login_dark` | Dark | PASS (readable fields, chips, Create Account) |
| Patient dashboard | `r03_e03`, `r03_e12_patient_dashboard_dark` | Light, dark | PASS |
| Patient profile | `r03_e04`, `r03_e13_patient_profile_dark` | Light, dark | PASS (only stored data) |
| Profile picture editor | `r03_e05_picture_editor` | Light | PASS (gallery, take a photo, remove, cancel) |
| Find a Doctor | `r03_e06_find_doctor_search` | Light | PASS (real picture and fee) |
| Doctor details | `r03_e07a…before_fix` → `r03_e07_doctor_details` | Light | **FAIL → fixed** (R03-BUG-003: invented 4.9 rating and "Top Ranked Specialist" banner) |
| AI Assistant with doctor card | `r03_e08_ai_assistant_doctor_card` | Light | PASS |
| My Appointments | `r03_e09_my_appointments` | Light | PASS |
| Emergency SOS | `r03_e10_emergency_sos_dialog` | Light | PASS (confirmation before the dialer) |
| Medication reminders | `r03_e10_medication_reminders_empty`, `r03_e23`–`r03_e25` | Light | PASS (truthful empty state; locked prescribed values) |
| Help and Support | `r03_e11_help_support` | Light | PASS (truthful empty state) |
| Doctor dashboard | `r03_e16_doctor_dashboard_dark` | Dark | PASS with minor issue R03-O2 (low-contrast stat labels) |
| Renewal queue and approval | `r03_e17`–`r03_e20` | Dark | PASS |
| Prescriptions | `r03_e21`, `r03_e22` | Light | **Fixed** (R03-BUG-004: false SLMC and tamper-evident claims) |

**Width and text scaling:** the 320/360/412 dp and 1.3× text checks of the patient navigation and the dark welcome/login checks are automated widget tests (R02 U01–U06). They are part of the final Flutter run (362 passed). R03 did not repeat the narrow-width device resizing done in R02.

## Admin web

| Screen | Screenshot | Result |
|---|---|---|
| Login, role refusal | `r03_b14_patient_account_refused` | PASS |
| Branding and sidebar | visible in every page screenshot (MediConnect Administration logo, operations menu) | PASS |
| Dashboard, doctors, verification, appointments, payments, refunds, reconciliation, fraud, support, monitoring, audit, analytics, reports | `r03_b01`–`r03_b13` | PASS (no errors; doctor avatar 32×32; "No reviews yet" shown truthfully) |

## Truthfulness

- **Invented data found and removed in R03:** doctor rating and banner (R03-BUG-003), verification claims on prescriptions (R03-BUG-004).
- **Empty states are truthful:** no reminders, no tickets, no reviews.
- **No fabricated medical data** on any captured screen.

## Limitations

- Minor cosmetic issues are left documented: R03-O2 (dark-mode stat labels), plus R01-O3 to O6 unchanged.
- Emulator only; no physical phone, no iOS.
