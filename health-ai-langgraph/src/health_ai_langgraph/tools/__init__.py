"""LangChain tools for the Health AI agent.

Tools are created via factory functions that accept their dependencies
(repositories, LLM clients) rather than relying on module-level globals.
"""

from health_ai_langgraph.tools.lab_report import create_lab_report_tool
from health_ai_langgraph.tools.medical_reasoning import create_medgemma_tool
from health_ai_langgraph.tools.symptom_analysis import create_symptom_analysis_tool
from health_ai_langgraph.tools.visit_summary import create_visit_summary_tool

__all__ = [
    "create_lab_report_tool",
    "create_medgemma_tool",
    "create_symptom_analysis_tool",
    "create_visit_summary_tool",
]
