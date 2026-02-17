"""LangChain tools for the Health AI MedGemma agent.

Tools are created via factory functions that accept their dependencies
(repositories, LLM clients) rather than relying on module-level globals.

Note: No medical_reasoning tool — MedGemma IS the agent and reasons directly.
"""

from health_ai_medgemma.tools.lab_report import create_lab_report_tool
from health_ai_medgemma.tools.symptom_analysis import create_symptom_analysis_tool
from health_ai_medgemma.tools.visit_summary import create_visit_summary_tool

__all__ = [
    "create_lab_report_tool",
    "create_symptom_analysis_tool",
    "create_visit_summary_tool",
]
