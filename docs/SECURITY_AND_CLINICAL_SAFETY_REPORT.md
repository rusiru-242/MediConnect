# Security & Clinical Safety Report

Branch `fix/comprehensive-system-ai-stabilization` · 2026-11-24 · Scope: baseline security review and clinical-safety fixes made during stabilization. **This is not a penetration test or a clinical validation.**

## 1. Release blockers (real-patient use)

1. **Clinical validation of emergency triage (BUG-013).** The new detector is software-tested only: 26 positive multilingual cases, 12 false-positive controls, context and API tests. A qualified clinician must review the red-flag categories, the Sinhala and Romanized vocabulary, the negation and historical rules, and the guidance wording. A clinician-labelled multilingual test set should then be run.
2. **Pharmacist review of all medicine content (BUG-016/017).** Every card is flagged `contentReviewStatus: PENDING_PHARMACIST_REVIEW`. Content was corrected to remove universal dose statements, but it was not sourced from a formal reference in this session.
3. **Clinical review of symptom-guidance text (BUG-012/018).** The self-care advice, red flags and "when to see a doctor" thresholds in `agents/clinical_intent.py` (for example, "fever for 2 days or more: see a doctor, consider dengue testing") need clinician sign-off.
4. **Privacy approval for external AI providers.**
   - Medicine label photos go to Gemini or OpenAI when `AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED=true` (default true).
   - Labels can contain patient names; the prompt tells the model not to transcribe personal data, but that cannot be guaranteed.
   - Before real use: get a data-processing agreement and a lawful-basis review, or set the flag to `false` (uploads are then answered truthfully with "not analysed").
5. **Live verification of Stripe (test mode), FCM, email and SMS.** See the final report.
6. **Native-speaker review of Sinhala output (BUG-004).**

## 2. Security controls verified (code review and automated tests)

| Control | Evidence | Result |
|---|---|---|
| Password hashing | `utils/security.py` uses bcrypt with salt | OK |
| JWT secret strength in production | `main.py` startup check (at least 32 bytes) | OK |
| Access and refresh tokens | refresh rotation in `auth_service.py`; mobile single-flight refresh in `api_client.dart` | OK. **Fixed**: multipart uploads now refresh and retry (BUG-025) |
| Token storage (mobile) | `flutter_secure_storage` | OK |
| Role-based access | `require_patient`, `require_doctor` and admin dependencies; AI tools filtered by role | OK (test_production_security_audit, test_phase7) |
| Object-level authorization | conversations filtered by `patientUserId` (test: other patient gets 404); medical records isolation tests | OK |
| AI tool authorization | fixed read-only tool registry, Pydantic arguments with `extra=forbid`, `AISafetyGuard.validate_tool_call`, bounded loop | OK |
| Prompt injection | model receives server-owned filters; tool results are reduced to public fields; final doctor list comes from the trusted ranked search; the system prompt forbids following instructions in results | Reduced risk. The model output is used only for tool choice and an approved one-line reply. |
| Stripe webhook | `stripe.Webhook.construct_event` signature check; idempotency keys for intents and notifications | OK in code; live webhook replay not tested |
| Payment amount integrity | amount taken from the server-side doctor fee or the accepted proposal. **Fixed**: no default LKR 2,500 charge (BUG-028) | OK |
| File upload validation | extension, magic bytes, 5 MB limit; images are no longer written to disk (BUG-035) | OK |
| NoSQL injection | user text goes into `re.escape` for regex filters; IDs validated with `ObjectId.is_valid` | No issue found in reviewed paths |
| Secrets | `.env` is git-ignored and not tracked; no keys printed. **Fixed**: Gemini Vision key moved from the URL query to a header | OK |
| CI database isolation | **Fixed** (BUG-034): CI always uses the disposable MongoDB container | OK |
| Sensitive logging | AI tool logs record only tool name, outcome and duration; `redact()` strips tokens, emails and phone numbers | OK |

## 3. Remaining security risks (for the dedicated security audit)

| Risk | Severity | Notes |
|---|---|---|
| AI rate limiter is in-memory per process (BUG-038) | Medium | Not shared across workers or instances; resets on restart. Use Redis or MongoDB TTL buckets. |
| `ALLOWED_ORIGINS` defaults to `*` (combined with an explicit list) | Medium | Set explicit origins in production; check that credentials and wildcard combinations are rejected. |
| Background workers run inside the API process | Low/Medium | Leases prevent duplicate sends, but scaling to N API processes runs N schedulers. Consider a single worker deployment. |
| Dependency vulnerabilities not scanned | Unknown | Run `pip-audit`, `npm audit` and `flutter pub outdated`. 45 Flutter packages have newer incompatible versions. |
| Secrets scanning not automated | Unknown | Add gitleaks or trufflehog to CI. |
| `/ai/booking/upload-image` legacy endpoint still stores files to disk | Low | Not used by the current app; remove or align with BUG-035. |
| Audit-log completeness for clinical edits | Unknown | Note signing and amendment exist; a full audit-trail review is pending. |
| Live webhook replay and timestamp tolerance | Unknown | Verify with Stripe CLI in test mode. |

## 4. Clinical safety: emergency detection results (software tests)

`backend/tests/test_comprehensive_stabilization.py`. All pass.

| Category | Languages covered by tests |
|---|---|
| Cardiac (chest pain, pressure, heart attack) | EN, SI script, Romanized, mixed |
| Respiratory (can't breathe, difficulty breathing) | EN, SI, Romanized |
| Stroke signs | EN, Romanized |
| Unconscious or collapse | EN, Romanized |
| Severe bleeding | EN, SI |
| Seizure | EN, Romanized |
| Anaphylaxis | EN |
| Poisoning or overdose | EN, Romanized |
| Self-harm (with 1926 / Sumithrayo guidance) | EN, SI, Romanized |
| Snakebite | EN, Romanized |
| Context: a follow-up after an alert stays escalated; symptoms split across turns are escalated; "I'm fine now" ends the escalation | EN, Romanized |
| False-positive controls: negation, historical, informational questions, blood pressure, breathing exercises, mild exertional breathlessness, food poisoning | EN, Romanized |

**Design choices that need clinical review:**
- When in doubt, the detector escalates (for example "burning chest" is escalated).
- Mild, exertional breathlessness is not escalated.
- Food poisoning is not escalated.
- Snakebite is always an emergency.
- Fainting is escalated.

## 5. Medication safety findings

- Removed the universal "8 tablets / 4000 mg per day" statement (English and Sinhala) and added eligibility-aware wording plus overdose escalation "even without symptoms" (BUG-017).
- Formulation and strength pairs are labelled per dosage form (BUG-016).
- Prescription, exact-dose and treatment-duration requests are refused, with an explanation and antibiotic-misuse risks (BUG-018).
- Medicine-image output separates text read from the photo from reference information, never identifies loose tablets, and always recommends pharmacist verification (BUG-023).
- **Not done:** an interaction checker (no verified interaction source exists in the repo, so none was invented) and a formal reference citation for each medicine.

## 6. External provider privacy considerations

| Data | Provider | When | Control |
|---|---|---|---|
| Doctor-search request (filters only, no free-text symptoms when filters exist; redacted otherwise) | Gemini or OpenAI | Patient AI search, if a key is configured | `orchestrator.redact`, server-owned filters |
| Medicine label photo | Gemini Vision or OpenAI vision | Image upload | `AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED`; prompt asks the model to omit personal data; no storage |
| Health-chat guidance text | Gemini (if configured) | Health chat | Pre- and post-generation safety filters |
