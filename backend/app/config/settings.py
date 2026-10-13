from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)


class Settings(BaseModel):
    """Application configuration loaded from environment variables."""

    APP_NAME: str = "MediConnect"
    MONGODB_URI: Optional[str] = Field(
        default_factory=lambda: (os.getenv("MONGODB_URI") or "").strip() or None
    )
    DATABASE_NAME: str = Field(
        default_factory=lambda: (os.getenv("DATABASE_NAME") or "mediconnect").strip() or "mediconnect"
    )
    JWT_SECRET: Optional[str] = Field(
        default_factory=lambda: (os.getenv("JWT_SECRET") or "").strip() or None
    )
    JWT_ALGORITHM: str = Field(
        default_factory=lambda: (os.getenv("JWT_ALGORITHM") or "HS256").strip() or "HS256"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default_factory=lambda: int((os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES") or "60").strip())
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default_factory=lambda: int((os.getenv("REFRESH_TOKEN_EXPIRE_DAYS") or "7").strip())
    )
    SMTP_HOST: Optional[str] = Field(
        default_factory=lambda: (os.getenv("SMTP_HOST") or "").strip() or None
    )
    SMTP_PORT: int = Field(
        default_factory=lambda: int((os.getenv("SMTP_PORT") or "587").strip())
    )
    SMTP_USERNAME: Optional[str] = Field(
        default_factory=lambda: (os.getenv("SMTP_USERNAME") or "").strip() or None
    )
    SMTP_PASSWORD: Optional[str] = Field(
        default_factory=lambda: (os.getenv("SMTP_PASSWORD") or "").strip() or None
    )
    SMTP_FROM_EMAIL: Optional[str] = Field(
        default_factory=lambda: (os.getenv("SMTP_FROM_EMAIL") or "").strip() or None
    )
    SMTP_FROM_NAME: str = Field(
        default_factory=lambda: (os.getenv("SMTP_FROM_NAME") or "MediConnect").strip() or "MediConnect"
    )
    GOOGLE_CLIENT_ID: Optional[str] = Field(
        default_factory=lambda: (os.getenv("GOOGLE_CLIENT_ID") or "").strip() or None
    )
    STRIPE_SECRET_KEY: Optional[str] = Field(
        default_factory=lambda: (os.getenv("STRIPE_SECRET_KEY") or "").strip() or None
    )
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(
        default_factory=lambda: (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip() or None
    )
    STRIPE_CURRENCY: str = Field(
        default_factory=lambda: (os.getenv("STRIPE_CURRENCY") or "lkr").strip().lower() or "lkr"
    )
    STRIPE_PUBLISHABLE_KEY: Optional[str] = Field(
        default_factory=lambda: (os.getenv("STRIPE_PUBLISHABLE_KEY") or "").strip() or None
    )
    FIREBASE_CREDENTIALS_PATH: Optional[str] = Field(
        default_factory=lambda: (os.getenv("FIREBASE_CREDENTIALS_PATH") or "").strip() or None
    )
    FIREBASE_SERVICE_ACCOUNT_JSON: Optional[str] = Field(
        default_factory=lambda: (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip() or None
    )
    REMINDER_CHECK_INTERVAL_SECONDS: int = Field(
        default_factory=lambda: int((os.getenv("REMINDER_CHECK_INTERVAL_SECONDS") or "60").strip())
    )
    GEMINI_API_KEY: Optional[str] = Field(
        default_factory=lambda: (os.getenv("GEMINI_API_KEY") or "").strip() or None
    )
    GEMINI_MODEL: str = Field(
        default_factory=lambda: (os.getenv("GEMINI_MODEL") or "gemini-3.8-flash").strip() or "gemini-3.8-flash"
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default_factory=lambda: (os.getenv("OPENAI_API_KEY") or "").strip() or None
    )
    OPENAI_MODEL: str = Field(
        default_factory=lambda: (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    )
    AI_TIMEOUT_SECONDS: int = Field(
        default_factory=lambda: int((os.getenv("AI_TIMEOUT_SECONDS") or "5").strip())
    )
    AI_MAX_RECOMMENDATIONS: int = Field(
        default_factory=lambda: int((os.getenv("AI_MAX_RECOMMENDATIONS") or "10").strip())
    )


settings = Settings()
