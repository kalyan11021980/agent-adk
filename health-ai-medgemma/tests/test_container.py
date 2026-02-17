"""Tests for the DI container."""

from __future__ import annotations

from health_ai_medgemma.config import Settings
from health_ai_medgemma.container import Container
from health_ai_medgemma.repositories.in_memory import (
    InMemoryLabReportRepository,
    InMemorySymptomRepository,
    InMemoryVisitRepository,
)


class TestContainer:

    def test_from_settings_creates_container(self):
        settings = Settings()  # type: ignore[call-arg]
        container = Container.from_settings(settings)
        assert isinstance(container.visit_repo, InMemoryVisitRepository)
        assert isinstance(container.symptom_repo, InMemorySymptomRepository)
        assert isinstance(container.lab_report_repo, InMemoryLabReportRepository)

    def test_single_llm_client(self):
        settings = Settings()  # type: ignore[call-arg]
        container = Container.from_settings(settings)
        assert container.medgemma_llm is not None
        # Verify no orchestrator_llm attribute (single-model architecture)
        assert not hasattr(container, "orchestrator_llm")
