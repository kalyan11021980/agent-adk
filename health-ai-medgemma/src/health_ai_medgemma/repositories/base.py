"""Abstract repository interfaces.

Defines the contracts for data access. Swap implementations
(in-memory, database, external API) without touching tool logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class VisitRepository(ABC):
    """Retrieve patient visit records."""

    @abstractmethod
    async def get_visit_summary(self, patient_id: str) -> dict | None:
        """Return visit data for *patient_id*, or ``None`` if not found."""

    @abstractmethod
    async def list_patient_ids(self) -> list[str]:
        """Return all known patient identifiers (for error hints)."""


class SymptomRepository(ABC):
    """Look up symptom analysis data."""

    @abstractmethod
    async def lookup_symptoms(self, keywords: list[str]) -> list[dict]:
        """Return matching symptom entries for the given *keywords*."""

    @abstractmethod
    async def get_default_analysis(self) -> dict:
        """Return fallback analysis when no keywords match."""


class LabReportRepository(ABC):
    """Retrieve lab report data."""

    @abstractmethod
    async def get_lab_report(self, patient_id: str) -> dict | None:
        """Return structured lab results for *patient_id*, or ``None`` if not found."""

    @abstractmethod
    async def list_patient_ids(self) -> list[str]:
        """Return all known patient identifiers (for error hints)."""
