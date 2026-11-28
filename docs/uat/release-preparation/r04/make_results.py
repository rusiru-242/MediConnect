"""Build R04_RESULTS.json from the recorded R04 evidence.

Usage (repository root):  python docs/uat/release-preparation/r04/make_results.py ['<integration json>']
"""
import json
import pathlib
import sys

R = pathlib.Path(__file__).resolve().parent
E = R / "evidence"
integration = json.loads(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].startswith("{") else "pending"
manifest = json.loads((E / "r04_release_manifest.json").read_text(encoding="utf-8"))
links = json.loads((E / "r04_link_check.json").read_text(encoding="utf-8"))
scan = json.loads((E / "r04_secret_scan_tracked.json").read_text(encoding="utf-8"))
shots = json.loads((R.parents[2] / "assets" / "screenshots" / "SCREENSHOTS.json").read_text(encoding="utf-8"))
apk = next(f for f in manifest["files"] if f["path"].startswith("android/"))
admin = next(f for f in manifest["files"] if f["path"].startswith("admin-web/"))

results = {
    "phase": "R04 Final Academic Release Preparation and Professional Documentation",
    "date": "2026-11-28",
    "release": {"version": "v1.0.0-academic", "classification": "Academic Demonstration / Engineering Preview",
                "existingTags": [], "published": False, "publicReleaseEligible": False,
                "reason": "historical database credential exposure without confirmed remediation; R04 not yet merged; no owner approval"},
    "startingMain": "1f95285",
    "r03Merge": {"pr": 31, "merge": "1f95285", "head": "2ed0ce3", "mergedWithChecksPending": True,
                 "ciOnMain": {"Backend CI": "success", "Mobile CI": "success"}},
    "branch": "release/mediconnect-v1",
    "documentation": {"readme": "rewritten", "developerSetup": "rewritten", "architectureOverview": "new (4 Mermaid diagrams)",
                      "linksChecked": len(links["results"]), "brokenLinks": links["broken"],
                      "screenshots": [s["file"] for s in shots]},
    "apk": {"type": "debug (emulator only)", "versionName": "1.0.0", "versionCode": 1,
            "apiBaseUrl": "http://10.0.2.2:8001", "command": "flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001",
            "buildOutput": "mobile/build/app/outputs/flutter-apk/app-debug.apk", "packagedPath": str(pathlib.Path(manifest["directory"]) / apk["path"]),
            "bytes": apk["bytes"], "sha256": apk["sha256"], "signed": False,
            "install": "success", "launch": "welcome screen, no crash", "login": "patient dashboard from 10.0.2.2:8001",
            "secretScan": "none; one Stripe test publishable key (informational)"},
    "adminWeb": {"typecheck": "ok", "lint": "ok", "tests": {"passed": 51, "failed": 0}, "build": "ok", "output": "admin-web/dist",
                 "archive": str(pathlib.Path(manifest["directory"]) / admin["path"]), "archiveSha256": admin["sha256"],
                 "preview": "login 200, favicon 200, logo loaded, 0 page errors", "secretScan": "none", "deployed": False},
    "newlyExecuted": {"backendSmoke": {"passed": 100, "failed": 0, "database": "fresh mediconnect_r04smoke_test", "providerAttempts": 0},
                      "flutterSmoke": {"passed": 40, "failed": 0}, "flutterAnalyze": "no issues", "adminTests": {"passed": 51},
                      "automatedTotal": 191},
    "historicalR03": {"backend": 1064, "flutter": 362, "adminWeb": 51, "total": 1477, "components": {"VERIFIED": 29, "PARTIAL": 9, "BLOCKED": 0},
                      "tracker": {"items": 340, "defects": 262, "fixed": 261, "open": ["BUG-039"]}},
    "secretScans": {"trackedFiles": {k: v for k, v in scan.items() if k != "hits"}, "apk": "clean", "adminDist": "clean",
                    "releasePackage": "clean", "publishableKeyInformational": "mobile/lib/core/constants/api_constants.dart:435 (pk_test_)"},
    "credentialRemediation": "NOT CONFIRMED",
    "releasePackage": {"zip": manifest["zip"], "bytes": manifest["zipBytes"], "sha256": manifest["zipSha256"], "files": len(manifest["files"])},
    "r05Handover": "docs/uat/release-preparation/r04/R04_R05_DEMO_HANDOVER.md",
    "integration": integration,
    "productionReady": False, "clinicallyValidated": False,
}
(R / "R04_RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(results["apk"]["sha256"], results["releasePackage"]["bytes"], len(results["documentation"]["screenshots"]))
