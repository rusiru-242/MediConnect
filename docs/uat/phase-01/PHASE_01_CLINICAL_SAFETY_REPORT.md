# Phase 01 — Clinical Safety Report

For: the project owner and the clinical, pharmacist and mental-health reviewers who must approve content before any real-patient use. 2026-11-25.

**Status: not clinically approved.** All triage, first-aid, medicine and mental-health content changed in this phase is marked **PENDING CLINICAL REVIEW** (pharmacist review for medicine content). The automated tests prove the software behaves as designed. They do not prove the clinical content is correct.

## 1. Emergency detection

**Architecture (unchanged in principle):**
- Deterministic and rule-based, in English, Sinhala script and Romanized Sinhala.
- It runs **before** any routing, search, booking, medicine or wellness logic in both the AI Assistant (`booking_agent.py`) and the Health Chat (`health_assistant_agent.py`).
- The LLM is never asked whether something is an emergency.

**Verified behaviour.** Unit tests and the real local UAT API agree; the probe is in `api-probe-after.json`.

| Input | Result |
|---|---|
| "I have severe chest pain and difficulty breathing. What should I do?" | Emergency, cardiac |
| "mata papuwa godak ridenawa. husma gannath amarui. mama mokakda karanna one?" | Emergency, cardiac (Sinhala reply) |
| "මගේ පපුව ගොඩක් රිදෙනවා. හුස්ම ගන්නත් අමාරුයි. මම මොකද කරන්න ඕනේ?" | Emergency, cardiac (Sinhala reply) |
| "thaththa sihiya nathi wuna" | Emergency, unconscious (another person) |
| "mata marenna hithenawa" / "I want to kill myself" / "මට මැරෙන්න හිතෙනවා" | Mental-health crisis (self_harm) |
| "My chest is very tight." → "What should I do?" | Emergency kept from context |
| "My chest is very tight." → "What are the symptoms of a heart attack?" | Emergency kept from context (not weakened) |
| "I accidentally took 10 paracetamol tablets" / "my son swallowed some tablets" | Emergency, poisoning (**was not escalated before**) |
| "I have no chest pain, just a cough." | Not an emergency (negated) |
| "I had chest pain last year but I am fine now" | Not an emergency (historical) |
| "What are the common symptoms of a heart attack?" / "What causes a stroke?" / "Is a stroke dangerous?" | Information plus "If you or someone near you has these symptoms now, call 1990" (**was an alarm before**) |
| "What should I do if someone has chest pain?" | Hypothetical: information with conditional escalation |
| "How can I prevent heart disease?" | Prevention information |
| "What are the warning signs of suicide?" | Informational |
| "what if I want to end my life" | Treated as a crisis: suicide questions are only informational when clearly about third-party facts |

**How false positives were reduced without weakening detection:**
- Suppression requires an informational or hypothetical *structure* **and** no sign of current personal experience. "I'm having / my chest / my father / right now" all keep the escalation.
- Context escalation is not bypassed.
- The legacy keyword safety nets still run when the new detector does not suppress.

**Routine booking is never offered during an emergency.** The emergency branch returns before search. The app hides routine chips during an emergency.

## 2. Category-specific guidance (BUG-044)

- Each of the 11 categories has its own first-aid steps after "Call 1990 now or go to the nearest ETU". Examples:
  - **Stroke:** note the time and check FAST.
  - **Snakebite:** keep the limb still; do not cut, suck or tie.
  - **Poisoning:** go even if you feel well; do not induce vomiting; bring the container.
  - **Seizure:** do not restrain or put anything in the mouth.
- Steps are written in English and Sinhala. The Tamil emergency text is unchanged from before.
- **Needs:** clinical review of every step, plus native-speaker review of the Sinhala.

## 3. Cough tiers

A cough lasting 3 weeks or more is now **"see a doctor within a day or two"**, not "call 1990". The 1990 tier keeps only danger signs: severe breathlessness, struggling to speak, blue or grey lips, chest pain, or more than a streak of blood. The reply states that a long cough alone is not an ambulance emergency. **Needs:** clinical review of the thresholds (38 °C for more than 3 days, "streak" of blood).

## 4. Mental-health crisis response

**Requirement check (backend text plus app UI):**

