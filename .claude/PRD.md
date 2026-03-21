# Product Requirements Document: Agent Harness

> **Working Title:** Agent Harness (final name TBD)
> **Version:** 1.1
> **Date:** March 21, 2026
> **Status:** Draft — Ready for Review

---

## 1. Executive Summary

Agent Harness is an open-source MCP (Model Context Protocol) server that provides persistent, structured knowledge graph memory for AI coding agents. It solves the critical problem of **context loss between AI coding sessions** — where agents like Claude Code forget project decisions, repeat failed approaches, and lose accumulated insights every time a session ends or the context window compacts.

Unlike existing solutions that either embed entire codebases (RAG-heavy) or replace the agent's native workflow (task manager overrides), Agent Harness operates as a **lightweight meta-layer** that captures knowledge as a natural byproduct of the coding workflow. The agent works normally — planning, implementing, debugging — and uses two simple primitives (`remember` and `recall`) to persist and retrieve project knowledge. Behind the scenes, Graphiti builds a temporal knowledge graph that tracks decisions, insights, errors, and architectural patterns with full historical context.

The MVP goal is: **An AI coding agent that starts Session 2 already knowing everything important from Session 1 — without the developer having to re-explain anything.**

---

## 2. Mission

**Mission Statement:** Make AI coding agents permanently smarter by giving them persistent, structured memory that grows with every session.

**Core Principles:**

1. **Invisible by Design** — The knowledge capture mechanism should feel like a natural part of the coding workflow, not an additional burden. No new task management systems to learn, no Kanban boards to maintain.
2. **Light on Context, Rich in Knowledge** — Every token sent to the agent's context window is precious. The system delivers maximum insight in minimum tokens (300–400 tokens for a full project briefing).
3. **Knowledge, Not Documents** — We don't embed codebases or crawl docs. We capture the *understanding* that emerges from working with code: decisions, failures, patterns, architectural choices.
4. **Open and Self-Hosted** — Zero vendor lock-in, zero data leaving the developer's machine (except LLM API calls for entity extraction). MIT licensed, Docker-based, runs anywhere.
5. **Agent-Agnostic Foundation** — Built for Claude Code first, but architected so any MCP-compatible agent can plug in.

---

## 3. Target Users

**Primary Persona: The AI-Native Developer**

Developers who use AI coding agents (Claude Code, Cursor, Windsurf) as their primary development tool, frequently starting new sessions across multi-day or multi-week projects. They are technically comfortable with Docker, CLI tools, and environment variables, but value frictionless setup. They are frustrated by having to re-explain project context at the start of every session and watching agents repeat mistakes that were already solved.

**Technical Comfort Level:** Can run `docker compose up`, edit `.env` files, add MCP servers to Claude Code config. Should not need to understand graph databases, knowledge graphs, or Graphiti internals.

**Key Pain Points:**
- Starting a new Claude Code session means re-explaining the entire project context
- Agents attempt approaches that were already tried and failed in previous sessions
- Architectural decisions and their rationale get lost between sessions
- Context window compaction (at ~167K tokens) loses nuanced reasoning
- CLAUDE.md and MEMORY.md are too static and limited to capture evolving project knowledge (MEMORY.md capped at 200 lines, ~30% redundancy after 10 sessions)
- No structured way to capture "negative knowledge" — things that don't work

---

## 4. MVP Scope

### In Scope — Core Functionality
- ✅ MCP server with 4 tools: `prime`, `remember`, `recall`, `init_project`
- ✅ Persistent knowledge graph per project using Graphiti + FalkorDB
- ✅ Automatic entity/relationship extraction from free-text insights via Graphiti
- ✅ Temporal knowledge management (facts have valid_at/invalid_at timestamps)
- ✅ Hybrid retrieval: semantic search + BM25 keyword search + graph traversal
- ✅ Compressed project briefing at session start (300–400 tokens)
- ✅ Fixed knowledge categories: `decision`, `insight`, `error`, `goal`, `architecture`
- ✅ Multi-project support via separate graph namespaces in FalkorDB
- ✅ Optional repo scanning at project init (config files + folder structure + README/docs)

### In Scope — Technical
- ✅ Python MCP server using FastMCP
- ✅ stdio transport for Claude Code integration
- ✅ HTTP/SSE transport for future dashboard connectivity
- ✅ REST API endpoints for dashboard data access (graph data, projects, insights)
- ✅ Configurable LLM provider for entity extraction (OpenAI, Anthropic, Ollama)
- ✅ OpenAI text-embedding-3-small for vector embeddings
- ✅ **FalkorDB in Docker + MCP server via uvx/pip on host** (not 2 Docker containers)
- ✅ Async Graphiti processing (non-blocking `remember` calls)
- ✅ Example CLAUDE.md instructions for agent integration

### In Scope — Deployment
- ✅ FalkorDB via `docker compose up` (single container)
- ✅ MCP server distributed via PyPI, installed/run via `uvx agent-harness`
- ✅ `.env.example` with clear configuration documentation
- ✅ Single-user, self-hosted, no authentication required

### Out of Scope — Deferred to Future Phases
- ❌ Web dashboard UI (will be built separately in Lovable)
- ❌ Multi-user support / authentication / user isolation
- ❌ Git commit integration / automatic knowledge from commits
- ❌ Codebase embedding / full RAG over source files
- ❌ Support for non-MCP agents (direct API integration)
- ❌ Knowledge graph merging across projects
- ❌ Agent-to-agent shared memory
- ❌ Hosted/cloud version
- ❌ Custom/variable knowledge categories
- ❌ Web crawling or document upload/processing

---

## 5. User Stories

