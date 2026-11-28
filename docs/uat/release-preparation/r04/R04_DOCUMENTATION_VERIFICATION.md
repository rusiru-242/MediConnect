# R04 — Documentation Verification

For: the project owner and reviewers. 2026-11-28.

## Documents created or updated

| Document | Status | Verified against |
|---|---|---|
| `README.md` | **Rewritten** | Code, R03 reports, actual screenshots. Kept the three genuine CI workflow badges (they show live GitHub Actions status; no other badges added) |
| `docs/DEVELOPER_SETUP.md` | **Rewritten** | `backend/scripts/start_uat_backend.ps1`, `tests/conftest.py`, `admin-web/vite.config.ts`, `admin-web/src/api/client.ts`, `mobile/lib/core/constants/api_constants.dart`, `android/app/build.gradle.kts`, CI workflows |
| `docs/ARCHITECTURE_OVERVIEW.md` | **New**: system, agentic AI, booking and clinical diagrams (Mermaid) | Routes, services, R03 Workflows A–C, A03 booking evidence |
| `docs/assets/screenshots/` | **New**: 16 optimised JPEGs (1.1 MB) + `SCREENSHOTS.json` (source, caption, checksum) | Genuine R03/R04 captures and three earlier ones (A01, A03) |
| `R04_RELEASE_NOTES.md`, `R04_R05_DEMO_HANDOVER.md` | **New** | R03 results, R03 demo checklist |
| Consolidated R03 documents | Unchanged; linked | — |

## Corrections to the previous README

| Previous claim | Corrected to |
|---|---|
| "Production-grade digital healthcare platform" | Academic demonstration / engineering preview |
| Backend on port 8000; MongoDB Atlas | Local UAT on port 8001 with a local database; Atlas only for a future deployment |
| Firebase push alerts delivered | Push, e-mail and SMS not configured |
| "Doctor SLMC credential verification" | Manual review of registration details; no registry integration |
| Test counts 190 / 177 / 28 | R03 results 1,064 / 362 / 51 (historical, labelled as R03) |
| Links as `file:///C:/Users/...` paths | Relative repository links |
| `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000` | `…10.0.2.2:8001`, emulator only, with physical-device notes |

## Accuracy rules applied

**Never claimed:**
- clinical validation;
- production readiness;
- medical-device status;
- autonomous diagnosis;
- AI accuracy figures;
- SLMC registry integration;
- validated drug interactions;
- external delivery;
- free-text messaging;
- tamper-evident signatures.

**Stated as they are:**
- 38 components, of which 7 have bounded LLM paths and 31 are deterministic;
- live Gemini only in earlier authorised tests; OpenAI not live; no live AI calls in R03;
- R03 numbers labelled as historical R03 results.

## Checks

| Check | Result |
|---|---|
| Relative links and images in 6 documents (`check_links.py`) | 50 checked, 0 broken |
| Mermaid diagrams | 6 diagrams (2 in the README, 4 in the overview), all describing implemented components only |
| Screenshot privacy review | 16/16 inspected: synthetic accounts (`uat.mediconnect.lk`), synthetic or abstract images, masked contact details; no tokens, credentials, database details or unrelated desktop content. A05 admin screenshots with the pre-R01 logo were not used; current-branding replacements were captured (`r04_b01`, `r04_b02`) |
| Multilingual screenshot | New genuine capture: romanised Sinhala request answered in Sinhala (deterministic engine); the rating 4.7 on the card was checked against three published synthetic reviews (mean 4.67) |
| Secrets in documentation | None (tracked-file scan) |
