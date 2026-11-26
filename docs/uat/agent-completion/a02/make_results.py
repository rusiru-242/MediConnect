"""Build A02_RESULTS.json from the recorded evidence (run from the repository root, after CI finishes).

Usage:  backend\\venv\\Scripts\\python.exe -I docs\\uat\\agent-completion\\a02\\make_results.py "<ci summary>"
"""
import json
import pathlib
import re
import sys

A = pathlib.Path(__file__).resolve().parent
E = A / "evidence"


def load(name):
    return json.loads((E / name).read_text(encoding="utf-8"))


live, worker, leak = load("a02_live_uat.json"), load("a02_worker_restart_race.json"), load("test_suite_provider_leak.json")
matrix = (A / "A02_TEST_VERIFICATION_MATRIX.md").read_text(encoding="utf-8")
scenarios = {}
for line in matrix.splitlines():
    m = re.match(r"^\| (A02-[MAFTNCIS]\d\d) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", line)
    if m:
        scenarios[m[1]] = {"scenario": m[2].strip(), "evidence": m[3].strip(), "status": m[4].strip()}
counts = {}
for row in scenarios.values():
    key = row["status"].split(" ")[0]
    counts[key] = counts.get(key, 0) + 1
bugs = re.findall(r"^\| (A02-BUG-\d{3}) \| ([^|]+) \|", (A / "A02_BUG_FIX_REPORT.md").read_text(encoding="utf-8"), re.M)

results = {
    "phase": "Agent Completion A02",
    "date": "2026-11-26",
    "branch": "fix/agents-a02-reminders-notifications",
    "baseBranch": "fix/agents-a01-ai-intelligence-vision",
    "baseCommit": "febd063",
    "codeCommits": ["eb2e6ef", "01129d9", "9d21532", "a16ff47", "cdde444", "36475b9", "19b8134", "07f8c22",
                    "f4f51aa", "235cce4"],
    "testedCodeCommit": "235cce4",
    "merged": False, "deployed": False, "remoteDatabaseAccessed": False, "mongoCredentialsChanged": False,
    "paidServicesEnabled": False, "externalMessagesSent": 0,
    "agents": {
        "05": {"name": "AI Medication Reminder", "before": "PARTIAL", "after": "PARTIAL",
               "verified": "live in-app + emulator device reminders", "blocked": ["FCM push (B4)", "pharmacist review (B2)"]},
        "07": {"name": "AI Appointment Reminder", "before": "PARTIAL", "after": "PARTIAL",
               "verified": "live in-app 2 h reminder, Colombo time", "blocked": ["push/e-mail/SMS (B4/B5)"]},
        "08": {"name": "AI Follow-up Reminder", "before": "PARTIAL", "after": "PARTIAL",
               "verified": "live plan notices; automated 09:00 reminders", "blocked": ["09:00 live delivery not observed", "external channels"]},
        "09": {"name": "AI Medical Test Reminder", "before": "PARTIAL", "after": "PARTIAL",
               "verified": "live test-task reminder", "blocked": ["external channels"]},
        "13": {"name": "AI Notification Assistant", "before": "PARTIAL", "after": "PARTIAL",
               "verified": "live + emulator in-app lifecycle; local SMTP", "blocked": ["FCM (B4)", "external e-mail (owner: local only)", "SMS (B5)"]},
        "19": {"name": "AI Patient Communication Assistant", "before": "PARTIAL", "after": "PARTIAL",
               "verified": "live doctor-approved batch and notices", "blocked": ["e-mail/SMS", "free-text messaging not implemented"]},
    },
    "matrixTotals": {"before": {"VERIFIED": 26, "PARTIAL": 12, "BLOCKED": 0},
                     "after": {"VERIFIED": 26, "PARTIAL": 12, "BLOCKED": 0}},
    "defects": {"count": len(bugs), "fixed": len(bugs), "ids": [b[0] for b in bugs],
                "high": [b[0] for b in bugs if b[1].strip().startswith("High")],
                "observations": ["A02-O1", "A02-O2", "A02-O3", "A02-O4", "A02-O5"]},
    "tests": {
        "backend": {"passed": 907, "failed": 0, "baseline": 865, "newA02File": 42, "database": "mediconnect_a02final_test",
                    "providerConnectionAttempts": {"baseline": leak["baseline"]["blockedAttempts"],
                                                   "final": leak["final"]["blockedAttempts"]}},
        "flutter": {"passed": 313, "failed": 0, "baseline": 309, "analyze": "no issues", "debugApk": "built"},
        "adminWeb": {"passed": 40, "failed": 0, "baseline": 39, "build": "ok"},
        "totalAutomated": {"before": 1213, "after": 907 + 313 + 40},
        "changedExpectations": ["test_phase05_scheduler::test_s06c (A02-BUG-005)"],
    },
    "liveUat": {"steps": len(live["steps"]), "summary": live["summary"],
                "summaryBeforeReevaluation": live.get("summaryBeforeReevaluation"),
                "reevaluated": [s["id"] for s in live["steps"] if s.get("reevaluated")],
                "startedAt": live["startedAt"], "finishedAt": live["finishedAt"]},
    "workerRestartAndRace": {"status": worker["status"], "rows": worker["rows"],
                             "backendTimeline": worker.get("backendTimeline")},
    "scenarioMatrix": {"total": len(scenarios), "counts": counts, "rows": scenarios},
    "external": {"firebase": "not configured (BLOCKED)", "smtp": "local SMTP server only (owner decision); external BLOCKED",
                 "sms": "no provider (BLOCKED)", "stripe": "test mode only (booking confirmation)"},
    "ci": sys.argv[1] if len(sys.argv) > 1 else "pending",
    "package": "C:\\Users\\REDTECH\\Downloads\\A02_REPORT_PACKAGE.zip",
    "productionReady": False, "clinicallyApproved": False,
}
(A / "A02_RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps({k: results[k] for k in ("scenarioMatrix",)}, default=str)[:300])
print(results["scenarioMatrix"]["total"], results["scenarioMatrix"]["counts"], results["defects"]["count"], results["liveUat"]["summary"])
