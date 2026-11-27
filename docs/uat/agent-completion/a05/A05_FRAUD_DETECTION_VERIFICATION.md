# A05 — Fraud Detection Verification (Agent 25)

For: the project owner and reviewers. 2026-11-28.

**Outcome:** Agent 25 PARTIAL → **VERIFIED (local)**, with provisional thresholds. The slot-hoarding rule that kept it PARTIAL is implemented and was raised by the real background worker in UAT. Four defects in the existing detection were fixed (A05-BUG-001, 002, 003, 010) and two in the review screen (011, 014). This is local engineering verification. The thresholds have **no real-world calibration and no measured false-positive rate**, and a signal is never proof of fraud.

## What the agent is

| Part | What it does |
|---|---|
| Rules (`FraudDetectionService.RULES_DEFINITION`) | Seven deterministic rules over stored records. Each rule has a fixed weight; the weights are summed, capped at 100 and mapped to a tier (25 MEDIUM, 50 HIGH, 75 CRITICAL). Below 25 nothing is stored |
| Evaluation | `evaluate_account_risk(account)`: reads the account's payments, appointments, refund requests and sign-in security events |
| Sweep (A05) | `run_detection_sweep`, run by the existing background worker every `FRAUD_SWEEP_INTERVAL_SECONDS` (300 s; 0 turns it off). It evaluates accounts with recent bookings, cancellations, payments, refund requests or sign-in failures, up to 200 per run |
| Alert store | `fraud_risk_assessments`: one open assessment per account (unique `openKey`), with per-rule evidence (`ruleEvidence`) and review history (`investigationNotes`) |
| Review | Administrators only: dismiss, investigate, resolve, or confirm (a human finding). Each decision is written to the admin audit log with `accountActionTaken: false` |
| What it never does | Suspend or ban an account, cancel a booking, approve or deny a refund, charge or change a payment, or penalize anyone. No code path for these exists in the agent |
| AI | None. No LLM generates or explains signals, and no account, payment or patient data goes to a provider |

## Rules, after A05

| Rule | Window | Fires when | Weight |
|---|---|---|---|
| MULTIPLE_FAILED_PAYMENTS | 24 h | 3 or more FAILED payments | 35 |
| DUPLICATE_PAYMENT_REFERENCES | — | A payment reference is also recorded for another account | 40 |
| EXCESSIVE_BOOKING_RATE | 1 h | More than 5 appointments created | 30 |
| RAPID_CANCELLATION_PATTERN | 24 h | More than 3 **patient cancellations of bookings**. Released or expired unpaid holds no longer count (A05-BUG-010) | 25 |
| EXCESSIVE_REFUND_REQUESTS | 7 d | More than 2 refund requests | 30 |
| **SLOT_HOARDING_ATTEMPT (A05)** | `FRAUD_SLOT_HOARDING_WINDOW_HOURS` (24) | At least `FRAUD_SLOT_HOARDING_MIN_SLOTS` (4) **distinct** slots held unpaid: expired unpaid, released before payment, or still held | 25 |
| UNAUTHORIZED_ACCESS_BURST | 15 min | 5 or more sign-in or authorization failures recorded for the account (manual admin entries excluded) | 35 |

**Windows:** the window for each rule starts at the later of its usual start or the account's latest closing review decision (A05-BUG-003).

**Provisional defaults:** the slot-hoarding defaults are engineering choices, not statistics.
- **Why distinct slots:** repeated attempts on one slot after a card failure or network error count as one slot.
- **Why 4:** it sits above a normal pattern of reserving, changing one's mind and booking a different time.
- **Why the window and weight:** 24 hours is one booking day, and weight 25 means the rule alone reaches the MEDIUM review tier.
- **Not counted:**
  - paid bookings;
  - free bookings;
  - bookings cancelled by a doctor or admin.
- **Time zones:**
  - slots are shown in Asia/Colombo time;
  - stored times are UTC;
  - windows are computed in UTC.

## Existing booking protections (unchanged)

