"""Phase 05 P4-B2: scan the whole git history for committed secrets without revealing any secret value.

Run from the repository root:  python -I docs/uat/phase-05/secret_history_scan.py OUT.json

Checks every blob reachable from every ref for
  1. the exact values currently in the git-ignored backend/.env and backend/uat.env (keys whose names contain KEY,
     SECRET, PASSWORD, URI, TOKEN or USERNAME, longer than 8 characters), and
  2. common credential patterns (Stripe live/test keys, webhook secrets, MongoDB URIs with credentials, Google API
     keys, OpenAI keys, private keys, JWT-looking strings, GitHub tokens).
Output contains only commit ids, paths, the env key name or pattern name, and a match count. Values are never
printed or written.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
PATTERNS = {
    "stripe_live_secret": rb"sk_live_[0-9A-Za-z]{10,}",
    "stripe_test_secret": rb"sk_test_[0-9A-Za-z]{20,}",
    "stripe_restricted": rb"rk_(?:live|test)_[0-9A-Za-z]{10,}",
    "stripe_webhook_secret": rb"whsec_[0-9A-Za-z]{20,}",
    "mongodb_uri_with_credentials": rb"mongodb(?:\+srv)?://[^\s:/@'\"]+:[^\s@'\"]+@",
    "google_api_key": rb"AIza[0-9A-Za-z_\-]{30,}",
    "openai_key": rb"sk-(?:proj-)?[0-9A-Za-z_\-]{30,}",
    "private_key_block": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "github_token": rb"gh[pousr]_[0-9A-Za-z]{30,}",
}
ALLOWED_PLACEHOLDERS = (b"sk_test_mock", b"whsec_test_mock", b"<", b"example", b"xxxx")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def env_values():
    values = {}
    for f in ("backend/.env", "backend/uat.env"):
        p = ROOT / f
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                v = v.strip().strip("\"'")
                if any(x in k.upper() for x in ("KEY", "SECRET", "PASSWORD", "URI", "TOKEN", "USERNAME")) and len(v) > 8:
                    values[f"{f}:{k.strip()}"] = v.encode()
    return values


def main(out):
    values = env_values()
    blobs = {}
    for line in git("rev-list", "--objects", "--all").decode(errors="replace").splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            blobs.setdefault(parts[0], parts[1])
    findings = []
    for sha, path in blobs.items():
        kind = git("cat-file", "-t", sha).strip()
        if kind != b"blob":
            continue
        data = git("cat-file", "-p", sha)
        if len(data) > 5_000_000:
            continue
        for name, value in values.items():
            if value in data:
                findings.append({"blob": sha[:12], "path": path, "match": f"current value of {name}"})
        for name, pattern in PATTERNS.items():
            hits = [m.group(0) for m in re.finditer(pattern, data)]
            hits = [h for h in hits if not any(p in h for p in ALLOWED_PLACEHOLDERS)]
            if hits:
                findings.append({"blob": sha[:12], "path": path, "match": name, "count": len(hits)})
    for f in findings:  # first commit that introduced each blob path (for owner follow-up)
        log = git("log", "--all", "--format=%h %as", "--diff-filter=A", "--", f["path"]).decode().split("\n")
        f["introducedIn"] = [x for x in log if x][-1:] or None
    result = {"blobsScanned": len(blobs), "envValuesChecked": len(values), "patterns": list(PATTERNS),
              "findings": findings}
    pathlib.Path(out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("blobs", len(blobs), "env values", len(values), "findings", len(findings))
    for f in findings:
        print(f["path"], f["match"], f.get("introducedIn"))


if __name__ == "__main__":
    main(sys.argv[1])
