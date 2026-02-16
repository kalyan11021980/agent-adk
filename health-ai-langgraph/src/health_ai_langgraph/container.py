"""Dependency injection container.

Holds all shared state (repositories, LLM clients, stores) in a single
object created at startup and threaded through the application. Replaces
module-level global singletons, enabling proper testing, horizontal scaling,
and clean shutdown.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from health_ai_langgraph.config import Settings
from health_ai_langgraph.repositories.base import (
    LabReportRepository,
    SymptomRepository,
    VisitRepository,
)
from health_ai_langgraph.repositories.in_memory import (
    InMemoryLabReportRepository,
    InMemorySymptomRepository,
    InMemoryVisitRepository,
)

logger = logging.getLogger("health_ai_langgraph.container")


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

    # LLM clients
    orchestrator_llm: BaseChatModel = field(init=False)
    medgemma_llm: BaseChatModel = field(init=False)

    def __post_init__(self) -> None:
        # Repositories — swap these for DB-backed implementations in production
        self.visit_repo = InMemoryVisitRepository()
        self.symptom_repo = InMemorySymptomRepository()
        self.lab_report_repo = InMemoryLabReportRepository()

        # Orchestrator LLM (tool-calling model)
        self.orchestrator_llm = ChatOllama(
            model=self.settings.model_name,
            base_url=self.settings.ollama_base_url,
            temperature=self.settings.model_temperature,
        )

        # Medical reasoning LLM (MedGemma)
        self.medgemma_llm = ChatOllama(
            model=self.settings.medgemma_model,
            base_url=self.settings.ollama_base_url,
            temperature=self.settings.medgemma_temperature,
            num_predict=400,
        )

        logger.info(
            "Container initialized: orchestrator=%s, medgemma=%s",
            self.settings.model_name,
            self.settings.medgemma_model,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Container:
        """Create a container from application settings."""
        return cls(settings=settings)

    async def close(self) -> None:
        """Clean up resources on shutdown."""
        logger.info("Container closing — releasing resources")
