# FastAPI + Uvicorn Dual Transport Reference — Agent Harness

> **FastAPI version:** Latest stable (0.115+)
> **Uvicorn version:** Latest stable (0.32+)
> **Pattern:** `asyncio.gather(mcp.run_async(), uvicorn.Server(config).serve())`
> **HTTP binding:** `127.0.0.1:8080` (localhost only — never 0.0.0.0)

---

## Overview

Agent Harness runs two servers in a single process:

1. **FastMCP** — stdio transport on stdin/stdout (for Claude Code)
2. **FastAPI + Uvicorn** — HTTP REST on `127.0.0.1:8080` (for dashboard)

Both run concurrently in the same asyncio event loop via `asyncio.gather()`. They share the same `KnowledgeService` and `ProjectsService` instances.

---

## Dual Transport Architecture

```python
# src/server.py

import asyncio
import sys
import logging

import uvicorn
from fastmcp import FastMCP
from fastapi import FastAPI

from src.config import get_settings
from src.api.routes import create_router
from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService

# Configure logging to stderr BEFORE anything else
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- MCP Server ---
mcp = FastMCP("agent-harness", version="0.1.0")

# --- REST API ---
app = FastAPI(
    title="Agent Harness",
    description="Persistent knowledge graph memory for AI coding agents",
    version="0.1.0",
)


async def startup():
    """Initialize services shared by both servers."""
    settings = get_settings()

    # Init services (with FalkorDB retry logic)
    knowledge = await KnowledgeService.create(settings)
    projects = await ProjectsService.create(settings)

    # Store on app state for REST routes
    app.state.knowledge = knowledge
    app.state.projects = projects

    # Attach tools to MCP (pass services via closure or global)
    from src.tools import register_tools
    register_tools(mcp, knowledge, projects)

    # Register REST routes
    app.include_router(create_router(knowledge, projects), prefix="/api")

    logger.info("Agent Harness startup complete")


async def main_async():
    settings = get_settings()

    await startup()

    # Uvicorn config — MUST bind to 127.0.0.1
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",    # Never 0.0.0.0
        port=settings.http_port,   # Default: 8080
        loop="asyncio",       # Use the current event loop
        workers=1,            # Required for programmatic mode (no multiprocessing)
        log_config=None,      # Don't let Uvicorn override our logging config
        access_log=False,     # Reduce noise in MCP stdio mode
    )
    server = uvicorn.Server(config)

    # Run both transports concurrently in the same event loop
    await asyncio.gather(
        mcp.run_async(),    # FastMCP reads stdin, writes stdout
        server.serve(),      # FastAPI serves HTTP on 127.0.0.1:8080
    )


def main():
    """Entry point for `uvx agent-harness` and console_scripts."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
```

---

## Uvicorn Configuration

### Critical Settings

```python
config = uvicorn.Config(
    app=app,
    host="127.0.0.1",    # CRITICAL: localhost only. Never "0.0.0.0"
    port=8080,
    loop="asyncio",       # CRITICAL: must match asyncio.run() event loop
    workers=1,            # CRITICAL: no multiprocessing in programmatic mode
    log_config=None,      # Prevents Uvicorn overriding our stderr logging
)
```

**Why `loop="asyncio"`:** Uvicorn defaults to its own event loop. Setting `loop="asyncio"` makes it use the running event loop from `asyncio.gather()` instead of creating a new one.

**Why `workers=1`:** `uvicorn.Server(config).serve()` is programmatic mode. Multiple workers use multiprocessing, which conflicts with the coroutine-based approach. For scaling, put a load balancer in front of multiple Agent Harness processes.

**Why `127.0.0.1`:** The REST API exposes internal data. Binding to `0.0.0.0` would expose it on all network interfaces (including external), which is a security risk. The Lovable dashboard connects via localhost.

---

## REST API Routes

### Route Registration Pattern

```python
# src/api/routes.py

from fastapi import APIRouter, HTTPException, Depends
from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService


def create_router(
    knowledge: KnowledgeService,
    projects: ProjectsService,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health():
        falkordb_ok = await knowledge.check_connection()
        return {
            "status": "ok" if falkordb_ok else "degraded",
            "falkordb_connected": falkordb_ok,
            "projects_count": await projects.count(),
        }

    @router.get("/projects")
    async def list_projects():
        return await projects.list_all()

    @router.get("/projects/{project_id}")
    async def get_project(project_id: str):
        project = await projects.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        return project

    @router.get("/projects/{project_id}/graph")
    async def get_graph(project_id: str):
        project = await projects.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        return await knowledge.get_graph_data(project_id)

    @router.get("/projects/{project_id}/insights")
    async def get_insights(project_id: str, page: int = 1, limit: int = 20, category: str = None):
        project = await projects.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        return await knowledge.get_insights(project_id, page=page, limit=limit, category=category)

    @router.get("/projects/{project_id}/timeline")
    async def get_timeline(project_id: str):
        project = await projects.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        return await knowledge.get_timeline(project_id)

    return router
```

