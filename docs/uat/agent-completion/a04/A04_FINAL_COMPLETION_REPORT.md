# A04 — Final Completion Report: AI Prescription Assistant (Agent 17)

For: the project owner and reviewers. 2026-11-27.

## Outcome

| Item | Result |
|---|---|
| Starting point | `origin/main` `d8c2142` (PR #25 merged; A01–A03 present) |
| Branch | `fix/agents-a04-prescription-assistant` |
| Tested code commit | `51bdaa3` |
| Defects | 16 confirmed, 16 fixed (7 High, 8 Medium, 1 Low); 0 open |
| Scenario matrix | 36 scenarios: 34 PASS, 1 PARTIAL (M04), 1 NOT APPLICABLE (P06), 0 FAIL, 0 BLOCKED |
| Automated tests | Backend 976, Flutter 327, Admin web 42: **1,345 passed** (A03 baseline 1,304), 0 failed, 0 provider connection attempts |
| Agent 17 | **PARTIAL → PARTIAL**: engineering verified; clinical gates open |
| Component totals | 27 VERIFIED, 11 PARTIAL, 0 BLOCKED (unchanged) |
| Production readiness | Not claimed; not clinically approved |

**Why Agent 17 stays PARTIAL.** Its matrix entry was PARTIAL because there is no clinically validated drug-interaction source (P3-B9) and no pharmacist review. Both remain. A04 completed the feasible engineering work and verified it end to end on the emulator. Raising the status would claim clinical assurance that nobody has given.

## What A04 changed

| Area | Change | Defects |
|---|---|---|
| Doctor app | Dosing is no longer pre-filled and quantity has a field. The review lists exactly what was entered, with allergy and active-medication findings and "interaction checking not available". A failed prescription can be retried. The documentation list works; before, it was always empty and the form was unreachable | 009, 010, 011 |
| Issuing | Whitespace and repeated-medicine validation; simultaneous identical submissions store one prescription (database claim, not a process lock); the consultation path notifies the patient | 001, 002, 003, 012 |
| Assistant review | Allergy warnings are returned (they were dropped); structural draft check endpoint that stores and signs nothing; amended prescriptions count as current | 004, 007 |
| Renewals | Only a medicine on a current prescription; one open request per medicine, race-safe. Doctor queue usable on phones, with the instructions shown before approval. Patients can open their renewal list and request a renewal from the prescription | 005, 006, 014, 015 |
| Reminders | An amendment stops reminders built on the old instructions and tells the patient; nothing is rescheduled automatically | 008 |
| AI assistant | Patient and doctor prescription requests are answered from role-checked tools or refused explicitly (prescribe, approve, finalize, change, other patient, "ignore restrictions"); "not stated" for absent values; no chat mutation | 016 |
| Messages | A duplicate reminder no longer says "An account with this email already exists" | 013 |

Agent 17 is **deterministic**:
- **Rule-based checks:** allergy, duplicate and structural checks.
- **Deterministic intent routing:** a configured provider can only propose an intent from a fixed list.
- **Role-checked tools:** answers are formatted from stored records.

No generative AI runs on prescription paths, and nothing is labelled AI-generated.

## Evidence

| Evidence | Where |
|---|---|
| Live probe before and after the fixes, against the UAT backend (deterministic AI, 0 provider requests) | `evidence/a04_probe_baseline.json`, `evidence/a04_probe_after_fix.json` |
| Emulator, 24 screenshots: doctor issue with review → patient view → reminder → renewal → doctor approval → notification → renewal status → AI list and refusals | `evidence/emulator/a04_e01`–`e24` |
| New backend tests on the pre-fix code: 22 of 31 fail | `evidence/a04_tests_on_pre_fix_main.txt` |
| Provider connection attempts in the final backend run: 0 | `evidence/a04_backend_provider_attempts.json` |
| Database checks of the emulator run | `A04_PRESCRIPTION_VERIFICATION.md` |

## Reports

| Report | Content |
|---|---|
| `A04_PRESCRIPTION_VERIFICATION.md` | Doctor and patient workflow, renewals, reminders |
| `A04_AI_ASSISTANT_VERIFICATION.md` | Classification and the 14 required AI requests |
| `A04_CLINICAL_SAFETY_REPORT.md` | Structural versus clinical validation, limitations, gates |
| `A04_BUG_FIX_REPORT.md` | Defects, changed expectation, observations |
| `A04_TEST_VERIFICATION_MATRIX.md` | Suites and the 36-scenario matrix |
| `A04_REMAINING_BLOCKERS.md` | Owner actions, carried-forward blockers, A03 webhook clarification |
| `A04_GIT_INTEGRATION_REPORT.md` | Branch, commits, deployment check, PR, CI, merge |
| `A04_RESULTS.json` | Machine-readable results |

## A03 webhook discrepancy (carried forward, now clarified)

51 deliveries = 48 events + 3 resends. Of the 5 deliveries refused during the deliberate outage, 3 events were resent and accepted. 2 `charge.refund.updated` events were never redelivered; their refund reached its final state through the resent events. The A03 JSON figure (3 resent) is correct; the A03 wording "5 … resent" was not. Details are in `A04_REMAINING_BLOCKERS.md`.

## Remaining gates and blockers

| Category | Items |
|---|---|
| Security | MongoDB credential rotation and incident check (P5-C1, P4-B1); provider credential rotation (P4-B2) |
| Clinical | Pharmacist review (B2), clinical validation (B1), drug-interaction source (P3-B9), renewal supersession policy (A04-O3) |
| Device and language | Physical phone (B10), native Sinhala and Tamil review (B12, including the new English-only replies) |
| Earlier phases | Stripe staging webhook endpoint, refund policy (B6), Firebase, e-mail and SMS providers, OpenAI credits and Gemini limits |

## Integration

| Item | Value |
|---|---|
| PR | **#26** (opened and merged by the owner; GitHub CLI could not be logged in for the agent) |
| Merge commit | `18e8a3272e5079e5a2afd303734479a4abd0c1e1` = `origin/main` |
| CI on `main` | Backend and Mobile success. Admin Web was not triggered because no admin-web change |
| Post-merge smoke | 31 of 31 A04 tests; live probe unchanged from after-fix |
| Deployment | None |

The PR was merged 9 seconds after it was opened, before its Backend check finished; that check then passed, as it already had for the same code (`51bdaa3`). Details: `A04_GIT_INTEGRATION_REPORT.md`.
