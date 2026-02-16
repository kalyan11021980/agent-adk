"""Tests for the DI container."""

from __future__ import annotations

import pytest

from health_ai_langgraph.config import Settings
from health_ai_langgraph.container import Container
from health_ai_langgraph.repositories.in_memory import (
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

    def test_llm_clients_initialized(self):
        settings = Settings()  # type: ignore[call-arg]
        container = Container.from_settings(settings)
        assert container.orchestrator_llm is not None
        assert container.medgemma_llm is not None

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self):
        settings = Settings()  # type: ignore[call-arg]
        container = Container.from_settings(settings)
        await container.close()  # should not raise
