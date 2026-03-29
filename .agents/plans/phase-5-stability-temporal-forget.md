# Feature: Phase 5 — Stability, Temporal Clarity, and forget()

The following plan should be complete, but validate documentation and codebase patterns before
implementing. Pay special attention to import paths, existing method signatures, and test
fixtures. Read every file listed in CONTEXT REFERENCES before touching it.

---

## Feature Description

Five targeted improvements that collectively make Agent Harness more reliable and useful as a
daily-driver MCP server. They are grouped into one plan because they share no new dependencies
and are all low-complexity targeted changes — ideal for a single focused implementation session.

1. **Fix test env isolation** — `test_settings_defaults` fails because `Settings()` reads the
   project `.env` file (which has `HTTP_PORT=8090`). This makes `pytest` return exit code 1,
   which will block CI pipelines.

2. **Re-queue orphaned episodes on startup** — Episodes with `status=pending` or
   `status=processing` at server shutdown are silently abandoned. They remain in SQLite forever
   as `pending` but are never extracted. Any knowledge stored immediately before a server crash
   or restart is lost.

3. **Temporal clarity in `prime`** — `prime()` currently shows both current and superseded graph
   facts together without any visual distinction. An agent reading the briefing cannot tell which
   facts are current state vs historical. The fix: filter out explicitly superseded edges
   (where Graphiti set `invalid_at`), sort remaining results by `created_at` DESC, and add a
   `~~strikethrough~~ (superseded)` marker for any superseded fact that appears as a fallback.

4. **Integration test suite** — All 129 existing tests mock Graphiti and FalkorDB. There are
   zero automated tests that exercise the live knowledge graph pipeline. Today's 20-test live
   validation was entirely manual. The integration suite codifies those scenarios so regressions
   are caught automatically.

5. **`forget()` MCP tool + REST DELETE endpoint** — No way to correct a mistakenly stored
   episode. Bad information persists until the next `remember()` overrides it (which may not
   fully overwrite graph entities). `forget()` deletes the SQLite episode record; graph entities
   derived from already-extracted episodes may persist (documented limitation).

---

## User Story

As a developer using Agent Harness across multiple coding sessions,
I want `prime()` to show clearly current vs historical facts, the server to resume extraction
after restarts without losing queued work, and the ability to delete mistakes with `forget()`,
So that the knowledge graph stays accurate and reliable without manual intervention.

---

## Problem Statement

Four reliability problems and one missing feature reduce the practical value of Agent Harness:
- `pytest` fails with a false-red exit code → blocks future CI setup
- Episodes silently lost on restart → knowledge holes that agents never notice
- Stale facts shown as current in `prime()` → agents act on wrong state
- No automated E2E test coverage → live-service regressions go undetected
- No `forget()` → wrong decisions are permanent

---

## Solution Statement

All five fixes use existing code paths and patterns. No new libraries or architectural changes.
The largest change is adding `invalid_at` to `SearchResult` (threading through 3 files), and
creating `tests/integration/` as a new directory. Everything else is additive to existing files.

---

## Feature Metadata

**Feature Type**: Bug Fix (3) + Enhancement (2)
**Estimated Complexity**: Low–Medium (no new architecture; targeted changes)
**Primary Systems Affected**:
  - `src/services/projects.py` — new methods: `get_all_orphaned_episodes`, `delete_episode`
  - `src/services/knowledge.py` — thread `invalid_at` through `SearchResult` mapping
  - `src/services/briefing.py` — temporal sorting + invalid_at filtering
  - `src/models.py` — add `invalid_at` field to `SearchResult`
  - `src/server.py` — re-queue logic at startup
  - `src/tools/forget.py` — new file
  - `src/tools/__init__.py` — register forget tool
  - `src/api/routes.py` — add DELETE endpoint
  - `tests/integration/` — new directory (3 files)
  - `tests/test_config.py` — env isolation fix
  - `tests/test_projects_service_crud.py` — new CRUD tests
  - `tests/test_knowledge_service.py` — invalid_at mapping test
  - `tests/test_briefing.py` — temporal filter + sorting tests
  - `tests/test_routes.py` — DELETE endpoint test
  - `tests/test_tools_forget.py` — new file
**Dependencies**: None new

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `src/config.py` (lines 1–48) — `Settings` class with `SettingsConfigDict(env_file=".env")`;
  the `get_settings()` function uses `@lru_cache`. The `_env_file` constructor override is key
  for test isolation.

- `src/models.py` (lines 29–34) — `SearchResult` Pydantic model. Add `invalid_at` field here
  following the same pattern as `created_at: datetime | None = None`.

- `src/services/knowledge.py` (lines 126–151) — `search()` method. Maps `EntityEdge` objects
  to `SearchResult`. Line 147: `created_at=getattr(edge, "created_at", None)` — mirror this
  pattern for `invalid_at`.

- `src/services/briefing.py` (lines 1–53) — `generate_briefing()` full file. Lines 25–26:
  calls `knowledge.search()` twice. Lines 35–47: Key Decisions + Known Pitfalls rendering loops.
  Lines 37–39 and 44–46: current label format. This is where temporal sorting + filtering goes.

- `src/services/projects.py` (lines 159–179) — `get_pending_episodes()` and
  `get_episodes_for_fallback()` methods. Mirror these patterns exactly for the two new methods:
  `get_all_orphaned_episodes()` (cross-project, no `project_id` filter) and `delete_episode()`.
  Line 238: `_row_to_episode()` helper function — use it in new query methods.

- `src/server.py` (lines 66–79) — Service initialization and worker creation. After line 79
  (worker tasks list built), insert the orphaned episode re-queue block. The `extraction_queue`
  variable is in scope at that point.

- `src/tools/__init__.py` (lines 9–23) — `register_tools()` function. Pattern:
  `make_X(mcp, services...)` calls. Add `make_forget(mcp, projects)` at line 23, after
  `make_prime`. Import at top of the function body, same as other tools.

- `src/api/routes.py` (lines 11–60) — `create_router()` function. Add the DELETE endpoint
  following the pattern of existing endpoints (lines 35–53). Use `_require_project()` helper
  (line 58) for 404 handling.

- `src/tools/remember.py` (lines 1–49) — Full file. Mirror the `make_X(mcp, ...) -> None`
  factory pattern and the `@mcp.tool async def tool_name(...)` inner function pattern for
  `forget()`. Note: `forget()` does NOT need the `extraction_queue` parameter.

- `tests/test_config.py` (lines 1–19) — Both test functions. `test_settings_defaults` needs
  `monkeypatch` fixture + `Settings(_env_file=None)`. `test_sqlite_path_resolved` is fine.

- `tests/test_projects_service_crud.py` — Full file. `_make_settings(tmp_path)` helper at
  line 7–9. Direct `ProjectsService.create(_make_settings(tmp_path))` call pattern. Use real
  SQLite via `tmp_path`. `asyncio_mode=auto` is set in `pyproject.toml:49` — no
  `@pytest.mark.asyncio` needed.

