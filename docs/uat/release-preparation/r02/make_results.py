"""Build R02_RESULTS.json from the recorded evidence and reports.

Usage (repository root):  python docs/uat/release-preparation/r02/make_results.py ["<integration json>"]
"""
import json
import pathlib
import re
import sys

R = pathlib.Path(__file__).resolve().parent
E = R / "evidence"
integration = json.loads(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].startswith("{") else "pending"


def matrix(report, prefix):
    rows = {}
    for line in (R / report).read_text(encoding="utf-8").splitlines():
        m = re.match(rf"^\| (R02-{prefix}\d\d) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", line)
        if m:
            rows[m[1]] = {"scenario": m[2].strip(), "evidence": m[3].strip(), "result": m[4].strip()}
    return rows


bugs = re.findall(r"^\| (R02-BUG-\d{3}) \| ([^|]+) \| ([^|]+) \|", (R / "R02_BUG_FIX_REPORT.md").read_text(encoding="utf-8"), re.M)
observations = re.findall(r"^\| (R02-O\d+) \|", (R / "R02_BUG_FIX_REPORT.md").read_text(encoding="utf-8"), re.M)
matrices = {"images": matrix("R02_PROFILE_PICTURE_VERIFICATION.md", "I"),
            "security": matrix("R02_IMAGE_STORAGE_SECURITY_REPORT.md", "S"),
            "profileData": matrix("R02_PROFILE_DATA_INTEGRITY_REPORT.md", "P"),
            "ui": matrix("R02_UI_CORRECTIONS_REPORT.md", "U")}
counts = {k: {"total": len(v), "pass": sum(r["result"].startswith("PASS") for r in v.values()),
              "qualified": sum(r["result"].startswith("PASS (") or "—" in r["result"][4:] for r in v.values())}
          for k, v in matrices.items()}
browser = {lbl: json.loads((E / f"r02_browser_admin_{lbl}.json").read_text(encoding="utf-8"))
           for lbl in ("with_photo", "replaced", "removed")}
probe = [json.loads(l) for l in (E / "r02_uat_visibility_probe.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

results = {
    "phase": "R02 Profile Pictures, Profile Data Integrity and UI Corrections",
    "date": "2026-11-28",
    "startingMain": "93520da63bb5ca8312d7bbd583f221b8a8a3b3c5",
    "r01Merge": {"pr": 28, "mergeCommit": "93520da", "ciOnMerge": {"Mobile CI": "success", "Admin Web CI": "success"},
                 "mergedWhilePrCheckPending": {"check": "Mobile CI (pull_request)", "mergedAt": "2026-11-27T20:23:09Z",
                                               "checkCompleted": "2026-11-27T20:24:54Z", "conclusion": "success"}},
    "branch": "feat/profile-picture-management",
    "storage": {"kind": "local disk, AES-256-GCM (document_crypto, store profile_images)", "path": "backend/uploads/profile_images/<userId>/<uuid4>.jpg",
                "dbReference": "users.profileImage + users.profileImageMeta (no Base64 in MongoDB)",
                "defaults": {"maxBytes": 5 * 1024 * 1024, "maxPixels": 40_000_000, "maxDimension": 8000, "outputSize": 512,
                             "uploadsPerHour": 20},
                "productionLimitation": "single-server disk; shared/object storage needed for multiple instances"},
    "resolved": {"A05-O1": "R02-BUG-001", "R01-O1": "R02-BUG-003", "R01-O2": "R02-BUG-004"},
    "defects": {"count": len(bugs), "fixed": len(bugs), "items": [{"id": b[0], "severity": b[1].strip(), "component": b[2].strip()} for b in bugs],
                "observations": observations},
    "tests": {
        "backend": {"passed": 1048, "failed": 0, "database": "fresh mediconnect_r02_test", "newFile": {"tests/test_r02_profile.py": 45},
                    "providerAttempts": json.loads((E / "r02_backend_provider_attempts.json").read_text(encoding="utf-8"))["blockedAttempts"],
                    "historicalBaseline": 1003,
                    "firstRunSharedDb": {"passed": 1042, "failed": 5, "causes": ["R02-BUG-006 (fixed)", "R02-O1 test data"]}},
        "flutter": {"passed": 361, "failed": 0, "baseline": 342, "new": {"test/screens/r02_profile_test.dart": 19},
                    "analyze": "no issues", "apk": "debug, --dart-define=API_BASE_URL=http://10.0.2.2:8001"},
        "adminWeb": {"passed": 51, "failed": 0, "baseline": 47, "new": {"src/test/r02DoctorAvatar.test.tsx": 4},
                     "tsc": "ok", "lint": "ok", "build": "ok"},
        "newlyExecutedTotal": 1048 + 361 + 51, "historicalCombinedBaseline": 1392,
        "changedExpectations": ["patient_profile_screen_test: MEDICONNECT PASS now asserted absent (+ Health Summary present)",
                                "a05_support_test C01: fake profile service injected"],
    },
    "matrices": {"counts": counts, "rows": matrices},
    "uat": {"emulatorScreenshots": sorted(p.name for p in (E / "emulator").glob("*.png")),
            "browserScreenshots": sorted(p.name for p in (E / "browser").glob("*.png")),
            "browserRuns": {k: {"steps": [(s["id"], s["status"]) for s in v["steps"]], "blocked": len(v["blockedRequests"]),
                                "pageErrors": len(v["pageErrors"])} for k, v in browser.items()},
            "visibilityProbe": probe,
            "backendRestart": (E / "r02_backend_restart_persistence.txt").read_text(encoding="utf-8").strip().splitlines()},
    "components38": {"VERIFIED": 29, "PARTIAL": 9, "BLOCKED": 0, "changed": False},
    "environment": {"remoteDatabaseAccessed": False, "credentialsChanged": False, "liveAiRequests": 0, "payments": 0,
                    "externalImageHosting": False, "realPhotographs": False, "deployed": False},
    "integration": integration,
    "productionReady": False, "clinicallyValidated": False,
}
(R / "R02_RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(counts), len(bugs), observations, len(results["uat"]["emulatorScreenshots"]), len(results["uat"]["browserScreenshots"]))
