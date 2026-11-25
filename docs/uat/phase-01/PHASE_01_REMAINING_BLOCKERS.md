# Phase 01 — Remaining Blockers and Untested Items

2026-11-25 · branch `fix/phase-01-patient-ai-ui-stabilization`

| # | Item | Status | Why it is incomplete | What is needed | Blocks Phase 02? | Manual action? |
|---|---|---|---|---|---|---|
| B1 | Clinical approval of the triage, first-aid, cough, prevention and mental-health content | BLOCKED | Needs qualified clinicians | Clinician and mental-health review; sign-off recorded | No (blocks clinical pilot and production) | Yes |
| B2 | Pharmacist approval of medicine cards and situation notes | BLOCKED | Needs a pharmacist | Pharmacist review of `medicine_knowledge.py` content | No (blocks pilot) | Yes |
| B3 | Native-speaker review of the new Sinhala and Tamil strings (emergency guidance, crisis text, dashboard) | NOT RUN | Needs a native reviewer (BUG-004 scope) | Review and corrections | No | Yes |
| B4 | Live LLM provider verification of the bounded intent layer | BLOCKED | No working Gemini or OpenAI key in UAT (see UAT_ENVIRONMENT_SETUP §6); only mocked providers were tested | A valid key with a usage budget, a privacy decision on sending patient messages, then a test with `-AiProvider gemini` | No | Yes |
| B5 | Live Vision (medicine image) analysis | BLOCKED | `AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED=false` by design; privacy approval needed | Privacy approval, a provider key, synthetic packaging photos | No | Yes |
| B6 | Cancel during an image upload on a device | NOT RUN (device) | The local backend replies in under 0.4 s, so Cancel cannot be tapped in time | Throttled network or a slow provider; covered by widget test | No | Optional |
| B7 | Sinhala-script typing on the device | NOT RUN (device) | adb cannot type Sinhala script; display was verified with messages sent through the API | A manual test on a phone with a Sinhala keyboard | No | Yes |
| B8 | Physical phone (not emulator) and small-screen device testing | NOT RUN | Only the Android 17 emulator was available | Manual UAT P-17 and P-01 on a real phone | No | Yes |
| B9 | DevTools frame-timing profile | NOT RUN | Not captured | Optional profiling session | No | Optional |
| B10 | Follow-up "I'm safe / I'm not safe" crisis flow | NOT IMPLEMENTED (proposed improvement) | Needs a clinical design decision | Clinician-designed flow | No | Yes |
| B11 | Backend reply language after a Sinhala emergency follow-up (English reply), and the English-only `urgencyReason` | OPEN (recorded, BUG-004 scope) | Backend language memory; not changed in this phase | Language-aware follow-up texts | No | No |
| B12 | Exact descriptions of the owner's working bug IDs 49–63 | NOT RECONCILED | Not present in the repository | The owner's list, to map onto P01-nn IDs | No | Yes |
| B13 | `test/integration/live_api_test.dart` | NOT RUN | Hard-wired to port 8000 (the production-like database) | Make the port configurable (8001) | No | No |
| B14 | GitHub Actions for the final commits | See the final report §10 | — | — | — | — |

Phase 02 can start: none of these block the booking, payment or patient-care work. B1, B2, B4, B5 and B8 block a clinical pilot and any production release.
