# Feature: Phase 1 — Core MCP Server

The following plan should be complete, but validate documentation and codebase patterns before implementing. There is NO existing source code — this is a greenfield implementation. All patterns come from `.agents/reference/` docs.

Pay special attention to import paths (`from graphiti_core...`, `from fastmcp...`), the per-project Graphiti cache pattern (one Graphiti instance per project, NOT one global), and never writing to stdout.

## Feature Description

Implement the complete Agent Harness MCP server: a FastMCP + FastAPI dual-transport Python process that exposes 4 MCP tools (`prime`, `remember`, `recall`, `init_project`) backed by per-project Graphiti instances + FalkorDB for persistent, temporal knowledge graph memory.

## User Story

As an AI coding agent (Claude Code),
I want to call `prime`, `remember`, `recall`, and `init_project` tools,
So that I have persistent memory of project decisions, insights, and errors across sessions.

## Problem Statement

No source code exists yet. The entire Phase 1 implementation must be built from scratch following the architecture in `.agents/reference/` and the PRD.

## Solution Statement

Implement all source files in dependency order: config → models → services → tools → server → infra files. Services are initialized once at startup and shared via injection into both MCP tools and REST routes. Background extraction uses an `asyncio.Queue` + worker pool to avoid circular imports and enable clean shutdown.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: All (greenfield)
**Dependencies**: fastmcp>=3.0,<4.0, graphiti-core[falkordb]>=0.28,<1.0, fastapi, uvicorn, aiosqlite, pydantic-settings, anyio

---

## VERIFIED FINDINGS (Pre-Implementation Research)

### Risk 1 RESOLVED — `graph_driver=` confirmed
Graphiti constructor uses `graph_driver=` (since v0.17.0). Also: `FalkorDriver` accepts `database=` as a **string** (not just int) for named graph isolation. Example:
```python
driver = FalkorDriver(host="localhost", port=6379, database="my-project-slug")
graphiti = Graphiti(graph_driver=driver)
```
FalkorDB creates the named graph automatically on first write — no explicit CREATE needed.

### Risk 2 RESOLVED — `mcp.run_async()` confirmed correct
Verified from FastMCP source and gofastmcp.com docs. For stdio, no arguments needed:
```python
await mcp.run_async()   # stdio is default transport
```
`run()` vs `run_async()`: `run()` creates its own event loop (cannot be called inside async functions). `run_async()` runs in the existing event loop — required for `asyncio.gather()` with Uvicorn.
There is NO `run_stdio_async()` in v3 — that name appears only in the CLI's v1.x backward-compatibility branch.

### Risk 3 RESOLVED — Use asyncio.Queue + worker pool
Instead of module-level `_background_tasks` set (circular import risk), use:
- `asyncio.Queue` created in `server.py`
- Worker coroutines consume from queue (N workers = concurrency limit)
- `remember.py` receives the queue via injection from `make_remember(mcp, knowledge, projects, extraction_queue)`
- Graceful shutdown: send sentinel `None` per worker, then `await extraction_queue.join()`

### Additional Verified Findings
- **FalkorDB env vars**: Must be passed explicitly to `FalkorDriver()`. Not auto-picked from environment.
- **Install extra**: Use `graphiti-core[falkordb]` — without `[falkordb]`, `from graphiti_core.driver.falkordb_driver import FalkorDriver` raises `ImportError`
- **SEMAPHORE_LIMIT**: Graphiti uses `SEMAPHORE_LIMIT` env var (default 10) to control concurrent LLM calls during extraction. Add to config and `.env.example`. Expose as `EXTRACTION_WORKERS=4` in our config → set as number of queue workers.
- **`build_indices_and_constraints()`**: Idempotent — safe to call on every startup. FalkorDB logs "Index already exists" as info (not error) if indices exist. Must be called per-project Graphiti instance.
- **FalkorDB graph auto-creation**: `database=project_id` → named graph created on first write. No explicit init needed.
- **Deployment**: uvx on host + FalkorDB in Docker only. Confirmed correct per PRD §6.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

- `.agents/reference/mcp-server.md` — FastMCP v3 tool definitions, ToolError, dual transport, logging rules, entry point pattern
- `.agents/reference/graphiti.md` — FalkorDriver setup, Graphiti constructor, `add_episode()`, `search()`, SearchConfig, SearchFilters, EpisodeType, retry pattern
- `.agents/reference/falkordb.md` — docker-compose.yml template (NO ports:), health check pattern, Python client
- `.agents/reference/fastapi.md` — Full dual transport code, Uvicorn config (loop=asyncio, workers=1, log_config=None), startup sequence, graceful shutdown, route registration pattern
- `.claude/PRD.md` lines 296–500 — Full tool specs (parameters, response shapes, error responses, output formats)
- `.claude/PRD.md` lines 780–798 — Phase 1 checklist

### New Files to Create

```
pyproject.toml
docker-compose.yml
.env.example
.gitignore
src/__init__.py
src/config.py
src/models.py
src/services/__init__.py
src/services/projects.py
src/services/knowledge.py
src/services/briefing.py
src/tools/__init__.py
src/tools/init_project.py
src/tools/remember.py
src/tools/recall.py
src/tools/prime.py
src/api/__init__.py
src/api/routes.py
src/server.py
```

### Relevant Documentation — READ BEFORE IMPLEMENTING

- `.agents/reference/mcp-server.md` — Complete FastMCP v3 API
- `.agents/reference/graphiti.md` — Complete Graphiti 0.28.x API
- `.agents/reference/fastapi.md` — Complete dual-transport pattern

### Patterns to Follow

