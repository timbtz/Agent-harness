# Agent Harness — CLAUDE.md

> AI coding agent reference for the Agent Harness project.
> Read at session start. Use `.agents/reference/` for deep dives.

---

## 1. Project Overview

**Agent Harness** is an open-source MCP server providing persistent, structured knowledge graph memory for AI coding agents (Claude Code). It captures decisions, insights, errors, and architectural choices as a temporal knowledge graph — so agents start each session already knowing what happened in previous sessions.

**4 MCP tools:** `prime` · `remember` · `recall` · `init_project`

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
│   │   └── init_project.py     # Project creation/retrieval
│   ├── services/
│   │   ├── knowledge.py        # Graphiti wrapper
│   │   ├── briefing.py         # Briefing generation for prime()
│   │   ├── scanner.py          # Repo structure scanning
│   │   └── projects.py         # SQLite project metadata
│   └── api/routes.py           # REST endpoints for dashboard
├── templates/
│   └── claude_md_instructions.md
└── tests/
```

---

## 5. Architecture

### Deployment Topology

- **FalkorDB:** Docker container only — port NOT exposed externally
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
3. **Namespace isolation** — each project = its own FalkorDB graph via Graphiti `group_id = project_id`
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
    └─ ASYNC: asyncio.create_task(graphiti.add_episode(...))
                  ├─ status=processing → LLM extraction (4-10 calls)
                  ├─ success → status=complete (graph nodes/edges in FalkorDB)
                  └─ failure → status=failed (raw text still searchable)

Concurrency limit: asyncio.Semaphore(4)  [3-5 max concurrent extractions]
Episode statuses: pending | processing | complete | failed
```

---

## 6. MCP Tools Reference

### `prime(project_id: str) → str`
First call at session start. Returns compressed project briefing (≤400 tokens).
```
## Project: [Name]
**Stack:** Next.js, Supabase  |  **Status:** 23 insights, 2 pitfalls
### Key Decisions        → decision + architecture entities
### Known Pitfalls       → error + insight entities (negative outcomes)
### Last Session         → most recent 3-5 episodes
```
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
Hybrid search (cosine + BM25 + graph BFS, fused via RRF). Falls back to raw episodes if extraction pending.
- `query`: 3–500 chars, natural language or keywords
- Output capped at 300–500 tokens · P95 latency ~300ms (no LLM calls)

### `init_project(name, description, scan_repo=False, repo_path=None) → dict`
Create or retrieve project namespace. **Idempotent.**
- `project_id` auto-generated: `"My SaaS App"` → `"my-saas-app"` (pattern `^[a-z0-9-]{1,64}$`)
- `scan_repo=True` reads: `package.json`, `pyproject.toml`, `docker-compose.yml`, folder structure (2 levels), `README.md`, `docs/*.md`
- Returns: `{"project_id":"...","status":"created"|"existing"}`

---

## 7. Code Patterns

**Async-first:** All tool handlers and service methods must be `async def`.

**Pydantic Settings** in `src/config.py` for all env vars — never hardcode values.

**Logging to stderr only:**
```python
logging.basicConfig(level=logging.INFO, stream=sys.stderr, ...)
logger = logging.getLogger(__name__)  # Use in all modules
```

**Background tasks with semaphore:**
```python
_background_tasks: set = set()
_sem = asyncio.Semaphore(4)

async def run_extraction(episode_id, content, group_id):
    async with _sem:
        try:
            await update_status(episode_id, "processing")
            await graphiti.add_episode(...)
            await update_status(episode_id, "complete")
        except Exception as e:
            logger.error(f"Extraction failed {episode_id}: {e}", exc_info=True)
            await update_status(episode_id, "failed")

task = asyncio.create_task(run_extraction(...))
_background_tasks.add(task)
task.add_done_callback(_background_tasks.discard)
```

**Slugify:**
```python
import re
def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:64]
```

**Always filter by group_id in Graphiti search:**
```python
await graphiti.search(query=q, filters=SearchFilters(group_ids=[project_id]))
```

---

## 8. Configuration (.env)

```env
# Required
LLM_PROVIDER=openai              # openai | anthropic | ollama
LLM_API_KEY=sk-...               # API key for entity extraction
LLM_MODEL=gpt-4.1-mini           # Model for Graphiti extraction
OPENAI_API_KEY=sk-...            # For text-embedding-3-small

# Optional (defaults shown)
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
MCP_TRANSPORT=stdio              # stdio | sse
HTTP_PORT=8080
LOG_LEVEL=info
SQLITE_PATH=~/.agent-harness/projects.db
UVICORN_HOST=127.0.0.1           # Do NOT change to 0.0.0.0
ALLOWED_ORIGINS=http://localhost:3000
MCP_ENV_FILE=/absolute/path/.env # Load config from explicit path
```

**Note:** MCP server processes do NOT inherit the developer's shell environment. All vars must be in the `env` block of `~/.claude/mcp.json`, or pointed to via `MCP_ENV_FILE`.

---

## 9. Critical Rules

1. **NEVER `print()` to stdout** in MCP server code — stdout IS the JSON-RPC protocol; any non-JSON output corrupts it
2. **NEVER add `ports:` to FalkorDB** in `docker-compose.yml` — Docker bridges `localhost:6379` automatically; external exposure is a security risk
3. **NEVER run the MCP server in Docker** — Claude Code requires MCP servers as direct stdio child processes
4. **ALWAYS pin FastMCP to major version** — `fastmcp>=3.0,<4.0` in `pyproject.toml`
5. **Uvicorn MUST bind to `127.0.0.1`** — never `0.0.0.0`
6. **`.env` MUST be in `.gitignore`** — only `.env.example` is committed
7. **Always pass `group_ids` filter** in Graphiti searches — prevents cross-project contamination
8. **Store `asyncio.create_task()` references** — tasks are GC'd if not referenced

---

## 10. Key Files

| File | Purpose |
|------|---------|
| `src/server.py` | Dual transport entry point, startup sequence, graceful shutdown |
| `src/config.py` | All env vars via Pydantic Settings |
| `src/models.py` | Episode (with status field), Project, SearchResult models |
| `src/tools/prime.py` | Briefing queries → ≤400 token output |
| `src/tools/remember.py` | Sync store + async extraction with semaphore |
| `src/tools/recall.py` | Hybrid search + raw episode fallback → ≤500 token output |
| `src/tools/init_project.py` | Idempotent project creation, optional repo scan |
| `src/services/knowledge.py` | Graphiti wrapper: `add_episode()`, `search()`, `build_indices()` |
| `src/services/projects.py` | SQLite CRUD for project metadata |
| `src/api/routes.py` | REST: `/api/health`, `/api/projects`, `/graph`, `/insights`, `/timeline` |
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

# No stdout in MCP server code
grep -rn "print(" src/         # Must return nothing
```
