"""Application settings loaded from environment variables and .env file."""

from __future__ import annotations

import functools
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Typed application configuration.

    Values are read from environment variables first, then fall back
    to the .env file at the project root.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_api_key: str
    google_genai_use_vertexai: str = "FALSE"

    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "INFO"

    agent_card_path: str = str(PROJECT_ROOT / "agent_card.json")


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()  # type: ignore[call-arg]