**Logging — CRITICAL:**
```python
import logging, sys
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,   # NEVER stdout
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
```
Never use `print()`. Never use `stream=sys.stdout`.

**Tool error pattern:**
```python
from fastmcp.exceptions import ToolError
raise ToolError("Project 'x' not found. Call init_project first.")
```

**Per-project Graphiti cache pattern:**
```python
class KnowledgeService:
    def __init__(self, settings):
        self._settings = settings
        self._llm_client = ...   # shared stateless HTTP client
        self._embedder = ...     # shared stateless HTTP client
        self._graphiti_cache: dict[str, Graphiti] = {}

    async def get_graphiti(self, project_id: str) -> Graphiti:
        if project_id not in self._graphiti_cache:
            driver = FalkorDriver(
                host=self._settings.falkordb_host,
                port=self._settings.falkordb_port,
                database=project_id,   # str — creates named graph automatically
            )
            g = Graphiti(graph_driver=driver, llm_client=self._llm_client, embedder=self._embedder)
            await g.build_indices_and_constraints()
            self._graphiti_cache[project_id] = g
        return self._graphiti_cache[project_id]
```

**Queue + worker pattern:**
```python
# server.py — created at startup, injected into tools
extraction_queue: asyncio.Queue = asyncio.Queue()

async def _extraction_worker(queue, knowledge, projects):
    while True:
        item = await queue.get()
        if item is None:   # shutdown sentinel
            queue.task_done()
            return
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

# remember.py tool just does:
await extraction_queue.put((episode_id, content, category, project_id))
```

**Slug pattern:**
```python
import re
def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:64]
```

**Graphiti search — no group_id filter needed** when using `database=project_id`:
```python
# Each project has its own Graphiti instance (its own named FalkorDB graph)
g = await knowledge.get_graphiti(project_id)
results = await g.search(query=q, limit=10)
# No SearchFilters needed — the database IS the namespace
```
Note: Still add `SearchFilters(group_ids=[project_id])` as a safety belt if the Graphiti version requires it.

**Uvicorn config (critical settings):**
```python
uvicorn.Config(app=app, host="127.0.0.1", port=8080,
               loop="asyncio", workers=1, log_config=None, access_log=False)
```

---

## IMPLEMENTATION PLAN

### Phase A: Infra + Config Layer
Foundation that everything else depends on.

### Phase B: Services Layer
Business logic — no MCP dependency, independently testable.

### Phase C: Tool Handlers
MCP tool implementations using service layer.

### Phase D: Server Assembly
Wire everything together: dual transport, queue workers, startup, shutdown.

---

## STEP-BY-STEP TASKS

### Task 1: CREATE pyproject.toml

- **IMPLEMENT**: Full package config with all dependencies, console_scripts entry point, python 3.11+
- **CRITICAL**: Use `graphiti-core[falkordb]` not just `graphiti-core`
- **CONTENT**:
  ```toml
  [project]
  name = "agent-harness"
  version = "0.1.0"
  description = "Persistent knowledge graph memory for AI coding agents"
  requires-python = ">=3.11"
  dependencies = [
      "fastmcp>=3.0,<4.0",
      "graphiti-core[falkordb]>=0.28,<1.0",
      "falkordb>=1.0.0,<2.0.0",
      "fastapi>=0.115",
      "uvicorn>=0.32",
      "aiosqlite>=0.20",
      "pydantic>=2.0",
      "pydantic-settings>=2.0",
      "anyio>=4.0",
      "python-dotenv>=1.0",
  ]

  [project.scripts]
  agent-harness = "src.server:main"

  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [tool.hatch.build.targets.wheel]
  packages = ["src"]

  [tool.ruff.lint]
  select = ["E", "F", "I"]

  [tool.mypy]
  python_version = "3.11"
  strict = false

  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  ```
- **VALIDATE**: `uv sync` completes without error

### Task 2: CREATE docker-compose.yml

- **IMPLEMENT**: FalkorDB only, NO ports: mapping, healthcheck, named volume
- **CRITICAL RULE**: MUST NOT have `ports:` key — Docker host networking bridges localhost:6379 → container
- **CONTENT**:
  ```yaml
  services:
    falkordb:
      image: falkordb/falkordb:latest
      container_name: agent-harness-falkordb
      restart: unless-stopped
      volumes:
        - falkordb_data:/data
      healthcheck:
        test: ["CMD", "redis-cli", "ping"]
        interval: 10s
        timeout: 5s
        retries: 5

  volumes:
    falkordb_data:
      driver: local
  ```
- **VALIDATE**: `docker compose up -d && docker compose ps` shows `(healthy)`

### Task 3: CREATE .env.example

- **IMPLEMENT**: All env vars, placeholder values only — NEVER real API keys
- **CONTENT**:
  ```env
  # Required
  LLM_PROVIDER=openai
  LLM_API_KEY=your-llm-api-key-here
  LLM_MODEL=gpt-4.1-mini
  OPENAI_API_KEY=your-openai-api-key-here

  # Optional (defaults shown)
  FALKORDB_HOST=localhost
  FALKORDB_PORT=6379
  HTTP_PORT=8080
  UVICORN_HOST=127.0.0.1
  LOG_LEVEL=info
  SQLITE_PATH=~/.agent-harness/projects.db
  ALLOWED_ORIGINS=http://localhost:3000
  EXTRACTION_WORKERS=4

  # If MCP server cannot read shell env, point to absolute path of your .env:
  # MCP_ENV_FILE=/absolute/path/to/.env
  ```
- **GOTCHA**: This file IS committed to git — it must never contain real keys
- **VALIDATE**: `grep -E "sk-|key-[a-zA-Z0-9]{20}" .env.example` returns nothing

