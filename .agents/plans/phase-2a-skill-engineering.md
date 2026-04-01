# Feature: Phase 2a — Agent Harness Skill Engineering

The following plan should be complete, but validate the referenced file paths and codebase patterns before starting.

Pay special attention to the YAML frontmatter format for SKILL.md (no extra fields beyond `name` and `description`), the progressive disclosure structure (SKILL.md body < 500 lines), and where reference files should be linked from SKILL.md.

## Feature Description

Create the `agent-harness` skill — a set of Markdown files that teach Claude Code agents exactly when and how to use the Agent Harness MCP tools. The skill establishes a quality gate at the input layer: it defines what deserves to be remembered vs. skipped, how to phrase fact updates to trigger Graphiti's contradiction detection, and the correct session workflow. This is the highest-leverage Phase 2 deliverable because it prevents graph slop before it enters the system.

The skill lives in `skills/agent-harness/` and follows the progressive disclosure pattern: `SKILL.md` contains the core workflow; `references/` files contain edge-case guidance loaded only when needed.

## User Story

As a coding agent starting a session on a project with Agent Harness configured,
I want clear procedural instructions for when to call each MCP tool and what's worth remembering,
So that I build a clean, high-signal knowledge graph that genuinely helps future sessions.

## Problem Statement

Without a skill, agents either over-record (polluting the graph with in-progress notes and transient debug steps) or under-record (missing key architectural decisions). The graph accumulates slop over time and `prime()` returns increasingly noisy briefings. The agent also lacks a reliable pattern for recording fact *changes* in a way that Graphiti can detect as contradictions.

## Solution Statement

Create a structured skill with YAML-gated frontmatter, a <500-line core workflow in SKILL.md, and three reference files covering quality gate rules, category selection, and fact update procedure. Update CLAUDE.md to document the skill's location, installation method, and the iteration feedback loop.

## Feature Metadata

**Feature Type**: New Capability (skill / documentation asset)
**Estimated Complexity**: Low
**Primary Systems Affected**: `skills/agent-harness/` (new directory), `CLAUDE.md`
**Dependencies**: None — no Python code, no tests, no new packages. Content only.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

- `.claude/PRD2.md` (lines 210–280) — Exact SKILL.md structure, frontmatter, and body content specified by the PRD. This is the canonical content spec.
- `.claude/PRD2.md` (lines 389–410) — Open Questions Q5, Q6, Q7: graceful degradation, recall query examples, multi-project context. Address all three in the skill.
- `.claude/PRD2.md` (lines 414–427) — Phase 2a validation criteria and deliverable checklist.
- `.claude/skills/skill-creator/SKILL.md` (lines 47–115) — Skill anatomy rules: YAML frontmatter `name`+`description` only, `references/` pattern, what NOT to include (no README.md, etc.).
- `.claude/skills/skill-creator/SKILL.md` (lines 118–199) — Progressive disclosure patterns. Pattern 1 (high-level guide with references) is the right fit here.
- `.claude/skills/skill-creator/SKILL.md` (lines 258–278) — Step 3 (init_skill.py) and Step 5 (package_skill.py) of the skill creation process. These are required steps per the skill-creator spec, not optional.
- `.claude/skills/skill-creator/SKILL.md` (lines 303–315) — Frontmatter writing rules: description must include both what the skill does AND "use when" triggers. All "when to use" goes in frontmatter, NOT in the body.
- `.claude/skills/skill-creator/references/output-patterns.md` — "Examples Pattern" section. The ❌/✅ before/after format used in `what-to-remember.md` IS this pattern. Read this before writing that file — it defines the right level of specificity and structure for showing correct vs incorrect examples.
- `.claude/skills/skill-creator/scripts/quick_validate.py` — The official validator. Checks YAML structure, name format, description length limits (max 1024 chars), allowed frontmatter fields. **Run this after writing SKILL.md and before package_skill.py.** NOTE: allowed frontmatter fields are `name`, `description`, `license`, `allowed-tools`, `metadata` — not just name+description. The validator will fail on any field outside this set.
- `.claude/skills/skill-creator/scripts/init_skill.py` — Scaffold script. Run this FIRST to create the template directory structure before writing any content. Generates SKILL.md template + example files in scripts/, references/, assets/ that you then replace or delete.
- `CLAUDE.md` (§6 MCP Tools Reference) — The five tools (`prime`, `remember`, `recall`, `init_project`, `forget`) with exact signatures and semantics. The skill must be consistent with this.
- `src/tools/remember.py` — Confirms categories are a `Literal` type: `decision | insight | error | goal | architecture`. 2000-char content limit. episode_id returned in response.
- `src/tools/forget.py` — `forget(project_id, episode_id)` pattern.
- `.agents/reference/context_update.md` (lines 250–314) — Approach B (graph edge pruning), C (briefing cache) and F (consolidation record) give context for why quality at input matters. Also confirms: Graphiti sets `invalid_at` automatically when a new episode contradicts an old fact — the skill's "update workflow" must teach agents to phrase updates with explicit contradiction language to trigger this.
- `.agents/reference/context_update.md` (lines 430–445) — What Agent Harness already does vs. what autoDream does. The skill fills gaps in agent behavior (near-duplicate avoidance, update workflow) that the server cannot handle automatically.

