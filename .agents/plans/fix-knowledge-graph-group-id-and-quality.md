# Feature: Fix Knowledge Graph Extraction — Hyphen Group ID, Prime Formatting, Recall Fallback

The following plan should be complete, but validate documentation and codebase patterns before
implementing. Pay attention to import paths, existing method signatures, and test fixtures.

---

## Background: What Was Discovered

This plan was produced after live MCP tool testing against a running agent-harness instance
revealed three bugs. The testing session involved 15 functional tests plus a separate graph
intelligence audit. The full transcript is at:

```
/root/.claude/projects/-root-Documents-Agent-harness/2cfd138d-38d8-4a32-be3c-8b8dc7c08755.jsonl
```

The most important finding: **the knowledge graph layer has never successfully extracted a single
episode for any real project** because every project created through `init_project` receives a
hyphenated `project_id`, and hyphens in Graphiti's `group_id` parameter crash the internal
RediSearch query with a syntax error. This means `recall` always falls back to keyword matching,
and `prime` never shows graph-derived "Key Decisions" or "Known Pitfalls" sections.

---

## Feature Description

Fix three bugs that collectively prevent the Graphiti knowledge graph layer from functioning:

1. **Critical — RediSearch syntax error from hyphens in `group_id`:** All Graphiti `add_episode()`
   calls fail for any project whose `project_id` contains a hyphen. This is every project
   created via `init_project` (the `slugify()` function intentionally generates hyphenated IDs).
   The bug is in `KnowledgeService` — it passes `project_id` directly as `group_id` to Graphiti,
   which then embeds the value into a RediSearch query string where `-` is parsed as NOT operator.

2. **Medium — `prime` shows edge relationship type names instead of fact content:** The "Key
   Decisions" and "Known Pitfalls" sections of the briefing show strings like `"MIGRATED_AWAY_TO"`
   and `"API_INCOMPATIBLE_WITH"` instead of the actual fact sentences. The bug is in
   `briefing.py:38`: `label = r.entity_name or r.content[:100]` — `r.entity_name` holds the
   Graphiti edge `name` field (the relationship type identifier), which is always truthy.

3. **Medium — `recall` fallback silently skips `failed` episodes:** When Graphiti extraction fails
   (e.g., due to the hyphen bug), episodes move to `status="failed"` and become invisible to
   both the graph search (nothing in FalkorDB) AND the raw keyword fallback (which only queries
   `pending` and `processing`). Knowledge is permanently inaccessible until re-stored.

## User Story

As a Claude Code agent using agent-harness for persistent memory,
I want `remember()` to reliably extract knowledge into the graph and `recall()`/`prime()` to
return accurate, human-readable results,
So that I can build a genuine semantic memory that persists across sessions and correctly
represents current project state including temporal changes.

## Problem Statement

The Graphiti knowledge graph is architecturally capable of semantic search, typed entity
relationships, and temporal fact tracking. None of this works in practice because `add_episode()`
always fails (Bug 1), `prime` output is unreadable when the graph does populate (Bug 2), and
`recall` silently loses knowledge when extraction fails (Bug 3).

## Solution Statement

Sanitize `group_id` in `KnowledgeService` to replace hyphens with underscores before passing to
any Graphiti API call. Fix `briefing.py` to display fact content rather than relationship type
names. Extend `ProjectsService` with a fallback query method that includes `failed` episodes, and
update `recall` to use it.

## Feature Metadata

**Feature Type**: Bug Fix (3 bugs)
**Estimated Complexity**: Low (targeted changes, no new architecture)
**Primary Systems Affected**: `src/services/knowledge.py`, `src/services/briefing.py`,
  `src/services/projects.py`, `src/tools/recall.py`
**Dependencies**: None new — all fixes use existing code paths

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `src/services/knowledge.py` (lines 104–141) — `add_episode()` and `search()` methods that pass
  `project_id` directly as `group_id`/`group_ids` to Graphiti. Also `get_graph_data()` at
  lines 143–174 which uses `project_id` in the Cypher WHERE clause for `n.group_id`.

- `src/services/briefing.py` (lines 35–47) — `generate_briefing()` constructs "Key Decisions"
  and "Known Pitfalls" sections. Line 38: `label = r.entity_name or r.content[:100]` is the bug.
  Compare with `src/tools/recall.py` lines 43–46 which does this correctly.

