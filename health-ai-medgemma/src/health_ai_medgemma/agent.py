"""Custom LangGraph agent for MedGemma with prompt-based tool calling.

Unlike the langgraph variant which uses ``create_react_agent()`` with a
tool-calling model, this builds a custom ``StateGraph`` because MedGemma
lacks native tool calling. The agent loop:

1. agent_node: calls MedGemma with the system prompt + conversation history
2. Parse the response for a tool call using ``tool_parser``
3. If tool call found → execute tool → feed result back as a message → loop
4. If no tool call → final answer → END
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from health_ai_medgemma.container import Container
from health_ai_medgemma.tool_parser import parse_tool_call
from health_ai_medgemma.tools import (
    create_lab_report_tool,
    create_symptom_analysis_tool,
    create_visit_summary_tool,
)

logger = logging.getLogger("health_ai_medgemma.agent")

SYSTEM_INSTRUCTION = """\
You are Health AI, a medical assistant.

To call a function, respond with ONLY this JSON format (no other text):
{{"name": "function_name", "parameters": {{"patient_id": "P001"}}}}

Available functions (ONLY these three exist):
1. get_visit_summary — parameters: {{"patient_id": "..."}}. Retrieves visit records.
2. analyze_symptoms — parameters: {{"symptoms": "..."}}. Analyzes reported symptoms.
3. summarize_lab_report — parameters: {{"patient_id": "..."}}. Retrieves lab results.

Rules:
- For visit and lab report requests, you need a patient_id. If the user does not provide one, \
ask which patient they mean. Demo patient IDs: P001, P002.
- For symptom analysis, pass the user's described symptoms as the symptoms parameter.
- After receiving "Function ... returned:" results, DO NOT call another function. \
Instead, present the data clearly in plain text with your medical interpretation.
- If a function returns an error, relay the error message to the user helpfully.
- The ONLY valid function names are: get_visit_summary, analyze_symptoms, summarize_lab_report.
- CRITICAL: When explaining results, ONLY reference data that appears in the function output. \
Use the exact dates, names, diagnoses, medications, and values from the returned data. \
NEVER invent or assume any clinical details not present in the data.
- Never give definitive diagnoses.
"""


# Grounding prefix injected before follow-up questions so the small
# model anchors its answer to the actual data instead of hallucinating.
_GROUNDING_PREFIX = (
    "IMPORTANT: Answer ONLY based on the data above. "
    "Use the exact values, dates, and names from the function results. "
    "Do NOT add any information that is not present in the data.\n\n"
)


class AgentState(TypedDict):
    """State for the custom MedGemma agent graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    iteration_count: int


# Regex to strip Gemma 3 thinking tokens: <unused94>...thinking...<unused95>
_THINKING_PATTERN = re.compile(r"<unused94>.*?<unused95>", re.DOTALL)


def _strip_thinking(text: str) -> str:
    """Remove Gemma 3 thinking blocks from model output.

    MedGemma may emit chain-of-thought between <unused94> and <unused95>
    tokens. We pass think=False to Ollama, but strip as a safety net.
    """
    cleaned = _THINKING_PATTERN.sub("", text).strip()
    return cleaned if cleaned else text


def _build_tool_map(tools: list[StructuredTool]) -> dict[str, StructuredTool]:
    """Create a name → tool mapping."""
    return {tool.name: tool for tool in tools}


def _get_expected_params(tool: StructuredTool) -> list[str]:
    """Return the list of expected parameter names from a tool's schema."""
    schema = tool.args_schema
    if schema is None:
        return []
    return list(schema.model_fields.keys())


def _normalize_parameters(
    parameters: dict, tool: StructuredTool
) -> dict:
    """Normalize parameters when MedGemma uses wrong key names.

    Small models often copy placeholder names from the prompt (e.g. "arg",
    "value", "input") instead of using the actual parameter names. When the
    tool expects exactly one required parameter and the model sent exactly
    one parameter with the wrong key, remap it.
    """
    expected = _get_expected_params(tool)
    if not expected:
        return parameters

    provided_keys = list(parameters.keys())

    # Happy path: keys already match
    if set(provided_keys) == set(expected):
        return parameters

    # Single-param tool, single provided value with wrong key → remap
    if len(expected) == 1 and len(provided_keys) == 1:
        wrong_key = provided_keys[0]
        correct_key = expected[0]
        if wrong_key != correct_key:
            logger.info(
                "Remapping parameter %r -> %r for tool %s",
                wrong_key, correct_key, tool.name,
            )
            return {correct_key: parameters[wrong_key]}

    # Multi-param tool: try positional mapping if count matches
    if len(provided_keys) == len(expected) and set(provided_keys) != set(expected):
        logger.info(
            "Positional remap %s -> %s for tool %s",
            provided_keys, expected, tool.name,
        )
        return dict(zip(expected, parameters.values()))

    return parameters


