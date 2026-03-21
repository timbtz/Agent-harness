# Feature: Phase 2 — Repo Scanner + Dashboard REST Endpoints

The following plan should be complete, but validate documentation and codebase patterns before implementing.
Pay special attention to imports, async patterns, and the episode content length constraint (10–2000 chars).

## Feature Description

Two parallel Phase 2 completions:

1. **`scan_repo`** — when `init_project` is called with `scan_repo=True`, scan the repo at `repo_path` for config files (`package.json`, `pyproject.toml`, `docker-compose.yml`), README, docs, and folder structure. Enqueue each discovery as an `architecture` episode. Currently stubbed with a warning.

2. **Dashboard REST endpoints** — three endpoints in `routes.py` currently call stub methods in `knowledge.py` that return empty data. Implement real data:
   - `GET /projects/{id}/graph` → nodes + edges from FalkorDB (via sync falkordb client in `asyncio.to_thread`)
   - `GET /projects/{id}/insights` → paginated SQLite episodes with category filter
   - `GET /projects/{id}/timeline` → chronological SQLite episodes

## User Story

As a developer using the Agent Harness dashboard,
I want to see my project's knowledge graph, episode history, and timeline,
So that I can inspect what my AI agent has learned across sessions.

As a developer initializing a new project,
I want the repo to be scanned for tech stack and structure automatically,
So that the agent starts the first session with existing context.

## Problem Statement

- `init_project(scan_repo=True)` silently ignores the request
- All three dashboard REST endpoints return empty data even when knowledge exists
- The `knowledge.py` stubs for `get_insights` and `get_timeline` are wrong-layered (those are SQLite queries, not graph queries)

## Solution Statement

1. Create `src/services/scanner.py` — reads repo files, truncates to fit episode limits, enqueues via `projects.create_episode()` + `extraction_queue.put()`
2. Update `make_init_project` to accept `extraction_queue`, call scanner as background task when `scan_repo=True`
3. Update `register_tools` in `__init__.py` to pass `extraction_queue` to `make_init_project`
4. Implement `get_graph_data()` in `knowledge.py` using direct FalkorDB sync client wrapped in `asyncio.to_thread()`
5. Add `get_insights()` and `get_timeline()` to `ProjectsService` (SQLite queries)
6. Update `routes.py` to call `projects.get_insights()` and `projects.get_timeline()` instead of `knowledge.*`

## Feature Metadata

**Feature Type**: Enhancement (completing stubs)
**Estimated Complexity**: Medium
**Primary Systems Affected**: `services/scanner.py` (new), `tools/init_project.py`, `tools/__init__.py`, `services/knowledge.py`, `services/projects.py`, `api/routes.py`
**Dependencies**: falkordb Python client (already installed), aiosqlite (already installed), pathlib (stdlib)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `src/tools/init_project.py` (lines 1–57) — current stub: `scan_repo=True` logs warning and is ignored; `make_init_project` signature currently only takes `mcp, projects`
- `src/tools/__init__.py` (lines 9–23) — `register_tools` passes services to tool factories; must add `extraction_queue` to `make_init_project` call
- `src/tools/remember.py` (lines 14–50) — MIRROR THIS: enqueue pattern is `projects.create_episode()` then `extraction_queue.put((ep.episode_id, content, category, project_id))`
- `src/services/projects.py` (lines 129–148) — `create_episode()` implementation; also `get_recent_episodes` and `get_pending_episodes` as patterns for new methods
- `src/services/projects.py` (lines 195–204) — `_row_to_episode()` helper; reuse in new methods
- `src/services/knowledge.py` (lines 76–87) — `check_connection()` uses sync falkordb client directly in async method; GOTCHA: blocks event loop. `get_graph_data()` should use `asyncio.to_thread()` instead
- `src/services/knowledge.py` (lines 149–158) — three stub methods to replace/augment
- `src/api/routes.py` (lines 40–54) — insight and timeline routes currently call `knowledge.*`; need to call `projects.*`
- `src/models.py` — `Episode` model (has `model_dump()` via Pydantic v2); returned by service layer

