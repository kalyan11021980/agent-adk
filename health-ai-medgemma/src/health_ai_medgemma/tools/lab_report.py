"""Tool for summarizing lab report results.

Delegates to a LabReportRepository injected via ``create_lab_report_tool()``.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from health_ai_medgemma.repositories.base import LabReportRepository
from health_ai_medgemma.schemas.ui import LabReportCard


def create_lab_report_tool(repo: LabReportRepository) -> StructuredTool:
    """Build the lab-report tool with a specific repository."""

    async def _summarize_lab_report(patient_id: str) -> dict:
        data = await repo.get_lab_report(patient_id)
        if data is None:
            available = await repo.list_patient_ids()
            ids_hint = ", ".join(available) if available else "none"
            return {
                "status": "error",
                "error_message": (
                    f"No lab reports found for patient '{patient_id}'. "
                    f"Available demo IDs: {ids_hint}."
                ),
            }
        card = LabReportCard(**data)
        return {"status": "success", **card.model_dump()}

    return StructuredTool.from_function(
        coroutine=_summarize_lab_report,
        name="summarize_lab_report",
        description=(
            "Retrieve and summarize laboratory test results for a patient. "
            "Use this tool when the user asks about lab results, blood work, or "
            "any laboratory report for a specific patient ID."
        ),
    )