### Task 4: CREATE .gitignore

- **CONTENT**:
  ```
  .env
  *.pyc
  __pycache__/
  .venv/
  dist/
  *.egg-info/
  .pytest_cache/
  .mypy_cache/
  .ruff_cache/
  *.db
  ```
- **VALIDATE**: `git check-ignore .env` outputs `.env`

### Task 5: CREATE src/__init__.py (empty) and src/config.py

- **IMPLEMENT**: Pydantic Settings with all env vars, `get_settings()` cached singleton
- **IMPORTS**: `from pydantic_settings import BaseSettings, SettingsConfigDict`
- **CONTENT**:
  ```python
  import sys
  from functools import lru_cache
  from pathlib import Path
  from typing import Literal
  from pydantic_settings import BaseSettings, SettingsConfigDict

  class Settings(BaseSettings):
      # LLM
      llm_provider: Literal["openai", "anthropic", "ollama"] = "openai"
      llm_api_key: str = ""
      llm_model: str = "gpt-4.1-mini"
      openai_api_key: str = ""

      # FalkorDB — must be passed explicitly, NOT read from env automatically by FalkorDriver
      falkordb_host: str = "localhost"
      falkordb_port: int = 6379

      # Server
      http_port: int = 8080
      uvicorn_host: str = "127.0.0.1"
      log_level: str = "info"
      allowed_origins: str = "http://localhost:3000"

      # SQLite
      sqlite_path: str = "~/.agent-harness/projects.db"

      # Background extraction worker count (controls concurrency to LLM API)
      extraction_workers: int = 4

      # Optional env file path (for MCP env isolation)
      mcp_env_file: str | None = None

      model_config = SettingsConfigDict(
          env_file=".env",
          env_file_encoding="utf-8",
          extra="ignore",
          case_sensitive=False,
      )

      @property
      def sqlite_path_resolved(self) -> Path:
          return Path(self.sqlite_path).expanduser()

  @lru_cache(maxsize=1)
  def get_settings() -> Settings:
      return Settings()
  ```
- **VALIDATE**: `uv run python -c "from src.config import get_settings; s = get_settings(); print(s.falkordb_host)"` prints `localhost`

### Task 6: CREATE src/models.py

- **IMPLEMENT**: All Pydantic v2 models
- **CONTENT**:
  ```python
  from datetime import datetime
  from typing import Literal
  from pydantic import BaseModel

  EpisodeStatus = Literal["pending", "processing", "complete", "failed"]
  KnowledgeCategory = Literal["decision", "insight", "error", "goal", "architecture"]

  class Project(BaseModel):
      project_id: str          # slug, e.g. "my-saas-app"
      name: str
      description: str
      created_at: datetime
      repo_path: str | None = None
      episode_count: int = 0

  class Episode(BaseModel):
      episode_id: str          # "ep_" + uuid4().hex[:12]
      project_id: str
      content: str
      category: KnowledgeCategory
      status: EpisodeStatus = "pending"
      created_at: datetime
      graphiti_episode_id: str | None = None

  class SearchResult(BaseModel):
      content: str
      score: float
      source: Literal["graph", "raw_episode"]
      entity_name: str | None = None
      created_at: datetime | None = None
  ```
- **VALIDATE**: `uv run python -c "from src.models import Episode, Project, SearchResult; print('ok')"`

### Task 7: CREATE src/services/__init__.py (empty) and src/services/projects.py

- **IMPLEMENT**: SQLite CRUD for project metadata and episode tracking using `aiosqlite`
- **SCHEMA**:
  ```sql
  CREATE TABLE IF NOT EXISTS projects (
      project_id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      description TEXT NOT NULL,
      created_at TEXT NOT NULL,
      repo_path TEXT
  );

  CREATE TABLE IF NOT EXISTS episodes (
      episode_id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL,
      content TEXT NOT NULL,
      category TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      created_at TEXT NOT NULL,
      graphiti_episode_id TEXT,
      FOREIGN KEY (project_id) REFERENCES projects(project_id)
  );
  ```
- **CLASS**:
  ```python
  import aiosqlite
  from pathlib import Path
  from uuid import uuid4
  from datetime import datetime, timezone
  from src.models import Project, Episode

  class ProjectsService:
      def __init__(self, db_path: Path):
          self._db_path = db_path

      @classmethod
      async def create(cls, settings) -> "ProjectsService":
          db_path = settings.sqlite_path_resolved
          db_path.parent.mkdir(parents=True, exist_ok=True)
          svc = cls(db_path)
          await svc._init_db()
          return svc

      async def _init_db(self):
          async with aiosqlite.connect(self._db_path) as db:
              await db.execute("""CREATE TABLE IF NOT EXISTS projects ...""")
              await db.execute("""CREATE TABLE IF NOT EXISTS episodes ...""")
              await db.commit()

      async def get(self, project_id: str) -> Project | None: ...
      async def create_project(self, name: str, description: str, repo_path: str | None = None) -> Project: ...
      async def list_all(self) -> list[Project]: ...
      async def count(self) -> int: ...

      async def create_episode(self, project_id: str, content: str, category: str) -> Episode:
          episode_id = "ep_" + uuid4().hex[:12]
          created_at = datetime.now(timezone.utc)
          # INSERT into episodes table
          return Episode(episode_id=episode_id, project_id=project_id,
                        content=content, category=category, status="pending",
                        created_at=created_at)

      async def update_episode_status(self, episode_id: str, status: str,
                                       graphiti_episode_id: str | None = None) -> None: ...
      async def get_pending_episodes(self, project_id: str) -> list[Episode]: ...
      async def get_recent_episodes(self, project_id: str, limit: int = 5) -> list[Episode]: ...
  ```
