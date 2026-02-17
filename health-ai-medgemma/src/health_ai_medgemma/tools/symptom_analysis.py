"""Tool for analyzing reported symptoms.

Delegates to a SymptomRepository injected via ``create_symptom_analysis_tool()``.
Uses simple keyword matching (no LLM extraction) since MedGemma is the agent
and handles intelligent dispatching itself.
"""

from __future__ import annotations

import logging

from langchain_core.tools import StructuredTool

from health_ai_medgemma.repositories.base import SymptomRepository
from health_ai_medgemma.schemas.ui import SymptomAnalysisCard

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "This is not a medical diagnosis. The information provided is for "
    "educational purposes only. Always consult a qualified healthcare "
    "professional for medical advice, diagnosis, or treatment."
)

_SEVERITY_RANK: dict[str, int] = {"low": 0, "moderate": 1, "high": 2, "urgent": 3}

# Known symptom keywords for simple matching
_KNOWN_SYMPTOMS = ["cough", "headache", "chest pain", "fever"]


def create_symptom_analysis_tool(repo: SymptomRepository) -> StructuredTool:
    """Build the symptom-analysis tool with injected dependencies."""

    async def _analyze_symptoms(symptoms: str) -> dict:
        # Simple keyword matching — MedGemma handles intelligent dispatch
        text_lower = symptoms.lower()
        keywords = [kw for kw in _KNOWN_SYMPTOMS if kw in text_lower]
        logger.info("Matched keywords from %r: %s", symptoms[:80], keywords)

        matches = await repo.lookup_symptoms(keywords) if keywords else []

        if not matches:
            default = await repo.get_default_analysis()
            card = SymptomAnalysisCard(
                reported_symptoms=[symptoms.strip()],
                possible_conditions=default["conditions"],
                severity=default["severity"],
                recommendations=default["recommendations"],
                when_to_seek_care=default["when_to_seek_care"],
                disclaimer=_DISCLAIMER,
            )
            return {"status": "success", **card.model_dump()}

        matched_symptoms: list[str] = []
        all_conditions: list[dict[str, str]] = []
        max_severity = "low"
        all_recommendations: list[str] = []
        when_to_seek: list[str] = []

        for entry in matches:
            matched_symptoms.append(entry["keyword"])
            all_conditions.extend(entry["conditions"])
            if _SEVERITY_RANK.get(entry["severity"], 0) > _SEVERITY_RANK.get(max_severity, 0):
                max_severity = entry["severity"]
            all_recommendations.extend(entry["recommendations"])
            when_to_seek.append(entry["when_to_seek_care"])

        # Deduplicate recommendations while preserving order
        unique_recs = list(dict.fromkeys(all_recommendations))

        card = SymptomAnalysisCard(
            reported_symptoms=matched_symptoms,
            possible_conditions=all_conditions,
            severity=max_severity,
            recommendations=unique_recs,
            when_to_seek_care=" ".join(when_to_seek),
            disclaimer=_DISCLAIMER,
        )
        return {"status": "success", **card.model_dump()}

    return StructuredTool.from_function(
        coroutine=_analyze_symptoms,
        name="analyze_symptoms",
        description=(
            "Analyze reported symptoms and provide health guidance. "
            "Use this tool when the user describes symptoms they are experiencing, "
            "such as cough, headache, fever, chest pain, or any health complaints."
        ),
    )
