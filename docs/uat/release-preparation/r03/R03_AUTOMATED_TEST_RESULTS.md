# R03 — Automated Test Results

For: the project owner and reviewers. 2026-11-28. All counts below were executed in R03. Historical counts are shown only for comparison and are not added to the R03 total.

## Final runs (tested code = implementation commit `4f64295`)

The final runs were made on the working tree that was then committed unchanged as `4f64295`. The admin web was run on the same tree; no admin file changed in R03.

| Suite | Command | Total | Passed | Failed | Skipped | Provider connection attempts |
|---|---|---|---|---|---|---|
| Backend (full) | `pytest -q -p a03_leak_detector -p no:cacheprovider -rfEs` on a **fresh** local database `mediconnect_r03_final2_test` (did not exist before the run) | 1,064 | **1,064** | 0 | 0 | **0** |
| Flutter (full) | `flutter test` | 362 | **362** | 0 | 0 | n/a (network-free tests) |
| Flutter analyze | `flutter analyze` | — | No issues | — | — | — |
| Android APK | `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001` | — | Built | — | — | — |
| Admin Web | `npx vitest run` | 51 | **51** | 0 | 0 | n/a |
| Admin TypeScript | `npm run typecheck` (`tsc --noEmit`) | — | Exit 0 | — | — | — |
| Admin ESLint | `npm run lint` (`--max-warnings 0`) | — | Clean | — | — | — |
| Admin build | `npm run build` | — | Built | — | — | — |

**Newly executed in R03 (final runs): 1,064 + 362 + 51 = 1,477 automated tests passed, 0 failed, 0 skipped.**

**Comparison with R02:**

| Suite | R02 | R03 | Difference |
|---|---|---|---|
| Backend | 1,048 | 1,064 | +2 R02-BUG-007 tests, +14 `test_r03_final_verification.py` |
| Flutter | 361 | 362 | +1 R03-BUG-004 test; `doctor_reviews_test.dart` gained assertions only |
| Admin | 51 | 51 | — |

The R03 total is not added to historical totals, and no run is counted twice.

## Run history (all R03 runs, honestly recorded)

| Run | Database / tree | Result | Note |
|---|---|---|---|
| 1. Full backend on the R02-BUG-007 fix (before R03 began) | fresh `mediconnect_r02fix_test` | 1,049 passed, **1 failed** (`test_phase3_care` medication test) | Led to R03-BUG-001 (test isolation). Passed alone and in its file |
| 2. Full backend after R03-BUG-001/002 | fresh `mediconnect_r03_final_test` | 1,064 passed | Before R03-BUG-004 (PDF wording) |
| 3. **Final full backend** | fresh `mediconnect_r03_final2_test` | **1,064 passed** | After every code change |
| Focused runs during fixes | `mediconnect_r03focus_test` | 177 emergency-related + isolation tests passed; R02 + A05 smoke 71/72 (S13 → R02-BUG-007, fixed before R03) | |
| Flutter during fixes | — | 361 → 362 | The R03-BUG-003 and 004 tests were confirmed to fail on the old code |

## Coverage of the requested areas

| Area | Where |
|---|---|
| Authorisation, object-level access | `test_production_security_audit`, Phase 04/05 security suites, `test_r02_profile` S-tests |
| Clinical workflows | Phase 03 suites, `test_a04_prescription_assistant`, `test_phase3_care` |
| Payments and reservations | `test_phase02_booking_payment`, `test_a03_booking_payments`, Stripe webhook tests (test doubles) |
| Concurrency | unique-slot holds, refund claims, prescription issue, `test_s13` (R02-BUG-007) |
| Fraud monitoring | `test_a05_fraud_support`, R02 sweep test, **R03 231-account real sweep** |
| Support tickets | `test_a05_fraud_support` (C-tests), Flutter `a05_support_test`, admin `a05FraudSupport` |
| Profile and image security | `test_r02_profile.py` (47) |
| Emergency triage | `test_phase05_emergency`, `test_a01_health_assistant`, stabilisation suite, **R03 detector tests** |

## Limitations

- The backend CI runs on Linux; the Windows-only path race (R02-BUG-007) shows such runs can differ, so the local Windows run is reported separately from CI.
- No live provider, Stripe, push, e-mail or SMS request is made by any suite (detector: 0 attempts).
