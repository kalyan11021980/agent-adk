"""Tests for the multi-strategy tool call parser and parameter normalization."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from health_ai_medgemma.agent import (
    _condense_for_prompt,
    _normalize_parameters,
    _parse_tool_result,
    _strip_thinking,
    _summarize_card,
    _try_direct_response,
)
from health_ai_medgemma.tool_parser import ParsedToolCall, parse_tool_call
from health_ai_medgemma.tools.lab_report import create_lab_report_tool
from health_ai_medgemma.tools.visit_summary import create_visit_summary_tool
from health_ai_medgemma.repositories.in_memory import (
    InMemoryLabReportRepository,
    InMemoryVisitRepository,
)

VALID_TOOLS = {"get_visit_summary", "analyze_symptoms", "summarize_lab_report"}


class TestParseToolCall:

    # --- Strategy 1: Full JSON response ---

    def test_full_json_tool_call(self):
        text = '{"name": "get_visit_summary", "parameters": {"patient_id": "P001"}}'
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is not None
        assert result.name == "get_visit_summary"
        assert result.parameters == {"patient_id": "P001"}

    def test_full_json_no_parameters(self):
        text = '{"name": "summarize_lab_report"}'
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is not None
        assert result.name == "summarize_lab_report"
        assert result.parameters == {}

    # --- Strategy 2: Code fence ---

    def test_code_fence_json(self):
        text = 'I will call the function:\n```json\n{"name": "analyze_symptoms", "parameters": {"symptoms": "headache"}}\n```'
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is not None
        assert result.name == "analyze_symptoms"
        assert result.parameters == {"symptoms": "headache"}

    def test_code_fence_no_lang(self):
        text = 'Calling:\n```\n{"name": "get_visit_summary", "parameters": {"patient_id": "P002"}}\n```'
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is not None
        assert result.name == "get_visit_summary"

    # --- Strategy 3: Embedded JSON ---

    def test_embedded_json_in_text(self):
        text = 'Let me look that up. {"name": "get_visit_summary", "parameters": {"patient_id": "P001"}} I will process this.'
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is not None
        assert result.name == "get_visit_summary"

    # --- No tool call (final answer) ---

    def test_no_tool_call_returns_none(self):
        text = "Based on your symptoms, I recommend getting plenty of rest and staying hydrated."
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is None

    def test_empty_string_returns_none(self):
        result = parse_tool_call("", VALID_TOOLS)
        assert result is None

    def test_whitespace_only_returns_none(self):
        result = parse_tool_call("   \n  ", VALID_TOOLS)
        assert result is None

    # --- Hallucinated tool rejection ---

    def test_rejects_hallucinated_tool(self):
        text = '{"name": "delete_patient_records", "parameters": {"patient_id": "P001"}}'
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is None

    def test_rejects_invalid_json(self):
        text = '{"name": "get_visit_summary", "parameters": {broken json'
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is None

    # --- Edge cases ---

    def test_json_with_nested_braces(self):
        text = '{"name": "analyze_symptoms", "parameters": {"symptoms": "chest pain with {sharp} sensation"}}'
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is not None
        assert result.name == "analyze_symptoms"

    def test_multiple_json_objects_picks_valid(self):
        text = 'Note: {"irrelevant": true}. Calling: {"name": "get_visit_summary", "parameters": {"patient_id": "P001"}}'
        result = parse_tool_call(text, VALID_TOOLS)
        assert result is not None
        assert result.name == "get_visit_summary"

    def test_result_is_frozen_dataclass(self):
        text = '{"name": "get_visit_summary", "parameters": {"patient_id": "P001"}}'
        result = parse_tool_call(text, VALID_TOOLS)
        assert isinstance(result, ParsedToolCall)
        with pytest.raises(AttributeError):
            result.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Parameter normalization
# ---------------------------------------------------------------------------

class TestNormalizeParameters:

    def test_correct_params_unchanged(self):
        tool = create_visit_summary_tool(InMemoryVisitRepository())
        params = {"patient_id": "P001"}
        result = _normalize_parameters(params, tool)
        assert result == {"patient_id": "P001"}

    def test_single_param_wrong_key_remapped(self):
        """MedGemma sends {"arg": "P001"} instead of {"patient_id": "P001"}."""
        tool = create_visit_summary_tool(InMemoryVisitRepository())
        params = {"arg": "P001"}
        result = _normalize_parameters(params, tool)
        assert result == {"patient_id": "P001"}

    def test_single_param_generic_value_key_remapped(self):
        """MedGemma sends {"value": "P001"} instead of {"patient_id": ...}."""
        tool = create_lab_report_tool(InMemoryLabReportRepository())
        params = {"value": "P001"}
        result = _normalize_parameters(params, tool)
        assert result == {"patient_id": "P001"}

    def test_empty_params_unchanged(self):
        tool = create_visit_summary_tool(InMemoryVisitRepository())
        params: dict = {}
        result = _normalize_parameters(params, tool)
        assert result == {}


# ---------------------------------------------------------------------------
# Thinking token stripping
# ---------------------------------------------------------------------------

class TestStripThinking:

    def test_strips_thinking_block(self):
        text = '<unused94>thought Let me analyze this...<unused95>Here is the actual answer.'
        result = _strip_thinking(text)
        assert result == "Here is the actual answer."

    def test_strips_multiline_thinking(self):
        text = (
            '<unused94>thought\nStep 1: identify symptoms\n'
            'Step 2: call function\n<unused95>'
            '{"name": "analyze_symptoms", "parameters": {"symptoms": "cough"}}'
        )
        result = _strip_thinking(text)
        assert result == '{"name": "analyze_symptoms", "parameters": {"symptoms": "cough"}}'

    def test_no_thinking_unchanged(self):
        text = '{"name": "get_visit_summary", "parameters": {"patient_id": "P001"}}'
        result = _strip_thinking(text)
        assert result == text

    def test_empty_string(self):
        result = _strip_thinking("")
        assert result == ""

    def test_thinking_only_returns_original(self):
        """If stripping leaves nothing, return original (fallback)."""
        text = "<unused94>only thinking here<unused95>"
        result = _strip_thinking(text)
        # After stripping, empty string → returns original
        assert result == text


# ---------------------------------------------------------------------------
# Short-circuit: _try_direct_response
# ---------------------------------------------------------------------------

class TestTryDirectResponse:

    def _make_tool_msg(self, data: dict) -> HumanMessage:
        return HumanMessage(
            content=f"Function get_visit_summary returned:\n{json.dumps(data)}"
        )

    def test_success_card_returns_intro(self):
        msg = self._make_tool_msg({
            "status": "success",
            "component_type": "visit_summary_card",
            "visit_date": "2025-12-15",
        })
        result = _try_direct_response(msg)
        assert result == "Here are the results."

    def test_symptom_card_returns_intro(self):
        msg = self._make_tool_msg({
            "status": "success",
            "component_type": "symptom_analysis_card",
            "reported_symptoms": ["cough"],
        })
        assert _try_direct_response(msg) == "Here are the results."

    def test_lab_card_returns_intro(self):
        msg = self._make_tool_msg({
            "status": "success",
            "component_type": "lab_report_card",
            "report_date": "2026-02-10",
        })
        assert _try_direct_response(msg) == "Here are the results."

    def test_error_result_returns_none(self):
        msg = self._make_tool_msg({
            "status": "error",
            "error_message": "Patient not found",
        })
        assert _try_direct_response(msg) is None

    def test_non_function_message_returns_none(self):
        msg = HumanMessage(content="explain this")
        assert _try_direct_response(msg) is None

    def test_ai_message_returns_none(self):
        msg = AIMessage(content="some response")
        assert _try_direct_response(msg) is None

    def test_no_json_returns_none(self):
        assert _try_direct_response(HumanMessage(content="Function X returned:")) is None


# ---------------------------------------------------------------------------
# Context trimming: _condense_for_prompt and _summarize_card
# ---------------------------------------------------------------------------

class TestCondenseForPrompt:

    def test_non_function_message_unchanged(self):
        msg = HumanMessage(content="explain this")
        assert _condense_for_prompt(msg) is msg

    def test_ai_message_unchanged(self):
        msg = AIMessage(content="Here is the summary.")
        assert _condense_for_prompt(msg) is msg

    def test_error_result_unchanged(self):
        data = {"status": "error", "error_message": "Not found"}
        msg = HumanMessage(content=f"Function X returned:\n{json.dumps(data)}")
        assert _condense_for_prompt(msg) is msg

    def test_success_card_condensed(self):
        data = {
            "status": "success",
            "component_type": "visit_summary_card",
            "visit_date": "2025-12-15",
            "provider_name": "Dr. Sarah Chen",
            "diagnosis": ["URI", "Dehydration"],
            "medications": [
                {"name": "Amoxicillin", "dosage": "500mg"},
            ],
            "vitals": {"bp": "120/78", "hr": "82"},
        }
        msg = HumanMessage(
            content=f"Function get_visit_summary returned:\n{json.dumps(data)}"
        )
        condensed = _condense_for_prompt(msg)

        assert isinstance(condensed, HumanMessage)
        assert condensed is not msg
        # Header preserved
        assert condensed.content.startswith("Function get_visit_summary returned:")
        # JSON braces removed, readable text instead
        assert "{" not in condensed.content
        # Key data preserved
        assert "Dr. Sarah Chen" in condensed.content
        assert "2025-12-15" in condensed.content
        assert "Amoxicillin" in condensed.content
        # Significantly shorter than original
        assert len(condensed.content) < len(msg.content)


class TestSummarizeCard:

    def test_visit_summary_card(self):
        card = {
            "status": "success",
            "component_type": "visit_summary_card",
            "visit_date": "2025-12-15",
            "provider_name": "Dr. Chen",
            "diagnosis": ["URI", "Dehydration"],
            "vitals": {"bp": "120/78", "hr": "82"},
        }
        result = _summarize_card(card)
        assert "[visit_summary_card]" in result
        assert "visit_date: 2025-12-15" in result
        assert "provider_name: Dr. Chen" in result
        assert "URI" in result
        assert "bp: 120/78" in result

    def test_numeric_and_bool_fields(self):
        card = {
            "status": "success",
            "component_type": "lab_report_card",
            "abnormal_count": 2,
            "follow_up_needed": True,
        }
        result = _summarize_card(card)
        assert "abnormal_count: 2" in result
        assert "follow_up_needed: True" in result

    def test_no_extra_fields(self):
        card = {"status": "success", "component_type": "test_card"}
        result = _summarize_card(card)
        assert result == "[test_card]"
