"""Fail-closed runtime configuration checks (Phase 05, P4-B5 / P4-B2).

The settings module loads ``backend/.env`` without overriding variables that are already set. Before Phase 05 a
backend started with no environment (``ENVIRONMENT`` unset, so "development") silently used whatever database
``.env`` named, which on the owner's machine is a remote cluster, and accepted any non-empty JWT secret.

Rules enforced here (nothing in this module connects anywhere or prints a secret):

* ``ENVIRONMENT`` must be one of ``development``, ``test``, ``staging`` or ``production``.
* ``test``: the database must be local and end with ``_test`` (same rule as ``tests/conftest.py``).
* ``development``: the database must be local unless ``ALLOW_REMOTE_DATABASE=true`` is set deliberately.
* ``staging`` / ``production``: remote databases are allowed; these modes are only reached by explicit configuration
  (``.env.production.example`` sets ``ENVIRONMENT=production``).
* Every environment except ``test`` needs a JWT secret of at least 32 bytes that is not a known default and is not
  a low-variety string; the algorithm must be an HMAC algorithm; access tokens may live at most 60 minutes.
"""

from __future__ import annotations

from typing import List, Optional

from app.config.db_safety import is_local_mongodb_uri, isolation_error

KNOWN_ENVIRONMENTS = ("development", "test", "staging", "production")
REMOTE_ALLOWED_ENVIRONMENTS = frozenset({"staging", "production"})
ALLOWED_JWT_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})
MIN_JWT_SECRET_BYTES = 32
MAX_ACCESS_TOKEN_MINUTES = 60

# Values copied from templates, tutorials and this repository's own CI/test configuration. They are public, so a
# backend that serves real users must never sign tokens with them.
KNOWN_WEAK_JWT_SECRETS = frozenset({
    "secret", "changeme", "change-me", "changethis", "jwt_secret", "jwt-secret", "your-secret-key", "your_secret_key",
    "supersecret", "super-secret", "mysecret", "mediconnect", "mediconnect_secret", "test", "testing", "password",
    "ci_test_secret_key_minimum_32_bytes_long_123456", "test_secret_key_for_testing_only_32bytes!!",
    "<generate_a_secure_random_secret>", "replace_me", "replace-me",
})


def truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def environment_error(environment: str) -> Optional[str]:
    if (environment or "").strip().lower() not in KNOWN_ENVIRONMENTS:
        return f"ENVIRONMENT must be one of {', '.join(KNOWN_ENVIRONMENTS)}."
    return None


def database_target_error(uri: Optional[str], database_name: str, environment: str,
                          allow_remote: bool) -> Optional[str]:
    """Why this database target must not be used in this environment, or None when it may be used."""
    env = (environment or "").strip().lower()
    problem = environment_error(env)
    if problem:
        return problem
    if not uri or not uri.strip():
        return "MONGODB_URI is not configured."
    if env == "test":
        return isolation_error(uri, database_name, "_test")
    if env in REMOTE_ALLOWED_ENVIRONMENTS:
        return None
    if is_local_mongodb_uri(uri) or allow_remote:
        return None
    return ("Refusing a non-local MongoDB in ENVIRONMENT=development. Use a local database "
            "(mongodb://127.0.0.1:27017), set ENVIRONMENT=production/staging for a deliberate deployment, or set "
            "ALLOW_REMOTE_DATABASE=true only with the database owner's approval.")


def jwt_secret_error(secret: Optional[str], environment: str) -> Optional[str]:
    """Why this JWT secret is unacceptable, or None. The secret itself is never included in the message."""
    value = (secret or "").strip()
    if not value:
        return "JWT_SECRET is missing."
    if (environment or "").strip().lower() == "test":
        return None
    if value.lower() in KNOWN_WEAK_JWT_SECRETS:
        return "JWT_SECRET is a known default value; generate a random secret."
    if len(value.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
        return f"JWT_SECRET must be at least {MIN_JWT_SECRET_BYTES} bytes of random data."
    if len(set(value)) < 10:
        return "JWT_SECRET has too little variety to be random; generate a random secret."
    return None


def jwt_settings_errors(algorithm: str, access_minutes: int, refresh_days: int) -> List[str]:
    errors = []
    if (algorithm or "").strip().upper() not in ALLOWED_JWT_ALGORITHMS:
        errors.append("JWT_ALGORITHM must be HS256, HS384 or HS512.")
    if not 1 <= int(access_minutes) <= MAX_ACCESS_TOKEN_MINUTES:
        errors.append(f"ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and {MAX_ACCESS_TOKEN_MINUTES}.")
    if not 1 <= int(refresh_days) <= 30:
        errors.append("REFRESH_TOKEN_EXPIRE_DAYS must be between 1 and 30.")
    return errors


def startup_errors(settings) -> List[str]:
    """All configuration problems that must stop the API from starting (messages contain no secrets)."""
    errors: List[str] = []
    env = settings.ENVIRONMENT
    for problem in (
        environment_error(env),
        database_target_error(settings.MONGODB_URI, settings.DATABASE_NAME, env, settings.ALLOW_REMOTE_DATABASE),
        jwt_secret_error(settings.JWT_SECRET, env),
    ):
        if problem and problem not in errors:
            errors.append(problem)
    errors.extend(jwt_settings_errors(settings.JWT_ALGORITHM, settings.ACCESS_TOKEN_EXPIRE_MINUTES,
                                      settings.REFRESH_TOKEN_EXPIRE_DAYS))
    if env != "production" and (settings.STRIPE_SECRET_KEY or "").startswith(("sk_live_", "rk_live_")):
        errors.append("A live Stripe key is only accepted with ENVIRONMENT=production.")
    return errors