def _parse_tool_result(msg: BaseMessage) -> dict | None:
    """Extract a successful card dict from a tool-result HumanMessage.

    Returns the parsed dict if the message is a ``"Function X returned:"``
    HumanMessage containing ``{"status": "success", "component_type": ...}``,
    otherwise ``None``. Used by both the short-circuit and context-condensing
    paths to avoid duplicating the parsing logic.
    """
    if not isinstance(msg, HumanMessage):
        return None
    content = msg.content if isinstance(msg.content, str) else ""
    if not content.startswith("Function "):
        return None
    lines = content.split("\n", 1)
    if len(lines) < 2:
        return None
    try:
        data = json.loads(lines[1].strip())
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(data, dict) and data.get("status") == "success" and "component_type" in data:
        return data
    return None


def _try_direct_response(msg: BaseMessage) -> str | None:
    """Return a short intro if the message is a successful card result.

    The frontend renders the card directly, so calling MedGemma again
    just to get a text summary wastes ~15-20s. The executor reads the
    full card JSON from the tool-result HumanMessage in graph state.
    """
    card = _parse_tool_result(msg)
    if card is None:
        return None
    return "Here are the results."


def _summarize_card(card: dict) -> str:
    """Convert card data dict to compact readable text.

    Tool output is **flat** — ``{"status": "success", "component_type": ...,
    "visit_date": ..., ...}`` — so we iterate all keys except the meta fields.
    """
    lines: list[str] = [f"[{card.get('component_type', 'card')}]"]
    skip = {"status", "component_type"}

    for key, value in card.items():
        if key in skip:
            continue
        if isinstance(value, str):
            lines.append(f"{key}: {value}")
        elif isinstance(value, (int, float, bool)):
            lines.append(f"{key}: {value}")
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                items = []
                for item in value[:5]:
                    brief = ", ".join(
                        f"{k}: {v}" for k, v in item.items()
                        if isinstance(v, (str, int, float, bool))
                    )
                    items.append(brief)
                lines.append(f"{key}: " + " | ".join(items))
            else:
                lines.append(f"{key}: {', '.join(str(v) for v in value)}")
        elif isinstance(value, dict):
            brief = ", ".join(
                f"{k}: {v}" for k, v in value.items()
                if isinstance(v, (str, int, float, bool))
            )
            lines.append(f"{key}: {brief}")

    return "\n".join(lines)


def _condense_for_prompt(msg: BaseMessage) -> BaseMessage:
    """Condense a tool-result message for LLM prompt efficiency.

    Replaces the raw JSON with a compact text summary. The original
    messages in the graph state are untouched.
    """
    card = _parse_tool_result(msg)
    if card is None:
        return msg
    content = msg.content if isinstance(msg.content, str) else ""
    header = content.split("\n", 1)[0]
    return HumanMessage(content=f"{header}\n{_summarize_card(card)}")


