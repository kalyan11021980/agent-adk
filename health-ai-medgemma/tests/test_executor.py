"""Tests for the A2A executor: error sanitization, parts builder, turn extraction."""

from __future__ import annotations

import asyncio
import json

from langchain_core.messages import AIMessage, HumanMessage

from health_ai_medgemma.executor import (
    _build_a2a_parts,
    _current_turn_messages,
    _sanitize_error,
)


# ---------------------------------------------------------------------------
# Error sanitization
# ---------------------------------------------------------------------------

class TestSanitizeError:

    def test_timeout_error(self):
        msg = _sanitize_error(asyncio.TimeoutError())
        assert "timed out" in msg.lower()
        assert "traceback" not in msg.lower()

    def test_connection_error(self):
        msg = _sanitize_error(ConnectionError("Connection refused to localhost:11434"))
        assert "unavailable" in msg.lower()
        assert "localhost" not in msg

    def test_os_error(self):
        msg = _sanitize_error(OSError("Network unreachable"))
        assert "unavailable" in msg.lower()

    def test_generic_error(self):
        msg = _sanitize_error(ValueError("some internal detail"))
        assert "unexpected error" in msg.lower()
        assert "internal detail" not in msg


# ---------------------------------------------------------------------------
# A2A parts builder (adapted for HumanMessage-based tool results)
# ---------------------------------------------------------------------------

class TestBuildA2AParts:

    def test_ai_text_only(self):
        messages = [
            HumanMessage(content="hello"),
            AIMessage(content="I can help with that."),
        ]
        parts = _build_a2a_parts(messages)
        assert len(parts) == 1
        assert "I can help with that." in parts[0].root.text

    def test_function_result_with_ai_response(self):
        card = {"status": "success", "component_type": "visit_summary_card", "visit_date": "2026-01-01"}
        messages = [
            HumanMessage(content="show visit summary"),
            AIMessage(content='{"name": "get_visit_summary", "parameters": {"patient_id": "P001"}}'),
            HumanMessage(content=f"Function get_visit_summary returned:\n{json.dumps(card)}"),
            AIMessage(content="Here is the visit summary for patient P001."),
        ]
        parts = _build_a2a_parts(messages)
        assert len(parts) == 1
        text = parts[0].root.text
        assert "visit_summary_card" in text
        assert "```json" in text

    def test_empty_messages(self):
        parts = _build_a2a_parts([])
        assert len(parts) == 0

    def test_function_result_without_ai_followup(self):
        card = {"status": "success", "component_type": "lab_report_card"}
        messages = [
            HumanMessage(content="summarize lab report"),
            HumanMessage(content=f"Function summarize_lab_report returned:\n{json.dumps(card)}"),
        ]
        parts = _build_a2a_parts(messages)
        assert len(parts) == 1
        assert "```json" in parts[0].root.text

    def test_followup_returns_text_only(self):
        """Follow-up questions should NOT include card JSON from prior turns."""
        card = {"status": "success", "component_type": "visit_summary_card"}
        messages = [
            # --- Turn 1: tool call + card ---
            HumanMessage(content="show visit summary for P001"),
            AIMessage(content='{"name": "get_visit_summary"}'),
            HumanMessage(content=f"Function get_visit_summary returned:\n{json.dumps(card)}"),
            AIMessage(content="Here are the results."),
            # --- Turn 2: follow-up explanation ---
            HumanMessage(content="explain this"),
            AIMessage(content="The patient visited Dr. Chen on 2025-12-15."),
        ]
        parts = _build_a2a_parts(messages)
        assert len(parts) == 1
        text = parts[0].root.text
        # Should be plain text, no card JSON
        assert "```json" not in text
        assert "Dr. Chen" in text


class TestCurrentTurnMessages:

    def test_single_turn(self):
        messages = [
            HumanMessage(content="hello"),
            AIMessage(content="hi there"),
        ]
        result = _current_turn_messages(messages)
        assert len(result) == 2

    def test_multi_turn_extracts_latest(self):
        messages = [
            HumanMessage(content="show P001"),
            AIMessage(content="tool call"),
            HumanMessage(content="Function get_visit_summary returned:\n{}"),
            AIMessage(content="Here is the summary."),
            HumanMessage(content="explain this"),
            AIMessage(content="The visit was on 2025-12-15."),
        ]
        result = _current_turn_messages(messages)
        assert len(result) == 2
        assert result[0].content == "explain this"
        assert result[1].content == "The visit was on 2025-12-15."

    def test_tool_result_not_treated_as_turn_boundary(self):
        """Function results are not user inputs — don't split on them."""
        messages = [
            HumanMessage(content="show P001"),
            AIMessage(content="tool call"),
            HumanMessage(content="Function get_visit_summary returned:\n{}"),
            AIMessage(content="Here is the summary."),
        ]
        result = _current_turn_messages(messages)
        # Turn started at "show P001"
        assert len(result) == 4
        assert result[0].content == "show P001"
