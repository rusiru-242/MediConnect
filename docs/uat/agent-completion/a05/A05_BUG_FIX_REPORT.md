# A05 — Bug Fix Report: Fraud Detection (Agent 25) and Customer Support (Agent 26)

For: reviewers and maintainers. 2026-11-28, branch `fix/agents-a05-fraud-support`, started from `origin/main` `18e8a32`.

**Summary:** 14 confirmed defects, all fixed with automated regression tests (3 High, 9 Medium, 2 Low). Missing workflows that were known limitations rather than defects are listed separately, as are 3 changed test expectations and 10 observations.

**How the defects were found:**
- Reading the code against the A05 requirements.
- The new backend tests, run on unchanged `main`.
- A reproduction script run on both code versions (`a05_repro_fraud.py`).
- The live UAT probe.
- The admin browser run and the emulator run.

**Evidence labels:**
- **Repro:** `evidence/a05_repro_fraud_pre_fix_main.json` against `evidence/a05_repro_fraud_a05_branch.json`.
- **Probe:** `evidence/a05_probe_uat.json`.
- **Browser:** `evidence/a05_browser_admin_*.json`.
- **Emu:** `evidence/emulator/a05_e*`.

## Defects

| ID | Sev. | Component | Defect (how it was found) | Root cause | Fix | Test / evidence |
|---|---|---|---|---|---|---|
| A05-BUG-001 | High | Agent 25 detection | Fraud rules ran only when an administrator called `POST /security/fraud/assessments/evaluate` with an account id, so **no signal appeared unless the account was already suspected** (code audit; no caller other than that endpoint) | No scheduler or event called `evaluate_account_risk` | `FraudDetectionService.run_detection_sweep` re-evaluates recently active accounts (bookings, cancellations, payments, refunds, sign-in failures) from the existing background worker, every `FRAUD_SWEEP_INTERVAL_SECONDS` (300 s). It reads stored records only, takes no action, and can be repeated or restarted safely | `test_f01`, `test_f03`, `test_f09`; Probe F03b: the worker raised the signal 260 s after the activity |
| A05-BUG-002 | High | Agent 25 alerts | **Simultaneous evaluations of one account stored one alert each.** Repro: 6 parallel evaluations stored **6** open assessments; the A05 branch stores 1 | Check-then-insert duplicate prevention (`find_one` then `insert_one`) with no database constraint | Unique partial index on `openKey` (set while an assessment is open, removed when a reviewer closes it). A losing insert refreshes the open assessment. Reopening a closed assessment while another is open returns 409 | `test_f08` (6 threads in lockstep → 1); Repro 6 → 1 |
| A05-BUG-003 | Medium | Agent 25 alerts | **A dismissed alert came straight back** from the same evidence on the next evaluation (Repro: `true` → `false`), so every sweep would re-raise what a reviewer had cleared | Rules always looked at the full time window, regardless of earlier decisions | Only activity after the account's latest closing decision counts toward a new signal; new activity can still raise one | `test_f07`; Repro |
| A05-BUG-004 | High | Agent 26 privacy | **Patients received the internal admin draft** in their ticket responses. It contained the suggested reply, the internal handling notes with the linked booking's status and payment state, and the assigned admin id (create, list and detail) | The patient endpoints returned the whole ticket document | `ticket_view` returns `aiDraft` and `assignedAdminId` to administrators only; internal duplicate keys are never returned | `test_c02_c05`; Phase 5 changed expectations below; Probe C02 `aiDraftReturnedToPatient: null` |
| A05-BUG-005 | Medium | Agent 26 tickets | **The category the patient chose was overwritten** by the keyword guess (a "payment" ticket about a password became "account access"), and **any string was stored as the category** (`"free_money"` → 201) | The triage result was written over `category`; the schema took `Optional[str]` | The category is limited to the defined values (otherwise 422). The guess only replaces "general support" and is always kept in the admin draft | `test_c03[payload4]`, `test_c03b`; Probe C03 |
| A05-BUG-006 | Medium | Agent 26 tickets | **A double tap or a retry after a timeout created duplicate tickets** (5 simultaneous identical submissions → 5 tickets on main) | No duplicate check | A unique partial index on `openDedupeKey` (hash of requester, subject and message) while the ticket is open. A duplicate gets 409 with the existing ticket id; after resolve or close the same text can be raised again | `test_c15` (5 concurrent → 1 × 201, 4 × 409); Probe C15a |
| A05-BUG-007 | Medium | Agent 26 messages | **A repeated admin reply was stored twice and notified the patient twice**; the same was possible for requester messages | Unconditional `$push`; the notification idempotency key used the millisecond timestamp | One atomic conditional update per message: the same text from the same sender within 2 minutes is stored once. One notification per stored message (key = message id) | `test_c15`; Probe C09-C15b (2 sends → 1 message, 1 notification); Browser (double-click → 1 message) |
| A05-BUG-008 | Medium | Agent 26 notifications | **The "Support ticket update" notification could not open the ticket**: it carried no ticket reference, so tapping it did nothing | Notifications had no field for a ticket | `relatedTicketId` is stored and returned. The mobile app opens `/patient/support/ticket` for it. The notification is in-app only (`send_push=False`) | Flutter `A05-C20`; `test_c06_c13`, `test_c21`; Emu a05_e06 → e07 |
| A05-BUG-009 | Medium | Agent 26 templates | **The refund template stated a financial fact it never checked**: "No refund has been approved yet". The general template promised "We are actively investigating … will provide an update shortly" | Fixed wording, no lookup | Refund template: "This message does not approve or decline a refund. Refund requests are decided by the MediConnect team …". General template: "a member of the support team will review it". Neither states a payment or refund status | `test_c18_c19`; Probe C18-C19 |
| A05-BUG-010 | Medium | Agent 25 rules | **Ordinary payment retries raised a review signal.** Four attempts on one slot after card failures (each hold released) triggered `RAPID_CANCELLATION_PATTERN` (Repro and `test_f05` on the first A05 run) | The rule counted every cancelled appointment, including unpaid holds released by the patient or expired by the system | The rule counts only the patient's own cancellations of bookings. Unpaid holds are assessed by the slot-hoarding rule, which counts **distinct** slots | `test_f05`, `test_f04`; Repro |
| A05-BUG-011 | Low | Admin web | **A double-click on "Send reply" sent two requests** (Browser UAT: 2 POSTs; the server stored one). "Record decision" on a fraud review had the same gap | The button is disabled only after React re-renders | An in-flight guard (`useRef`) on both actions | Admin `a05FraudSupport` (double-click → 1 call); Browser recheck: 1 POST (`a05_browser_admin_reply_after_fix.json`) |
| A05-BUG-012 | Medium | Admin web | **Rule-based templates were presented as AI output**: "AI-Assisted", "AI Support Intelligence", "AI draft response generated", "AI-classified … inquiries". Opening a ticket also pre-filled the reply box with the template | Labels written for an LLM that is not used on this path | Labels now say "Rule-based triage" and "Suggested reply (template, rule-based)". The reply box starts empty; "Insert suggested reply" fills it on request, and the admin edits and sends it | Admin `a05FraudSupport`; Browser a05_b04/b05 |
| A05-BUG-013 | Low | Agent 26 status | After an admin replied, the ticket said **"in progress"**, so the patient could not tell that support had answered. Follow-ups stayed buried because the queue was sorted by creation time | The default reply status was `in_progress`; the list was sorted by `createdAt` | Default after a reply: `waiting_for_user` ("Support replied"). A requester message moves the ticket back to `open`. Queues are sorted by latest activity, with `awaitingReplyFrom` shown | `test_c06_c13`, `test_c14`; Probe C10, C11-C13; Browser "Requester replied" |
| A05-BUG-014 | Medium | Admin web, Agent 25 | **The fraud review screen showed no evidence or history.** It offered only "Dismiss" and **"Confirm Fraud"**, presenting a rule hit as an established finding; "investigate" and "resolve" existed only in the API | The UI showed only the explanation string; there was no evidence field | Stored per-rule evidence (`ruleEvidence`: threshold, observed value, references, slot rows), shown with the review history. Four decisions: Dismiss (not suspicious), Investigate, Resolve, Confirm finding (human decision). A note states that a decision changes only the review record | Admin `a05FraudSupport`; Browser a05_b02 |

