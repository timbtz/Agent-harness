# Agent Harness

**Persistent knowledge graph memory for AI coding agents.**

Agent Harness is an open-source MCP server that gives Claude Code a persistent memory across sessions. It captures decisions, insights, errors, and architectural choices as a temporal knowledge graph — so your agent starts every session already knowing what happened in previous ones.

---

## The Problem

Claude Code forgets everything between sessions. Every new conversation starts from zero:
- "Why did we choose JWT over sessions again?"
- "We already tried that approach — it failed because of X"
- "What's the current auth architecture?"

Agent Harness solves this with two primitives: **`remember`** and **`recall`**.

---

## How It Works

```
Claude Code ──────────────────────────────────────────────────────────────────
    │
    ├─ remember("we chose JWT because session storage was too slow", "decision")
    │       └─→ stored immediately in SQLite
    │           └─→ Graphiti extracts entities/relationships in background
    │
    ├─ recall("why did we choose JWT?")
    │       └─→ hybrid search (cosine + BM25 + graph traversal)
    │           └─→ returns relevant facts from the knowledge graph
    │
    └─ prime("my-project")  ← call this at session start
            └─→ compressed briefing: decisions, pitfalls, last session
```

---

## Quickstart

### Prerequisites

- Docker (for FalkorDB)
- Python 3.11+
- An OpenAI API key (for embeddings + entity extraction)

### 1. Start FalkorDB

```bash
docker compose up -d
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set:
# LLM_API_KEY=sk-...         (your OpenAI key)
# OPENAI_API_KEY=sk-...      (same key, used for embeddings)
```

### 3. Add to Claude Code

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "agent-harness": {
      "command": "uvx",
      "args": ["agent-harness"],
      "env": {
        "LLM_PROVIDER": "openai",
        "LLM_API_KEY": "sk-...",
        "LLM_MODEL": "gpt-4.1-mini",
        "OPENAI_API_KEY": "sk-...",
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6379"
      }
    }
  }
}
```

Or use `MCP_ENV_FILE` to point at your `.env` file:

```json
{
  "mcpServers": {
    "agent-harness": {
      "command": "uvx",
      "args": ["agent-harness"],
      "env": {
        "MCP_ENV_FILE": "/absolute/path/to/.env"
      }
    }
  }
}
```

### 4. Initialize your project

In Claude Code:
```
init_project("My App", "Next.js SaaS with Supabase and Stripe", scan_repo=True)
```

Returns: `{ "project_id": "my-app", "status": "created", "scan_repo_queued": true }`

Add to your project's CLAUDE.md:
```markdown
At session start, always call: prime("my-app")
```

---

## MCP Tools Reference

### `prime(project_id)` → str

Call at the **start of every session**. Returns a compressed briefing in under 400 tokens. Superseded facts are marked with `~~strikethrough~~ (superseded)` so the agent can distinguish current state from historical context.

```
## Project: My App
**Stack:** Next.js SaaS with Supabase and Stripe
**Status:** 23 insights stored

### Key Decisions
- Auth: Custom JWT (Supabase RLS incompatible with service-role)
- Payments: Stripe Payment Intents (Checkout v2 abandoned — no webhook reliability)

### Known Pitfalls
- Supabase Edge Functions timeout after 10s for large queries

### Last Session
- [decision] Chose pgBouncer for connection pooling
- [error] Stripe webhook verification fails in dev without ngrok
- [architecture] Moved to edge middleware for auth
```

---

### `remember(project_id, content, category)` → dict

Store knowledge. Returns immediately — Graphiti extraction runs async in background.

| Parameter | Type | Constraints |
|-----------|------|-------------|
| `project_id` | str | `^[a-z0-9-]{1,64}$` |
| `content` | str | 10–2000 chars |
| `category` | enum | `decision` \| `insight` \| `error` \| `goal` \| `architecture` |

**Categories:**
- `decision` — choice with rationale ("chose Redis over Memcached because...")
- `insight` — new understanding of an API/library/system
- `error` — something tried and failed (with why)
- `goal` — requirement or constraint from the user
- `architecture` — system structure, component relationships

**Response:**
```json
{
  "status": "stored",
  "episode_id": "ep_a3f9c12b",
  "category": "decision",
  "processing": "async — graph extraction in progress"
}
```

---

### `recall(project_id, query)` → str

Search the knowledge graph. No LLM calls during retrieval — P95 latency ~300ms.

| Parameter | Type | Constraints |
|-----------|------|-------------|
| `project_id` | str | `^[a-z0-9-]{1,64}$` |
| `query` | str | 3–500 chars, natural language or keywords |

Output capped at 300–500 tokens. Falls back to raw episode keyword search when Graphiti extraction is still pending, processing, or has failed — so knowledge is never silently lost.

---

### `init_project(name, description, scan_repo=False, repo_path=None)` → dict

Create or retrieve a project namespace. **Idempotent** — safe to call multiple times.

- `project_id` auto-generated: `"My SaaS App"` → `"my-saas-app"`
- `scan_repo=True` reads config files, README, docs, and folder structure from `repo_path` and enqueues them as `architecture` episodes
- Only scans **new** projects (not existing ones)

---

### `forget(project_id, episode_id)` → dict

Delete a stored knowledge item by its episode ID.

- `episode_id` is returned by `remember()` in the `episode_id` field
- Removes the SQLite record and excludes the episode from all future keyword fallback searches
- Graph entities already extracted into FalkorDB may persist (noted in the response)

**Response:**
```json
{
  "deleted": true,
  "episode_id": "ep_a3f9c12b",
  "note": "SQLite record removed. Graph entities from extraction may persist."
}
```

Error if `project_id` not found or `episode_id` not found in that project.

---

## REST API (Dashboard)

The server exposes a REST API on `http://localhost:8080` for the dashboard.

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Server health + FalkorDB connection status |
| `GET /api/projects` | List all projects |
| `GET /api/projects/{id}` | Get project details |
| `DELETE /api/projects/{id}` | Delete a project and all its episodes |
| `GET /api/projects/{id}/graph` | Knowledge graph nodes + edges |
| `GET /api/projects/{id}/insights` | Paginated episodes (`?page=1&limit=20&category=decision`) |
| `GET /api/projects/{id}/timeline` | Episodes in chronological order |
| `POST /api/projects/{id}/search` | Search knowledge (graph + raw fallback) — body: `{"query": "...", "limit": 10}` |
| `DELETE /api/projects/{id}/episodes/{ep_id}` | Delete a single episode |