- `tests/test_briefing.py` (lines 1–157) — Full file. `_make_knowledge(search_results=[...])`,
  `_make_settings(tmp_path)` helpers. Direct `generate_briefing(project, knowledge, projects)`
  call. Tests use real SQLite for `ProjectsService` but mock `KnowledgeService`.

- `tests/test_knowledge_service.py` (lines 192–215) — Tests for `add_episode` and `search`
  sanitization. Mirror `test_add_episode_uses_sanitized_group_id` pattern for the `invalid_at`
  mapping test. The `patch.object(svc, "get_graphiti", return_value=mock_graphiti)` pattern.

- `tests/test_routes.py` — Existing REST endpoint tests. Mirror the `AsyncClient` setup
  pattern for the DELETE endpoint test.

- `pyproject.toml` (lines 48–49) — `[tool.pytest.ini_options]` section. Add `markers` entry
  here for the integration test marker.

### New Files to Create

- `src/tools/forget.py` — `make_forget(mcp, projects)` factory function with `forget` tool
- `tests/integration/__init__.py` — Empty file (marks directory as package)
- `tests/integration/conftest.py` — Skip logic + shared fixtures for live-service tests
- `tests/integration/test_e2e_full_workflow.py` — 10 E2E scenarios using real services
- `tests/test_tools_forget.py` — Unit tests for the forget tool

### Patterns to Follow

**Method factory pattern (all tools follow this):**
```python
# src/tools/forget.py — mirror src/tools/remember.py structure
def make_forget(mcp: FastMCP, projects: ProjectsService) -> None:
    @mcp.tool
    async def forget(project_id: str, episode_id: str) -> dict:
        """Tool docstring here."""
        project = await projects.get(project_id)
        if project is None:
            raise ToolError(f"Project '{project_id}' not found. Call init_project first.")
        # ... rest of implementation
```

**SQLite async CRUD pattern (mirror `get_pending_episodes` at projects.py:159):**
```python
async with aiosqlite.connect(self._db_path) as db:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT ...", (params,)) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_episode(row) for row in rows]
```

**SQLite DELETE pattern (with rowcount check):**
```python
async with aiosqlite.connect(self._db_path) as db:
    async with db.execute(
        "DELETE FROM episodes WHERE episode_id = ? AND project_id = ?",
        (episode_id, project_id),
    ) as cursor:
        await db.commit()
        return cursor.rowcount > 0
```

**Test isolation for Settings (pydantic-settings v2):**
```python
def test_settings_defaults(monkeypatch):
    # monkeypatch.delenv removes env var if set; _env_file=None disables .env loading
    monkeypatch.delenv("HTTP_PORT", raising=False)
    s = Settings(_env_file=None)
    assert s.http_port == 8080
```

**SearchResult invalid_at (mirror created_at mapping):**
```python
# In knowledge.py search()
SearchResult(
    content=edge.fact,
    score=1.0,
    source="graph",
    entity_name=edge.name,
    created_at=getattr(edge, "created_at", None),
    invalid_at=getattr(edge, "invalid_at", None),  # Same defensive getattr pattern
)
```

**Temporal sorting + filtering in briefing.py:**
```python
from datetime import datetime, timezone

def _sort_by_created(results, reverse=True):
    """Sort SearchResults by created_at, None values go last."""
    _epoch = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(results, key=lambda r: r.created_at or _epoch, reverse=reverse)

# Split current vs superseded, sort each, take current first with historical fallback
current = _sort_by_created([r for r in decisions if r.invalid_at is None])
historical = _sort_by_created([r for r in decisions if r.invalid_at is not None])
to_show = (current or historical)[:4]  # Fall back to historical if no current facts

# Render with visual marker for superseded fallback
for r in to_show:
    label = r.entity_name or ""
    content = r.content[:100]
    if r.invalid_at is not None:
        lines.append(f"- ~~{label + ': ' if label else ''}{content}~~ *(superseded)*")
    else:
        lines.append(f"- {label + ': ' if label else ''}{content}")
```

**Integration test skip pattern:**
```python
# tests/integration/conftest.py
import os
import pytest

def pytest_runtest_setup(item):
    if "integration" in item.keywords and not os.getenv("INTEGRATION_TESTS"):
        pytest.skip("Set INTEGRATION_TESTS=1 and ensure FalkorDB is running")
```

**Integration test fixture pattern:**
```python
# module-scoped to create project once per test module, not per test
@pytest_asyncio.fixture(scope="module")
async def live_services():
    settings = get_settings()
    projects = await ProjectsService.create(settings)
    knowledge = await KnowledgeService.create(settings)
    yield {"projects": projects, "knowledge": knowledge, "settings": settings}
```

---

## IMPLEMENTATION PLAN

### Phase 1: Test Isolation + Restart Resilience (Improvements 1 & 2)

Foundation work first. These changes are independent of each other and of the later phases.
Fixing test isolation restores a clean test baseline. The restart re-queue fix is in
`server.py` and `projects.py` — no other layers are affected.

### Phase 2: Temporal Clarity (Improvement 3)

Add `invalid_at` to `SearchResult` (model change) → update `knowledge.search()` (maps it) →
update `briefing.py` (uses it for filtering + sorting). These three files form a data pipeline
— implement in dependency order.

### Phase 3: `forget()` Tool (Improvement 5)

Add `delete_episode()` to `ProjectsService` → create `src/tools/forget.py` → register in
`src/tools/__init__.py` → add DELETE endpoint to `src/api/routes.py`. Tests last.

### Phase 4: Integration Test Suite (Improvement 4)

Create `tests/integration/` directory with skip infrastructure and 10 test scenarios. These
tests require live FalkorDB + API keys and are skipped by default. They are the final phase
because they test the fully improved codebase end-to-end.

---

## STEP-BY-STEP TASKS

### Task 1: FIX `tests/test_config.py` — env isolation

- **UPDATE** `tests/test_config.py` line 5: add `monkeypatch` fixture parameter
- **IMPLEMENT**:
  ```python
  def test_settings_defaults(monkeypatch):
      monkeypatch.delenv("HTTP_PORT", raising=False)
      monkeypatch.delenv("LLM_API_KEY", raising=False)
      monkeypatch.delenv("OPENAI_API_KEY", raising=False)
      s = Settings(_env_file=None)
      assert s.falkordb_host == "localhost"
      assert s.falkordb_port == 6379
      assert s.http_port == 8080
      assert s.uvicorn_host == "127.0.0.1"
      assert s.extraction_workers == 4
      assert s.llm_model == "gpt-4.1-mini"
  ```
- **GOTCHA**: `monkeypatch.delenv` must use `raising=False` because the env vars may not exist
  in all environments. Also clear `LLM_API_KEY` and `OPENAI_API_KEY` so they default to `""`
  (their defined default). Do NOT use `clear=True` on `patch.dict` — that clears everything
  including vars needed by other pytest internals.
- **GOTCHA**: `_env_file=None` is a pydantic-settings v2 constructor override that disables
  `.env` file loading for that specific instance. Do NOT call `get_settings()` (which is
  `@lru_cache`d and returns a cached instance that already read `.env`).
- **VALIDATE**: `uv run pytest tests/test_config.py -v`
  Expected: both tests pass, zero failures

