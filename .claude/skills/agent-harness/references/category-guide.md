# Category Guide

Choose the category that best describes the *type* of knowledge being stored.

## decision
A choice between alternatives, with rationale. Should explain what options were
considered and why this one won.

**Use for:**
- "Chose X over Y because Z"
- "Decided to NOT do X because Y"
- "Reversed prior X decision — now using Y because Z"

**Examples:**
- "Chose asyncio.Queue over semaphore for extraction workers: Queue provides
  natural backpressure; semaphore doesn't buffer — rejected tasks would be lost"
- "Decided against LLM consolidation pass for Phase 2 — rule-based pruning
  delivers 80% of the benefit at 10% of the complexity and risk"

## insight
Observed behavior of an API, library, or system that isn't obvious from docs,
or that contradicts the documented behavior.

**Use for:**
- "Library X does Y when you expect Z"
- "API call X requires parameter Y even though docs say it's optional"
- "Pattern X doesn't work with framework version Y"

**Examples:**
- "Graphiti search() returns list[EntityEdge], not a SearchResults object —
  the official docs show an incorrect return type"
- "graphiti_core imports load_dotenv() at module import time — any test that
  imports graphiti will load the project .env and override test defaults"

## error
An approach that was tried and failed. Records what was attempted, why it
failed, and why it shouldn't be retried.

**Use for:**
- "Tried X — failed because Y — don't retry"
- "Approach X causes Y error in Z context"

**Examples:**
- "Binding FalkorDB ports without '127.0.0.1:' prefix doesn't bridge to
  localhost on Linux Docker — traffic doesn't reach the container"
- "Using patch('src.services.knowledge.FalkorDB') fails because FalkorDB is
  a local import inside function bodies — patch 'falkordb.FalkorDB' instead"

## goal
A requirement, constraint, or objective that future agents must respect.
Not a decision (no alternatives were weighed) — just a constraint.

**Use for:**
- "Must do X"
- "Never do Y"
- "X must stay under Y"

**Examples:**
- "HTTP server must bind to 127.0.0.1 only — never 0.0.0.0 in any environment"
- "MCP server must never print() to stdout — corrupts JSON-RPC protocol"
- "FastMCP must be pinned to >=3.0,<4.0 — v3 was a breaking change from v2"

## architecture
How the system is structured. Relationships between components. Why the system
is designed the way it is (if the reason is architectural, not a specific choice).

**Use for:**
- "Component X connects to Y via Z"
- "System is organized as X because Y"
- "The {concept} in this system means {specific definition}"

**Examples:**
- "FalkorDB graph name is the sanitized group_id (hyphens→underscores) —
  Graphiti's add_episode() calls driver.clone(database=group_id)"
- "Both FastMCP (stdio) and FastAPI (HTTP :8080) run in the same process
  via asyncio.gather() — not separate services"
- "Namespace isolation: each project = its own FalkorDB graph; _graphiti_group_id()
  converts project_id hyphens to underscores before every Graphiti call"
