# Phase 3 — Testing Suite & README

> **Status:** Complete (March 2026)
> **Builds on:** Phase 1 (core MCP server), Phase 2 (repo scanner + dashboard endpoints)

---

## Objectives

1. **README.md** — Full user-facing documentation for PyPI / GitHub
2. **Comprehensive test suite** — Unit tests for all components with no external dependencies
3. **Phase 4 plan** — Roadmap for PyPI publish, Lovable dashboard, and E2E tests

---

## Deliverables

### Test Files Added

| File | Covers |
|------|--------|
| `tests/test_projects_service_crud.py` | Full CRUD: create, get, list, count, episode lifecycle |
| `tests/test_tools_remember.py` | `remember` tool: validation, enqueue, success/error paths |
| `tests/test_tools_recall.py` | `recall` tool: graph search, raw fallback, no-results |
| `tests/test_tools_prime.py` | `prime` tool: briefing generation, empty state |
| `tests/test_tools_init_project.py` | `init_project` tool: create, idempotent, scan_repo flag |
| `tests/test_briefing.py` | `generate_briefing()`: empty/populated project output |
| `tests/test_routes.py` | All 6 FastAPI REST endpoints via httpx.AsyncClient |
| `tests/test_knowledge_service.py` | KnowledgeService: mocked Graphiti, search, add_episode |
| `tests/test_mcp_registration.py` | Tool registration: names, parameter schemas, count |

### Other Changes
- `httpx>=0.27` added to `[project.optional-dependencies.dev]` (routes testing)
- `README.md` created at project root

---

## Test Strategy

### Philosophy
- **No external service dependencies** — all tests run offline (no FalkorDB, no LLM API)
- **Real SQLite** — ProjectsService tests use real aiosqlite with `tmp_path` fixtures
- **AsyncMock for Graphiti** — KnowledgeService tests mock the Graphiti and FalkorDB layers
- **FastMCP in-process** — Tool tests use `mcp.call_tool()` for realistic end-to-end tool invocation without a running server
- **httpx ASGI transport** — Route tests use `httpx.AsyncClient(transport=ASGITransport(app))` for real HTTP semantics without binding a port

### FastMCP Test Pattern
```python
# Register tool
mcp = FastMCP("test")
make_remember(mcp, knowledge_mock, projects_svc, queue)

# Call it — ToolError raises as exception
result = await mcp.call_tool("remember", {...})
assert result.structured_content["status"] == "stored"

with pytest.raises(ToolError):
    await mcp.call_tool("remember", {"project_id": "missing", ...})
```

### What CANNOT be tested without live services (manual validation required)
- Graphiti entity extraction (requires OpenAI API + FalkorDB)
- Full `remember` → `recall` round-trip with actual graph data
- `prime` with real knowledge graph entities
- `scan_repo` → extraction → recall of scanned content
- MCP stdio protocol (requires Claude Code to launch the server)

---

## Coverage Map

```
src/
  config.py          → test_config.py (defaults, path resolution)
  models.py          → test_smoke.py (model validation)
  server.py          → test_mcp_registration.py (tool registration)
  tools/
    remember.py      → test_tools_remember.py
    recall.py        → test_tools_recall.py
    prime.py         → test_tools_prime.py
    init_project.py  → test_tools_init_project.py
  services/
    projects.py      → test_projects_service.py + test_projects_service_crud.py
    briefing.py      → test_briefing.py
    scanner.py       → test_scanner.py (existing)
    knowledge.py     → test_knowledge_service.py
  api/
    routes.py        → test_routes.py
```

---

## Key Findings (from Phase 3 implementation)

1. **FastMCP v3 `call_tool()` is the right test entry point** — propagates ToolError, returns ToolResult with `.structured_content` (dict) and `.content[0].text` (str)
2. **asyncio_mode=auto** — already set in pyproject.toml; no `@pytest.mark.asyncio` decorators needed
3. **KnowledgeService instantiation** — `create()` classmethod calls `_verify_connection()` which hits FalkorDB; tests must bypass this by instantiating directly: `KnowledgeService(settings, llm_mock, embedder_mock)` and mocking `check_connection`
4. **Route 404 pattern** — `_require_project()` helper in routes.py raises HTTPException(404) when `projects.get()` returns None; test by setting `mock_projects.get = AsyncMock(return_value=None)`

---

## Validation Commands

```bash
# Run all tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/
uv run ruff format --check src/

# No print() in src/
grep -rn "print(" src/ || echo "OK: no print() calls"

# Import sanity
uv run python3 -c "
from src.services.scanner import scan_repo
from src.services.projects import ProjectsService
from src.services.knowledge import KnowledgeService
from src.tools import register_tools
from src.api.routes import create_router
print('All imports OK')
"
```

---

## What Still Needs Manual Validation

See Phase 4 plan for the full checklist. Critical items:

1. **FalkorDB end-to-end** — start Docker, run server, call `init_project` + `remember` + `recall` via MCP
2. **Graphiti extraction** — verify episodes reach `status=complete` in SQLite after ~30s
3. **Dashboard endpoints with real data** — after storing episodes, verify `/graph`, `/insights`, `/timeline` return real content
4. **MCP stdio protocol** — add to `~/.claude/mcp.json` and verify Claude Code can call all 4 tools
5. **uvx installation** — `uvx agent-harness` installs and starts from PyPI or local build
