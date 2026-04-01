# Changelog

All notable changes to Agent Harness are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added (Phase 2a)
- `skills/agent-harness/` — Claude Code skill providing session workflow and
  knowledge quality standards for Agent Harness. Includes core `SKILL.md` and
  three progressive-disclosure reference files: `what-to-remember.md` (quality
  gate with ❌/✅ examples), `category-guide.md` (one-liner examples per
  category), and `update-workflow.md` (step-by-step procedure for recording
  changed facts to trigger Graphiti's `invalid_at` contradiction detection).
- `CLAUDE.md` §13 — Skill location, install command, and iteration loop
  documentation.

### Added

#### Backend
- `GET /api/projects/{id}/graph` now returns **episodic nodes** as a distinct node type (`node_type: "episodic"`). Each episodic node carries `category` (parsed from the `[CATEGORY]` prefix written by `remember()`), full untruncated `summary` content, and `created_at`.
- Entity nodes in the graph response now include `created_at`.
- Entity→Entity edges now include `valid_at`, `invalid_at`, and `stale` fields. Superseded/overwritten relationships are no longer filtered out — they are returned with `invalid_at` set, enabling temporal exploration on the client.
- `DELETE /api/projects/{id}/graph/nodes/{node_id}` — remove a specific entity node and all its edges from the FalkorDB graph.
- `DELETE /api/projects/{id}/graph/edges/{edge_id}` — remove a specific relationship edge from the FalkorDB graph.

#### Dashboard (frontend)
- **Temporal scrubber**: horizontal range slider docked at the bottom of the graph canvas. Default view shows only currently-active (non-superseded) edges. Dragging left reveals the graph as it existed at any past point in time — nodes that didn't exist yet disappear, stale edges reappear. A "× Reset" button returns to the live view. Visible only when a project is selected.
- **Camera fly-to animation**: clicking any node (in the canvas, from the left panel, or from the right panel) smoothly lerps the camera to a position ~8 units from that node using `useFrame` + `OrbitControls.target` interpolation.
- **Node-to-node navigation from NodeDetailPanel**: connected node names in the Outgoing and Incoming edge lists are now interactive. Clicking a neighbour name selects it, opens its detail panel, and flies the camera to it — enabling traversal through the graph purely from the right sidebar.
- **Left panel navigation to graph nodes**: clicking an item in Episodes, Timeline, or Search Results flies the camera to the corresponding node in the 3D canvas and opens its NodeDetailPanel. Episodes and timeline items navigate to the matching episodic (diamond) node; search results navigate to the matching entity node.
- **Episodic node hover label**: episodic nodes previously showed a raw internal UUID as their label. They now show `[CATEGORY]` as the prominent prefix followed by the first 35 characters of the episode content.
- **NodeDetailPanel category badge**: the circle icon in the panel header is now coloured to match the episode category (amber for `decision`, cyan for `insight`, red for `error`, green for `goal`, purple for `architecture`). The title displays `[CATEGORY]` for episodic nodes instead of the raw UUID name.
- **Shared colour constants**: `CATEGORY_COLORS` extracted to `src/lib/colors.ts` and imported by both `GraphView` and `NodeDetailPanel`, eliminating duplication.
- **Recent entity node colour**: changed from warm cream (`#f0e6d8`) to pure white (`#ffffff`). The previous colour picked up purple tint from the scene's ambient lighting; pure white blooms correctly as a stellar point of light and contrasts clearly against the deep-indigo older-entity colour (`#3d2a6e`). Legend swatch updated to match.
- `GraphEdge` TypeScript type: added optional `valid_at` and `invalid_at` string fields.

### Changed
- `get_graph_data()` in `KnowledgeService` no longer truncates episodic node content to 120 characters. Full content is stored in `summary` so the NodeDetailPanel can display it without cut-off.
- `get_graph_data()` issues four Cypher queries instead of two: entity nodes, episodic nodes, entity→entity edges, and episodic→entity MENTIONS edges (unchanged query, previously already present).

### Fixed
- Test `test_get_graph_data_structure` updated to match the new four-query structure and extended column shapes (entity nodes now return 4 columns; edges return 7 columns including `valid_at` / `invalid_at`).

---

## [0.5.0] — 2026-03-29

### Added
- `forget(project_id, episode_id)` MCP tool — delete a stored knowledge item by its episode ID. Removes the SQLite record and excludes the episode from all future keyword fallback searches.
- Orphan re-queue on server startup: episodes in `pending` or `processing` state at shutdown are automatically re-enqueued when the server restarts, preventing knowledge loss across restarts.
- Temporal filtering in `prime()`: superseded facts (graph edges with `invalid_at` set) are marked with `~~strikethrough~~ (superseded)` in the briefing so the agent can distinguish current state from historical context.
- `DELETE /api/projects/{id}` REST endpoint (cascade-deletes all episodes and graph data).
- `POST /api/projects/{id}/search` REST endpoint (graph + raw fallback search, body: `{"query": "...", "limit": 10}`).
- `get_all_orphaned_episodes()` in `ProjectsService` — queries SQLite for all non-complete, non-failed episodes across all projects.
- `delete_project()` in `ProjectsService` — cascades to episodes table.

### Changed
- `prime()` output format: Key Decisions and Known Pitfalls now show both the relationship-type label and the human-readable fact sentence (`RelationshipType: fact sentence`). Sections are omitted entirely when no graph results exist yet (previously showed empty headers).
- `get_episodes_for_fallback()` now includes episodes with `status=failed` in the keyword fallback search (previously only `pending`/`processing` were included).

---

## [0.4.0] — 2026-03-28

### Fixed
- **Critical**: hyphens in `project_id` values broke Graphiti entity extraction. `_graphiti_group_id()` now replaces hyphens with underscores before passing to Graphiti (`my-app` → `my_app`). FalkorDB graph name retains the original hyphenated ID. Applied consistently to all `add_episode()`, `search()`, and `get_graph_data()` calls.
- `prime()` was displaying raw graph edge-type names (e.g. `MIGRATED_AWAY_TO`) instead of the fact sentence. Fixed label logic in `briefing.py`.
- `recall()` keyword fallback was not including `failed` episodes. Fixed `get_episodes_for_fallback()` filter.
- `test_settings_defaults` test isolation: `graphiti_core` calls `load_dotenv()` at import time, causing `.env` values to bleed into Settings defaults tests. Fixed with `monkeypatch.delenv()` + `Settings(_env_file=None)`.

---

## [0.3.0] — 2026-03-27

### Added
- Comprehensive test suite: 122 tests covering all 5 MCP tool handlers, ProjectsService CRUD, KnowledgeService (mocked Graphiti and FalkorDB), FastAPI REST routes (httpx ASGI transport), MCP tool registration, and the repo scanner.
- Integration test scaffold at `tests/integration/` for live-stack validation with a real FalkorDB instance.

### Changed
- Test count: 0 → 122.

---

## [0.2.0] — 2026-03-26

### Added
- `init_project(scan_repo=True, repo_path=...)` — optional repository scan on project creation. Reads `package.json`, `pyproject.toml`, `requirements.txt`, `docker-compose.yml`/`.yaml`, `README.md`/`.rst`, up to 5 `docs/*.md` files, and a two-level folder tree. Each file becomes an `architecture` episode enqueued asynchronously. Scan only runs for new projects.
- `RepoScanner` service (`src/services/scanner.py`).
- REST API for the dashboard on `http://localhost:8080`:
  - `GET /api/health`
  - `GET /api/projects` / `GET /api/projects/{id}`
  - `GET /api/projects/{id}/graph`
  - `GET /api/projects/{id}/insights` (paginated, filterable by category)
  - `GET /api/projects/{id}/timeline`
  - `DELETE /api/projects/{id}/episodes/{ep_id}`

---

## [0.1.0] — 2026-03-25

### Added
- Initial implementation: FastMCP + FastAPI dual-transport server in a single process.
- Five MCP tools: `prime`, `remember`, `recall`, `init_project`, `forget`.
- `KnowledgeService`: Graphiti wrapper with per-project instance cache, `_graphiti_group_id()` sanitiser, `add_episode()`, `search()`, `get_graph_data()`.
- `ProjectsService`: SQLite-backed CRUD for projects and episodes with status tracking (`pending` → `processing` → `complete` / `failed`).
- `BriefingService`: compressed ≤400-token session briefing for `prime()`.
- Background extraction queue: `asyncio.Queue` + configurable worker pool (default 4) with graceful shutdown via `None` sentinel.
- FalkorDB connection with exponential-backoff retry (5 attempts: 1 s, 2 s, 4 s, 8 s, 15 s).
- Pydantic Settings for all configuration; `MCP_ENV_FILE` for explicit `.env` path.
- `docker-compose.yml` binding FalkorDB to `127.0.0.1:6379` only.
