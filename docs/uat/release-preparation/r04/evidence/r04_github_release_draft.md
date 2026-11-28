# MediConnect v1.0.0-academic (draft, not published)

**Academic demonstration / engineering preview.** Not clinically validated, not production-ready, not a medical device, not for real patients.

MediConnect is a full-stack healthcare platform made of:
- a Flutter app for patients and doctors;
- a React admin web app;
- a FastAPI backend with MongoDB.

It has a hybrid agentic AI layer of **38 AI-assisted, automation and shared infrastructure components** (7 with an optional bounded LLM path, 31 deterministic). Bookings, payments, refunds, prescriptions and account actions are human-controlled.

**Final engineering verification (R03):**
- 1,477 automated tests passed (0 failed, 0 skipped);
- 29 components verified locally, 9 partially verified;
- 261 of 262 confirmed defects recorded as fixed; 1 open product decision.

**Assets (if approved):**
- an emulator-only debug APK (`API_BASE_URL=http://10.0.2.2:8001`), with its SHA-256 in `CHECKSUMS.sha256`;
- the admin web build;
- documentation and screenshots.

**Known limitations:**
- no clinical or pharmacist validation;
- external push, e-mail and SMS not configured;
- emulator only;
- open product decisions (consultation fee, refund policy).

Full notes: `docs/uat/release-preparation/r04/R04_RELEASE_NOTES.md`.

**Publication condition:** the owner must confirm that the historical database credential has been rotated before this is published.
