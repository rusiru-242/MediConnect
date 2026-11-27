# R01 — Visual Verification

For: the project owner and reviewers. All screenshots are real captures. Mobile shots come from the Android emulator (Pixel 7 Pro AVD, Android API 37, 1440×3120 px at 560 dpi), taken with `adb screencap`. Admin shots come from the locally installed Chrome, driven by `browser_admin_branding_r01.mjs`. Every capture uses the local UAT backend (`127.0.0.1:8001`, `mediconnect_uat`) and synthetic accounts only. Before shots were taken on `main` `96e6fe7` (the A05 build); after shots on the R01 branch.

## Mobile (`evidence/emulator/`)

| Check | Before | After | Result |
|---|---|---|---|
| Android launcher icon (app drawer + zoom) | `r01_before_e01`, `e01b`: Flutter logo, "mediconnect" | `r01_after_e01`, `e01b`: MediConnect symbol inside the circular adaptive mask, "MediConnect" | PASS: symbol fully inside the mask, not clipped, legible at launcher size |
| Native splash (Android 12+) | `r01_before_e02`: Flutter logo | `r01_after_e02`: MediConnect symbol, white background | PASS: the system splash ends when Flutter draws its first frame; no extra delay added |
| Flutter splash / loading screen | `r01_before_e03`: shield tile, "Your Health, Connected." | `r01_after_e03`: symbol, "MediConnect", "Intelligent Healthcare. Connected Workflows.", spinner | PASS: proportions kept, no duplicated wordmark |
| Flutter splash, dark in-app theme | — | `r01_after_e12_flutter_splash_dark` | PASS: dark background, light text, symbol readable |
| Welcome | `r01_before_e04` | `r01_after_e04` | PASS |
| Patient login | `r01_before_e06` | `r01_after_e06` | PASS: symbol above the unchanged title; fields shift down about 16 dp; nothing clipped |
| Doctor login (Doctor tab) | `r01_before_e07` | `r01_after_e07` | PASS |
| Patient dashboard header | `r01_before_e05` | `r01_after_e05` | PASS: symbol beside "MEDICONNECT / Patient Dashboard"; notification badge, settings and logout untouched |
| Patient dashboard, dark theme | — | `r01_after_e11` | PASS: symbol readable on the dark app bar; Emergency SOS keeps its red treatment |
| Doctor dashboard header | `r01_before_e08` | `r01_after_e08` | PASS: symbol beside "MEDICONNECT / Doctor Dashboard"; doctor avatar (practice icon) unchanged |
| Settings sheet (theme switch used for the dark shots) | — | `r01_after_e10` | Context only |
| Doctor registration header | — | `r01_after_e17` | PASS: symbol beside "Doctor Registration", back and language buttons unaffected |
| Small viewport (720×1280 px at 320 dpi = 360×640 dp, set temporarily with `wm size`/`wm density`, then reset) | — | `r01_after_e13` native splash, `e14` dashboard (dark), `e15` welcome, `e16` login | PASS for branding: no clipping or overlap. Two pre-existing issues are visible and recorded: R01-O1 (bottom-nav overflow) and R01-O2 (welcome/login not dark-aware) |
| Session restore after a cold start | — | Doctor and patient sessions reopen on their dashboards after the splash | PASS (the auth sequence is unchanged) |

## Admin web (`evidence/browser/`, run results in `evidence/r01_browser_{before,after}.json`)

| Check | Before | After | Result |
|---|---|---|---|
| Login (1440×950) | `r01_before_b01`: shield tile | `r01_after_b01`: symbol above "MediConnect Admin" | PASS |
| Favicon (declared icons fetched and drawn at tab sizes on light and dark strips) | `r01_before_b02`: `/vite.svg` returned `text/html`, **B02 FAIL** | `r01_after_b02`: `favicon.ico` `image/x-icon`, 32/16 PNG, apple-touch, **B02 PASS** | PASS; low contrast at 16 px on dark strips (R01-O6) |
| Real Chrome tab strip (visible Chrome window, desktop capture) | — | `r01_after_b08_chrome_tab_favicon` | PASS: the MediConnect symbol is shown in the tab |
| In-layout module loading (dashboard module delayed 3 s) | `r01_before_b03` | `r01_after_b03` | PASS (unchanged by design; the sidebar shows the brand) |
| Full-screen route loading (lazy route delayed 3 s) | `r01_before_b03b`: spinner only | `r01_after_b03b`: symbol above the spinner | PASS |
| Dashboard with sidebar and header | `r01_before_b04` | `r01_after_b04` | PASS: charts, cards and navigation unchanged |
| Sidebar brand zoom | `r01_before_b05` | `r01_after_b05`: rendered 40×36, natural 168×131 (about 4× density) | PASS: no distortion |
| Mobile width 390 px: login and the opened off-canvas sidebar | `r01_before_b06`, `b07` | `r01_after_b06`, `b07` | PASS: horizontal overflow 0 |
| Requests to hosts other than the local app and backend | 0 | 0 | PASS |
| Page errors | 0 | 0 | PASS |

## Proportions and duplication

- Every placement uses the symbol only. The wordmark is never drawn as an image, so "MediConnect" appears once per screen as existing text. This is asserted in the Flutter and admin tests.
- Images are shown with `BoxFit.contain` (Flutter) and `object-contain` (admin) inside their boxes, so they are never stretched. The asset ratio is 509:398 everywhere.
- No shadow, gradient tile or other effect is added around the symbol.

## Not verified

- **iOS:** no macOS or Xcode environment, so no iOS build or runtime check (R01-O7).
- **Physical Android phone:** emulator only.
- **Themed (monochrome) launcher icons on Android 13+:** the layer is provided but was not switched on in the emulator launcher.
- **Before shots in the dark theme:** none were captured, so dark-theme results are after-only.