### New Files to Create

- `src/services/scanner.py` — repo scanning logic (fully async, enqueues episodes)

### Files to Modify

- `src/tools/init_project.py` — add `extraction_queue` param, call scanner
- `src/tools/__init__.py` — pass `extraction_queue` to `make_init_project`
- `src/services/knowledge.py` — implement `get_graph_data()` (real FalkorDB query); can remove `get_insights` and `get_timeline` stubs (moved to projects)
- `src/services/projects.py` — add `get_insights()` and `get_timeline()` methods
- `src/api/routes.py` — wire insights/timeline to `projects` service

### Relevant Reference Documentation — READ BEFORE IMPLEMENTING

- `.agents/reference/falkordb.md` — Cypher query patterns (lines 196–260), Python client usage (lines 88–132), temporal query patterns (lines 229–242: filter `r.invalid_at IS NULL`)
- `.agents/reference/graphiti.md` — `EntityNode` and `EntityEdge` fields (lines 239–263); `EpisodeType.text` for episode source; `add_episode()` result structure
- `.agents/reference/mcp-server.md` — `Context` injection for progress reporting in long-running `init_project` calls (lines 161–190)

### Patterns to Follow

**Async pattern for sync I/O (FalkorDB client):**
```python
# knowledge.py — check_connection uses sync falkordb in async, blocks loop
# For get_graph_data, use asyncio.to_thread() to avoid blocking
import asyncio

async def get_graph_data(self, project_id: str) -> dict:
    def _query() -> dict:
        from falkordb import FalkorDB
        db = FalkorDB(host=self._settings.falkordb_host, port=self._settings.falkordb_port)
        g = db.select_graph(project_id)
        # ... cypher queries ...
        return {"nodes": nodes, "edges": edges}
    try:
        return await asyncio.to_thread(_query)
    except Exception as e:
        logger.warning(f"Graph data query failed for {project_id}: {e}")
        return {"nodes": [], "edges": []}
```

**Episode enqueue pattern (mirror from remember.py:42–43):**
```python
episode = await projects.create_episode(project_id, content, category)
await extraction_queue.put((episode.episode_id, content, category, project_id))
```

**SQLite paginated query pattern (mirror from projects.py:174–184):**
```python
async with aiosqlite.connect(self._db_path) as db:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT ...", params) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_episode(row) for row in rows]
```

**Background task from tool handler:**
```python
# server.py worker_tasks pattern — store reference to prevent GC
task = asyncio.create_task(scan_repo(...))
# scanner runs in background; init_project returns immediately
```

**Content length constraints (enforced in remember.py but scanner bypasses MCP tool):**
- Minimum: 10 chars (always met if file has content)
- Maximum: 2000 chars → truncate at 1800 chars + `"...[truncated]"` in scanner

**Logging pattern (all files):**
```python
logger = logging.getLogger(__name__)
logger.info("scan_repo: queued episode for package.json")
logger.warning("scan_repo: path not found: /bad/path")
```

**Ignore dirs for folder tree:**
```python
_IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".next", ".nuxt"}
```

---

## IMPLEMENTATION PLAN

### Phase 1: New Service — `scanner.py`

Create the repo scanning service before wiring it into tools.

### Phase 2: Core — `ProjectsService` methods + `KnowledgeService.get_graph_data`

Add SQLite-based insight/timeline queries and the real graph data query.

### Phase 3: Integration — Wire scanner into `init_project`, update routes

Connect all pieces together.

### Phase 4: Testing & Validation

Run existing tests, verify no regressions.

---

## STEP-BY-STEP TASKS

### CREATE `src/services/scanner.py`

