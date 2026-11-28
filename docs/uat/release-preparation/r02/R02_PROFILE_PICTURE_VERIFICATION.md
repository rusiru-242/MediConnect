# R02 — Profile Picture Verification

For: the project owner and reviewers. Workflows implemented for patients and doctors, where pictures appear, and the I01–I24 results.

**Environment:**
- Android emulator: Pixel 7 Pro AVD, API 37.
- APK built with `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001`.
- UAT backend: `127.0.0.1:8001`, `mediconnect_uat`, AI deterministic, e-mail/push/SMS disabled.
- Admin web: Vite `127.0.0.1:5174`, in Chrome.

**Accounts and images:** synthetic accounts `uat.patient2`, `uat.doctor.gp`, `uat.doctor.neuro`, `uat.patient1` and `uat.admin`. Four original abstract images were generated for R02 (shapes and stripes, no people), each carrying fake GPS EXIF and a "R02SyntheticCam" marker so metadata removal can be checked. The camera test used the emulator's virtual scene; no person was photographed.

## Workflows

| Capability | Patient | Doctor |
|---|---|---|
| Where | Profile → tap the avatar | Dashboard → My Profile & Credentials → "Add / Change profile photo" |
| Gallery | Android system photo picker ("MediConnect will only have access to the photos you select"); no storage permission requested | Same |
| Camera | System camera app through `IMAGE_CAPTURE`; MediConnect declares no CAMERA permission | Same |
| Preview and crop | "Adjust photo": a square view with pan and pinch, starting centred; the chosen square is sent as fractions and cropped on the server | Same |
| Upload | Progress bar ("Uploading n%"), then "Profile photo updated." | Same |
| Retry | A failed upload shows the error and "Retry upload"; the previous picture stays | Same |
| Replace | A new upload; the version changes and the old file is deleted | Same |
| Remove | "Remove photo" → confirmation → default avatar | Same (API) |
| Cancel | Closing the sheet, cancelling the picker or cancelling the adjust screen changes nothing | Same |
| Errors | Denied permission, missing camera and unreadable photos give a clear message | Same |
| Shown in | Profile header, dashboard "Profile & Settings" sheet | Dashboard card, profile sheet; patient-facing: search cards, doctor details, AI assistant cards, AI recommendation cards, booking summary, booking-assistant candidates, My Appointments, appointment details; admin doctor list, verification queue, application detail |

The MediConnect logo is untouched everywhere (U07). Patient pictures are never shown to other patients: the review list in doctor details keeps its icon.

## Matrix

| ID | Scenario | Evidence | Result |
|---|---|---|---|
| R02-I01 | Patient gallery selection | Device `e03`→`e08`; widget I01 | PASS |
| R02-I02 | Patient camera selection | Device `e10` (system camera, virtual scene) → `e11` → `e12`; stored without GPS | PASS (emulator camera; not a physical camera) |
| R02-I03 | Crop and preview | Device `e05/e06` (panned); stored picture matches the panned square (`r02_stored_patient_a.jpg`); `test_i03` (server crop); widget (centred default crop) | PASS |
| R02-I04 | Patient upload | Device `e07` (progress, "Profile photo updated."), `e08`; `test_i04_i07`; stored as a 512×512 JPEG, served `private` | PASS |
| R02-I05 | Patient replacement | Device: gallery → camera, new version `d0c38a80…`; `test_i05_i06`; one file on disk | PASS |
| R02-I06 | Patient removal | Device `e26` → `e27` ("Profile photo removed."), server `profileImage: null`, 0 files; `test_i05_i06`; widget I06 | PASS |
| R02-I07 | Patient default avatar | Device `e01/e27`; widget I07/I24; `test_i04_i07` | PASS |
| R02-I08 | Doctor upload | Device `e17` → `e18` (dashboard card); `test_i08…` | PASS |
| R02-I09 | Doctor replacement | Device `e24`, new version `d6ff84d7…`, one file; `test_i09_i10` | PASS |
| R02-I10 | Doctor removal | API (the same endpoint the app uses) → `null`, 0 files; admin `r02_removed_b01–b03`; patient search falls back to initials (`e28`); `test_i09_i10` | PASS (removal action run through the API, not tapped on the device) |
| R02-I11 | Doctor search card | Device `e19` (picture), `e25` (replaced), `e28` (removed → initials); `test_i08…` | PASS |
| R02-I12 | AI recommendation card | `test_i12` (`/api/ai/doctor-recommendations` returns the stored path); device AI assistant doctor card `e23` (deterministic engine, 0 provider calls) | PASS — the dedicated recommendation screen is not reachable from the app UI (R02-O2) |
| R02-I13 | Doctor details | Device `e20`; `test_i08…` | PASS |
| R02-I14 | Appointment doctor image | Device booking summary `e21` (no hold created) and My Appointments `e22`; API `doctorProfileImage`; `test_i08…` | PASS |
| R02-I15 | Admin doctor management | Browser `with_photo`, `replaced`, `removed` runs: list (blob from the admin session), verification queue, 32×32 square, no row distortion, no path or token in the DOM, 0 blocked requests, 0 page errors | PASS |
| R02-I16 | Logout/login persistence | Device: patient → doctor → patient; the picture and data return after each login | PASS |
| R02-I17 | App restart persistence | Device `e15` after force-stop (process 27364 → 29513) | PASS |
| R02-I18 | Backend restart persistence | `r02_backend_restart_persistence.txt`: both pictures byte-identical (SHA-256) after restarting the UAT backend; `test_i18` | PASS |
| R02-I19 | Cached image replaced | Device `e25`: the patient sees the new doctor picture after replacement; widget I04/I19 (a new version is fetched again) | PASS |
| R02-I20 | Account switching isolation | Device `e16`: the doctor dashboard after the patient session shows the default, not the patient's picture; widget I20 (logout clears the cache); cache cleared at every login | PASS |
| R02-I21 | Cancelled selection | Widget I21 (sheet cancel, picker cancel → no upload, no change) | PASS (automated) |
| R02-I22 | Failed upload recovery | Widget I22 (error shown, previous picture kept, retry succeeds); `test_s14` | PASS (automated) |
| R02-I23 | Denied permission / no camera | Widget I23 (clear message, no change). The app requests no runtime permission; the system picker and camera need none | PASS (automated; a denial cannot be triggered on the device because no permission is requested) |
| R02-I24 | Unavailable image fallback | Widget I07/I24 (404, junk URL → fallback, no crash); admin `DoctorAvatar` tests | PASS |