- **GOTCHA**: Store datetimes as ISO strings (`dt.isoformat()`), parse with `datetime.fromisoformat()`
- **GOTCHA**: `episode_count` for Project comes from a COUNT query on episodes table
- **VALIDATE**: `uv run python -c "import asyncio; from src.services.projects import ProjectsService; from src.config import get_settings; asyncio.run(ProjectsService.create(get_settings())); print('ok')"`

### Task 8: CREATE src/services/knowledge.py

- **IMPLEMENT**: Per-project Graphiti cache, FalkorDB retry (on initial health check), `add_episode()`, `search()`, health check, REST data methods
- **ARCHITECTURE**: One shared LLM client + embedder. One Graphiti instance per project, lazily created and cached. FalkorDriver uses `database=project_id` (string) for true graph isolation.
- **CRITICAL IMPORTS**:
  ```python
  from graphiti_core import Graphiti
  from graphiti_core.driver.falkordb_driver import FalkorDriver
  from graphiti_core.llm_client import OpenAIClient
  from graphiti_core.llm_client.anthropic_client import AnthropicClient
  from graphiti_core.llm_client.config import LLMConfig
  from graphiti_core.embedder import OpenAIEmbedder
  from graphiti_core.embedder.config import EmbedderConfig
  from graphiti_core.nodes import EpisodeType
  from graphiti_core.search.search_config import SearchConfig, SearchFilters
  ```
- **CONSTRUCTOR** (verified — `graph_driver=` not `driver=`):
  ```python
  graphiti = Graphiti(graph_driver=driver, llm_client=llm_client, embedder=embedder)
  ```
- **FalkorDB RETRY** — used at startup to verify FalkorDB is reachable (test with a dummy graph):
  ```python
  @classmethod
  async def create(cls, settings) -> "KnowledgeService":
      llm_client = cls._build_llm_client(settings)
      embedder = cls._build_embedder(settings)
      svc = cls(settings, llm_client, embedder)
      await svc._verify_connection()   # retry loop on _health graph
      return svc

  async def _verify_connection(self):
      delays = [1, 2, 4, 8, 15]
      for attempt, delay in enumerate(delays, 1):
          try:
              healthy = await self.check_connection()
              if healthy:
                  logger.info("FalkorDB connection verified")
                  return
          except Exception as e:
              logger.warning(f"FalkorDB attempt {attempt} failed: {e}")
              if attempt < len(delays):
                  await asyncio.sleep(delay)
      raise RuntimeError("FalkorDB unavailable after 5 attempts")
  ```
- **get_graphiti (per-project cache)**:
  ```python
  async def get_graphiti(self, project_id: str) -> Graphiti:
      if project_id not in self._graphiti_cache:
          driver = FalkorDriver(
              host=self._settings.falkordb_host,
              port=self._settings.falkordb_port,
              database=project_id,   # str — auto-creates named graph on first write
          )
          g = Graphiti(graph_driver=driver, llm_client=self._llm_client, embedder=self._embedder)
          await g.build_indices_and_constraints()
          self._graphiti_cache[project_id] = g
          logger.info(f"Graphiti instance created for project: {project_id}")
      return self._graphiti_cache[project_id]
  ```
- **add_episode**:
  ```python
  async def add_episode(self, episode_id: str, content: str, category: str, project_id: str) -> str:
      g = await self.get_graphiti(project_id)
      result = await g.add_episode(
          name=f"ep-{episode_id}",
          episode_body=f"[{category.upper()}] {content}",
          source=EpisodeType.text,
          source_description=f"Agent knowledge capture — category: {category}",
          reference_time=datetime.now(timezone.utc),
          group_id=project_id,   # safety belt even with database isolation
      )
      return result.episode_id
  ```
- **search**:
  ```python
  async def search(self, query: str, project_id: str, limit: int = 10) -> list[SearchResult]:
      g = await self.get_graphiti(project_id)
      results = await g.search(
          query=query,
          filters=SearchFilters(group_ids=[project_id]),  # safety belt
          limit=limit,
      )
      # Build SearchResult list from results.nodes + results.edges + results.episodes
  ```
- **check_connection** (health check using `_health` graph):
  ```python
  async def check_connection(self) -> bool:
      try:
          from falkordb import FalkorDB
          db = FalkorDB(host=self._settings.falkordb_host, port=self._settings.falkordb_port)
          g = db.select_graph("_health_check")
          g.query("RETURN 1")
          return True
      except Exception:
          return False
  ```
- **REST data methods** (return empty for Phase 1, real data in Phase 2):
  ```python
  async def get_graph_data(self, project_id: str) -> dict:
      return {"nodes": [], "edges": []}

  async def get_insights(self, project_id: str, page: int, limit: int, category: str | None) -> dict:
      return {"items": [], "total": 0, "page": page, "limit": limit}

  async def get_timeline(self, project_id: str) -> list[dict]:
      return []
  ```
- **VALIDATE**: `uv run python -c "import asyncio; from src.services.knowledge import KnowledgeService; from src.config import get_settings; asyncio.run(KnowledgeService.create(get_settings())); print('ok')"`

### Task 9: CREATE src/services/briefing.py

- **IMPLEMENT**: Briefing generation for `prime()` — ≤400 token output
- **FUNCTION SIGNATURE**:
  ```python
  async def generate_briefing(
      project: Project,
      knowledge: KnowledgeService,
      projects: ProjectsService,
  ) -> str:
  ```
