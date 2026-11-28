# R02 — Remaining Blockers and Limitations

For: the project owner. Nothing here is resolved by R02 unless it says so. No security or clinical blocker from earlier phases is removed.

## Resolved by R02 (verified)

| Item | Evidence |
|---|---|
| A05-O1: invented patient Profile data (including "Allergies: Penicillin") | R02-BUG-001, P01–P10 |
| R01-O1: patient navigation overflow | R02-BUG-003, U01–U03 |
| R02-BUG-002, 004, 005, 006 | `R02_BUG_FIX_REPORT.md` |
| R01-O2: dark-mode welcome and login | R02-BUG-004, U05–U06 |

## New R02 limitations

| Item | Detail | Owner action |
|---|---|---|
| Picture storage is local disk | Fine for one server. Several instances, server replacement or backups need shared or object storage behind the same service, plus volume encryption | Decide on production storage before deployment |
| Physical device | Gallery and camera verified on the emulator only (virtual camera scene) | Test on a real Android phone |
| iOS | Camera and photo usage strings added; no iOS build or run (no macOS) | iOS build and test |
| Picture malware scanning | None. Images are fully decoded and re-encoded, so no original bytes are kept | Optional |
| Clinician confirmation of self-reported values | Self-reported height, weight and allergies are labelled; no workflow lets a clinician confirm them | Product decision |
| Production data check | Invented values were never stored. A read-only check of `users.healthProfile` before release is still advised | Optional |
| Dedicated AI recommendation screen | Registered but not reachable from the UI (R02-O2) | Product decision |
| Shared test database | The local `mediconnect_test` database has grown and contains future-dated fixtures (R02-O1). CI is unaffected | Optionally reset the local test database |

## Carried forward (unchanged)

- **Security:** MongoDB credential rotation and incident check (P5-C1, P4-B1); provider credential rotation (P4-B2).
- **Clinical:**
  - pharmacist review (B2);
  - clinical validation (B1);
  - a drug-interaction source (P3-B9);
  - BUG-039 (the one open defect).
- **Device and language:** physical-device testing (B10); native Sinhala and Tamil review (B12). New R02 strings are English only.
- **Integrations:**
  - the Stripe staging webhook endpoint;
  - the refund policy (B6);
  - Firebase, e-mail and SMS providers;
  - OpenAI credits and Gemini limits.
- **Earlier agents:**
  - the A04 renewed-prescription reminder on a device;
  - the A05 fraud thresholds and review process;
  - R01-O3 to O7.

No production deployment is authorised or performed. R02 makes no claim of clinical validation or production readiness.