### New Files to Create

```
skills/
└── agent-harness/
    ├── SKILL.md                        # Core workflow + quality standard
    └── references/
        ├── what-to-remember.md         # Quality gate: anti-patterns + good examples
        ├── category-guide.md           # Category selection guide with one-liner examples
        └── update-workflow.md          # Step-by-step for recording a fact change
```

### Files to Update

- `CLAUDE.md` — Add §13 or new section: "Skill: agent-harness" — skill location, how to install, iteration loop
- `CHANGELOG.md` — Add Phase 2a entry

### Relevant Documentation — REVIEW BEFORE IMPLEMENTING

- `.claude/PRD2.md` §7.1 — Full SKILL.md body content spec (copy this, don't reinvent)
- `.claude/PRD2.md` §6 — Context Engineering principles that should inform SKILL.md tone and structure
- `.claude/PRD2.md` §9 — Research backing for why skill quality matters (can be condensed into the skill's quality standard)
- `.agents/reference/context_update.md` §"Mapping autoDream Concepts" — Concept 5 (cursor/incremental) and Concept 3 (four-phase prompt) inform update-workflow.md content
- `.claude/skills/skill-creator/references/output-patterns.md` — "Examples Pattern": use for structuring the ❌/✅ good/bad examples in `what-to-remember.md`. The pattern recommends showing input+output pairs with brief explanation, not just a list of bullets.

### Patterns to Follow

**Skill frontmatter — YAML only `name` + `description`:**
```yaml
---
name: agent-harness
description: Provides workflow and quality standards for using the Agent Harness
  knowledge graph MCP server. Use when: starting any coding session on a project
  that has an Agent Harness MCP configured, calling init_project/prime/remember/
  recall/forget/consolidate, deciding what knowledge is worth persisting, or
  updating a fact that has changed since it was last recorded.
---
```
No other YAML fields. The description is the primary trigger mechanism — it must be comprehensive.

**Progressive disclosure linking (from skill-creator Pattern 1):**
```markdown
## Quality Gate
Ask: "Would a future agent, starting from scratch, need this in the first 30 seconds?"
If yes: `remember()`. If no: skip.
See [references/what-to-remember.md](references/what-to-remember.md) for examples and anti-patterns.
```
The body mentions the reference file and when to read it — it does NOT duplicate the content.

**SKILL.md body structure (imperative form, <500 lines):**
```markdown
# Agent Harness

## Session Start Workflow
1. init_project(name, description) — idempotent
2. prime(project_id) — returns briefing

## During Work
- recall(project_id, query) for specific facts
- remember(project_id, content, category) at decision points

## Recording a Changed Fact
[3-4 line explanation + example]

## Categories
[one-liner per category]

## Quality Standard
[one-liner + link to references/what-to-remember.md]

## If MCP Tools Fail
[graceful degradation note]
```

---

## IMPLEMENTATION PLAN

### Phase 1: Scaffold and Create Core SKILL.md

Use `init_skill.py` to scaffold the correct directory structure (required by the skill-creator process), then replace the template content with the actual skill. Delete the unused `scripts/` and `assets/` scaffolding directories.

**Tasks:**
- Run `init_skill.py agent-harness --path skills/` to scaffold the directory
- Delete unused scaffold directories: `scripts/`, `assets/`, `references/api_reference.md`
- Write `skills/agent-harness/SKILL.md` content (replacing the TODO template)

### Phase 2: Create Reference Files

Create the three progressive-disclosure reference files. Each file is loaded only when Claude determines it's needed — keep them focused and scannable.

**Tasks:**
- Write `skills/agent-harness/references/what-to-remember.md`
- Write `skills/agent-harness/references/category-guide.md`
- Write `skills/agent-harness/references/update-workflow.md`

### Phase 3: Integration

Update CLAUDE.md to document the skill, and update CHANGELOG.md.

**Tasks:**
- Add skill documentation section to `CLAUDE.md`
- Add Phase 2a entry to `CHANGELOG.md`

### Phase 4: Validation

Validate the skill structure and content.

**Tasks:**
- Validate YAML frontmatter
- Run packaging script to confirm no structural errors
- Manual spot-check: verify SKILL.md is under 500 lines

---

## STEP-BY-STEP TASKS

### TASK 1: SCAFFOLD `skills/agent-harness/` using `init_skill.py`

- **IMPLEMENT**: Run the scaffold script to create the correct directory structure with the SKILL.md template. The skill-creator process requires this as the first step for any new skill.
- **COMMAND**: `python3 .claude/skills/skill-creator/scripts/init_skill.py agent-harness --path skills/`
- **RESULT**: Creates `skills/agent-harness/` with `SKILL.md` (TODO template), `scripts/example.py`, `references/api_reference.md`, `assets/example_asset.txt`
- **CLEANUP**: After scaffolding, delete the directories and files that aren't needed for this skill:
  - Delete `skills/agent-harness/scripts/` (entire directory — no scripts in this skill)
  - Delete `skills/agent-harness/assets/` (entire directory — no assets in this skill)
  - Delete `skills/agent-harness/references/api_reference.md` (will be replaced by 3 specific reference files)
- **GOTCHA**: Do NOT rename or move the scaffold output. The skill directory name must match the skill's `name` field in SKILL.md exactly: `agent-harness`.
- **VALIDATE**: `ls skills/agent-harness/` → shows only `SKILL.md` and `references/` (empty directory)

---

### TASK 2: WRITE `skills/agent-harness/SKILL.md`

- **IMPLEMENT**: Replace the scaffold TODO template with the full SKILL.md content. Content is fully specified below — do not deviate from the structure.
- **GOTCHA**: YAML frontmatter allows `name`, `description`, `license`, `allowed-tools`, `metadata`. Do NOT add `version` or any other custom field — the validator will reject it. For this skill, only `name` and `description` are needed.
- **GOTCHA**: Description must include "Use when:" language — this is the trigger mechanism. Do NOT put "When to use" sections in the body (the body only loads AFTER the skill triggers, so those sections are never read by Claude when deciding whether to use the skill).
- **GOTCHA**: Description max length is 1024 characters — the validator enforces this. Check with `quick_validate.py` after writing.
- **GOTCHA**: All "during work" instructions reference the `references/` files with explicit `[text](path)` links — do not duplicate content that belongs in a reference file.
- **GOTCHA**: Include graceful degradation note (Q5 from PRD2 §10) — agents must know to continue work if MCP tools fail.
- **GOTCHA**: Include multi-project note (Q7) — call `init_project`+`prime` per distinct project, not once globally.
- **VALIDATE**: `wc -l skills/agent-harness/SKILL.md` → should be well under 500 lines
- **VALIDATE**: `python3 .claude/skills/skill-creator/scripts/quick_validate.py skills/agent-harness` → "Skill is valid!"

**Content spec for `skills/agent-harness/SKILL.md`:**

```markdown
---
name: agent-harness
description: Provides workflow and quality standards for using the Agent Harness
  knowledge graph MCP server. Use when: starting any coding session on a project
  that has an Agent Harness MCP configured, calling init_project/prime/remember/
  recall/forget/consolidate, deciding what knowledge is worth persisting, or
  updating a fact that has changed since it was last recorded. Also use when the
  agent needs to recall project-specific decisions, known pitfalls, or
  architectural facts from prior sessions.
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
```

---

### TASK 3: CREATE `skills/agent-harness/references/what-to-remember.md`

- **IMPLEMENT**: Quality gate reference with explicit good examples AND anti-patterns. Content from PRD2 §7.1 ("what-to-remember.md" section), expanded with concrete project-specific examples.
- **PATTERN**: `.claude/skills/skill-creator/references/output-patterns.md` "Examples Pattern" — use the ❌/✅ before/after format. Each anti-pattern shows the bad input and explains why it's wrong; each good example shows the input and names what makes it valuable. This is more instructive than a plain list.
- **PATTERN**: The context_update.md §"Problems in the Current Agent Harness Knowledge Graph" lists the real patterns to prevent (redundant episodes, failed-extraction noise, in-progress work as facts).
- **GOTCHA**: Include a table of contents at the top (file will be > 50 lines) so Claude can see the scope when previewing.
- **GOTCHA**: The examples must be drawn from the REAL Agent Harness codebase — not generic placeholders. Verify each example against the actual code before including it.
- **VALIDATE**: `wc -l skills/agent-harness/references/what-to-remember.md` → should be < 150 lines

**Content spec:**

```markdown
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
```

---

### TASK 4: CREATE `skills/agent-harness/references/category-guide.md`

- **IMPLEMENT**: One-liner examples per category, matching the exact 5 categories in `remember.py` Literal type.
- **PATTERN**: PRD2 §7.1 "category-guide.md" section gives the format. Expand with 2-3 examples each, NOT just one.
- **GOTCHA**: Categories must exactly match the Literal from `src/tools/remember.py`: `decision | insight | error | goal | architecture`. No typos, no extras.
- **VALIDATE**: File exists and contains all 5 categories

**Content spec:**

```markdown
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
```

---

### TASK 5: CREATE `skills/agent-harness/references/update-workflow.md`

- **IMPLEMENT**: Step-by-step procedure for recording a fact change in a way that triggers Graphiti's contradiction detection (`invalid_at` edge marking).
- **KEY INSIGHT**: From `context_update.md` — Graphiti sets `invalid_at` on old edges automatically when a new episode contradicts them. The skill must teach agents to phrase updates with EXPLICIT contradiction language, not just state the new fact in isolation. If the new fact is stated in isolation, Graphiti may not detect the contradiction.
- **VALIDATE**: File exists and references `recall()` in the procedure (step 1 is always "recall the old fact first")

**Content spec:**

```markdown
# Update Workflow: Recording a Changed Fact

When a decision or fact changes, use this procedure to record it so that
Graphiti automatically supersedes the old version in the knowledge graph.

## Why This Matters

Graphiti detects contradictions by comparing new episode content against
existing graph entities. If you just state the new fact without mentioning
what changed, Graphiti may add it as a second fact alongside the old one —
not replace it. Including explicit contradiction language ("reverses prior X",
"replaces X with Y") reliably triggers the supersession logic.

## Procedure

### Step 1 — Recall the Old Fact
```
recall(project_id, "old decision about [topic]")
```
Confirm the old fact exists and note its exact phrasing. This ensures you
reference the right entity in the update.

### Step 2 — Compose the Update

Structure the new `remember()` content as:
```
[New state] because [reason]. [Reference to old state that is now wrong.]
```

**Template:**
> "Changed [old thing] to [new thing] because [reason]. Reverses prior
> [old thing] decision."

**Expanded example:**
> "Switched from JWT to session-based auth because JWT token rotation was
> incompatible with multi-tab sessions — edge cases required stateful server
> logic anyway. Reverses prior decision to use JWT for stateless auth."

### Step 3 — Call remember()
```
remember(
  project_id,
  content="[your composed update from Step 2]",
  category="decision"   # or whichever category fits
)
```

Graphiti will process this episode, detect the reference to the old fact, set
`invalid_at` on the old graph edge, and create a new edge with the updated fact.

### Step 4 — Optional Verification

After the extraction completes (a few seconds), call `prime(project_id)` to
confirm the new fact appears in the briefing and the old fact does not.

`prime()` output already filters `invalid_at` edges — if your update worked,
the old fact will no longer appear in the "Key Decisions" section.

## Common Mistakes

**❌ Stating only the new fact:**
> "We use session-based auth."

This may be added as a second fact alongside the JWT fact, not replacing it.

**✅ Referencing the contradiction:**
> "Switched to session-based auth from JWT because [reason]. Reverses prior
> JWT decision."

**❌ Forgetting the reason:**
> "Changed from JWT to sessions. Reverses JWT decision."

Reasons are essential — they're what future agents need to understand the tradeoff.

**✅ Always include the reason:**
> "Switched to sessions from JWT because token rotation caused multi-tab
> session invalidation bugs — the stateless model broke down in practice."
```

---

### TASK 6: UPDATE `CLAUDE.md`

- **IMPLEMENT**: Add a new section to CLAUDE.md documenting the skill's location, how to install it in Claude Code, and the iteration feedback loop.
- **PATTERN**: Existing CLAUDE.md §6 (MCP Tools Reference) and §11 (On-Demand Context) show the documentation style — concise tables + short paragraphs.
- **LOCATION**: Add as a new top-level section. Best placement: after §12 (Validation Checklist), as §13.
- **CONTENT**: Location, install command, iteration loop, link to PRD2 for full spec.
- **GOTCHA**: Do not duplicate the full skill content in CLAUDE.md — CLAUDE.md should just say where the skill is and how to use it.
- **VALIDATE**: `grep -n "skills/agent-harness" CLAUDE.md` → returns the new section line

**Content to add to CLAUDE.md (new §13):**

```markdown
---

## 13. Skill: agent-harness

The Agent Harness skill teaches coding agents the correct session workflow and
knowledge quality standards. It lives in the repository and can be installed
directly in Claude Code.

**Location:** `skills/agent-harness/SKILL.md`

**Install in Claude Code:**
```bash
claude skills install skills/agent-harness
```
Or manually: configure the skill in Claude Code settings pointing to
`skills/agent-harness/`.

**Skill files:**

| File | Purpose |
|------|---------|
| `skills/agent-harness/SKILL.md` | Core workflow, quality standard, trigger description |
| `skills/agent-harness/references/what-to-remember.md` | Quality gate: good examples + anti-patterns |
| `skills/agent-harness/references/category-guide.md` | Category selection guide |
| `skills/agent-harness/references/update-workflow.md` | Step-by-step for recording changed facts |

**Iteration loop (Phase 2d):**

1. Run agent sessions with the skill loaded
2. Observe: what was remembered that shouldn't have been? What was missed?
3. Identify the gap in `SKILL.md` or a reference file
4. Edit the relevant file
5. Test on the next session
6. Commit with a note on what was fixed and why

See `.claude/PRD2.md` §11 (Phase 2d) for the full iteration process.
```

---

### TASK 7: UPDATE `CHANGELOG.md`

- **IMPLEMENT**: Add a Phase 2a entry at the top of CHANGELOG.md.
- **PATTERN**: Read `CHANGELOG.md` first to match the existing format.
- **VALIDATE**: `head -20 CHANGELOG.md` shows the new entry

---

### TASK 8: VALIDATE and PACKAGE with skill-creator scripts

- **IMPLEMENT**: Run the official skill-creator validation and packaging pipeline. This is a required step per the skill-creator process, not optional — the packaging script is the final structural gate.
- **STEP 1 — Quick validate** (fast, run first):
  ```bash
  python3 .claude/skills/skill-creator/scripts/quick_validate.py skills/agent-harness
  ```
  Expected output: `Skill is valid!` — fix any reported errors before proceeding.
- **STEP 2 — Package** (also validates, then creates distributable):
  ```bash
  python3 .claude/skills/skill-creator/scripts/package_skill.py skills/agent-harness
  ```
  Expected output: creates `agent-harness.skill` file with no errors.
- **GOTCHA**: The `.skill` file output does NOT need to be committed to the repo. In-repo distribution (pointing Claude Code at `skills/agent-harness/`) is sufficient for Phase 2a. But the packaging step must pass as proof of structural correctness.
- **GOTCHA**: If packaging fails, fix the reported error before marking this task complete — do not skip or treat failures as warnings.
- **VALIDATE**: Both scripts exit with code 0

---

## TESTING STRATEGY

This feature creates content files (Markdown), not Python code. Traditional unit tests don't apply. Validation is structural and behavioral.

### Structural Validation

1. **YAML frontmatter validity** — SKILL.md must parse as valid YAML between the `---` delimiters.
2. **Line count** — SKILL.md body must be < 500 lines.
3. **Required fields** — YAML must have exactly `name` and `description`, nothing else.
4. **Reference links** — Every `[text](path)` in SKILL.md must point to a file that exists in `references/`.
5. **Category coverage** — `category-guide.md` must cover all 5 categories: `decision`, `insight`, `error`, `goal`, `architecture`.

### Behavioral Validation (Manual)

After creating the files, install the skill and run at least one session:

1. Start a new Claude Code session on the Agent Harness project
2. Verify the skill triggers (Claude should reference it for Agent Harness work)
3. Run the session start workflow: `init_project` + `prime`
4. Record one real decision using `remember()`
5. Verify the quality standard was applied (no slop episodes)

**Acceptance criteria per PRD2 §11 Phase 2a:**
> After 3 sessions with skill installed, zero "in-progress work" episodes appear in the graph.
> At least 3 high-signal decision episodes per session.

### Edge Cases to Verify

1. **Skill triggers on first agent message** — description must be specific enough to trigger reliably
2. **Reference files load on demand** — agent should only load `what-to-remember.md` when it needs category clarification, not on every call
3. **Update workflow example is unambiguous** — new agents must be able to follow it without additional explanation

---

## VALIDATION COMMANDS

### Level 1: Official Skill Validator (Run First)

```bash
# The official skill-creator validator — checks YAML structure, name format,
# description length, and allowed frontmatter fields.
# Run this immediately after writing SKILL.md.
python3 .claude/skills/skill-creator/scripts/quick_validate.py skills/agent-harness
# Expected: "Skill is valid!"
```

### Level 2: Syntax & Structure

```bash
# Validate SKILL.md YAML frontmatter parses correctly and has required fields
python3 -c "
import re, yaml
content = open('skills/agent-harness/SKILL.md').read()
match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
assert match, 'No valid frontmatter block found'
fm = yaml.safe_load(match.group(1))
assert 'name' in fm, 'Missing name field'
assert 'description' in fm, 'Missing description field'
allowed = {'name', 'description', 'license', 'allowed-tools', 'metadata'}
extra = set(fm.keys()) - allowed
assert not extra, f'Unexpected YAML fields (validator will reject): {extra}'
print('YAML OK:', fm['name'])
print('Description length:', len(fm['description']), '/ 1024 max')
assert len(fm['description']) <= 1024, 'Description exceeds 1024 char limit'
"

# Check SKILL.md line count (must be < 500)
wc -l skills/agent-harness/SKILL.md

# Verify all reference links in SKILL.md point to files that exist
python3 -c "
import re, os
content = open('skills/agent-harness/SKILL.md').read()
links = re.findall(r'\[.*?\]\((references/[^)]+)\)', content)
assert links, 'No reference links found — SKILL.md must link to reference files'
for link in links:
    path = os.path.join('skills/agent-harness', link)
    assert os.path.exists(path), f'Missing referenced file: {path}'
    print(f'OK: {path}')
"

# Verify all 5 categories present in category-guide.md
python3 -c "
content = open('skills/agent-harness/references/category-guide.md').read()
for cat in ['decision', 'insight', 'error', 'goal', 'architecture']:
    assert f'## {cat}' in content, f'Missing category: {cat}'
    print(f'OK: {cat}')
"
```

### Level 3: Content Completeness Check

```bash
# Verify key terms are present in SKILL.md
python3 -c "
content = open('skills/agent-harness/SKILL.md').read()
required = ['init_project', 'prime', 'remember', 'recall', 'forget',
            'what-to-remember.md', 'category-guide.md', 'update-workflow.md',
            'MCP Tools Fail']
for term in required:
    assert term in content, f'Missing in SKILL.md: {term}'
    print(f'OK: {term}')
"

# Verify update-workflow.md has the recall step and invalid_at explanation
python3 -c "
content = open('skills/agent-harness/references/update-workflow.md').read()
assert 'recall' in content.lower(), 'update-workflow.md missing recall step'
assert 'invalid_at' in content, 'update-workflow.md missing invalid_at explanation'
print('update-workflow.md OK')
"

# Verify what-to-remember.md has both good examples AND anti-patterns
python3 -c "
content = open('skills/agent-harness/references/what-to-remember.md').read()
assert '❌' in content, 'Missing anti-patterns (❌ markers)'
assert '✅' in content or 'Good Example' in content, 'Missing good examples'
print('what-to-remember.md OK')
"
```

### Level 4: CLAUDE.md Update Check

```bash
# Verify CLAUDE.md was updated with skill section
grep -n "skills/agent-harness" CLAUDE.md && echo "OK: CLAUDE.md updated" || echo "FAIL: missing skill reference"
```

### Level 5: Packaging (Required — Final Structural Gate)

```bash
# Run the packaging script — also validates before packaging.
# The .skill output file does not need to be committed, but this must pass.
python3 .claude/skills/skill-creator/scripts/package_skill.py skills/agent-harness
# Expected: "agent-harness.skill" created with no errors
# Exit code must be 0
```

---

## ACCEPTANCE CRITERIA

- [ ] `init_skill.py` was run to scaffold the directory (not created manually)
- [ ] `skills/agent-harness/` contains only `SKILL.md` and `references/` — no `scripts/`, `assets/`, or extra files
- [ ] `skills/agent-harness/SKILL.md` exists with valid YAML frontmatter (`name` + `description` only)
- [ ] `SKILL.md` body is under 500 lines
- [ ] `SKILL.md` description length ≤ 1024 characters (validator enforces this)
- [ ] `SKILL.md` description explicitly lists all MCP tools and "use when" triggers
- [ ] `SKILL.md` body references all three reference files with working relative links
- [ ] `SKILL.md` includes graceful degradation note (what to do if MCP tools fail)
- [ ] `SKILL.md` includes multi-project note (call init_project+prime per repo)
- [ ] `skills/agent-harness/references/what-to-remember.md` exists with both ❌ anti-patterns AND ✅ good examples
- [ ] `skills/agent-harness/references/category-guide.md` exists with all 5 categories covered
- [ ] `skills/agent-harness/references/update-workflow.md` exists with step-by-step procedure starting with `recall()`
- [ ] `update-workflow.md` explains WHY contradiction language is needed (Graphiti `invalid_at` mechanism)
- [ ] `CLAUDE.md` updated with §13 documenting skill location, install command, and iteration loop
- [ ] `CHANGELOG.md` updated with Phase 2a entry
- [ ] `quick_validate.py` exits 0: "Skill is valid!"
- [ ] `package_skill.py` exits 0 and creates `agent-harness.skill`
- [ ] No README.md, INSTALLATION.md, or other non-skill files created in `skills/agent-harness/`

---

## COMPLETION CHECKLIST

- [ ] All 8 tasks completed in order
- [ ] Task 1: `init_skill.py` ran successfully; scaffold directories deleted
- [ ] Task 2: `quick_validate.py` passes after SKILL.md written
- [ ] Task 3: `what-to-remember.md` has both ❌ and ✅ examples from real codebase
- [ ] Task 4: `category-guide.md` covers all 5 Literal categories
- [ ] Task 5: `update-workflow.md` step 1 starts with `recall()` and explains `invalid_at`
- [ ] Task 6: CLAUDE.md grep confirms §13 added
- [ ] Task 7: CHANGELOG.md updated
- [ ] Task 8: `quick_validate.py` + `package_skill.py` both exit 0
- [ ] No regressions: existing tests unaffected (`uv run pytest tests/ -v` still shows 148 passing)

---

## NOTES

### Why No Tests?

This feature creates Markdown content files, not Python code. The existing pytest suite tests server behavior and remains unchanged. The "tests" for this feature are structural validators (Python one-liners checking YAML parse, line count, link existence) and behavioral manual testing (observing agent behavior in real sessions).

### Skill vs. CLAUDE.md

There is intentional overlap between the skill and CLAUDE.md §6 (MCP Tools Reference). CLAUDE.md is for developers and CI agents reading the project; the skill is for coding agents at runtime. CLAUDE.md is a developer reference; the skill is an agent workflow guide. They can reference the same tools with different emphasis and level of detail.

### No `consolidate()` in the Skill Yet

Phase 2a ships the skill before `consolidate()` is implemented (Phase 2b). The skill's `SKILL.md` description should include `consolidate` in the trigger list to future-proof it, but the body should either omit it or mention "see project docs" if the tool isn't available yet. The implementation agent should check whether `consolidate.py` exists before including it in SKILL.md body content.

### Packaging vs. In-Repo Distribution

The `package_skill.py` script serves two purposes: validation and distribution. The validation side is required — it's the final structural gate that confirms the skill is well-formed. The distribution side (the `.skill` output file) is not required to be committed for Phase 2a — in-repo distribution is sufficient for now. Users install by pointing Claude Code at `skills/agent-harness/`. The `.skill` file becomes relevant when we publish alongside the PyPI package (future consideration from PRD2 §14).

### Content is the Critical Path

The quality of the skill content — especially the anti-patterns in `what-to-remember.md` and the contradiction-language examples in `update-workflow.md` — directly determines how clean the knowledge graph stays. Spend more time on content quality than file structure. The 30-second test ("Would a future agent need this?") should be the anchor for every example chosen.

---

## Confidence Score: 9/10

High confidence because:
- All content is fully specified in PRD2 §7.1 — no design decisions needed
- Skill structure is well-documented in skill-creator SKILL.md
- No Python code, no database changes, no new dependencies
- Validation is straightforward (YAML parse + file existence checks)

Risk: The one-liner examples in reference files need to be accurate to the real codebase behavior. The implementation agent must verify examples against actual tool behavior (categories from remember.py Literal, tool signatures from CLAUDE.md §6) before committing.
