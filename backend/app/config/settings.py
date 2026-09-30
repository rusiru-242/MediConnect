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


settings = Settings()
