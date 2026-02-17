"""A2A server entrypoint for the Health AI MedGemma agent.

Simplified from the langgraph variant — no Redis, no PostgreSQL.
Uses in-memory task store and MemorySaver for conversation state.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Context variable for request-scoped correlation IDs
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON with correlation IDs."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get("-"),
        }
        for key in ("task_id", "context_id", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                log_obj[key] = val
        if record.exc_info and record.exc_info[1]:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, default=str)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
    logging.root.handlers.clear()
    logging.root.addHandler(handler)
    logging.root.setLevel(getattr(logging, level.upper(), logging.INFO))


logger = logging.getLogger("health_ai_medgemma")


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware:
    """Inject a unique ``X-Request-ID`` header and set the contextvar."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        rid = str(uuid.uuid4())
        scope.setdefault("state", {})
        scope["state"]["request_id"] = rid
        token = request_id_var.set(rid)

        async def send_with_id(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


# ---------------------------------------------------------------------------
# Agent card loader
# ---------------------------------------------------------------------------

def _load_agent_card(path: str):
    from a2a.types import AgentCard

    card_data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AgentCard(**card_data)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> Starlette:
    """Build and return the A2A ASGI application.

    Simplified bootstrap — no Redis/PostgreSQL:
    1. Load .env and configure settings + logging
    2. Create DI container (single LLM client + repositories)
    3. Build agent with MemorySaver checkpointer
    4. Mount JSONRPC + HTTP/REST transports
    """
    load_dotenv()

    from health_ai_medgemma.config import get_settings

    settings = get_settings()
    _configure_logging(settings.log_level)

    from health_ai_medgemma.container import Container

    logger.info("Loading AgentCard from %s", settings.agent_card_path)
    agent_card = _load_agent_card(settings.agent_card_path)

    # Create DI container
    container = Container.from_settings(settings)

    # Starlette with middleware stack
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ]

    app = Starlette(middleware=middleware)
    app.add_middleware(RequestIDMiddleware)
    app.state.container = container

    # --- Startup: build agent + mount transports (all in-memory) ----------

    async def _on_startup() -> None:
        from a2a.server.apps import A2AStarletteApplication
        from a2a.server.apps.rest.rest_adapter import RESTAdapter
        from a2a.server.request_handlers import DefaultRequestHandler
        from a2a.server.tasks import InMemoryTaskStore
        from langgraph.checkpoint.memory import MemorySaver

        from health_ai_medgemma.agent import build_agent
        from health_ai_medgemma.executor import MedGemmaA2AExecutor

        # 1) In-memory task store (no Redis)
        task_store = InMemoryTaskStore()
        app.state.task_store = task_store

        # 2) MemorySaver checkpointer (no PostgreSQL)
        checkpointer = MemorySaver()
        app.state.checkpointer = checkpointer
        logger.info("In-memory task store and MemorySaver checkpointer ready")

        # 3) Build agent
        graph = build_agent(container, checkpointer=checkpointer)
        agent_executor = MedGemmaA2AExecutor(graph=graph, settings=settings)

        # 4) Wire up request handler
        request_handler = DefaultRequestHandler(
            agent_executor=agent_executor,
            task_store=task_store,
        )

        # 5) Mount transports
        jsonrpc_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )
        jsonrpc_app.add_routes_to_app(app)
        logger.info("JSONRPC transport mounted at /")

        rest_adapter = RESTAdapter(
            agent_card=agent_card,
            http_handler=request_handler,
        )
        for (path, method), handler in rest_adapter.routes().items():
            app.add_route(path, handler, methods=[method])
            logger.info("REST route: %s %s", method, path)

    app.add_event_handler("startup", _on_startup)

    # --- Health / readiness endpoints -------------------------------------

    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    async def readiness_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ready"})

    app.add_route("/healthz", health_check, methods=["GET"])
    app.add_route("/readyz", readiness_check, methods=["GET"])

    logger.info(
        "Starting Health AI MedGemma server on %s:%s (JSONRPC + HTTP/REST)",
        settings.host,
        settings.port,
    )

    return app


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entrypoint — starts the uvicorn server."""
    load_dotenv()

    from health_ai_medgemma.config import get_settings

    settings = get_settings()
    _configure_logging(settings.log_level)

    logger.info(
        "Launching Health AI MedGemma server -> http://%s:%s",
        settings.host,
        settings.port,
    )

    uvicorn.run(
        "health_ai_medgemma.server:create_app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        factory=True,
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    main()