### Route Summary

```
GET  /api/health                              → Service status + FalkorDB connection
GET  /api/projects                            → List all projects with stats
GET  /api/projects/{project_id}               → Project details
GET  /api/projects/{project_id}/graph         → Nodes + edges for graph visualization
GET  /api/projects/{project_id}/insights      → Paginated knowledge items (filterable by category)
GET  /api/projects/{project_id}/timeline      → Chronological episode list
```

---

## CORS Configuration

For the Lovable dashboard (Phase 4):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origins],   # e.g., "http://localhost:3000"
    allow_credentials=False,
    allow_methods=["GET"],       # Read-only dashboard
    allow_headers=["*"],
)
```

**Note:** In `.env`:
```env
ALLOWED_ORIGINS=http://localhost:3000
```

---

## Graceful Shutdown

Both Uvicorn and FastMCP need to be shut down cleanly on SIGTERM/SIGINT:

```python
import signal
import asyncio

async def main_async():
    settings = get_settings()
    await startup()

    # Create Uvicorn server
    config = uvicorn.Config(app=app, host="127.0.0.1", port=settings.http_port,
                            loop="asyncio", workers=1, log_config=None)
    http_server = uvicorn.Server(config)

    # Background task registry (prevent GC)
    _background_tasks: set = set()

    # Shutdown handler
    shutdown_event = asyncio.Event()

    def handle_shutdown(sig, frame):
        logger.info(f"Received {signal.Signals(sig).name}, initiating graceful shutdown...")
        shutdown_event.set()
        http_server.should_exit = True   # Signal Uvicorn to stop

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    try:
        await asyncio.gather(
            mcp.run_async(),
            http_server.serve(),
        )
    finally:
        # Await background extraction tasks (30s timeout)
        if _background_tasks:
            logger.info(f"Waiting for {len(_background_tasks)} background tasks...")
            await asyncio.wait_for(
                asyncio.gather(*_background_tasks, return_exceptions=True),
                timeout=30.0,
            )
        logger.info("Shutdown complete")
```

---

## Health Check Endpoint

This is used for the validation checklist before every commit:

```bash
curl http://localhost:8080/api/health
```

Expected response:
```json
{
  "status": "ok",
  "falkordb_connected": true,
  "projects_count": 3
}
```

Degraded state (FalkorDB unreachable):
```json
{
  "status": "degraded",
  "falkordb_connected": false,
  "projects_count": 0
}
```

---

## Startup Sequence

```python
# src/server.py — startup order matters

async def startup():
    settings = get_settings()  # 1. Load + validate config (fail fast on missing vars)

    await ProjectsService.init_db(settings)  # 2. Initialize SQLite (create tables)

    knowledge = await KnowledgeService.create(settings)  # 3. Connect FalkorDB (with retry)
    #   └─ FalkorDB retry: 5 attempts, delays [1, 2, 4, 8, 15]s
    #   └─ Calls graphiti.build_indices_and_constraints()  # 4. Init graph schema

    projects = await ProjectsService.create(settings)  # 5. Init project service

    register_tools(mcp, knowledge, projects)  # 6. Register MCP tools
    app.include_router(...)                   # 7. Register REST routes

    logger.info("Startup complete — ready for connections")
```

---

## Development vs Production

### Development

```bash
# Run directly (hot reload via watchfiles if needed)
uv run python -m src.server

# With file watching for development
uv run watchfiles "python -m src.server" src/
```

### Production (via uvx)

```bash
# Users install and run via uvx — no code changes needed
uvx agent-harness
```

### Health verification

```bash
# After starting, verify both transports work
curl http://localhost:8080/api/health
# → {"status":"ok","falkordb_connected":true}

# MCP transport is verified automatically when Claude Code connects
```

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `RuntimeError: Event loop closed` | Uvicorn creating new loop | Set `loop="asyncio"` in Config |
| Port 8080 already in use | Previous server process running | `lsof -i :8080 \| kill $(awk 'NR>1 {print $2}')` |
| CORS errors from dashboard | `ALLOWED_ORIGINS` not set | Add `ALLOWED_ORIGINS=http://localhost:3000` to `.env` |
| Uvicorn logs on stdout | Default Uvicorn log config | Set `log_config=None` in Config |
| REST API accessible externally | Bound to `0.0.0.0` | Always use `host="127.0.0.1"` |

---

*See also: [FastMCP reference](.agents/reference/mcp-server.md) for tool definitions and MCP-specific patterns.*