- **IMPLEMENT**: `async def scan_repo(repo_path, project_id, projects, extraction_queue) -> int`
  - Resolves `repo_path` via `Path(repo_path).expanduser().resolve()`
  - Returns early if path doesn't exist or isn't a directory (logs warning)
  - Reads these files in order (skip if not found): `package.json`, `pyproject.toml`, `requirements.txt`, `docker-compose.yml`, `docker-compose.yaml`, `README.md`, `README.rst`
  - Reads `docs/*.md` (up to 5 files, sorted)
  - Builds folder tree (2 levels deep, ignoring `_IGNORE_DIRS`)
  - For each piece of content: calls `projects.create_episode(project_id, content, "architecture")` then `extraction_queue.put((ep.episode_id, content, "architecture", project_id))`
  - Returns count of episodes created
- **IMPLEMENT**: `def _read_file_content(path, label) -> str | None` — reads file, truncates to 1800 chars, prepends label (`f"Repository {label} ({path.name}):\n{text}"`)
- **IMPLEMENT**: `def _build_folder_tree(root, max_depth=2) -> str | None` — walks tree, skips `_IGNORE_DIRS` and dot-dirs/files, limits to 30 entries per level, returns tree as `"Repository folder structure:\n  ...\n  src/\n    server.py\n  ..."`
- **GOTCHA**: Episode content minimum is 10 chars — check `len(content) >= 10` before enqueuing
- **GOTCHA**: `pathlib.Path.iterdir()` can raise `PermissionError` — catch and skip
- **GOTCHA**: File reads can raise `UnicodeDecodeError` — use `errors="replace"` in `path.read_text()`
- **PATTERN**: Each file becomes one episode; folder tree becomes one episode; total typically 4–10 episodes
- **IMPORTS**: `import asyncio, logging; from pathlib import Path`
- **VALIDATE**: `uv run python -c "from src.services.scanner import scan_repo; print('import ok')"`

### UPDATE `src/tools/init_project.py`

- **UPDATE**: `make_init_project` signature: add `extraction_queue: asyncio.Queue` parameter
- **ADD**: Import `asyncio` at top; import `scan_repo` from `src.services.scanner` inside the function body (lazy import to avoid circular)
- **UPDATE**: Inside `init_project` tool handler: after `existing` check and after `project = await projects.create_project(...)`, add:
  ```python
  if scan_repo:
      actual_path = repo_path or "."
      asyncio.create_task(
          _do_scan(actual_path, project_id, projects, extraction_queue)
      )
  ```
- **ADD**: Module-level `async def _do_scan(repo_path, project_id, projects, extraction_queue)` that imports and calls `scan_repo(...)`, logs result, handles exceptions
- **UPDATE**: Remove `logger.warning("scan_repo=True is not yet implemented...")` line
- **UPDATE**: Add `scan_repo_queued: bool` to the `"created"` response dict when scan is triggered
- **GOTCHA**: `asyncio.create_task()` must be called from within a running event loop — it is, since the tool handler is `async def`
- **GOTCHA**: Do NOT call `scan_repo` for `existing` projects (only new ones). The `if existing: return ...` block exits early before the scan.
- **IMPORTS**: `import asyncio` at top
- **VALIDATE**: `uv run python -c "from src.tools.init_project import make_init_project; print('import ok')"`

### UPDATE `src/tools/__init__.py`

- **UPDATE**: `make_init_project(mcp, projects)` → `make_init_project(mcp, projects, extraction_queue)`
- **VALIDATE**: `uv run python -c "from src.tools import register_tools; print('import ok')"`

### UPDATE `src/services/projects.py` — add `get_insights()` and `get_timeline()`