**US-1: Session Continuity**
As a developer using Claude Code, I want my agent to automatically know what happened in previous sessions, so that I don't have to re-explain the project context every time I start a new session.
> *Example: Developer starts a new Claude Code session on a Next.js project. Agent calls `prime()` and immediately knows: "Auth uses custom JWT because Supabase RLS was incompatible with service-role keys. Stripe Payment Intents are used instead of Checkout v2. Edge Functions have a 10s timeout issue."*

**US-2: No Repeated Failures**
As a developer, I want the agent to remember which approaches were tried and failed, so that it doesn't waste time attempting the same dead-end solutions.
> *Example: In Session 1, the agent spent 20 API calls discovering that Supabase's `signInWithOAuth` doesn't support PKCE flow for mobile. In Session 2, calling `prime()` or `recall("Supabase OAuth mobile")` immediately surfaces this as a known pitfall.*

**US-3: Decision Retrieval**
As a developer, I want to query why specific architectural decisions were made, so that I (or the agent) can make informed choices about related decisions.
> *Example: `recall("why custom JWT instead of Supabase Auth")` returns the full decision chain: RLS incompatibility → service-role key limitations → custom JWT solution with specific token endpoint.*

**US-4: Knowledge Accumulation**
As a developer, I want insights to be captured automatically as part of the normal coding workflow, so that I don't have to manually document everything.
> *Example: After solving a tricky CORS issue, the agent calls `remember(project_id, "Supabase Edge Functions require explicit CORS headers — Access-Control-Allow-Origin must be set per-function, not globally", category="insight")`. This is captured as a graph entity linked to "Supabase", "Edge Functions", and "CORS".*

**US-5: Project Initialization**
As a developer starting a new project, I want to optionally scan my repo structure to bootstrap the knowledge graph, so that the agent has basic context from the start.
> *Example: `init_project("my-saas", "SaaS platform for...", scan_repo=True)` reads package.json, tsconfig.json, folder structure 2 levels deep, and README.md, creating initial entities for the tech stack and project structure.*

**US-6: Minimal Setup**
As a developer, I want to set up the knowledge graph system with a single Docker command and a short addition to my CLAUDE.md, so that I can start benefiting immediately without learning a new tool.
> *Example: `docker compose up -d` (starts FalkorDB), add MCP config to Claude Code (runs `uvx agent-harness`), add instruction snippet to CLAUDE.md. Total setup time: under 5 minutes.*

**US-7: Multi-Project Isolation**
As a developer working on multiple projects, I want each project to have its own isolated knowledge graph, so that insights from one project don't leak into or pollute another.
> *Example: `init_project("project-a", ...)` and `init_project("project-b", ...)` create completely separate graph namespaces in FalkorDB. `prime("project-a")` only returns knowledge from project A.*

---

## 6. Core Architecture & Patterns

### High-Level Architecture

```
┌──────────────────────────────────────────────────┐
│           Claude Code (or any MCP client)         │
└──────────────────────┬───────────────────────────┘
                       │ MCP Protocol (stdio)
                       ▼
┌──────────────────────────────────────────────────┐
│     Agent Harness MCP Server (HOST PROCESS)       │
│     Installed via uvx / pip — runs on host        │
│     Python / FastMCP + FastAPI                    │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │  MCP Tool Layer                              │ │
│  │  prime() | remember() | recall()             │ │
│  │  init_project()                              │ │
│  └──────────────────┬──────────────────────────┘ │
│                     ▼                             │
│  ┌─────────────────────────────────────────────┐ │
│  │  Knowledge Service Layer                     │ │
│  │  - Briefing Generator (prime)                │ │
│  │  - Episode Creator (remember)                │ │
│  │  - Hybrid Search Engine (recall)             │ │
│  │  - Project Manager (init)                    │ │
│  │  - Repo Scanner (optional)                   │ │
│  └──────────────────┬──────────────────────────┘ │
│                     ▼                             │
│  ┌─────────────────────────────────────────────┐ │
│  │  Graphiti Core Library (Python import)       │ │
│  │  - Entity Extraction (async, LLM-powered)    │ │
│  │  - Relationship Resolution                   │ │
│  │  - Temporal Fact Management                  │ │
│  │  - Deduplication                             │ │
│  │  - Hybrid Retrieval (semantic+BM25+graph)    │ │
│  └──────────────────┬──────────────────────────┘ │
│                     │                             │
│  ┌─────────────────────────────────────────────┐ │
│  │  FastAPI REST Layer (HTTP, port 8080)        │ │
│  │  GET /projects | GET /projects/{id}/graph    │ │
│  │  GET /projects/{id}/insights                 │ │
│  │  GET /projects/{id}/timeline                 │ │
│  │  (For Lovable Dashboard consumption)         │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────┘
                       │ Cypher + Vector queries
                       │ (localhost:6379)
                       ▼
┌──────────────────────────────────────────────────┐
│          FalkorDB  ←  DOCKER CONTAINER ONLY       │
│  Graph Database + Native Vector Search            │
│  Separate namespace per project (group_id)        │
│  Port NOT exposed externally — Docker-internal    │
└──────────────────────────────────────────────────┘
```

**Deployment topology:** Only FalkorDB runs in Docker. The MCP server runs directly on the host, launched by Claude Code via `uvx agent-harness`. The server connects to FalkorDB at `localhost:6379` (Docker host-networking or port-forwarded at `127.0.0.1:6379`).

### Key Architectural Decisions

**Graphiti as Internal Library, Not External Service:** Graphiti-core is imported directly as a Python library within the MCP server process. There is no second MCP server or external Graphiti service. This eliminates network hops and simplifies deployment.

**MCP Server on Host, Not Docker:** The MCP server is distributed as a PyPI package and run via `uvx agent-harness`. This is required because Claude Code launches MCP servers via stdio — the parent process must spawn the child directly; Docker containers cannot be stdio children of Claude Code in the standard way.