- **LOGIC**:
  1. `recent = await projects.get_recent_episodes(project_id, limit=5)`
  2. If `len(recent) == 0` → return early with empty-state message
  3. `decisions = await knowledge.search("key decisions architecture choices", project_id, limit=4)`
  4. `pitfalls = await knowledge.search("errors failures pitfalls issues problems", project_id, limit=3)`
  5. `total_count = await projects.count_episodes(project_id)` (add this method to ProjectsService)
  6. Format output per PRD template (below)
- **OUTPUT FORMAT**:
  ```
  ## Project: {project.name}
  **Stack:** {project.description[:120]}
  **Status:** {total_count} insights stored

  ### Key Decisions
  {for each decision result: "- {entity_name or content[:100]}"}

  ### Known Pitfalls
  {for each pitfall result: "- {entity_name or content[:100]}"}

  ### Last Session
  {for each recent episode: "- [{category}] {content[:80]}"}
  ```
- **EMPTY STATE**: `"## Project: {name}\nNo knowledge stored yet. Use remember() to capture decisions, insights, and errors."`
- **TOKEN BUDGET**: Truncate each line to stay ≤400 tokens total (~300 words). Limit decisions to 4 items, pitfalls to 3, last session to 5.
- **VALIDATE**: `uv run python -c "from src.services.briefing import generate_briefing; print('ok')"`

### Task 10: CREATE src/tools/__init__.py

- **IMPLEMENT**: Central tool registration factory — receives services + queue, registers all 4 tools
- **CONTENT**:
  ```python
  import asyncio
  from fastmcp import FastMCP
  from src.services.knowledge import KnowledgeService
  from src.services.projects import ProjectsService

  def register_tools(
      mcp: FastMCP,
      knowledge: KnowledgeService,
      projects: ProjectsService,
      extraction_queue: asyncio.Queue,
  ) -> None:
      from src.tools.init_project import make_init_project
      from src.tools.remember import make_remember
      from src.tools.recall import make_recall
      from src.tools.prime import make_prime

      make_init_project(mcp, projects)
      make_remember(mcp, knowledge, projects, extraction_queue)
      make_recall(mcp, knowledge, projects)
      make_prime(mcp, knowledge, projects)
  ```
- **VALIDATE**: `uv run python -c "from src.tools import register_tools; print('ok')"`

### Task 11: CREATE src/tools/init_project.py

- **IMPLEMENT**: `init_project` MCP tool — idempotent project creation
- **CONTENT**:
  ```python
  import re, logging
  from fastmcp import FastMCP
  from fastmcp.exceptions import ToolError
  from src.services.projects import ProjectsService

  logger = logging.getLogger(__name__)

  def slugify(name: str) -> str:
      s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
      return re.sub(r"-+", "-", s)[:64]

  def make_init_project(mcp: FastMCP, projects: ProjectsService) -> None:
      @mcp.tool
      async def init_project(
          name: str,
          description: str,
          scan_repo: bool = False,
          repo_path: str | None = None,
      ) -> dict:
          """Create or retrieve a project with its own isolated knowledge graph namespace.

          Idempotent: safe to call multiple times with the same name.
          Returns existing project if name already exists.
          """
          if not name or len(name) > 128:
              raise ToolError("name must be 1–128 characters.")
          if not description or len(description) > 2000:
              raise ToolError("description must be 1–2000 characters.")

          project_id = slugify(name)
          if not project_id:
              raise ToolError("name produces empty slug — use alphanumeric characters.")

          existing = await projects.get(project_id)
          if existing:
              return {"project_id": project_id, "status": "existing",
                      "name": existing.name, "description": existing.description}

          if scan_repo:
              logger.warning("scan_repo=True is not yet implemented (Phase 2). Ignoring.")

          project = await projects.create_project(name, description, repo_path)
          return {"project_id": project.project_id, "status": "created",
                  "name": project.name, "description": project.description}
  ```
- **VALIDATE**: Tool appears in `mcp list-tools` (or server starts successfully)

### Task 12: CREATE src/tools/remember.py

- **IMPLEMENT**: `remember` MCP tool — store knowledge, push to extraction queue
- **NOTE**: No background task management here — just `queue.put()`. The server owns the workers.
- **CONTENT**:
  ```python
  import asyncio, logging
  from typing import Literal
  from fastmcp import FastMCP
  from fastmcp.exceptions import ToolError
  from src.services.knowledge import KnowledgeService
  from src.services.projects import ProjectsService

  logger = logging.getLogger(__name__)

  def make_remember(
      mcp: FastMCP,
      knowledge: KnowledgeService,
      projects: ProjectsService,
      extraction_queue: asyncio.Queue,
  ) -> None:
      @mcp.tool
      async def remember(
          project_id: str,
          content: str,
          category: Literal["decision", "insight", "error", "goal", "architecture"],
      ) -> dict:
          """Store a piece of project knowledge in the persistent knowledge graph.

          Call this whenever you discover something new about an API, make an
          architectural decision, encounter a failure, or receive a new requirement.
          """
          if len(content) < 10:
              raise ToolError("Content must be at least 10 characters.")
          if len(content) > 2000:
              raise ToolError("Content must be 2000 characters or fewer.")

          project = await projects.get(project_id)
          if project is None:
              raise ToolError(f"Project '{project_id}' not found. Call init_project first.")

          episode = await projects.create_episode(project_id, content, category)
          await extraction_queue.put((episode.episode_id, content, category, project_id))

          return {
              "status": "stored",
              "episode_id": episode.episode_id,
              "category": category,
              "processing": "async — graph extraction in progress",
          }
  ```
- **VALIDATE**: `remember` stores episode in SQLite with status=pending; `extraction_queue.qsize()` increases by 1

