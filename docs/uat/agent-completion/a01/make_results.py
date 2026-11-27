"""Build A01_RESULTS.json from the recorded evidence (run from the repository root, after CI finishes).

Usage:  backend\\venv\\Scripts\\python.exe docs\\uat\\agent-completion\\a01\\make_results.py "<ci summary>"
"""
import json
import pathlib
import sys

A = pathlib.Path(__file__).resolve().parent
E = A / "evidence"


def load(name):
    return json.loads((E / name).read_text(encoding="utf-8"))


before, after = load("health_probe_before.json"), load("health_probe_after_deterministic.json")
GENERIC = ("Balanced nutrition, adequate hydration", "Your symptoms can be associated")
generic = lambda d: sum(any(g in c["turns"][-1]["reply"] for g in GENERIC) for c in d["cases"])
vision = load("vision_live_v01.json")["rows"] + load("vision_live_rest.json")["rows"]
retest = {r["fixture"]: r for r in load("vision_live_retest.json")["rows"]}
final_vision = [retest.get(r["fixture"], r) for r in vision]
usage = load("live_usage_metrics_uat.json")

results = {
    "phase": "Agent Completion A01",
    "date": "2026-11-26",
    "branch": "fix/agents-a01-ai-intelligence-vision",
    "baseBranch": "fix/phase-05-final-ai-security-integration",
    "baseCommit": "9363b54",
    "codeCommits": {"providerLayer": "0b8e702", "healthAssistant": "9473ef2", "medicineVision": "d4b2c5c",
                    "mobile": "8b81a5d"},
    "testedCodeCommit": "8b81a5d",
    "merged": False, "deployed": False, "remoteDatabaseAccessed": False, "mongoCredentialsChanged": False,
    "agents": {
        "02": {"name": "AI Health Assistant", "before": "PARTIAL",
               "after": "VERIFIED (local + live Gemini) · clinical review", "engineeringComplete": True},
        "04": {"name": "AI Medicine Image Analysis", "before": "BLOCKED",
               "after": "PARTIAL · live vision verified (synthetic images)", "engineeringComplete": True},
        "32": {"name": "AI Provider Management", "before": "BLOCKED",
               "after": "PARTIAL · Gemini live-verified, OpenAI live blocked (no credits)", "engineeringComplete": True},
    },
    "matrixTotals": {"before": {"VERIFIED": 25, "PARTIAL": 11, "BLOCKED": 2},
                     "after": {"VERIFIED": 26, "PARTIAL": 12, "BLOCKED": 0}},
    "defects": {"ids": [f"A01-N{i:02d}" for i in range(1, 18)], "count": 17, "fixed": 17,
                "critical": ["A01-N01"], "foundLive": ["A01-N07", "A01-N09"],
                "observations": ["A01-O1", "A01-O2", "A01-O3", "A01-O4"]},
    "tests": {
        "backend": {"passed": 865, "failed": 0, "baseline": 782, "newA01": 83,
                    "newByFile": {"test_a01_provider_layer": 26, "test_a01_health_assistant": 36,
                                  "test_a01_medicine_vision": 21}, "database": "mediconnect_a01b_test"},
        "flutter": {"passed": 309, "failed": 0, "baseline": 307, "analyze": "no issues", "debugApk": "built"},
        "adminWeb": {"passed": 39, "failed": 0},
        "phase05LiveUatRegression": {"passed": 12, "total": 12},
        "phase05IntentProbeRegression": {"rows": 25, "differences": 0},
        "changedExpectations": ["test_phase05_ai_architecture::test_s02a (retired id -> gemini-3.8-flash)",
                                "test_comprehensive_stabilization::test_bug023_retired_model_names_are_mapped",
                                "flutter ai_care_assistant_screen_test #11 (no 'High Confidence')"],
    },
    "scenarioMatrices": {
        "provider": {"total": 16, "pass": 15, "blocked": ["A01-P04"]},
        "healthAssistant": {"total": 20, "pass": 20},
        "vision": {"total": 18, "pass": 18},
    },
    "healthProbe": {"cases": len(after["cases"]), "genericTemplatesBefore": generic(before),
                    "genericTemplatesAfter": generic(after)},
    "liveVision": [{"fixture": r["fixture"], "status": r["status"], "model": r["model"], "checks": r["checks"]}
                   for r in final_vision],
    "live": {
        "authorization": "owner 2026-11-26: capped, synthetic data only, no billing changes",
        "geminiModelUsedLive": "gemini-3.5-flash-lite",
        "geminiDefaultModel": "gemini-3.8-flash (live generation not verified: 503 then free-tier daily quota)",
        "openaiDefaultModel": "gpt-6-luna (live generation blocked: insufficient_quota)",
        "gatewayUsage": usage,
        "testSuiteLeakBeforeFix": {"gemini": ">=3", "openai": ">=3"},
    },
    "ci": sys.argv[1] if len(sys.argv) > 1 else "pending",
    "package": "C:\\Users\\REDTECH\\Downloads\\A01_REPORT_PACKAGE.zip",
    "productionReady": False, "clinicallyApproved": False,
}
(A / "A01_RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps({k: results[k] for k in ("healthProbe", "scenarioMatrices", "ci")}, indent=1))
print([(r["fixture"], r["status"]) for r in final_vision])
