"""A2A server entrypoint for the Health AI agent.

Exposes both JSONRPC and HTTP/REST transports on the same server,
sharing a single request handler and agent executor.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

logger = logging.getLogger("health_ai")


def _configure_logging(level: str) -> None:
    """Set up structured logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def _load_agent_card(path: str):
    """Load and validate an AgentCard from a JSON file."""
    from a2a.types import AgentCard

    card_data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AgentCard(**card_data)


def create_app():
    """Build and return the A2A ASGI application.

    This factory function handles all bootstrap logic:
    1. Load .env and set required environment variables
    2. Configure logging
    3. Build shared ADK runner + A2A request handler
    4. Mount JSONRPC transport (default, at ``/``)
    5. Mount HTTP/REST transport (at ``/v1/...``)
    6. Serve the agent card at ``/.well-known/agent.json``
    """
    load_dotenv()

    from health_ai.config import get_settings

    settings = get_settings()

    _configure_logging(settings.log_level)

    # google-genai SDK reads GOOGLE_API_KEY from the environment.
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", settings.google_genai_use_vertexai)

    from a2a.server.apps import A2AStarletteApplication
    from a2a.server.apps.rest.rest_adapter import RESTAdapter
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.tasks import InMemoryTaskStore
    from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
    from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
    from google.adk.auth.credential_service.in_memory_credential_service import (
        InMemoryCredentialService,
    )
    from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
    from google.adk.runners import Runner
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from health_ai.agent import root_agent

    logger.info("Loading AgentCard from %s", settings.agent_card_path)
    agent_card = _load_agent_card(settings.agent_card_path)

    # --- Shared infrastructure (one executor, one handler) ----------------

    async def _create_runner() -> Runner:
        return Runner(
            app_name=root_agent.name,
            agent=root_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            credential_service=InMemoryCredentialService(),
        )

    task_store = InMemoryTaskStore()
    agent_executor = A2aAgentExecutor(runner=_create_runner)
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
    )

    # --- Starlette app with dual transport --------------------------------

    app = Starlette()

    async def _setup_transports():
        # 1) JSONRPC transport (POST / — default A2A transport)
        jsonrpc_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )
        jsonrpc_app.add_routes_to_app(app)
        logger.info("JSONRPC transport mounted at /")

        # 2) HTTP/REST transport (POST /v1/message:send, GET /v1/tasks/{id}, etc.)
        rest_adapter = RESTAdapter(
            agent_card=agent_card,
            http_handler=request_handler,
        )
        for (path, method), handler in rest_adapter.routes().items():
            # Skip the SDK's unimplemented list_tasks route — we add our own below.
            if path == "/v1/tasks" and method == "GET":
                continue
            app.add_route(path, handler, methods=[method])
            logger.info("REST route: %s %s", method, path)

        # 3) Custom list-tasks endpoint (not yet in a2a-sdk REST handler)
        async def list_tasks(request: Request) -> JSONResponse:
            async with task_store.lock:
                tasks = [
                    t.model_dump(mode="json", exclude_none=True)
                    for t in task_store.tasks.values()
                ]
            return JSONResponse({"tasks": tasks, "totalCount": len(tasks)})

        app.add_route("/v1/tasks", list_tasks, methods=["GET"])
        logger.info("REST route: GET /v1/tasks (custom list)")

        logger.info("HTTP/REST transport mounted at /v1/...")

    app.add_event_handler("startup", _setup_transports)

    logger.info(
        "Starting Health AI A2A server on %s:%s (JSONRPC + HTTP/REST)",
        settings.host,
        settings.port,
    )

    return app


def main() -> None:
    """CLI entrypoint — starts the uvicorn server."""
    load_dotenv()

    from health_ai.config import get_settings

    settings = get_settings()

    _configure_logging(settings.log_level)

    logger.info(
        "Launching Health AI server → http://%s:%s",
        settings.host,
        settings.port,
    )

    uvicorn.run(
        "health_ai.server:create_app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        factory=True,
    )


if __name__ == "__main__":
    main()
