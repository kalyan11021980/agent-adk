# Health AI — LangGraph Edition

A full-stack healthcare information assistant using a **dual-model architecture**: **Mistral Large 3** (orchestrator with tool calling) + **MedGemma 1.5 4B** (medical reasoning), connected via the **A2A** (Agent-to-Agent) protocol to a **Next.js** generative UI frontend.

Both models run through **Ollama** (local or cloud) using the native Ollama API via `langchain-ollama`.

---

## Architecture

```
                    ┌──────────────────────────────────┐
                    │          Next.js Frontend         │
                    │                                  │
                    │  POST /api/chat → returns taskId │
                    │  GET /api/chat/status?taskId=xxx │
                    │  (client-side exponential backoff │
                    │   500ms → 1s → 2s → 4s cap)     │
                    └──────────────┬───────────────────┘
                                   │
                         A2A Protocol (HTTP/REST)
                                   │
                    ┌──────────────▼───────────────────┐
                    │     Starlette ASGI Server         │
                    │                                  │
                    │  ┌─────────────────────────────┐ │
                    │  │    DI Container              │ │
                    │  │  ┌─────────┐ ┌───────────┐  │ │
                    │  │  │  Repos  │ │ LLM Clients│  │ │
                    │  │  └─────────┘ └───────────┘  │ │
                    │  └─────────────────────────────┘ │
                    │                                  │
                    │  ┌─────────────────────────────┐ │
                    │  │  LangGraph ReAct Agent       │ │
                    │  │  (Mistral Large 3)           │ │
                    │  │  Circuit Breaker + Timeout   │ │
                    │  └──────────┬──────────────────┘ │
                    │             │                     │
                    │     ┌───────┴────────┐           │
                    │     │   Tool Layer   │           │
                    │     │  (DI closures) │           │
                    │     └───────┬────────┘           │
                    │             │                     │
                    │     ┌───────┴────────┐           │
                    │     │   MedGemma     │           │
                    │     │   (4B, local)  │           │
                    │     └────────────────┘           │
                    │                                  │
                    │  Structured JSON logging          │
                    │  Request ID correlation           │
                    │  Graceful shutdown                │
                    └──────────────────────────────────┘
```

### Dual-Model Flow

```
User Message
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Mistral Large 3 (675B, Ollama cloud)           │
│  Role: Orchestrator                             │
│                                                 │
│  • Understands user intent                      │
│  • Calls the right tool (native tool calling)   │
│  • Formats final response                       │
│  • Does NOT do medical reasoning                │
└──────┬──────────────────┬───────────────────────┘
       │                  │
  Data request         Analysis request
  "show lab report"    "explain lab report"
       │                  │
       ▼                  ▼
  ┌──────────┐     ┌──────────────┐
  │ Data Tool │     │ Data Tool    │  ← fetch data first
  └─────┬─────┘     └──────┬───────┘
       │                  │
       │                  ▼
       │         ┌──────────────────────────┐
       │         │ MedGemma 1.5 4B (local)  │
       │         │ Role: Medical expert      │
       │         │                          │
       │         │ • Interprets medical data │
       │         │ • Plain-language analysis │
       │         │ • Output sent directly    │
       │         │   to user (not rewritten) │
       │         └────────┬─────────────────┘
       │                  │
       ▼                  ▼
  Card UI (JSON)    MedGemma text (as-is)
```

| User says | Mistral does | MedGemma does | User sees |
|---|---|---|---|
| "show me my lab report" | Calls `summarize_lab_report` | Not called | Lab Report card UI |
| "explain my lab report" | Calls `summarize_lab_report`, then `consult_medgemma` | Interprets the lab data | MedGemma's bullet-point analysis |
| "I have headache and fever" | Calls `analyze_symptoms` | Not called | Symptom Analysis card UI |
| "my head is pounding" | LLM extracts keyword "headache" | Not called | Symptom Analysis card UI |
| "yes" / "tell me more" | Calls `consult_medgemma` with prior context | Explains the previous data | MedGemma's analysis |

---

## Production-Grade Features

### Dependency Injection
All shared state (repositories, LLM clients) lives in a single `Container` created at startup. Tools receive their dependencies via factory closures — no module-level globals, no monkey-patching.

### Circuit Breaker
LLM calls are protected by a circuit breaker (5 consecutive failures → open, 30s recovery → half-open probe). When open, requests fail fast instead of queuing behind a dead backend.

