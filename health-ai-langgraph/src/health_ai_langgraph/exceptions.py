"""Custom exception hierarchy for the Health AI agent."""

from __future__ import annotations


class HealthAIError(Exception):
    """Base exception for all Health AI errors."""


class PatientNotFoundError(HealthAIError):
    """Raised when a patient ID is not found in the data source."""

    def __init__(self, patient_id: str) -> None:
        self.patient_id = patient_id
        super().__init__(f"No records found for patient '{patient_id}'.")


class RepositoryError(HealthAIError):
    """Raised when a data access operation fails."""


class AgentExecutionError(HealthAIError):
    """Raised when the LangGraph agent fails during execution."""