---

### Task 2: ADD `get_all_orphaned_episodes()` to `src/services/projects.py`

- **ADD** a new method to `ProjectsService` after `get_episodes_for_fallback()` (after line 179)
- **IMPLEMENT**:
  ```python
  async def get_all_orphaned_episodes(self) -> list[Episode]:
      """Return all pending/processing episodes across ALL projects.

      Called at startup to re-queue episodes that were interrupted by a
      server restart. Returns oldest first (ASC) so they re-extract in
      original order.
      """
      async with aiosqlite.connect(self._db_path) as db:
          db.row_factory = aiosqlite.Row
          async with db.execute(
              "SELECT * FROM episodes WHERE status IN ('pending', 'processing') "
              "ORDER BY created_at ASC",
          ) as cursor:
              rows = await cursor.fetchall()
              return [_row_to_episode(row) for row in rows]
  ```
- **PATTERN**: Mirror `get_pending_episodes()` at lines 159–168; only difference is no
  `project_id` filter and `ASC` ordering (process oldest first on restart)
- **VALIDATE**: `uv run pytest tests/test_projects_service_crud.py -v` (existing tests still pass)

---

### Task 3: ADD startup re-queue to `src/server.py`

- **UPDATE** `src/server.py` after line 79 (after the worker tasks loop)
- **IMPLEMENT** — insert immediately after the `logger.info(f"Started {settings.extraction_workers}...")` line:
  ```python
  # Re-queue episodes orphaned by a previous restart
  orphaned = await projects.get_all_orphaned_episodes()
  if orphaned:
      for ep in orphaned:
          if ep.status == "processing":
              # Was mid-extraction when server died — reset to pending
              await projects.update_episode_status(ep.episode_id, "pending")
          await extraction_queue.put((ep.episode_id, ep.content, ep.category, ep.project_id))
      logger.info(f"Re-queued {len(orphaned)} orphaned episode(s) from previous run")
  ```
- **GOTCHA**: `extraction_queue` is defined at line 74, and `projects` is initialized at line 68.
  Both are in scope. Insert AFTER worker tasks are created (line 79) so workers are ready to
  consume the re-queued items immediately.
- **GOTCHA**: The `ep.content` and `ep.category` are available directly from the `Episode` model
  fields. Do NOT re-read from SQLite — the `get_all_orphaned_episodes()` already returns full
  Episode objects with content.
- **VALIDATE**: `uv run python3 -c "
  import asyncio
  from src.services.projects import ProjectsService
  from unittest.mock import MagicMock
  settings = MagicMock()
  settings.sqlite_path_resolved = __import__('pathlib').Path('/tmp/test_requeue.db')
  async def t():
      svc = await ProjectsService.create(settings)
      p = await svc.create_project('TestRequeue', 'desc')
      ep = await svc.create_episode(p.project_id, 'A pending episode', 'decision')
      orphaned = await svc.get_all_orphaned_episodes()
      assert len(orphaned) == 1
      assert orphaned[0].episode_id == ep.episode_id
      print('OK')
  asyncio.run(t())
  "`

---

### Task 4: ADD test for `get_all_orphaned_episodes` in `tests/test_projects_service_crud.py`

- **ADD** test at end of file
- **IMPLEMENT**:
  ```python
  async def test_get_all_orphaned_episodes_returns_pending_and_processing(tmp_path):
      svc = await ProjectsService.create(_make_settings(tmp_path))
      p1 = await svc.create_project("Project One", "desc")
      p2 = await svc.create_project("Project Two", "desc")

      ep1 = await svc.create_episode(p1.project_id, "Episode one content here", "decision")
      ep2 = await svc.create_episode(p2.project_id, "Episode two content here", "insight")
      ep3 = await svc.create_episode(p1.project_id, "Episode three content", "goal")

      # ep1 → processing (interrupted mid-extraction), ep2 → complete, ep3 → pending (default)
      await svc.update_episode_status(ep1.episode_id, "processing")
      await svc.update_episode_status(ep2.episode_id, "complete")

      orphaned = await svc.get_all_orphaned_episodes()

      assert len(orphaned) == 2
      ids = {ep.episode_id for ep in orphaned}
      assert ep1.episode_id in ids   # processing
      assert ep3.episode_id in ids   # pending
      assert ep2.episode_id not in ids  # complete — must NOT appear


  async def test_get_all_orphaned_episodes_empty_when_all_complete(tmp_path):
      svc = await ProjectsService.create(_make_settings(tmp_path))
      p = await svc.create_project("Project", "desc")
      ep = await svc.create_episode(p.project_id, "Some content here yes", "decision")
      await svc.update_episode_status(ep.episode_id, "complete")

      orphaned = await svc.get_all_orphaned_episodes()

      assert orphaned == []
  ```
- **VALIDATE**: `uv run pytest tests/test_projects_service_crud.py -v`

---

### Task 5: ADD `invalid_at` field to `SearchResult` in `src/models.py`

- **UPDATE** `src/models.py` lines 29–34 — add `invalid_at` field to `SearchResult`
- **IMPLEMENT**: Add after `created_at: datetime | None = None`:
  ```python
  invalid_at: datetime | None = None
  ```
- **PATTERN**: Identical to `created_at` — optional datetime defaulting to None
- **GOTCHA**: Do NOT add a required field (no default). Adding an optional field with default
  None is backwards-compatible — existing code that creates `SearchResult(...)` without
  `invalid_at` will continue to work.
- **VALIDATE**: `uv run python3 -c "
  from src.models import SearchResult
  r = SearchResult(content='test', score=1.0, source='graph')
  assert r.invalid_at is None
  from datetime import datetime, timezone
  r2 = SearchResult(content='x', score=0.5, source='graph', invalid_at=datetime.now(timezone.utc))
  assert r2.invalid_at is not None
  print('OK')
  "`

---

### Task 6: UPDATE `search()` in `src/services/knowledge.py` to map `invalid_at`

- **UPDATE** `src/services/knowledge.py` lines 139–149 — the `SearchResult` construction inside
  the `for edge in edges:` loop
- **IMPLEMENT**: Add `invalid_at=getattr(edge, "invalid_at", None)` to `SearchResult(...)`:
  ```python
  search_results.append(
      SearchResult(
          content=edge.fact,
          score=1.0,
          source="graph",
          entity_name=edge.name,
          created_at=getattr(edge, "created_at", None),
          invalid_at=getattr(edge, "invalid_at", None),
      )
  )
  ```
- **GOTCHA**: Use `getattr(..., None)` (defensive) — same pattern as `created_at`. The
  `EntityEdge` from Graphiti 0.28.x does have `invalid_at`, but defensive access future-proofs
  against minor API changes.
- **VALIDATE**: `uv run pytest tests/test_knowledge_service.py -v`

---

### Task 7: ADD `invalid_at` mapping test to `tests/test_knowledge_service.py`