- A unique index allows one active booking per doctor slot.
- Holds last 10 minutes (server-owned `holdExpiresAt`).
- The worker releases expired holds with a conditional update.
- The patient's "Release reservation" cancels any open PaymentIntent first.
- A03 webhook settlement and refund rules are untouched.

No per-patient limit on simultaneous holds exists. The slot-hoarding rule flags the pattern for review; it does not add a limit.

## Results

| Scenario | Result | Evidence |
|---|---|---|
| F01 failed logins | 5 real failed logins → 5 `AUTH_FAILURE` events, 1 `BRUTE_FORCE` event, sweep → `UNAUTHORIZED_ACCESS_BURST` (MEDIUM), account ACTIVE | `test_f01` |
| F02 normal login | 1 typo then success → no signal | `test_f02` |
| F03 hoarding | UAT: 4 holds on distinct slots (2 released by the patient, 1 expired by the worker, 1 held) → the **worker sweep** raised `SLOT_HOARDING_ATTEMPT`, MEDIUM, 25/100, after 260 s. The evidence lists each slot, its outcome and appointment id | Probe F03a/F03b; Browser b01–b02 |
| F04 normal booking | Account with no bookings in 24 h: one hold released → no signal. The probe's first "normal" account (`uat.p02.patientb`) was flagged: 4 unpaid holds from the A03 UAT session that morning + 1 = 5 distinct slots. A correct application of the rule, and evidence that QA traffic can trip it (A05-O2) | `a05_negative.json`; Probe F04b; `test_f04` |
| F05 payment recovery | 4 attempts on one slot, 2 failed payments, each released → no signal (was `RAPID_CANCELLATION_PATTERN` on main) | `test_f05`; Repro |
| F06 thresholds | Minimum 2 → fires on 2 slots; a window before the activity sees nothing | `test_f06` |
| F07 duplicates | Repeated evaluation → same assessment; after a dismissal the same evidence raises nothing; new activity raises a new one | `test_f07`; Probe F07; Repro |
| F08 concurrency | 6 evaluations in lockstep → 1 assessment (main: 6) | `test_f08`; Repro |
| F09 restart | Sweep state reset (what a restart does) → still 1 assessment; throttled within the interval; interval 0 → off | `test_f09`; UAT signal raised by a freshly restarted backend |
| F10–F12 review | Evidence, threshold, observed count, history; four human decisions; INVESTIGATING recorded and audited | Browser; Probe F12 |
| F13 access | Patient and doctor: list, review and evaluate → 403; unauthenticated → 401 | Probe F13; `test_f13` |
| F14–F15 no action | Account ACTIVE, no revoked sessions, payments and refunds unchanged, other bookings unchanged | Probe F14-F15; `test_f03` |
| F16 integrity | Holds still expire, a released slot can be booked by another patient, a paid booking is unchanged; the full A03 suite passes | `test_f16`; full suite |

## Presentation to administrators

| Element | Text or behaviour |
|---|---|
| Section title | "Rule-based Risk Signals" |
| Section note | "A signal is a reason to review an account, not proof of fraud. No account, booking, refund or payment action is taken automatically; thresholds are provisional and not calibrated on real fraud data" |
| Explanation | Rule weight total, tier, rules and "signals for human review, not a finding of fraud" |
| Distinctions | **Suspicious activity:** the stored records. **Rule-based indicator:** the triggered rule with threshold and observed value. **Human-confirmed finding:** "Confirm finding (human decision)", recorded only in the review history |
| Privacy | Evidence shows appointment ids, slot times and outcomes only, with no clinical or payment-card data |

## Limitations

- No real-world fraud data, calibration or measured false-positive or false-negative rate. Thresholds and weights are provisional.
- QA, demo and exploratory booking can trigger the hoarding rule (A05-O2).
- The sweep covers up to 200 recently active accounts per run. A much larger deployment would need paging or an event trigger.
- Signals for sign-in failures against unknown e-mail addresses have no account to attach to; they remain security events only.
- `BRUTE_FORCE` event de-duplication is not atomic (A05-O4, pre-existing, monitoring only).
- No external fraud service, paid API or machine-learning model was added.
