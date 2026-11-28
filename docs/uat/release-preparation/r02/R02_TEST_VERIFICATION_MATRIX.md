# R02 — Test Verification Matrix

For: the project owner and reviewers. Every count below comes from a command run in R02 on the final working tree, unless it is labelled historical.

## Environment

| Item | Value |
|---|---|
| Backend tests | Local MongoDB on loopback. Final full run on a fresh database, `mediconnect_r02_test` (`_test`, conftest guard). Provider connection detector: A03 `a03_leak_detector.py` (SMTP, Twilio, FCM, OAuth, Stripe API and files, Gemini, OpenAI hosts) |
| UAT backend | `127.0.0.1:8001`, `mediconnect_uat`, synthetic accounts. AI deterministic; e-mail, push and SMS disabled; Stripe test mode, no payment made |
| Mobile | Emulator `emulator-5554` (Pixel 7 Pro AVD, API 37). APK: `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001` |
| Admin | Vite `127.0.0.1:5174` against `:8001`, in Chrome through `playwright-core`. Every request to any other host is aborted: 0 attempted |

## Automated suites

| Suite | Command | Result in R02 | Previous (historical) |
|---|---|---|---|
| Backend full | `pytest -q -p a03_leak_detector` (fresh DB) | **1,048 passed**, 0 failed. **0 provider connection attempts** | 1,003 (A05 full run); R01 ran only a 27-test smoke |
| Backend R02 | `tests/test_r02_profile.py` | 45 (part of the 1,048) | — |
| Flutter | `flutter test` | **361 passed**, 0 failed (19 new in `r02_profile_test.dart`) | 342 (R01) |
| Flutter analyze | `flutter analyze` | No issues | No issues |
| Android APK | debug build with the UAT dart-define | Built, installed, used for UAT | Built |
| Admin vitest | `npx vitest run` | **51 passed**, 14 files (4 new in `r02DoctorAvatar.test.tsx`) | 47 (R01) |
| Admin typecheck / lint / build | `tsc --noEmit`, `npm run lint` (`--max-warnings 0`), `npm run build` | OK / OK / OK | OK |

**Newly executed in R02: 1,048 + 361 + 51 = 1,460 automated tests passed, 0 failed.** The historical combined baseline was 1,392: backend 1,003 from A05, plus Flutter 342 and admin 47 from R01.

### Backend run history (honest record)

1. **First full run, on the long-lived shared `mediconnect_test` database:** 1,042 passed, 5 failed.
   - **4 A05 fraud tests:** caused by R02-BUG-006. A latent A05 defect that appears once more than 200 accounts are active; reproduced on unchanged `main`; fixed, with a regression test.
   - **1 admin endpoint test:** caused by about 42 future-dated payments left behind by earlier fixture runs (R02-O1, test isolation).
2. **Final run, after the fix, on a fresh database (as CI uses):** 1,048 passed. Details in `evidence/r02_backend_runs.txt`.

## Changed expectations

Two existing Flutter tests: the profile-screen test now asserts the invented "MEDICONNECT PASS" is **absent**, and both inject a fake profile service. No assertion was removed. See `R02_BUG_FIX_REPORT.md`.

## Scenario matrices

| Matrix | Scenarios | PASS | Qualified PASS | FAIL / BLOCKED | Report |
|---|---|---|---|---|---|
| Profile pictures | R02-I01–I24 | 24 | I02 (emulator camera), I10 (removal through the API), I12 (dedicated screen unreachable from the UI, R02-O2), I21–I23 (automated; I23 cannot be triggered because no permission is requested) | 0 | `R02_PROFILE_PICTURE_VERIFICATION.md` |
| Security | R02-S01–S15 | 15 | — | 0 | `R02_IMAGE_STORAGE_SECURITY_REPORT.md` |
| Profile data | R02-P01–P10 | 10 | — | 0 | `R02_PROFILE_DATA_INTEGRITY_REPORT.md` |
| UI | R02-U01–U08 | 8 | — | 0 | `R02_UI_CORRECTIONS_REPORT.md` |
| **Total** | **57** | **57** | 6 qualified | **0** | |

## Evidence index (`evidence/`)

| File | Content |
|---|---|
| `emulator/r02_before_e01–e03` | The old Profile screen on the R01 build (invented data) |
| `emulator/r02_after_e01–e33` | Patient profile, photo sheet, system picker, adjust, upload, camera, edit/save, restart, doctor flows, search, details, booking summary, appointments, AI card, replacement, removal, navigation at 360/320 dp and 1.3× text, dark welcome and login |
| `browser/r02_{with_photo,replaced,removed}_b01–b03` + `r02_browser_admin_*.json` | Admin doctor list, row zoom and verification queue in each state |
| `r02_stored_*.jpg` | The pictures exactly as stored (synthetic shapes and the emulator scene), downloaded through the API |
| `r02_uat_visibility_probe.jsonl` | Live visibility checks between synthetic accounts |
| `r02_backend_restart_persistence.txt` | SHA-256 of both pictures before and after a backend restart |
| `r02_backend_provider_attempts.json` | Provider connection attempts in the final backend run: 0 |
| `r02_backend_runs.txt` | Summary of the backend runs |

UAT scripts: `emu.py` (emulator driver with a foreground-app guard), `login.sh`, `fill.py`, `r02_api_probe.py`, `browser_admin_r02.mjs`, `make_results.py`.
