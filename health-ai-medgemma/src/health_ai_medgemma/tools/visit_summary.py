"""Tool for retrieving patient visit summaries.

Delegates to a VisitRepository injected via ``create_visit_summary_tool()``.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from health_ai_medgemma.repositories.base import VisitRepository
from health_ai_medgemma.schemas.ui import VisitSummaryCard


def create_visit_summary_tool(repo: VisitRepository) -> StructuredTool:
    """Build the visit-summary tool with a specific repository."""

    async def _get_visit_summary(patient_id: str) -> dict:
        data = await repo.get_visit_summary(patient_id)
        if data is None:
            available = await repo.list_patient_ids()
            ids_hint = ", ".join(available) if available else "none"
            return {
                "status": "error",
                "error_message": (
                    f"No visit records found for patient '{patient_id}'. "
                    f"Available demo IDs: {ids_hint}."
                ),
            }
        card = VisitSummaryCard(**data)
        return {"status": "success", **card.model_dump()}

    return StructuredTool.from_function(
        coroutine=_get_visit_summary,
        name="get_visit_summary",
        description=(
            "Retrieve the most recent visit summary for a patient. "
            "Use this tool when the user asks for a visit summary, appointment "
            "details, or clinical records for a specific patient ID."
        ),
    )
