# R04 — Build Verification

For: the project owner and reviewers. 2026-11-28. Built from `release/mediconnect-v1` at `main` `1f95285` (R03 merge). R04 changed no application code; every check below was run in R04.

## Android demonstration APK

| Item | Value |
|---|---|
| Build type | **Debug**, for the **Android emulator only**. Not a signed production release |
| Command | `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001` |
| Version | `versionName 1.0.0`, `versionCode 1` (`mobile/pubspec.yaml` `1.0.0+1`; unchanged); package `com.mediconnect.mediconnect` (unchanged); minSdk 24, targetSdk 36 |
| Output | `mobile/build/app/outputs/flutter-apk/app-debug.apk` (not committed) |
| Packaged copy | `C:\Users\REDTECH\Downloads\MediConnect-v1.0.0-academic\android\MediConnect-v1.0.0-academic-emulator-debug.apk` |
| Size | 257,233,513 bytes |
| SHA-256 | `ca477aab1df01c020d913aa309e4f2b7402593174fb4042b2fe0bf4ebf208357` |
| API configuration | `API_BASE_URL=http://10.0.2.2:8001` (the emulator's alias for the host's local UAT backend); it takes priority over the built-in host candidates |
| Signing | No `android/key.properties` or keystore exists; no signed release was built and no signing material was created |
| Pre-build check | `flutter analyze`: no issues |
| Install | `adb install -r`: Success; `pm clear` for a clean first launch |
| Launch | MainActivity in front; no crash in logcat; welcome screen after start-up (`evidence/emulator/r04_apk_first_launch_welcome.png`) |
| Backend connectivity | Signed in as `uat.patient2`: Patient Dashboard loaded from `10.0.2.2:8001` |
| Content | R01 launcher icon and splash; R02 profile pictures; R03 fixes (no invented rating; truthful prescription wording; no sample credential documents in release builds) — all in the merged code at `1f95285` |

### APK content scan (all 1,498 entries)

| Check | Result |
|---|---|
| Secret keys, webhook secrets, AI keys, private keys, JWTs, database URIs with credentials | **None** |
| UAT password | Not present |
| Database names or hosts | None |
| Stripe publishable key | **One test-mode publishable key (`pk_test_…`)** compiled in as the default of `STRIPE_PUBLISHABLE_KEY` (`mobile/lib/core/constants/api_constants.dart` line 435, since `966fd18`). Publishable keys are meant for client apps and grant no secret access; it is reported as informational. Recommended: supply it with `--dart-define` and rotate it together with the Stripe test keys |
| Local URLs | `10.0.2.2:8001` (configured); developer host candidates on port 8000 and two private LAN addresses (`192.168.x.x`), used only by auto-detection and the debug server-settings sheet when no `API_BASE_URL` is set |

## Admin web build

| Item | Value |
|---|---|
| Commands | `npm run typecheck` (exit 0) · `npm run lint` (clean, `--max-warnings 0`) · `npx vitest run` (**14 files, 51 tests passed**) · `npm run build` (built in 6.6 s) |
| Output | `admin-web/dist/` (44 files, about 1.2 MB; not committed) |
| Archive | `C:\Users\REDTECH\Downloads\MediConnect-v1.0.0-academic\admin-web\mediconnect-admin-web-dist.zip`, 354,975 bytes, SHA-256 `0fa594c49ef8e8a3dc64306df01b7241f883f0029c2a256c668e86cf036a80a6` |
| Secret scan of `dist/` | None. URLs present: `http://127.0.0.1:8001/api` (the development default in the client code) and `http://localhost` |
| Local startup | `vite preview` on `127.0.0.1:4173`: `/login` 200, favicon 200 (`image/x-icon`), title "MediConnect — Administration Portal", logo image loaded, 0 page errors, 0 external requests (`evidence/browser/r04_b03_admin_build_preview_login.png`). Preview stopped afterwards |
| Deployment | None |

## Other R04 checks

| Check | Result |
|---|---|
| R03 post-merge backend smoke (`test_r03_final_verification.py`, `test_r02_profile.py`, `test_a05_fraud_support.py`, `test_phase05_emergency.py`) on a fresh local `mediconnect_r04smoke_test` | **100 passed**; provider-connection detector 0 attempts |
| R03 post-merge Flutter smoke (`doctor_reviews_test`, `a04_prescription_test`, `r02_profile_test`, `r01_branding_test`) | **40 passed** |
| Documentation links (`check_links.py`, 6 documents) | 50 links checked, 0 broken (`evidence/r04_link_check.json`) |
| Screenshot review | 16 selected screenshots inspected; synthetic data only; no tokens, credentials, database details or unrelated desktop content; masked e-mail and phone in the booking summary |

**Newly executed automated tests in R04:**
- backend 100 + Flutter 40 + admin 51 = **191**, all passed. These are focused re-runs of existing tests on the merged code, not new test cases.
- The R03 baseline of 1,477 is historical and not re-counted here.