- `src/services/projects.py` (lines 159–168) — `get_pending_episodes()` method; only queries
  `status IN ('pending', 'processing')`. This is where the new `get_episodes_for_fallback()`
  method needs to be added, following the exact same pattern.

- `src/tools/recall.py` (lines 29–35) — calls `projects.get_pending_episodes()` for the fallback.
  Line 46: `lines.append(f"- {label + ': ' if label else ''}{snippet}")` — this is the correct
  pattern that `briefing.py` should mirror.

- `tests/test_knowledge_service.py` — Full file. Key patterns: `patch("falkordb.FalkorDB")` (NOT
  `src.services.knowledge.FalkorDB` — local import), constructing `KnowledgeService` directly
  via `KnowledgeService(settings, MagicMock(), MagicMock())` to bypass `_verify_connection`.
  `patch.object(svc, "get_graphiti", return_value=mock_graphiti)` pattern for mocking graphiti.

- `tests/test_briefing.py` — Full file. Pattern: `_make_knowledge(search_results=[...])` helper,
  direct call to `generate_briefing(project, knowledge, projects)`.

- `tests/test_tools_recall.py` — Full file. Pattern: `_setup(tmp_path, search_results=[...])`
  helper returns `(mcp, projects, knowledge)`. Tests call `mcp.call_tool("recall", {...})` and
  assert on `result.content[0].text`.

- `tests/test_projects_service_crud.py` — Read for the CRUD test pattern for SQLite queries.

### New Files to Create

None. All changes are to existing files.

### Updated Test Files

- `tests/test_knowledge_service.py` — Add tests for `_graphiti_group_id()` sanitization and
  verify that `add_episode` and `search` pass sanitized group_id to Graphiti.
- `tests/test_briefing.py` — Add test verifying that when graph results exist, the displayed text
  contains the fact content (not just the relationship type name like "MIGRATED_AWAY_TO").
- `tests/test_tools_recall.py` — Add test verifying that a `failed` episode with matching content
  appears in the fallback section of recall results.
- `tests/test_projects_service_crud.py` — Add test for `get_episodes_for_fallback()` verifying
  it returns pending + processing + failed but NOT complete.

### Patterns to Follow

**Graphiti group_id sanitization (new `_graphiti_group_id` helper):**
The helper belongs as a module-level function or static method in `knowledge.py`.
Pattern for static methods in the file: `_build_llm_client` and `_build_embedder` at lines 33–60
are `@staticmethod` methods. The new helper is simpler (pure string transform, no `settings`
arg needed) — a module-level function is fine.

**SQLite async query pattern (for new `get_episodes_for_fallback`):**
Mirror `get_pending_episodes` at `projects.py:159–168` exactly:
```python
async with aiosqlite.connect(self._db_path) as db:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT ...", (project_id,)) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_episode(row) for row in rows]
```
Use `_row_to_episode(row)` helper (defined at `projects.py:227–236`).

**Briefing label pattern:**
`recall.py:46` shows the correct approach: show BOTH the relationship label AND the content:
```python
lines.append(f"- {label + ': ' if label else ''}{snippet}")
```
where `label = r.entity_name or ""` and `snippet = r.content[:120]`.
`briefing.py` should match this pattern, not suppress the fact content.

**Test fixture for KnowledgeService:**
```python
@pytest.fixture
def svc(settings):
    return KnowledgeService(settings, MagicMock(), MagicMock())
```
Do NOT use `await KnowledgeService.create(settings)` in tests — that would require a live FalkorDB.

**MagicMock `.name` attribute:**
`m = MagicMock(); m.name = "x"` — NOT `MagicMock(name="x")` (special constructor param).
See `test_knowledge_service.py:107–112`.

**Async test pattern:**
No `@pytest.mark.asyncio` decorator needed — `asyncio_mode=auto` is set in `pyproject.toml`.

---

## IMPLEMENTATION PLAN

### Phase 1: Core Bug Fix — Sanitize group_id in KnowledgeService

The entire graph layer becomes functional once hyphens are replaced with underscores in the
`group_id` value passed to Graphiti. The `project_id` in SQLite and the FalkorDB `database` name
stay unchanged — only the `group_id` field within Graphiti's episode/search API calls changes.