- **ADD** one new test after `test_search_uses_sanitized_group_ids` (line 215)
- **IMPLEMENT**:
  ```python
  async def test_search_maps_invalid_at_from_edge(svc):
      """SearchResult.invalid_at is populated from edge.invalid_at (None for valid edges)."""
      from datetime import datetime, timezone

      superseded_edge = MagicMock()
      superseded_edge.fact = "Old fact that was superseded"
      superseded_edge.name = "OLD_FACT"
      superseded_edge.created_at = None
      superseded_edge.invalid_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

      valid_edge = MagicMock()
      valid_edge.fact = "Current valid fact"
      valid_edge.name = "CURRENT_FACT"
      valid_edge.created_at = None
      valid_edge.invalid_at = None

      mock_graphiti = AsyncMock()
      mock_graphiti.search = AsyncMock(return_value=[superseded_edge, valid_edge])

      with patch.object(svc, "get_graphiti", return_value=mock_graphiti):
          results = await svc.search("query", "my-project", limit=10)

      assert results[0].invalid_at is not None   # superseded
      assert results[1].invalid_at is None        # valid
  ```
- **VALIDATE**: `uv run pytest tests/test_knowledge_service.py -v`

---

### Task 8: UPDATE `src/services/briefing.py` — temporal filtering and sorting

- **UPDATE** `src/services/briefing.py` — replace the Key Decisions and Known Pitfalls
  rendering sections (lines 35–47) with the temporal-aware version
- **ADD** import at the top of the file: `from datetime import datetime, timezone`
- **ADD** a module-level helper function after the imports, before `generate_briefing`:
  ```python
  def _sort_by_recency(results):
      """Sort SearchResults newest-first; treat None created_at as oldest."""
      _epoch = datetime.min.replace(tzinfo=timezone.utc)
      return sorted(results, key=lambda r: r.created_at or _epoch, reverse=True)
  ```
- **UPDATE** the `if decisions:` block (currently lines 35–40):
  ```python
  if decisions:
      current = _sort_by_recency([r for r in decisions if r.invalid_at is None])
      historical = _sort_by_recency([r for r in decisions if r.invalid_at is not None])
      to_show = (current or historical)[:4]  # Fall back to historical if no current facts
      lines.append("### Key Decisions")
      for r in to_show:
          label = r.entity_name or ""
          content = r.content[:100]
          if r.invalid_at is not None:
              lines.append(f"- ~~{label + ': ' if label else ''}{content}~~ *(superseded)*")
          else:
              lines.append(f"- {label + ': ' if label else ''}{content}")
      lines.append("")
  ```
- **UPDATE** the `if pitfalls:` block (currently lines 42–47) with the same pattern:
  ```python
  if pitfalls:
      current_p = _sort_by_recency([r for r in pitfalls if r.invalid_at is None])
      historical_p = _sort_by_recency([r for r in pitfalls if r.invalid_at is not None])
      to_show_p = (current_p or historical_p)[:3]
      lines.append("### Known Pitfalls")
      for r in to_show_p:
          label = r.entity_name or ""
          content = r.content[:100]
          if r.invalid_at is not None:
              lines.append(f"- ~~{label + ': ' if label else ''}{content}~~ *(superseded)*")
          else:
              lines.append(f"- {label + ': ' if label else ''}{content}")
      lines.append("")
  ```
- **GOTCHA**: The `(current or historical)` pattern uses Python's truthiness: if `current` is
  an empty list (falsy), it falls back to `historical`. This ensures Key Decisions is never
  empty purely because Graphiti marked all edges as superseded.
- **GOTCHA**: Do NOT change the `### Last Session` block (lines 49–51) — it shows raw SQLite
  episodes and has no graph-derived content; temporal logic does not apply.
- **VALIDATE**: `uv run pytest tests/test_briefing.py -v`

---

### Task 9: ADD temporal briefing tests to `tests/test_briefing.py`

- **ADD** two new tests at the end of `tests/test_briefing.py`
- **IMPLEMENT**:
  ```python
  async def test_briefing_filters_superseded_facts_when_current_available(tmp_path):
      """When both current and superseded facts exist, only current appears in Key Decisions."""
      from datetime import datetime, timezone
      projects = await ProjectsService.create(_make_settings(tmp_path))
      project = await projects.create_project("Test Project", "desc")
      await projects.create_episode(project.project_id, "Some decision was captured", "decision")

      superseded = SearchResult(
          content="Old approach using PostgreSQL",
          score=0.9,
          source="graph",
          entity_name="USED",
          created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
          invalid_at=datetime(2026, 2, 1, tzinfo=timezone.utc),  # superseded
      )
      current = SearchResult(
          content="New approach using SQLite",
          score=0.8,
          source="graph",
          entity_name="NOW_USES",
          created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
          invalid_at=None,  # still valid
      )
      knowledge = _make_knowledge(search_results=[superseded, current])

      result = await generate_briefing(project, knowledge, projects)

      assert "New approach using SQLite" in result
      assert "~~" not in result   # No strikethrough when a current fact exists


  async def test_briefing_marks_superseded_as_fallback_when_no_current_exists(tmp_path):
      """When all search results are superseded, shows them with strikethrough marker."""
      from datetime import datetime, timezone
      projects = await ProjectsService.create(_make_settings(tmp_path))
      project = await projects.create_project("Test Project", "desc")
      await projects.create_episode(project.project_id, "Some decision was captured", "decision")

      all_superseded = SearchResult(
          content="Ancient approach no longer used",
          score=1.0,
          source="graph",
          entity_name="USED_TO_USE",
          created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
          invalid_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
      )
      knowledge = _make_knowledge(search_results=[all_superseded])

      result = await generate_briefing(project, knowledge, projects)

      # Falls back to showing superseded fact with visual marker
      assert "Ancient approach no longer used" in result
      assert "~~" in result
      assert "superseded" in result
  ```
- **IMPORTS NEEDED**: `from datetime import datetime, timezone` is already imported in
  `test_briefing_key_decisions_shows_fact_content` at line 147 — verify the import exists
  at file level (not inside a test). If it's inside a test, move it to the top of the file.
- **VALIDATE**: `uv run pytest tests/test_briefing.py -v`

---

### Task 10: ADD `delete_episode()` to `src/services/projects.py`

- **ADD** a new method to `ProjectsService` after `update_episode_status()` (after line 157)
- **IMPLEMENT**:
  ```python
  async def delete_episode(self, project_id: str, episode_id: str) -> bool:
      """Delete an episode by ID. Returns True if deleted, False if not found.

      Note: Only deletes the SQLite record. If the episode was already extracted
      into the Graphiti knowledge graph, those entities may persist in FalkorDB.
      """
      async with aiosqlite.connect(self._db_path) as db:
          async with db.execute(
              "DELETE FROM episodes WHERE episode_id = ? AND project_id = ?",
              (episode_id, project_id),
          ) as cursor:
              await db.commit()
              return cursor.rowcount > 0
  ```
- **GOTCHA**: The `AND project_id = ?` constraint is a security boundary — prevents one project
  from deleting episodes belonging to another project. Never omit it.
- **GOTCHA**: `cursor.rowcount` is only valid after `db.commit()`. The `await db.commit()` must
  come BEFORE the `return cursor.rowcount > 0` check. With `async with db.execute(...)`, the
  cursor is still accessible after `commit()` within the `with` block.
