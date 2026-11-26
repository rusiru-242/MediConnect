"""Test-session safety guard (Phase 03 P03-N22, tightened in Phase 04 P04-N01).

The application settings load backend/.env, which may point at a shared or remote database and a real Stripe key.
Before any application module is imported, this file:

1. defaults the test session to the isolated local database ``mediconnect_test`` and mock Stripe keys (the same
   values the backend CI workflow uses), because ``load_dotenv`` never overrides variables that are already set;
2. refuses to run unless every host in MONGODB_URI is a loopback host and DATABASE_NAME (and any database named in
   the URI) ends with ``_test``. Hosts are parsed, so ``localhost.example.com``, ``127.0.0.1.nip.io``,
   ``user@remote`` tricks, ``mongodb+srv://`` and multi-host seed lists are all refused;
3. refuses a Stripe key that is not a test key.

So ``pytest`` with no environment can never reach the database configured in backend/.env.
"""
import os

os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017/mediconnect_test")
os.environ.setdefault("DATABASE_NAME", "mediconnect_test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_mock_webhook_secret")
# Phase 05: the test session never inherits the JWT secret, environment or provider keys from backend/.env.
os.environ.setdefault("ENVIRONMENT", "test")
# A01-N06: the comment above was not true for provider keys. load_dotenv() filled GEMINI_API_KEY / OPENAI_API_KEY from
# backend/.env, so tests that did not patch the network made real provider calls. An empty value set here wins over
# .env (load_dotenv never overrides an existing variable), so every test runs with no provider unless it patches one.
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
# A02-BUG-002: the same applied to e-mail. SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD came from backend/.env, so five
# doctor-approval tests submitted real messages through the owner's SMTP account on every local run (13 connection
# attempts per run, measured on the A02 baseline). Delivery providers are blank unless a test sets them.
for _name in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL", "TWILIO_ACCOUNT_SID",
              "TWILIO_AUTH_TOKEN", "TWILIO_MESSAGING_SERVICE_SID", "FIREBASE_CREDENTIALS_PATH",
              "FIREBASE_SERVICE_ACCOUNT_JSON", "GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ[_name] = ""
if not os.environ.get("DOCUMENT_ENCRYPTION_KEYS"):  # a throwaway per-session test key (never a deployment key)
    import base64 as _b64
    os.environ["DOCUMENT_ENCRYPTION_KEYS"] = "test-session:" + _b64.b64encode(os.urandom(32)).decode()
if not os.environ.get("JWT_SECRET"):
    import secrets as _secrets
    os.environ["JWT_SECRET"] = os.environ["JWT_SECRET_KEY"] = _secrets.token_urlsafe(48)

from app.config.db_safety import isolation_error  # noqa: E402  (pure parsing helper, no settings import)

_problem = isolation_error(os.environ["MONGODB_URI"], os.environ["DATABASE_NAME"], "_test")
if _problem:
    raise SystemExit(
        f"Refusing to run tests: {_problem} The database configured in backend/.env is never used by the test suite."
    )
if not os.environ["STRIPE_SECRET_KEY"].strip().startswith("sk_test_"):
    raise SystemExit("Refusing to run tests with a non-test Stripe key.")


def _gha_escape(text, prop=False):
    text = str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return text.replace(":", "%3A").replace(",", "%2C") if prop else text


def pytest_runtest_logreport(report):
    """On GitHub Actions, surface each failing test as an annotation (readable without log access)."""
    if os.environ.get("GITHUB_ACTIONS") == "true" and report.failed:
        detail = (report.longreprtext or "")[-900:]
        print(f"\n::error title={_gha_escape(report.nodeid, prop=True)}::{_gha_escape(detail)}", flush=True)


import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _fresh_rate_limit_counters():
    """Rate-limit counters are shared through MongoDB since Phase 05, so they survive between pytest runs. Each test
    session starts from empty counters in its own (local, *_test) database."""
    from app.config.database import DatabaseManager
    from app.utils.rate_limiter import COLLECTION
    try:
        DatabaseManager.get_database()[COLLECTION].delete_many({})
    except Exception:
        pass
    yield


_LIVE_AI_HOSTS = ("generativelanguage.googleapis.com", "api.openai.com")


@pytest.fixture(autouse=True)
def _no_live_ai_provider_calls(monkeypatch):
    """A01-N06 second guard: a request that reaches the transport for a live AI provider host fails as a network
    error. Tests that patch requests.post never reach the transport, so test doubles keep working."""
    import requests
    import requests.adapters

    real_send = requests.adapters.HTTPAdapter.send

    def guarded(self, request, *args, **kwargs):
        if any(host in (request.url or "") for host in _LIVE_AI_HOSTS):
            raise requests.ConnectionError("live AI provider call blocked in tests")
        return real_send(self, request, *args, **kwargs)

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", guarded)


# Real delivery providers (A02-BUG-002). Loopback hosts stay reachable for the local SMTP test server.
_DELIVERY_HOSTS = ("smtp.gmail.com", "api.twilio.com", "fcm.googleapis.com", "oauth2.googleapis.com",
                   "smtp.sendgrid.net", "email-smtp.")


@pytest.fixture(autouse=True)
def _no_real_delivery_provider_calls(monkeypatch):
    """No test can open a connection to a real e-mail, SMS or push provider, whatever settings it patches."""
    import socket

    real_create = socket.create_connection

    def guarded(address, *args, **kwargs):
        host = str(address[0]).lower()
        if any(host == h or host.startswith(h) or host.endswith("." + h) for h in _DELIVERY_HOSTS):
            raise ConnectionRefusedError("real delivery provider blocked in tests")
        return real_create(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", guarded)
