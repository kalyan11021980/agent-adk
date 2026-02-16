"""Tool for medical reasoning via MedGemma.

Calls the MedGemma model (injected via DI) through Ollama to provide
medical analysis on data retrieved by other tools.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import StructuredTool

from health_ai_langgraph.config import Settings

logger = logging.getLogger(__name__)


def create_medgemma_tool(llm: BaseChatModel, settings: Settings) -> StructuredTool:
    """Build the MedGemma consultation tool with an injected LLM client."""

    async def _consult_medgemma(query: str, medical_data: str) -> str:
        prompt = (
            "Give a clear, patient-friendly interpretation in 4-6 bullet points.\n"
            "Use plain language. Keep it under 300 words.\n"
            "No greetings, no sign-offs, no emojis.\n\n"
            f"Q: {query}\n\nData:\n{medical_data}"
        )

        response = await asyncio.wait_for(
            llm.ainvoke(prompt),
            timeout=settings.request_timeout_seconds,
        )
        return response.content

    return StructuredTool.from_function(
        coroutine=_consult_medgemma,
        name="consult_medgemma",
        description=(
            "Consult MedGemma for medical reasoning and analysis. "
            "Use this tool AFTER retrieving patient data with other tools "
            "(get_visit_summary, analyze_symptoms, summarize_lab_report) when you "
            "need deeper medical interpretation, clinical insights, or want to "
            "explain findings in patient-friendly language."
        ),
    )
