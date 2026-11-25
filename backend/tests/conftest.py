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

from app.config.db_safety import isolation_error  # noqa: E402  (pure parsing helper, no settings import)

_problem = isolation_error(os.environ["MONGODB_URI"], os.environ["DATABASE_NAME"], "_test")
if _problem:
    raise SystemExit(
        f"Refusing to run tests: {_problem} The database configured in backend/.env is never used by the test suite."
    )
if not os.environ["STRIPE_SECRET_KEY"].strip().startswith("sk_test_"):
    raise SystemExit("Refusing to run tests with a non-test Stripe key.")
