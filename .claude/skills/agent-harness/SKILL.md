---
name: agent-harness
description: "Provides workflow and quality standards for using the Agent Harness knowledge graph MCP server. Use when: starting any coding session on a project that has an Agent Harness MCP configured, calling init_project, prime, remember, recall, or forget, deciding what knowledge is worth persisting, or updating a fact that has changed since it was last recorded. Also use when the agent needs to recall project-specific decisions, known pitfalls, or architectural facts from prior sessions."
---

# Agent Harness

Agent Harness is a persistent knowledge graph for coding sessions. It stores
decisions, insights, errors, and architecture facts across sessions so you don't
start from scratch each time.

## Session Start Workflow

Call these two tools at the start of every session on a project:

1. `init_project(name, description)` — Creates or retrieves the project namespace.
   Idempotent: safe to call every session.
2. `prime(project_id)` — Returns a compact briefing: current decisions, known
   pitfalls, last-session notes. Read this before starting any work.

**Multi-project sessions**: If you work across multiple repos in one session,
call `init_project` + `prime` for each distinct project when you first touch it.

## During Work

**Recalling facts**: Use `recall(project_id, query)` with a natural language
query when you need a specific fact mid-task.
- Good queries: "authentication approach", "why we chose SQLite over PostgreSQL",
  "known issues with the FalkorDB client"
- Avoid: bare keywords ("JWT") — use a short phrase instead

**Recording knowledge**: Call `remember(project_id, content, category)` at
decision points — not continuously.

See [references/what-to-remember.md](references/what-to-remember.md) for the
quality gate rules: what to record vs. skip.

## Recording a Changed Fact

When a decision or fact changes, include what changed AND why in the `remember()`
call. Mention the old fact explicitly. This lets Graphiti detect the contradiction
and automatically mark the old fact as superseded in the knowledge graph.

**Template**: "Changed [old fact] to [new fact] because [reason]. Reverses prior
[old fact] decision."

**Example**: `remember("Switched from JWT to session-based auth because JWT token
rotation was incompatible with multi-tab sessions — reverses prior JWT decision",
category="decision")`

See [references/update-workflow.md](references/update-workflow.md) for the full
step-by-step procedure.

## Categories

Pass one of: `decision` | `insight` | `error` | `goal` | `architecture`

See [references/category-guide.md](references/category-guide.md) for one-liner
examples per category.

## Quality Standard

Ask before every `remember()` call:
> "Would a future agent, starting this project from scratch, need this fact in
> the first 30 seconds?"

If yes: `remember()`. If no: skip.

See [references/what-to-remember.md](references/what-to-remember.md) for
explicit good examples and anti-patterns.

## Forgetting Incorrect Facts

Use `forget(project_id, episode_id)` to delete a wrongly-stored episode. The
`episode_id` is returned by `remember()` in its response.

## If MCP Tools Fail

If any Agent Harness tool fails (server not running, FalkorDB down, etc.),
continue the session normally. Agent Harness is optional context enrichment —
it is never required for the coding work itself.
