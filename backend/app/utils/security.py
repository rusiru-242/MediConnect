from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Dict, Optional
import bcrypt
from fastapi import HTTPException, status
import jwt

from app.config.settings import settings


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt. Never logs or exposes plain-text."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def generate_refresh_token() -> str:
    """Generate a cryptographically secure, high-entropy opaque refresh token."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Compute deterministic SHA-256 hash of a token for secure database storage and lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token with restricted claims."""
    if not settings.JWT_SECRET or not settings.JWT_SECRET.strip():
        raise RuntimeError("JWT_SECRET environment variable is missing.")

    now = datetime.now(timezone.utc)
    lifetime = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + lifetime

    payload: Dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token, enforcing signature, expiration, and type."""
    if not settings.JWT_SECRET or not settings.JWT_SECRET.strip():
        raise RuntimeError("JWT_SECRET environment variable is missing.")

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
