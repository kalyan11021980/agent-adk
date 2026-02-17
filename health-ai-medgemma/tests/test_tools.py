"""Tests for tool factory functions.

Uses real in-memory repositories to validate tool output conforms
to the Pydantic schemas (VisitSummaryCard, SymptomAnalysisCard, etc.).
"""

from __future__ import annotations

import pytest

from health_ai_medgemma.repositories.in_memory import (
    InMemoryLabReportRepository,
    InMemorySymptomRepository,
    InMemoryVisitRepository,
)
from health_ai_medgemma.schemas.ui import LabReportCard, SymptomAnalysisCard, VisitSummaryCard
from health_ai_medgemma.tools.lab_report import create_lab_report_tool
from health_ai_medgemma.tools.symptom_analysis import create_symptom_analysis_tool
from health_ai_medgemma.tools.visit_summary import create_visit_summary_tool


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
        VisitSummaryCard(**{k: v for k, v in result.items() if k != "status"})

    @pytest.mark.asyncio
    async def test_missing_patient_returns_error(self):
        repo = InMemoryVisitRepository()
        tool = create_visit_summary_tool(repo)
        result = await tool.ainvoke({"patient_id": "P999"})
        assert result["status"] == "error"
        assert "error_message" in result


# ---------------------------------------------------------------------------
# Symptom analysis tool
# ---------------------------------------------------------------------------

class TestSymptomAnalysisTool:

    @pytest.mark.asyncio
    async def test_known_symptom_returns_card(self):
        repo = InMemorySymptomRepository()
        tool = create_symptom_analysis_tool(repo)
        result = await tool.ainvoke({"symptoms": "I have a bad cough"})
        assert result["status"] == "success"
        assert result["component_type"] == "symptom_analysis_card"
        SymptomAnalysisCard(**{k: v for k, v in result.items() if k != "status"})

    @pytest.mark.asyncio
    async def test_unknown_symptom_returns_default(self):
        repo = InMemorySymptomRepository()
        tool = create_symptom_analysis_tool(repo)
        result = await tool.ainvoke({"symptoms": "my elbow feels weird"})
        assert result["status"] == "success"
        assert result["component_type"] == "symptom_analysis_card"


# ---------------------------------------------------------------------------
# Lab report tool
# ---------------------------------------------------------------------------

class TestLabReportTool:

    @pytest.mark.asyncio
    async def test_existing_patient_returns_card(self):
        repo = InMemoryLabReportRepository()
        tool = create_lab_report_tool(repo)
        result = await tool.ainvoke({"patient_id": "P001"})
        assert result["status"] == "success"
        assert result["component_type"] == "lab_report_card"
        LabReportCard(**{k: v for k, v in result.items() if k != "status"})

    @pytest.mark.asyncio
    async def test_missing_patient_returns_error(self):
        repo = InMemoryLabReportRepository()
        tool = create_lab_report_tool(repo)
        result = await tool.ainvoke({"patient_id": "P999"})
        assert result["status"] == "error"
        assert "error_message" in result
        assert "P999" in result["error_message"]


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
