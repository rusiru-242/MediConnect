"""Build R03_RESULTS.json from the recorded R03 evidence and reports.

Usage (repository root):  python docs/uat/release-preparation/r03/make_results.py ['<integration json>']
"""
import json
import pathlib
import re
import sys

R = pathlib.Path(__file__).resolve().parent
E = R / "evidence"
U = R.parents[1]
integration = json.loads(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].startswith("{") else "pending"


def load(name):
    return json.loads((E / name).read_text(encoding="utf-8"))


bug_text = (R / "R03_BUG_FIX_REPORT.md").read_text(encoding="utf-8")
bugs = re.findall(r"^\| (R03-BUG-\d{3}) \| ([^|]+) \| ([^|]+) \|", bug_text, re.M)
observations = re.findall(r"^\| (R03-O\d+) \|", bug_text, re.M)
probe = load("r03_workflow_probe.json")
pictures = load("r03_picture_probe.json")
browser = load("r03_browser_admin.json")
tracker = json.loads((U / "phase-05" / "evidence" / "master-tracker-counts.json").read_text(encoding="utf-8"))

results = {
    "phase": "R03 Final System Verification and Academic Release Readiness",
    "date": "2026-11-28",
    "startingMain": "b20e683",
    "branch": "fix/final-release-verification",
    "implementationCommit": "4f64295",
    "priorMerges": {
        "PR25": "d8c2142 (A01-A03)", "PR26": "A04", "PR27": "96e6fe7 (A05)", "PR28": "93520da (R01)",
        "PR29": {"merge": "8ac5a41", "head": "e652c5e", "mergedWithChecksPending": True},
        "PR30": {"merge": "b20e683", "head": "e58cec3", "mergedWithChecksPending": True,
                 "note": "R02-BUG-007 fix; also committed a generated detector file (R03-BUG-006)"},
    },
    "defects": {"count": len(bugs), "fixed": len(bugs),
                "items": [{"id": b[0], "severity": b[1].strip(), "component": b[2].strip()} for b in bugs],
                "observations": observations},
    "tests": {
        "backend": {"passed": 1064, "failed": 0, "skipped": 0, "database": "fresh mediconnect_r03_final2_test",
                    "providerConnectionAttempts": 0, "new": {"tests/test_r03_final_verification.py": 14}},
        "flutter": {"passed": 362, "failed": 0, "skipped": 0, "analyze": "no issues",
                    "apk": "debug, --dart-define=API_BASE_URL=http://10.0.2.2:8001"},
        "adminWeb": {"passed": 51, "failed": 0, "skipped": 0, "typecheck": "ok", "lint": "ok", "build": "ok"},
        "newlyExecutedTotal": 1064 + 362 + 51,
        "previousR02": {"backend": 1048, "flutter": 361, "adminWeb": 51, "total": 1460},
    },
    "components38": {"VERIFIED": 29, "PARTIAL": 9, "BLOCKED": 0, "changed": False,
                     "partial": ["04", "05", "07", "08", "09", "13", "17", "19", "32"]},
    "workflows": {"A": "PASS (to explicit hold; payment via automated tests and A03 evidence)", "B": "PASS",
                  "C": "PASS (device-level renewed-prescription reminder verified)", "D": "PASS",
                  "E": "PASS (231-account real sweep); UAT check qualified (R03-O1)", "F": "PASS"},
    "workflowProbe": {s["id"]: s["pass"] for s in probe["steps"]},
    "safety": [{"id": s["id"], "type": s["type"], "deltas": s["deltas"]} for s in probe["safety"]],
    "security": probe["security"],
    "pictures": {k: pictures[m][k] for m in ("upload", "check") for k in
                 ("visibilityAsDesigned", "metadataStripped", "searchUsesTrustedUrl", "appointmentsUseTrustedUrl")},
    "picturePersistenceAfterRestart": pictures["upload"]["doctorPicture"]["sha256"] == pictures["check"]["doctorPicture"]["sha256"],
    "adminBrowser": {"pages": {p["id"]: p["status"] for p in browser["pages"]},
                     "patientAccount": browser["patientAccount"]["status"],
                     "patientPictureRequested": browser["patientPictureRequested"],
                     "blockedExternalRequests": len(browser["blockedRequests"])},
    "providerUsageDelta": probe["providerUsageDelta"],
    "stripeRequests": 0,
    "secretScan": {k: v for k, v in load("r03_secret_scan_tracked.json").items() if k != "hits"},
    "historicalCredentialExposure": "UNRESOLVED (no rotation evidence); critical",
    "dependencyAudit": load("r03_dependency_audit.json")["counts"],
    "masterTracker": {k: tracker[k] for k in ("uniqueTrackedItems", "confirmedDefects", "defectsFixed", "defectsOpen")},
    "evidence": {"emulatorScreenshots": sorted(p.name for p in (E / "emulator").glob("*.png")),
                 "browserScreenshots": sorted(p.name for p in (E / "browser").glob("*.png"))},
    "readiness": {"academicDemonstration": "READY with conditions (local, synthetic, test mode)",
                  "engineering": "functioning in the verified environment", "clinical": "NOT READY",
                  "security": "NOT READY for shared/public deployment", "production": "NOT READY"},
    "openProductDecisions": ["BUG-039 consultation fee", "B6 refund and cancellation policy", "fraud thresholds"],
    "integration": integration,
    "productionReady": False, "clinicallyValidated": False,
}
(R / "R03_RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(len(bugs), observations, len(results["evidence"]["emulatorScreenshots"]), len(results["evidence"]["browserScreenshots"]),
      results["tests"]["newlyExecutedTotal"], results["picturePersistenceAfterRestart"])