## Changed files

| Defect | Files |
|---|---|
| 001 | `backend/app/services/fraud_detection_service.py`, `backend/app/main.py`, `backend/app/config/settings.py` |
| 002, 003, 010 | `backend/app/services/fraud_detection_service.py`, `backend/app/models/fraud_assessment.py` |
| 004, 005, 006, 007, 009, 013 | `backend/app/services/support_ticket_service.py`, `backend/app/routes/admin_workflow.py`, `backend/app/schemas/admin_workflow.py`, `backend/app/models/support_ticket.py` |
| 008 | `backend/app/models/notification.py`, `backend/app/schemas/notification.py`, `backend/app/services/notification_service.py`, `backend/app/services/support_ticket_service.py`, `mobile/lib/models/notification_model.dart`, `mobile/lib/screens/notifications/notifications_screen.dart` |
| 011, 012 | `admin-web/src/pages/SupportTicketsPage.tsx`, `admin-web/src/pages/MonitoringPage.tsx`, `admin-web/src/types/adminWorkflow.ts`, `admin-web/src/api/adminWorkflowApi.ts` |
| 014 | `admin-web/src/pages/MonitoringPage.tsx`, `admin-web/src/api/securityMonitoringApi.ts`, `backend/app/schemas/security_monitoring.py` |

## Missing workflows implemented (known limitations, not counted as defects)

