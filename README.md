# Health AI

A full-stack healthcare information assistant powered by **Google ADK** (Agent Development Kit) with the **A2A** (Agent-to-Agent) protocol on the backend and a **Next.js** generative UI frontend.

The agent provides visit summaries, symptom analysis, and lab report interpretations — returning structured JSON that the frontend renders as rich, interactive UI cards.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser (localhost:3000)                                            │
│  Next.js App  ──  React Chat UI  ──  Card Renderer (registry)       │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  POST /api/chat
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Next.js Route Handler (server-side proxy)                           │
│  • Constructs A2A message (ROLE_USER, protobuf format)               │
│  • POST /v1/message:send → agent                                     │
│  • Polls GET /v1/tasks/{id} until terminal state                     │
│  • Returns unwrapped task as { result, error } envelope              │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  HTTP/REST transport
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Health AI A2A Server (localhost:8001)                                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Dual Transport                                                │  │
│  │  • JSONRPC  →  POST /                                          │  │
│  │  • HTTP/REST → POST /v1/message:send, GET /v1/tasks/{id}, etc. │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Google ADK LlmAgent (gemini-2.0-flash)                        │  │
│  │  Tools:                                                        │  │
│  │  • get_visit_summary(patient_id) → VisitSummaryCard            │  │
│  │  • analyze_symptoms(symptoms)    → SymptomAnalysisCard         │  │
│  │  • summarize_lab_report(text)    → LabReportCard               │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | >= 3.11 |
| Node.js | >= 18 |
| npm | >= 9 |
| Google API Key | [Get one from Google AI Studio](https://aistudio.google.com/apikey) |

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url> health-ai
cd health-ai
```

### 2. Backend setup

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install the package and all dependencies
pip install -e .

# For development tools (ruff, pytest)
pip install -e ".[dev]"
```

### 3. Backend environment

Copy the example env file and add your Google API key:

```bash
cp .env.example .env
```

Edit `.env`:

```env
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_GENAI_USE_VERTEXAI=FALSE
HOST=0.0.0.0
PORT=8001
LOG_LEVEL=INFO
```

### 4. Frontend setup

```bash
cd frontend
npm install
```

The frontend env file is pre-configured at `frontend/.env.local`:

```env
A2A_AGENT_URL=http://localhost:8001
```

---

## Running

You need **two terminals** — one for the backend, one for the frontend.

**Terminal 1 — Backend:**

```bash
cd health-ai
source .venv/bin/activate
python -m health_ai.server
```

You should see:

```
Starting Health AI A2A server on 0.0.0.0:8001 (JSONRPC + HTTP/REST)
JSONRPC transport mounted at /
REST route: POST /v1/message:send
REST route: GET /v1/tasks/{task_id}
...
```

**Alternative — Docker (backend only):**

```bash
docker build -t health-ai .
docker run --rm -p 8001:8001 -e GOOGLE_API_KEY=your_key_here health-ai
```

**Terminal 2 — Frontend:**

```bash
cd health-ai/frontend
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## Test Queries

| Query | Expected Card |
|---|---|
| `Show me the visit summary for patient P001` | Visit Summary Card (Dr. Sarah Chen, cardiology) |
| `Get visit summary for P002` | Visit Summary Card (second patient) |
| `I have a headache and fever` | Symptom Analysis Card (severity, conditions, recommendations) |
| `Show me my lab results` | Lab Report Card (CBC panel with status indicators) |
| `Visit summary for P999` | Error Card (patient not found) |

Demo patient IDs: **P001**, **P002**

---

## How the Backend Works

### Google ADK Agent

The core agent is defined in `src/health_ai/agent.py` as a `google.adk.agents.LlmAgent`:

- **Model**: `gemini-2.0-flash`
- **Function calling**: `FunctionCallingConfigMode.AUTO` — the model decides when to call tools based on user input
- **System instruction**: Directs the agent to always use tools for health queries and return the tool result JSON verbatim in a code block

### Tools

Each tool is a plain Python function in `src/health_ai/tools/` that returns a dictionary with a `status` field:

| Tool | File | Purpose |
|---|---|---|
| `get_visit_summary` | `tools/visit_summary.py` | Looks up mock visit records by patient ID |
| `analyze_symptoms` | `tools/symptom_analysis.py` | Analyzes a comma-separated symptom string |
| `summarize_lab_report` | `tools/lab_report.py` | Parses and summarizes lab report text |

**Return convention** (ADK best practice):

```python
# Success
{"status": "success", "component_type": "visit_summary_card", ...fields...}

# Error
{"status": "error", "error_message": "No visit records found for patient 'P999'."}
```

The `component_type` field acts as a discriminator — the frontend uses it to select which React component renders the card.

### Pydantic Schemas

`src/health_ai/schemas/ui.py` defines the card structures:

- **VisitSummaryCard** — visit_date, provider_name, diagnosis, medications, vitals, follow_up
- **SymptomAnalysisCard** — reported_symptoms, possible_conditions, severity, recommendations, when_to_seek_care
- **LabReportCard** — report_date, results (test_name, value, unit, reference_range, status), abnormal_count

### A2A Server

`src/health_ai/server.py` creates a Starlette ASGI app with dual transport:

1. **JSONRPC** (POST `/`) — standard A2A protocol transport
2. **HTTP/REST** (POST `/v1/message:send`, GET `/v1/tasks/{id}`, etc.) — protobuf-style REST transport used by the frontend

The server uses:
- `A2aAgentExecutor` — wraps the ADK agent for A2A task execution
- `DefaultRequestHandler` — handles A2A protocol request/response lifecycle
- `InMemoryTaskStore` — stores task state during async execution
- In-memory services for sessions, artifacts, memory, and credentials

### Agent Card

`agent_card.json` describes the agent's capabilities per the A2A protocol (v0.3.0), including supported skills, transport endpoints, and I/O modes.

### Configuration

`src/health_ai/config.py` uses `pydantic-settings` to load configuration from environment variables and `.env` file with LRU-cached singleton access.

---

## How the Frontend Works

### Next.js Route Handler Proxy

`src/app/api/chat/route.ts` acts as a server-side proxy between the browser and the A2A agent:

1. Receives `{ message: string }` from the chat UI
2. Constructs a protobuf-format A2A message (`ROLE_USER`, `content` array)
3. Sends `POST /v1/message:send` to the agent
4. If the task isn't in a terminal state, polls `GET /v1/tasks/{id}` every 500ms (max 30s)
5. Returns `{ result: task }` or `{ error: {...} }` to the browser

This keeps the agent URL server-side (no CORS issues) and is extensible for auth/logging.

### JSON Extractor

`src/lib/json-extractor.ts` is the core extraction engine that pulls structured card data from A2A responses. It handles multiple serialization formats:

**Extraction priority** (first match wins):
1. **ADK DataPart** with `function_response` metadata — direct tool result (most reliable)
2. **Plain DataPart** with `component_type` — structured data part
3. **JSON code block** in text — ` ```json {...} ``` ` embedded in agent prose
4. **Raw JSON** in text — outermost `{...}` in agent text

**Handles edge cases:**
- Protobuf REST format (`adk_type` underscore) vs Pydantic format (`adk:type` colon)
- Double-nested data (`data.data.response`) from REST transport
- LLM wrapper objects (`{"get_visit_summary_response": {...card...}}`)
- Tool error status conversion (`status: "error"` → ErrorCard)

### Chat State Management

`src/hooks/use-chat.ts` uses `useReducer` with four actions:

| Action | Purpose |
|---|---|
| `ADD_USER_MESSAGE` | Appends user message, sets `isLoading: true` |
| `ADD_AGENT_PLACEHOLDER` | Adds a loading placeholder for the agent response |
| `RESOLVE_AGENT_MESSAGE` | Replaces placeholder with agent text + optional card |
| `REJECT_AGENT_MESSAGE` | Replaces placeholder with error message + ErrorCard |

### Card Rendering (Registry Pattern)

`src/components/cards/CardRenderer.tsx` maps `component_type` to React components:

```
visit_summary_card   →  VisitSummaryCard
symptom_analysis_card →  SymptomAnalysisCard
lab_report_card      →  LabReportCard
error                →  ErrorCard
```

Adding a new card type requires: (1) a backend tool returning the new `component_type`, (2) a new React component, (3) one line in the CardRenderer switch.

### UI Components

| Component | Purpose |
|---|---|
| `SeverityBadge` | Color-coded severity indicator (low/moderate/high/urgent) |
| `StatusBadge` | Lab result status indicator (normal/low/high/critical) |
| `VitalsGrid` | 4-column key-value grid for patient vitals |
| `MedicationTable` | 3-column table (medication, dosage, frequency) |
| `LabResultsTable` | Table with color-coded status per test result |
| `MedicalDisclaimer` | Persistent disclaimer banner |
| `Spinner` | Loading animation |

### Styling

- **Tailwind CSS v4** with a healthcare-themed color palette (teal primary, blue secondary)
- Custom CSS variables in `globals.css` for `medical-*` color tokens
- Compact card design optimized for information density

---

## Project Structure

```
health-ai/
├── .env.example                          # Backend env template
├── .env                                  # Backend env (git-ignored)
├── agent_card.json                       # A2A agent card (protocol v0.3.0)
├── pyproject.toml                        # Python package config
├── src/
│   └── health_ai/
│       ├── __init__.py
│       ├── agent.py                      # LlmAgent definition + system instruction
│       ├── config.py                     # pydantic-settings configuration
│       ├── server.py                     # A2A server (JSONRPC + REST dual transport)
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── ui.py                     # Pydantic card models
│       └── tools/
│           ├── __init__.py
│           ├── visit_summary.py          # get_visit_summary tool
│           ├── symptom_analysis.py       # analyze_symptoms tool
│           └── lab_report.py             # summarize_lab_report tool
└── frontend/
    ├── .env.local                        # Frontend env (agent URL)
    ├── package.json                      # Next.js + React + Tailwind
    ├── tsconfig.json
    ├── next.config.ts
    ├── tailwind.config.ts
    ├── postcss.config.mjs
    └── src/
        ├── app/
        │   ├── layout.tsx                # Root layout, fonts, metadata
        │   ├── page.tsx                  # Main page → ChatContainer
        │   ├── globals.css               # Tailwind + healthcare CSS vars
        │   └── api/chat/route.ts         # Proxy: POST /api/chat → agent REST
        ├── lib/
        │   ├── types.ts                  # All TypeScript types
        │   ├── a2a-client.ts             # Client: calls /api/chat
        │   ├── json-extractor.ts         # Extract card JSON from A2A response
        │   ├── constants.ts              # Component types, severity colors
        │   └── utils.ts                  # cn() helper (clsx + tailwind-merge)
        ├── hooks/
        │   └── use-chat.ts              # useReducer chat state
        └── components/
            ├── chat/
            │   ├── ChatContainer.tsx      # Top-level client component
            │   ├── ChatMessageList.tsx    # Scrollable message list
            │   ├── ChatMessage.tsx        # User/agent bubble + card
            │   ├── ChatInput.tsx          # Text input + send button
            │   └── TypingIndicator.tsx    # Animated loading dots
            ├── cards/
            │   ├── CardRenderer.tsx       # component_type → component registry
            │   ├── VisitSummaryCard.tsx   # Visit details card
            │   ├── SymptomAnalysisCard.tsx # Symptom triage card
            │   ├── LabReportCard.tsx      # Lab results card
            │   └── ErrorCard.tsx          # Error display card
            └── ui/
                ├── MedicalDisclaimer.tsx  # Disclaimer banner
                ├── SeverityBadge.tsx      # Severity color badge
                ├── StatusBadge.tsx        # Lab status color badge
                ├── VitalsGrid.tsx         # Vitals key-value grid
                ├── MedicationTable.tsx    # Medication table
                ├── LabResultsTable.tsx    # Lab results table
                └── Spinner.tsx           # Loading spinner
```

---

## Tech Stack

### Backend
| Package | Purpose |
|---|---|
| `google-adk[a2a]` >= 1.18.0 | Google Agent Development Kit with A2A support |
| `a2a-sdk` >= 0.3.22 | Agent-to-Agent protocol SDK |
| `pydantic-settings` >= 2.7.0 | Typed configuration from env vars |
| `uvicorn` >= 0.34.0 | ASGI server |
| `python-dotenv` >= 1.1.0 | .env file loading |

### Frontend
| Package | Purpose |
|---|---|
| `next` 16.x | React framework (App Router) |
| `react` 19.x | UI library |
| `tailwindcss` v4 | Utility-first CSS |
| `clsx` + `tailwind-merge` | Conditional class merging |

---

## A2A Protocol Details

This project implements the [A2A protocol](https://github.com/google/A2A) v0.3.0 with dual transport:

- **JSONRPC transport** — `POST /` with standard JSON-RPC 2.0 envelope (`message/send`, `tasks/get`)
- **HTTP/REST transport** — RESTful endpoints with protobuf-style enums:
  - `POST /v1/message:send` — send a message, returns task
  - `GET /v1/tasks/{id}` — poll task status
  - `GET /v1/tasks` — list all tasks
  - `GET /.well-known/agent.json` — agent card discovery

The frontend uses the **REST transport** because it maps naturally to HTTP fetch and the protobuf format is well-defined for parsing.

---

## License

MIT