**Async Knowledge Extraction:** When `remember()` is called, the raw episode text is stored immediately (synchronous), and Graphiti's LLM-powered entity extraction runs asynchronously in the background. This means the agent gets an instant response and can continue working, while the knowledge graph enrichment happens in parallel. If `recall()` is called before extraction completes, it falls back to full-text search on raw episodes.

**Namespace Isolation:** Each project gets its own graph namespace in FalkorDB via Graphiti's `group_id` parameter, where `group_id = project_id` (the deterministic slug). Project metadata (name, description, created_at, repo_path) is stored in a lightweight SQLite database alongside the MCP server — this does not need to be in the graph.

**`project_id` Format — Deterministic Slug:** The `project_id` is derived from `name` by lowercasing, replacing spaces/special chars with hyphens, and truncating to 64 characters. Example: `"My SaaS App"` → `"my-saas-app"`. The slug is always reconstructable from the hardcoded name in CLAUDE.md — the agent never needs to "remember" the ID separately. Pattern: `^[a-z0-9-]{1,64}$`.

**Dual Transport:** The server process runs both FastMCP (for stdio/MCP communication with Claude Code) and FastAPI (for HTTP/REST communication with the dashboard). One process, one codebase, two interfaces sharing the same knowledge service layer.

**Meta-Layer, Not Task Manager:** Unlike Archon which overrides the agent's native task system, Agent Harness coexists with the agent's built-in tools (TodoWrite, TodoRead, etc.). It captures knowledge at the meta level — decisions, insights, errors — rather than managing individual tasks. The agent decides when something is worth remembering.

### Server Startup Architecture

The server runs a **dual-transport event loop**: `asyncio.gather()` runs the FastMCP stdio coroutine and the Uvicorn HTTP server coroutine concurrently in the same event loop.

- **stdio mode:** FastMCP reads/writes JSON-RPC on stdin/stdout; FastAPI runs concurrently on port 8080
- **Critical logging requirement:** All logging MUST go to `stderr` in stdio mode — stdout is the MCP protocol channel. Any `print()` or log output directed to stdout will corrupt the JSON-RPC stream and cause client errors.
- **Uvicorn binding:** Uvicorn MUST bind to `127.0.0.1` (not `0.0.0.0`) by default — the REST API is for local dashboard use only.
- **FastMCP version pinning:** FastMCP must be pinned to a specific major version in `pyproject.toml`; the API shape differs significantly between major versions.

```python
# Conceptual startup (simplified)
async def main():
    await asyncio.gather(
        fastmcp_app.run_stdio_async(),   # MCP protocol on stdin/stdout
        uvicorn.Server(config).serve(),  # REST API on localhost:8080
    )
```

### Startup Sequence

1. **Load and validate config** — Fail fast on missing required env vars (LLM_API_KEY, etc.)
2. **Initialize SQLite database** — Create tables if they don't exist; verify write access
3. **Attempt FalkorDB connection** — Exponential backoff retry: 5 attempts, ~30s total (delays: 1s, 2s, 4s, 8s, 15s)
4. **Initialize Graphiti client** — Call `build_indices_and_constraints()` to ensure graph schema is ready
5. **Register MCP tools** — Bind all 4 tool handlers to FastMCP
6. **Start event loop** — `asyncio.gather(stdio_server, http_server)`

### Graceful Shutdown

- Register `SIGTERM`/`SIGINT` handler at process start
- Stop accepting new tool calls (return error to new requests)
- Await all pending background extraction tasks with configurable timeout (default: 30s)
- Close FalkorDB connection cleanly
- Close SQLite connection cleanly
- Exit with code 0

### Background Task Lifecycle

`remember()` spawns a background extraction task via `asyncio.create_task()`. Task reference is stored to prevent garbage collection before completion.

- **Exception handling:** Each task has an explicit exception handler — catches all exceptions, logs to stderr, updates episode status to `failed`
- **Concurrency limit:** An `asyncio.Queue` with N worker coroutines (default 4, configurable via `EXTRACTION_WORKERS`) limits simultaneous Graphiti extraction tasks. Workers consume from the queue one item at a time, providing natural back-pressure. Prevents overwhelming the LLM API rate limits.
- **Episode status field:** `pending | processing | complete | failed`
- **On abrupt kill (no SIGTERM):** In-flight background tasks may be lost. The raw episode text is always safe (stored synchronously before spawning the task); only graph enrichment enrichment may be incomplete. On next startup, episodes with `status=pending` or `status=processing` can be re-queued.

### Directory Structure

```
agent-harness/
├── docker-compose.yml          # FalkorDB only (no MCP server container)
├── .env.example
├── README.md
├── LICENSE                     # MIT
├── pyproject.toml              # Includes console_scripts entry point
│
├── src/
│   ├── __init__.py
│   ├── server.py               # FastMCP + FastAPI dual server + main()
│   ├── config.py               # Pydantic Settings, LLM provider config
│   ├── models.py               # Pydantic models
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── prime.py
│   │   ├── remember.py
│   │   ├── recall.py
│   │   └── init_project.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── knowledge.py        # Graphiti wrapper
│   │   ├── briefing.py         # Briefing generation
│   │   ├── scanner.py          # Repo structure scanning
│   │   └── projects.py         # SQLite project metadata
│   └── api/
│       ├── __init__.py
│       └── routes.py           # REST endpoints for dashboard
│
├── templates/
│   └── claude_md_instructions.md
│
├── tests/
│   ├── test_tools.py
│   ├── test_knowledge.py
│   └── test_briefing.py
│
└── docs/
    ├── setup.md
    ├── architecture.md
    └── configuration.md
```

---

## 7. Tools / Features

### Tool 1: `prime(project_id: str) → str`

**MCP Description (shown to LLM in tool schema):**
> "Load compressed project context at the start of every coding session. Call this immediately when starting work on a project. Returns a structured briefing with key decisions, known pitfalls, and recent session summary in under 400 tokens."

**Parameters:**

| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| `project_id` | `string` | yes | Pattern: `^[a-z0-9-]{1,64}$` | The project slug, e.g. `'my-saas-app'`. Must match the project created with `init_project`. |

**Purpose:** Load compressed project context at session start. This is the first thing an agent calls in every session via CLAUDE.md instruction.

**Operations:**
1. Query Graphiti for entities of type `decision`, `architecture` — extract Key Decisions
2. Query for entities of type `error`, `insight` with negative outcomes — extract Known Pitfalls
3. Get the most recent 3–5 episodes — extract Last Session Summary
4. Query project metadata from SQLite — extract Tech Stack
5. Compile into structured markdown briefing

**Output Format:**
```markdown
## Project: [Name]
**Stack:** Next.js 14, Supabase, Stripe
**Status:** 23 insights stored, 2 known pitfalls

### Key Decisions
- Auth: Custom JWT (Supabase RLS incompatible with service-role)
- Payments: Stripe Payment Intents (Checkout v2 abandoned — no webhook reliability)

### Known Pitfalls
- Supabase Edge Functions timeout after 10s for large queries
- Stripe webhook signature verification fails in dev without ngrok

### Last Session
- Implemented user registration flow
- Discovered rate limit on Supabase Auth (30 req/min)
- Started payment integration, paused at webhook setup
```

**Key Features:**
- Output capped at 300–400 tokens to preserve context window
- Prioritizes most recent and most impactful knowledge
- Temporal awareness: shows current valid state, not superseded historical states
- Returns helpful empty-state message for new projects with no knowledge yet

**Error Responses:**
```json
{ "error": "project_not_found", "message": "Project 'x' not found. Call init_project first." }
```

---

### Tool 2: `remember(project_id: str, content: str, category: str) → dict`

**MCP Description (shown to LLM in tool schema):**
> "Store a piece of project knowledge in the persistent knowledge graph. Call this whenever you discover something new about an API, make an architectural decision, encounter a failure, or receive a new requirement."

**Parameters:**

| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| `project_id` | `string` | yes | Pattern: `^[a-z0-9-]{1,64}$` | Which project this knowledge belongs to |
| `content` | `string` | yes | Min: 10 chars, Max: 2000 chars | Free-text description of the insight, decision, error, goal, or architectural choice |
| `category` | `string` (enum) | yes | Enum: `decision`, `insight`, `error`, `goal`, `architecture` | Knowledge category — controls how Graphiti classifies entities |

**Purpose:** Capture a piece of project knowledge. Core knowledge ingestion mechanism.

**Operations:**
1. Validate category against allowed enum values
2. Store raw episode text immediately (synchronous) with timestamp, category metadata, and `status=pending`
3. Trigger Graphiti `add_episode()` asynchronously — entity extraction, relationship resolution, deduplication, temporal fact creation all happen in background (3–6 LLM calls per episode)
4. Return confirmation immediately; background task updates status to `processing` then `complete` or `failed`

**Response:**
```json
{
  "status": "stored",
  "episode_id": "ep_abc123",
  "category": "decision",
  "processing": "async — graph extraction in progress"
}
```

**Error Responses:**
```json
{ "error": "invalid_category", "message": "Category must be one of: decision, insight, error, goal, architecture" }
{ "error": "content_too_short", "message": "Content must be at least 10 characters." }
{ "error": "project_not_found", "message": "Project 'x' not found. Call init_project first." }
```

**Key Features:**
- Non-blocking: Agent gets instant confirmation, Graphiti processes in background
- Graphiti automatically extracts entities, creates relationships, and manages temporal facts
- Deduplication: Existing entities are merged, not duplicated
- Contradiction handling: Old facts get `invalid_at` timestamps but are never deleted
- Background task is tracked by status: `pending | processing | complete | failed`

**Category Definitions:**
- `decision` — Choosing between approaches, with rationale and alternatives considered
- `insight` — New understanding about an API, library, tool, or system behavior
- `error` — Something that was tried and failed, including why it failed
- `goal` — A user-defined requirement, objective, or constraint
- `architecture` — System structure changes, component relationships, tech stack choices

---

### Tool 3: `recall(project_id: str, query: str) → str`

**MCP Description (shown to LLM in tool schema):**
> "Search the knowledge graph for specific information. Use natural language questions or keyword phrases. Call this when unsure if something was already tried or decided."

**Parameters:**

| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| `project_id` | `string` | yes | Pattern: `^[a-z0-9-]{1,64}$` | Which project to search |
| `query` | `string` | yes | Min: 3 chars, Max: 500 chars | Natural language question or keyword phrase. Example: `'why did we choose JWT over Supabase Auth?'` |

**Purpose:** Search the knowledge graph for specific information.

**Operations:**
1. Execute Graphiti hybrid search: cosine semantic similarity + BM25 keyword match + breadth-first graph traversal
2. Fuse results via Reciprocal Rank Fusion (RRF)
3. If graph extraction is still pending for recent episodes, also search raw episode text
4. Format top results as structured markdown
5. Cap output at 300–500 tokens

**Key Features:**
- No LLM calls during retrieval — all search is index-based (P95 ~300ms)
- Graph traversal follows entity relationships to surface connected knowledge
- Temporal awareness: returns current valid facts with historical context when relevant
- Falls back to raw episode full-text search for recently stored but not-yet-extracted knowledge

**Error Responses:**
```json
{ "error": "no_results", "message": "No matching knowledge found for query." }
{ "error": "project_not_found", "message": "Project 'x' not found. Call init_project first." }
```

---

### Tool 4: `init_project(name: str, description: str, scan_repo: bool = False, repo_path: str = None) → dict`

**MCP Description (shown to LLM in tool schema):**
> "Create or retrieve a project with its own isolated knowledge graph namespace. Idempotent: safe to call multiple times with the same name. Returns existing project if name already exists."

