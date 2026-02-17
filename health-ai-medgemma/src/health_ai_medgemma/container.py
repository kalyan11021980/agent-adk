"""Dependency injection container.

Holds all shared state (repositories, LLM client) in a single object
created at startup. Simplified from the langgraph variant — single LLM
(MedGemma via OpenAI-compatible API).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from health_ai_medgemma.config import Settings
from health_ai_medgemma.repositories.base import (
    LabReportRepository,
    SymptomRepository,
    VisitRepository,
)
from health_ai_medgemma.repositories.in_memory import (
    InMemoryLabReportRepository,
    InMemorySymptomRepository,
    InMemoryVisitRepository,
)

logger = logging.getLogger("health_ai_medgemma.container")


@dataclass
class Container:
    """Application-wide dependency container.

    Created once at startup by ``Container.from_settings()`` and passed
    explicitly to components that need shared resources.
    """

    settings: Settings

    # Repositories
    visit_repo: VisitRepository = field(init=False)
    symptom_repo: SymptomRepository = field(init=False)
    lab_report_repo: LabReportRepository = field(init=False)

    # Single LLM client — MedGemma via Ollama OpenAI-compatible API
    medgemma_llm: BaseChatModel = field(init=False)

    def __post_init__(self) -> None:
        # Repositories
        self.visit_repo = InMemoryVisitRepository()
        self.symptom_repo = InMemorySymptomRepository()
        self.lab_report_repo = InMemoryLabReportRepository()

        # MedGemma via Ollama's OpenAI-compatible endpoint
        # extra_body={"think": False} disables Gemma 3's chain-of-thought
        # reasoning mode (the <unused94>...<unused95> tokens) which wastes
        # time and num_predict budget. Passed via extra_body to bypass
        # the OpenAI SDK's strict parameter validation.
        self.medgemma_llm = ChatOpenAI(
            base_url=f"{self.settings.ollama_base_url}/v1",
            api_key="ollama",
            model=self.settings.medgemma_model,
            temperature=self.settings.medgemma_temperature,
            max_tokens=self.settings.medgemma_num_predict,
            timeout=float(self.settings.llm_call_timeout_seconds),
            extra_body={"think": False},
        )

        logger.info(
            "Container initialized: medgemma=%s (via %s/v1)",
            self.settings.medgemma_model,
            self.settings.ollama_base_url,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Container:
        """Create a container from application settings."""
        return cls(settings=settings)
