# FastMCP Reference — Agent Harness

> **Version:** fastmcp 3.1.1 (March 14, 2026)
> **Install:** `pip install fastmcp`
> **License:** Apache 2.0
> **Python:** 3.10+
> **CRITICAL:** v3.0 (Feb 18, 2026) was a major breaking change from v2 — pin to `fastmcp>=3.0,<4.0`

---

## Overview

FastMCP is the Python framework for building MCP (Model Context Protocol) servers. Agent Harness uses it to expose 4 tools to Claude Code via stdio transport. FastMCP handles:

- JSON-RPC message framing on stdin/stdout
- Tool schema generation from type hints and docstrings
- Error propagation to the MCP client
- Progress reporting via Context injection

**CRITICAL RULE: ALL logging MUST go to `stderr`. stdout is the MCP protocol channel. Any `print()` or log output to stdout corrupts the JSON-RPC stream and causes client errors.**

---

## Installation & Version Pinning

```toml
# pyproject.toml
[project]
dependencies = [
    "fastmcp>=3.0,<4.0",   # Pin to major version — breaking changes between majors
    ...
]
```

```bash
# Install
uv add "fastmcp>=3.0,<4.0"
```

Why pin the major version: FastMCP v3.0 had breaking API changes from v2. Future major versions may have similar breaking changes. Pin to prevent silent breakage when running via `uvx`.

---

## Basic Server Setup

```python
from fastmcp import FastMCP

mcp = FastMCP(
    name="agent-harness",
    version="0.1.0",
)
```

---

## Defining Tools

### Simple Tool

```python
@mcp.tool
async def prime(project_id: str) -> str:
    """Load compressed project context at the start of every coding session.

    Call this immediately when starting work on a project. Returns a structured
    briefing with key decisions, known pitfalls, and recent session summary
    in under 400 tokens.
    """
    # Implementation
    return briefing_text
```

**Tool schema is auto-generated from:**
- **Name:** function name (`prime`)
- **Description:** first line of docstring (shown to LLM)
- **Parameters:** function type hints → JSON schema
- **Required:** parameters without defaults

### Tool with Multiple Parameters

```python
@mcp.tool
async def remember(
    project_id: str,
    content: str,
    category: str,
) -> dict:
    """Store a piece of project knowledge in the persistent knowledge graph.

    Call this whenever you discover something new about an API, make an
    architectural decision, encounter a failure, or receive a new requirement.
    """
    # Validation
    if category not in VALID_CATEGORIES:
        raise ToolError(f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}")

    # Implementation
    return {"status": "stored", "episode_id": ep_id}
```

### Tool with Optional Parameters

```python
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
    ...
```

---

## Error Handling

### ToolError

Use `ToolError` to return structured errors to the MCP client (Claude Code sees this as a tool error, not a crash):

```python
from fastmcp.exceptions import ToolError

@mcp.tool
async def prime(project_id: str) -> str:
    """..."""
    project = await projects_service.get(project_id)
    if project is None:
        raise ToolError(
            f"Project '{project_id}' not found. Call init_project first."
        )
    return await generate_briefing(project)
```

**ToolError vs exceptions:**
- `ToolError`: Expected errors — validation failures, not-found, user mistakes. Returned to Claude as a readable error message.
- Unhandled exceptions: Server crashes, programming errors. FastMCP converts these to MCP error responses but with less context.

### Error Response Pattern

Match the error format from the PRD:

```python
# PRD-specified error format
raise ToolError('{"error": "project_not_found", "message": "Project \'x\' not found. Call init_project first."}')

# Or simpler string format (FastMCP will wrap it)
raise ToolError("Project 'x' not found. Call init_project first.")
```

---

## Context Injection

For long-running operations, inject `Context` to report progress:

```python
from fastmcp import Context

@mcp.tool
async def init_project(
    name: str,
    description: str,
    scan_repo: bool = False,
    ctx: Context = None,   # Injected by FastMCP — not part of tool schema
) -> dict:
    """..."""
    if scan_repo and ctx:
        await ctx.report_progress(0, 100, "Starting repo scan...")

    result = await do_init(name, description)

    if scan_repo:
        if ctx:
            await ctx.report_progress(50, 100, "Scanning repository...")
        await scan_repository(result.project_id)
        if ctx:
            await ctx.report_progress(100, 100, "Scan complete")

    return result
```

**Note:** `ctx: Context` is automatically excluded from the tool's JSON schema — Claude won't see it as a parameter.

---

## Logging (CRITICAL)

**NEVER use `print()` in MCP server code. NEVER log to stdout.**

```python
import logging
import sys

# Configure ALL logging to stderr
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,   # CRITICAL: stderr, not stdout
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

# CORRECT: logs go to stderr
logger.info("Server starting up")
logger.error("FalkorDB connection failed", exc_info=True)

# WRONG: corrupts MCP protocol
print("Server starting")              # BAD - writes to stdout
logging.basicConfig(stream=sys.stdout)  # BAD - logs to stdout
```

**Why:** FastMCP reads JSON-RPC messages from stdin and writes responses to stdout. Any non-JSON text on stdout causes the JSON parser in the MCP client (Claude Code) to fail, breaking all tool calls.

---

## Transport Modes

### stdio (Default — Required for Claude Code)

```python
# Sync entry point (for main())
def main():
    mcp.run()   # Runs stdio transport in current thread

# Async entry point (for dual-transport with FastAPI)
async def run_mcp():
    await mcp.run_async()   # Async version for asyncio.gather
```

