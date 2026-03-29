# Agent Harness — CLAUDE.md

> AI coding agent reference for the Agent Harness project.
> Read at session start. Use `.agents/reference/` for deep dives.

---

## 1. Project Overview

**Agent Harness** is an open-source MCP server providing persistent, structured knowledge graph memory for AI coding agents (Claude Code). It captures decisions, insights, errors, and architectural choices as a temporal knowledge graph — so agents start each session already knowing what happened in previous sessions.

**5 MCP tools:** `prime` · `remember` · `recall` · `init_project` · `forget`

**Distribution:** PyPI package (`agent-harness`) run via `uvx agent-harness`.

**Core design:** Lightweight meta-layer that coexists with native agent tools. `remember()` / `recall()` are the only primitives agents need to learn.

---

## 2. Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Primary language |
| FastMCP | `>=3.0,<4.0` | MCP server framework (stdio transport) |
| FastAPI + Uvicorn | latest | REST API, HTTP :8080 (bound to 127.0.0.1) |
| graphiti-core | `>=0.28,<1.0` | Temporal knowledge graph engine |
| FalkorDB | Docker (`falkordb/falkordb:latest`) | Graph + vector database (port 6379) |
| falkordb | `>=1.0.0,<2.0.0` | Python client |
| SQLite + aiosqlite | stdlib + pip | Project metadata storage |
| OpenAI SDK | latest | Embeddings (`text-embedding-3-small`) + default LLM |
| Anthropic SDK | latest | Alternative LLM provider |
| Pydantic v2 + pydantic-settings | latest | Models + config |
| anyio | latest | asyncio compatibility layer |

---

## 3. Commands

```bash
# Start FalkorDB
docker compose up -d

# Verify FalkorDB healthy
docker compose ps

# Verify full service (after starting MCP server)
curl http://localhost:8080/api/health
# Expected: {"status":"ok","falkordb_connected":true,"projects_count":0}

# Run MCP server (development)
uv run python -m src.server

# Run via uvx (production, after PyPI publish)
uvx agent-harness

# Tests
uv run pytest tests/ -v

# Lint + format
uv run ruff check src/ && uv run ruff format src/

# Type check
uv run mypy src/
```

---

## 4. Project Structure

```
agent-harness/
├── docker-compose.yml          # FalkorDB ONLY — MCP server runs on host
├── .env.example
├── pyproject.toml              # console_scripts: agent-harness = "src.server:main"
├── src/
│   ├── server.py               # FastMCP + FastAPI dual server + main()
│   ├── config.py               # Pydantic Settings
│   ├── models.py               # Pydantic models (Episode, Project, etc.)
│   ├── tools/
│   │   ├── prime.py            # Session briefing
│   │   ├── remember.py         # Knowledge ingestion (async extraction)
│   │   ├── recall.py           # Hybrid search
│   │   ├── init_project.py     # Project creation/retrieval
│   │   └── forget.py           # Episode deletion by ID
│   ├── services/
│   │   ├── knowledge.py        # Graphiti wrapper (per-project cache) + get_graph_data()
│   │   ├── briefing.py         # Briefing generation for prime()
│   │   ├── projects.py         # SQLite CRUD: projects + episodes, delete_project(), get_insights(), get_timeline(), get_all_orphaned_episodes()
│   │   └── scanner.py          # Repo scanner: reads config files + folder tree → architecture episodes
│   └── api/routes.py           # REST endpoints for dashboard
└── tests/
```

---

## 5. Architecture

### Deployment Topology

- **FalkorDB:** Docker container — bound to `127.0.0.1:6379` (localhost only, not externally exposed)
- **MCP server:** HOST process only via `uvx agent-harness` (stdio requires direct child of Claude Code)
- **Both FastMCP (stdio) and FastAPI (HTTP :8080) run in the same process** via `asyncio.gather()`

```
Claude Code → stdio → FastMCP → services/ → Graphiti → FalkorDB (Docker)
                                           → SQLite (project metadata)
Dashboard   → HTTP  → FastAPI → routes.py → (same services)
```

### Key Architectural Decisions

