# R04 — Final Release Preparation Report

For: the project owner and academic reviewers. 2026-11-28. Release `v1.0.0-academic`, classified as **academic demonstration / engineering preview**.

## Outcome

| Item | Result |
|---|---|
| Starting point | `origin/main` `1f95285` (R03 merged as PR #31; all earlier phases and PR #30 preserved; Backend and Mobile CI on `main` succeeded) |
| Branch | `release/mediconnect-v1` |
| README | Rewritten: accurate, concise, with real screenshots, diagrams, verification results, setup and limitations |
| Architecture | New `docs/ARCHITECTURE_OVERVIEW.md` with system, agentic AI, booking and clinical diagrams; links to the R03 38-component document |
| Developer setup | `docs/DEVELOPER_SETUP.md` rewritten and checked against the scripts and configuration |
| Screenshots | 16 genuine, privacy-reviewed screenshots in `docs/assets/screenshots/` (1.1 MB), including two new R04 admin captures and a new multilingual capture |
| Android APK | Debug, emulator-only, `API_BASE_URL=http://10.0.2.2:8001`; 257,233,513 bytes; SHA-256 `ca477aab…8357`; installs, launches and signs in on the emulator |
| Admin build | `admin-web/dist/`; type check, lint, 51 tests, build and local preview all passed |
| Newly executed checks | 191 automated tests (backend 100, Flutter 40, admin 51); Flutter analyze; APK build, install, launch and login; admin build and preview; 50 documentation links; secret scans |
| Historical R03 baseline | 1,477 tests passed (not re-counted) |
| Secret scans | No secrets in tracked files, the APK, the admin build, the release package or the report package. One Stripe **test publishable** key in the app (informational) |
| Credential remediation | **Not confirmed** |
| Public release | **Not eligible**; local package only, with no tag or GitHub release |
| Release package | `C:\Users\REDTECH\Downloads\MediConnect-v1.0.0-academic.zip` (109,779,845 bytes) |
| R05 handover | `docs/uat/release-preparation/r04/R04_R05_DEMO_HANDOVER.md` |

## Reports

| Report | Content |
|---|---|
| `R04_DOCUMENTATION_VERIFICATION.md` | What changed, README corrections, link and privacy checks |
| `R04_BUILD_VERIFICATION.md` | APK and admin builds, scans, focused checks |
| `R04_RELEASE_SECURITY_GATE.md` | Publication conditions, scans, owner actions |
| `R04_RELEASE_NOTES.md` | v1.0.0-academic release notes |
| `R04_ARTIFACT_MANIFEST.md` | Package contents and checksums |
| `R04_R05_DEMO_HANDOVER.md` | Startup, accounts, scenarios, automation, restrictions, authorisations |
| `R04_GIT_INTEGRATION_REPORT.md` | Starting point, changes, PR, CI, merge |
| `R04_RESULTS.json` | Machine-readable results |

## Limitations carried forward

Clinical validation · pharmacist review · drug-interaction source · real packaging testing · native-language review · push/e-mail/SMS · OpenAI credits · Gemini limits · Stripe staging webhook · shared storage · backups · monitoring · production security · BUG-039 · refund policy · fraud thresholds · messaging scope · physical device and camera · iOS.

**No new feature or policy was introduced in R04.** Next phase: R05 — Automated Emulator and Admin Web Demonstration Video.
