# A05 — AI Architecture Verification (Agents 25 and 26)

For: reviewers and anyone describing MediConnect's AI. 2026-11-28.

## Classification

| Agent | Classification | Generative AI? | Provider calls |
|---|---|---|---|
| 25 Fraud Detection | **Deterministic rule engine** with a background sweep, explainable evidence and human review | No | None |
| 26 Customer Support | **Deterministic, tool-orchestrated assistance**: keyword triage, fixed reply templates, role-checked read tools in the patient chat, human-approved sending | No | None |

Both agents are part of MediConnect's hybrid agentic architecture. A bounded LLM may only propose an intent from a fixed list in the chat router; the server validates it and the reply is built from tools. Neither agent is an autonomous LLM agent, and they are not described as one. The admin web page used to label the support templates "AI-Assisted" and "AI Support Intelligence"; A05-BUG-012 corrected that to "Rule-based triage" and "Suggested reply (template, rule-based)". The draft record carries `draftType: "template"`.

## Agent 25 control flow

```
background worker (every 60 s) ── run_detection_sweep (throttled to 300 s)
      └─ recently active accounts ── evaluate_account_risk(account)
              ├─ 7 rules over payments / appointments / refund_requests / security_events
              ├─ score = Σ weights (cap 100) → tier; < 25 → nothing stored
              └─ upsert the one open assessment (unique openKey) with ruleEvidence
admin (require_admin) ── list / review (dismiss | investigate | resolve | confirm) ── audit log
```

**Trusted tools:** the admin assistant's `get_fraud_alerts` and `get_fraud_review_details` read assessments (ADMIN role only). Nothing writes on behalf of an LLM.

**Human approval:** every outcome beyond the signal itself is a human decision recorded in the review history. Account, booking, refund and payment actions are separate manual steps elsewhere in the admin app.

## Agent 26 control flow

```
patient app / API (authenticated) ── create ticket ── rules: category, priority, emergency notice
                                                   └─ fixed template → admin-only aiDraft
admin (require_admin) ── read ticket ── "Insert suggested reply" (on request) ── edit ── "Send reply"
      └─ one atomic message append (duplicates within 2 min stored once) ── one in-app notification
patient chat ── intent router ── support_request → get_my_support_tickets (PATIENT role, own tickets)
                              └─ support_action_request → fixed refusal (no tool, no mutation)
```

**Emergencies:** an emergency in the chat is handled earlier by the existing emergency detector (1990 escalation), before the support intents. In tickets, the same detector plus the existing keyword list marks the ticket URGENT and shows the requester the 1990 notice.

**Separation from clinical assistance:** support refuses medical advice and points to the doctor or the health assistant. It never answers clinical questions.

## Authorization checks (verified)

| Path | Rule | Test |
|---|---|---|
| `/security/fraud/*` | `require_admin` | f13; Probe F13 |
| `GET /admin/workflow/tickets[/{id}]` | Requester sees own; admin sees all; internal fields admin-only | c02, c16 |
| `POST …/tickets/{id}/messages` | Requester only (admin 403) | c16 |
| `POST …/reply`, `…/ai-draft`, `…/status` | `require_admin` | c16 |
| Tool `get_my_support_tickets` | PATIENT role, caller's tickets, minimal fields | c18c |

## Provider fallback

Neither agent calls a provider, so there is nothing to fall back from. With a failing provider injected into the chat, the support answers are identical (C22). In UAT the AI was deterministic (provider keys blanked) and provider usage stayed at 0 Gemini and 0 OpenAI. No live AI authorization was granted or used in A05.

## What is not claimed

- Not machine learning, anomaly detection or a calibrated fraud model.
- Not generated support replies.
- Not autonomous: no agent action changes an account, booking, refund, payment or ticket without a human or the requester acting.
