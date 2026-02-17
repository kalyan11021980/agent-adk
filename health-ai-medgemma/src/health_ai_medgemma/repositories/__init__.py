"""Data access layer — repository interfaces and implementations."""

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

__all__ = [
    "LabReportRepository",
    "SymptomRepository",
    "VisitRepository",
    "InMemoryLabReportRepository",
    "InMemorySymptomRepository",
    "InMemoryVisitRepository",
]