### Task 13: CREATE src/tools/recall.py

- **IMPLEMENT**: `recall` MCP tool — hybrid search + raw episode fallback
- **CONTENT**:
  ```python
  import logging
  from fastmcp import FastMCP
  from fastmcp.exceptions import ToolError
  from src.services.knowledge import KnowledgeService
  from src.services.projects import ProjectsService

  logger = logging.getLogger(__name__)

  def make_recall(mcp: FastMCP, knowledge: KnowledgeService, projects: ProjectsService) -> None:
      @mcp.tool
      async def recall(project_id: str, query: str) -> str:
          """Search the knowledge graph for specific information.

          Use natural language questions or keyword phrases. Call this when
          unsure if something was already tried or decided.
          """
          if len(query) < 3:
              raise ToolError("Query must be at least 3 characters.")
          if len(query) > 500:
              raise ToolError("Query must be 500 characters or fewer.")

          project = await projects.get(project_id)
          if project is None:
              raise ToolError(f"Project '{project_id}' not found. Call init_project first.")

          # Primary: graph search
          graph_results = await knowledge.search(query, project_id, limit=8)

          # Fallback: search raw pending/processing episodes
          raw_episodes = await projects.get_pending_episodes(project_id)
          query_words = set(query.lower().split())
          raw_matches = [
              ep for ep in raw_episodes
              if any(w in ep.content.lower() for w in query_words)
          ][:3]

          if not graph_results and not raw_matches:
              return "No matching knowledge found for this query."

          lines = [f'### Recall Results: "{query}"', ""]
          if graph_results:
              lines.append("**From knowledge graph:**")
              for r in graph_results[:6]:
                  label = r.entity_name or ""
                  snippet = r.content[:120]
                  lines.append(f"- {label + ': ' if label else ''}{snippet}")
              lines.append("")
          if raw_matches:
              lines.append("**From recent unprocessed episodes:**")
              for ep in raw_matches:
                  lines.append(f"- [{ep.category}] {ep.content[:120]}")

          return "\n".join(lines)
  ```
- **VALIDATE**: After `remember()`, `recall()` with a matching keyword returns the episode content from raw fallback

### Task 14: CREATE src/tools/prime.py

- **IMPLEMENT**: `prime` MCP tool — session briefing, delegates to briefing service
- **CONTENT**:
  ```python
  import logging
  from fastmcp import FastMCP
  from fastmcp.exceptions import ToolError
  from src.services.knowledge import KnowledgeService
  from src.services.projects import ProjectsService
  from src.services.briefing import generate_briefing

  logger = logging.getLogger(__name__)

  def make_prime(mcp: FastMCP, knowledge: KnowledgeService, projects: ProjectsService) -> None:
      @mcp.tool
      async def prime(project_id: str) -> str:
          """Load compressed project context at the start of every coding session.

          Call this immediately when starting work on a project. Returns a structured
          briefing with key decisions, known pitfalls, and recent session summary
          in under 400 tokens.
          """
          project = await projects.get(project_id)
          if project is None:
              raise ToolError(f"Project '{project_id}' not found. Call init_project first.")

          return await generate_briefing(project, knowledge, projects)
  ```
- **VALIDATE**: `prime("test-project")` returns formatted string ≤400 tokens

### Task 15: CREATE src/api/__init__.py and src/api/routes.py

- **IMPLEMENT**: FastAPI router factory with all REST endpoints
- **PATTERN**: `.agents/reference/fastapi.md` — Route Registration Pattern section
- **ROUTES**:
  ```
  GET /api/health                              → {status, falkordb_connected, projects_count}
  GET /api/projects                            → list[Project]
  GET /api/projects/{project_id}               → Project
  GET /api/projects/{project_id}/graph         → {nodes: [], edges: []}
  GET /api/projects/{project_id}/insights      → {items: [], total, page, limit}
  GET /api/projects/{project_id}/timeline      → []
  ```
- **HEALTH RESPONSE** (exact format for validation checklist):
  ```json
  {"status": "ok", "falkordb_connected": true, "projects_count": 0}
  ```
- **CONTENT**:
  ```python
  from fastapi import APIRouter, HTTPException
  from src.services.knowledge import KnowledgeService
  from src.services.projects import ProjectsService

  def create_router(knowledge: KnowledgeService, projects: ProjectsService) -> APIRouter:
      router = APIRouter()

      @router.get("/health")
      async def health():
          ok = await knowledge.check_connection()
          count = await projects.count()
          return {"status": "ok" if ok else "degraded", "falkordb_connected": ok, "projects_count": count}

      @router.get("/projects")
      async def list_projects():
          return await projects.list_all()

      @router.get("/projects/{project_id}")
      async def get_project(project_id: str):
          p = await projects.get(project_id)
          if not p:
              raise HTTPException(404, detail=f"Project '{project_id}' not found")
          return p

      @router.get("/projects/{project_id}/graph")
      async def get_graph(project_id: str):
          await _require_project(project_id, projects)
          return await knowledge.get_graph_data(project_id)

      @router.get("/projects/{project_id}/insights")
      async def get_insights(project_id: str, page: int = 1, limit: int = 20, category: str = None):
          await _require_project(project_id, projects)
          return await knowledge.get_insights(project_id, page, limit, category)

      @router.get("/projects/{project_id}/timeline")
      async def get_timeline(project_id: str):
          await _require_project(project_id, projects)
          return await knowledge.get_timeline(project_id)

      return router

  async def _require_project(project_id: str, projects: ProjectsService):
      if not await projects.get(project_id):
          raise HTTPException(404, detail=f"Project '{project_id}' not found")
  ```