- **VALIDATE**: `uv run pytest tests/test_projects_service_crud.py -v`

---

### Task 11: ADD `delete_episode` tests to `tests/test_projects_service_crud.py`

- **ADD** two tests at end of file
- **IMPLEMENT**:
  ```python
  async def test_delete_episode_returns_true_when_found(tmp_path):
      svc = await ProjectsService.create(_make_settings(tmp_path))
      p = await svc.create_project("My Project", "desc")
      ep = await svc.create_episode(p.project_id, "Content to be deleted here", "decision")

      result = await svc.delete_episode(p.project_id, ep.episode_id)

      assert result is True
      # Episode no longer retrievable
      remaining = await svc.get_recent_episodes(p.project_id, limit=10)
      assert all(e.episode_id != ep.episode_id for e in remaining)


  async def test_delete_episode_returns_false_when_not_found(tmp_path):
      svc = await ProjectsService.create(_make_settings(tmp_path))
      p = await svc.create_project("My Project", "desc")

      result = await svc.delete_episode(p.project_id, "ep_nonexistent000")

      assert result is False


  async def test_delete_episode_cannot_delete_across_projects(tmp_path):
      """project_id boundary: cannot delete another project's episode."""
      svc = await ProjectsService.create(_make_settings(tmp_path))
      p1 = await svc.create_project("Project One", "desc")
      p2 = await svc.create_project("Project Two", "desc")
      ep = await svc.create_episode(p1.project_id, "Content in project one here", "decision")

      result = await svc.delete_episode(p2.project_id, ep.episode_id)  # wrong project_id

      assert result is False
      # Original episode still exists
      remaining = await svc.get_recent_episodes(p1.project_id, limit=10)
      assert any(e.episode_id == ep.episode_id for e in remaining)
  ```
- **VALIDATE**: `uv run pytest tests/test_projects_service_crud.py -v`

---

### Task 12: CREATE `src/tools/forget.py`

- **CREATE** new file `src/tools/forget.py`
- **IMPLEMENT**:
  ```python
  import logging

  from fastmcp import FastMCP
  from fastmcp.exceptions import ToolError

  from src.services.projects import ProjectsService

  logger = logging.getLogger(__name__)


  def make_forget(mcp: FastMCP, projects: ProjectsService) -> None:
      @mcp.tool
      async def forget(project_id: str, episode_id: str) -> dict:
          """Delete a stored knowledge item by its episode ID.

          Use this to remove incorrectly stored information. The episode_id is
          returned by remember() in the 'episode_id' field of its response.

          Note: If the episode was already extracted into the knowledge graph,
          graph entities derived from it may persist in FalkorDB. Only the
          SQLite record and future keyword fallback results are affected.
          """
          project = await projects.get(project_id)
          if project is None:
              raise ToolError(f"Project '{project_id}' not found. Call init_project first.")

          deleted = await projects.delete_episode(project_id, episode_id)
          if not deleted:
              raise ToolError(
                  f"Episode '{episode_id}' not found in project '{project_id}'. "
                  "Check the episode_id returned by remember()."
              )

          logger.info(f"Episode deleted: {episode_id} from project {project_id}")
          return {
              "deleted": True,
              "episode_id": episode_id,
              "note": "SQLite record removed. Graph entities from extraction may persist.",
          }
  ```
- **PATTERN**: Mirrors `src/tools/remember.py` structure exactly — module-level logger,
  `make_X(mcp, services) -> None` factory, inner `@mcp.tool async def` function
- **VALIDATE**: `uv run python3 -c "from src.tools.forget import make_forget; print('OK')"`

---

### Task 13: REGISTER `forget` tool in `src/tools/__init__.py`

- **UPDATE** `src/tools/__init__.py` — add import and registration call
- **IMPLEMENT**:
  ```python
  # Add to the imports block inside register_tools():
  from src.tools.forget import make_forget

  # Add as the last line before closing register_tools():
  make_forget(mcp, projects)
  ```
- **PATTERN**: Same pattern as `make_prime(mcp, knowledge, projects)` — add to the block of
  lazy imports inside `register_tools()` body (line 15–18), then call after `make_prime` (line 23)
- **GOTCHA**: `make_forget` only needs `mcp` and `projects` — it does NOT need `knowledge` or
  `extraction_queue`. Match the existing signatures in the file.
- **VALIDATE**: `uv run python3 -c "
  from fastmcp import FastMCP
  from unittest.mock import MagicMock, AsyncMock
  import asyncio
  mcp = FastMCP('test')
  knowledge = MagicMock(); knowledge.check_connection = AsyncMock(return_value=True)
  projects = MagicMock()
  queue = asyncio.Queue()
  from src.tools import register_tools
  register_tools(mcp, knowledge, projects, queue)
  print('OK')
  "`

---

### Task 14: ADD `DELETE` endpoint to `src/api/routes.py`

- **UPDATE** `src/api/routes.py` — add DELETE route inside `create_router()` after the
  `get_timeline` route (before the closing `return router` at line 55)
- **IMPLEMENT**:
  ```python
  @router.delete("/projects/{project_id}/episodes/{episode_id}")
  async def delete_episode(project_id: str, episode_id: str):
      await _require_project(project_id, projects)
      deleted = await projects.delete_episode(project_id, episode_id)
      if not deleted:
          raise HTTPException(404, detail=f"Episode '{episode_id}' not found")
      return {"deleted": True, "episode_id": episode_id}
  ```
- **PATTERN**: Mirrors `get_graph` route (lines 35–38) — call `_require_project` helper for
  project 404, then call service method, then raise HTTPException for resource-not-found
- **VALIDATE**: `uv run pytest tests/test_routes.py -v`

---

### Task 15: ADD route test for DELETE endpoint to `tests/test_routes.py`

- **UPDATE** `tests/test_routes.py` — add test for the new DELETE endpoint
  (read the file first to understand the existing setup — `AsyncClient`, `TestClient` pattern)
- **IMPLEMENT** (mirror existing route test patterns):
  ```python
  async def test_delete_episode_success(tmp_path):
      # Setup: project + episode using real SQLite
      projects = await ProjectsService.create(_make_settings(tmp_path))
      project = await projects.create_project("Test Project", "desc")
      ep = await projects.create_episode(project.project_id, "Content to delete here now", "decision")
      knowledge = _make_knowledge()
      app = create_test_app(projects, knowledge)

      async with AsyncClient(app=app, base_url="http://test") as client:
          response = await client.delete(
              f"/api/projects/{project.project_id}/episodes/{ep.episode_id}"
          )

      assert response.status_code == 200
      assert response.json()["deleted"] is True
      assert response.json()["episode_id"] == ep.episode_id


  async def test_delete_episode_not_found(tmp_path):
      projects = await ProjectsService.create(_make_settings(tmp_path))
      await projects.create_project("Test Project", "desc")
      knowledge = _make_knowledge()
      app = create_test_app(projects, knowledge)

      async with AsyncClient(app=app, base_url="http://test") as client:
          response = await client.delete("/api/projects/test-project/episodes/ep_nonexistent")

      assert response.status_code == 404
  ```
