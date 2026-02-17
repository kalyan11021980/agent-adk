"""LangGraph <-> A2A protocol bridge.

Implements the ``AgentExecutor`` interface from the ``a2a-sdk`` so that
the ``DefaultRequestHandler`` can drive the MedGemma agent while
producing standards-compliant A2A task events.

Adapted from the langgraph variant. Key difference: tool results appear
as HumanMessage("Function X returned:\n{json}") instead of ToolMessage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
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
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from health_ai_medgemma.config import Settings

logger = logging.getLogger("health_ai_medgemma.executor")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_error(exc: Exception) -> str:
    """Return a user-safe error message without leaking internals."""
    if isinstance(exc, asyncio.TimeoutError):
        return "The request timed out. Please try again in a moment."
    if isinstance(exc, (ConnectionError, OSError)):
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


def _current_turn_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Extract only the current conversational turn from the full history.

    The graph state (with MemorySaver) contains ALL messages across turns.
    We only want the messages from the latest user input onwards so that
    ``_build_a2a_parts`` doesn't pick up card results from prior turns.

    The boundary is the last non-function ``HumanMessage`` (i.e. a real
    user input, not a ``"Function X returned:..."`` tool feedback).
    """
    turn_start = 0
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
            if not msg.content.startswith("Function "):
                turn_start = i
                break
    return messages[turn_start:]


def _build_a2a_parts(messages: list[BaseMessage]) -> list[Part]:
    """Convert agent output messages into A2A Part objects.

    Only processes the **current turn** so that follow-up text responses
    are not contaminated with card data from previous turns.

    For the MedGemma agent, tool results appear as HumanMessage starting
    with "Function " containing JSON. The last such message holds the
    structured card data. The final AIMessage holds the agent's text.
    """
    current = _current_turn_messages(messages)

    last_card_result: dict | None = None
    last_tool_is_text: bool = False
    last_tool_text: str = ""
    last_ai_text: str = ""

    for msg in current:
        # Tool results come back as HumanMessage("Function X returned:\n{json}")
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
            if msg.content.startswith("Function "):
                # Extract JSON from the function result message
                lines = msg.content.split("\n", 1)
                if len(lines) > 1:
                    json_text = lines[1].strip()
                    try:
                        parsed = json.loads(json_text)
                        if isinstance(parsed, dict):
                            last_card_result = parsed
                            last_tool_is_text = False
                        else:
                            last_tool_is_text = True
                            last_tool_text = json_text
                    except (json.JSONDecodeError, TypeError):
                        last_tool_is_text = True
                        last_tool_text = json_text

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

class MedGemmaA2AExecutor(AgentExecutor):
    """Bridges A2A protocol requests to the compiled MedGemma agent graph."""

    def __init__(self, graph: object, settings: Settings) -> None:
        super().__init__()
        self._graph = graph
        self._timeout = settings.request_timeout_seconds

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        task_id = context.task_id
        context_id = context.context_id
        start_time = time.monotonic()
        extra = {"task_id": task_id, "context_id": context_id}

        # 1. New task -> submitted
        # Note: do NOT include message=context.message here. The
        # DefaultRequestHandler already records the user's message when
        # creating the task. Re-attaching it causes a duplicate in history.
        if not context.current_task:
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    final=False,
                    status=TaskStatus(
                        state=TaskState.submitted,
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
            user_text = _extract_user_text(context)
            logger.info(
                "Invoking MedGemma agent input=%r",
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

            # Convert output -> A2A parts
            output_messages: list[BaseMessage] = result.get("messages", [])
            parts = _build_a2a_parts(output_messages)

            if not parts:
                parts = [Part(root=TextPart(
                    text="I processed your request but have no output to show."
                ))]

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
            duration_ms = int((time.monotonic() - start_time) * 1000)

            logger.exception(
                "Task failed: %s",
                exc,
                extra={**extra, "duration_ms": duration_ms},
            )

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
