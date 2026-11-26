# Phase 05 — Remaining Blockers

For: the project owner and anyone planning staging, a clinical pilot or production. Every earlier blocker is reconciled; nothing was closed without evidence. 2026-11-26.

## 1. Closed in Phase 05

| ID | Item | Evidence |
|---|---|---|
| P4-B3 | Admin web development target pointed at port 8000 | `.env.example` and fallback now 127.0.0.1:8001 (UAT); test updated |
| P4-B5 | Backend silently used the remote database in `backend/.env` when started without configuration | fail-closed `runtime_safety` (P05-N01); owner migration note in the security report |
| P4-B9 | Failed logins not recorded; slot-hoarding rule | failed-login telemetry delivered (P05-N08). **Slot-hoarding rule still not implemented → moved to P5-B5** |
| P4-B10 | Pending Stripe refunds had no follow-up; reconcile-refund not audited | refund events + polling fallback (`wh`), audit (P05-N25). External delivery stays under B3 |
| P4-O1/O3/O4/O7/O8 | malformed record list crash; Google Fonts/CSP; in-memory paging; reconcile audit; duplicate router | P05-N24, I08, I09, N25, N10 |
| B7 | Two measurement stores | read model unified without migration (P05-N18); storage back-fill is optional (owner, §3) |
| B8 | Encryption at rest for uploaded documents | AES-256-GCM, rotation, migration script; production key management remains (P5-S1) |
| B16 | "Change my dose" reply | P05-N22; pharmacist review of wording remains (B2) |
| B17 | Reply language after a Sinhala emergency | P05-N21 |
| BUG-038 | Per-process rate limiting | P05-N09 (verified across OS processes) |
| P3-B7 | Raw field names in the doctor workflow screen | labels (I07), emulator screenshot |
| P3-B8 | Consultation preparation scope | shared authorized sources + missing-information list (I06); other clinicians' note text = owner decision (§3) |
| P3-B11 | Multi-process doctor mutation testing | `mp` (6 mutations across OS processes; found N17 and N20) |

## 2. Open

| ID | Item | Type | Owner action | Blocks |
|---|---|---|---|---|
| **P5-C1** | **Live MongoDB credentials in public git history** (`a41b659`) | Security incident | Rotate now; review access (checklist 1.1–1.4) | Staging, production |
| **P4-B1** | Remote database incident unverified (now including possible third-party access) | Owner, urgent | Read-only inspection (Phase 04 review §4–6) | Staging, production |
| **P4-B2** | Rotate SMTP, Gemini, OpenAI; replace the development JWT secret (now refused at start-up) | Owner | Checklist 1.5–1.6 | Staging, production |
| P5-S1 | Production key management (`DOCUMENT_ENCRYPTION_KEYS`, JWT secret) in a secrets manager; encrypt existing uploads | Deployment | Checklist 1.7–1.8 | Production |
| P5-S2 | Major dependency upgrades: react-router 7, zod 4 (production; advisories not exploitable in current use), vite/vitest (dev-only) | Engineering | Plan and test the upgrades | — |
| P5-B1 | Mobile debug builds still default to port 8000 / LAN hosts when no `API_BASE_URL` is given (UAT builds always pass 10.0.2.2:8001) | Configuration | Decide whether the developer device workflow should default to the UAT port | — |
| P5-B2 | Admin and doctor assistants answer from templates; no LLM phrasing | Design choice | Keep (figures cannot drift) or add bounded LLM phrasing after B13 | — |
| P5-B3 | Doctor workflow shows raw ISO timestamps | UX polish | Format dates/times | — |
| P5-B4 | Analytics overview not cached (≈110 ms median locally) | Performance | Cache if dashboards are polled heavily | — |
| P5-B5 | Slot-hoarding fraud rule not implemented | Feature | Define thresholds with evidence | — |
| P05-O1 | Intermittent `test_phase3_care` failure (once; not reproduced in 8 targeted runs and 4 full runs) | Test stability | Watch CI; investigate the reused `mediconnect_phase3_test` database | — |

## 3. Carried and still open (owner decisions, approvals, external)

| ID | Item | Status |
|---|---|---|
| B1 | Clinical approval | **BLOCKED** (no clinician review) |
| B2 | Pharmacist approval | **BLOCKED** |
| B3 | Stripe → backend webhook delivery | **BLOCKED** (local signed events verified) |
| B4 | FCM push delivery | **BLOCKED** |
| B5 | E-mail and SMS delivery | **BLOCKED** |
| B6 | Refund and rescheduling policy | OPEN – owner (policy unchanged) |
| B9 | In-person migration on shared data | NOT RUN (approval required) |
| B10 / P3-B10 | Physical Android device; doctor screens on a device | NOT RUN |
| — | Physical iPhone | NOT RUN (never built) |
| B12 | Sinhala and Tamil review | NOT RUN |
| B13 | Live Gemini/OpenAI and vision | **BLOCKED** (authorization, rotated keys) |
| P3-B5 | Old automatically created medication reminders | OPEN – owner |
| P3-B6 | Rejected doctor re-application | OPEN – owner |
| P3-B9 | Drug-interaction source | NOT IMPLEMENTED (needs a licensed source); blocks a clinical pilot |
| P4-B4a / P4-B4b | Admin access to care-plan content / booking notes | OPEN – owner (privacy) |
| P4-B6 | Historical paid doctor cancellations without refunds | OPEN – owner (UAT read-only report: 1) |
| P4-B7 | Platform commission and payout model | OPEN – owner |
| P4-B8 | Support scope | OPEN – owner |
| P3-B8 follow-up | Other clinicians' note text in preparation | OPEN – owner |
| — | Conversation retention period | OPEN – owner (setting available) |

## 4. By type

| Type | Items |
|---|---|
| Security incidents (owner, urgent) | P5-C1, P4-B1, P4-B2 |
| Deployment | P5-S1 |
| Engineering | P5-S2, P5-B1–B5, P05-O1 |
| External integrations | B3, B4, B5, B13 |
| Clinical / pharmacist / language | B1, B2, B12, P3-B9 |
| Owner product and privacy decisions | B6, B9, P3-B5, P3-B6, P3-B8 follow-up, P4-B4a/b, P4-B6, P4-B7, P4-B8, retention |
| Physical devices | B10, P3-B10, iPhone |
