# Phase 05 — Owner Action Checklist

For: the project owner (and the clinical, pharmacist and language reviewers you appoint). Only tasks that cannot be done safely by engineering are listed. 2026-11-26.

Legend — **Blocks:** S = blocks staging, P = blocks production, C = blocks a clinical pilot.

## 1. Critical (do first)

| # | Task | Why | Exact action | Prerequisites | How to verify | Blocks |
|---|---|---|---|---|---|---|
| 1.1 | **Rotate the MongoDB credentials exposed in public git history (P5-C1)** | The real `MONGODB_URI` (user and password) is in commit `a41b659` (`backend/.env.example`), reachable from `origin/main` of a public repository | Atlas → Database Access: change that user's password or replace the user with a new least-privilege user; update `backend/.env` and deployment secrets. Atlas → Network Access: remove `0.0.0.0/0` if present | Atlas owner login | Old URI fails to authenticate; app works with the new secret | S, P |
| 1.2 | Review database access since 2026-09-30 | Third parties could have connected | Atlas activity feed / access logs (tier permitting); look for unknown IPs and unexpected writes or deletions | 1.1 | Written note of findings | S, P |
| 1.3 | **Remote-database incident inspection (P4-B1)** | Nov 25 test run may have written to/deleted from `mediconnect`, sent e-mails, created/dropped `mediconnect_phase*_test` | Follow `docs/uat/phase-04/PHASE_04_DATABASE_INCIDENT_REVIEW.md` §4–6 (read-only queries first, backup before any cleanup) | 1.1 (use the new credentials) | Completed checklist in that document | S, P |
| 1.4 | Decide on git history rewrite | History still contains the old credential | Optional: `git filter-repo` on a fresh clone + force-push, after 1.1. Rotation is what actually protects you | Explicit decision | `secret_history_scan.py` shows no match | — |
| 1.5 | **Rotate SMTP, Gemini and OpenAI credentials (P4-B2)** | Printed in part in Phase 02; the Nov 25 run could have used them | Provider consoles: create new keys/passwords, revoke old ones; store in a secret manager | Provider logins | Old keys rejected | S, P |
| 1.6 | Replace the development `JWT_SECRET` | 11-character common word; tokens could be forged for any backend using it. The backend now refuses to start with it | `python -c "import secrets; print(secrets.token_urlsafe(48))"` → `JWT_SECRET` in `backend/.env` | — | Backend starts; old tokens invalid | S, P |
| 1.7 | Configure secure deployment settings | New fail-closed start-up rules | Set `ENVIRONMENT=production` (or `staging`), strong `JWT_SECRET`, `DOCUMENT_ENCRYPTION_KEYS` (generate with `python -m scripts.encrypt_existing_documents --generate-key prod-1`), `ACCESS_TOKEN_EXPIRE_MINUTES` ≤ 60, `ALLOWED_ORIGINS`, a secrets manager for keys | 1.5, 1.6 | `/api/health` healthy; start-up refuses a weak config | S, P |
| 1.8 | Encrypt existing uploaded documents in each deployed environment | B8 encrypts new uploads only | Back up `uploads/`, then `python -m scripts.encrypt_existing_documents` (dry run) → `--apply`; keep the key safe (losing it loses the files) | 1.7, backup | Dry run shows 0 plaintext; documents open in the app | P |

## 2. External integrations

| # | Task | Why | Exact action | Verify | Blocks |
|---|---|---|---|---|---|
| 2.1 | Stripe webhook delivery (B3) | Webhook handling is verified only with locally signed events | Stripe CLI `listen --forward-to http://127.0.0.1:8001/api/payments/webhook` with a UAT-only `whsec_` (see External Integration Report) | `stripe_webhook_events` rows processed; refund moves PROCESSING → SUCCEEDED from the event | S, P |
| 2.2 | Firebase FCM (B4) | Push is not configured | Firebase project + service account in a secret store; test device | Device receives a reminder; monitoring shows push delivered | P |
| 2.3 | SMTP (B5) | E-mail disabled in UAT | Sandbox SMTP + synthetic recipients; `-EnableEmail` | Sandbox inbox receives booking confirmation | P |
| 2.4 | SMS (B5) | Not configured | Twilio test credentials and verified number | Test SMS received | P (if SMS is in scope) |
| 2.5 | Authorized Gemini/OpenAI testing (B13) | Only test doubles were used | Approve synthetic-data use and a cost cap; set `AI_DAILY_REQUEST_LIMIT`; run `intent_probe.py` with `-AiProvider gemini` | Provider metrics show real calls; answers still grounded | P (for LLM features) |
| 2.6 | Authorized medicine-image analysis (B13) | Vision disabled | Data-processing agreement; synthetic packaging photos | Correct extraction; loose tablets never identified | P (for that feature) |
| 2.7 | Drug-interaction data source (P3-B9) | No authoritative source | Choose and license a source; pharmacist review | Interaction checks cite the source | C, P |

## 3. Product decisions (engineering prerequisites are in place)

| # | Decision | Options and consequences | Blocks |
|---|---|---|---|
| 3.1 | Refund and rescheduling policy (B6) | Keep current tiers (unchanged) or define new rules; any change needs versioning for existing bookings | P |
| 3.2 | Platform commission and doctor payout (P4-B7) | Until defined, revenue/earnings stay "not calculated" | P (if shown) |
| 3.3 | Support scope (P4-B8) | Patient replies/reopen and a mobile support screen, or admin-only support | P |
| 3.4 | Rejected doctor re-application (P3-B6) | Allow re-submission with history, or contact-support only | P |
| 3.5 | Admin access to care-plan content (P4-B4a) and booking notes (P4-B4b) | Remove from routine admin views, or allow via an audited break-glass flow with purpose and privacy approval | P |
| 3.6 | Other clinicians' note text in consultation preparation (P3-B8 follow-up) | Keep excluded (current) or include signed notes with audit | C |
| 3.7 | Conversation retention (`CONVERSATION_RETENTION_DAYS`) | 0 keeps chats until deleted (current); a number deletes them that many days after the last message | P |
| 3.8 | Historical paid doctor cancellations without refunds (P4-B6) | Review each via reconciliation (UAT: 1 found, read-only report) — no automatic backfill | P |
| 3.9 | Measurement storage (B7) | Reads are unified now; decide whether to back-fill `measurementId`/`measuredAt` in storage (reversible migration, not run) | — |
| 3.10 | In-person migration on shared data (B9) and old auto-created reminders cleanup (P3-B5) | Approve reversible migrations with backup, or leave | P |

## 4. Human verification

| # | Review | What to review | Blocks |
|---|---|---|---|
| 4.1 | Clinical review (B1) | Emergency triage rules and wording, mental-health crisis flow, measurement alert thresholds, care-plan and follow-up content, consultation preparation wording | C, P |
| 4.2 | Pharmacist review (B2) | Medicine information, refusal wording, renewal workflow, dose-change reply (B16) | C, P |
| 4.3 | Native Sinhala and Tamil review (B12) | Intent patterns and every Sinhala/Tamil reply, including emergency and B16 texts | C, P |
| 4.4 | Physical Android device (B10, P3-B10) | Install the debug APK pointed at a test backend; booking, payment sheet, reminders, emergency dialer confirmation | P |
| 4.5 | Physical iPhone | Not built or run in any phase | P (if iOS is in scope) |