1. **Graphiti as Python library** — imported directly, no second service
2. **Async extraction** — `remember()` stores raw episode sync; Graphiti entity extraction runs async
3. **Namespace isolation** — each project = its own FalkorDB graph; `_graphiti_group_id(project_id)` converts hyphens to underscores before passing to Graphiti (RediSearch treats `-` as NOT operator); FalkorDB graph name stays hyphenated
4. **SQLite for project metadata** — stores name, description, created_at, repo_path
5. **Deterministic slugs** — `project_id` always reconstructable: `"My App"` → `"my-app"`

### Startup Sequence

1. Load + validate config (fail fast on missing `LLM_API_KEY`)
2. Initialize SQLite (create tables if not exist)
3. Connect FalkorDB — exponential backoff retry (5 attempts: 1s, 2s, 4s, 8s, 15s)
4. Call `await graphiti.build_indices_and_constraints()` — creates vector/BM25 indices
5. Register MCP tools + REST routes
6. `asyncio.gather(mcp.run_async(), uvicorn.Server(config).serve())`

### Background Task Lifecycle (remember)

```
remember() called
    ├─ SYNC: store raw episode text → status=pending → return confirmation
    └─ PUT: extraction_queue.put((episode_id, content, category, project_id))
                ↓ consumed by N worker coroutines (N = EXTRACTION_WORKERS)
                  ├─ status=processing → LLM extraction (4-10 calls)
                  ├─ success → status=complete (graph nodes/edges in FalkorDB)
                  └─ failure → status=failed (raw text still searchable)

Concurrency limit: asyncio.Queue + EXTRACTION_WORKERS workers (default 4)
Graceful shutdown: send None sentinel per worker, await queue.join()
Episode statuses: pending | processing | complete | failed
```

---

## 6. MCP Tools Reference

### `prime(project_id: str) → str`
First call at session start. Returns compressed project briefing (≤400 tokens).
```
## Project: [Name]
**Stack:** Next.js, Supabase
**Status:** 23 insights stored

### Key Decisions
- MIGRATED_AWAY_TO: We migrated from PostgreSQL to SQLite for simplicity
- AUTH_USES: JWT chosen over sessions — Supabase RLS incompatible with service role

### Known Pitfalls
- API_INCOMPATIBLE_WITH: Supabase Edge Functions timeout after 10s on large queries

### Last Session
- [decision] Chose pgBouncer for connection pooling
- [error] Stripe webhook verification fails in dev without ngrok
```
Key Decisions and Known Pitfalls show `RelationshipType: fact sentence` (both the graph edge label and the human-readable fact). If no graph results exist yet, these sections are omitted.

Error: `{"error":"project_not_found","message":"Project 'x' not found. Call init_project first."}`

### `remember(project_id, content, category) → dict`
Store knowledge. Returns immediately; Graphiti extraction async.
- `project_id`: `^[a-z0-9-]{1,64}$`
- `content`: 10–2000 chars
- `category`: `decision | insight | error | goal | architecture`

Response: `{"status":"stored","episode_id":"ep_abc123","category":"decision","processing":"async"}`

Errors: `invalid_category`, `content_too_short`, `project_not_found`

**Category guide:** `decision` = choice with rationale · `insight` = API/library behavior · `error` = tried+failed · `goal` = requirement/constraint · `architecture` = system structure

### `recall(project_id, query) → str`
Hybrid search (cosine + BM25 + graph BFS, fused via RRF). Falls back to keyword search over raw episodes when extraction is `pending`, `processing`, or `failed` — knowledge is never silently lost.
- `query`: 3–500 chars, natural language or keywords
- Output capped at 300–500 tokens · P95 latency ~300ms (no LLM calls)

### `init_project(name, description, scan_repo=False, repo_path=None) → dict`
Create or retrieve project namespace. **Idempotent.**
- `project_id` auto-generated: `"My SaaS App"` → `"my-saas-app"` (pattern `^[a-z0-9-]{1,64}$`)
- `scan_repo=True` reads (if found): `package.json`, `pyproject.toml`, `requirements.txt`, `docker-compose.yml`, `docker-compose.yaml`, `README.md`, `README.rst`, `docs/*.md` (up to 5), folder tree (2 levels deep). Each file → one `architecture` episode enqueued async. Scan only runs for **new** projects, not existing ones.
- Returns (created): `{"project_id":"...","status":"created","name":"...","description":"...","scan_repo_queued":true}`
- Returns (existing): `{"project_id":"...","status":"existing","name":"...","description":"..."}`