- **GOTCHA**: Read `tests/test_routes.py` before implementing — the `create_test_app` helper
  and `_make_settings`/`_make_knowledge` patterns in that file may differ slightly from other
  test files. Use the exact pattern from `test_routes.py`, not from `test_tools_*.py`.
- **VALIDATE**: `uv run pytest tests/test_routes.py -v`

---

### Task 16: CREATE `tests/test_tools_forget.py`

- **CREATE** new file `tests/test_tools_forget.py`
- **IMPLEMENT**:
  ```python
  """Tests for the forget MCP tool."""
  import pytest
  from fastmcp import FastMCP
  from fastmcp.exceptions import ToolError

  from src.services.projects import ProjectsService
  from src.tools.forget import make_forget
  from unittest.mock import MagicMock


  def _make_settings(tmp_path):
      settings = MagicMock()
      settings.sqlite_path_resolved = tmp_path / "test.db"
      return settings


  async def _setup(tmp_path):
      projects = await ProjectsService.create(_make_settings(tmp_path))
      await projects.create_project("Test Project", "desc")
      mcp = FastMCP("test")
      make_forget(mcp, projects)
      return mcp, projects


  async def test_forget_deletes_existing_episode(tmp_path):
      mcp, projects = await _setup(tmp_path)
      ep = await projects.create_episode("test-project", "Content to be deleted here", "decision")

      result = await mcp.call_tool("forget", {
          "project_id": "test-project",
          "episode_id": ep.episode_id,
      })

      assert result.content[0].text  # response is JSON string — check non-empty
      import json
      data = json.loads(result.content[0].text)
      assert data["deleted"] is True
      assert data["episode_id"] == ep.episode_id


  async def test_forget_project_not_found(tmp_path):
      mcp, projects = await _setup(tmp_path)

      with pytest.raises(ToolError):
          await mcp.call_tool("forget", {
              "project_id": "nonexistent-project",
              "episode_id": "ep_abc123",
          })


  async def test_forget_episode_not_found(tmp_path):
      mcp, projects = await _setup(tmp_path)

      with pytest.raises(ToolError):
          await mcp.call_tool("forget", {
              "project_id": "test-project",
              "episode_id": "ep_doesnotexist",
          })


  async def test_forget_episode_no_longer_in_fallback(tmp_path):
      """After forget(), episode does not appear in get_episodes_for_fallback."""
      mcp, projects = await _setup(tmp_path)
      ep = await projects.create_episode("test-project", "Redis was chosen for caching layer", "architecture")

      await mcp.call_tool("forget", {
          "project_id": "test-project",
          "episode_id": ep.episode_id,
      })

      remaining = await projects.get_episodes_for_fallback("test-project")
      assert all(e.episode_id != ep.episode_id for e in remaining)
  ```
- **GOTCHA**: `mcp.call_tool` returns a result where `result.content[0].text` is a JSON string
  (for dict return types). Parse with `json.loads()` to assert on specific fields.
- **VALIDATE**: `uv run pytest tests/test_tools_forget.py -v`

---

### Task 17: CREATE `tests/integration/` directory structure

- **CREATE** `tests/integration/__init__.py` — empty file
- **CREATE** `tests/integration/conftest.py`:
  ```python
  """Integration test configuration.

  These tests require live FalkorDB and a valid OpenAI API key.
  They are skipped by default unless INTEGRATION_TESTS=1 is set.

  Usage:
      INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v
  """
  import os
  import pytest
  import pytest_asyncio

  from src.config import get_settings
  from src.services.knowledge import KnowledgeService
  from src.services.projects import ProjectsService


  def pytest_runtest_setup(item):
      if "integration" in item.keywords and not os.getenv("INTEGRATION_TESTS"):
          pytest.skip(
              "Integration tests require: INTEGRATION_TESTS=1, "
              "docker compose up -d, and valid OPENAI_API_KEY"
          )


  @pytest_asyncio.fixture(scope="module")
  async def live_projects(tmp_path_factory):
      """ProjectsService backed by a real (but temp) SQLite database."""
      from unittest.mock import MagicMock
      tmp = tmp_path_factory.mktemp("integration")
      settings = MagicMock()
      settings.sqlite_path_resolved = tmp / "integration.db"
      svc = await ProjectsService.create(settings)
      return svc


  @pytest_asyncio.fixture(scope="module")
  async def live_knowledge():
      """KnowledgeService backed by real FalkorDB (requires docker compose up -d)."""
      settings = get_settings()
      svc = await KnowledgeService.create(settings)
      return svc
  ```

- **UPDATE** `pyproject.toml` `[tool.pytest.ini_options]` section — add markers:
  ```toml
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  markers = [
      "integration: marks tests requiring live FalkorDB and API keys (skip with -m 'not integration')",
  ]
  ```

- **VALIDATE**: `uv run pytest tests/ -v` (integration tests skipped, not failed)
  `uv run pytest tests/ --co | grep integration` (shows integration tests are collected)

---

### Task 18: CREATE `tests/integration/test_e2e_full_workflow.py`

