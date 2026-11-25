"""Test-session safety guard (Phase 03, P03-N22).

The application settings load backend/.env, which may point at a shared or remote database and a real Stripe key.
Before any application module is imported, this file:

1. defaults the test session to the isolated local database ``mediconnect_test`` and mock Stripe keys (the same
   values the backend CI workflow uses), because ``load_dotenv`` never overrides variables that are already set;
2. refuses to run when MONGODB_URI is not a localhost URI or DATABASE_NAME does not end with ``_test``.

So ``pytest`` with no environment can no longer reach the database configured in backend/.env.
"""
import os

os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017/mediconnect_test")
os.environ.setdefault("DATABASE_NAME", "mediconnect_test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_secret_key")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_mock_webhook_secret")

_uri = os.environ["MONGODB_URI"].strip()
_db = os.environ["DATABASE_NAME"].strip()
_local = _uri.startswith(("mongodb://127.0.0.1", "mongodb://localhost"))
if not _local or not _db.endswith("_test"):
    raise SystemExit(
        "Refusing to run tests: MONGODB_URI must be a local mongodb://127.0.0.1 or localhost URI and DATABASE_NAME "
        "must end with '_test'. The database configured in backend/.env is never used by the test suite."
    )
if not os.environ["STRIPE_SECRET_KEY"].startswith("sk_test_"):
    raise SystemExit("Refusing to run tests with a non-test Stripe key.")
