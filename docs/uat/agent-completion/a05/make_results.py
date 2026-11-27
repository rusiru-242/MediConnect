"""Build A05_RESULTS.json from the recorded evidence and reports.

Usage (repository root):
  backend\\venv\\Scripts\\python.exe -I docs\\uat\\agent-completion\\a05\\make_results.py "<integration json>"
The integration argument is a JSON object with the PR, CI and merge facts read from GitHub (or "pending").
"""
import json
import pathlib
import re
import sys

A = pathlib.Path(__file__).resolve().parent
E = A / "evidence"


def load(name):
    return json.loads((E / name).read_text(encoding="utf-8"))


matrix = (A / "A05_TEST_VERIFICATION_MATRIX.md").read_text(encoding="utf-8")
scenarios = {}
for line in matrix.splitlines():
    m = re.match(r"^\| (A05-[FC]\d\d) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", line)
    if m:
        scenarios[m[1]] = {"scenario": m[2].strip(), "evidence": m[3].strip(), "status": m[4].strip()}
counts = {}
for row in scenarios.values():
    key = row["status"].split(" (")[0]
    counts[key] = counts.get(key, 0) + 1
bugs_text = (A / "A05_BUG_FIX_REPORT.md").read_text(encoding="utf-8")
bugs = re.findall(r"^\| (A05-BUG-\d{3}) \| (\w+) \|", bugs_text, re.M)
observations = re.findall(r"^\| (A05-O\d+) \|", bugs_text, re.M)
probe = load("a05_probe_uat.json")
steps = {s["id"]: s["result"] for s in probe["steps"]}
pre = load("a05_repro_fraud_pre_fix_main.json")
post = load("a05_repro_fraud_a05_branch.json")
browser = {m: load(f"a05_browser_admin_{m}.json") for m in ("fraud", "reply", "followup")}
integration = json.loads(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].startswith("{") else "pending"

results = {
    "phase": "Agent Completion A05",
    "date": "2026-11-28",
    "agents": {
        "25": {"name": "Fraud Detection Agent", "before": "PARTIAL", "after": "VERIFIED (local) · thresholds provisional",
               "classification": "deterministic rule engine with background sweep; no generative AI, no provider call",
               "slotHoarding": {"windowHours": 24, "minDistinctSlots": 4, "weight": 25, "calibrated": False}},
        "26": {"name": "Customer Support Assistant", "before": "PARTIAL", "after": "VERIFIED (local)",
               "classification": "deterministic, tool-orchestrated (keyword triage, fixed templates, role-checked tools); "
                                 "admin sends every reply"},
    },
    "startingMain": "18e8a3272e5079e5a2afd303734479a4abd0c1e1",
    "a04DocsReconciled": {"from": "f3765cd", "commit": "348bbd6"},
    "branch": "fix/agents-a05-fraud-support",
    "codeCommits": ["d6144e6", "f075b33"],
    "testedCodeCommit": "f075b33",
    "remoteDatabaseAccessed": False, "mongoCredentialsChanged": False, "liveAiRequests": 0, "liveStripeRequests": 0,
    "externalMessagesSent": 0, "deployed": False,
    "matrixTotals": {"before": {"VERIFIED": 27, "PARTIAL": 11, "BLOCKED": 0},
                     "after": {"VERIFIED": 29, "PARTIAL": 9, "BLOCKED": 0}},
    "defects": {"count": len(bugs), "fixed": len(bugs), "ids": [b[0] for b in bugs],
                "bySeverity": {s: [b[0] for b in bugs if b[1] == s] for s in ("High", "Medium", "Low")},
                "observations": observations},
    "tests": {
        "backend": {"passed": 1003, "failed": 0, "baseline": 976, "newFile": {"test_a05_fraud_support.py": 27},
                    "providerAttempts": load("a05_backend_provider_attempts.json")["blockedAttempts"],
                    "detector": "docs/uat/agent-completion/a03/a03_leak_detector.py"},
        "flutter": {"passed": 333, "failed": 0, "baseline": 327, "analyze": "no issues", "debugApk": "built"},
        "adminWeb": {"passed": 44, "failed": 0, "baseline": 42, "tsc": "ok", "build": "ok"},
        "total": {"passed": 1003 + 333 + 44, "baseline": 1345},
        "changedExpectations": ["test_phase04 N22 (slot hoarding now also fires)",
                                "test_phase5 support workflow (draft admin-only)",
                                "test_phase5 emergency ticket (draft admin-only, safety notice)"],
        "newTestsOnPreFixMain": (E / "a05_tests_on_pre_fix_main.txt").read_text(encoding="utf-8").strip().splitlines()[-1],
    },
    "repro": {"preFixMain": pre, "a05Branch": post},
    "probe": {
        "workerRaisedHoardingSignal": steps["F03b"]["found"], "waitedSeconds": steps["F03b"]["waitedSeconds"],
        "assessment": steps["F03b"]["assessment"],
        "normalAccountFirstProbe": "flagged from earlier A03 UAT holds (A05-O2)",
        "cleanNegative": load("a05_negative.json")["evaluate"],
        "noAccountOrFinancialChange": steps["F14-F15"], "nonAdmin": steps["F13"], "review": steps.get("F12"),
        "support": {k: steps[k] for k in steps if k.startswith("C")},
        "providerUsageDelta": probe["providerUsageDelta"],
    },
    "browser": {m: [{"id": s["id"], "status": s["status"]} for s in b["steps"]] for m, b in browser.items()},
    "emulator": {"screenshots": sorted(p.name for p in (E / "emulator").glob("a05_e*.png")),
                 "ticket": "TCK-8B612CA6"},
    "a03WebhookEvidence": {"forwardedDeliveries": 51, "distinctEvents": 48, "http200": 46, "refusedDuringOutage": 5,
                           "resent": 3, "neverRedelivered": 2},
    "scenarioMatrix": {"total": len(scenarios), "counts": counts, "rows": scenarios},
    "integration": integration,
    "productionReady": False, "clinicallyApproved": False,
}
(A / "A05_RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(results["scenarioMatrix"]["total"], counts, results["defects"]["count"], results["tests"]["total"],
      results["tests"]["backend"]["providerAttempts"])
