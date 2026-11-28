# R02 — UI Corrections Report

For: the project owner and reviewers. Records the R01 observations corrected in R02 and the status of the rest.

## R01-O1 — Patient bottom navigation overflow (R02-BUG-003): RESOLVED

| | Before | After |
|---|---|---|
| 360 dp | "Profile" overflowed by 15 px; yellow-and-black overflow stripe (R01 `r01_after_e14`) | All four items fit (`r02_after_e29_nav_360dp`) |
| 320 dp | Not tested in R01 | Fits (`r02_after_e30_nav_320dp`) |
| 320 dp, system text 1.3× | — | Fits; long labels scale down instead of overflowing (`r02_after_e31`) |
| Standard large viewport (412 dp) | Fitted | Fits (widget test) |

**Change:**
- Each item takes an equal share of the bar (`Expanded`).
- Each label is a single line inside `FittedBox(scaleDown)`.
- Each item is one accessible button with a 48 dp minimum height.

All four destinations (Home, My Appointments, Find a Doctor, Profile) and their navigation are unchanged.

**Tests:** five widget tests (320/360/412 dp at 1.0×, and 320/360 dp at 1.3×) check that labels stay on screen and that no overflow comes from the navigation.

## R01-O2 — Dark-mode welcome and login (R02-BUG-004): RESOLVED

| | Before (R01 `e15`/`e16`) | After (`r02_after_e32`/`e33`) |
|---|---|---|
| Background | Light in dark mode | Dark (`AppTheme.darkBackground`) |
| Title and subtitle | Dark text | Light text (`darkTextPrimary` / `darkTextSecondary`) |
| Language chips | Dark chips on a light page | Readable outlined chips on dark |
| "Create Account" outlined button | Text nearly invisible | Readable (contrast above 4.5:1, tested) |
| Login fields and role tabs | Dark fields on a light page | Dark surfaces, readable labels |
| Logo | Visible | Visible |

**Change:** `lib/core/theme/auth_palette.dart` maps the fixed light colours to the existing dark tokens; only colours changed. Light mode keeps its exact previous colours (tested). Layout, validation and navigation are unchanged.

## Other R01 observations

| ID | Status in R02 |
|---|---|
| R01-O3 (1.2 s minimum splash) | Not changed. It is optional, and R02 avoided touching startup and session restoration |
| R01-O4 (white native splash in both modes) | Not changed; documented design choice |
| R01-O5 (raster logo upscaling) | Not changed; accepted limitation |
| R01-O6 (16 px favicon contrast on dark tabs) | Not changed; optional |
| R01-O7 (no iOS runtime) | Still applies. R02 added iOS camera and photo usage strings, which were not runtime-verified |
| R01-O8 (UAT build command) | Not repeated: the R02 APK was built with `--dart-define=API_BASE_URL=http://10.0.2.2:8001` |

## UI matrix

| ID | Scenario | Evidence | Result |
|---|---|---|---|
| R02-U01 | Patient navigation at 320 dp | Device `e30`, `e31` (1.3×); widget tests | PASS |
| R02-U02 | Patient navigation at 360 dp | Device `e29`; widget tests | PASS |
| R02-U03 | Standard viewport | Device 1440×3120 (all other shots); widget 412 dp | PASS |
| R02-U04 | Light-theme login | Widget U04 (exact previous colours); device logins throughout | PASS |
| R02-U05 | Dark-theme login | Device `e33`; widget U05/U06 | PASS |
| R02-U06 | Dark-theme welcome | Device `e32`; widget U05/U06 (Create Account contrast > 4.5:1) | PASS |
| R02-U07 | Logo vs profile avatar | Widget U07 (both present, separate); device: the profile and dashboard headers keep the MediConnect logo while avatars change | PASS |
| R02-U08 | R01 branding preserved | `r01_branding_test.dart` and `widget_test.dart` pass in the full suite; logo visible on every R02 screenshot | PASS |