**Rationale for underscore replacement:** Graphiti's RediSearch query template embeds `group_id`
into a filter string `(@group_id:"<value>")`. The hyphen inside the double-quoted value is still
parsed as a NOT operator by RediSearch (FalkorDB's full-text search engine). Underscores have no
special meaning in RediSearch queries and are safe. The mapping `project_id → group_id` is
internal to `KnowledgeService` — no other layer is affected.

**Consistency requirement:** The `group_id` stored on nodes/edges in FalkorDB must match the
`group_id` used in queries. After this fix, `add_episode()` stores nodes with `group_id =
"my_saas_app"` (underscores). The WHERE clause in `get_graph_data()` must also use the
sanitized form. The `FalkorDriver(database=project_id)` call uses the original hyphenated ID
for the graph name — this is CORRECT and must NOT change (FalkorDB graph names support hyphens).

### Phase 2: Prime Output Fix — Show Fact Content in Briefing

`SearchResult.entity_name` holds `edge.name` from Graphiti, which is a relationship type
identifier (e.g., `"MIGRATED_AWAY_TO"`). `SearchResult.content` holds `edge.fact`, which is the
human-readable sentence (e.g., `"We migrated away from PostgreSQL to SQLite"`). The briefing
currently uses `entity_name` as the label, hiding the fact. The fix mirrors the pattern in
`recall.py` — show both the relationship type prefix and the fact content.

### Phase 3: Recall Fallback Fix — Include Failed Episodes

Add `get_episodes_for_fallback()` to `ProjectsService` that returns episodes with status in
`('pending', 'processing', 'failed')`. Update `recall.py` to call this instead of
`get_pending_episodes()`. This ensures that knowledge stored before the hyphen fix (currently
all stuck as `failed`) is still searchable via keyword fallback.

### Phase 4: Tests — Update and Add

Update existing tests that may be affected by the group_id sanitization (particularly
`test_add_episode_passes_category_in_body` which asserts on kwargs). Add new tests for:
the sanitization helper, the fallback method, the briefing fact display, and the failed-episode
fallback in recall.

---

## STEP-BY-STEP TASKS

### Task 1: ADD `_graphiti_group_id` helper to `src/services/knowledge.py`

- **ADD** a module-level function after the imports and before the `KnowledgeService` class
- **IMPLEMENT**: `def _graphiti_group_id(project_id: str) -> str: return project_id.replace("-", "_")`
- **RATIONALE**: Module-level keeps it testable without instantiating KnowledgeService
- **VALIDATE**: `uv run python3 -c "from src.services.knowledge import _graphiti_group_id; assert _graphiti_group_id('my-saas-app') == 'my_saas_app'; print('OK')"`

### Task 2: UPDATE `add_episode()` in `src/services/knowledge.py`

- **UPDATE** line 113: change the `group_id=project_id` kwarg in `g.add_episode(...)` call
- **IMPLEMENT**: use `_graphiti_group_id(project_id)` instead of raw `project_id`
- **GOTCHA**: The `name=f"ep-{episode_id}"` and other params are unchanged; only `group_id` changes
- **VALIDATE**: `uv run pytest tests/test_knowledge_service.py::test_add_episode_calls_graphiti -v`

### Task 3: UPDATE `search()` in `src/services/knowledge.py`

- **UPDATE** line 122: change `group_ids=[project_id]` to `group_ids=[_graphiti_group_id(project_id)]`
- **VALIDATE**: `uv run pytest tests/test_knowledge_service.py::test_search_converts_edges_to_results -v`

### Task 4: UPDATE `get_graph_data()` in `src/services/knowledge.py`

- **UPDATE** the `_query()` inner function: wherever `params={"gid": project_id}` is used in
  the Cypher `WHERE n.group_id = $gid` and `WHERE r.group_id = $gid` clauses, pass
  `_graphiti_group_id(project_id)` as the value instead
- **GOTCHA**: `db.select_graph(project_id)` uses the ORIGINAL hyphenated `project_id` as the
  FalkorDB graph name — do NOT change this line. Only the `params` dict values change.
- **VALIDATE**: `uv run pytest tests/test_knowledge_service.py::test_get_graph_data_structure -v`

### Task 5: UPDATE `briefing.py` label logic

- **UPDATE** `src/services/briefing.py` lines 38 and 45 — in both the `decisions` and `pitfalls`
  loops, change the label construction
- **IMPLEMENT**: Replace `label = r.entity_name or r.content[:100]` with two lines:
  `label = r.entity_name or ""`
  `lines.append(f"- {label + ': ' if label else ''}{r.content[:100]}")`
- **PATTERN**: This mirrors `src/tools/recall.py:44–46` exactly
- **VALIDATE**: Manually confirm prime output no longer shows bare edge type names

### Task 6: ADD `get_episodes_for_fallback()` to `src/services/projects.py`

- **ADD** a new method to `ProjectsService` after `get_pending_episodes()` (around line 168)
- **IMPLEMENT**: Same structure as `get_pending_episodes()` but with
  `status IN ('pending', 'processing', 'failed')` instead of `status IN ('pending', 'processing')`
- **PATTERN**: Mirror `get_pending_episodes` at `projects.py:159–168` exactly — same
  `aiosqlite.connect`, same `db.row_factory`, same `_row_to_episode(row)` converter
- **VALIDATE**: `uv run pytest tests/test_projects_service_crud.py -v`

### Task 7: UPDATE `recall.py` to use new fallback method

- **UPDATE** `src/tools/recall.py` line 33: change
  `raw_episodes = await projects.get_pending_episodes(project_id)` to
  `raw_episodes = await projects.get_episodes_for_fallback(project_id)`
- **VALIDATE**: `uv run pytest tests/test_tools_recall.py -v`

### Task 8: ADD tests for `_graphiti_group_id` sanitization

- **UPDATE** `tests/test_knowledge_service.py`
- **ADD** tests:
  1. `test_graphiti_group_id_replaces_hyphens` — assert `_graphiti_group_id("my-saas-app") == "my_saas_app"`
  2. `test_graphiti_group_id_no_hyphens_unchanged` — assert `_graphiti_group_id("testproject") == "testproject"`
  3. `test_graphiti_group_id_multiple_hyphens` — assert `_graphiti_group_id("a-b-c-d") == "a_b_c_d"`
  4. `test_add_episode_uses_sanitized_group_id` — mock `get_graphiti`, call `add_episode("ep_x", "content", "decision", "my-project")`, assert `mock_graphiti.add_episode.call_args.kwargs["group_id"] == "my_project"`
  5. `test_search_uses_sanitized_group_ids` — mock `get_graphiti`, call `search("query", "my-project")`, assert `mock_graphiti.search.call_args.kwargs["group_ids"] == ["my_project"]`
- **IMPORT**: Add `from src.services.knowledge import _graphiti_group_id` at top of test file
- **VALIDATE**: `uv run pytest tests/test_knowledge_service.py -v`

### Task 9: ADD test for briefing fact display

- **UPDATE** `tests/test_briefing.py`
- **ADD** test `test_briefing_key_decisions_shows_fact_content`:
  1. Create project, create one episode
  2. Set up knowledge mock returning a `SearchResult` with `entity_name="MIGRATED_AWAY_TO"` and
     `content="We migrated from PostgreSQL to SQLite"`
  3. Call `generate_briefing(project, knowledge, projects)`
  4. Assert `"We migrated from PostgreSQL to SQLite" in result`
  5. Assert the result does NOT contain ONLY `"MIGRATED_AWAY_TO"` as a bare line (the edge type
     name is acceptable as a prefix, but the fact content must also appear)
- **PATTERN**: Use `_make_knowledge(search_results=[SearchResult(...)])` helper from same file
- **IMPORT**: `from src.models import SearchResult` and `from datetime import datetime, timezone`
- **VALIDATE**: `uv run pytest tests/test_briefing.py -v`

### Task 10: ADD test for failed-episode recall fallback

- **UPDATE** `tests/test_tools_recall.py`
- **ADD** test `test_recall_fallback_includes_failed_episodes`:
  1. `mcp, projects, knowledge = await _setup(tmp_path, search_results=[])`
  2. Create episode: `ep = await projects.create_episode("test-project", "We chose Redis for caching", "architecture")`
  3. Manually update episode status to `failed`: `await projects.update_episode_status(ep.episode_id, "failed")`
  4. Call `mcp.call_tool("recall", {"project_id": "test-project", "query": "Redis caching"})`
  5. Assert `"From recent unprocessed episodes:" in result.content[0].text`
- **RATIONALE**: Verifies that failed episodes (from extraction errors) remain searchable via keyword fallback
- **VALIDATE**: `uv run pytest tests/test_tools_recall.py::test_recall_fallback_includes_failed_episodes -v`

### Task 11: ADD test for `get_episodes_for_fallback`

- **UPDATE** `tests/test_projects_service_crud.py`
- **ADD** test `test_get_episodes_for_fallback_includes_failed`:
  1. Create project and 3 episodes
  2. Update episode 1 to `complete`, episode 2 to `failed`, episode 3 stays `pending`
  3. Call `await projects.get_episodes_for_fallback(project_id)`
  4. Assert 2 episodes returned (failed + pending); complete episode NOT in results
  5. Assert statuses in result: `{"failed", "pending"} == {ep.status for ep in results}`
- **VALIDATE**: `uv run pytest tests/test_projects_service_crud.py -v`

---

## TESTING STRATEGY

### Unit Tests

All test changes are in existing test files. No new test files needed. Tests use real SQLite
via `tmp_path` for `ProjectsService` tests, and `MagicMock`/`AsyncMock` for Graphiti/FalkorDB.

### Edge Cases

- `_graphiti_group_id("testproject")` — no hyphens → should return unchanged (no regression)
- `_graphiti_group_id("a")` — single char no hyphen → unchanged
- `_graphiti_group_id("")` — empty string → returns empty string (shouldn't happen in practice)
- `get_episodes_for_fallback` with all-complete episodes → returns empty list
- `get_episodes_for_fallback` with mixed statuses → returns only pending/processing/failed
- briefing with empty search results → still shows Last Session, no Key Decisions section

---

## VALIDATION COMMANDS

### Level 1: Lint

```bash
cd "/root/Documents/Agent harness"
uv run ruff check src/
uv run ruff format src/ --check
```

### Level 2: Type Check

```bash
cd "/root/Documents/Agent harness"
uv run mypy src/
```

### Level 3: Full Test Suite

```bash
cd "/root/Documents/Agent harness"
uv run pytest tests/ -v
```

### Level 4: Targeted Regression Tests (run after each task)

```bash
cd "/root/Documents/Agent harness"
# After Task 1–4 (knowledge.py changes)
uv run pytest tests/test_knowledge_service.py -v

# After Task 5 (briefing.py)
uv run pytest tests/test_briefing.py -v

# After Task 6–7 (projects.py + recall.py)
uv run pytest tests/test_tools_recall.py tests/test_projects_service_crud.py -v

# After all tasks
uv run pytest tests/ -v
```

### Level 5: Live Integration Test (requires FalkorDB + API keys)

```bash
cd "/root/Documents/Agent harness"
# Confirm FalkorDB is healthy
docker compose ps
curl -s http://127.0.0.1:8090/api/health | python3 -m json.tool

# Run the server and test via MCP or direct Python:
uv run python3 -c "
import asyncio, os
key = open('.env').read().split('LLM_API_KEY=')[1].split('\n')[0]
os.environ['LLM_API_KEY'] = key; os.environ['OPENAI_API_KEY'] = key

async def test():
    from src.services.knowledge import KnowledgeService, _graphiti_group_id
    from src.config import get_settings

    # Unit test the helper
    assert _graphiti_group_id('my-saas-app') == 'my_saas_app'
    assert _graphiti_group_id('testproject') == 'testproject'
    print('group_id sanitization: OK')

    # Integration: add_episode with a hyphenated project_id must succeed
    settings = get_settings()
    svc = await KnowledgeService.create(settings)
    from datetime import datetime, timezone
    result = await svc.add_episode('ep_integ001', 'Integration test: SQLite chosen for simplicity.', 'decision', 'my-hyphenated-project')
    print(f'add_episode with hyphenated project_id: OK (uuid={result})')

asyncio.run(test())
"
```

---

## ACCEPTANCE CRITERIA

- [ ] `_graphiti_group_id("my-saas-app")` returns `"my_saas_app"`
- [ ] `KnowledgeService.add_episode(...)` called with a hyphenated `project_id` succeeds (no RediSearch syntax error)
- [ ] All episodes for any project with hyphens in `project_id` reach `status="complete"` after extraction
- [ ] `prime` "Key Decisions" section shows fact sentences (e.g., `"MIGRATED_AWAY_TO: We migrated from PostgreSQL to SQLite"`) not bare edge type names alone
- [ ] `recall` returns keyword-matched content for `status="failed"` episodes when graph search returns nothing
- [ ] `get_episodes_for_fallback()` returns `pending`, `processing`, AND `failed` episodes but NOT `complete`
- [ ] `uv run pytest tests/ -v` — all tests pass (no regressions)
- [ ] `uv run ruff check src/` — zero linting errors
- [ ] Live integration: project `my-saas-app` extraction succeeds end-to-end with `status="complete"`

---

## COMPLETION CHECKLIST

- [ ] Task 1: `_graphiti_group_id` helper added to `knowledge.py`
- [ ] Task 2: `add_episode()` uses sanitized group_id
- [ ] Task 3: `search()` uses sanitized group_ids
- [ ] Task 4: `get_graph_data()` WHERE clause uses sanitized group_id
- [ ] Task 5: `briefing.py` label logic fixed to show fact content
- [ ] Task 6: `get_episodes_for_fallback()` added to `ProjectsService`
- [ ] Task 7: `recall.py` uses `get_episodes_for_fallback()`
- [ ] Task 8: New knowledge service tests added and passing
- [ ] Task 9: New briefing test added and passing
- [ ] Task 10: New recall fallback test added and passing
- [ ] Task 11: New projects service CRUD test added and passing
- [ ] Full test suite passes: `uv run pytest tests/ -v`
- [ ] Linting passes: `uv run ruff check src/`
- [ ] Live integration test confirms extraction succeeds for hyphenated project IDs

---

## NOTES

### Why underscores and not something else

Underscores have no special meaning in RediSearch query syntax. Dots, colons, slashes, and
hyphens all have special meaning. Underscores are safe in property values, graph names, and
Cypher identifiers. The transformation is trivially reversible for debugging.

### Why the FalkorDriver `database` parameter is NOT changed

The FalkorDB graph name (used in `db.select_graph(project_id)`) supports hyphens — confirmed by
live testing where `FalkorDriver(database="test-direct")` initialised without error. The RediSearch
syntax error only occurs when the value is embedded in a full-text query string, which Graphiti
does internally for `group_id`. Keeping the database name as the original `project_id` preserves
all existing `get_graph_data()` REST API behaviour.

### Existing failed episodes from before the fix

After deploying this fix, all previously `failed` episodes (those created while the hyphen bug
was active) will remain `failed` in SQLite. They cannot be automatically re-extracted without
re-calling `remember()`. The `recall` fallback fix (Bug 3) ensures their content is at least
still keyword-searchable. If full graph extraction of historical episodes is desired, a
migration script would need to re-enqueue them — that is out of scope for this plan.

### Temporal awareness

The temporal invalidation mechanism in Graphiti (`invalid_at` on edges) is architecturally
correct and works as designed once Bug 1 is fixed. Live testing with project `testgraph`
(no hyphens) confirmed:
- Semantic search returns results with zero keyword overlap (vector embeddings working)
- Relationship types are semantically meaningful (MIGRATED_AWAY_TO, API_INCOMPATIBLE_WITH, etc.)
- Temporal transitions are captured as graph edges (e.g., "We migrated away from PostgreSQL to SQLite")

Automatic edge invalidation (setting `invalid_at`) fires only when Graphiti's LLM detects a
direct contradiction between a new fact and an existing entity property. Narrative migration
statements ("we switched from X to Y") are captured as new `MIGRATED_AWAY_TO` edges rather than
invalidating the original "X was used" edges. This is Graphiti's designed behaviour, not a bug.

### Test for `test_add_episode_passes_category_in_body` — possible update needed

`tests/test_knowledge_service.py:142–159` uses a `fake_add_episode` that captures kwargs. After
Bug 1 fix, the `group_id` kwarg will be `"proj_x"` (underscore) rather than `"proj-x"`. If that
test currently asserts on `group_id`, update it. If it only asserts on `episode_body`, no change
is needed. Read the test carefully before touching it.
