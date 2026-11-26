"""A01 live provider checks (A01-P01..P16 live rows) through the application's own provider layer.

Authorized by the owner on 2026-11-26: capped live requests with synthetic data only (no patient data).
Run from backend/:  venv\\Scripts\\python.exe ..\\docs\\uat\\agent-completion\\a01\\live_provider_check.py OUT.json [rows]

Safety:
* The database is forced to the local UAT database before the app is imported (usage metrics only), so the remote
  URI in backend/.env is never used.
* Keys are read by the app settings from backend/.env and are never printed or written; every recorded string is
  scrubbed for the key values before it is stored.
* AI_DAILY_REQUEST_LIMIT is set to 150 for this process, enforced by the gateway.
"""
import json
import os
import pathlib
import sys
import time

os.environ["MONGODB_URI"] = "mongodb://127.0.0.1:27017/mediconnect_uat"
os.environ["DATABASE_NAME"] = "mediconnect_uat"
os.environ["ENVIRONMENT"] = "staging"
os.environ["AI_DAILY_REQUEST_LIMIT"] = "150"
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("OPENAI_MODEL", None)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "backend"))

from dotenv import dotenv_values  # noqa: E402

_ENV = dotenv_values(pathlib.Path(__file__).resolve().parents[4] / "backend" / ".env")
for name in ("GEMINI_API_KEY", "OPENAI_API_KEY"):
    os.environ[name] = (_ENV.get(name) or "").strip()
SECRETS = [v for v in (os.environ["GEMINI_API_KEY"], os.environ["OPENAI_API_KEY"]) if v]

from pydantic import BaseModel  # noqa: E402

from app.agents import llm_client as llm  # noqa: E402
from app.agents import provider_gateway as gw  # noqa: E402
from app.config.settings import settings  # noqa: E402

assert settings.MONGODB_URI.startswith("mongodb://127.0.0.1"), "local database only"
GEMINI_LIVE_MODEL = os.environ.get("A01_GEMINI_MODEL", "gemini-3.8-flash")
settings.GEMINI_MODEL, settings.OPENAI_MODEL = GEMINI_LIVE_MODEL, "gpt-6-luna"


def scrub(value):
    text = json.dumps(value, default=str, ensure_ascii=False)
    for secret in SECRETS:
        text = text.replace(secret, "<redacted>")
    return json.loads(text)


class Pong(BaseModel):
    answer: str
    ok: bool


PONG_SCHEMA = llm.strict_object({"answer": {"type": "string"}, "ok": {"type": "boolean"}})


def pong(providers, label):
    started = time.monotonic()
    try:
        res = llm.generate_json(task="probe", system="You are a test endpoint. Synthetic test only.",
                                user="Reply with JSON: answer='pong', ok=true.", model_cls=Pong, schema=PONG_SCHEMA,
                                providers=providers, max_output_tokens=64, temperature=0, timeout=30)
        return {"row": label, "result": "ok", "provider": res.provider, "model": res.model,
                "data": res.data.model_dump(), "attempts": res.attempts, "latencyMs": res.latency_ms}
    except llm.LLMUnavailable as exc:
        return {"row": label, "result": "unavailable", "attempts": exc.attempts,
                "elapsedS": round(time.monotonic() - started, 1)}


def main(out_path, rows):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out = {"authorization": "owner, 2026-11-26, capped synthetic-only", "rows": []}
    if "P03" in rows:
        out["rows"].append(pong(["gemini"], f"A01-P03 Gemini live text ({GEMINI_LIVE_MODEL})"))
    if "P04" in rows:
        out["rows"].append(pong(["openai"], "A01-P04 OpenAI live text (gpt-6-luna)"))
    if "P06" in rows:
        real = os.environ["GEMINI_API_KEY"]
        settings.GEMINI_API_KEY = "invalid-key-for-a01-test"
        out["rows"].append(pong(["gemini"], "A01-P06 invalid API key (Gemini)"))
        settings.GEMINI_API_KEY = real
    if "P07" in rows:
        settings.GEMINI_MODEL = "gemini-a01-no-such-model"
        out["rows"].append(pong(["gemini"], "A01-P07 invalid model id (Gemini)"))
        settings.GEMINI_MODEL = GEMINI_LIVE_MODEL
    if "P11" in rows:
        # OpenAI has no credits (owner action), so it is configured as the primary here to show a live primary
        # failure followed by a live answer from the secondary provider.
        out["rows"].append(pong(["openai", "gemini"], "A01-P11/P12 primary openai fails, secondary gemini answers"))
    if "P13" in rows:
        # gemini-3.8-flash's free-tier daily quota was exhausted on 2026-11-26 and OpenAI has no credits.
        settings.GEMINI_MODEL = "gemini-3.8-flash"
        out["rows"].append(pong(["gemini", "openai"], "A01-P13 both providers unavailable (live)"))
        settings.GEMINI_MODEL = GEMINI_LIVE_MODEL
    out["providerStatus"] = {p: gw.provider_status(p) for p in ("gemini", "openai")}
    out = scrub(out)
    for row in out["rows"]:
        print(row["row"], "=>", row["result"], [(a.get("provider"), a.get("category")) for a in row.get("attempts", [])])
    pathlib.Path(out_path).write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2].split(",") if len(sys.argv) > 2 else ["P03", "P04", "P06", "P07", "P11"])