### Timeout Enforcement
All LLM calls are wrapped with `asyncio.wait_for(timeout)` using the configured `REQUEST_TIMEOUT_SECONDS`. The timeout is actually enforced, not just configured.

### Sanitized Errors
Raw exception messages never reach the client. The executor maps exceptions to user-safe messages:
- `TimeoutError` → "The request timed out. Please try again in a moment."
- Connection errors → "The AI service is temporarily unavailable."
- Everything else → "An unexpected error occurred."

Full stack traces are logged server-side for debugging.

### Client-Side Polling with Exponential Backoff
The Next.js server returns immediately (no held connections). The browser polls `GET /api/chat/status?taskId=xxx` with exponential backoff: 500ms → 1s → 2s → 4s cap. Each request completes in <1s, safe for API gateways with short timeouts (e.g. Apigee 10s).

### Structured JSON Logging
All log output is single-line JSON with correlation IDs:
```json
{"timestamp": "2026-02-15T10:30:00", "level": "INFO", "logger": "health_ai_langgraph.executor", "message": "Task completed with 1 parts", "request_id": "abc-123", "task_id": "task-456", "context_id": "ctx-789", "duration_ms": 3420}
```
`request_id` flows from the HTTP layer (via `contextvars.ContextVar`) through every downstream log line automatically.

### Graceful Shutdown
Starlette `on_shutdown` event cleans up the DI container (closes DB pools, flushes state). Uvicorn is configured with `timeout_graceful_shutdown=30` to drain in-flight requests before terminating.

### Pydantic Schema Validation
Tool output is validated through Pydantic models (`VisitSummaryCard`, `SymptomAnalysisCard`, `LabReportCard`) before serialization. Typos and missing fields are caught at the tool layer, not at the frontend.

### LLM-Based Symptom Extraction
Instead of a hardcoded keyword list, the orchestrator LLM extracts symptom keywords from free text and maps synonyms to canonical terms (e.g. "wheezing" → "cough", "head is pounding" → "headache"). Falls back to simple substring matching if the LLM call fails.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | >= 3.11 |
| Node.js | >= 18 |
| PostgreSQL | >= 14 (local or remote) |
| Redis | >= 5.0 (local or remote) |
| Ollama | Latest (running locally) |
| Ollama models | `mistral-large-3:675b-cloud` + `MedAIBase/MedGemma1.5:4b` |

### Install Ollama models

```bash
ollama pull mistral-large-3:675b-cloud
ollama pull MedAIBase/MedGemma1.5:4b
```

Verify they're available:

```bash
ollama list
```

---

## Installation

### 1. Backend setup

```bash
cd health-ai-langgraph

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux

# Install the package
pip install -e .

# For development tools (ruff, pytest, mypy)
pip install -e ".[dev]"
```

### 2. Backend environment

Copy the example env and configure:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434

# Orchestrator model (must support tool calling)
MODEL_NAME=mistral-large-3:675b-cloud

# Medical reasoning model
MEDGEMMA_MODEL=MedAIBase/MedGemma1.5:4b
MEDGEMMA_TEMPERATURE=0.1

# Database (PostgreSQL)
DATABASE_URL=postgresql://localhost:5432/health_ai

# Server configuration
HOST=0.0.0.0
PORT=8001
LOG_LEVEL=INFO

# Circuit breaker tuning
CIRCUIT_BREAKER_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_SECONDS=30

# Request timeout (seconds)
REQUEST_TIMEOUT_SECONDS=120
```

### 3. Frontend setup

```bash
cd ../frontend
npm install
```

Frontend env is pre-configured at `frontend/.env.local`:

```env
A2A_AGENT_URL=http://localhost:8001
```

---

## Running

Two terminals — one for backend, one for frontend.

**Terminal 1 — Backend:**

```bash
cd health-ai-langgraph
source .venv/bin/activate
python -m health_ai_langgraph.server
```

You should see structured JSON logs:

```json
{"timestamp": "2026-02-15T10:00:00", "level": "INFO", "logger": "health_ai_langgraph", "message": "Container initialized: orchestrator=mistral-large-3:675b-cloud, medgemma=MedAIBase/MedGemma1.5:4b", "request_id": "-"}
{"timestamp": "2026-02-15T10:00:00", "level": "INFO", "logger": "health_ai_langgraph", "message": "Starting Health AI A2A server on 0.0.0.0:8001 (JSONRPC + HTTP/REST)", "request_id": "-"}
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000**.

