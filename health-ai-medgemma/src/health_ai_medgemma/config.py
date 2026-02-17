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

    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "INFO"

    agent_card_path: str = str(PROJECT_ROOT / "agent_card.json")

    # Ollama base URL (OpenAI-compatible endpoint at /v1)
    ollama_base_url: str = "http://localhost:11434"

    # MedGemma model configuration
    medgemma_model: str = "MedAIBase/MedGemma1.5:4b"
    medgemma_temperature: float = 0.1
    medgemma_num_predict: int = 512

    # Agent tuning
    max_agent_iterations: int = 5
    llm_call_timeout_seconds: int = 90

    # Server tuning
    cors_origins: list[str] = ["*"]
    request_timeout_seconds: int = 300


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()  # type: ignore[call-arg]
