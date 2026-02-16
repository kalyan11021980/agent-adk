"""Tool for analyzing reported symptoms.

Delegates to a SymptomRepository injected via ``create_symptom_analysis_tool()``.
Uses the orchestrator LLM to extract symptom keywords from free-text,
replacing the previous hardcoded keyword list.
"""

from __future__ import annotations

import json
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import StructuredTool

from health_ai_langgraph.repositories.base import SymptomRepository
from health_ai_langgraph.schemas.ui import SymptomAnalysisCard

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "This is not a medical diagnosis. The information provided is for "
    "educational purposes only. Always consult a qualified healthcare "
    "professional for medical advice, diagnosis, or treatment."
)

_SEVERITY_RANK: dict[str, int] = {"low": 0, "moderate": 1, "high": 2, "urgent": 3}

_EXTRACTION_PROMPT = """\
Extract medical symptom keywords from the following patient text.
Return ONLY a JSON array of lowercase symptom keywords.
Map synonyms to canonical terms: e.g. "wheezing" → "cough", \
"head is pounding" → "headache", "tightness in chest" → "chest pain", \
"feel hot"/"burning up" → "fever".
If no recognizable symptoms are found, return an empty array.

Patient text: {text}

JSON array:"""


def create_symptom_analysis_tool(
    repo: SymptomRepository,
    llm: BaseChatModel,
) -> StructuredTool:
    """Build the symptom-analysis tool with injected dependencies."""

    async def _analyze_symptoms(symptoms: str) -> dict:
        # Use LLM to extract symptom keywords from free text
        all_keywords = await _extract_keywords(llm, symptoms)
        logger.info("Extracted keywords from %r: %s", symptoms[:80], all_keywords)

        matches = await repo.lookup_symptoms(all_keywords) if all_keywords else []

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

        # Deduplicate recommendations while preserving order.
        seen: set[str] = set()
        unique_recs: list[str] = []
        for rec in all_recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recs.append(rec)

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


async def _extract_keywords(llm: BaseChatModel, text: str) -> list[str]:
    """Use LLM to extract symptom keywords from free-text input."""
    try:
        prompt = _EXTRACTION_PROMPT.format(text=text)
        response = await llm.ainvoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        # Strip markdown fences if present
        content = content.strip().strip("`").strip()
        if content.startswith("json"):
            content = content[4:].strip()
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [str(kw).lower() for kw in parsed]
    except Exception:
        logger.warning("LLM keyword extraction failed, falling back to simple matching")
        # Fallback: simple substring matching against known terms
        text_lower = text.lower()
        return [kw for kw in ["cough", "headache", "chest pain", "fever"] if kw in text_lower]
    return []
