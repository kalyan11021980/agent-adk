"""Tests for the A2A executor: circuit breaker, error sanitization, helpers."""

from __future__ import annotations

import asyncio
import time

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from health_ai_langgraph.agent import _build_prompt_with_message_filter
from health_ai_langgraph.executor import CircuitBreaker, _sanitize_error


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:

    def test_starts_closed(self):
        cb = CircuitBreaker(threshold=3, recovery_timeout=1.0)
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(threshold=3, recovery_timeout=1.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(threshold=3, recovery_timeout=10.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_success_resets_count(self):
        cb = CircuitBreaker(threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == "closed"
        # One more failure shouldn't open it
        cb.record_failure()
        assert cb.state == "closed"

    def test_half_open_after_recovery(self):
        cb = CircuitBreaker(threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.15)
        assert cb.state == "half-open"
        assert cb.allow_request() is True


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
        assert "localhost" not in msg  # no internal details leaked

    def test_generic_error(self):
        msg = _sanitize_error(ValueError("some internal detail"))
        assert "unexpected error" in msg.lower()
        assert "internal detail" not in msg  # no raw message leaked


# ---------------------------------------------------------------------------
# Ollama-safe prompt modifier (strips empty AIMessages)
# ---------------------------------------------------------------------------

class TestPromptMessageFilter:

    def setup_method(self):
        self._modifier = _build_prompt_with_message_filter("You are a test assistant.")

    def test_prepends_system_message(self):
        state = {"messages": [HumanMessage(content="hello")]}
        result = self._modifier(state)
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "You are a test assistant."
        assert isinstance(result[1], HumanMessage)

    def test_strips_empty_ai_message(self):
        """AIMessage with no content and no tool_calls should be removed."""
        state = {"messages": [
            HumanMessage(content="hello"),
            AIMessage(content=""),
            HumanMessage(content="follow up"),
        ]}
        result = self._modifier(state)
        # System + 2 HumanMessages — the empty AIMessage is gone
        assert len(result) == 3
        assert all(not isinstance(m, AIMessage) for m in result)

    def test_keeps_ai_message_with_content(self):
        state = {"messages": [
            HumanMessage(content="hello"),
            AIMessage(content="I can help with that."),
        ]}
        result = self._modifier(state)
        assert len(result) == 3
        assert isinstance(result[2], AIMessage)
        assert result[2].content == "I can help with that."

    def test_keeps_ai_message_with_tool_calls(self):
        """AIMessage with tool_calls but empty content should be kept."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "get_weather", "args": {"city": "NYC"}, "id": "tc1"}],
        )
        state = {"messages": [HumanMessage(content="weather?"), ai_msg]}
        result = self._modifier(state)
        assert len(result) == 3
        assert isinstance(result[2], AIMessage)
        assert result[2].tool_calls

    def test_preserves_tool_messages(self):
        """ToolMessages should never be filtered."""
        state = {"messages": [
            HumanMessage(content="hello"),
            AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "tc1"}]),
            ToolMessage(content="result", tool_call_id="tc1"),
            AIMessage(content="Here are the results."),
        ]}
        result = self._modifier(state)
        # System + Human + AI(tool_calls) + Tool + AI(content) = 5
        assert len(result) == 5