- **ADD**: `async def get_insights(self, project_id: str, page: int, limit: int, category: str | None) -> dict`
  ```python
  offset = (page - 1) * limit
  # Build base WHERE clause
  if category:
      count_sql = "SELECT COUNT(*) FROM episodes WHERE project_id = ? AND category = ?"
      count_params = (project_id, category)
      items_sql = "SELECT * FROM episodes WHERE project_id = ? AND category = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
      items_params = (project_id, category, limit, offset)
  else:
      count_sql = "SELECT COUNT(*) FROM episodes WHERE project_id = ?"
      count_params = (project_id,)
      items_sql = "SELECT * FROM episodes WHERE project_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
      items_params = (project_id, limit, offset)
  async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(count_sql, count_params) as cur:
          row = await cur.fetchone()
          total = row[0] if row else 0
      async with db.execute(items_sql, items_params) as cur:
          rows = await cur.fetchall()
          items = [_row_to_episode(row) for row in rows]
  return {"items": items, "total": total, "page": page, "limit": limit}
  ```
- **ADD**: `async def get_timeline(self, project_id: str, limit: int = 100) -> list`
  ```python
  async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
          "SELECT * FROM episodes WHERE project_id = ? ORDER BY created_at ASC LIMIT ?",
          (project_id, limit)
      ) as cursor:
          rows = await cursor.fetchall()
          return [_row_to_episode(row) for row in rows]
  ```
- **PATTERN**: Mirror `get_recent_episodes` (projects.py:174–184) for aiosqlite pattern
- **PATTERN**: Reuse existing `_row_to_episode()` helper (projects.py:195–204) — no new deserialization code
- **VALIDATE**: `uv run python -c "from src.services.projects import ProjectsService; print('import ok')"`

### UPDATE `src/services/knowledge.py` — implement `get_graph_data()`

- **UPDATE**: Replace stub `get_graph_data` with real implementation:
  ```python
  async def get_graph_data(self, project_id: str) -> dict:
      def _query() -> dict:
          from falkordb import FalkorDB
          db = FalkorDB(
              host=self._settings.falkordb_host,
              port=self._settings.falkordb_port,
          )
          g = db.select_graph(project_id)
          # Entity nodes
          nodes_result = g.query(
              "MATCH (n:Entity) WHERE n.group_id = $gid "
              "RETURN n.uuid, n.name, n.summary",
              params={"gid": project_id},
          )
          nodes = [
              {"id": row[0], "name": row[1], "summary": row[2]}
              for row in nodes_result.result_set
              if row[0]
          ]
          # Active edges (invalid_at IS NULL = currently valid)
          edges_result = g.query(
              "MATCH (a:Entity)-[r]->(b:Entity) "
              "WHERE r.group_id = $gid AND r.invalid_at IS NULL "
              "RETURN a.uuid, b.uuid, r.fact, type(r)",
              params={"gid": project_id},
          )
          edges = [
              {"source": row[0], "target": row[1], "fact": row[2], "type": row[3]}
              for row in edges_result.result_set
              if row[0] and row[1]
          ]
          return {"nodes": nodes, "edges": edges}

      try:
          return await asyncio.to_thread(_query)
      except Exception as e:
          logger.warning(f"Graph data query failed for {project_id}: {e}")
          return {"nodes": [], "edges": []}
  ```
- **REMOVE**: `get_insights()` and `get_timeline()` stub methods (moved to `ProjectsService`)
- **ADD**: `import asyncio` at top of file (check if already present — it is, see line 1)
- **GOTCHA**: FalkorDB Python client is **synchronous** — MUST use `asyncio.to_thread()`. Do NOT call it directly in `async def` (blocks the event loop). `check_connection()` does this wrong (acceptable for brief health check, not for data queries)
- **GOTCHA**: If the FalkorDB graph for `project_id` doesn't exist yet (no episodes processed), `select_graph()` creates it but the query returns empty results — this is fine, return `{"nodes": [], "edges": []}`
- **GOTCHA**: Graphiti uses `group_id` on both nodes and edges. The `WHERE n.group_id = $gid` filter is critical — without it, you'd get data from all projects
- **PATTERN**: See falkordb.md lines 196–260 for Cypher patterns; lines 229–242 for temporal filtering
- **VALIDATE**: `uv run python -c "from src.services.knowledge import KnowledgeService; print('import ok')"`

