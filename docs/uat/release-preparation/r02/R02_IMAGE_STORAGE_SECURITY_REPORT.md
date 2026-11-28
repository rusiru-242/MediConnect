# R02 — Image Storage and Security Report

For: the project owner, reviewers and a security reviewer. Describes how profile pictures are stored, served and protected, and records the S01–S15 results.

## Storage decision

| Item | Decision |
|---|---|
| Where | Local disk: `backend/uploads/profile_images/<userId>/<uuid4>.jpg`, beside the existing encrypted stores (`doctor_verification`, `medical_documents`, `companion_images`). `backend/uploads/` is git-ignored |
| Encryption at rest | The Phase 05 AES-256-GCM helper (`document_crypto.seal_for_storage`), store name `profile_images`. The associated data binds each file to its store and path, so a copied file does not decrypt elsewhere. Files on disk start with `MCENC1`, confirmed in UAT |
| Database | `users.profileImage` holds the display path `/api/profile/pictures/<userId>?v=<version>`. `users.profileImageMeta` holds `{storageKey, version, contentType, width, height, bytes, updatedAt}`. No Base64 image data is stored in MongoDB |
| Why this choice | It reuses the existing, tested storage and encryption. There is no new service, cost or credential, and no external image host |
| Production limitation | Local disk belongs to one server. Several backend instances, or a server replacement, need shared or object storage behind the same interface, with backups. The disk should also be encrypted at the volume level. Recorded in `R02_REMAINING_BLOCKERS.md` |
| Existing field reused | `profileImage` was already read from the database by search, details, AI recommendations, the booking agent and the tool registry. Doctor pictures therefore reach those views from trusted data; no model output is ever used as an image address |

## Upload pipeline (`app/services/profile_image_service.py`)

| Step | Control | Default (setting) |
|---|---|---|
| Who | The authenticated identity only; any owner id sent by a client is ignored. Patients and doctors only; administrators get 403 | — |
| Rate | Shared sliding-window limiter (MongoDB counters), per user, covering uploads and removals | 20 per hour (`PROFILE_IMAGE_UPLOADS_PER_HOUR`) |
| Size | Reads at most limit + 1 bytes; larger uploads get 413 without buffering the rest | 5 MB (`PROFILE_IMAGE_MAX_BYTES`) |
| Real type | Pillow identifies the format from the content; the file name and the client's content type are ignored. JPEG, PNG and WebP only; animated images are refused | — |
| Dimensions and bombs | Header size is checked before decoding. Pillow's decompression-bomb warning and error are turned into a 400 | 8000 px per side (`PROFILE_IMAGE_MAX_DIMENSION`), 40 megapixels (`PROFILE_IMAGE_MAX_PIXELS`) |
| Malformed data | `verify()` then a full `load()`; any decoder error gives a 400 | — |
| Normalise | EXIF orientation applied, optional square crop (fractions 0–1, validated), resize to 512×512, re-encode as a new JPEG (quality 85) from a fresh image | 512 (`PROFILE_IMAGE_OUTPUT_SIZE`) |
| Metadata | Re-encoding drops EXIF (including GPS), XMP, ICC and comments. Verified in tests and in UAT with synthetic photos carrying fake GPS and a camera marker | — |
| Path | `<authenticated userId>/<uuid4 hex>.jpg`; the resolved path must stay inside the store | — |
| Replace | Write the new file → one atomic `find_one_and_update` returns the previous reference → delete only that previous file. If the database update fails, the new file is deleted and the old picture stays | — |
| Remove | Atomic unset, then delete the stored file | — |

## Serving and visibility (`GET /api/profile/pictures/{userId}`)

| Viewer → owner | Result |
|---|---|
| Anyone → their own picture | 200 |
| Any signed-in user → an **approved and active** doctor | 200 (the same rule as doctor discovery) |
| Admin → any doctor (including pending) | 200 |
| Anyone else → a pending, rejected or inactive doctor | 404 |
| Doctor with a care relationship (confirmed or completed appointment, consultation or care plan; the existing clinical-records rule) → patient | 200 |
| Unrelated doctor, other patient or admin → patient | 404 |
| Unauthenticated | 401 |

Refusals use 404, so an outsider cannot learn whether a picture exists. Responses carry `Cache-Control: private, max-age=86400`, an `ETag`, `X-Content-Type-Options: nosniff` and `Content-Disposition: inline`. A replacement changes the version in the URL, so a cached copy is never shown for a new picture. Identifiers other than `[A-Za-z0-9_-]{1,64}` never reach storage.

