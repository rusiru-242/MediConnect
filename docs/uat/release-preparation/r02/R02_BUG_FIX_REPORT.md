# R02 — Bug Fix Report

For: the project owner, reviewers and future maintainers. Defects confirmed in R02, their root causes and fixes. Every fix has an automated regression test; device checks are noted where they were also run.

## Defects

| ID | Severity | Component | Defect, root cause and fix |
|---|---|---|---|
| R02-BUG-001 | High (A05-O1) | Mobile — patient profile | **The patient Profile screen showed invented personal and clinical data**, including height 5'7", weight 134 lbs, BMI 21.0 "Normal", allergy "Penicillin (Moderate)", "Emergency Contact: Spouse" (labelled on the patient's own phone number), a "BlueCross MediConnect" insurance policy "#9482-108", patient number "#MC-88392", "28 yrs • Female • Blood Type: O+", a "MediConnect Pass / Active Tier 1" card, and record summaries ("Updated 3 days ago", "2 current medications"). Root cause: the screen was built from a static design mock-up with literal values; no profile API existed. Fix: new `GET/PATCH /api/profile/me` returning only stored data. Patient-reported height, weight, allergy status and emergency contact are labelled "Entered by you". Recorded allergies come from the medical record with their provenance. BMI is calculated only from two real values and shown with a "not a diagnosis" note. Everything else shows "Not provided". The invented card, numbers and summaries are removed. Tests: `test_p01…p10`, `r02_profile_test.dart` P-group; device `r02_after_e01/e02/e14/e15` |
| R02-BUG-002 | Medium | Mobile — patient profile | **Profile actions reported success without doing anything.** "Edit Profile" showed "Profile information updated successfully." and saved nothing, "Share ID card" showed "Sharing…", and the emergency "Call" button showed "Calling …". Root cause: placeholder handlers. Fix: "Edit Profile" opens a real form that validates, sends only changed fields and persists; the fake Share and Call actions are removed. Tests: `P07/P08` widget test, `test_p03_p07_p09`; device `r02_after_e13/e14/e15` |
| R02-BUG-003 | Medium (R01-O1) | Mobile — patient navigation | **The bottom navigation overflowed** by 15 px at 360 dp, with the yellow-and-black stripe over "Profile". Root cause: a `Row(spaceAround)` of fixed-padding items with fixed-size labels; it did not fit four items at narrow widths or with larger text. Fix: each item is `Expanded`, labels use `FittedBox(scaleDown)` with one line, padding is smaller, and each item is a single accessible button with a 48 dp minimum height. All four destinations are kept. Tests: five widget tests (320/360/412 dp, text 1.0 and 1.3); device `r02_after_e29/e30/e31` |
| R02-BUG-004 | Medium (R01-O2) | Mobile — welcome and login | **The welcome and login screens were unreadable in dark mode.** The background stayed light, the language chips turned dark, and the outlined "Create Account" text became invisible. Root cause: the screens mixed fixed light-theme colours with theme-styled buttons and chips. Fix: an `AuthPalette` maps those colours to the existing dark tokens (`AppTheme.dark*`); light mode is unchanged, as is the layout. Tests: `U04`, `U05/U06` (background, title colour, Create Account contrast > 4.5:1); device `r02_after_e32/e33` against R01 `e15/e16` |
| R02-BUG-005 | Medium | Mobile — AI care assistant | **The doctor card in the AI assistant loaded the picture without the session** (`Image.network` with no credentials). With pictures now private to signed-in users, it would always fall back. Root cause: written when `profileImage` could only be an external URL. Fix: it uses the authenticated `UserAvatar`, like every other doctor placement. Device `r02_after_e23` |
| R02-BUG-006 | Medium | Backend — fraud sweep (A05, latent) | **With more than 200 recently active accounts, the fraud sweep silently skipped the newest ones.** Root cause: `sorted(account_ids)[:200]`; ObjectId strings sort by creation time, so the most recent accounts were cut. Found when the shared test database reached 223 candidates: the A05 tests F01, F03, F09 and F10 failed, and fail the same way on unchanged `main`. Fix: every candidate is evaluated; an explicit `limit` is reported as `deferred` and never hidden. Test: `test_fraud_sweep_evaluates_every_active_account_even_beyond_200` |
| R02-BUG-007 | Medium | Backend — profile picture storage (found after merge) | **Parallel first uploads were intermittently refused with "Invalid storage destination."** Found in the post-merge smoke run on `main` `8ac5a41`, where `test_s13` failed (3 of 5 uploads returned 400); it had passed in the pre-merge runs and in CI, so it was intermittent. Root cause: the path check compared `str(resolve())` strings, and on Windows `Path.resolve()` returns the `\?\C:\...` long-path form while another request is creating the user's folder, so the prefix check failed. It refused uploads (never allowed an escape), so it was a reliability defect, not a security one. Fix (branch `fix/profile-image-path-race`): storage keys are validated against the strict server format `<userId>/<32-hex>.jpg` and joined to the resolved base without resolving the full path; the same helper is used for write, read and delete. Tests: `test_s13_concurrent_first_uploads_into_a_new_storage_folder_never_refuse` (8 rounds × 5 parallel first uploads; failed every run before the fix) and `test_storage_keys_are_strictly_validated_and_never_leave_the_base` |