def build_agent(
    container: Container,
    checkpointer: BaseCheckpointSaver | None = None,
) -> StateGraph:
    """Construct and compile the custom MedGemma agent graph.

    Args:
        container: DI container providing LLM client and repositories.
        checkpointer: LangGraph checkpoint saver for conversation memory.
                      Pass ``MemorySaver`` for in-process state.

    Returns:
        A compiled StateGraph that can be invoked with ``ainvoke``.
    """
    tools = [
        create_visit_summary_tool(container.visit_repo),
        create_symptom_analysis_tool(container.symptom_repo),
        create_lab_report_tool(container.lab_report_repo),
    ]
    tool_map = _build_tool_map(tools)
    valid_tool_names = set(tool_map.keys())
    llm = container.medgemma_llm
    max_iterations = container.settings.max_agent_iterations
    llm_timeout = container.settings.llm_call_timeout_seconds
    system_msg = SystemMessage(content=SYSTEM_INSTRUCTION)

    async def agent_node(state: AgentState) -> dict[str, Any]:
        """Call MedGemma and parse the response for tool calls.

        Short-circuits (skips LLM call) when the last message is a
        successful card result from a tool — the frontend renders
        the card directly, so a second LLM call is unnecessary.
        """
        messages = state["messages"]
        iteration = state.get("iteration_count", 0)

        # Short-circuit: if the tool already returned a successful card,
        # generate a canned response instead of calling MedGemma again.
        # This saves ~15-20s per request on a 4B local model.
        if messages:
            last_msg = messages[-1]
            direct = _try_direct_response(last_msg)
            if direct is not None:
                logger.info("Short-circuit: returning card directly (skipping LLM call)")
                return {
                    "messages": [AIMessage(content=direct)],
                    "iteration_count": iteration + 1,
                }

        # Build prompt: system + conversation history
        # - Skip empty AIMessages
        # - Condense tool-result HumanMessages to save tokens
        # - Inject grounding prefix on follow-up turns so the 4B model
        #   anchors to actual data instead of hallucinating
        has_tool_results = any(
            isinstance(m, HumanMessage)
            and isinstance(m.content, str)
            and m.content.startswith("Function ")
            for m in messages
        )

        prompt_messages: list[BaseMessage] = [system_msg]
        for msg in messages:
            if isinstance(msg, AIMessage) and not msg.content:
                continue
            condensed = _condense_for_prompt(msg)

            # On follow-up turns (user message AFTER a tool result),
            # prepend grounding instructions to the user's message
            if (
                has_tool_results
                and condensed is msg  # not a tool-result (wasn't condensed)
                and isinstance(msg, HumanMessage)
                and not msg.content.startswith("Function ")
            ):
                prompt_messages.append(
                    HumanMessage(content=_GROUNDING_PREFIX + msg.content)
                )
            else:
                prompt_messages.append(condensed)

        try:
            response = await asyncio.wait_for(
                llm.ainvoke(prompt_messages),
                timeout=llm_timeout,
            )
        except asyncio.TimeoutError:
            # The 4B model can stall when the request is ambiguous.
            # On the first iteration (no tool results yet), return a
            # clarification prompt instead of failing the whole task.
            if not has_tool_results:
                logger.warning("LLM timed out on first iteration, asking for clarification")
                return {
                    "messages": [AIMessage(
                        content=(
                            "I'd like to help! Could you provide a bit more detail? "
                            "For example:\n"
                            "- A patient ID (e.g. P001, P002) for visit or lab report lookups\n"
                            "- A description of your symptoms for analysis"
                        )
                    )],
                    "iteration_count": iteration + 1,
                }
            raise

        response_text = (
            response.content if isinstance(response.content, str)
            else str(response.content)
        )

        # Strip any thinking tokens that leaked through despite think=False
        response_text = _strip_thinking(response_text)

        # Parse for tool call
        parsed = parse_tool_call(response_text, valid_tool_names)

        if parsed is not None:
            # Guard: if the model picked a patient_id that the user never
            # mentioned, it guessed. Return a clarification message (no
            # parsed_tool_call) so should_continue routes to END — no loop.
            pid = parsed.parameters.get("patient_id")
            user_text = _latest_user_text(messages)
            if pid and pid not in user_text:
                logger.info(
                    "Rejected guessed patient_id=%r (not in %r), asking for clarification",
                    pid, user_text,
                )
                ai_msg = AIMessage(
                    content=(
                        "I'd be happy to help! Could you please provide the patient ID? "
                        "Available demo IDs: P001, P002."
                    )
                )
            else:
                # Store parsed tool call in additional_kwargs for routing
                ai_msg = AIMessage(
                    content=response_text,
                    additional_kwargs={"parsed_tool_call": {
                        "name": parsed.name,
                        "parameters": parsed.parameters,
                    }},
                )
        else:
            ai_msg = AIMessage(content=response_text)

        return {
            "messages": [ai_msg],
            "iteration_count": iteration + 1,
        }

    def _latest_user_text(messages: list[BaseMessage]) -> str:
        """Return the most recent real user message (not a function result)."""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
                if not msg.content.startswith("Function "):
                    return msg.content
        return ""

    async def tool_node(state: AgentState) -> dict[str, Any]:
        """Execute the parsed tool call and return result as a message."""
        messages = state["messages"]
        last_msg = messages[-1]

        parsed_data = last_msg.additional_kwargs.get("parsed_tool_call", {})
        tool_name = parsed_data.get("name", "")
        parameters = parsed_data.get("parameters", {})

        tool = tool_map.get(tool_name)
        if tool is None:
            result_text = json.dumps({
                "status": "error",
                "error_message": f"Unknown function: {tool_name}",
            })
        else:
            try:
                parameters = _normalize_parameters(parameters, tool)
                result = await tool.ainvoke(parameters)
                result_text = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            except Exception as exc:
                logger.exception("Tool %s failed: %s", tool_name, exc)
                result_text = json.dumps({
                    "status": "error",
                    "error_message": f"Function {tool_name} encountered an error.",
                })

        # Feed result back as a HumanMessage (MedGemma doesn't understand ToolMessage)
        feedback = HumanMessage(
            content=f"Function {tool_name} returned:\n{result_text}"
        )
        return {"messages": [feedback]}

    def should_continue(state: AgentState) -> str:
        """Route to 'tools' if a tool call was parsed, else END."""
        messages = state["messages"]
        iteration = state.get("iteration_count", 0)

        # Safety: stop if we've hit max iterations
        if iteration >= max_iterations:
            logger.warning("Max iterations (%d) reached, ending", max_iterations)
            return END

        if not messages:
            return END

        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage):
            parsed = last_msg.additional_kwargs.get("parsed_tool_call")
            if parsed is not None:
                return "tools"

        return END

    # Build the graph
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {END: END, "tools": "tools"})
    graph.add_edge("tools", "agent")

    compiled = graph.compile(checkpointer=checkpointer)

    logger.info(
        "MedGemma agent built with model=%s, tools=%s, max_iterations=%d",
        container.settings.medgemma_model,
        list(valid_tool_names),
        max_iterations,
    )
    return compiled
