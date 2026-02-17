"""Shared fixtures for the Health AI MedGemma test suite."""

from __future__ import annotations

import pytest

from health_ai_medgemma.repositories.in_memory import (
    InMemoryLabReportRepository,
    InMemorySymptomRepository,
    InMemoryVisitRepository,
)


@pytest.fixture
def visit_repo() -> InMemoryVisitRepository:
    return InMemoryVisitRepository()


@pytest.fixture
def symptom_repo() -> InMemorySymptomRepository:
    return InMemorySymptomRepository()


@pytest.fixture
def lab_report_repo() -> InMemoryLabReportRepository:
    return InMemoryLabReportRepository()
