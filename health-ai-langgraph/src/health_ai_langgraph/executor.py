"""LangGraph ↔ A2A protocol bridge.

Implements the ``AgentExecutor`` interface from the ``a2a-sdk`` so that
the ``DefaultRequestHandler`` can drive a LangGraph ReAct agent while
producing standards-compliant A2A task events.

Includes:
- Circuit breaker for LLM calls (fail fast when backend is down)
- Timeout enforcement via asyncio.wait_for()
- Sanitized error messages (no raw exceptions sent to client)
- Correlated logging (task_id, context_id on every log line)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import (
    Artifact,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

from health_ai_langgraph.config import Settings

logger = logging.getLogger("health_ai_langgraph.executor")


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Simple circuit breaker: opens after ``threshold`` consecutive failures,
    stays open for ``recovery_timeout`` seconds, then moves to half-open."""

    def __init__(self, threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self._threshold = threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._state = "closed"  # closed | open | half-open

    @property
    def state(self) -> str:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                self._state = "half-open"
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._threshold:
            self._state = "open"

    def allow_request(self) -> bool:
        state = self.state
        if state == "closed":
            return True
        if state == "half-open":
            return True  # allow one probe request
        return False


# Module-level circuit breaker (shared across executor invocations within one process)
_circuit = CircuitBreaker(threshold=5, recovery_timeout=30.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_error(exc: Exception) -> str:
    """Return a user-safe error message without leaking internals."""
    exc_type = type(exc).__name__
    if isinstance(exc, asyncio.TimeoutError):
        return "The request timed out. Please try again in a moment."
    if "connection" in str(exc).lower() or "refused" in str(exc).lower():
        return "The AI service is temporarily unavailable. Please try again later."
    return "An unexpected error occurred while processing your request. Please try again."


def _extract_user_text(context: RequestContext) -> str:
    """Pull the user's text from the A2A request message."""
    if context.message and context.message.parts:
        for part in context.message.parts:
            root = part.root if hasattr(part, "root") else part
            if isinstance(root, TextPart):
                return root.text
            if hasattr(root, "text") and root.text:
                return root.text
    return ""


def _build_a2a_parts(messages: list[BaseMessage]) -> list[Part]:
    """Convert LangGraph output messages into A2A Part objects.

    The frontend's json-extractor.ts parses cards from:
    1. ``extractJsonFromText`` — finds ```json code blocks in TextPart text
    2. ``getPartData`` + ``isKnownCard`` — checks DataPart data for component_type

    Strategy:
    - Find the last ToolMessage containing structured tool output (the card).
    - Find the last AIMessage for the intro text.
    - Strip the LLM's JSON code block from the intro text and replace it
      with a properly-serialized JSON code block from ``json.dumps``.
    - Emit a single TextPart so the frontend's text-based extraction works.
    """
    import json
    import re

    last_card_result: dict | None = None
    last_tool_is_text: bool = False
    last_tool_text: str = ""
    last_ai_text: str = ""

    for msg in messages:
        if isinstance(msg, ToolMessage):
            content = msg.content
            if isinstance(content, dict):
                last_card_result = content
                last_tool_is_text = False
            elif isinstance(content, str):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        last_card_result = parsed
                        last_tool_is_text = False
                    else:
                        last_tool_is_text = True
                        last_tool_text = content
                except (json.JSONDecodeError, TypeError):
                    last_tool_is_text = True
                    last_tool_text = content

        elif isinstance(msg, AIMessage) and msg.content:
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
            if text.strip():
                last_ai_text = text

    parts: list[Part] = []

    if last_tool_is_text and last_tool_text:
        parts.append(Part(root=TextPart(text=last_tool_text)))
    elif last_card_result is not None:
        intro = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", last_ai_text).strip()
        if not intro:
            intro = "Here are the results:"

        valid_json = json.dumps(last_card_result, indent=2, ensure_ascii=False)
        combined = f"{intro}\n```json\n{valid_json}\n```"
        parts.append(Part(root=TextPart(text=combined)))
    elif last_ai_text:
        parts.append(Part(root=TextPart(text=last_ai_text)))

    return parts


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class LangGraphA2AExecutor(AgentExecutor):
    """Bridges A2A protocol requests to a compiled LangGraph agent."""

    def __init__(self, graph: CompiledStateGraph, settings: Settings) -> None:
        super().__init__()
        self._graph = graph
        self._timeout = settings.request_timeout_seconds

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Process an A2A request through the LangGraph agent.

        Lifecycle:
        1. Emit ``submitted`` status if this is a new task.
        2. Emit ``working`` status.
        3. Check circuit breaker — fail fast if open.
        4. Invoke the LangGraph agent with timeout enforcement.
        5. Convert the agent output to A2A artifacts + ``completed`` status.
        6. On failure, emit ``failed`` status with sanitized error message.
        """
        task_id = context.task_id
        context_id = context.context_id
        start_time = time.monotonic()

        extra = {"task_id": task_id, "context_id": context_id}

        # 1. New task → submitted
        if not context.current_task:
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    final=False,
                    status=TaskStatus(
                        state=TaskState.submitted,
                        message=context.message,
                        timestamp=_now_iso(),
                    ),
                )
            )

        # 2. Working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                final=False,
                status=TaskStatus(state=TaskState.working, timestamp=_now_iso()),
            )
        )

        try:
            # 3. Circuit breaker check
            if not _circuit.allow_request():
                raise ConnectionError(
                    "Circuit breaker is open — LLM backend is unavailable"
                )

            # 4. Invoke LangGraph agent with timeout
            user_text = _extract_user_text(context)
            logger.info(
                "Invoking LangGraph agent input=%r",
                user_text[:120],
                extra=extra,
            )

            config = {"configurable": {"thread_id": context_id or task_id}}

            result = await asyncio.wait_for(
                self._graph.ainvoke(
                    {"messages": [HumanMessage(content=user_text)]},
                    config=config,
                ),
                timeout=self._timeout,
            )

            _circuit.record_success()

            # 5. Convert output → A2A parts
            output_messages: list[BaseMessage] = result.get("messages", [])
            parts = _build_a2a_parts(output_messages)

            if not parts:
                parts = [Part(root=TextPart(text="I processed your request but have no output to show."))]

            # Emit artifact
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    last_chunk=True,
                    artifact=Artifact(
                        artifact_id=str(uuid.uuid4()),
                        parts=parts,
                    ),
                )
            )

            # Emit completed
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    final=True,
                    status=TaskStatus(
                        state=TaskState.completed,
                        timestamp=_now_iso(),
                        message=Message(
                            message_id=str(uuid.uuid4()),
                            role=Role.agent,
                            parts=parts,
                        ),
                    ),
                )
            )
            logger.info(
                "Task completed with %d parts",
                len(parts),
                extra={**extra, "duration_ms": duration_ms},
            )

        except Exception as exc:
            _circuit.record_failure()
            duration_ms = int((time.monotonic() - start_time) * 1000)

            # Log full exception for debugging
            logger.exception(
                "Task failed: %s",
                exc,
                extra={**extra, "duration_ms": duration_ms},
            )

            # 6. Send sanitized error to client
            safe_message = _sanitize_error(exc)
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    final=True,
                    status=TaskStatus(
                        state=TaskState.failed,
                        timestamp=_now_iso(),
                        message=Message(
                            message_id=str(uuid.uuid4()),
                            role=Role.agent,
                            parts=[Part(root=TextPart(text=safe_message))],
                        ),
                    ),
                )
            )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Cancel a running task."""
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=True,
                status=TaskStatus(
                    state=TaskState.canceled,
                    timestamp=_now_iso(),
                    message=Message(
                        message_id=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[Part(root=TextPart(text="Task cancelled."))],
                    ),
                ),
            )
        )
