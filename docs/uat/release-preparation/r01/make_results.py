"""Build R01_RESULTS.json from the recorded evidence.

Usage (repository root):  python docs/uat/release-preparation/r01/make_results.py ["<integration json>"]
The optional argument is a JSON object with the PR, CI and merge facts read from GitHub; otherwise "pending".
"""
import json
import pathlib
import sys

R = pathlib.Path(__file__).resolve().parent
E = R / "evidence"
browser = {k: json.loads((E / f"r01_browser_{k}.json").read_text(encoding="utf-8")) for k in ("before", "after")}
integration = json.loads(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].startswith("{") else "pending"

results = {
    "phase": "R01 Branding, Logo and Splash Screen",
    "date": "2026-11-28",
    "startingMain": "96e6fe7dce0578f4387a161c606aa8c6c39006d3",
    "a05Merge": {"pr": 27, "mergeCommit": "96e6fe7", "ciOnMergeCommit": {
        "Backend CI": "success", "Mobile CI": "success", "Admin Web CI": "success"}},
    "branch": "feat/mediconnect-branding",
    "sourceLogo": {"path": "branding/source/mediconnect_logo_source.png", "size": [2172, 724], "mode": "RGBA",
                   "sha256": "b350a5055dbb1463f440c43fd084e3d882763bbcd52c99ff324dc690ed07485a",
                   "symbolCrop": [509, 398], "fullTrim": [1786, 398]},
    "assetsGenerator": "branding/generate_brand_assets.py",
    "placements": {
        "mobile": ["launcher icon (adaptive + legacy + monochrome)", "Android 12+ system splash", "pre-12 launch window",
                   "Flutter splash/loading", "welcome", "login (patient and doctor tabs)", "create account",
                   "forgot/reset password", "reset OTP", "email verification", "admin-access-blocked",
                   "patient dashboard header", "doctor dashboard header", "patient profile header",
                   "doctor registration header", "iOS AppIcon + LaunchImage (not runtime verified)"],
        "admin": ["login card", "sidebar brand area", "full-screen route loading", "auth verification loading",
                  "favicon.ico + 16/32 png + apple-touch-icon", "application-name meta"],
    },
    "labels": {"androidLauncher": {"before": "mediconnect", "after": "MediConnect"},
               "iosDisplayName": {"before": "Mediconnect", "after": "MediConnect"},
               "packageIdChanged": False, "signingChanged": False},
    "splashTagline": "Intelligent Healthcare. Connected Workflows.",
    "tests": {
        "flutter": {"passed": 342, "failed": 0, "baseline": 333, "new": {"test/screens/r01_branding_test.dart": 9},
                    "analyze": "no issues", "debugApk": "built (--dart-define=API_BASE_URL=http://10.0.2.2:8001)"},
        "adminWeb": {"passed": 47, "failed": 0, "baseline": 44, "new": {"src/test/r01Branding.test.tsx": 3},
                     "tsc": "ok", "lint": "ok", "build": "ok"},
        "backend": {"modified": False, "focusedSmoke": {"tests/test_a05_fraud_support.py": {"passed": 27, "failed": 0}},
                    "previousFullSuite": {"passed": 1003, "phase": "A05", "rerunInR01": False}},
        "executedInR01": {"passed": 342 + 47 + 27, "failed": 0},
        "changedExpectations": ["mobile/test/widget_test.dart: splash tagline text (+1 logo assertion)"],
    },
    "browser": {k: {"steps": [{"id": s["id"], "status": s["status"]} for s in b["steps"]],
                    "blockedRequests": len(b["blockedRequests"]), "pageErrors": len(b["pageErrors"]),
                    "icons": [{"href": i["href"].split("/")[-1], "status": i["status"], "contentType": i["contentType"]}
                              for i in b["icons"]]}
                for k, b in browser.items()},
    "screenshots": {"emulator": sorted(p.name for p in (E / "emulator").glob("*.png")),
                    "browser": sorted(p.name for p in (E / "browser").glob("*.png"))},
    "findings": {
        "R01-BUG-001": {"type": "defect, pre-existing", "status": "fixed",
                        "summary": "admin favicon referenced missing /vite.svg (served as text/html)"},
        "R01-O1": "patient bottom navigation 'Profile' overflows 15 px at 360 dp width (pre-existing, not R01)",
        "R01-O2": "welcome/login use fixed light colours; not dark-theme ready (pre-existing)",
        "R01-O3": "splash keeps pre-existing 1.2 s minimum display (not introduced by R01)",
        "R01-O4": "native splash is white in both system modes by design (app theme is an in-app setting)",
        "R01-O5": "raster source: 1024 iOS icon and Android 12 splash icon are upscaled; vector master recommended",
        "R01-O6": "16 px favicon low contrast on dark tab strips",
        "R01-O7": "iOS assets updated but not built or run (no macOS)",
        "R01-O8": "process: first APK built without the UAT dart-define could not reach the backend; rebuilt",
    },
    "carriedForward": ["A05-O1 hard-coded patient Profile health data (mandatory in R02)",
                       "MongoDB credential rotation P5-C1 and other A05 blockers (unchanged by branding)"],
    "environment": {"backend": "127.0.0.1:8001 mediconnect_uat (synthetic)", "emulatorApi": 37,
                    "remoteDatabaseAccessed": False, "credentialsChanged": False, "liveAiRequests": 0,
                    "payments": 0, "deployed": False},
    "integration": integration,
    "productionReady": False,
}
(R / "R01_RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print("screens", len(results["screenshots"]["emulator"]), len(results["screenshots"]["browser"]),
      "after steps", [s["status"] for s in results["browser"]["after"]["steps"]])
