# R01 — Test Results

For: the project owner and reviewers. Every number below comes from a command run in this phase on the R01 working tree, unless it is labelled as a previous result.

## Summary

| Suite | Command | Result in R01 | A05 baseline |
|---|---|---|---|
| Flutter tests | `flutter test` (mobile/) | **342 passed**, 0 failed (9 new in `test/screens/r01_branding_test.dart`) | 333 |
| Flutter analyze | `flutter analyze` | **No issues found** | clean |
| Android debug APK | `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001` | **Built**, installed on the emulator with `adb install -r` | built |
| Admin vitest | `npx vitest run` (admin-web/) | **47 passed**, 0 failed, 13 files (3 new in `src/test/r01Branding.test.tsx`) | 44 |
| Admin TypeScript | `npx tsc --noEmit` | **OK** | OK |
| Admin lint | `npm run lint` (`--max-warnings 0`) | **OK** | — |
| Admin production build | `npm run build` | **OK** (`dist/assets/mediconnect-symbol-*.png` 22.8 kB, favicons copied) | OK |
| Backend | No backend file changed in R01. Focused smoke: `pytest tests/test_a05_fraud_support.py` on the local `mediconnect_test` database (conftest guard) | **27 passed** | 1,003 (A05, **not re-run** in R01) |
| Live UAT logins (emulator → `10.0.2.2:8001`) | Synthetic patient and doctor login, logout, cold-start session restore | **PASS** | — |
| Admin browser run | `browser_admin_branding_r01.mjs … after` | **6/6 PASS** (B01–B05, B03b), 0 blocked requests, 0 page errors | Before run: B02 FAIL (R01-BUG-001) |

**Executed in R01:** 342 Flutter + 47 admin + 27 backend = **416 automated tests passed, 0 failed.**

The A05 backend total of 1,003 is a previous result and was not re-run, because R01 changes no backend file. CI on the R01 pull request runs only the workflows whose paths changed (mobile and admin web).

## New tests

| File | Tests | What they check |
|---|---|---|
| `mobile/test/screens/r01_branding_test.dart` | 9 | Symbol asset and 3.0x/4.0x variants are bundled. The widget draws the asset with `BoxFit.contain` in a square box and is decorative unless labelled. The spoken label works. The caption follows the dark theme. Login and welcome on a small (320×568) and a large (412×915) phone: exactly one symbol, exactly one "MediConnect" text, the logo on screen, centred and above the title without overlap, no layout error from the logo. The login logo renders in the dark theme |
| `admin-web/src/test/r01Branding.test.tsx` | 3 | Login: one decorative symbol (`alt=""`, `aria-hidden`, `object-contain`) and "MediConnect" text once. Sidebar: symbol beside the title, while the Dashboard link and the close button still work. `index.html` no longer references `/vite.svg`, the title is unchanged, and the four declared icons exist in `public/` |

## Changed expectation

| Test | Change | Why |
|---|---|---|
| `mobile/test/widget_test.dart` (app launch smoke) | Tagline expected "Intelligent Healthcare. Connected Workflows." instead of "Your Health, Connected."; adds an assertion that the logo symbol is present | The tagline was intentionally changed to the one proposed for R01. No assertion was removed; one was added. A missing `material.dart` import, needed for `Key`, was added |

## Layout errors seen only under `flutter test`

Flutter's test font (Ahem) draws every glyph as a full em square. Under test, some long text rows on the login and welcome screens therefore overflow: "Remember me / Forgot Password?", "Don't have an account? Create Account" and, on the 320 px welcome screen, one further text row. These rows are unchanged by R01. So the new tests do not fail on unrelated overflow. Instead they collect layout errors, assert that none comes from `mediconnect_logo.dart`, and check the logo's geometry directly. On the emulator with real fonts these rows do not overflow (`r01_after_e06`, `e16`). The one real overflow seen on a 360 dp screen is the bottom navigation (R01-O1, pre-existing).

## Not run

- The full backend suite (no backend change).
- Any iOS build or test (no macOS).
- Physical-device tests.
