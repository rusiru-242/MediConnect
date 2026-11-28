"""R04: verify relative links and image paths in the release documentation (no network requests).

Usage (repository root): python docs/uat/release-preparation/r04/check_links.py
"""
import json
import pathlib
import re
import sys

DOCS = ["README.md", "docs/DEVELOPER_SETUP.md", "docs/ARCHITECTURE_OVERVIEW.md",
        "docs/uat/release-preparation/r04/R04_RELEASE_NOTES.md", "docs/uat/release-preparation/r04/R04_R05_DEMO_HANDOVER.md",
        "docs/uat/MEDICONNECT_FINAL_ENGINEERING_SUMMARY.md"]
link = re.compile(r"\]\(([^)\s]+)\)|<img src=\"([^\"]+)\"")
results, broken = [], []
for doc in DOCS:
    p = pathlib.Path(doc)
    text = p.read_text(encoding="utf-8")
    anchors = {re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-") for h in re.findall(r"^#+ (.+)$", text, re.M)}
    for m in link.finditer(text):
        target = m.group(1) or m.group(2)
        if target.startswith(("http://", "https://", "mailto:")):
            results.append({"doc": doc, "target": target, "kind": "external (not fetched)"})
            continue
        if target.startswith("#"):
            ok = target[1:] in anchors
        else:
            ok = (p.parent / target.split("#")[0]).resolve().exists()
        results.append({"doc": doc, "target": target, "ok": ok})
        if not ok:
            broken.append(f"{doc} -> {target}")
print(json.dumps({"checked": len(results), "broken": broken}, indent=1))
if len(sys.argv) > 1:
    pathlib.Path(sys.argv[1]).write_text(json.dumps({"results": results, "broken": broken}, indent=2), encoding="utf-8")
sys.exit(1 if broken else 0)