- **VALIDATE**: `curl http://localhost:8080/api/health` returns `{"status":"ok","falkordb_connected":true,"projects_count":0}`

### Task 16: CREATE src/server.py

- **IMPLEMENT**: Dual-transport entry point — FastMCP + FastAPI, queue workers, startup, graceful shutdown
- **STARTUP ORDER** (strict — logging FIRST):
  1. `logging.basicConfig(stream=sys.stderr, ...)` — before anything logs
  2. Load `MCP_ENV_FILE` if set (via `python-dotenv` `load_dotenv()`)
  3. `settings = get_settings()` — fail fast on bad config
  4. `projects = await ProjectsService.create(settings)` — init SQLite + create tables
  5. `knowledge = await KnowledgeService.create(settings)` — connect FalkorDB with retry
  6. Create `extraction_queue: asyncio.Queue()`
  7. Start `settings.extraction_workers` worker coroutines as tasks
  8. `register_tools(mcp, knowledge, projects, extraction_queue)` — bind tool handlers
  9. `app.include_router(create_router(knowledge, projects), prefix="/api")` — bind REST routes
  10. Add CORS middleware
  11. `asyncio.gather(mcp.run_async(), http_server.serve())` — start both servers

- **WORKER STARTUP**:
  ```python
  worker_tasks = []
  for _ in range(settings.extraction_workers):
      t = asyncio.create_task(_extraction_worker(extraction_queue, knowledge, projects))
      worker_tasks.append(t)
  ```

- **EXTRACTION WORKER** (defined in server.py, NOT in remember.py):
  ```python
  async def _extraction_worker(queue: asyncio.Queue, knowledge: KnowledgeService, projects: ProjectsService):
      logger.info("Extraction worker started")
      while True:
          item = await queue.get()
          if item is None:   # shutdown sentinel
              queue.task_done()
              return
          episode_id, content, category, project_id = item
          try:
              await projects.update_episode_status(episode_id, "processing")
              gid = await knowledge.add_episode(episode_id, content, category, project_id)
              await projects.update_episode_status(episode_id, "complete", gid)
              logger.info(f"Extraction complete: {episode_id}")
          except Exception as e:
              logger.error(f"Extraction failed {episode_id}: {e}", exc_info=True)
              await projects.update_episode_status(episode_id, "failed")
          finally:
              queue.task_done()
  ```

- **GRACEFUL SHUTDOWN** (SIGTERM/SIGINT):
  ```python
  import signal

  def handle_shutdown(sig, frame):
      logger.info(f"Signal {sig} received — initiating shutdown")
      http_server.should_exit = True

  signal.signal(signal.SIGTERM, handle_shutdown)
  signal.signal(signal.SIGINT, handle_shutdown)

  try:
      await asyncio.gather(mcp.run_async(), http_server.serve())
  finally:
      logger.info("Draining extraction queue (30s timeout)...")
      for _ in range(settings.extraction_workers):
          await extraction_queue.put(None)  # sentinel per worker
      try:
          await asyncio.wait_for(extraction_queue.join(), timeout=30.0)
      except asyncio.TimeoutError:
          logger.warning("Extraction queue drain timed out after 30s")
      for t in worker_tasks:
          t.cancel()
      logger.info("Shutdown complete")
  ```

- **UVICORN CONFIG** (exact settings — do not change):
  ```python
  uvicorn.Config(
      app=app,
      host=settings.uvicorn_host,   # "127.0.0.1" from settings
      port=settings.http_port,       # 8080
      loop="asyncio",
      workers=1,
      log_config=None,
      access_log=False,
  )
  ```

- **ENTRY POINTS**:
  ```python
  def main():
      asyncio.run(main_async())

  if __name__ == "__main__":
      main()
  ```

- **MCP_ENV_FILE handling** (before `get_settings()`):
  ```python
  import os
  from dotenv import load_dotenv
  env_file = os.environ.get("MCP_ENV_FILE")
  if env_file:
      load_dotenv(env_file, override=True)
  ```

- **VALIDATE**: `uv run python -m src.server` starts without crashing (with FalkorDB running); `curl http://localhost:8080/api/health` returns `{"status":"ok","falkordb_connected":true,"projects_count":0}`

### Task 17: VERIFY no print() calls

- **VALIDATE**: `grep -rn "print(" src/` returns nothing

### Task 18: ADD pytest-asyncio dependency and stub tests

- **ADD to pyproject.toml**: `"pytest-asyncio>=0.23"` in dev dependencies
- **CREATE tests/__init__.py** (empty)
- **CREATE tests/test_smoke.py**:
  ```python
  """Smoke tests — verify imports and basic model validation."""
  import pytest
  from src.models import Project, Episode, SearchResult
  from src.tools.init_project import slugify
  from datetime import datetime, timezone

  def test_slugify():
      assert slugify("My SaaS App") == "my-saas-app"
      assert slugify("Hello World!") == "hello-world"
      assert slugify("test") == "test"

  def test_episode_model():
      ep = Episode(
          episode_id="ep_abc123",
          project_id="test",
          content="test content",
          category="decision",
          status="pending",
          created_at=datetime.now(timezone.utc),
      )
      assert ep.episode_id == "ep_abc123"

  def test_project_model():
      p = Project(
          project_id="test",
          name="Test",
          description="desc",
          created_at=datetime.now(timezone.utc),
      )
      assert p.project_id == "test"
  ```
- **VALIDATE**: `uv run pytest tests/ -v` all pass

---

## TESTING STRATEGY

### Unit Tests
- `tests/test_smoke.py` — imports, model validation, slugify
- `tests/test_config.py` — Settings loads with defaults (no env file needed)

