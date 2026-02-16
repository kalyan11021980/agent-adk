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

    # LLM configuration (Ollama native API)
    ollama_base_url: str = "http://localhost:11434"

    # Orchestrator model (must support tool calling)
    model_name: str = "mistral-large-3:675b-cloud"
    model_temperature: float = 0.0

    # Medical reasoning model
    medgemma_model: str = "MedAIBase/MedGemma1.5:4b"
    medgemma_temperature: float = 0.1

    # Database (PostgreSQL) — used for LangGraph checkpoints
    database_url: str = "postgresql://localhost:5432/health_ai"

    # Redis — used for A2A task store
    redis_url: str = "redis://localhost:6379/0"
    task_ttl_seconds: int = 3600

    # Server tuning
    cors_origins: list[str] = ["*"]
    request_timeout_seconds: int = 120

    # Circuit breaker
    circuit_breaker_threshold: int = 5
    circuit_breaker_recovery_seconds: float = 30.0


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()  # type: ignore[call-arg]
