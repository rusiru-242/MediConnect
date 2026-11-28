"""Redacted secret scan of git-tracked files (R03). Prints file, line and pattern type only; never the value.

Usage (repository root): python docs/uat/release-preparation/r03/secret_scan.py [out.json]
"""
import json
import re
import subprocess
import sys

PATTERNS = {
    "mongodb_uri_with_credentials": rb"mongodb(\+srv)?://[^\s:/@\"']+:[^\s@\"']+@",
    "stripe_live_secret": rb"sk_live_[A-Za-z0-9]{10,}",
    "stripe_test_secret_real_length": rb"sk_test_[A-Za-z0-9]{24,}",
    "stripe_restricted": rb"rk_(live|test)_[A-Za-z0-9]{10,}",
    "stripe_webhook_secret_real_length": rb"whsec_[A-Za-z0-9]{24,}",
    "google_api_key": rb"AIza[0-9A-Za-z_-]{35}",
    "openai_key": rb"sk-(proj-)?[A-Za-z0-9_-]{32,}",
    "private_key_block": rb"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----",
    "jwt_token": rb"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}",
    "firebase_service_account": rb"\"type\":\s*\"service_account\"",
}
SKIP = re.compile(r"\.(png|jpg|jpeg|webp|gif|ico|apk|zip|ttf|otf|woff2?|lock)$|pubspec\.lock$|package-lock\.json$", re.I)

files = subprocess.run(["git", "ls-files", "-z"], capture_output=True).stdout.decode().split("\0")
hits = []
for f in filter(None, files):
    if SKIP.search(f):
        continue
    try:
        data = open(f, "rb").read()
    except OSError:
        continue
    for name, pat in PATTERNS.items():
        for m in re.finditer(pat, data):
            hits.append({"file": f, "line": data.count(b"\n", 0, m.start()) + 1, "type": name})
env_files = [f for f in files if re.search(r"(^|/)\.env($|\.)", f) and not f.endswith(".example")]
result = {"trackedFiles": len([f for f in files if f]), "hits": hits, "trackedEnvFiles": env_files}
print(json.dumps({"trackedFiles": result["trackedFiles"], "hitCount": len(hits), "trackedEnvFiles": env_files}))
for h in hits:
    print(h["file"], h["line"], h["type"])
if len(sys.argv) > 1:
    open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(result, indent=2))
