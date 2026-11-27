# R01 — Branding Update Report: MediConnect Logo, Launcher Icon and Splash Screen

For: the project owner and reviewers. 2026-11-28. First release-preparation phase (after A01–A05).

## Outcome

| Item | Result |
|---|---|
| Starting point | `origin/main` `96e6fe7` (PR #27, A05 merged; Backend, Mobile and Admin Web CI succeeded on that merge commit) |
| Branch | `feat/mediconnect-branding` |
| Source of truth | The owner-supplied horizontal logo, stored unchanged as `branding/source/mediconnect_logo_source.png` (2172×724 RGBA, transparent background; SHA-256 `b350a505…485a`) |
| How assets were made | `branding/generate_brand_assets.py` crops, resizes and pads the source. Nothing is redrawn and aspect ratios are kept. The only recolour is the navy wordmark in the dark full-logo variant, made white so it stays readable |
| Mobile | One shared widget (`MediConnectLogo`) now draws the symbol instead of a generic shield icon. All 12 existing placements switched to it automatically; the doctor registration header gained it |
| Splash | The Android 12+ system splash shows the symbol. The Flutter splash shows the symbol, the existing title and the tagline "Intelligent Healthcare. Connected Workflows.", and follows the in-app theme. iOS launch image updated |
| Launcher icon | Android: legacy icons plus adaptive icon (white background, symbol in the 66 dp safe zone, monochrome layer for themed icons). iOS: all AppIcon sizes. Label "mediconnect" → "MediConnect" (package id and signing unchanged) |
| Admin web | Symbol in the login card, sidebar brand area and both full-screen loading states. Real favicons replace the missing `/vite.svg` |
| Scope kept | No change to backend, AI agents, schemas, payments, booking, prescriptions, fraud, support or authentication logic. Avatars untouched. No global colour change |
| Tests | Flutter 342 passed (333 + 9 new); analyze clean; debug APK built. Admin 47 passed (44 + 3 new); tsc, lint and build OK. Backend not modified: focused A05 smoke 27/27 |

## Logo asset variants

| Variant | File | Size |
|---|---|---|
| Original source (unchanged) | `branding/source/mediconnect_logo_source.png` | 2172×724 |
| Symbol only (heart, ECG, cross, orbit; no wordmark) | `branding/exports/mediconnect_symbol.png` | 509×398, transparent |
| Full horizontal logo for light backgrounds | `branding/exports/mediconnect_logo_full_light.png` | 1786×398, transparent |
| Full horizontal logo for dark backgrounds (navy wordmark → slate-100) | `branding/exports/mediconnect_logo_full_dark.png` | 1786×398, transparent |
| Previews of both full variants | `branding/exports/preview_full_on_{light,dark}.png` | 1200×326 |
| High-resolution app icon | `branding/exports/mediconnect_app_icon_1024.png` | 1024×1024, opaque white |
| Flutter symbol (1x, 3.0x, 4.0x) | `mobile/assets/branding/[3.0x/|4.0x/]mediconnect_symbol.png` | 264 / 396 / 509 px wide |
| Android legacy launcher | `res/mipmap-{m..xxxh}dpi/ic_launcher.png` | 48–192 px, white rounded square |
| Android adaptive foreground / monochrome | `res/mipmap-*/ic_launcher_{foreground,monochrome}.png` + `mipmap-anydpi-v26/ic_launcher.xml` | 108–432 px |
| Android 12+ splash icon | `res/drawable-nodpi/splash_icon.png` | 864×864, symbol inside the 192/288 dp circle |
| Android pre-12 launch symbol | `res/drawable-*/launch_symbol.png` | 112 dp wide |
| iOS AppIcon set (all 15 entries) | `ios/Runner/Assets.xcassets/AppIcon.appiconset/` | 20–1024 px, opaque |
| iOS launch image | `ios/Runner/Assets.xcassets/LaunchImage.imageset/` | 120 pt wide (1x/2x/3x) |
| Admin in-app symbol | `admin-web/src/assets/brand/mediconnect-symbol.png` | 168×131 (hashed into `dist/assets` at build) |
| Admin favicons | `admin-web/public/favicon.ico` (16/32/48), `favicon-16x16.png`, `favicon-32x32.png`, `apple-touch-icon.png` (180) | |

Shipped image assets total about 1.2 MB:
- Flutter in-app symbol variants: 256 KB (the largest single file, the 4.0x symbol, is 125 KB).
- Android icon and splash resources: 513 KB.
- iOS icon and launch images: 401 KB.
- Admin web: 46 KB (the symbol is 22.8 KB in the production build).

The source and exports in `branding/` take a further 1.5 MB. They are kept for future use and are not bundled into either app.

## Placements

### Mobile (Flutter)

| Screen | Before | After |
|---|---|---|
| Android launcher | Default Flutter logo, label "mediconnect" | MediConnect symbol (adaptive), label "MediConnect" |
| Native splash (Android 12+) | Flutter logo on white | MediConnect symbol on white |
| Flutter splash / loading screen | Blue shield tile, "Your Health, Connected." | Symbol (112 dp), "MediConnect", "Intelligent Healthcare. Connected Workflows.", small spinner; light or dark per the in-app theme |
| Welcome | Shield tile above "MediConnect" | Symbol above the same title |
| Patient and doctor login (shared screen) | Shield tile (48) | Symbol (64) above the same title |
| Create account, forgot / reset password, OTP, email verification, admin-blocked | Shield tile | Symbol (same widget, same sizes) |
| Patient dashboard header | Shield tile (28) beside "MEDICONNECT / Patient Dashboard" | Symbol (34) beside the same text |
| Doctor dashboard header | Shield tile (26) beside "MEDICONNECT / Doctor Dashboard" | Symbol (34) beside the same text |
| Patient profile header | Shield tile (26) beside "Profile" | Symbol (34) beside the same text |
| Doctor registration | Title text only | Symbol (30) beside "Doctor Registration" (ellipsis-safe) |

The symbol is decorative to screen readers by default (`excludeFromSemantics`), because the name is always shown as text next to it. A `semanticLabel` can be passed where that is not the case. Patient and doctor avatars, the doctor's practice icon and every clinical, emergency and payment colour are unchanged.

### Admin web

| Place | Before | After |
|---|---|---|
| Login card | Blue shield tile above "MediConnect Admin" | Symbol above the same title |
| Sidebar brand area | Blue shield tile beside "MediConnect / Administration" | Symbol beside the same text |
| Full-screen loading ("Loading MediConnect Admin…", "Verifying administrative credentials…") | Spinner only | Symbol above the spinner |
| In-layout module loading | Spinner beside the sidebar | Unchanged; the sidebar already shows the brand |
| Browser favicon | `/vite.svg`, which does not exist: the dev server and the Vercel rewrite both answer with `index.html`, so no icon was shown (R01-BUG-001) | `favicon.ico` + 16/32 PNG + 180 apple-touch icon |
| Document title | "MediConnect — Administration Portal" | Unchanged; `application-name` meta added |

The sidebar has no collapsed mode, only the mobile off-canvas drawer. The brand was checked in that drawer at 390 px width: no horizontal overflow.

## Changed files

| Area | Files |
|---|---|
| Brand source and generator | `branding/source/mediconnect_logo_source.png`, `branding/generate_brand_assets.py`, `branding/exports/*` |
| Flutter code | `lib/widgets/mediconnect_logo.dart` (image instead of icon tile), `lib/screens/splash_screen.dart` (tagline, theme-aware colours, 112 dp symbol; the routing and auth initialisation are untouched), sizes only in `login_screen.dart`, `patient_home_screen.dart`, `doctor_home_screen.dart`, `patient_profile_screen.dart`; header in `doctor_registration_screen.dart`; `pubspec.yaml` (assets) |
| Android | `AndroidManifest.xml` (label), `res/values/colors.xml`, `res/values-v31/styles.xml`, `res/drawable{,-v21}/launch_background.xml`, `res/mipmap-anydpi-v26/ic_launcher.xml`, icon and splash PNGs |
| iOS | `Info.plist` (display name "Mediconnect" → "MediConnect"), `LaunchScreen.storyboard` (image size), AppIcon and LaunchImage PNGs |
| Admin | `src/components/common/BrandMark.tsx` (new), `Sidebar.tsx`, `LoginPage.tsx`, `App.tsx`, `index.html`, `public/` favicons, `src/assets/brand/` |
| Tests | `mobile/test/screens/r01_branding_test.dart` (new, 9), `mobile/test/widget_test.dart` (tagline expectation), `admin-web/src/test/r01Branding.test.tsx` (new, 3) |
| Docs and UAT scripts | `docs/uat/release-preparation/r01/` |

## Findings

| ID | Type | Finding | Action |
|---|---|---|---|
| R01-BUG-001 | Defect (pre-existing), **fixed** | The admin favicon pointed to `/vite.svg`, which was never in `public/`. The server answered with HTML (`text/html`), so browsers showed no icon. Captured by the before run (`B02 FAIL`) | Real favicon set; covered by `r01Branding.test.tsx` and the after run (`B02 PASS`, `image/x-icon`, `image/png`) |
| R01-O1 | Observation (pre-existing, not R01) | At 360 dp width the patient bottom navigation's "Profile" item overflows by 15 px (`r01_after_e14_small_patient_dashboard_dark.png`). R01 changes nothing in the navigation bar | Carry forward to UI polish |
| R01-O2 | Observation (pre-existing) | Welcome and login use fixed light colours. With the in-app dark theme on, the background stays light, the language chips turn dark, and the "Create Account" outlined button's text is barely visible (`r01_after_e15/e16`). The logo itself reads correctly | Carry forward. Fixing it is a screen redesign, outside R01 |
| R01-O3 | Observation (pre-existing) | The splash waits at least 1.2 s (`Future.delayed(1200 ms)` beside the session check). R01 did not add it and kept it, to avoid changing the startup and authentication sequence | Recommend removing the minimum in a later phase |
| R01-O4 | Design decision | The native splash is white in light and dark system modes. The app's dark mode is an in-app setting (default light) and is not read before Flutter starts. A system-dark native splash would therefore flash dark before a light app. Users who chose dark in the app see white → dark | Documented |
| R01-O5 | Limitation | The source is a raster. The symbol region is 509×398, so the 1024 iOS icon and the 864 px Android 12 splash icon are upscaled (about 1.4× and 1.1×). Smaller sizes are downscaled from the source | A vector (SVG/AI) master from the designer would remove this |
| R01-O6 | Limitation | At 16 px on dark tab strips the favicon has low contrast (`r01_after_b02`, `b08`) | Acceptable; a white-outlined small-size variant is possible later |
| R01-O7 | Platform | iOS icons, launch image, storyboard size and display name were updated but not built or run: there is no macOS/Xcode environment | Not verified on iOS |
| R01-O8 | Process note | The first R01 APK was built without `--dart-define=API_BASE_URL=http://10.0.2.2:8001`, so it used its built-in default and could not reach the UAT backend. The doctor session then fell back to the cached offline path and showed "Application Pending". This was a build-command error, not an app defect; it disappeared with the correct build. The affected screenshot was deleted | UAT APKs must be built with the dart-define |

**Carried forward:** A05-O1 (hard-coded patient Profile health data, including "Allergies: Penicillin") is still open. It must be resolved in R02. Branding does not resolve any security or clinical blocker.