Clients:
- **Mobile:** fetches pictures with the session through `ApiClient.getBytes`, which includes token refresh, and keeps them only in memory. The cache is cleared at every login and logout.
- **Admin web:** fetches with the admin session into object URLs. It only fetches `/api/profile/pictures/<id>?v=<v>` paths and revokes them on logout.
- **External pictures:** a Google account photo (an existing `https://` value) is loaded without MediConnect credentials.

Pictures are display-only. They are not sent to any AI provider and not used for identification, inference or ranking. Ranking code is unchanged; see `test_i12`.

## Security matrix

| ID | Scenario | Evidence | Result |
|---|---|---|---|
| R02-S01 | Unauthenticated upload, removal and retrieval | `test_s01` (401/403); UAT `curl` without a session → 401 | PASS |
| R02-S02 | Cross-user modification | `test_s02`: a `userId` form field is ignored; the other user's picture is unchanged; `PUT /pictures/{other}` → 405; admin upload → 403 | PASS |
| R02-S03 | Cross-user deletion | `test_s02`: `DELETE /pictures/{other}` → 405; the other user's file and reference are intact | PASS |
| R02-S04 | Unauthorised patient picture retrieval | `test_s04_s05`; UAT probe: other patient → 404, admin → 404 (`r02_uat_visibility_probe.jsonl`) | PASS |
| R02-S05 | Unrelated doctor access | `test_s04_s05` (unrelated → 404; doctor with a confirmed appointment → 200); UAT: Dr. UAT General (cancelled appointment only) → 404, Dr. UAT Neuro (confirmed appointments) → 200 | PASS |
| R02-S06 | Invalid format (GIF, BMP, EXE) | `test_s06_s07` → 400, nothing stored | PASS |
| R02-S07 | Disguised non-image (text or script named .jpg/.png, HTML behind JPEG magic bytes) | `test_s06_s07` → 400, nothing stored | PASS |
| R02-S08 | Oversized upload | `test_s08`: 5 MB + 10 bytes → 413, nothing stored | PASS |
| R02-S09 | Oversized decoded dimensions / decompression bomb | `test_s09`: 8100 px side → 400; a highly compressed 1200×1200 PNG under a 1 MP limit → 400 "dimensions" | PASS |
| R02-S10 | Malformed images | `test_s10`: truncated PNG and a bare PNG header → 400. A JPEG with corrupted bytes is either refused or fully decoded and re-encoded (nothing of the original is stored) | PASS |
| R02-S11 | Metadata removal including GPS | `test_s11` (camera make, software and GPS IFD gone; no `Exif` bytes); UAT gallery, camera and doctor uploads: `exifTags 0, gpsPresent false, syntheticCamMarkerPresent false` | PASS |
| R02-S12 | Path traversal | `test_s12`: `../`, encoded variants, backslashes, junk and over-long ids → 404/422; a filename of `../../../../etc/evil.jpg` is stored as `<uuid>.jpg` in the owner's folder | PASS |
| R02-S13 | Concurrent replacement integrity | `test_s13`: 5 parallel uploads → all 200, exactly one file, and the reference matches it. After merge, an intermittent refusal of parallel first uploads was found and fixed (R02-BUG-007); the new 8-round test passes | PASS (after R02-BUG-007 fix) |
| R02-S14 | Failed replacement keeps the previous picture | `test_s14`: invalid replacement → 400; a simulated database failure removes the new file and the old one is still served byte for byte | PASS |
| R02-S15 | An unapproved doctor's picture is not public | `test_s15`: pending doctor's picture → 404 to patients and other doctors, 200 to the doctor and admin; the doctor stays out of search and details | PASS |
| — | Rate limit | `test_upload_rate_limit`: third change within the window → 429 | PASS |
| — | No secrets or paths in admin pages | Browser runs `S-ADMIN`: no `uploads/profile_images`, `storageKey`, `Bearer` or JWT in the DOM | PASS |
| — | Persistence | Backend restart: both pictures byte-identical (`r02_backend_restart_persistence.txt`); `test_i18` | PASS |

## Not covered

- **Production deployment:** object storage, backups and CDN rules (none planned without a decision).
- **Malware scanning:** none. Decoding and re-encoding removes the original bytes, but no antivirus engine is used.
- **Physical-device camera:** only the emulator's virtual scene camera was used.