**Parameters:**

| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| `name` | `string` | yes | Min: 1 char, Max: 128 chars | Human-readable project name. Used to generate the deterministic `project_id` slug. |
| `description` | `string` | yes | Min: 1 char, Max: 500 chars | Brief project description |
| `scan_repo` | `bool` | no | Default: `false` | Whether to scan a directory for initial context |
| `repo_path` | `string` | no | Valid filesystem path | Path to repo root. Defaults to current working directory if `scan_repo=true` and this is omitted. |

**`project_id` Generation:**
The returned `project_id` is a deterministic slug derived from `name`:
- Lowercase
- Spaces and non-alphanumeric characters replaced with hyphens
- Consecutive hyphens collapsed
- Leading/trailing hyphens removed
- Truncated to 64 characters
- Pattern: `^[a-z0-9-]{1,64}$`

Example: `"My SaaS App"` → `"my-saas-app"`, `"Project Alpha (v2)"` → `"project-alpha-v2"`

**Repo Scan Behavior (when `scan_repo=True`):**
1. Read config files: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `docker-compose.yml`, `tsconfig.json`, `.env.example`
2. Read folder structure 2 levels deep (excluding `node_modules`, `.git`, `__pycache__`, `dist`, `build`)
3. Read `README.md` and any `docs/*.md` files
4. Feed all collected context as initial episodes into Graphiti for entity extraction

**Response:**
```json
{
  "project_id": "my-saas-app",
  "name": "My SaaS App",
  "status": "created",
  "description": "...",
  "created_at": "2026-03-21T10:00:00Z"
}
```
*(When project already exists, `"status": "existing"` is returned instead of `"created"`)*

**Error Responses:**
```json
{ "error": "invalid_name", "message": "Project name cannot be empty." }
{ "error": "scan_failed", "message": "Could not read repo at path '/invalid/path'." }
```

**Key Features:**
- **Idempotent:** Calling with an existing project name returns the existing project unchanged
- Repo scan is non-destructive and read-only
- Without `scan_repo`, the project starts empty — knowledge builds purely from `remember()` calls
- `project_id` in response should be hardcoded into CLAUDE.md for future sessions

---

### REST API Endpoints (for Lovable Dashboard)

Read-only HTTP endpoints for future dashboard consumption. Detailed schemas defined during implementation.

```
GET  /api/health                              → Service status, FalkorDB connection
GET  /api/projects                            → List all projects with stats
GET  /api/projects/{project_id}               → Project details
GET  /api/projects/{project_id}/graph         → Nodes + edges for visualization
GET  /api/projects/{project_id}/insights      → Paginated knowledge items, filterable by category
GET  /api/projects/{project_id}/timeline      → Chronological episode list
```

---

## 8. Technology Stack

### Backend
- **Python 3.11+** — Primary language
- **FastMCP** (pinned major version) — MCP server framework (stdio + SSE transport)
- **FastAPI** — REST API framework for dashboard endpoints
- **graphiti-core** — Temporal knowledge graph library (Apache 2.0). **[VERIFY latest version on PyPI before pinning — version ≥X.Y.Z]**
- **Uvicorn** — ASGI server (bind to `127.0.0.1` by default)
- **anyio** — Required for `asyncio.gather` dual-transport event loop

### Database
- **FalkorDB** (latest Docker image — pin to specific version for production) — Graph database with native vector search
- **SQLite** — Project metadata storage (embedded, zero-config)

### AI/ML (Configurable)
- **LLM for Entity Extraction:**
  - OpenAI `gpt-4.1-mini` (default)
  - Anthropic `claude-3-5-haiku-20241022` (alternative) — **[VERIFY: check if Claude 4 Haiku model ID is available and preferred]**
  - Ollama local models (cost-free option)
- **Embedding Model:** OpenAI `text-embedding-3-small`

### Infrastructure
- **Docker + Docker Compose** — FalkorDB container only (MCP server runs on host)
- **PyPI** — Distribution channel for MCP server package (`agent-harness`)
- **uv / uvx** — Recommended install and run method

### Core Dependencies
`graphiti-core`, `fastmcp`, `fastapi`, `uvicorn`, `anyio`, `falkordb`, `openai`, `anthropic`, `pydantic`, `aiosqlite`

---

## 9. Deployment

### Pattern A: FalkorDB in Docker + MCP Server via uvx (Primary)

This is the only supported deployment pattern for the MVP.

**Prerequisites:**
- Docker Desktop (or Docker Engine) installed and running
- Python 3.11+ installed
- `uv` installed (`pip install uv` or via official installer)

**Setup Steps:**

1. **Start FalkorDB:**
   ```bash
   # Clone or download docker-compose.yml (FalkorDB-only version)
   docker compose up -d
   # Verify: docker compose ps → falkordb should be "healthy"
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env — fill in LLM_API_KEY and OPENAI_API_KEY at minimum
   ```

3. **Add MCP server to Claude Code:**
   ```bash
   # Edit ~/.claude/.mcp.json (see Appendix for full config)
   # Claude Code will launch the MCP server via: uvx agent-harness
   ```

4. **Restart Claude Code** to pick up the new MCP server

5. **Initialize your first project** (from within Claude Code):
   ```
   Call init_project with your project name to create the knowledge graph namespace.
   Then hardcode the returned project_id slug into your CLAUDE.md.
   ```

**Verification:**
```bash
curl http://localhost:8080/api/health
# Expected: {"status": "ok", "falkordb_connected": true, "projects_count": 0}
```

---

## 10. Security & Configuration

### Environment Variables (`.env`)

