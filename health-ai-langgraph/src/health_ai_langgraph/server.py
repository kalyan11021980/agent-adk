"""A2A server entrypoint for the Health AI LangGraph agent.

Exposes both JSONRPC and HTTP/REST transports on the same Starlette server,
sharing a single request handler and agent executor. Includes production-grade
middleware: CORS, request-ID propagation, health checks, and graceful shutdown.

External stores:
- **Redis** — task store (fast, ephemeral, TTL-based expiry)
- **PostgreSQL** — LangGraph checkpoints (durable conversation memory)
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
        # Include extra fields if attached
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


logger = logging.getLogger("health_ai_langgraph")


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

    Bootstrap sequence (sync part — ``create_app``):
    1. Load .env and configure settings + logging
    2. Create DI container (LLM clients + repositories)
    3. Set up middleware stack

    Async startup (``_on_startup``):
    4. Connect to Redis → create task store
    5. Connect to PostgreSQL → create checkpointer + setup tables
    6. Build LangGraph agent + A2A executor
    7. Mount JSONRPC + HTTP/REST transports
    """
    load_dotenv()

    from health_ai_langgraph.config import get_settings

    settings = get_settings()
    _configure_logging(settings.log_level)

    from health_ai_langgraph.container import Container

    logger.info("Loading AgentCard from %s", settings.agent_card_path)
    agent_card = _load_agent_card(settings.agent_card_path)

    # Create DI container (sync — LLM clients + repos)
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

    # --- Async startup: Redis + Postgres + transports ---------------------

    async def _on_startup() -> None:
        from a2a.server.apps import A2AStarletteApplication
        from a2a.server.apps.rest.rest_adapter import RESTAdapter
        from a2a.server.request_handlers import DefaultRequestHandler
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg import AsyncConnection

        from health_ai_langgraph.agent import build_agent
        from health_ai_langgraph.executor import LangGraphA2AExecutor
        from health_ai_langgraph.task_store import RedisTaskStore

        # 1) Redis task store
        task_store = await RedisTaskStore.create(
            redis_url=settings.redis_url,
            ttl=settings.task_ttl_seconds,
        )
        app.state.task_store = task_store

        # 2) PostgreSQL checkpointer
        pg_conn = await AsyncConnection.connect(
            settings.database_url,
            autocommit=True,
            prepare_threshold=0,
        )
        checkpointer = AsyncPostgresSaver(pg_conn)
        await checkpointer.setup()
        logger.info("PostgreSQL checkpointer ready at %s", settings.database_url)
        app.state.pg_conn = pg_conn
        app.state.checkpointer = checkpointer

        # 3) Build agent with Postgres checkpointer
        graph = build_agent(container, checkpointer=checkpointer)
        agent_executor = LangGraphA2AExecutor(graph=graph, settings=settings)

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
            if path == "/v1/tasks" and method == "GET":
                continue
            app.add_route(path, handler, methods=[method])
            logger.info("REST route: %s %s", method, path)

        # 6) Custom list-tasks endpoint using Redis
        async def list_tasks(request: Request) -> JSONResponse:
            tasks = await task_store.list_tasks()
            return JSONResponse({
                "tasks": [
                    t.model_dump(mode="json", exclude_none=True) for t in tasks
                ],
                "totalCount": len(tasks),
            })

        app.add_route("/v1/tasks", list_tasks, methods=["GET"])
        logger.info("REST route: GET /v1/tasks (Redis-backed)")

    app.add_event_handler("startup", _on_startup)

    # --- Graceful shutdown ------------------------------------------------

    async def _on_shutdown() -> None:
        logger.info("Shutting down — cleaning up resources")

        # Close Redis
        task_store = getattr(app.state, "task_store", None)
        if task_store:
            await task_store.close()
            logger.info("Redis task store closed")

        # Close PostgreSQL
        pg_conn = getattr(app.state, "pg_conn", None)
        if pg_conn:
            await pg_conn.close()
            logger.info("PostgreSQL connection closed")

        # Close container (LLM clients, etc.)
        await container.close()
        logger.info("Shutdown complete")

    app.add_event_handler("shutdown", _on_shutdown)

    # --- Health / readiness endpoints -------------------------------------

    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    async def readiness_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ready"})

    app.add_route("/healthz", health_check, methods=["GET"])
    app.add_route("/readyz", readiness_check, methods=["GET"])

    logger.info(
        "Starting Health AI A2A server on %s:%s (JSONRPC + HTTP/REST)",
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

    from health_ai_langgraph.config import get_settings

    settings = get_settings()
    _configure_logging(settings.log_level)

    logger.info(
        "Launching Health AI LangGraph server → http://%s:%s",
        settings.host,
        settings.port,
    )

    uvicorn.run(
        "health_ai_langgraph.server:create_app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        factory=True,
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    main()