- **CREATE** `tests/integration/test_e2e_full_workflow.py`
- **IMPLEMENT** 10 scenarios covering the key behaviors validated in the live test session:
  ```python
  """E2E integration tests for Agent Harness.

  These tests exercise the full stack: SQLite → Graphiti extraction → FalkorDB.
  They require live infrastructure and take 30–60 seconds to complete (graph extraction latency).

  Run with:
      INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v -s
  """
  import asyncio
  import pytest
  import pytest_asyncio
  from uuid import uuid4

  from src.services.briefing import generate_briefing
  from src.services.projects import ProjectsService


  # Unique suffix prevents interference between test runs on same DB
  RUN_ID = uuid4().hex[:8]


  @pytest.mark.integration
  async def test_project_creation_and_idempotency(live_projects):
      """init_project creates, second call returns same project."""
      pid = f"e2e-create-{RUN_ID}"
      p1 = await live_projects.create_project(f"E2E Create {RUN_ID}", "test")
      assert p1.project_id == pid

      p2 = await live_projects.get(pid)
      assert p2 is not None
      assert p2.project_id == pid
      assert p2.name == p1.name


  @pytest.mark.integration
  async def test_remember_stores_episode_immediately(live_projects):
      """remember() stores episode with status=pending before extraction completes."""
      pid = f"e2e-store-{RUN_ID}"
      await live_projects.create_project(f"E2E Store {RUN_ID}", "test")

      ep = await live_projects.create_episode(pid, "We chose FastAPI for REST because of native async support", "decision")

      assert ep.episode_id.startswith("ep_")
      assert ep.status == "pending"
      assert ep.content == "We chose FastAPI for REST because of native async support"


  @pytest.mark.integration
  async def test_recall_keyword_fallback_works_before_extraction(live_projects):
      """Keyword fallback returns episodes before graph extraction completes."""
      pid = f"e2e-fallback-{RUN_ID}"
      await live_projects.create_project(f"E2E Fallback {RUN_ID}", "test")
      await live_projects.create_episode(pid, "PostgreSQL was selected as primary database for its ACID guarantees", "decision")

      # Immediate search — should hit fallback (episode is pending)
      fallback = await live_projects.get_episodes_for_fallback(pid)
      assert any("PostgreSQL" in ep.content for ep in fallback)


  @pytest.mark.integration
  async def test_delete_episode_removes_from_fallback(live_projects):
      """forget() removes episode from SQLite and keyword fallback."""
      pid = f"e2e-forget-{RUN_ID}"
      await live_projects.create_project(f"E2E Forget {RUN_ID}", "test")
      ep = await live_projects.create_episode(pid, "Wrong information that should be deleted", "error")

      deleted = await live_projects.delete_episode(pid, ep.episode_id)
      assert deleted is True

      fallback = await live_projects.get_episodes_for_fallback(pid)
      assert all(e.episode_id != ep.episode_id for e in fallback)


  @pytest.mark.integration
  async def test_orphan_requeue_logic(live_projects):
      """get_all_orphaned_episodes returns pending + processing across all projects."""
      pid = f"e2e-orphan-{RUN_ID}"
      await live_projects.create_project(f"E2E Orphan {RUN_ID}", "test")
      ep1 = await live_projects.create_episode(pid, "Episode one orphaned pending test", "goal")
      ep2 = await live_projects.create_episode(pid, "Episode two orphaned processing test", "goal")
      await live_projects.update_episode_status(ep2.episode_id, "processing")

      orphaned = await live_projects.get_all_orphaned_episodes()
      orphan_ids = {ep.episode_id for ep in orphaned}

      assert ep1.episode_id in orphan_ids
      assert ep2.episode_id in orphan_ids


  @pytest.mark.integration
  async def test_graph_extraction_completes(live_projects, live_knowledge):
      """After extraction, episode status becomes complete and graph is populated."""
      pid = f"e2e-extract-{RUN_ID}"
      await live_projects.create_project(f"E2E Extract {RUN_ID}", "test")
      ep = await live_projects.create_episode(
          pid,
          "We chose Redis for session caching because of its sub-millisecond latency",
          "decision",
      )

      # Trigger extraction directly (simulates worker)
      gid = await live_knowledge.add_episode(ep.episode_id, ep.content, ep.category, pid)
      await live_projects.update_episode_status(ep.episode_id, "complete", gid)

      updated = await live_projects.get_episodes_for_fallback(pid)
      assert not any(e.episode_id == ep.episode_id for e in updated)  # complete = not in fallback


  @pytest.mark.integration
  async def test_graph_search_returns_results_after_extraction(live_projects, live_knowledge):
      """After extraction, graph search returns semantically relevant results."""
      pid = f"e2e-search-{RUN_ID}"
      await live_projects.create_project(f"E2E Search {RUN_ID}", "test")
      ep = await live_projects.create_episode(
          pid,
          "SQLite was selected over PostgreSQL for project metadata because it requires no deployment",
          "decision",
      )

      await live_knowledge.add_episode(ep.episode_id, ep.content, ep.category, pid)
      await asyncio.sleep(5)  # brief wait for index propagation

      results = await live_knowledge.search("database choice", pid, limit=5)
      assert len(results) > 0
      assert all(r.source == "graph" for r in results)


  @pytest.mark.integration
  async def test_cross_project_isolation(live_projects, live_knowledge):
      """Graph search for project A returns no results for project B."""
      pid_a = f"e2e-iso-a-{RUN_ID}"
      pid_b = f"e2e-iso-b-{RUN_ID}"
      await live_projects.create_project(f"E2E Iso A {RUN_ID}", "test")
      await live_projects.create_project(f"E2E Iso B {RUN_ID}", "test")

      ep = await live_projects.create_episode(
          pid_a, "Kubernetes was chosen for container orchestration in project A", "architecture"
      )
      await live_knowledge.add_episode(ep.episode_id, ep.content, ep.category, pid_a)
      await asyncio.sleep(5)

      # Search in project B — should find nothing from project A
      results_b = await live_knowledge.search("Kubernetes container orchestration", pid_b, limit=5)
      assert results_b == []


  @pytest.mark.integration
  async def test_prime_briefing_with_graph_data(live_projects, live_knowledge):
      """prime() returns structured briefing after extraction completes."""
      pid = f"e2e-prime-{RUN_ID}"
      project = await live_projects.create_project(f"E2E Prime {RUN_ID}", "Test project for prime briefing")
      ep = await live_projects.create_episode(
          pid, "JWT authentication was chosen over OAuth because we control all API clients", "decision"
      )
      await live_knowledge.add_episode(ep.episode_id, ep.content, ep.category, pid)
      await asyncio.sleep(5)

      briefing = await generate_briefing(project, live_knowledge, live_projects)

      assert "## Project:" in briefing
      assert "### Last Session" in briefing
      assert f"E2E Prime {RUN_ID}" in briefing


  @pytest.mark.integration
  async def test_temporal_transition_captured(live_projects, live_knowledge):
      """Storing two contradicting facts results in a temporal edge in the graph."""
      pid = f"e2e-temporal-{RUN_ID}"
      await live_projects.create_project(f"E2E Temporal {RUN_ID}", "test")

      ep1 = await live_projects.create_episode(
          pid, "PostgreSQL was chosen as the primary database for this project", "decision"
      )
      await live_knowledge.add_episode(ep1.episode_id, ep1.content, ep1.category, pid)

      ep2 = await live_projects.create_episode(
          pid, "Migrated away from PostgreSQL to SQLite — PostgreSQL was overkill", "decision"
      )
      await live_knowledge.add_episode(ep2.episode_id, ep2.content, ep2.category, pid)

      await asyncio.sleep(8)  # allow both extractions + entity deduplication to complete

      results = await live_knowledge.search("database migration PostgreSQL", pid, limit=10)
      assert len(results) > 0

      facts = [r.content for r in results]
      # At least one fact should reference both the original choice and the migration
      combined = " ".join(facts).lower()
      assert "postgresql" in combined
  ```
- **VALIDATE** (requires live services):
  `INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v -s`
  Without live services: `uv run pytest tests/integration/ -v` (all skipped, not failed)

---

## TESTING STRATEGY

### Unit Tests

All unit test changes use the existing pattern: real SQLite via `tmp_path`, mocked
`KnowledgeService` (AsyncMock). No live FalkorDB required. The `asyncio_mode = "auto"` in
`pyproject.toml:49` means no `@pytest.mark.asyncio` decorator is needed on any test function.

### Integration Tests

Require `INTEGRATION_TESTS=1` env var + live FalkorDB (`docker compose up -d`) + valid API
keys in `.env`. Skipped by default in all CI runs. Tests use `scope="module"` fixtures to
share service instances across tests in a module, reducing FalkorDB connection overhead. Each
test uses a unique `RUN_ID` suffix on project IDs to avoid cross-test contamination.

### Edge Cases

- `get_all_orphaned_episodes()` with empty DB → returns `[]`, re-queue loop is a no-op
- `get_all_orphaned_episodes()` with only `complete` episodes → returns `[]`
- `delete_episode()` with episode from different project → returns `False`, data intact
- `delete_episode()` on already-deleted episode → returns `False`
- `briefing.py` temporal sort with all `created_at=None` → all sort to `datetime.min`, order
  is undefined but no exception raised
