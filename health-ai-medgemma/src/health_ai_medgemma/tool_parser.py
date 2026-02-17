"""Multi-strategy parser for extracting tool calls from MedGemma text output.

MedGemma lacks native tool calling. Instead, it is prompted with Gemma 3's
function calling format:

    {"name": "function_name", "parameters": {"arg": "value"}}

This module extracts such JSON tool calls from free-text LLM responses using
multiple strategies:

1. Entire response is a JSON object with a "name" key (happy path)
2. JSON object with "name" key embedded in surrounding text
3. JSON inside markdown code fences
4. Returns None if no tool call found (= final answer)

Validates against a set of valid tool names to prevent hallucinated tool calls.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedToolCall:
    """A successfully parsed tool call from model output."""

    name: str
    parameters: dict


def parse_tool_call(
    text: str,
    valid_tool_names: set[str],
) -> ParsedToolCall | None:
    """Extract a tool call from model text output.

    Tries multiple strategies in order of likelihood. Returns ``None``
    if the text is a final answer (no tool call found).

    Args:
        text: The raw text output from MedGemma.
        valid_tool_names: Set of allowed tool names. Calls to unknown
            tools are rejected to prevent hallucinated invocations.

    Returns:
        A ``ParsedToolCall`` if found and valid, otherwise ``None``.
    """
    text = text.strip()
    if not text:
        return None

    # Strategy 1: Entire response is JSON with "name" key
    result = _try_parse_full_json(text, valid_tool_names)
    if result is not None:
        return result

    # Strategy 2: JSON inside markdown code fences
    result = _try_parse_code_fence(text, valid_tool_names)
    if result is not None:
        return result

    # Strategy 3: JSON object embedded in surrounding text
    result = _try_parse_embedded_json(text, valid_tool_names)
    if result is not None:
        return result

    return None


def _try_parse_full_json(
    text: str, valid_tool_names: set[str]
) -> ParsedToolCall | None:
    """Strategy 1: entire text is a JSON object with 'name' key."""
    try:
        obj = json.loads(text)
        return _validate_tool_call(obj, valid_tool_names)
    except (json.JSONDecodeError, TypeError):
        return None


def _try_parse_code_fence(
    text: str, valid_tool_names: set[str]
) -> ParsedToolCall | None:
    """Strategy 2: JSON inside markdown code fences (```json ... ```)."""
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        try:
            obj = json.loads(match.strip())
            result = _validate_tool_call(obj, valid_tool_names)
            if result is not None:
                return result
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _try_parse_embedded_json(
    text: str, valid_tool_names: set[str]
) -> ParsedToolCall | None:
    """Strategy 3: JSON object embedded in surrounding text."""
    # Find all potential JSON objects using brace matching
    for match in re.finditer(r"\{", text):
        start = match.start()
        candidate = _extract_json_object(text, start)
        if candidate is not None:
            try:
                obj = json.loads(candidate)
                result = _validate_tool_call(obj, valid_tool_names)
                if result is not None:
                    return result
            except (json.JSONDecodeError, TypeError):
                continue
    return None


def _extract_json_object(text: str, start: int) -> str | None:
    """Extract a balanced JSON object starting at ``start``."""
    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape_next:
            escape_next = False
            continue

        if ch == "\\":
            escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


def _validate_tool_call(
    obj: object, valid_tool_names: set[str]
) -> ParsedToolCall | None:
    """Validate that a parsed JSON object is a well-formed tool call."""
    if not isinstance(obj, dict):
        return None

    name = obj.get("name")
    if not isinstance(name, str):
        return None

    if name not in valid_tool_names:
        logger.warning("Rejected hallucinated tool call: %r", name)
        return None

    parameters = obj.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}

    return ParsedToolCall(name=name, parameters=parameters)
