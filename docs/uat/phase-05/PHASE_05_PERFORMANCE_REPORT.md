# Phase 05 — Performance Report

For: the project owner and engineers sizing a staging deployment. 2026-11-26.

**These are bounded local measurements on one developer laptop. They are not production capacity estimates.**

## 1. Environment

| Item | Value |
|---|---|
| Machine | Intel Core i5-11400H @ 2.70 GHz, 12 logical CPUs, 15.7 GB RAM, Windows 11 |
| Backend | FastAPI under one uvicorn worker on 127.0.0.1:8001 (`start_uat_backend.ps1`), Python 3.13 venv |
| Database | Local MongoDB on 127.0.0.1, `mediconnect_uat` (synthetic): 47 users, 19 doctor profiles, 111 appointments, 82 payments, 418 notifications, 357 booking sessions |
| AI | Deterministic engine (providers disabled) |
| Load generator | `docs/uat/phase-05/load_test.py` (thread pool on the same machine, so client and server share the CPU) |
| CPU/RSS | psutil sampling of the backend process every 0.5 s (CPU % is per core; >100 % means more than one core) |

## 2. Results (`evidence/load-test.json`)

| Scenario | Requests | Concurrency | Throughput (req/s) | Errors | Median ms | P95 ms | Peak CPU % | Peak RSS MB |
|---|---|---|---|---|---|---|---|---|
| Liveness probe | 400 | 20 | 553 | 0 % | 34.5 | 47.3 | 99.9 | 135.6 |
| Readiness (DB ping) | 300 | 20 | 454 | 0 % | 41.6 | 56.4 | 125.0 | 135.0 |
| `/auth/me` (JWT + account + revocation check) | 300 | 20 | 383 | 0 % | 50.1 | 63.8 | 106.1 | 140.4 |
| Doctor search (signed-in patient) | 200 | 10 | 316 | 0 % | 29.9 | 45.4 | 121.8 | 133.8 |
| Patient appointments | 200 | 10 | 167 | 0 % | 57.9 | 70.7 | 84.3 | 135.7 |
| Doctor appointments | 200 | 10 | 215 | 0 % | 45.5 | 58.9 | 99.8 | 134.3 |
| Admin analytics overview (30 days) | 100 | 5 | 46 | 0 % | 108.7 | 122.0 | 65.6 | 135.9 |
| Admin payments list (page 1) | 150 | 10 | 188 | 0 % | 52.3 | 64.7 | 100.0 | 137.1 |
| Admin appointments search | 150 | 10 | 121 | 0 % | 82.1 | 96.9 | 74.9 | 135.5 |
| Platform monitoring snapshot | 100 | 5 | 203 | 0 % | 22.7 | 40.3 | 118.7 | 136.3 |
| Admin AI assistant (deterministic) | 25 | 5 | 65 | 0 % | 74.1 | 92.8 | 28.1 | 136.2 |
| Doctor AI assistant (deterministic) | 25 | 5 | 164 | 0 % | 29.0 | 33.6 | 28.1 | 136.2 |

2,150 requests, 0 errors. A first run showed 401 for the doctor search because that endpoint requires a signed-in user (script corrected, not a defect).

Observations:
- The per-request cost of the Phase 05 session checks (revocation lookup by `jti`, `tokensValidAfter`) is visible in `/auth/me` (≈50 ms median at 20 concurrent clients on a shared CPU), which is acceptable here; it is one indexed `_id` lookup.
- Admin analytics is the slowest read (≈110 ms): it aggregates payments, appointments and refunds for 30 days on every call. It is not cached.
- Memory stayed flat at about 135 MB across the whole run.

## 3. Database query review

| Query | Before | After | Change |
|---|---|---|---|
| Admin appointments list (P4-O4) | whole collection loaded, searched and paginated in Python | search via indexed user/profile lookups, `count_documents`, `skip/limit` in MongoDB | code (P4-O4) |
| Admin payments list (P4-O4) | whole filtered collection loaded and sliced in Python | `count_documents` + `skip/limit` | code (P4-O4) |
| Paging order `createdAt desc, _id desc` on payments and appointments | `COLLSCAN` + in-memory `SORT` (explain) | `IXSCAN` → `FETCH` → `LIMIT`, 20 documents examined | two indexes added (`idx_payments_created_desc`, `idx_appointments_created_desc`) |
| Patient appointments | `IXSCAN` | unchanged | — |
| Reminder claim (`state`, `nextAttemptAt`) | `IXSCAN` | unchanged | — |
| Measurements (B7) | `find().sort(measuredAt)` (missed Care Agenda rows) | aggregation with `$ifNull(measuredAt, recordedAt)` sort and limit in MongoDB | correctness + server-side ordering |
| Rate-limit counters | in-process | one upsert + one point read per request, TTL-expired | new storage cost bounded by 2 windows |

Indexes were added only where an explain plan showed a collection scan on a paged admin query. No other index was added (write cost).

## 4. AI latency and fallback

All AI paths ran on the deterministic engine (providers disabled in UAT). Provider latency, timeouts and fallbacks were exercised with test doubles only (S-02); real provider latency is **not measured** (B13). The provider gateway records latency and token usage per day, so the first authorized live run will produce these numbers in `/api/security/monitoring/ai-providers`.

## 5. Not measured

- Multiple uvicorn workers or hosts, network latency, TLS, a remote MongoDB cluster.
- Sustained load (minutes to hours), memory growth over days.
- Flutter frame timing (no DevTools profile captured) and admin web Lighthouse metrics.
