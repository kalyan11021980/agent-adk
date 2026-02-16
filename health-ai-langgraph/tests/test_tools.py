"""Tests for tool factory functions.

Uses real in-memory repositories to validate tool output conforms
to the Pydantic schemas (VisitSummaryCard, SymptomAnalysisCard, etc.).
"""

from __future__ import annotations

import pytest

from health_ai_langgraph.repositories.in_memory import (
    InMemoryLabReportRepository,
    InMemorySymptomRepository,
    InMemoryVisitRepository,
)
from health_ai_langgraph.schemas.ui import LabReportCard, SymptomAnalysisCard, VisitSummaryCard
from health_ai_langgraph.tools.lab_report import create_lab_report_tool
from health_ai_langgraph.tools.visit_summary import create_visit_summary_tool


# ---------------------------------------------------------------------------
# Visit summary tool
# ---------------------------------------------------------------------------

class TestVisitSummaryTool:

    @pytest.mark.asyncio
    async def test_existing_patient_returns_card(self):
        repo = InMemoryVisitRepository()
        tool = create_visit_summary_tool(repo)
        result = await tool.ainvoke({"patient_id": "P001"})
        assert result["status"] == "success"
        assert result["component_type"] == "visit_summary_card"
        # Validate it conforms to VisitSummaryCard schema
        VisitSummaryCard(**{k: v for k, v in result.items() if k != "status"})

    @pytest.mark.asyncio
    async def test_missing_patient_returns_error(self):
        repo = InMemoryVisitRepository()
        tool = create_visit_summary_tool(repo)
        result = await tool.ainvoke({"patient_id": "P999"})
        assert result["status"] == "error"
        assert "error_message" in result


# ---------------------------------------------------------------------------
# Lab report tool
# ---------------------------------------------------------------------------

class TestLabReportTool:

    @pytest.mark.asyncio
    async def test_returns_valid_card(self):
        repo = InMemoryLabReportRepository()
        tool = create_lab_report_tool(repo)
        result = await tool.ainvoke({"report_text": "blood work"})
        assert result["status"] == "success"
        assert result["component_type"] == "lab_report_card"
        # Validate schema conformance
        LabReportCard(**{k: v for k, v in result.items() if k != "status"})


# ---------------------------------------------------------------------------
# Pydantic schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_visit_summary_card_validates(self):
        card = VisitSummaryCard(
            visit_date="2026-01-01",
            provider_name="Dr. Test",
            provider_specialty="Testing",
            diagnosis=["Test Condition"],
            clinical_notes="Test notes.",
            medications=[{"name": "Testazol", "dosage": "10mg", "frequency": "daily"}],
            follow_up="Follow up in 7 days.",
            vitals={"blood_pressure": "120/80"},
        )
        dumped = card.model_dump()
        assert dumped["component_type"] == "visit_summary_card"

    def test_symptom_analysis_card_validates(self):
        card = SymptomAnalysisCard(
            reported_symptoms=["cough"],
            possible_conditions=[{"condition": "Cold", "likelihood": "high"}],
            severity="low",
            recommendations=["Rest"],
            when_to_seek_care="If symptoms persist",
        )
        dumped = card.model_dump()
        assert dumped["component_type"] == "symptom_analysis_card"

    def test_lab_report_card_validates(self):
        card = LabReportCard(
            report_date="2026-01-01",
            ordering_provider="Dr. Test",
            results=[{
                "test_name": "WBC",
                "value": "10.0",
                "unit": "x10^3/uL",
                "reference_range": "4.5-11.0",
                "status": "normal",
            }],
            summary="All normal.",
            abnormal_count=0,
            follow_up_needed=False,
        )
        dumped = card.model_dump()
        assert dumped["component_type"] == "lab_report_card"