```env
# Required
LLM_PROVIDER=openai              # openai | anthropic | ollama
LLM_API_KEY=sk-...               # API key for chosen provider
LLM_MODEL=gpt-4.1-mini           # Model for entity extraction
OPENAI_API_KEY=sk-...             # For embeddings (text-embedding-3-small)

# Optional (defaults shown)
FALKORDB_HOST=localhost           # localhost when MCP server runs on host
FALKORDB_PORT=6379
MCP_TRANSPORT=stdio               # stdio | sse
HTTP_PORT=8080                    # REST API port
LOG_LEVEL=info
SQLITE_PATH=~/.agent-harness/projects.db   # Configurable SQLite location
UVICORN_HOST=127.0.0.1            # Default: localhost only (do not change to 0.0.0.0)
ALLOWED_ORIGINS=http://localhost:3000      # CORS for dashboard (Phase 4)
MCP_ENV_FILE=/absolute/path/.env  # Optional: load config from explicit file path
```

### Security Model
- Single-user, self-hosted, no authentication (MVP)
- All data stored locally (FalkorDB volume + SQLite file)
- No data transmitted except to configured LLM API for entity extraction
- FalkorDB port is exposed **only on `127.0.0.1:6379`** via `ports: "127.0.0.1:6379:6379"` in `docker-compose.yml` — loopback-only, not accessible from outside the machine. On Linux, Docker does NOT bridge `localhost:6379` to the container without an explicit `ports:` mapping; the binding is required.
- Uvicorn binds to `127.0.0.1` by default — REST API not exposed to network

### Security Notes

- **`.env` MUST be in `.gitignore`** — only `.env.example` (with placeholder values) is committed to source control
- **MCP env vars are NOT inherited from the developer's shell** — all config must be placed in the `.mcp.json` `env` block or pointed to via `MCP_ENV_FILE` path. Do not assume shell env vars are available to the MCP server process.
- **FalkorDB port isolation:** The `docker-compose.yml` MUST include `ports: "127.0.0.1:6379:6379"` — binds FalkorDB only on the loopback interface. On Linux, Docker does NOT auto-bridge `localhost:6379` without an explicit `ports:` mapping. The `127.0.0.1` prefix ensures the port is not reachable from external machines.

---

## 11. API Specification

### MCP Tool Schemas

#### `prime`
```json
{
  "name": "prime",
  "description": "Load compressed project context at the start of every coding session. Call this immediately when starting work on a project. Returns a structured briefing with key decisions, known pitfalls, and recent session summary in under 400 tokens.",
  "inputSchema": {
    "type": "object",
    "required": ["project_id"],
    "properties": {
      "project_id": {
        "type": "string",
        "pattern": "^[a-z0-9-]{1,64}$",
        "description": "The project slug, e.g. 'my-saas-app'. Must match the project created with init_project."
      }
    }
  }
}
```

#### `remember`
```json
{
  "name": "remember",
  "description": "Store a piece of project knowledge in the persistent knowledge graph. Call this whenever you discover something new about an API, make an architectural decision, encounter a failure, or receive a new requirement.",
  "inputSchema": {
    "type": "object",
    "required": ["project_id", "content", "category"],
    "properties": {
      "project_id": {
        "type": "string",
        "pattern": "^[a-z0-9-]{1,64}$",
        "description": "Which project this knowledge belongs to."
      },
      "content": {
        "type": "string",
        "minLength": 10,
        "maxLength": 2000,
        "description": "Free-text description of the insight, decision, error, goal, or architectural choice. Be specific."
      },
      "category": {
        "type": "string",
        "enum": ["decision", "insight", "error", "goal", "architecture"],
        "description": "Knowledge category. Use 'error' for failed approaches, 'decision' for choices with rationale, 'insight' for API/library learnings."
      }
    }
  }
}
```

#### `recall`
```json
{
  "name": "recall",
  "description": "Search the knowledge graph for specific information. Use natural language questions or keyword phrases. Call this when unsure if something was already tried or decided.",
  "inputSchema": {
    "type": "object",
    "required": ["project_id", "query"],
    "properties": {
      "project_id": {
        "type": "string",
        "pattern": "^[a-z0-9-]{1,64}$",
        "description": "Which project to search."
      },
      "query": {
        "type": "string",
        "minLength": 3,
        "maxLength": 500,
        "description": "Natural language question or keyword phrase. Example: 'why did we choose JWT over Supabase Auth?'"
      }
    }
  }
}
```

#### `init_project`
```json
{
  "name": "init_project",
  "description": "Create or retrieve a project with its own isolated knowledge graph namespace. Idempotent: safe to call multiple times with the same name. Returns existing project if name already exists.",
  "inputSchema": {
    "type": "object",
    "required": ["name", "description"],
    "properties": {
      "name": {
        "type": "string",
        "minLength": 1,
        "maxLength": 128,
        "description": "Human-readable project name. Used to generate the deterministic project_id slug."
      },
      "description": {
        "type": "string",
        "minLength": 1,
        "maxLength": 500,
        "description": "Brief project description."
      },
      "scan_repo": {
        "type": "boolean",
        "default": false,
        "description": "Whether to scan a directory for initial context (reads config files, README, folder structure)."
      },
      "repo_path": {
        "type": "string",
        "description": "Path to repo root. Defaults to current working directory if scan_repo=true and omitted."
      }
    }
  }
}
```

### REST Endpoints

```
GET  /api/health                         → { status, falkordb_connected, projects_count }
GET  /api/projects                       → [ { project_id, name, insights_count, created_at } ]
GET  /api/projects/{id}                  → { project_id, name, description, stats }
GET  /api/projects/{id}/graph            → { nodes: [...], edges: [...] }
GET  /api/projects/{id}/insights         → { items: [...], total, page }
GET  /api/projects/{id}/timeline         → [ { timestamp, type, content } ]
```

---

## 12. Success Criteria

### MVP Success Definition
A developer can install the system in under 5 minutes and experience measurable context continuity across Claude Code sessions.

