"""P04-N01: the database isolation guard must refuse every non-local or non-isolated target.

Phase 03 used a prefix test (``uri.startswith("mongodb://localhost")``), which accepted hosts such as
``localhost.example.com`` and multi-host seed lists that include a remote server.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config.db_safety import is_local_mongodb_uri, isolation_error, redacted_target

BACKEND = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("uri", [
    "mongodb://127.0.0.1:27017/mediconnect_test",
    "mongodb://localhost:27017",
    "mongodb://localhost",
    "mongodb://[::1]:27017/mediconnect_test",
    "mongodb://user:secret@127.0.0.1:27017/mediconnect_test?authSource=admin",
    "mongodb://127.0.0.1:27017,localhost:27018/?replicaSet=rs0",
])
def test_local_uris_are_accepted(uri):
    assert is_local_mongodb_uri(uri)


@pytest.mark.parametrize("uri", [
    "mongodb://localhost.example.com:27017/mediconnect_test",
    "mongodb://127.0.0.1.nip.io/mediconnect_test",
    "mongodb://localhost:27017,cluster0.example.net:27017/mediconnect_test",
    "mongodb+srv://user:secret@cluster0.example.net/mediconnect_test",
    "mongodb://127.0.0.1:27017@cluster0.example.net/mediconnect_test",
    "mongodb://cluster0.example.net/mediconnect_test",
    "MONGODB://localhost",
    "",
    "localhost:27017",
])
def test_remote_or_ambiguous_uris_are_refused(uri):
    assert not is_local_mongodb_uri(uri)


@pytest.mark.parametrize("uri,name,ok", [
    ("mongodb://127.0.0.1:27017/mediconnect_test", "mediconnect_test", True),
    ("mongodb://127.0.0.1:27017", "mediconnect_test", True),
    ("mongodb://127.0.0.1:27017/mediconnect_test", "mediconnect", False),
    ("mongodb://127.0.0.1:27017/mediconnect", "mediconnect_test", False),
    ("mongodb://127.0.0.1:27017/mediconnect_uat", "mediconnect_uat", False),
])
def test_test_database_name_is_required(uri, name, ok):
    assert (isolation_error(uri, name, "_test") is None) is ok


def test_redacted_target_never_contains_credentials():
    meta = redacted_target("mongodb+srv://someone:hunter2@cluster0.example.net/x", "mediconnect")
    assert "hunter2" not in repr(meta) and "someone" not in repr(meta)
    assert meta["local"] is False


@pytest.mark.parametrize("uri,name", [
    ("mongodb://localhost.example.com:27017/mediconnect_test", "mediconnect_test"),
    ("mongodb://127.0.0.1:27017/mediconnect", "mediconnect"),
    ("mongodb://localhost:27017,cluster0.example.net:27017/mediconnect_test", "mediconnect_test"),
])
def test_conftest_guard_refuses_unsafe_target(uri, name):
    """Loading tests/conftest.py with an unsafe environment exits before anything connects."""
    env = {**os.environ, "MONGODB_URI": uri, "DATABASE_NAME": name}
    code = "import runpy; runpy.run_path('tests/conftest.py')"
    result = subprocess.run([sys.executable, "-c", code], cwd=str(BACKEND), env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert "Refusing to run tests" in (result.stdout + result.stderr)


def test_conftest_guard_accepts_local_test_target():
    env = {**os.environ, "MONGODB_URI": "mongodb://127.0.0.1:27017/mediconnect_test", "DATABASE_NAME": "mediconnect_test",
           "STRIPE_SECRET_KEY": "sk_test_mock_secret_key"}
    result = subprocess.run([sys.executable, "-c", "import runpy; runpy.run_path('tests/conftest.py')"],
                            cwd=str(BACKEND), env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr


def test_conftest_guard_refuses_live_stripe_key():
    env = {**os.environ, "MONGODB_URI": "mongodb://127.0.0.1:27017/mediconnect_test", "DATABASE_NAME": "mediconnect_test",
           "STRIPE_SECRET_KEY": "sk_live_not_a_real_key"}
    result = subprocess.run([sys.executable, "-c", "import runpy; runpy.run_path('tests/conftest.py')"],
                            cwd=str(BACKEND), env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "non-test Stripe key" in (result.stdout + result.stderr)
