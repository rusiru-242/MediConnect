import logging
from typing import Any, Dict
from fastapi import HTTPException, status
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.config.settings import settings

logger = logging.getLogger(__name__)


class GoogleAuthVerifier:
    """Handles independent verification of Google OAuth2 ID tokens."""

    @staticmethod
    def verify_token(id_token_str: str) -> Dict[str, Any]:
        """Verify the Google ID token and return verified claims."""
        if not id_token_str or not id_token_str.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Google ID token is required.",
            )

        request = google_requests.Request()
        audience = settings.GOOGLE_CLIENT_ID if settings.GOOGLE_CLIENT_ID else None

        try:
            id_info = google_id_token.verify_oauth2_token(
                id_token_str.strip(),
                request,
                audience=audience,
            )
        except (ValueError, GoogleAuthError) as exc:
            logger.warning("Google ID token verification failed: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google ID token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate issuer
        if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token issuer.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate email existence and verification
        email = id_info.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google token does not contain an email address.",
            )

        if not id_info.get("email_verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google account email is not verified.",
            )

        return id_info
