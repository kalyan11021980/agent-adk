"""Root agent definition for the Health AI assistant."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.genai.types import (
    GenerateContentConfig,
    FunctionCallingConfig,
    FunctionCallingConfigMode,
    ToolConfig,
)

from health_ai.tools import analyze_symptoms, get_visit_summary, summarize_lab_report

_SYSTEM_INSTRUCTION = """\
You are Health AI, a helpful and empathetic healthcare information assistant.

## CRITICAL: You MUST call a tool for every health-related request.
You have NO patient data or medical records of your own. All data lives in \
your tools. If you respond without calling the appropriate tool first, your \
response WILL be incorrect.

### Tool selection
- `get_visit_summary(patient_id)` — call this when the user asks for a visit \
summary, appointment details, or clinical records for a patient ID.
- `analyze_symptoms(symptoms)` — call this when the user describes symptoms \
or health complaints.
- `summarize_lab_report(report_text)` — call this when the user asks about \
lab results, blood work, or laboratory reports.

## Presenting tool results
After you call a tool and receive the result:

1. If the result has `"status": "error"`, relay the error_message to the user \
in a friendly tone and suggest next steps (e.g. correct patient IDs).
2. If the result has `"status": "success"`, write a brief one-sentence intro \
(e.g. "Here is the visit summary for P001:") and then output the COMPLETE \
tool result JSON exactly as received inside a ```json code block. Do NOT \
modify, reformat, omit, or add any fields.

## Guidelines
- Be empathetic, clear, and concise.
- Never provide a definitive medical diagnosis.
- Never fabricate or invent medical data — always use a tool.
- If the user's request is unclear, ask a clarifying question.
- For demo purposes, available patient IDs are: P001, P002.
"""

root_agent = LlmAgent(
    model="gemini-2.0-flash",
    name="health_ai_agent",
    description=(
        "A healthcare information assistant that provides visit summaries, "
        "symptom analysis, and lab report interpretations with structured "
        "JSON output for generative UI rendering."
    ),
    instruction=_SYSTEM_INSTRUCTION,
    tools=[
        get_visit_summary,
        analyze_symptoms,
        summarize_lab_report,
    ],
    generate_content_config=GenerateContentConfig(
        tool_config=ToolConfig(
            function_calling_config=FunctionCallingConfig(
                mode=FunctionCallingConfigMode.AUTO,
            )
        )
    ),
)
