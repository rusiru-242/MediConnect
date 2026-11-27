"""Build A03_RESULTS.json from the recorded evidence (run from the repository root after CI finishes).

Usage:  backend\\venv\\Scripts\\python.exe -I docs\\uat\\agent-completion\\a03\\make_results.py "<backend result>" "<ci summary>"
"""
import json
import pathlib
import re
import sys

A = pathlib.Path(__file__).resolve().parent
E = A / "evidence"


def load(name):
    return json.loads((E / name).read_text(encoding="utf-8"))


live = load("a03_live_stripe_uat.json")
restart = load("a03_backend_restart_during_payment.json")
browser = load("a03_browser_admin_uat.json")
fallback = load("a03_provider_fallback.json")
probes = {k: load(f"a03_booking_probe_{k}.json") for k in ("deterministic", "gemini_run1", "gemini_final")}
matrix = (A / "A03_TEST_VERIFICATION_MATRIX.md").read_text(encoding="utf-8")
scenarios = {}
for line in matrix.splitlines():
    m = re.match(r"^\| (A03-[ARPWCU]\d\d) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", line)
    if m:
        scenarios[m[1]] = {"scenario": m[2].strip(), "evidence": m[3].strip(), "status": m[4].strip()}
counts = {}
for row in scenarios.values():
    key = row["status"].split(" ")[0]
    counts[key] = counts.get(key, 0) + 1
bug_text = (A / "A03_BUG_FIX_REPORT.md").read_text(encoding="utf-8")
bugs = re.findall(r"^\| (A03-BUG-\d{3}) \| ([^|]+) \|", bug_text, re.M)
observations = re.findall(r"^\| (A03-O\d) \|", bug_text, re.M)

results = {
    "phase": "Agent Completion A03",
    "date": "2026-11-27",
    "agent": {"id": "01", "name": "AI Appointment Booking", "before": "PARTIAL",
              "after": "VERIFIED (test mode + live Gemini)",
              "gates": ["refund/cancellation policy confirmation (B6)", "physical phone PaymentSheet (B10)",
                        "Sinhala review (B12)", "staging webhook endpoint (production delivery not tested)"]},
    "branch": "fix/agents-a03-booking-payments",
    "baseBranch": "fix/agents-a02-reminders-notifications", "baseCommit": "048ad48",
    "codeCommits": ["4e03d86", "9f6796b", "4b5b5e2", "60cf1b8", "a8376d3", "e513d01", "3bc2917", "94d85ca",
                    "d3a2b86", "d48c9c6", "32ef187", "020f3b6", "e3722ba"],
    "testedCodeCommit": "e3722ba",
    "merged": False, "deployed": False, "remoteDatabaseAccessed": False, "mongoCredentialsChanged": False,
    "paidServicesEnabled": False, "livePayments": False, "externalMessagesSent": 0,
    "ownerApprovals": {"liveGemini": "capped at 60 requests", "stripeCli": "stripe listen with the backend sk_test key"},
    "matrixTotals": {"before": {"VERIFIED": 26, "PARTIAL": 12, "BLOCKED": 0},
                     "after": {"VERIFIED": 27, "PARTIAL": 11, "BLOCKED": 0}},
    "defects": {"count": len(bugs), "fixed": len(bugs), "ids": [b[0] for b in bugs],
                "high": [b[0] for b in bugs if b[1].strip().startswith("High")],
                "observations": observations, "resolvedEarlierObservations": ["A02-O4"]},
    "tests": {
        "backend": {"baseline": {"passed": 907, "commit": "048ad48", "providerAttempts": 0},
                    "final": sys.argv[1] if len(sys.argv) > 1 else "pending",
                    "newA03Files": {"test_a03_booking_payments.py": 22, "test_a03_booking_agent.py": 16},
                    "firstFinalRun": "020f3b6: 944 passed, 1 failed (A01 test_p09 flaky: global time.sleep patch; "
                                     "isolated in e3722ba)"},
        "flutter": {"passed": 317, "failed": 0, "baseline": 313, "analyze": "no issues", "debugApk": "built"},
        "adminWeb": {"passed": 42, "failed": 0, "baseline": 40, "build": "ok", "tsc": "ok"},
        "changedExpectations": ["test_phase04_admin_system::test_n10 (A03-BUG-007)",
                                "test_phase05_stripe_webhooks fixtures (A03-BUG-006)",
                                "phase04Admin.test.tsx retry text (A03-BUG-007)"],
    },
    "liveStripe": {"steps": len(live["steps"]), "summary": live.get("summary"),
                   "reevaluated": [s["id"] for s in live["steps"] if s.get("reevaluated")],
                   "backendRestart": restart["result"]},
    "webhooks": {"stripeCliForwarded": 51, "http200": 46, "non2xx": 0, "notDeliveredDuringOutage": 5,
                 "resent": 3, "productionEndpointTested": False},
    "liveGemini": {"model": "gemini-3.5-flash-lite", "calls": 44, "successes": 44, "failures": 0,
                   "refusedLocallyByCap": 4, "cap": 60, "fallback": fallback["turns"]},
    "probe": {k: {"turns": sum(len(t) for t in v["threads"].values()), "anyHold": v["anyHoldFromConversation"],
                  "unverifiedCards": len(v["anyUnverifiedCard"]), "geminiDelta": v.get("geminiUsageDelta")}
              for k, v in probes.items()},
    "browser": {"steps": [{"id": s["id"], "status": s["status"]} for s in browser["steps"]],
                "blockedHosts": browser["blocked"], "pageErrors": browser["pageErrors"]},
    "scenarioMatrix": {"total": len(scenarios), "counts": counts, "rows": scenarios},
    "ci": sys.argv[2] if len(sys.argv) > 2 else "pending",
    "package": "C:\\Users\\REDTECH\\Downloads\\A03_REPORT_PACKAGE.zip",
    "productionReady": False, "clinicallyApproved": False,
}
(A / "A03_RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(results["scenarioMatrix"]["total"], results["scenarioMatrix"]["counts"], results["defects"]["count"],
      results["liveStripe"]["summary"], results["probe"])
