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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default_factory=lambda: int((os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES") or "60").strip())
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default_factory=lambda: int((os.getenv("REFRESH_TOKEN_EXPIRE_DAYS") or "7").strip())
    )


settings = Settings()
