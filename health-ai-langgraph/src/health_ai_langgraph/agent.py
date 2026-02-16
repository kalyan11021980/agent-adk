"""LangGraph ReAct agent for the Health AI assistant."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from health_ai_langgraph.container import Container
from health_ai_langgraph.tools import (
    create_lab_report_tool,
    create_medgemma_tool,
    create_symptom_analysis_tool,
    create_visit_summary_tool,
)

logger = logging.getLogger("health_ai_langgraph.agent")

SYSTEM_INSTRUCTION = """\
You are Health AI, a helpful and empathetic healthcare information assistant.
You are powered by two AI models: you handle orchestration and tool calling, \
while MedGemma (a specialized medical model) provides deep medical reasoning.

## CRITICAL RULES
1. You MUST call a tool for every health-related request. NEVER ask \
clarifying questions when a tool can handle the request directly.
2. You have NO patient data or medical records of your own. All data lives \
in your tools.
3. When in doubt, CALL THE TOOL. Do not ask the user to clarify — just \
call the most relevant tool with whatever information is available.

### Tool selection
- `get_visit_summary(patient_id)` — call when the user asks for a visit \
summary, appointment details, or clinical records. Use "P001" as default \
if no patient ID is specified.
- `analyze_symptoms(symptoms)` — call when the user describes symptoms \
or health complaints. Pass the user's message as-is.
- `summarize_lab_report(report_text)` — call when the user asks about \
lab results, blood work, or any laboratory report. Pass the user's \
message as-is. Do NOT ask which report — just call the tool immediately.
- `consult_medgemma(query, medical_data)` — call AFTER retrieving data \
with the above tools when the user asks for explanations or deeper \
analysis. Pass the tool output as medical_data and your question as query.

### When to call consult_medgemma
ONLY call `consult_medgemma` when the user explicitly asks for:
- "explain", "summarize", "what does this mean", "break it down", "interpret"
- Follow-up questions like "yes", "tell me more", "go on" after showing data.

Do NOT call `consult_medgemma` for simple data retrieval requests like:
- "show me my lab report", "get visit summary", "show results"

### Presenting results
- **Data-only request** (show, get, retrieve): Output a one-sentence intro \
then the COMPLETE tool result JSON inside a ```json code block. Do NOT \
modify, reformat, omit, or add any fields.
- **Analysis request** (explain, summarize, interpret): Call \
`consult_medgemma`, then output MedGemma's response EXACTLY as returned. \
Do NOT rephrase, expand, summarize, or add anything to MedGemma's text. \
Copy it word-for-word. Do NOT include the raw JSON code block.
- **Error result**: Relay the error_message in a friendly tone.

## Guidelines
- Be empathetic, clear, and concise.
- Never provide a definitive medical diagnosis.
- Never fabricate or invent medical data — always use a tool.
- If the user's request is unclear, ask a clarifying question.
- For demo purposes, available patient IDs are: P001, P002.
"""


def _build_prompt_with_message_filter(
    system_instruction: str,
) -> callable:
    """Build a prompt callable that prepends the system message and strips
    empty ``AIMessage``s from checkpointed conversations.

    Some LLM backends reject assistant messages that have neither ``content``
    nor ``tool_calls``.  These can appear when LangGraph replays checkpointed
    ReAct steps.  Filtering them here is a cheap safety net.
    """
    _system = SystemMessage(content=system_instruction)

    def _modifier(state: dict[str, Any]) -> list[BaseMessage]:
        messages: list[BaseMessage] = state.get("messages", [])
        result: list[BaseMessage] = [_system]
        for msg in messages:
            if isinstance(msg, AIMessage):
                has_content = bool(msg.content)
                has_tool_calls = bool(getattr(msg, "tool_calls", None))
                if not has_content and not has_tool_calls:
                    logger.debug("Stripping empty AIMessage from checkpoint replay")
                    continue
            result.append(msg)
        return result

    return _modifier


def build_agent(
    container: Container,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Construct and compile the LangGraph ReAct agent.

    Args:
        container: DI container providing LLM clients and repositories.
        checkpointer: LangGraph checkpoint saver for conversation memory.
                      Pass ``AsyncPostgresSaver`` for production or
                      ``MemorySaver`` for testing. If ``None``, no
                      checkpointing (stateless).

    Returns:
        A compiled LangGraph that can be invoked with ``ainvoke`` or
        iterated with ``astream``.
    """
    tools = [
        create_visit_summary_tool(container.visit_repo),
        create_symptom_analysis_tool(container.symptom_repo, container.orchestrator_llm),
        create_lab_report_tool(container.lab_report_repo),
        create_medgemma_tool(container.medgemma_llm, container.settings),
    ]

    graph = create_react_agent(
        model=container.orchestrator_llm,
        tools=tools,
        checkpointer=checkpointer,
        prompt=_build_prompt_with_message_filter(SYSTEM_INSTRUCTION),
    )

    logger.info(
        "LangGraph ReAct agent built with model=%s, tools=%s",
        container.settings.model_name,
        [t.name for t in tools],
    )
    return graph
