# What to Remember

## Contents
- [The Quality Test](#the-quality-test)
- [What to Remember (Good Examples)](#what-to-remember-good-examples)
- [What NOT to Remember (Anti-patterns)](#what-not-to-remember-anti-patterns)
- [The Boundary Cases](#the-boundary-cases)

## The Quality Test

Before calling `remember()`, ask:
> "Would a future agent, starting this project from scratch, need this fact in
> the first 30 seconds?"

A future agent has: access to the codebase, ability to grep/read files, general
coding knowledge. It does NOT have: the reasoning behind past decisions, known
pitfalls discovered in practice, architectural tradeoffs considered and rejected.

## What to Remember (Good Examples)

**Decisions with rationale and alternatives considered:**
- "Chose asyncio.Queue over threading.Lock for extraction workers because the
  async event loop already manages concurrency — threading would cause GIL
  contention with aiosqlite"
- "Selected SQLite over PostgreSQL for project metadata: multi-server deployment
  not needed in current scope; simplifies dev setup significantly"

**API/library behavior not documented or surprising:**
- "Graphiti search() returns list[EntityEdge], not a SearchResults object —
  official docs show wrong return type"
- "FalkorDB Python client is synchronous — must wrap all data queries in
  asyncio.to_thread() or the event loop blocks"

**Errors that took time to debug and shouldn't be repeated:**
- "Hyphens in project_id break Graphiti/RediSearch — RediSearch treats '-' as
  NOT operator. Always replace with underscores before passing as group_id"
- "MCP server print() to stdout corrupts the JSON-RPC protocol — all logging
  must use stderr"

**Goals or constraints that aren't obvious from the code:**
- "Must keep uvicorn bound to 127.0.0.1 — 0.0.0.0 exposes the API externally
  in our deployment environment"

**Architecture decisions that constrain future work:**
- "FalkorDB graph name IS the sanitized group_id (hyphens→underscores) —
  Graphiti's add_episode() calls driver.clone(database=group_id)"

## What NOT to Remember (Anti-patterns)

**In-progress work** — Not a decision, will be obsolete in minutes:
- ❌ "Currently implementing the consolidate() tool"
- ❌ "Working on fixing the briefing cache bug"

**Facts visible in the codebase** — A future agent can grep for these:
- ❌ "The project uses Python 3.11" (visible in pyproject.toml)
- ❌ "There are 148 tests" (run `uv run pytest --collect-only` to count)
- ❌ "The entry point is src.server:main" (visible in pyproject.toml)

**Transient debug steps** — Not reusable knowledge:
- ❌ "Ran the test suite — all 148 tests passing"
- ❌ "Checked docker compose ps — falkordb shows healthy"
- ❌ "Grepped for print() calls — none found"

**Log entries and status updates** — These belong in commit messages, not the graph:
- ❌ "Completed Phase 5 — temporal filtering and forget tool"
- ❌ "Fixed the FalkorDB group_id bug"

## The Boundary Cases

**Refactoring decisions**: Remember IF the refactoring established a pattern
other code should follow. Skip if it was purely mechanical cleanup.

**Test results**: Remember IF a test revealed unexpected library behavior.
Skip if the test just confirmed something works as expected.

**Config values**: Remember IF you discovered a required config value by trial
and error. Skip if it's documented in the README or .env.example.