| Requirement | Implementation |
|---|---|
| Compassionate, non-judgemental | "I'm really glad you told me. What you're feeling matters, and you deserve support right now." |
| Does not imply the chatbot resolves the crisis | "I'm an automated assistant, so I can't give you the care a person can" |
| Brief question about immediate safety | "**Are you safe right now?**" and "tell me whether you are safe right now" |
| Trusted person, not alone | "Reach out to someone you trust and ask them to stay with you. Try not to be alone." |
| Means safety | "If it is safe to do so, move away from anything you could use to hurt yourself…" |
| Verified resources | 1926 and 1333 (see §5) |
| 1990/ETU for imminent danger, injury or overdose | "If you might act on these thoughts soon, or you have already hurt yourself or taken something, call 1990 or go to the nearest hospital ETU now"; app: "In danger now? Call 1990" |
| Escalation not removed for appearance | 1990 is present in the banner text, the reply and the action list |
| Dedicated UI | Purple "You don't have to face this alone" banner, 1926 primary; not the red cardiac banner |
| No automatic calls | Every number → confirmation dialog → `ACTION_DIAL` (pre-fills only); emulator `dumpsys telecom`: 0 calls |
| Languages | English and Sinhala texts (Romanized Sinhala now detected as Sinhala); app strings en/si/ta |

**Needs:** review by a mental-health clinician, and a decision on whether a follow-up "I'm safe" / "I'm not safe" flow should be added (not implemented).

## 5. Phone numbers (verified 2026-11-25)

| Number | Service | Source |
|---|---|---|
| 1990 | 1990 Suwa Seriya free ambulance | Official site 1990.lk |
| 1926 | National Mental Health Helpline, National Institute of Mental Health, 24 hours | NIMH annual report (issuu, nimh.angoda); Newswire 2026 |
| 1333 | CCCline crisis support, CCC Foundation, 24/7, toll free, si/ta/en | Lifeline International; Find A Helpline; Daily Mirror |
| 119 | Sri Lanka Police emergency | police.lk |

**Removed:**
- "Sumithrayo 011 2 696 666": no source found. Sumithrayo is listed elsewhere with other numbers and limited hours.
- "General Emergency: 911": 911 is not a Sri Lankan number.

**Unresolved:** one directory lists 1926 SMS hours as 08:00–16:00. Voice is described as 24 hours by NIMH, so the app says "24 hours" for calls only.

**Recommendation:** re-verify all numbers before each release.

## 6. Emergency call UX

- Assistant (1990), mental-health (1926, 1333, 1990) and Home SOS (1990) all show a localized confirmation dialog first.
- Cancel never dials. Confirming only pre-fills the dialer (`Intent.ACTION_DIAL`). The app has no `CALL_PHONE` permission, and the Android channel accepts only 3–6 digit numbers.
- If no dialer is available, the user is told to dial the number manually.
- **Verified:**
  - Widget tests: 1926, 1333 and 1990 each require confirmation; cancel never dials; the exact number is passed; failure shows the fallback.
  - Emulator: the dialer was pre-filled with 1990 (SOS) and 1926 (crisis), 0 calls.
- No real call was placed at any point.

## 7. Medicine safety

- **No universal doses:** BUG-017 is unchanged, and the new situation notes contain no doses.
- **Overdose escalation:** the detector now escalates overdoses, and the card warning is retained.
- **Antibiotics:** still refused (BUG-018); UAT-API M5 shows `prescription_request_declined`.
- **Situation notes:** child, pregnancy or breastfeeding, liver or kidney disease or alcohol, and combining medicines all add a general "ask a pharmacist or doctor" note.
- **No duplication:** the medicine text no longer repeats the card.
- **Needs pharmacist approval:** every card remains `contentReviewStatus: PENDING_PHARMACIST_REVIEW`.

## 8. AI hallucination and authority boundaries

- Doctor recommendations use only server-side search results: verified doctors, real fees, published reviews and listed experience. Missing data is stated as missing ("Years of experience not listed", "No published patient reviews yet").
- Ranking explanations say they are not a clinical-quality judgement.
- The LLM proposal layer can only propose search preferences, through a strict schema. Emergency, prescription, auth, verification, prices, availability, booking and payments stay server-side.
- Medicine images:
  - Never identified from file names.
  - Never shown as analysed when the provider is unavailable.
  - Loose tablets and blurry images are "unreadable".
  - External processing is disabled by configuration in UAT.

## 9. Authentication, authorization and privacy

- Cross-account access to a conversation is refused (`b01::test_p01_conversation_is_not_visible_to_another_patient`: 403/404).
- Image endpoints require authentication (existing BUG-025 test).
- LLM input is redacted (emails, phone numbers, NIC numbers, "my name is…"), only the current message is sent, and only when the deterministic parser found nothing.
- The UAT probe outputs committed to the repo were checked: they contain no tokens, passwords or account emails.