## Issues found and fixed in R02's own new code before commit

Not counted as product defects, because they never reached `main`. They are recorded because the tests caught them.

| Issue | Found by | Fix |
|---|---|---|
| The avatar cache never completed a load: `whenComplete(() => _inFlight.remove(url))` returned the removed Future, which is the same future, so it waited on itself forever | Avatar widget test hung | Block-bodied callback |
| The edit form used a lazy `ListView`, so off-screen fields were not built and `Form.validate()` skipped them | Edit form widget test | `SingleChildScrollView` + `Column`, so every field always exists |
| The adjust screen opened on the top-left square, not the centre | Crop widget test | Initial transform centres the photo, matching the server's default crop |
| During loading or after a failed load, the emergency contact claimed "Not provided" | Profile error-state widget test | Shows "Loading…" or "Unavailable" until the data is actually known |

## Changed files

| Area | Files |
|---|---|
| Backend (new) | `app/services/profile_image_service.py`, `app/services/patient_profile_service.py`, `app/routes/profile.py`, `tests/test_r02_profile.py` |
| Backend (changed) | `app/main.py` (router), `app/config/settings.py` (5 `PROFILE_IMAGE_*` settings), `app/schemas/appointment.py` + `app/services/appointment_service.py` (`doctorProfileImage`), `app/schemas/admin.py` + `app/services/admin_service.py` (`profileImage` in admin doctor views), `app/services/fraud_detection_service.py` (R02-BUG-006), `requirements.txt` (`pillow>=12.0.0`, previously only a transitive dependency of reportlab) |
| Mobile (new) | `lib/widgets/user_avatar.dart` (authenticated avatar + private in-memory cache), `lib/widgets/profile_picture_editor.dart` (gallery / camera / adjust / upload / retry / remove), `lib/services/profile_service.dart`, `lib/models/patient_profile.dart`, `lib/screens/patient/edit_patient_profile_screen.dart`, `lib/core/theme/auth_palette.dart` |
| Mobile (changed) | `patient_profile_screen.dart` (rewritten), `patient_home_screen.dart` (navigation, sheet avatar), `doctor_home_screen.dart` (dashboard and sheet avatar, change-photo action), doctor avatars in `find_doctor_screen`, `doctor_detail_screen`, `ai_doctor_recommendation_screen`, `ai_care_assistant_screen`, `ai_booking_assistant_screen`, `booking_confirmation_screen`, `my_appointments_screen`, `appointment_detail_screen`; `welcome_screen.dart` and `login_screen.dart` (dark mode); `models/appointment.dart`; `providers/auth_provider.dart` (cache cleared at login/logout, avatar and name updates); `core/network/api_client.dart` (optional upload progress); `pubspec.yaml`/`.lock` (`image_picker`); `AndroidManifest.xml` (camera intent visibility only, no new permission); `ios/Runner/Info.plist` (camera and photo usage strings); generated plugin registrants |
| Admin web | `components/common/DoctorAvatar.tsx`, `components/common/doctorAvatarCache.ts` (new); `pages/DoctorsPage.tsx`, `pages/DoctorVerificationPage.tsx`, `types/doctor.ts`, `context/AuthContext.tsx` (cache cleared on logout) |
| Tests | `backend/tests/test_r02_profile.py` (45), `mobile/test/screens/r02_profile_test.dart` (19), `mobile/test/helpers/fake_profile_service.dart`, `admin-web/src/test/r02DoctorAvatar.test.tsx` (4) |

## Changed expectations in existing tests

| Test | Change | Why |
|---|---|---|
| `mobile/test/screens/patient_profile_screen_test.dart` | Expected "MEDICONNECT PASS" → now expects it to be **absent**, and expects "Health Summary"; the screen gets a fake profile service | The pass card was invented data (R02-BUG-001). The check is stronger, not weaker |
| `mobile/test/screens/a05_support_test.dart` (C01) | Builds the profile screen with a fake profile service | The screen now loads real data; the test previously relied on static content |

No assertion was removed.

## Observations

| ID | Observation |
|---|---|
| R02-O1 | The long-lived local `mediconnect_test` database had collected about 10,000 users and 42 payments with future `createdAt` values from earlier fixture runs. On it, `test_admin_web_endpoints_rbac_and_crud` fails because its fresh payment is not on page 1. The test passes on a fresh database, and the full suite passes on a fresh database (1,048). CI always starts empty. Test isolation, not an application defect |
| R02-O2 | `/patient/ai-recommendations` (`AiDoctorRecommendationScreen`) is registered but no screen navigates to it. The in-app "AI Doctor Finder" opens the AI assistant. Both show the trusted picture: the endpoint is covered by `test_i12`, and the assistant card was checked on the device |
| R02-O3 | The deterministic assistant maps "general practitioner" to a specialty name that the synthetic doctor "General Practice" does not match, so that query found no doctor. Asking by name worked. A specialty-synonym gap in the deterministic engine; not changed in R02 |
| R02-O4 | On the profile card, a screen reader announces the photo button together with the name and e-mail ("Change profile photo, UAT Patient Two, …"), because the card merges semantics. Usable, but could be tidier |
| R02-O5 | No historical fabricated values exist in the database: the invented profile values were literals in the screen, never stored. No data remediation is needed. A production database should still be checked once with a read-only query on `users.healthProfile` before release |