### `forget(project_id: str, episode_id: str) → dict`
Delete a stored knowledge item by its episode ID.
- `episode_id` is returned by `remember()` in the `episode_id` field
- Removes the SQLite record; excludes episode from all future keyword fallback searches
- Graph entities already extracted into FalkorDB may persist (Graphiti does not expose per-episode deletion)
- Returns: `{"deleted":true,"episode_id":"ep_...","note":"SQLite record removed. Graph entities from extraction may persist."}`

Errors: project not found → `ToolError`; episode not found → `ToolError`

---

## 7. Code Patterns

**Async-first:** All tool handlers and service methods must be `async def`.

**Pydantic Settings** in `src/config.py` for all env vars — never hardcode values.

**Logging to stderr only:**
```python
logging.basicConfig(level=logging.INFO, stream=sys.stderr, ...)
logger = logging.getLogger(__name__)  # Use in all modules
```

**Background extraction — Queue + worker pool (in server.py):**
```python
# server.py: create queue + start N workers at startup
extraction_queue: asyncio.Queue = asyncio.Queue()
worker_tasks = [
    asyncio.create_task(_extraction_worker(extraction_queue, knowledge, projects))
    for _ in range(settings.extraction_workers)
]

async def _extraction_worker(queue, knowledge, projects):
    while True:
        item = await queue.get()
        if item is None:   # shutdown sentinel
            queue.task_done(); return
        episode_id, content, category, project_id = item
        try:
            await projects.update_episode_status(episode_id, "processing")
            gid = await knowledge.add_episode(episode_id, content, category, project_id)
            await projects.update_episode_status(episode_id, "complete", gid)
        except Exception as e:
            logger.error(f"Extraction failed {episode_id}: {e}", exc_info=True)
            await projects.update_episode_status(episode_id, "failed")
        finally:
            queue.task_done()

# remember.py tool: just enqueue
await extraction_queue.put((episode.episode_id, content, category, project_id))
```

**Slugify:**
```python
import re
def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:64]
```

**Graphiti group_id sanitization — REQUIRED:**
```python
def _graphiti_group_id(project_id: str) -> str:
    """RediSearch treats hyphens as NOT operators. Replace with underscores."""
    return project_id.replace("-", "_")
```
This is a module-level function in `knowledge.py`. Every call to Graphiti that takes `group_id` or `group_ids` MUST use the sanitized value. The FalkorDB `database=` name keeps the original hyphenated `project_id`.

**Graphiti search — correct API (graphiti-core 0.28.x):**
```python
# search() returns list[EntityEdge] — NOT a SearchResults object
edges = await graphiti.search(
    query=q,
    group_ids=[_graphiti_group_id(project_id)],  # sanitized — hyphens → underscores
    num_results=10,                               # NOT limit=
)
# Embedder: use OpenAIEmbedderConfig (NOT EmbedderConfig — that class doesn't exist)
from graphiti_core.embedder import OpenAIEmbedder, OpenAIEmbedderConfig
# SearchFilters import: graphiti_core.search.search_filters (NOT search_config)
```

---

