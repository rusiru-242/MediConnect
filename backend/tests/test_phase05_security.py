"""Phase 05 security regression tests: fail-closed configuration, JWT hardening, session revocation, refresh-token
rotation races and replay, authentication telemetry, the shared rate limiter and router mounting.

IDs (P05-Nxx) refer to docs/uat/phase-05/PHASE_05_BUG_FIX_REPORT.md. Nothing here connects to a non-local database:
the configuration checks are pure functions, and DatabaseManager is only exercised with a remote URI after its client
cache is cleared, so the refusal happens before any MongoClient is created.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import subprocess
import sys
import textwrap
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId
import jwt
import pytest

from app.config import runtime_safety as rs
from app.config.settings import settings
from app.models.appointment import utc_now
from app.utils.security import create_access_token, hash_password
from tests.test_payment import _make_test_patient, client, db  # noqa: F401  (db fixture)
from tests.test_phase02_booking_payment import _admin, _auth

@pytest.fixture(autouse=True)
def _reset_auth_limiters():
    from app.utils.rate_limiter import auth_login_limiter, auth_refresh_limiter
    auth_login_limiter.reset()
    auth_refresh_limiter.reset()
    yield


STRONG = "q8V3n_Zk2pLr7Tx4Wm9Yb1Cd6Fh0Jg5Ns-AeUoIiOyRt"
REMOTE = "mongodb+srv://user:pw@cluster0.example.net/?retryWrites=true"


# ------------------------------------------------------------------------------------------------ P05-N01 (P4-B5)
@pytest.mark.parametrize("env,uri,name,allow,ok", [
    ("development", "mongodb://127.0.0.1:27017", "mediconnect", False, True),
    ("development", REMOTE, "mediconnect", False, False),          # the pre-Phase-05 silent fallback
    ("development", "mongodb://localhost.example.com:27017", "mediconnect", False, False),
    ("development", REMOTE, "mediconnect", True, True),             # deliberate owner opt-in
    ("test", "mongodb://127.0.0.1:27017", "mediconnect_test", False, True),
    ("test", "mongodb://127.0.0.1:27017", "mediconnect", False, False),
    ("test", REMOTE, "mediconnect_test", True, False),               # tests can never opt in
    ("staging", REMOTE, "mediconnect", False, True),
    ("production", REMOTE, "mediconnect", False, True),
    ("prod", REMOTE, "mediconnect", False, False),                   # unknown environment fails closed
    ("development", None, "mediconnect", False, False),
])
def test_n01_database_target_rules(env, uri, name, allow, ok):
    assert (rs.database_target_error(uri, name, env, allow) is None) is ok


def test_n01_database_manager_refuses_remote_in_development_before_connecting():
    from app.config.database import DatabaseManager
    saved = (DatabaseManager._client, DatabaseManager._db)
    DatabaseManager._client = DatabaseManager._db = None
    try:
        with patch.object(settings, "ENVIRONMENT", "development"), patch.object(settings, "MONGODB_URI", REMOTE), \
                patch.object(settings, "ALLOW_REMOTE_DATABASE", False), \
                patch("app.config.database.MongoClient") as mongo_client:
            with pytest.raises(ConnectionError, match="non-local"):
                DatabaseManager.get_client()
            mongo_client.assert_not_called()
    finally:
        DatabaseManager._client, DatabaseManager._db = saved


def test_n01_backend_without_environment_refuses_remote_env_file_in_a_subprocess(tmp_path):
    """A fresh interpreter with ENVIRONMENT unset and a remote URI (as backend/.env has) must refuse to start."""
    code = textwrap.dedent("""
        import sys
        from app.config.settings import settings
        from app.config.runtime_safety import startup_errors
        errors = startup_errors(settings)
        print("REFUSED" if any("non-local" in e for e in errors) else "ALLOWED")
    """)
    env = {k: v for k, v in os.environ.items() if k not in ("ENVIRONMENT", "ALLOW_REMOTE_DATABASE")}
    env.update({"MONGODB_URI": REMOTE, "DATABASE_NAME": "mediconnect", "JWT_SECRET": STRONG, "ENVIRONMENT": ""})
    out = subprocess.run([sys.executable, "-c", code], cwd=os.path.dirname(os.path.dirname(__file__)), env=env,
                         capture_output=True, text=True, timeout=60)
    assert "REFUSED" in out.stdout, out.stderr[-500:]


# ------------------------------------------------------------------------------------------------ P05-N04 (P4-B2)
@pytest.mark.parametrize("secret,env,ok", [
    ("mediconnect", "development", False),               # the class of value found in backend/.env (P4-B2)
    ("short-but-random-9f", "production", False),
    ("a" * 64, "production", False),                     # long but no variety
    ("ci_test_secret_key_minimum_32_bytes_long_123456", "staging", False),  # public CI value
    (STRONG, "production", True),
    (STRONG, "development", True),
    ("anything", "test", True),
    ("", "test", False),
])
def test_n04_jwt_secret_strength(secret, env, ok):
    assert (rs.jwt_secret_error(secret, env) is None) is ok


def test_n04_jwt_algorithm_and_lifetime_rules():
    assert rs.jwt_settings_errors("HS256", 15, 7) == []
    assert rs.jwt_settings_errors("none", 15, 7)
    assert rs.jwt_settings_errors("RS256", 15, 7)
    assert rs.jwt_settings_errors("HS256", 24 * 60, 7)
    assert rs.jwt_settings_errors("HS256", 15, 365)


def test_n04_startup_refuses_weak_secret_and_live_stripe_outside_production():
    cfg = SimpleNamespace(ENVIRONMENT="development", MONGODB_URI="mongodb://127.0.0.1:27017", DATABASE_NAME="x",
                          ALLOW_REMOTE_DATABASE=False, JWT_SECRET="mediconnect", JWT_ALGORITHM="HS256",
                          ACCESS_TOKEN_EXPIRE_MINUTES=15, REFRESH_TOKEN_EXPIRE_DAYS=7,
                          STRIPE_SECRET_KEY="sk_live_" + "x" * 20)
    errors = rs.startup_errors(cfg)
    assert any("known default" in e for e in errors) and any("live Stripe" in e for e in errors)
    assert all("mediconnect" not in e.split("JWT_SECRET")[-1] for e in errors)  # the secret is never echoed


# ------------------------------------------------------------------------------------------------ P05-N05 token claims
def _forge(claims, secret=None, alg="HS256"):
    return jwt.encode(claims, secret or settings.JWT_SECRET, algorithm=alg)


def test_n05_access_tokens_require_issuer_audience_type_and_jti(db):
    patient = _make_test_patient(db, "P05N05")
    good = jwt.decode(patient["token"], settings.JWT_SECRET, algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
    assert good["iss"] == settings.JWT_ISSUER and good["jti"] and good["type"] == "access"
    now = int(datetime.now(timezone.utc).timestamp())
    base = {"sub": patient["id"], "role": "PATIENT", "type": "access", "iat": now, "exp": now + 600,
            "iss": settings.JWT_ISSUER, "aud": settings.JWT_AUDIENCE, "jti": "x1"}
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {_forge(base)}"}).status_code == 200
    for missing in ("aud", "iss", "jti", "type"):
        claims = {k: v for k, v in base.items() if k != missing}
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {_forge(claims)}"})
        assert res.status_code == 401, missing
    for field, value in (("aud", "other-app"), ("iss", "evil"), ("type", "refresh")):
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {_forge({**base, field: value})}"})
        assert res.status_code == 401, field
    unsigned = jwt.encode(base, key=None, algorithm="none") if hasattr(jwt, "encode") else None
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401
    expired = _forge({**base, "iat": now - 7200, "exp": now - 3600})
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def _patient(db, suffix):
    """Test patient whose stored e-mail is lower case (login normalises e-mail; the shared helper keeps the case)."""
    patient = _make_test_patient(db, suffix)
    patient["email"] = patient["email"].lower()
    db["users"].update_one({"_id": ObjectId(patient["id"])}, {"$set": {"email": patient["email"]}})
    return patient


def _login(email, password="Secret123!"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


# ------------------------------------------------------------------------------------------------ P05-N06 logout
def test_n06_logout_revokes_the_access_token_too(db):
    patient = _patient(db, "P05N06")
    session = _login(patient["email"])
    headers = {"Authorization": f"Bearer {session['accessToken']}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", json={"refreshToken": session["refreshToken"]},
                       headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.post("/api/auth/refresh", json={"refreshToken": session["refreshToken"]}).status_code == 401
    entry = db["revoked_access_tokens"].find_one({"userId": patient["id"]})
    assert entry and entry["expiresAt"] > utc_now()  # removed by the TTL index when the token would expire anyway


# ------------------------------------------------------------------------------------------------ P05-N02 refresh race
def test_n02_concurrent_refresh_of_one_token_yields_exactly_one_session(db):
    patient = _patient(db, "P05N02")
    refresh = _login(patient["email"])["refreshToken"]

    def attempt(_):
        return client.post("/api/auth/refresh", json={"refreshToken": refresh}).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(attempt, range(8)))
    assert codes.count(200) == 1 and codes.count(401) == 7, codes


def test_n02_replayed_rotated_refresh_token_revokes_the_family_and_is_recorded(db):
    patient = _patient(db, "P05N02R")
    first = _login(patient["email"])["refreshToken"]
    second = client.post("/api/auth/refresh", json={"refreshToken": first}).json()["refreshToken"]
    assert client.post("/api/auth/refresh", json={"refreshToken": first}).status_code == 401  # replay
    assert client.post("/api/auth/refresh", json={"refreshToken": second}).status_code == 401  # family revoked
    event = db["security_events"].find_one({"metadata.eventType": "REFRESH_TOKEN_REPLAY", "actorId": patient["id"]})
    assert event and first not in repr(event) and second not in repr(event)  # no raw token values stored
    assert set(event["metadata"]) == {"eventType", "accountRef", "sourceRef", "reason"}


# ------------------------------------------------------------------------------------------------ P05-N03
def test_n03_refresh_for_a_removed_account_is_401_not_500(db):
    patient = _patient(db, "P05N03")
    refresh = _login(patient["email"])["refreshToken"]
    db["users"].delete_one({"_id": ObjectId(patient["id"])})
    assert client.post("/api/auth/refresh", json={"refreshToken": refresh}).status_code == 401


# ------------------------------------------------------------------------------------------------ P05-N07 suspension
def test_n07_tokens_issued_before_suspension_stay_invalid_after_reinstatement(db):
    admin, patient = _admin(db), _patient(db, "P05N07")
    old = {"Authorization": f"Bearer {patient['token']}"}
    assert client.patch(f"/api/admin/users/{patient['id']}/status", json={"accountStatus": "SUSPENDED", "reason": "UAT"},
                        headers=_auth(admin)).status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401
    import time
    time.sleep(1.1)
    assert client.patch(f"/api/admin/users/{patient['id']}/status", json={"accountStatus": "ACTIVE", "reason": "UAT"},
                        headers=_auth(admin)).status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401
    assert client.get("/api/auth/me", headers=_auth({"token": _login(patient["email"])["accessToken"]})).status_code == 200


# ------------------------------------------------------------------------------------------------ P05-N08 (P4-B9)
def test_n08_failed_logins_are_recorded_without_credentials_or_enumeration(db):
    patient = _patient(db, "P05N08")
    unknown = f"nobody_{ObjectId()}@mediconnect.lk"
    r1 = client.post("/api/auth/login", json={"email": patient["email"], "password": "Wrong-pass-1"})
    r2 = client.post("/api/auth/login", json={"email": unknown, "password": "Wrong-pass-1"})
    assert r1.status_code == r2.status_code == 401 and r1.json() == r2.json()  # same answer: no enumeration
    events = list(db["security_events"].find({"metadata.eventType": "LOGIN_FAILED"}).sort("timestamp", -1).limit(5))
    dump = repr(events)
    assert patient["email"] not in dump and unknown not in dump and "Wrong-pass-1" not in dump
    refs = {e["metadata"]["accountRef"] for e in events}
    from app.services.security_event_service import SecurityEventService as S
    assert S.pseudonym(patient["email"]) in refs and S.pseudonym(unknown) in refs


def test_n08_repeated_failures_raise_one_brute_force_signal_and_do_not_lock(db):
    patient = _patient(db, "P05N08B")
    for _ in range(6):
        client.post("/api/auth/login", json={"email": patient["email"], "password": "Wrong-pass-2"})
    from app.services.security_event_service import SecurityEventService as S
    ref = S.pseudonym(patient["email"])
    assert db["security_events"].count_documents({"category": "BRUTE_FORCE", "metadata.accountRef": ref}) == 1
    assert client.post("/api/auth/login", json={"email": patient["email"], "password": "Secret123!"}).status_code == 200


# ------------------------------------------------------------------------------------------------ P05-N09 (BUG-038)
def test_n09_rate_limit_is_shared_between_limiter_instances():
    from app.utils.rate_limiter import SlidingWindowRateLimiter
    name = f"p05_shared_{ObjectId()}"
    a = SlidingWindowRateLimiter(max_requests=5, window_seconds=60, name=name)
    b = SlidingWindowRateLimiter(max_requests=5, window_seconds=60, name=name)  # "another process"
    for limiter in (a, b, a, b, a):
        limiter.check("1.2.3.4")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        b.check("1.2.3.4")
    assert exc.value.status_code == 429 and exc.value.headers["Retry-After"] == "60"
    a.check("5.6.7.8")  # other keys unaffected


def test_n09_rate_limit_holds_across_separate_os_processes():
    name = f"p05_proc_{ObjectId()}"
    code = textwrap.dedent(f"""
        from fastapi import HTTPException
        from app.utils.rate_limiter import SlidingWindowRateLimiter
        lim = SlidingWindowRateLimiter(max_requests=20, window_seconds=60, name="{name}")
        rejected = 0
        for _ in range(10):
            try:
                lim.check("10.0.0.9")
            except HTTPException:
                rejected += 1
        print("REJECTED", rejected)
    """)
    root = os.path.dirname(os.path.dirname(__file__))
    procs = [subprocess.Popen([sys.executable, "-c", code], cwd=root, env=dict(os.environ), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) for _ in range(3)]
    total = 0
    for p in procs:
        out, err = p.communicate(timeout=120)
        assert "REJECTED" in out, err[-400:]
        total += int(out.split("REJECTED")[1].split()[0])
    assert total == 10  # 30 attempts against one limit of 20 shared by three processes


def test_n09_counters_expire_and_store_no_raw_keys(db):
    from app.utils.rate_limiter import COLLECTION, SlidingWindowRateLimiter
    name = f"p05_ttl_{ObjectId()}"
    SlidingWindowRateLimiter(max_requests=3, window_seconds=60, name=name).check("203.0.113.77")
    doc = db[COLLECTION].find_one({"limiter": name})
    assert doc and "203.0.113.77" not in repr(doc) and doc["expiresAt"] <= utc_now() + timedelta(seconds=121)
    assert any(ix.get("expireAfterSeconds") == 0 for ix in db[COLLECTION].list_indexes())


def test_n09_health_chat_429_still_gives_emergency_guidance():
    from app.utils.rate_limiter import ai_health_chat_limiter
    assert "1990" in ai_health_chat_limiter.detail


# ------------------------------------------------------------------------------------------------ P05-N10 (P4-O8)
def test_n10_security_api_only_under_api_and_probes_at_root():
    assert client.get("/health/live").status_code == 200
    assert client.get("/api/health/live").status_code == 200
    assert client.get("/security/events").status_code == 404
    assert client.get("/security/monitoring/platform").status_code == 404
    paths = client.app.openapi()["paths"]
    assert "/api/security/events" in paths and "/security/events" not in paths
    assert "/health/live" in paths and "/api/health/live" in paths