---

## Testing

```bash
cd health-ai-langgraph
source .venv/bin/activate
python -m pytest tests/ -v
```

38 tests covering:
- **Repositories** — CRUD operations, custom data injection, edge cases
- **Tools** — Factory creation, Pydantic schema validation, error paths
- **Executor** — Circuit breaker state machine, error sanitization
- **Container** — DI initialization, cleanup

---

## Tools

| Tool | Factory | When called | Returns |
|---|---|---|---|
| `get_visit_summary` | `create_visit_summary_tool(repo)` | User asks for visit/appointment records | `VisitSummaryCard` (validated JSON) |
| `analyze_symptoms` | `create_symptom_analysis_tool(repo, llm)` | User describes symptoms | `SymptomAnalysisCard` (validated JSON) |
| `summarize_lab_report` | `create_lab_report_tool(repo)` | User asks about lab/blood results | `LabReportCard` (validated JSON) |
| `consult_medgemma` | `create_medgemma_tool(llm, settings)` | User asks to explain/summarize data | Plain text analysis (from MedGemma) |

Tools are created via factory functions that receive their dependencies (repositories, LLM clients) from the DI container. No module-level globals.

---

## Conversation Context

The frontend maintains conversation context across messages via `contextId`:

1. First message → backend generates a `contextId`, returns it in the response
2. Frontend stores `contextId` in a `useRef` (avoids stale closures with rapid sends)
3. Follow-up messages include `contextId` → backend loads prior conversation from LangGraph's checkpointer
4. The agent remembers what was discussed and can answer follow-ups like "yes", "explain that", "tell me more"

---

## Configuration

`src/health_ai_langgraph/config.py` uses `pydantic-settings`:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama native API |
| `MODEL_NAME` | `mistral-large-3:675b-cloud` | Orchestrator model (needs tool calling) |
| `MEDGEMMA_MODEL` | `MedAIBase/MedGemma1.5:4b` | Medical reasoning model |
| `MEDGEMMA_TEMPERATURE` | `0.1` | MedGemma generation temperature |
| `MODEL_TEMPERATURE` | `0.0` | Orchestrator temperature |
| `DATABASE_URL` | `postgresql://localhost:5432/health_ai` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `TASK_TTL_SECONDS` | `3600` | Redis task TTL (seconds) |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8001` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins |
| `REQUEST_TIMEOUT_SECONDS` | `120` | Request timeout (enforced via asyncio) |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit opens |
| `CIRCUIT_BREAKER_RECOVERY_SECONDS` | `30` | Seconds before half-open probe |

---

## Project Structure

```
health-ai-langgraph/
├── .env.example                          # Backend env template
├── .env                                  # Backend env (git-ignored)
├── agent_card.json                       # A2A agent card (protocol v0.3.0)
├── pyproject.toml                        # Python package config + pytest config
├── Dockerfile                            # Container build
├── README.md                             # This file
├── src/
│   └── health_ai_langgraph/
│       ├── __init__.py
│       ├── agent.py                      # Dual-model ReAct agent + system prompt
│       ├── config.py                     # pydantic-settings configuration
│       ├── container.py                  # DI container (repos + LLM clients)
│       ├── exceptions.py                 # Custom exception hierarchy
│       ├── executor.py                   # LangGraph ↔ A2A bridge + circuit breaker
│       ├── server.py                     # ASGI server (JSON logging, graceful shutdown)
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── ui.py                     # Pydantic card models (validated at tool layer)
│       ├── repositories/
│       │   ├── __init__.py
│       │   ├── base.py                   # Abstract repository interfaces
│       │   └── in_memory.py              # In-memory demo implementations
│       └── tools/
│           ├── __init__.py               # Factory function exports
│           ├── visit_summary.py          # create_visit_summary_tool(repo)
│           ├── symptom_analysis.py       # create_symptom_analysis_tool(repo, llm)
│           ├── lab_report.py             # create_lab_report_tool(repo)
│           └── medical_reasoning.py      # create_medgemma_tool(llm, settings)
└── tests/
    ├── __init__.py
    ├── conftest.py                       # Shared fixtures
    ├── test_repositories.py              # Repository unit tests
    ├── test_tools.py                     # Tool factory + schema tests
    ├── test_executor.py                  # Circuit breaker + error sanitization
    └── test_container.py                 # DI container tests