### Functional Requirements
- ✅ `prime()` returns coherent briefing from previously stored knowledge
- ✅ `remember()` stores knowledge with automatic entity/relationship extraction
- ✅ `recall()` returns relevant results within 500ms
- ✅ `init_project()` creates isolated project namespaces
- ✅ Knowledge persists across Claude Code session restarts
- ✅ Agent does not repeat approaches stored as `category: "error"`
- ✅ Multiple projects are fully isolated
- ✅ Repo scan correctly identifies tech stack from config files
- ✅ REST API returns valid graph data for dashboard consumption

### Quality Indicators
- Setup time: **under 5 minutes**
- `prime()` latency: **under 2 seconds**
- `recall()` latency: **under 500ms**
- `remember()` sync response: **under 200ms**
- Briefing token budget: **300–400 tokens**

---

## 13. Implementation Phases

### Phase 1: Core MCP Server (Week 1–2)
**Goal:** Working MCP server with all 4 tools connected to Graphiti + FalkorDB.

- ✅ FastMCP server with stdio transport
- ✅ All 4 tools implemented and connected to Graphiti
- ✅ FalkorDB Docker container with volume persistence (`ports: "127.0.0.1:6379:6379"` — loopback only)
- ✅ MCP server runs on host (not in Docker)
- ✅ `.env.example` with configuration
- ✅ Basic error handling; all logs to **stderr** (never stdout in stdio mode)
- ✅ Uvicorn bound to `127.0.0.1`
- ✅ FalkorDB connection retry with exponential backoff (5 attempts, ~30s total)
- ✅ `build_indices_and_constraints()` called at startup
- ✅ SIGTERM/SIGINT graceful shutdown handler
- ✅ Background task Queue + N worker coroutines (default 4, configurable) with per-worker exception handling and graceful shutdown via sentinel pattern
- ✅ Episode status tracking: `pending | processing | complete | failed`

**Validation:** Install, connect Claude Code, init project, remember 5 insights, prime new session, recall specific knowledge.

### Phase 2: Repo Scanning + REST API (Week 2–3)
**Goal:** Repo bootstrapping and HTTP endpoints for dashboard.

- ✅ Repo scanner (config files, folders, README/docs)
- ✅ FastAPI REST endpoints for dashboard
- ✅ SSE transport option
- ✅ Configurable LLM provider switching

**Validation:** REST API returns visualizable graph data. Repo scan produces meaningful entities.

### Phase 3: Polish + Open Source Launch (Week 3–4)
**Goal:** Production-ready open-source release on PyPI.

- ✅ README with demo GIF, architecture diagram, quick start
- ✅ Example CLAUDE.md instructions
- ✅ Automated tests
- ✅ Error recovery and performance optimization
- ✅ GitHub setup (issues, contributing guide, CI)
- ✅ **PyPI publication** (`agent-harness` package)
- ✅ `pyproject.toml` console script entry point: `agent-harness = "src.server:main"`
- ✅ Verification: `uvx agent-harness --health-check` CLI command

**Validation:** New user goes from zero to working knowledge graph in under 5 minutes via `uvx agent-harness`.

### Phase 4: Dashboard Integration (Week 4–5)
**Goal:** Lovable dashboard connected to REST API.

- ✅ Lovable-built dashboard consuming REST endpoints
- ✅ Knowledge graph visualization
- ✅ Project overview, timeline, category filtering

---

## 14. Future Considerations

### Post-MVP
- Variable/custom knowledge categories
- Intelligent briefing ranking based on predicted next task
- Session-level automatic summaries
- Knowledge decay for old unused insights
- Export/import knowledge graphs as JSON

### Integrations
- Multi-agent support (Cursor, Windsurf, Copilot CLI)
- CI/CD failure integration
- IDE sidebar plugins

### Long-term
- Cross-project knowledge transfer
- Team/multi-user mode
- Auto-generated architecture documentation from graph
- Hosted cloud version

---

## 15. Risks & Mitigations

### Risk 1: Graphiti LLM Cost Accumulation
**Risk:** Entity extraction makes 3–6 LLM calls per `add_episode()` invocation. With intensive usage (20+ `remember()` calls/day), costs could reach $2–5/day with gpt-4.1-mini, higher with more capable models.
**Mitigation:** Document costs transparently. Support Ollama as free alternative. Consider batching episodes. Default to gpt-4.1-mini (efficient and cheap).

### Risk 2: Knowledge Quality Depends on Input
**Risk:** Vague `remember()` content produces low-quality graph entities.
**Mitigation:** Well-crafted CLAUDE.md with concrete examples of good vs. bad input. Category-specific guidance. Min-length validation (10 chars) rejects trivially empty calls.

### Risk 3: FalkorDB SSPL Licensing Perception
**Risk:** SSPL is not OSI-approved; some users may object.
**Mitigation:** SSPL only restricts managed-service resale — irrelevant for self-hosting. Document clearly. Architecture supports backend swapping (Neo4j, Apache AGE).

### Risk 4: Context Window Pollution
**Risk:** Large `prime()`/`recall()` outputs consume too many context tokens.
**Mitigation:** Hard caps (400/500 tokens). Configurable limits. Relevance-based prioritization.

### Risk 5: Async Extraction Race Condition
**Risk:** `recall()` called immediately after `remember()` may miss unextracted knowledge.
**Mitigation:** `recall()` searches both graph nodes AND raw episode text. Unprocessed episodes always findable via full-text.

### Risk 6: Background Task Data Loss on Abrupt Kill
**Risk:** If the MCP server process is killed without SIGTERM (e.g., `kill -9`), in-flight background extraction tasks are lost. The graph may be incomplete.
**Mitigation:** Raw episode text is always persisted synchronously before spawning the background task — the user's knowledge is never lost, only graph enrichment may be incomplete. SIGTERM handler awaits tasks with 30s timeout for graceful shutdown. On next startup, episodes with `status=pending/processing` can be re-queued.

