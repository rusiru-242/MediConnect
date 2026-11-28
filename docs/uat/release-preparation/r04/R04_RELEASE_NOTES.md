# MediConnect v1.0.0-academic — Release Notes

**Classification: academic demonstration / engineering preview.** 2026-11-28.

MediConnect is **not** clinically validated software, production-ready healthcare infrastructure, a certified medical device, approved for real patient use, or an autonomous medical decision system, and it makes no claim of medical accuracy.

**Publication status:** prepared as a **local release package only**. No public GitHub release, tag or APK is published, because the historical database credential exposure has no confirmed remediation (see "Security" below).

## Purpose

This release demonstrates the engineering of a full-stack healthcare platform with a hybrid agentic AI layer and human-controlled clinical and financial workflows, for academic assessment and a recorded demonstration. It runs locally with synthetic data and Stripe test mode.

## What's included

| Area | Features |
|---|---|
| Patient (Android) | AI Health Assistant with emergency triage; contextual doctor discovery (English, Sinhala, romanised Sinhala); multi-step booking with explicit confirmation and Stripe test payments; medicine package image analysis (optional vision provider); medication, appointment, follow-up and medical-test reminders (in-app); prescriptions and renewal requests; profile data and secure profile pictures; notifications; Help and Support; Emergency SOS |
| Doctor (Android) | Dashboard, schedule, queue and consultations; consultation preparation; clinical notes signed by the doctor; prescriptions with allergy and active-medicine checks; renewal review; care plans and follow-ups; approved reminder messages; profile picture |
| Admin (web) | Dashboard and analytics; doctor management and verification; appointment, payment, refund and reconciliation monitoring; fraud signals for human review; customer support; system and notification monitoring; audit logs |

## Hybrid agentic AI architecture

MediConnect has **38 AI-assisted, automation and shared infrastructure components**:

| Class | Count |
|---|---|
| LLM-assisted agents | 2 |
| Hybrid agents | 2 |
| Deterministic workflow assistants | 15 |
| Rule-based automation services | 13 |
| Shared infrastructure components | 6 |

**LLM paths:**
- Seven components have an optional, bounded LLM path; the other 31 are deterministic.
- Gemini was exercised live (text and vision, synthetic data) in authorised earlier tests.
- OpenAI live generation was not run (no account credits).
- The final verification used the deterministic engine without live AI calls.

## Milestones

| Phase | Milestone |
|---|---|
| Phases 01–05 | Stabilisation of AI entry points, booking and payments, doctor and admin systems, security, encryption and scheduler |
| A01–A05 | Agent completion: AI intelligence and medicine vision; reminders and notifications; booking and payments; prescription assistant; fraud signals and customer support |
| R01 | Branding, logo and splash screen |
| R02 | Secure profile pictures; invented profile data removed; navigation and dark-mode fixes |
| R03 | Final system verification; six defects fixed, including invented doctor ratings and false verification claims |
| R04 | This academic release preparation: README, setup guide, architecture overview, demonstration APK and admin build |

## Verification (R03, the final engineering verification)

| Measure | Result |
|---|---|
| Automated tests | **1,477 passed in R03** (backend 1,064 on a fresh database, Flutter 362, admin 51); 0 failed, 0 skipped; 0 unintended provider connections |
| Components | **29 locally verified**, **9 partially verified**, 0 blocked |
| Defects | 340 tracked items; 262 confirmed defects, **261 recorded as fixed**, 1 open (BUG-039, a product decision) |
| Workflows | Patient, doctor and admin workflows, six cross-role workflows and ten AI safety scenarios verified locally |

**About the fixed defects:** they are fixed with automated regression tests. Some still await a physical-device, external-provider or clinical check, which the tracker records per item.

R04 is a release-preparation phase. Its own newly run checks are listed separately in `R04_BUILD_VERIFICATION.md`.

## Safeguards

**Human-controlled workflows:**
- A booking needs the patient's explicit Accept.
- Payments are taken only through Stripe, for server-set amounts.
- Refunds need an admin decision and are idempotent.
- Prescriptions and renewals are decided by the doctor, with nothing pre-filled.
- Fraud signals never act on an account.
- Support replies are sent by an administrator.

**Privacy and security:**
- Role and object-level authorisation.
- Clinical data only with a care relationship.
- Encrypted documents and profile pictures, with metadata removed from pictures.
- Refresh-token rotation and logout revocation.
- Role allow-lists for AI tools; prompt-injection handling.

## Known limitations

| Area | Limitations |
|---|---|
| Clinical | No clinical validation; no pharmacist review; no validated drug-interaction source; image analysis tested on synthetic packaging only; Sinhala and Tamil wording not reviewed by native speakers |
| Security | **Historical database credential exposure without confirmed rotation (critical)**; provider keys to rotate |
| Providers | Firebase push, external e-mail and SMS not configured; OpenAI without credits; Gemini free-tier limits; no Stripe staging webhook endpoint |
| Infrastructure | Single-server local encrypted storage; no backup and restore, production monitoring or production security configuration |
| Product decisions | Doctor consultation fee (BUG-039: no entry or edit path; default LKR 2,500); refund and cancellation policy; fraud thresholds; free-text messaging scope |
| Devices | Android emulator only; no physical phone, physical camera or iOS run |

## Installation

See [`docs/DEVELOPER_SETUP.md`](../../../DEVELOPER_SETUP.md).

**Requirements:**
- Python 3.12+
- Node.js 20+
- Flutter (Dart ≥ 3.7)
- Android SDK with an emulator
- a local MongoDB

**Demonstration APK:**
- a **debug** build for the **Android emulator only** (`API_BASE_URL=http://10.0.2.2:8001`);
- not signed for distribution and not a production release.

## Demonstration restrictions

- Run only on a local machine with the local `mediconnect_uat` database and synthetic accounts.
- Use no real patient data or photographs, and make no live payments.
- Live Gemini, Gemini Vision and Stripe test-mode calls need separate authorisation for the demonstration.
- Don't expose the backend on a public network while the credential incident is open.