---

## Configuration

Full config via environment variables (or `.env` file):

```env
# Required
LLM_PROVIDER=openai              # openai | anthropic | ollama
LLM_API_KEY=sk-...               # API key for entity extraction
LLM_MODEL=gpt-4.1-mini           # Model for Graphiti extraction
OPENAI_API_KEY=sk-...            # For text-embedding-3-small (always required)

# Optional (defaults shown)
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
HTTP_PORT=8080
LOG_LEVEL=info
SQLITE_PATH=~/.agent-harness/projects.db
EXTRACTION_WORKERS=4             # Concurrent Graphiti extraction workers
MCP_ENV_FILE=/absolute/path/.env # Load config from an explicit .env file
```

> **Note:** MCP server processes do NOT inherit your shell environment. Use `MCP_ENV_FILE` or list all vars in the `env` block of `mcp.json`.

---

## Architecture

```
Claude Code → stdio → FastMCP → tools/ → services/ → Graphiti → FalkorDB (Docker)
                                                     → SQLite (project metadata)
Dashboard   → HTTP  → FastAPI → routes.py → (same services)
```

Both transports run in the same process via `asyncio.gather()`. FalkorDB and Uvicorn both bind to `127.0.0.1` only — not externally exposed.

### Background Extraction

`remember()` stores raw episode text synchronously (instant response), then enqueues Graphiti extraction to a worker pool (default: 4 workers):

```
remember() called
    ├─ SYNC: store raw episode → status=pending → return confirmation
    └─ QUEUE: extraction_queue.put(episode_id, content, category, project_id)
                ↓ consumed by N worker coroutines
                  ├─ status=processing → LLM entity extraction (4-10 calls)
                  ├─ success → status=complete (graph nodes/edges in FalkorDB)
                  └─ failure → status=failed (raw text still searchable)
```

Episodes with `status=pending` or `status=processing` at shutdown are automatically re-queued when the server restarts, so no knowledge is lost across restarts.

### Project Isolation

Each project has its own FalkorDB graph. `KnowledgeService` translates `project_id` to a Graphiti `group_id` by replacing hyphens with underscores (`my-app` → `my_app`) — required because RediSearch (FalkorDB's full-text engine) treats hyphens as NOT operators in query strings. The FalkorDB graph name itself keeps the original hyphenated `project_id`. Cross-project contamination is prevented at the search layer by always filtering on `group_id`.

---

## Development

```bash
# Clone + install
git clone https://github.com/your-org/agent-harness
cd agent-harness
uv sync --dev

# Start FalkorDB
docker compose up -d

# Run server
uv run python -m src.server

# Run tests (no FalkorDB required)
uv run python -m pytest tests/ -v

# Lint
uv run ruff check src/
```

### Test Coverage

The test suite (161 tests) covers all components without requiring live services:
- All 5 MCP tool handlers (validation, success/error paths, queue behavior)
- ProjectsService CRUD (SQLite with real temp databases)
- KnowledgeService (mocked Graphiti and FalkorDB)
- FastAPI REST routes (httpx ASGI transport)
- MCP tool registration (parameter schemas, required fields)
- Repo scanner (file reading, truncation, folder tree)
- Integration test scaffold (`tests/integration/`) for live-stack validation with real FalkorDB

---

## Security

- FalkorDB binds to `127.0.0.1:6379` only (not `0.0.0.0`)
- Uvicorn binds to `127.0.0.1:8080` only
- `.env` is in `.gitignore` — never committed
- MCP server runs on host only (never in Docker)

---

## License

MIT