### Risk 7: Developer Deploys MCP Server Inside Docker
**Risk:** Some developers may instinctively try to run the MCP server in Docker (e.g., adding it to `docker-compose.yml`). This is incompatible with stdio transport — Claude Code must spawn the MCP server as a direct child process.
**Mitigation:** README and setup docs prominently document Pattern A (host process only). `docker-compose.yml` only contains FalkorDB. Explicit warning in setup guide.

---

## 16. Appendix

### Key Dependencies

| Dependency | License | Purpose |
|---|---|---|
| graphiti-core | Apache 2.0 | Temporal knowledge graph engine — **[VERIFY latest version on PyPI]** |
| FalkorDB | SSPL | Graph + vector database |
| FastMCP | MIT | MCP server framework (pin to major version) |
| FastAPI | MIT | REST API framework |
| OpenAI SDK | MIT | LLM + embedding API client |
| Pydantic v2 | MIT | Data validation |
| anyio | MIT | Async runtime compatibility layer |

### Example CLAUDE.md Instructions

```markdown
## Knowledge Graph Integration

You have access to a persistent knowledge graph via MCP. Follow these rules:

1. **At the start of every session**, call `prime("my-saas-app")` to load project context.
   *(Replace `my-saas-app` with the project_id returned by init_project)*
2. **Use `remember()`** whenever you:
   - Discover something new about an API, library, or system behavior
   - Try an approach that fails (with WHY it failed)
   - Make an architectural decision (with the alternatives considered)
   - Receive a new goal or requirement from the user
   - Complete a significant implementation
3. **Use `recall()`** when unsure if something was already tried or decided.
4. **Categories:** Always specify one of: decision, insight, error, goal, architecture.
5. **Be specific:** "Stripe webhook signature fails without ngrok in dev" is better
   than "webhook issue".

**After running `init_project`:** Replace the project_id placeholder above with the
slug returned in the response (e.g., `"my-saas-app"`). This slug never changes.
```

### Claude Code `.mcp.json` Configuration

Add this to your Claude Code MCP configuration file (`~/.claude/.mcp.json` or project-level `.mcp.json`):

```json
{
  "mcpServers": {
    "agent-harness": {
      "type": "stdio",
      "command": "uvx",
      "args": ["agent-harness"],
      "env": {
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6379",
        "LLM_PROVIDER": "openai",
        "LLM_API_KEY": "sk-your-key-here",
        "LLM_MODEL": "gpt-4.1-mini",
        "OPENAI_API_KEY": "sk-your-key-here"
      }
    }
  }
}
```

> **Note:** MCP server env vars are NOT inherited from your shell. All required config must be specified in this `env` block. Alternatively, use `MCP_ENV_FILE` to point to an absolute path of your `.env` file.

### FalkorDB Docker Configuration

`docker-compose.yml` (FalkorDB only — MCP server is NOT containerized):

```yaml
services:
  falkordb:
    image: falkordb/falkordb:latest  # Pin to specific version in production
    container_name: agent-harness-falkordb
    restart: unless-stopped
    ports:
      - "127.0.0.1:6379:6379"   # loopback only — required on Linux for host→container access
    volumes:
      - falkordb_data:/data       # /data is mandatory persistence path for FalkorDB
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "6379", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 10s

volumes:
  falkordb_data:
    name: agent-harness-falkordb-data   # Predictable name for backup/restore
```

### First-Run Setup Sequence

Zero-to-working steps:

1. **Install prerequisites:** Docker Desktop, Python 3.11+, `uv` (`pip install uv`)
2. **Get docker-compose.yml:** Download from GitHub releases or copy from repo
3. **Start FalkorDB:** `docker compose up -d`
4. **Verify FalkorDB health:** `docker compose ps` → status should be `healthy`
5. **Configure:** Edit `~/.claude/.mcp.json` to add the `agent-harness` server (see config above). Add your API keys.
6. **Restart Claude Code** to load the new MCP server
7. **Initialize project:** In a Claude Code session, ask Claude to call `init_project` with your project name
8. **Note the returned `project_id`:** Hardcode it in your project's `CLAUDE.md` as shown in the CLAUDE.md template above
9. **Verify end-to-end:** Ask Claude to call `prime("your-project-id")` — should return empty-state message for a new project

### Backup and Restore Procedure

**Backup FalkorDB data:**
```bash
# Stop FalkorDB first to ensure consistent snapshot
docker compose stop falkordb

# Export the named volume
docker run --rm \
  -v agent-harness-falkordb-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/falkordb-backup-$(date +%Y%m%d).tar.gz /data

# Restart FalkorDB
docker compose start falkordb
```

**Restore FalkorDB data:**
```bash
docker compose stop falkordb

docker run --rm \
  -v agent-harness-falkordb-data:/data \
  -v $(pwd):/backup \
  alpine sh -c "rm -rf /data/* && tar xzf /backup/falkordb-backup-YYYYMMDD.tar.gz -C /"

docker compose start falkordb
```

**Backup SQLite (project metadata):**
```bash
# SQLite file location (default)
cp ~/.agent-harness/projects.db ~/.agent-harness/projects.db.bak
```

### Upgrade Procedure

**Upgrade MCP server** (PyPI package):
```bash
uvx --reinstall agent-harness
# Then restart Claude Code to reload the updated server
```

**Upgrade FalkorDB** (Docker image):
```bash
docker compose pull falkordb
docker compose up -d falkordb
# Volume data is preserved across image upgrades
```

### References
- [Graphiti by Zep](https://github.com/getzep/graphiti) — Temporal knowledge graph framework
- [FalkorDB](https://www.falkordb.com/) — Graph database with vector search
- [MCP Specification](https://modelcontextprotocol.io/) — Model Context Protocol standard
- [Archon](https://github.com/coleam00/Archon) — Reference for task-driven AI coding workflows
