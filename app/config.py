"""
Application configuration loaded from environment variables.

Required env vars on Render:
  DATABASE_URL            – Postgres connection string
  LICENSE_PRIVATE_KEY_PEM – Base64-encoded Ed25519 private key (PEM)
  ADMIN_API_TOKEN         – Secret token protecting /admin/* routes
  APP_ENV                 – "production" | "development" (optional)
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./dev.db"

    # ── Signing ──────────────────────────────────────────
    LICENSE_PRIVATE_KEY_PEM: str = ""  # base64-encoded Ed25519 PEM

    # ── Admin auth ───────────────────────────────────────
    ADMIN_API_TOKEN: str = "change-me-in-production"

    # ── Application ──────────────────────────────────────
    APP_ENV: str = "development"
    APP_NAME: str = "Intellexia License Server"
    DEFAULT_MAX_DEVICES: int = 1
    DEFAULT_EXPIRES_AFTER_DAYS: int = 365

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