```

---

## Request Flow

```
Browser
    │
    ├─ POST /api/chat {message, contextId?}
    │      Next.js returns immediately with {taskId, state}
    │
    ├─ GET /api/chat/status?taskId=xxx  (exponential backoff)
    │      Next.js thin proxy → GET /v1/tasks/{id} → backend
    │      Repeats: 500ms → 1s → 2s → 4s until terminal state
    │
    ▼
A2A Server (health-ai-langgraph, port 8001)
    │  REST transport parses request
    │  DefaultRequestHandler → LangGraphA2AExecutor
    │
    ▼
LangGraphA2AExecutor.execute()
    │  Circuit breaker check (fail fast if open)
    │  asyncio.wait_for(timeout) wraps agent call
    │  Extracts user text from A2A message
    │  Sets thread_id = contextId (for conversation memory)
    │  Calls graph.ainvoke({messages: [HumanMessage]})
    │
    ▼
LangGraph ReAct Agent (Mistral Large 3)
    │  Reasons about user intent
    │  Calls tool(s) via native function calling
    │  Tools receive repos/LLM via DI closures
    │  Tool output validated through Pydantic models
    │
    ▼
A2A TaskStatusUpdateEvent (completed) → returned to frontend
    │  Sanitized error message on failure (no raw exceptions)
    │
    ▼
Frontend parseA2AResponse()
    │  Extracts text + optional card from A2A response
    │  Renders markdown text via react-markdown
    │  Renders card via CardRenderer (if present)
    │
    ▼
User sees response
```

---

## A2A Protocol

Implements the [A2A protocol](https://github.com/google/A2A) v0.3.0 with dual transport:

- **JSONRPC** — `POST /` (standard JSON-RPC 2.0)
- **HTTP/REST** — protobuf-style endpoints:
  - `POST /v1/message:send` — send a message
  - `GET /v1/tasks/{id}` — poll task status
  - `GET /v1/tasks` — list all tasks
  - `GET /.well-known/agent.json` — agent card discovery
- **Health** — `GET /healthz`, `GET /readyz`

---

## Tech Stack

### Backend
| Package | Purpose |
|---|---|
| `langchain-core` >= 0.3.0 | LangChain core abstractions |
| `langchain-ollama` >= 1.0.0 | Native Ollama integration |
| `langgraph` >= 0.2.0 | Agent orchestration (ReAct graph, checkpointing) |
| `a2a-sdk[http-server]` >= 0.3.22 | A2A protocol SDK with HTTP server |
| `pydantic-settings` >= 2.7.0 | Typed config from env vars |
| `uvicorn` >= 0.34.0 | ASGI server |
| `python-dotenv` >= 1.1.0 | .env file loading |
| `starlette` >= 0.40.0 | ASGI framework |

### Frontend
| Package | Purpose |
|---|---|
| `next` 16.x | React framework (App Router) |
| `react` 19.x | UI library |
| `tailwindcss` v4 | Utility-first CSS |
| `@tailwindcss/typography` | Prose styling for markdown |
| `react-markdown` | Markdown rendering in chat bubbles |

### Models (via Ollama)
| Model | Role | Size | Runs on |
|---|---|---|---|
| `mistral-large-3:675b-cloud` | Orchestrator (tool calling) | Cloud | Ollama cloud |
| `MedAIBase/MedGemma1.5:4b` | Medical reasoning | 7.8 GB | Local (CPU/Metal) |

---

## Test Queries

| Query | Expected Result |
|---|---|
| `Show me the visit summary for patient P001` | Visit Summary card |
| `Get visit summary for P002` | Visit Summary card (second patient) |
| `Show me my lab report` | Lab Report card |
| `I have a headache and fever` | Symptom Analysis card |
| `My head is pounding and I feel hot` | Symptom Analysis card (LLM extracts synonyms) |
| `Explain my lab report` | MedGemma bullet-point analysis (no card) |
| `yes` / `tell me more` (after data) | MedGemma explains previous data |
| `Visit summary for P999` | Error card (patient not found) |

Demo patient IDs: **P001**, **P002**

---

## License

MIT