- `briefing.py` temporal filter: `current=[]`, `historical=[r1, r2]` → shows historical with
  `~~strikethrough~~` marker (fallback path)

---

## VALIDATION COMMANDS

### Level 1: Lint + Type Check

```bash
cd "/root/Documents/Agent harness"
uv run ruff check src/
uv run ruff format src/ --check
```

### Level 2: Full Unit Test Suite (no live services required)

```bash
cd "/root/Documents/Agent harness"
uv run pytest tests/ -v --ignore=tests/integration/
```

Expected: all existing 129 tests pass + ~20 new tests pass. Zero failures.

### Level 3: Integration Test Suite (requires live FalkorDB)

```bash
cd "/root/Documents/Agent harness"
docker compose ps  # falkordb must show "healthy"
INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v -s
```

### Level 4: Verify MCP tool list includes `forget`

```bash
cd "/root/Documents/Agent harness"
uv run python3 -c "
import asyncio
from fastmcp import FastMCP
from unittest.mock import MagicMock, AsyncMock
import asyncio as aio

mcp = FastMCP('test')
knowledge = MagicMock()
knowledge.check_connection = AsyncMock(return_value=True)
projects = MagicMock()

from src.tools import register_tools
register_tools(mcp, knowledge, projects, aio.Queue())

async def check():
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert 'forget' in names, f'forget not in tools: {names}'
    assert 'prime' in names
    assert 'recall' in names
    assert 'remember' in names
    assert 'init_project' in names
    print(f'All 5 tools registered: {names}')

asyncio.run(check())
"
```

### Level 5: Verify no print() in src/

```bash
grep -rn "print(" src/ && echo "FAIL: print() found" || echo "OK: no print() calls"
```

---

## ACCEPTANCE CRITERIA

- [ ] `uv run pytest tests/ -v` — all tests pass (129 existing + new unit tests), zero failures
- [ ] `test_settings_defaults` passes with clean env isolation (no `.env` dependency)
- [ ] Server restart re-queues orphaned episodes: `get_all_orphaned_episodes()` returns
      pending + processing, server.py re-enqueues them at startup
- [ ] `prime()` does not show explicitly superseded facts (invalid_at IS NOT NULL) as current;
      superseded facts appear only as fallback with `~~strikethrough~~ (superseded)` markup
- [ ] `prime()` Key Decisions section shows facts sorted newest-first by `created_at`
- [ ] `forget()` MCP tool is registered and operational (5th tool alongside 4 existing ones)
- [ ] `forget()` returns `{"deleted": true, "episode_id": "..."}` for valid episode
- [ ] `forget()` raises ToolError for unknown project or unknown episode
- [ ] `DELETE /api/projects/{id}/episodes/{ep_id}` returns 200 on success, 404 on not-found
- [ ] Integration tests in `tests/integration/` are skipped (not failed) without
      `INTEGRATION_TESTS=1`
- [ ] `uv run ruff check src/` — zero linting errors

---

## COMPLETION CHECKLIST

- [ ] Task 1: test_config env isolation fixed (test passes clean)
- [ ] Task 2: `get_all_orphaned_episodes()` added to `ProjectsService`
- [ ] Task 3: Startup re-queue block added to `server.py`
- [ ] Task 4: Orphaned episodes tests added
- [ ] Task 5: `invalid_at` field added to `SearchResult` in `models.py`
- [ ] Task 6: `search()` maps `invalid_at` from edge to `SearchResult`
- [ ] Task 7: `invalid_at` mapping test added to `test_knowledge_service.py`
- [ ] Task 8: `briefing.py` temporal filtering + sorting implemented
- [ ] Task 9: Two new temporal briefing tests added
- [ ] Task 10: `delete_episode()` added to `ProjectsService`
- [ ] Task 11: Three `delete_episode` tests added
- [ ] Task 12: `src/tools/forget.py` created
- [ ] Task 13: `forget` tool registered in `src/tools/__init__.py`
- [ ] Task 14: `DELETE` endpoint added to `src/api/routes.py`
- [ ] Task 15: DELETE route test added to `test_routes.py`
- [ ] Task 16: `tests/test_tools_forget.py` created with 4 tests
- [ ] Task 17: `tests/integration/` directory created with `conftest.py` + marker in `pyproject.toml`
- [ ] Task 18: `tests/integration/test_e2e_full_workflow.py` created with 10 scenarios
- [ ] Full unit test suite passes: `uv run pytest tests/ -v --ignore=tests/integration/`
- [ ] Linting passes: `uv run ruff check src/`
- [ ] Integration tests skipped without flag: `uv run pytest tests/integration/ -v` (all skipped)
- [ ] `forget` appears in MCP tool list alongside the 4 existing tools

---

## NOTES

### Why `(current or historical)[:4]` in briefing.py

Python list truthiness: `[] or [r1, r2]` evaluates to `[r1, r2]`. This ensures Key Decisions
is never empty just because Graphiti marked all search results as superseded. The fallback
shows historical facts with a visual marker rather than an empty section.

### Why `~~strikethrough~~` and not `[HISTORICAL]`

GitHub Flavored Markdown strikethrough renders in Claude Code's output panel. It's visually
unambiguous: the fact was true, is now superseded. `[HISTORICAL]` is a text prefix that blends
with regular content. The `*(superseded)*` italics annotation makes the state change explicit
for agents that don't render markdown.

### Narrative migrations and invalid_at

As documented in the Phase 4 notes: Graphiti only sets `invalid_at` when it detects a direct
entity property contradiction. For narrative migrations ("we switched from X to Y"), both the
original decision edge and the new migration edge have `invalid_at = None`. The temporal
sorting by `created_at` DESC is the primary mitigation — newer facts appear first. This is a
Graphiti behavior constraint, not a bug in Agent Harness.

### forget() and graph persistence

`forget()` only deletes the SQLite episode record. Graph entities in FalkorDB (extracted
during the async `add_episode()` call) are NOT deleted, because:
1. Graphiti has no "delete by episode" API
2. Entity nodes may be shared across multiple episodes (entity deduplication)
3. Deleting a shared node would corrupt other projects' knowledge

The PRD explicitly accepts this limitation. Document it in the tool docstring (already
included in Task 12 implementation above) so agents understand the behavior.

### Integration test RUN_ID isolation

Each test run generates a `RUN_ID = uuid4().hex[:8]` at module load time. All project IDs
include this suffix. This prevents tests from a previous run (where cleanup was skipped due
to failure) from interfering with a fresh run. The tradeoff is test data accumulates in the
FalkorDB Docker volume — acceptable for a development environment.

### re-queue ordering: ASC not DESC

`get_all_orphaned_episodes()` returns oldest episodes first (`ORDER BY created_at ASC`).
This ensures that if an agent stored "decision A then decision B" before the crash, they
are re-extracted in the same temporal order — preserving the chronological narrative that
Graphiti uses for temporal awareness.

---

*Plan created: 2026-03-29 | Confidence: 9/10*