### UPDATE `src/api/routes.py` — wire insights/timeline to projects service

- **UPDATE**: `/projects/{project_id}/insights` route: change `await knowledge.get_insights(...)` → `await projects.get_insights(project_id, page, limit, category)`
- **UPDATE**: `/projects/{project_id}/timeline` route: change `await knowledge.get_timeline(project_id)` → `await projects.get_timeline(project_id)`
- **GOTCHA**: `get_insights` and `get_timeline` are now on `projects`, not `knowledge`. The `projects` variable is already in scope (passed to `create_router`)
- **VALIDATE**: `uv run python -c "from src.api.routes import create_router; print('import ok')"`

---

## TESTING STRATEGY

### Unit Tests (no external services needed)

Test the scanner in isolation by creating a temp directory with fake files:

```python
# tests/test_scanner.py
import asyncio
import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def fake_repo(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "test", "dependencies": {"react": "^18"}}))
    (tmp_path / "README.md").write_text("# Test Project\nA test project for unit testing.")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").touch()
    return tmp_path

@pytest.mark.asyncio
async def test_scan_repo_basic(fake_repo):
    from src.services.scanner import scan_repo
    projects_mock = AsyncMock()
    # create_episode returns an Episode-like object with episode_id
    projects_mock.create_episode.return_value = MagicMock(episode_id="ep_test001")
    queue = asyncio.Queue()
    count = await scan_repo(str(fake_repo), "test-project", projects_mock, queue)
    assert count >= 2  # package.json + README.md at minimum
    assert not queue.empty()

@pytest.mark.asyncio
async def test_scan_repo_missing_path():
    from src.services.scanner import scan_repo
    projects_mock = AsyncMock()
    queue = asyncio.Queue()
    count = await scan_repo("/nonexistent/path", "test-project", projects_mock, queue)
    assert count == 0
    assert queue.empty()
```

### Unit Tests — `ProjectsService` new methods

```python
# tests/test_projects_service.py
import pytest
import asyncio
from src.config import Settings

@pytest.mark.asyncio
async def test_get_insights_empty(tmp_path):
    from src.services.projects import ProjectsService
    from unittest.mock import MagicMock
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    svc = await ProjectsService.create(settings)
    result = await svc.get_insights("nonexistent", 1, 20, None)
    assert result == {"items": [], "total": 0, "page": 1, "limit": 20}

@pytest.mark.asyncio
async def test_get_timeline_empty(tmp_path):
    from src.services.projects import ProjectsService
    from unittest.mock import MagicMock
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    svc = await ProjectsService.create(settings)
    result = await svc.get_timeline("nonexistent")
    assert result == []
```

### Edge Cases

- `scan_repo` with `repo_path=None` or `"."` (defaults to cwd)
- `scan_repo` with a file path (not directory) — should return 0 gracefully
- `scan_repo` with a repo that has no config files — only folder tree episode created
- `get_insights` with `category` filter that returns no results
- `get_insights` page 2 when total < limit
- `get_graph_data` for project with no Graphiti data yet — should return `{"nodes": [], "edges": []}`
- `get_graph_data` when FalkorDB is down — should return empty, not raise

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
uv run ruff check src/
uv run ruff format --check src/
grep -rn "print(" src/   # Must return nothing
```

### Level 2: Unit Tests

```bash
uv run pytest tests/ -v
```

### Level 3: Import Sanity

```bash
uv run python -c "
from src.services.scanner import scan_repo
from src.services.projects import ProjectsService
from src.services.knowledge import KnowledgeService
from src.tools.init_project import make_init_project
from src.tools import register_tools
from src.api.routes import create_router
print('All imports OK')
"
```

### Level 4: Manual Integration (requires FalkorDB running)

```bash
# Start FalkorDB
docker compose up -d && docker compose ps

