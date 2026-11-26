# A01 — Test Verification Matrix

For: reviewers and engineers. 2026-11-26, branch `fix/agents-a01-ai-intelligence-vision`.

Every count below comes from an executed run. Nothing unexecuted is counted as passed.

## Environment and isolation

- **Before any code ran**, these were confirmed:
  - UAT backend on 127.0.0.1:8001, `/health` → `mediconnect_uat`, `isolatedTestData: true`, `environment: staging`.
  - Local MongoDB 127.0.0.1:27017.
  - Port 8000 belongs to an owner-started `--reload` server. It was left untouched and never used.
- **Automated tests:**
  - Fresh databases `mediconnect_a01_test` and `mediconnect_a01b_test` (conftest requires the `_test` suffix).
  - Provider keys are blanked and provider hosts blocked (A01-N06).
- **No remote database connection**, and no change to MongoDB credentials or git history.

## Suites

| Suite | Command / location | Result | Baseline (Phase 05) |
|---|---|---|---|
| Backend (full, final code) | `pytest -q` on `mediconnect_a01b_test` | **865 passed, 0 failed** (407.9 s) | 782 |
| …of which new A01 tests | `test_a01_provider_layer` 26, `test_a01_health_assistant` 36, `test_a01_medicine_vision` 21 | 83 passed | — |
| Backend compile | `python -m compileall app` | clean | clean |
| Flutter (full) | `flutter test` | **309 passed, 0 failed** | 307 |
| Flutter analyze | `flutter analyze` | No issues found | clean |
| Android debug APK | `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001` | built, installed on emulator-5554 | built |
| Admin web | `npm test -- --run` (Vitest) | **39 passed** (unchanged code) | 39 |
| Phase 05 live UAT (regression) | `phase-05/phase05_live_uat.py` on UAT 8001 | **12/12** | 12/12 |
| Phase 05 intent probe (regression) | `phase-05/intent_probe.py` on UAT 8001 | 25 rows, **0 differences** from Phase 05 | — |

## Changed or added test expectations

All three changes are explained in `A01_BUG_FIX_REPORT.md`:
- Two retired-model mapping assertions now expect `gemini-3.8-flash`.
- Flutter test #11 expects no "High Confidence" badge.

Two existing tests failed against an A01 draft and were kept unchanged, with the code fixed instead:
- `test_prompt_care_escalation`
- `test_bug023_reads_actual_label_fields` / `test_02_known_medicine_label_image`

## Scenario matrices

| Matrix | Scenarios | PASS | BLOCKED | Live evidence | Report |
|---|---|---|---|---|---|
| Provider (A01-P01–P16) | 16 | 15 | 1 (P04 OpenAI live: no credits) | Gemini rows P01, P03, P05–P07, P09 (after fix), P11–P15 | `A01_AI_PROVIDER_VERIFICATION.md` |
| Health Assistant (A01-H01–H20) | 20 | 20 | 0 | deterministic: all 20 (26 probe cases); LLM: H01, H02, H03, H06, H08 | `A01_HEALTH_ASSISTANT_VERIFICATION.md` |
| Medicine vision (A01-V01–V18) | 18 | 18 | 0 | V01–V08, V17 (Gemini); V11/V12 widget tests | `A01_MEDICINE_VISION_VERIFICATION.md` |

Notes on the provider matrix:
- P05 is counted PASS on Gemini vision; OpenAI vision is blocked by the same lack of credits as P04.
- P09 passed only after the A01-N07 fix.

Mocked vs live:
- Rows verified only with test doubles say so: V14, V16, and all OpenAI generation and vision.
- Live counts are in the provider report: 29 gateway requests to Gemini (22 succeeded), 4 to OpenAI (all rejected for no credits).

## Live probes (UAT 8001)

| Probe | Mode | Result | Evidence |
|---|---|---|---|
| Health Chat baseline | Phase 05 build, providers off | 15/26 generic templates; overdose missed | `evidence/health_probe_before.json` |
| Health Chat after | A01, providers off | 26/26 expected answer kind; 0 generic templates | `evidence/health_probe_after_deterministic.json` |
| Health Chat live LLM | Gemini `gemini-3.5-flash-lite` | 7 + 3 cases; rewrites grounded, 1990 kept; 1 timeout fell back (fixed) | `evidence/health_probe_live_gemini*.json` |
| Vision live | Gemini, 8 fixtures + 3 re-tests | all match expected after N09 and prompt fixes | `evidence/vision_live_*.json` |
| Provider rows | live, mixed | P03 ok, P04 quota, P06 auth, P07 model, P11/12 fallback, P13 both down | `evidence/live_*.json` |

## Emulator (Android emulator-5554, Pixel 7 Pro image)

- **Foreground check:** the helper `emu.py` refuses input unless MediConnect is in the foreground. The single tap in the system file picker was made after confirming the picker's identity.
- **Flow covered:** login as `uat.patient1` → Health Chat (library answer, markdown, duplicate pointer, live LLM sleep reply) → AI Care Assistant → pick fixture → preview → send → live vision result and card.
- **Screenshots:** `evidence/emulator/a01_01`–`a01_13`.
- **Defects found on the device, fixed and re-verified there:**
  - medicine text rendered "P; a; i";
  - Health Chat showed literal `**`.

## Not executed

- **Flutter `integration_test`:** the project has no integration-test target. The emulator flow above was driven through adb instead.
- **Live OpenAI:** no credits.
- **Physical device.**
- **Real photographed packaging.**