Claude Code launches Agent Harness as:
```bash
uvx agent-harness
```
And communicates via stdin/stdout (stdio transport).

### SSE (Server-Sent Events — Optional)

```python
# For web-based MCP clients (not Claude Code)
mcp.run(transport="sse", host="127.0.0.1", port=8765)
```

---

## Dual Transport with FastAPI

Agent Harness runs both FastMCP (stdio) and FastAPI (HTTP) in the same process:

```python
import asyncio
import uvicorn
from fastmcp import FastMCP
from fastapi import FastAPI

mcp = FastMCP("agent-harness")
app = FastAPI()

async def main_async():
    # Configure Uvicorn (MUST bind to 127.0.0.1)
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",  # Never 0.0.0.0 — local dashboard only
        port=8080,
        loop="asyncio",    # Use current event loop
        workers=1,         # Required for programmatic mode
        log_config=None,   # Prevent Uvicorn from hijacking log config
    )
    server = uvicorn.Server(config)

    # Run both in same event loop
    await asyncio.gather(
        mcp.run_async(),        # FastMCP stdio
        server.serve(),          # FastAPI HTTP
    )

def main():
    asyncio.run(main_async())
```

**Why asyncio.gather works:** FastMCP uses anyio internally, which is compatible with the asyncio backend. Both coroutines run concurrently in the same event loop.

---

## pyproject.toml Entry Point

```toml
[project.scripts]
agent-harness = "src.server:main"
```

This enables:
```bash
# Direct execution
uv run python -m src.server

# Via PyPI (after publish)
uvx agent-harness

# Via installed package
agent-harness
```

---

## MCP Client Configuration (Claude Code)

Add to `~/.claude/mcp.json` (or project-level `.mcp.json`):

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

**Note:** MCP server processes do NOT inherit the shell environment. All env vars must be explicitly listed in the `env` block, or use `MCP_ENV_FILE` to point to an absolute path:

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

---

## Tool Schema Validation

FastMCP auto-generates JSON Schema from type hints:

| Python Type | JSON Schema |
|-------------|-------------|
| `str` | `{"type": "string"}` |
| `int` | `{"type": "integer"}` |
| `bool` | `{"type": "boolean"}` |
| `float` | `{"type": "number"}` |
| `list[str]` | `{"type": "array", "items": {"type": "string"}}` |
| `dict` | `{"type": "object"}` |
| `str \| None` | `{"type": "string", "nullable": true}` |
| `Literal["a", "b"]` | `{"type": "string", "enum": ["a", "b"]}` |

For category enum validation:

```python
from typing import Literal

@mcp.tool
async def remember(
    project_id: str,
    content: str,
    category: Literal["decision", "insight", "error", "goal", "architecture"],
) -> dict:
    """..."""
```

---

## Complete Tool Handler Pattern

```python
import logging
import sys
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

logger = logging.getLogger(__name__)

# Configure logging to stderr BEFORE creating FastMCP instance
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

mcp = FastMCP("agent-harness", version="0.1.0")

@mcp.tool
async def recall(project_id: str, query: str) -> str:
    """Search the knowledge graph for specific information.

    Use natural language questions or keyword phrases. Call this when unsure
    if something was already tried or decided.
    """
    # Validate
    if len(query) < 3:
        raise ToolError("Query must be at least 3 characters.")
    if len(query) > 500:
        raise ToolError("Query must be 500 characters or fewer.")

    # Check project exists
    project = await projects_service.get(project_id)
    if project is None:
        raise ToolError(f"Project '{project_id}' not found. Call init_project first.")

    # Execute search
    try:
        results = await knowledge_service.search(
            query=query,
            project_id=project_id,
        )
    except Exception as e:
        logger.error(f"Search failed for project {project_id}: {e}", exc_info=True)
        raise ToolError("Search failed. Check server logs for details.")

    if not results:
        return "No matching knowledge found for this query."

    return format_search_results(results)  # Max 300-500 tokens
```

---

## Testing Tools (In-Process)

FastMCP v3 supports in-process testing without spawning a subprocess.

### Calling tools in tests

```python
import asyncio
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

# Call a registered tool
result = await mcp.call_tool("prime", {"project_id": "my-project"})
# result.content[0].text  → str output
# result.structured_content → dict output (if tool returns dict)

# ToolError is re-raised as an exception from call_tool
with pytest.raises(ToolError):
    await mcp.call_tool("prime", {"project_id": "nonexistent"})
```

### Inspecting tool schemas

```python
tools = await mcp.list_tools()
# Returns list of FunctionTool objects

tool = next(t for t in tools if t.name == "remember")

# Access JSON schema via .parameters (NOT .inputSchema — that attribute does not exist in v3)
params = tool.parameters.get("properties", {})   # dict of param name → schema
required = tool.parameters.get("required", [])   # list of required param names
```

**Important:** FastMCP v3 uses `tool.parameters` (snake_case dict), not `tool.inputSchema`. Using `inputSchema` raises `AttributeError`.

---

## Version Compatibility Notes

| Version | Status | Notes |
|---------|--------|-------|
| 3.1.x | Current (use this) | Stable API |
| 3.0.x | Minimum supported | Major API overhaul from v2 |
| 2.x | DO NOT USE | Incompatible API |
| 1.x | DO NOT USE | Pre-release |

Always check `fastmcp --version` after installation to confirm v3.x.

---

*See also: [FastAPI reference](.agents/reference/fastapi.md) for dual transport setup.*
