"""Build A04_RESULTS.json from the recorded evidence and reports.

Usage (repository root):
  backend\\venv\\Scripts\\python.exe -I docs\\uat\\agent-completion\\a04\\make_results.py "<integration json>"
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


matrix = (A / "A04_TEST_VERIFICATION_MATRIX.md").read_text(encoding="utf-8")
scenarios = {}
for line in matrix.splitlines():
    m = re.match(r"^\| (A04-[PAURMS]\d\d) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", line)
    if m:
        scenarios[m[1]] = {"scenario": m[2].strip(), "evidence": m[3].strip(), "status": m[4].strip()}
counts = {}
for row in scenarios.values():
    key = row["status"].split(" (")[0]
    counts[key] = counts.get(key, 0) + 1
bugs_text = (A / "A04_BUG_FIX_REPORT.md").read_text(encoding="utf-8")
bugs = re.findall(r"^\| (A04-BUG-\d{3}) \| (\w+) \|", bugs_text, re.M)
observations = re.findall(r"^\| (A04-O\d) \|", bugs_text, re.M)
before, after = load("a04_probe_baseline.json"), load("a04_probe_after_fix.json")
pre_fix = (E / "a04_tests_on_pre_fix_main.txt").read_text(encoding="utf-8").strip().splitlines()[-1]
integration = json.loads(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].startswith("{") else "pending"


def step(probe, sid):
    return next((s["result"] for s in probe["steps"] if s["id"] == sid), None)


results = {
    "phase": "Agent Completion A04",
    "date": "2026-11-27",
    "agent": {"id": "17", "name": "Prescription Assistant", "before": "PARTIAL",
              "after": "PARTIAL (engineering verified; clinical gates open)",
              "classification": "deterministic, tool-orchestrated (no generative AI on prescription paths)",
              "gates": ["drug-interaction source (P3-B9)", "pharmacist review (B2)", "clinical validation (B1)",
                        "physical phone (B10)", "native-language review (B12)"]},
    "startingMain": "d8c2142dd497971947fa24d395b8c157b25b3eee",
    "a01a03Preserved": {"A01": "febd063", "A02": "048ad48", "A03": "2cb5569", "pr25": "merged", "allAncestors": True},
    "branch": "fix/agents-a04-prescription-assistant",
    "codeCommits": ["3002dfa", "94bbd71", "51bdaa3"],
    "testedCodeCommit": "51bdaa3",
    "remoteDatabaseAccessed": False, "mongoCredentialsChanged": False, "liveAiRequests": 0,
    "externalMessagesSent": 0, "livePayments": False, "deployed": False,
    "matrixTotals": {"before": {"VERIFIED": 27, "PARTIAL": 11, "BLOCKED": 0},
                     "after": {"VERIFIED": 27, "PARTIAL": 11, "BLOCKED": 0}},
    "defects": {"count": len(bugs), "fixed": len(bugs), "ids": [b[0] for b in bugs],
                "bySeverity": {s: [b[0] for b in bugs if b[1] == s] for s in ("High", "Medium", "Low")},
                "observations": observations},
    "tests": {
        "backend": {"final": {"passed": 976, "failed": 0, "commit": "51bdaa3", "providerAttempts":
                              load("a04_backend_provider_attempts.json")["blockedAttempts"]},
                    "baseline": 945, "newFile": {"test_a04_prescription_assistant.py": 31},
                    "newTestsOnPreFixMain": pre_fix},
        "flutter": {"passed": 327, "failed": 0, "baseline": 317, "analyze": "no issues", "debugApk": "built"},
        "adminWeb": {"passed": 42, "failed": 0, "baseline": 42, "tsc": "ok", "build": "ok"},
        "total": {"passed": 976 + 327 + 42, "baseline": 1304},
        "changedExpectations": ["mobile create_consultation_record_screen_test (A04-BUG-009)"],
    },
    "probe": {
        "before": {"V01": step(before, "V01")["http"], "V02": step(before, "V02")["http"],
                   "P08c": step(before, "P08c"), "R01b": step(before, "R01b")["http"], "R04b": step(before, "R04b"),
                   "allergyWarningsField": "allergyWarnings" in (step(before, "A03a")["response"] or {})},
        "after": {"V01": step(after, "V01")["http"], "V02": step(after, "V02")["http"],
                  "P08c": step(after, "P08c"), "R01b": step(after, "R01b")["http"], "R04b": step(after, "R04b"),
                  "allergyWarnings": step(after, "A03a")["response"].get("allergyWarnings"),
                  "aiRequests": len(step(after, "AI-PAT")) + len(step(after, "AI-DOC")),
                  "aiMutations": sum(r.get("renewalsCreated", 0) for r in step(after, "AI-PAT"))
                  + sum(r["prescriptionsCreated"] + r["renewalsApproved"] for r in step(after, "AI-DOC")),
                  "authorization": step(after, "S")},
        "providerUsageDelta": {"before": before["providerUsageDelta"], "after": after["providerUsageDelta"]},
    },
    "emulator": {"screenshots": sorted(p.name for p in (E / "emulator").glob("a04_e*.png")),
                 "issuedPrescription": "RX-20261127-E389AE", "renewal": "REN-20261127-FDCB86",
                 "renewedPrescription": "RX-REN-20261127-D70D5D"},
    "a03WebhookClarification": {"forwardedDeliveries": 51, "distinctEvents": 48, "resends": 3, "http200": 46,
                                "refusedDuringOutage": 5, "resentOfThose": 3,
                                "neverRedelivered": ["charge.refund.updated", "charge.refund.updated"],
                                "a03JsonResent3": "correct"},
    "scenarioMatrix": {"total": len(scenarios), "counts": counts, "rows": scenarios},
    "integration": integration,
    "productionReady": False, "clinicallyApproved": False,
}
(A / "A04_RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(results["scenarioMatrix"]["total"], counts, results["defects"]["count"], results["probe"]["after"]["aiMutations"])
