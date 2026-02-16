"""Tool for summarizing lab report results.

Delegates to a LabReportRepository injected via ``create_lab_report_tool()``.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from health_ai_langgraph.repositories.base import LabReportRepository
from health_ai_langgraph.schemas.ui import LabReportCard


def create_lab_report_tool(repo: LabReportRepository) -> StructuredTool:
    """Build the lab-report tool with a specific repository."""

    async def _summarize_lab_report(report_text: str) -> dict:
        data = await repo.get_lab_report(report_text)
        card = LabReportCard(**data)
        return {"status": "success", **card.model_dump()}

    return StructuredTool.from_function(
        coroutine=_summarize_lab_report,
        name="summarize_lab_report",
        description=(
            "Parse and summarize laboratory test results. "
            "Use this tool when the user asks about lab results, blood work, or "
            "any laboratory report. Pass the user's request text as report_text."
        ),
    )