## 8. Configuration (.env)

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
UVICORN_HOST=127.0.0.1           # Do NOT change to 0.0.0.0
ALLOWED_ORIGINS=http://localhost:3000
EXTRACTION_WORKERS=4             # Concurrent Graphiti extraction workers
MCP_ENV_FILE=/absolute/path/.env # Load config from explicit path
```

**Note:** MCP server processes do NOT inherit the developer's shell environment. All vars must be in the `env` block of `~/.claude/mcp.json`, or pointed to via `MCP_ENV_FILE`.

---

## 9. Critical Rules

1. **NEVER `print()` to stdout** in MCP server code — stdout IS the JSON-RPC protocol; any non-JSON output corrupts it
2. **FalkorDB ports MUST bind to `127.0.0.1` only** — use `ports: "127.0.0.1:6379:6379"` in `docker-compose.yml`; on Linux Docker does NOT auto-bridge localhost without this; never bind to `0.0.0.0`
3. **NEVER run the MCP server in Docker** — Claude Code requires MCP servers as direct stdio child processes
4. **ALWAYS pin FastMCP to major version** — `fastmcp>=3.0,<4.0` in `pyproject.toml`
5. **Uvicorn MUST bind to `127.0.0.1`** — never `0.0.0.0`
6. **`.env` MUST be in `.gitignore`** — only `.env.example` is committed
7. **Always pass `group_ids` filter** in Graphiti searches — prevents cross-project contamination
8. **Store worker task references** — keep `worker_tasks` list from `asyncio.create_task()` calls so workers aren't GC'd before shutdown
9. **`asyncio.to_thread()` for FalkorDB data queries** — the `falkordb` Python client is synchronous; calling it directly in `async def` blocks the event loop. `check_connection()` (single `RETURN 1`) is exempt; all multi-query data methods (e.g. `get_graph_data`) must use `asyncio.to_thread()`
10. **`FalkorDB` is imported inside function bodies** — `KnowledgeService` uses local imports (`from falkordb import FalkorDB` inside the function). When mocking in tests, patch `"falkordb.FalkorDB"` (source module), not `"src.services.knowledge.FalkorDB"` (which has no module-level binding and raises `AttributeError`)
11. **`graphiti_core` calls `load_dotenv()` at import time** — importing any `graphiti_core` module loads the project `.env` into `os.environ`. Tests that assert on `Settings()` defaults must use `Settings(_env_file=None)` + `monkeypatch.delenv(var, raising=False)` for each env var being tested, or the `.env` values will override the expected defaults

---

## 10. Key Files

| File | Purpose |
|------|---------|
| `src/server.py` | Dual transport entry point, startup sequence, graceful shutdown |
| `src/config.py` | All env vars via Pydantic Settings |
| `src/models.py` | Episode (with status field), Project, SearchResult models |
| `src/tools/prime.py` | Briefing queries → ≤400 token output; filters `invalid_at` edges, marks superseded facts |
| `src/tools/remember.py` | Sync store → enqueue for async extraction |
| `src/tools/recall.py` | Hybrid search + raw episode fallback → ≤500 token output |
| `src/tools/init_project.py` | Idempotent project creation, optional repo scan |
| `src/tools/forget.py` | Delete episode from SQLite by ID |
| `src/services/knowledge.py` | Graphiti wrapper: `_graphiti_group_id()` sanitizer, `add_episode()`, `search()`, `get_graph_data()` (via `asyncio.to_thread`) |
| `src/services/projects.py` | SQLite CRUD: projects + episodes; `get_episodes_for_fallback()`, `get_insights()` (paginated), `get_timeline()`, `delete_project()` (cascade), `delete_episode()`, `get_all_orphaned_episodes()` |
| `src/services/scanner.py` | Repo scanner: reads config files + folder tree, enqueues `architecture` episodes |
| `src/api/routes.py` | REST: `/api/health`, `/api/projects`, `/graph`, `/insights`, `/timeline`, `/search`; `DELETE` project + episode |
| `docker-compose.yml` | FalkorDB only (no MCP server) |
| `.env.example` | Config template |
| `pyproject.toml` | `agent-harness = "src.server:main"` console script |

---

## 11. On-Demand Context

Load these when working on the relevant subsystem:

| Topic | File |
|-------|------|
| Graphiti API — `add_episode()`, `search()`, `SearchConfig`, entity models | `.agents/reference/graphiti.md` |
| FalkorDB Docker, Cypher queries, vector search, SSPL license | `.agents/reference/falkordb.md` |
| FastMCP v3 — `@mcp.tool`, `ToolError`, `Context`, logging rules | `.agents/reference/mcp-server.md` |
| FastAPI + Uvicorn dual transport, route patterns, graceful shutdown | `.agents/reference/fastapi.md` |
| Full requirements, user stories, success criteria | `.claude/PRD.md` |

---

## 12. Validation Checklist

Run before every commit:

```bash
# Infrastructure
docker compose ps              # falkordb must show "healthy"

# Service health
curl http://localhost:8080/api/health
# Must return: {"status":"ok","falkordb_connected":true}

# Tests
uv run pytest tests/ -v        # All passing

# Lint
uv run ruff check src/         # Zero errors

# No stdout in MCP server code (grep exits 1 on no match — that is the desired outcome)
grep -rn "print(" src/ && echo "FAIL: print() found" || echo "OK: no print() calls"
```