| Item | Former limitation | Implementation |
|---|---|---|
| Slot-hoarding rule | P04-N12: `SLOT_HOARDING_ATTEMPT` declared, never evaluated | `slot_hoarding_evidence`: unpaid reservations of **distinct** slots within the window (expired unpaid, released before payment, still held). Paid, free, doctor- or admin-cancelled bookings and repeated attempts on one slot are not counted. Weight 25 (MEDIUM tier) |
| Patient replies | P4-B8 scope: no requester reply | `POST /admin/workflow/tickets/{id}/messages` (own ticket only; closed → 409; resolved or waiting → open) |
| Mobile support UI | None | Profile → Help & Support: list, create (category, subject, message), thread, reply. Plain-text rendering; loading, empty, error, retry and closed states |
| Patient chat support intent | Support questions fell through to the doctor search | `support_request` lists the patient's own tickets through the role-checked `get_my_support_tickets`. `support_action_request` refuses refund approval, password reset and account unlock |
| Emergency routing in support | Only the admin draft flagged it | A ticket or reply that may describe an emergency is marked urgent and shows the requester the 1990 notice (existing keywords plus the assistant's `detect_emergency`) |
| Admin status change | None without a message | `POST /admin/workflow/tickets/{id}/status` (admin only; audited) |

## Changed test expectations

| Test | Before | After | Why |
|---|---|---|---|
| `test_phase04_admin_system.py::test_n22_re_evaluation_returns_current_rules_and_explanation` | Rules {failed payments, booking rate}, 65.0/100 | Rules also include `SLOT_HOARDING_ATTEMPT`, 90.0/100, "Triggered 3" | The fixture's six unpaid holds on six distinct slots now meet the new rule. What N22 checks (refreshed rule list and explanation, no duplicate) is unchanged |
| `test_phase5_admin_ai_automation.py::test_customer_support_ticket_workflow_and_ai_draft` | The patient's create response contains `aiDraft` | Patient response `aiDraft is None`; the admin view contains it | A05-BUG-004 |
| `test_phase5_admin_ai_automation.py::test_emergency_ticket_ai_draft_escalation` | Emergency draft read from the patient response | Patient gets `safetyNotice` with 1990; draft checked on the admin view (still URGENT, flag, 1990) | A05-BUG-004 plus the new safety notice |

No assertion was removed or weakened. Each moved assertion is checked on the administrator's view.

## Pre-fix evidence

- **Repro:** `a05_repro_fraud.py`, run against a detached worktree of `main` `18e8a32` and against the A05 branch, each on its own fresh `_test` database. Results:

  | Check | `main` | A05 branch |
  |---|---|---|
  | 6 parallel evaluations | 6 alerts | 1 |
  | Re-raised after dismissal | true | false |
  | 4 retries on one slot | `RAPID_CANCELLATION_PATTERN` | none |
  | 4 distinct unpaid slots | only `RAPID_CANCELLATION_PATTERN` | `SLOT_HOARDING_ATTEMPT` |

- **The new backend tests on `main`:** 23 of 27 fail (`evidence/a05_tests_on_pre_fix_main.txt`).
  - **Not reproductions:** most fraud tests fail because the A05 sweep and helper methods do not exist on `main`, so they are not counted as defect reproductions.
  - **Behavioural failures on `main`:**
    - the patient receives the draft (C02);
    - an unknown category is accepted (C03);
    - the chosen category is overwritten (C03b);
    - a duplicate ticket returns 201 (C15);
    - the reply endpoint does not exist, so 404 (C16);
    - the refund template claims a refund status (C18);
    - the chat has no support answer (C18c).

## Observations (not fixed in A05)

| ID | Observation |
|---|---|
| A05-O1 | The patient Profile screen shows hard-coded health data that is not the patient's: height 5'7", weight 134 lbs, BMI 21.0, **"Allergies: Penicillin"**, "Emergency Contact: Spouse", plus a "Calling …" snackbar that calls no one. It is outside A05 scope (profile management is the next release phase), but a fabricated allergy on a patient screen should be fixed before release |
| A05-O2 | In UAT the slot-hoarding rule flagged `uat.p02.patientb`, whose earlier A03 test session had released four unpaid holds that day. The rule applied correctly to the data, but it shows that QA or exploratory booking can trip the provisional threshold. A signal is review-only; calibration needs real data |
| A05-O3 | The explanation counts supporting references with at most 5 per rule ("Supported by 5 event reference(s)") while the evidence can show 6 observed slots. Cosmetic; the evidence list is complete |
| A05-O4 | The pre-existing `BRUTE_FORCE` security event uses check-then-insert, so two simultaneous failed logins could record it twice. It is a monitoring event only, with no account action |
| A05-O5 | Administrators get no in-app notification for a requester's follow-up. The ticket moves to the top of the queue with a "Requester replied" badge |
| A05-O6 | Doctors can create tickets through the API but have no support screen in the doctor app |
| A05-O7 | Support screens, templates and chat answers are English only (native-language review B12) |
| A05-O8 | The admin ticket queue loads the 50 most recently active tickets and has no paging controls |
| A05-O9 | Text an admin appends to the template appears after the template's signature unless the admin moves it; editing convenience only |
| A05-O10 | The mobile ticket thread does not refresh by itself; pull to refresh or reopen it (a notification opens the current state) |