### Integration Tests (require running FalkorDB)
- `tests/test_integration.py` — Full flow: init_project → remember → recall → prime
- Mark with `@pytest.mark.integration` and skip if FalkorDB not running

### Edge Cases
- `init_project` twice with same name → `status: "existing"` (idempotent)
- `recall` before extraction completes → raw fallback returns episode content
- FalkorDB down on startup → RuntimeError after 5 retries with clear message
- `content` of exactly 10 chars → valid; 9 chars → ToolError
- `remember` with `project_id` for non-existent project → ToolError

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```bash
uv run ruff check src/
uv run ruff format src/ --check
grep -rn "print(" src/    # Must return nothing
```

### Level 2: Unit Tests
```bash
uv run pytest tests/ -v -m "not integration"
```

### Level 3: Infrastructure
```bash
docker compose up -d
sleep 3
docker compose ps    # falkordb must show (healthy)
docker exec agent-harness-falkordb redis-cli ping   # PONG
```

### Level 4: Service Start + Health Check
```bash
uv run python -m src.server &
SERVER_PID=$!
sleep 5
curl http://localhost:8080/api/health
# Expected: {"status":"ok","falkordb_connected":true,"projects_count":0}
curl http://localhost:8080/api/projects
# Expected: []
kill $SERVER_PID
```

### Level 5: End-to-End Service Layer Test
```bash
uv run python -c "
import asyncio
from src.config import get_settings
from src.services.projects import ProjectsService
from src.services.knowledge import KnowledgeService
from src.services.briefing import generate_briefing
from src.tools.init_project import slugify

async def test():
    s = get_settings()
    projects = await ProjectsService.create(s)
    knowledge = await KnowledgeService.create(s)

    pid = slugify('Test Project')
    p = await projects.create_project('Test Project', 'A test project for Phase 1 validation')
    print(f'Project created: {p.project_id}')

    ep = await projects.create_episode(pid, 'Use JWT for auth because Supabase RLS is incompatible with service-role keys', 'decision')
    print(f'Episode stored: {ep.episode_id} status={ep.status}')

    briefing = await generate_briefing(p, knowledge, projects)
    print(f'Briefing preview: {briefing[:200]}')
    print('All checks passed.')

asyncio.run(test())
"
```

---

## ACCEPTANCE CRITERIA

- [ ] `uv sync` installs all dependencies without error
- [ ] `docker compose up -d && docker compose ps` shows FalkorDB (healthy)
- [ ] `uv run python -m src.server` starts without error (with FalkorDB running)
- [ ] `curl http://localhost:8080/api/health` returns exact format: `{"status":"ok","falkordb_connected":true,"projects_count":0}`
- [ ] All 4 MCP tools are registered and appear in server schema
- [ ] `init_project("Test", "desc")` returns `{"project_id":"test","status":"created",...}`
- [ ] Calling `init_project` again with same name returns `{"status":"existing",...}`
- [ ] `remember` returns immediately with `{"status":"stored",...}` and item is on extraction queue
- [ ] `recall` returns raw episode content for pending episodes (fallback path works)
- [ ] `prime` returns formatted briefing ≤400 tokens
- [ ] `grep -rn "print(" src/` returns nothing
- [ ] `uv run ruff check src/` returns zero errors
- [ ] `uv run pytest tests/ -v -m "not integration"` all pass
- [ ] `docker-compose.yml` has NO `ports:` mapping under falkordb
- [ ] `.env.example` has NO real API keys (only placeholder strings)
- [ ] Uvicorn binds only to `127.0.0.1` (from settings, never hardcoded `0.0.0.0`)

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in dependency order (1 → 18)
- [ ] Each task validated immediately after implementation
- [ ] Level 1–5 validation commands all pass
- [ ] No regressions (no print(), no 0.0.0.0, no ports: in compose)
- [ ] Health endpoint matches exact expected format

---

## NOTES

### Key Design Decisions

**Per-project Graphiti instance (not global with group_id filter):** Using `database=project_id` in FalkorDriver gives true graph-level isolation — no cross-project contamination is possible even without `group_id` filters. We still pass `group_id` as a safety belt. Graphiti instances are lazily created on first project access and cached in a dict on `KnowledgeService`.

**asyncio.Queue + worker pool in server.py:** Avoids circular imports (remember.py → server.py → remember.py). Clean shutdown via `queue.join()`. Worker count controlled by `EXTRACTION_WORKERS` setting (default 4).

**Extraction worker in server.py:** The worker function lives in `server.py`, not in `remember.py`, because it needs to await `knowledge.add_episode()` and `projects.update_episode_status()` — both of which are services that the server owns. The `remember.py` tool just does `await queue.put(...)`.

**scan_repo=True silently ignored in Phase 1:** Log a warning, return success. Real scanner is Phase 2.

**REST data methods return empty in Phase 1:** `/graph`, `/insights`, `/timeline` return empty structures. Routes must exist for the server to start and health check to work, but real data queries are Phase 2.

**MCP_ENV_FILE**: MCP server processes don't inherit shell environment. If users set `MCP_ENV_FILE=/abs/path/.env` in their mcp.json `env` block, we load it before `get_settings()` is called. This is the recommended pattern for Claude Code MCP integration.

### Confidence Score: 9.5/10

All three original risks are resolved with verified findings. API shapes are confirmed, architectural patterns are clear, and all integration points are documented. The only residual uncertainty is the exact FalkorDriver `database=` string behavior — if it doesn't accept strings (only integers), fall back to `database=0` (single database) and rely solely on `group_id` for isolation.