# Start server in background
uv run python -m src.server &
sleep 3

# Health check
curl -s http://localhost:8080/api/health | python3 -m json.tool

# Create a project
curl -s -X POST http://localhost:8080/api/projects  # Not an API endpoint — test via MCP

# Test insights endpoint (project must exist first)
curl -s "http://localhost:8080/api/projects/test-project/insights"
curl -s "http://localhost:8080/api/projects/test-project/graph"
curl -s "http://localhost:8080/api/projects/test-project/timeline"
```

---

## ACCEPTANCE CRITERIA

- [ ] `init_project(name, description, scan_repo=True, repo_path="/path")` enqueues architecture episodes for discovered files (verified via SQLite episode count increasing)
- [ ] `init_project(scan_repo=True)` returns immediately (does not block); scan runs in background
- [ ] `GET /api/projects/{id}/insights` returns `{"items": [...], "total": N, "page": 1, "limit": 20}` with real Episode data from SQLite
- [ ] `GET /api/projects/{id}/insights?category=decision` filters correctly
- [ ] `GET /api/projects/{id}/timeline` returns episodes ordered oldest-first
- [ ] `GET /api/projects/{id}/graph` returns `{"nodes": [...], "edges": [...]}` (empty lists if no Graphiti data yet — not an error)
- [ ] All existing tests pass (`uv run pytest tests/ -v`)
- [ ] Zero ruff errors (`uv run ruff check src/`)
- [ ] No `print()` calls in src/ (`grep -rn "print(" src/` returns nothing)
- [ ] `asyncio.to_thread()` used for sync FalkorDB client in `get_graph_data`

---

## COMPLETION CHECKLIST

- [ ] `src/services/scanner.py` created
- [ ] `src/tools/init_project.py` updated (extraction_queue param + scanner call)
- [ ] `src/tools/__init__.py` updated (passes extraction_queue to make_init_project)
- [ ] `src/services/projects.py` updated (get_insights + get_timeline added)
- [ ] `src/services/knowledge.py` updated (get_graph_data implemented, stubs removed)
- [ ] `src/api/routes.py` updated (insights/timeline call projects service)
- [ ] All validation commands executed successfully
- [ ] Existing tests still pass

---

## NOTES

### Why `asyncio.to_thread()` for `get_graph_data`
The falkordb Python client is synchronous (no async API). Calling it directly in an `async def` blocks the asyncio event loop for the duration of the query. `check_connection()` in knowledge.py already does this (acceptable for a brief health ping), but `get_graph_data` does multiple queries and should be non-blocking. `asyncio.to_thread()` runs the sync function in a thread pool executor.

### Why insights/timeline move to `ProjectsService`
Episodes are stored in SQLite, managed by `ProjectsService`. Querying them belongs there. `KnowledgeService` owns FalkorDB/Graphiti interactions. This maintains clean service boundaries.

### Scanner does NOT call `knowledge.add_episode()` directly
It follows the same pattern as `remember()`: `projects.create_episode()` → `extraction_queue.put()`. This means:
- The scan returns immediately
- Background workers pick up the episodes
- Status transitions: `pending` → `processing` → `complete`
- All existing graceful shutdown logic handles scanned episodes correctly

### `scan_repo` for existing projects
The `init_project` tool returns early for existing projects (`if existing: return {...}`). The scanner is only called for newly created projects. This prevents re-scanning on every `init_project` call.

### Folder tree scope
2 levels deep, skipping `_IGNORE_DIRS`. This gives the agent enough structural context (top-level dirs, key files) without overwhelming the episode with hundreds of file paths. Each level is capped at 30 entries.

### Confidence Score: 9/10
All integration points are well-understood from Phase 1 implementation. The only minor uncertainty is exact FalkorDB node/edge label names used by Graphiti (using `Entity` based on reference docs) — if wrong, `get_graph_data` returns empty rather than erroring.
