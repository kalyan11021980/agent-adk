"""Tests for in-memory repository implementations."""

from __future__ import annotations

import pytest

from health_ai_medgemma.repositories.in_memory import (
    InMemoryLabReportRepository,
    InMemorySymptomRepository,
    InMemoryVisitRepository,
)


# ---------------------------------------------------------------------------
# VisitRepository
# ---------------------------------------------------------------------------

class TestInMemoryVisitRepository:

    @pytest.mark.asyncio
    async def test_get_existing_patient(self, visit_repo: InMemoryVisitRepository):
        result = await visit_repo.get_visit_summary("P001")
        assert result is not None
        assert "visit_date" in result
        assert "provider_name" in result
        assert "diagnosis" in result

    @pytest.mark.asyncio
    async def test_get_missing_patient_returns_none(self, visit_repo: InMemoryVisitRepository):
        result = await visit_repo.get_visit_summary("P999")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_patient_ids(self, visit_repo: InMemoryVisitRepository):
        ids = await visit_repo.list_patient_ids()
        assert "P001" in ids
        assert "P002" in ids

    @pytest.mark.asyncio
    async def test_custom_data(self):
        custom_data = {"T001": {"visit_date": "2026-01-01", "provider_name": "Dr. Test"}}
        repo = InMemoryVisitRepository(data=custom_data)
        result = await repo.get_visit_summary("T001")
        assert result is not None
        assert result["provider_name"] == "Dr. Test"


# ---------------------------------------------------------------------------
# SymptomRepository
# ---------------------------------------------------------------------------

class TestInMemorySymptomRepository:

    @pytest.mark.asyncio
    async def test_lookup_known_keyword(self, symptom_repo: InMemorySymptomRepository):
        results = await symptom_repo.lookup_symptoms(["cough"])
        assert len(results) == 1
        assert results[0]["keyword"] == "cough"
        assert "conditions" in results[0]

    @pytest.mark.asyncio
    async def test_lookup_multiple_keywords(self, symptom_repo: InMemorySymptomRepository):
        results = await symptom_repo.lookup_symptoms(["cough", "fever"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_lookup_unknown_keyword(self, symptom_repo: InMemorySymptomRepository):
        results = await symptom_repo.lookup_symptoms(["xyz_unknown"])
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_default_analysis(self, symptom_repo: InMemorySymptomRepository):
        default = await symptom_repo.get_default_analysis()
        assert "conditions" in default
        assert "severity" in default
        assert "recommendations" in default


# ---------------------------------------------------------------------------
# LabReportRepository
# ---------------------------------------------------------------------------

class TestInMemoryLabReportRepository:

    @pytest.mark.asyncio
    async def test_get_existing_patient(self, lab_report_repo: InMemoryLabReportRepository):
        result = await lab_report_repo.get_lab_report("P001")
        assert result is not None
        assert "report_date" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        assert len(result["results"]) > 0

    @pytest.mark.asyncio
    async def test_get_missing_patient_returns_none(self, lab_report_repo: InMemoryLabReportRepository):
        result = await lab_report_repo.get_lab_report("P999")
        assert result is None

    @pytest.mark.asyncio
    async def test_has_abnormal_count(self, lab_report_repo: InMemoryLabReportRepository):
        result = await lab_report_repo.get_lab_report("P001")
        assert result is not None
        assert "abnormal_count" in result
        assert isinstance(result["abnormal_count"], int)

    @pytest.mark.asyncio
    async def test_summary(self, lab_report_repo: InMemoryLabReportRepository):
        result = await lab_report_repo.get_lab_report("P001")
        assert result is not None
        assert "summary" in result
        assert len(result["summary"]) > 0

    @pytest.mark.asyncio
    async def test_list_patient_ids(self, lab_report_repo: InMemoryLabReportRepository):
        ids = await lab_report_repo.list_patient_ids()
        assert "P001" in ids
        assert "P002" in ids
