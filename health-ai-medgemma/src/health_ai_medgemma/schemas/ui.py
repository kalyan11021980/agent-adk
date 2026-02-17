"""Pydantic models for generative UI components.

Each model represents a structured JSON card that a frontend can render
as a rich UI component. The ``component_type`` field acts as a discriminator
so the frontend knows which renderer to use.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VisitSummaryCard(BaseModel):
    """Structured output for a patient visit summary."""

    component_type: str = Field(default="visit_summary_card")
    visit_date: str
    provider_name: str
    provider_specialty: str
    diagnosis: list[str]
    clinical_notes: str
    medications: list[dict[str, str]] = Field(
        description="List of {name, dosage, frequency} dicts"
    )
    follow_up: str
    vitals: dict[str, str] = Field(default_factory=dict)


class SymptomAnalysisCard(BaseModel):
    """Structured output for symptom analysis results."""

    component_type: str = Field(default="symptom_analysis_card")
    reported_symptoms: list[str]
    possible_conditions: list[dict[str, str]] = Field(
        description="List of {condition, likelihood} dicts"
    )
    severity: str = Field(description="low | moderate | high | urgent")
    recommendations: list[str]
    when_to_seek_care: str
    disclaimer: str = Field(
        default=(
            "This is not a medical diagnosis. Always consult a qualified "
            "healthcare professional for medical advice."
        )
    )


class LabResult(BaseModel):
    """A single lab test result entry."""

    test_name: str
    value: str
    unit: str
    reference_range: str
    status: str = Field(description="normal | low | high | critical")


class LabReportCard(BaseModel):
    """Structured output for lab report summaries."""

    component_type: str = Field(default="lab_report_card")
    report_date: str
    ordering_provider: str
    results: list[LabResult]
    summary: str
    abnormal_count: int
    follow_up_needed: bool
