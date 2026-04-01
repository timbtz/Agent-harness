# Product Requirements Document: Agent Harness — Phase 2
### Knowledge Quality, Skill Engineering, and Context Lifecycle Management

> **Version:** 1.0
> **Date:** March 31, 2026
> **Status:** Draft
> **Predecessor:** `.claude/PRD.md` (Phase 1 — complete, 148 tests passing)

---

## 1. Executive Summary

Phase 1 delivered a working MCP server with 5 tools, a temporal knowledge graph backed by Graphiti/FalkorDB, a SQLite episode store, and a React dashboard. The system correctly stores knowledge, performs hybrid semantic search, and persists cross-session context for coding agents.

Phase 2 addresses the next critical layer: **the system knows how to store and retrieve knowledge, but agents don't yet know how to use it well, and the graph has no lifecycle management.** The result is an accumulation problem: agents store too much (slop), or too little (key decisions missed), and the graph grows indefinitely with no curation. Neither failure is catastrophic, but both degrade the core value proposition over time.

The Phase 2 thesis — drawn from studying Claude Code's autoDream system and Anthropic's published context engineering research — is: **the best place to enforce quality is at the input gate, not in a cleanup pass**. A well-designed skill that teaches agents *exactly when and what to remember* eliminates slop before it enters the graph. Graphiti's natural contradiction detection handles temporal updates automatically. What remains is minimal: a briefing cache, pruning of technical noise (failed extractions), and a manual consolidation tool for edge cases.

The deliverable for Phase 2 is a production-ready, self-improving system: a skill that grows smarter through iteration, a graph that stays lean through discipline rather than deletion, and a `prime()` experience that genuinely orients agents in seconds.

**MVP goal for Phase 2:** A coding agent starting a session on an established project calls `prime()` and is fully oriented — current state, live decisions, known pitfalls — in one tool call. It records a handful of high-signal facts during the session. The graph stays clean. Nothing important is lost.

---

## 2. Mission

**Mission Statement:** Make the Agent Harness knowledge graph self-maintaining through quality-enforced input, natural temporal updates, and a skill that turns every coding agent into a disciplined knowledge curator.

**Core Principles:**

1. **Quality at the source, not in cleanup** — A skill that defines what *not* to remember is worth more than a consolidation pass that fixes bad input after the fact.
2. **Temporal history is the value proposition** — The graph's advantage over flat markdown memory is that it shows *how* understanding evolved. Preserve superseded facts; only delete technical failures.
3. **Context is a finite resource** — Every instruction, every fact, every token in the agent's context window has a cost. Skills, briefings, and tool outputs must earn their place.
4. **Measurable iteration over guessed-at improvement** — Skill quality should be tested against real usage, tracked, and improved in structured iterations inspired by the autoresearch feedback loop.
5. **The skill teaches the workflow; the workflow teaches the skill** — The skill and the agent's behavior are co-designed: usage reveals gaps in the skill, gaps in the skill reveal gaps in the workflow.

---

## 3. Target Users

**Primary: AI Coding Agent (Claude Code)**
The immediate user of the MCP tools and the skill. The agent needs to know: when to call `init_project`, when to `prime()`, when and what to `remember()`, when to `recall()`, and the rare case for `forget()`. The skill must encode this knowledge so concisely that it costs minimal context tokens and fires reliably.

**Secondary: Human Developer**
The developer who configured Agent Harness and wants sessions to feel continuous. They want `prime()` to work without manual curation. They want the dashboard to show a clean, meaningful graph, not an ever-growing pile of raw transcriptions.

**Tertiary: Future Agent Sessions**
Every `remember()` call is ultimately written for a future agent session, not the current one. The quality bar should be: "Would a future agent, starting from scratch on this project, find this fact useful in the first 30 seconds?"

---

## 4. Phase 2 Scope

### In Scope ✅

**Skill Engineering**
- ✅ `agent-harness` skill: SKILL.md + reference files teaching agents when/how to use all 5 MCP tools
- ✅ Quality gate definitions: explicit rules for what to remember vs. what to skip
- ✅ Update workflow: explicit pattern for recording fact changes (to trigger Graphiti contradiction detection)
- ✅ Progressive disclosure structure: core workflow in SKILL.md, edge-case guidance in `references/`
- ✅ Skill iteration loop: test → observe gaps → improve → repeat

**Server-Side Maintenance (Minimal)**
- ✅ Failed episode pruning: delete `status=failed` episodes older than 30 days
- ✅ Orphaned pending cleanup: re-queue or delete `status=pending` episodes older than 2 hours on startup
- ✅ Briefing cache: store pre-computed briefing in SQLite, invalidate on new episodes
- ✅ `consolidate()` MCP tool: manual trigger for rule-based cleanup (no LLM calls)
- ✅ `POST /api/projects/{id}/consolidate` REST endpoint

**Improved `prime()` Output**
- ✅ "Since your last session" delta: N new episodes since last `prime()` call, top new decisions
- ✅ Faster response via briefing cache
- ✅ Overdue consolidation hint: surface when graph has accumulated significant unreviewed episodes

**CLAUDE.md Updates**
- ✅ Document skill structure, location, and triggering conventions
- ✅ Document consolidation endpoint and its semantics
- ✅ Update Phase 2 context to CLAUDE.md

### Out of Scope ❌

- ❌ LLM-powered consolidation pass (autoDream-equivalent) — deferred pending evidence that rule-based is insufficient
- ❌ Embedding-based near-duplicate detection at the SQLite layer — deferred; Graphiti handles semantic merging at graph level
- ❌ FalkorDB edge pruning / deletion of `invalid_at` edges — explicitly excluded; these constitute the temporal graph
- ❌ Cross-project knowledge federation — out of scope for Phase 2
- ❌ Team memory sync (per-server shared memory across developers) — future consideration
- ❌ Drift detection via codebase re-scanning — deferred; the skill handles this via instructed update workflow
- ❌ PyPI publish / CI/CD pipeline — deferred from Phase 1 (unchanged)
- ❌ Dashboard enhancements beyond what exists — no new frontend features in Phase 2

---

## 5. User Stories

**US-1: Skill-Guided Session Start**
> As a coding agent starting a session, I want to know exactly what to call and in what order, so that I orient correctly without burning context on uncertainty.

*Concrete example:* Agent reads SKILL.md, sees: "Start every session with `init_project()` then `prime()`." Calls both. Receives briefing with current decisions and last-session notes. Proceeds with full project context. No re-explaining needed.

**US-2: Disciplined Knowledge Capture**
> As a coding agent completing a decision during a session, I want clear rules for what deserves to be remembered, so I don't pollute the graph with noise or miss things a future agent will need.

*Concrete example:* Skill says: "Remember decisions that will constrain future work. Don't remember: things already visible in the codebase, in-progress work, transient debugging steps." Agent hits a key architectural decision, calls `remember("Chose SQLite over PostgreSQL for simplicity — multi-server deployment not needed in current scope", category="decision")`. Skips writing "ran the test suite, all passing."

**US-3: Natural Fact Updates**
> As a coding agent discovering that a previous decision has changed, I want to record the update in a way that Graphiti can detect as a contradiction and automatically supersede the old fact.

*Concrete example:* Skill says: "When a fact changes, include what changed and why in the new remember() call. Don't just state the new fact in isolation." Agent calls `remember("Migrated from JWT to session auth because JWT token rotation was incompatible with multi-tab sessions — reverses prior JWT decision", category="decision")`. Graphiti detects the JWT entity, sets `invalid_at` on the old edge, creates the new one. `prime()` now shows only the new fact; the temporal graph preserves both.

**US-4: Fast Orientation**
> As a coding agent returning to a project after several days, I want `prime()` to tell me what changed since my last session alongside the standing decisions, so I orient in one call without reading through raw episode history.

*Concrete example:* `prime()` returns: "## Project: MyApp — 3 new decisions since your last session (5 days ago). New: [decision about session auth]. Standing: [8 active architectural decisions]. Known pitfalls: [3]. Last session work: [summary of recent episodes]."

**US-5: Clean Graph Over Time**
> As a developer reviewing the dashboard after 6 months, I want the graph to show a meaningful history rather than a growing pile of failed extractions and redundant raw notes.

*Concrete example:* Background pruning job has silently removed all `status=failed` episodes older than 30 days. Dashboard shows 180 meaningful episodes across 2 years; 37 `invalid_at` edges showing superseded decisions; 0 noise from failed LLM extraction attempts.

**US-6: Manual Consolidation on Demand**
> As a developer who notices the graph is getting cluttered, I want a manual consolidation tool that I can trigger to clean up technical noise without risking loss of real knowledge.

*Concrete example:* Calls `consolidate(project_id="my-app")` via MCP or REST. Gets back: `{"pruned_failed": 12, "pruned_pending": 3, "briefing_refreshed": true, "episodes_remaining": 94}`. No edges deleted, no semantic knowledge lost, no LLM calls.

**US-7: Skill Iteration via Feedback Loop**
> As a developer wanting to improve how the agent uses the knowledge graph, I want a structured way to observe skill gaps, update the skill, and verify improvement.

*Concrete example:* After 5 sessions, developer notices agent is recording "ran the test suite" as insights. Opens SKILL.md, adds explicit anti-pattern example. Tests 3 more sessions. Anti-pattern stops appearing. Skill version bumped.

---

## 6. Core Architecture & Context Engineering Model

### The Two-Layer Quality Model

Phase 2 establishes a deliberate two-layer quality architecture:

```
Layer 1 — INPUT QUALITY (Skill)
    Coding agent has skill loaded
    Skill defines: what to remember, what not to, how to phrase updates
    Agent applies quality judgment before calling remember()
    → Only high-signal episodes enter the graph

Layer 2 — LIFECYCLE MANAGEMENT (Server)
    Background task: prune failed/orphaned episodes
    On init: re-queue truly-orphaned pending episodes
    On prime(): return cached briefing if no new episodes
    On consolidate(): rule-based cleanup, no LLM
    Graphiti: natural contradiction detection on new remember() calls
    → Graph stays clean; temporal history preserved
```

### Context Engineering Principles Applied

Drawing from Anthropic's published context engineering research and the skill-creator framework:

**Progressive Disclosure in the Skill:**
- Level 1: Skill description in system prompt (~50 tokens) — triggers the skill
- Level 2: SKILL.md body (<500 lines) — core workflow loaded when skill activates
- Level 3: `references/` files — edge cases, anti-pattern catalogue, category decision guide (loaded only when needed)

**Just-in-Time Knowledge:**
- `prime()` provides orientation context upfront (fast path)
- `recall()` provides specific facts just-in-time during work
- The skill explicitly teaches this split: "prime at start, recall when working, remember at decision points"

**Finite Resource Respect:**
- Skill teaches: the context window is shared with code, tests, and errors — don't fill it with graph management
- `prime()` output stays under 400 tokens by design
- Skill body stays under 500 lines by design (progressive disclosure for the rest)

**Feedback Loop (autoresearch pattern):**
```
Session → observe agent behavior → identify skill gap → update skill → test → repeat
```
This mirrors karpathy/autoresearch: the "program.md" (here: SKILL.md) is the thing being iterated, not the model. The improvement loop is human-in-the-loop but structured.

### Directory Structure (Phase 2 additions)

```
agent-harness/
├── .claude/
│   ├── PRD.md                    # Phase 1 (existing)
│   └── PRD2.md                   # This document
├── .claude/skills/
│   └── skill-creator/            # Existing skill creator tool
├── skills/                       # NEW: agent-harness skill
│   └── agent-harness/
│       ├── SKILL.md              # Core workflow: init → prime → recall → remember
│       └── references/
│           ├── what-to-remember.md    # Quality gate: examples, anti-patterns
│           ├── category-guide.md      # When to use each category
│           └── update-workflow.md     # How to record fact changes correctly
├── src/
│   ├── tools/
│   │   └── consolidate.py        # NEW: consolidate() MCP tool
│   ├── services/
│   │   ├── projects.py           # UPDATED: prune_stale_episodes(), briefing cache columns
│   │   └── knowledge.py          # UNCHANGED (temporal graph preserved)
│   └── api/
│       └── routes.py             # UPDATED: POST /api/projects/{id}/consolidate
└── tests/
    └── test_tools_consolidate.py # NEW
```

---

## 7. Tool & Skill Specifications

### 7.1 The `agent-harness` Skill

**Purpose:** Transform a general-purpose coding agent into a disciplined knowledge curator that uses Agent Harness correctly and efficiently.

**SKILL.md structure (top-level):**

```markdown
---
name: agent-harness
description: Provides workflow and quality standards for using the Agent Harness
  knowledge graph MCP server. Use when: starting any coding session on a project
  that has an Agent Harness MCP configured, calling init_project/prime/remember/
  recall/forget, deciding what knowledge is worth persisting, or updating a fact
  that has changed since it was last recorded.
---

# Agent Harness

## Session Start Workflow
1. init_project(name, description) — idempotent, creates or retrieves project
2. prime(project_id) — returns current decisions, pitfalls, last-session notes

## During Work
- recall(project_id, query) when you need a specific fact
- remember(project_id, content, category) at decision points (see references/what-to-remember.md)

## Recording a Changed Fact
Include what changed and why — not just the new state.
Example: "Switched to session auth from JWT because [reason]. Reverses prior JWT decision."
This allows Graphiti to detect the contradiction and preserve temporal history.

## Categories
decision | insight | error | goal | architecture
See references/category-guide.md for examples.

## Quality Standard
Ask: "Would a future agent, starting from scratch, need this in the first 30 seconds?"
If yes: remember(). If no: skip.
```

**references/what-to-remember.md:**

Documents explicit anti-patterns with examples:
- Anti-pattern: "Ran the test suite — all 148 tests passing" → This is a log entry, not knowledge
- Anti-pattern: "We're currently implementing the consolidate() tool" → In-progress, not a decision
- Anti-pattern: "The project uses Python 3.11" → Visible in `pyproject.toml`, the agent can read it
- Pattern: "Chose asyncio.Queue over threading.Lock for extraction workers because..." → Architectural decision with rationale
- Pattern: "Graphiti search() returns list[EntityEdge], not a SearchResults object" → API behavior not in docs

**references/category-guide.md:**

Category selection guide with concrete one-liner examples for each:
- `decision`: "We chose X over Y because Z" — with alternatives and rationale
- `insight`: "Library API does X unexpectedly — documented behavior says Y"
- `error`: "Approach A fails because B — don't retry this"
- `goal`: "Must support multi-user access without authentication in MVP"
- `architecture`: "FalkorDB graph name is the sanitized project_id (hyphens→underscores)"

**references/update-workflow.md:**

Step-by-step for recording a fact update:
1. Recall the old fact to confirm it exists
2. Compose new fact with explicit contradiction context
3. Call remember() — Graphiti detects and supersedes automatically
4. (Optional) Verify with prime() that the new fact appears in the briefing

### 7.2 The `consolidate()` MCP Tool

**Purpose:** Rule-based cleanup of technical noise. No LLM calls. No semantic knowledge deleted. Safe to call at any time.

**Operations:**
1. Delete SQLite episodes with `status=failed` and `created_at < now() - 30 days`
2. Re-queue SQLite episodes with `status=pending` and `created_at < now() - 2 hours` (or mark failed if re-queue limit reached)
3. Invalidate the cached briefing for the project
4. Record a consolidation audit episode: `"Consolidation run on {date}: pruned {N} failed, requeued {M} pending. Graph unchanged."`
5. Return summary dict: `{pruned_failed, requeued_pending, briefing_invalidated, project_id}`

**Does NOT do:**
- Delete graph edges or entity nodes
- Delete `invalid_at` edges (these are the temporal history)
- Merge near-duplicate episodes
- Call any LLM

**MCP signature:**
```python
@mcp.tool()
async def consolidate(project_id: str) -> dict:
    """Prune technical noise from the knowledge graph.

    Deletes failed extraction episodes older than 30 days.
    Re-queues orphaned pending episodes.
    Refreshes the briefing cache.
    Does NOT delete graph edges or entity nodes.

    Returns: {pruned_failed, requeued_pending, briefing_invalidated}
    """
```

### 7.3 Improved `prime()` Output

**Delta section:** When `last_prime_at` is stored per-project and episodes exist with `created_at > last_prime_at`:

```
### Since Your Last Session (5 days ago)
- 3 new decisions recorded
- Key new fact: [most recent decision episode, first 100 chars]
```

**Briefing cache:** Store `cached_briefing TEXT` and `briefing_episode_count INT` on projects table. Return cached version if `episode_count == briefing_episode_count`. Regenerate and cache otherwise.

**Consolidation hint:** If `failed_episode_count > 20 OR days_since_consolidation > 30`: append "⚑ Consider running consolidate() — {N} failed episodes accumulated."

---

## 8. Technology Stack

No new dependencies required for Phase 2. All changes operate within the existing stack:

| Component | Technology | Notes |
|-----------|-----------|-------|
| Skill format | Markdown + YAML frontmatter | Per skill-creator spec |
| Consolidation logic | Python (asyncio) | New `src/tools/consolidate.py` |
| Briefing cache | SQLite (new columns) | Migration: `ALTER TABLE projects ADD COLUMN...` |
| Background pruning | asyncio.Task (existing pattern) | Reuse extraction worker pattern |
| REST endpoint | FastAPI (existing routes.py) | `POST /api/projects/{id}/consolidate` |

**Skill distribution:** Skills live in `skills/agent-harness/` in the repository. Users add them to Claude Code via the skills API or by pointing Claude Code at the skills directory. No packaging step required for in-repo skills.

---

## 9. Context Engineering Research: What the Field Agrees On

This section synthesizes current consensus from Anthropic's published research, the Claude Agent SDK documentation, and the broader AI agent engineering community, as it applies to Agent Harness Phase 2.

### The Fundamental Principle

> *"Find the smallest possible set of high-signal tokens that maximize the likelihood of your desired outcome."*
> — Anthropic, "Effective Context Engineering for AI Agents" (2025)

This applies at every layer:
- `prime()` output: smallest briefing that fully orients the agent
- Skill body: smallest instruction set that produces correct behavior
- `remember()` content: smallest fact that will still be useful in 6 months

### What Research Agrees On

**1. Context is a finite attention budget with diminishing returns.** The transformer architecture creates n² pairwise attention across all tokens. More context is not always better — it can reduce precision for long-range reasoning. Agent Harness's decision to cap `prime()` at 400 tokens is correct.

**2. Just-in-time loading beats pre-loading.** Claude Code's hybrid model — CLAUDE.md preloaded, files discovered via glob/grep — is the right pattern. Agent Harness implements this correctly: `prime()` for orientation, `recall()` for specific facts during work. The skill should teach this split explicitly.

**3. Agentic search beats semantic search for accuracy.** Starting with targeted exploration (grep, tail) is more accurate and maintainable than vector embeddings alone. Agent Harness uses hybrid search (cosine + BM25 + graph BFS), which is correct. The skill should teach agents to use `recall()` with natural language queries, not keyword lists.

**4. Sub-agents preserve context quality.** Parallel work with isolated context windows, returning condensed summaries, keeps the main agent's context clean. Agent Harness is itself a "sub-service" that handles knowledge storage so the main agent's context stays focused on the current task.

**5. Structured note-taking enables multi-session coherence.** The consensus pattern for long-horizon agents: persist notes outside the context window, retrieve them at later times. This is exactly what Agent Harness does. The skill ensures agents know to do it correctly.

**6. The best prompt is the one you iterate.** Skills should be treated like code: version-controlled, tested against real usage, improved based on observed failures. The autoresearch feedback loop (observe → gap → fix → test) applies directly to SKILL.md iteration.

### The Karpathy/autoresearch Insight Applied

karpathy/autoresearch treats `program.md` as the "one file you improve" — not the model, not the code, but the instructions that shape agent behavior. For Agent Harness, `SKILL.md` is that file. The iteration loop is:

```
1. Run agent sessions with current SKILL.md
2. Observe: what did the agent remember that it shouldn't have? What did it miss?
3. Identify the gap in SKILL.md (missing anti-pattern, ambiguous category guidance, etc.)
4. Edit SKILL.md
5. Test on the next session
6. Repeat — the skill improves session by session
```

The key autoresearch insight: **constraints drive intelligence**. A well-constrained skill (clear rules, explicit anti-patterns, concrete examples) produces better agent behavior than a vague, flexible one. Narrow the bridge; don't leave the agent in an open field.

---

## 10. Open Questions

These are unresolved design questions for Phase 2 that require either experimentation or explicit decisions before or during implementation:

**Q1: Where should the skill live for distribution?**
Options: (a) In the agent-harness repository under `skills/`, users install manually; (b) Documented in README with a copy-paste SKILL.md; (c) Published as a `.skill` file alongside the PyPI package. All three are valid. Option (a) is lowest friction for now and supports iteration. Option (c) is the right long-term answer when the skill is stable.

**Q2: What is the right cadence for background pruning?**
Options: (a) On every server startup (check all projects); (b) On each `prime()` call for that project; (c) Periodic background task (e.g., every 6 hours). Option (b) has nice properties — pruning happens naturally as projects are used — but adds latency to `prime()`. Option (c) is cleanest but requires a new asyncio task.

**Q3: Should `consolidate()` be automatic or always manual?**
The current design makes it manual (explicit tool call). An automatic trigger (e.g., after N failed episodes accumulate, or X days since last consolidation) would be more ergonomic but adds complexity and surprises. Recommendation: start manual, observe if developers actually call it, automate if they do.

**Q4: What is the right `prime()` output for a project with hundreds of episodes?**
The current briefing generator hard-codes result limits (4 decisions, 3 pitfalls, 5 recent). On a 2-year project with 500 high-quality episodes, these limits may surface the wrong things. A ranking model (recency × relevance × category weight) would improve quality but adds complexity. For Phase 2, keep the simple limits but make them configurable via environment variables.

**Q5: How should the skill handle the case where Agent Harness is not running?**
If FalkorDB is down or the MCP server isn't running, all 5 tools will fail. The skill should include a brief graceful degradation note: "If MCP tools fail, continue the session normally — Agent Harness is not required for coding work." This prevents agents from blocking on unavailable infrastructure.

**Q6: Should the skill include `recall()` query patterns?**
Agents sometimes struggle with what to put in a recall query — too specific (misses relevant edges), too broad (returns noisy results). Including 3-5 concrete good query examples in the skill might significantly improve recall quality. To be validated against real usage data.

**Q7: Multi-project context — should `init_project` be called once per session or per-task?**
A developer working across multiple repos in one session might need multiple `init_project` calls. The skill should address this: call `init_project` and `prime()` for each distinct project encountered in the session, not once globally.

---

## 11. Implementation Phases

### Phase 2a — Skill (2-3 days)

**Goal:** Ship a working `agent-harness` skill that immediately improves agent behavior.

Deliverables:
- ✅ `skills/agent-harness/SKILL.md` — core workflow, quality standard
- ✅ `skills/agent-harness/references/what-to-remember.md` — anti-patterns + good examples
- ✅ `skills/agent-harness/references/category-guide.md` — one-liner examples per category
- ✅ `skills/agent-harness/references/update-workflow.md` — fact update procedure
- ✅ Skill installed in local Claude Code and tested against 3 real sessions
- ✅ CLAUDE.md updated with skill location and usage notes

**Validation:** After 3 sessions with skill installed, zero "in-progress work" episodes appear in the graph. At least 3 high-signal decision episodes per session.

### Phase 2b — Server Maintenance (1-2 days)

**Goal:** Server-side cleanup that runs without developer intervention.

Deliverables:
- ✅ `prune_stale_episodes(project_id, days=30)` in `ProjectsService`
- ✅ Background pruning task registered at startup (alongside extraction workers)
- ✅ Briefing cache: `cached_briefing`, `briefing_episode_count` columns + migration
- ✅ `prime()` returns cached briefing when episode count unchanged
- ✅ Tests for pruning and cache logic
- ✅ `consolidate()` MCP tool + REST endpoint
- ✅ Tests for `consolidate()`

**Validation:** After 30 days of operation, `status=failed` episode count stays bounded (< 20 per project). `prime()` response time drops significantly for projects with stable knowledge.

### Phase 2c — Improved `prime()` (1 day)

**Goal:** `prime()` output includes delta section and consolidation hint.

Deliverables:
- ✅ `last_prime_at TIMESTAMP` column on projects
- ✅ Delta section: episodes since last `prime()` call
- ✅ Consolidation hint when thresholds exceeded
- ✅ Tests for delta section logic

**Validation:** A developer returning after a week immediately sees what changed. `prime()` output < 400 tokens even with delta section.

### Phase 2d — Skill Iteration Loop (Ongoing)

**Goal:** Establish structured skill improvement practice.

Process:
1. Use the skill for 5-10 sessions
2. Review the graph: what slop appeared? what was missed?
3. Open `skills/agent-harness/SKILL.md`, add/fix the relevant guidance
4. Re-test for 3 sessions
5. Commit the updated skill with a note on what was fixed and why
6. Repeat

**Validation:** Each iteration cycle improves at least one measurable behavior. Skill version history in git shows clear progression with rationale.

---

## 12. Success Criteria

**Phase 2 is complete when:**

✅ The `agent-harness` skill is installed and agents use it correctly without additional prompting

✅ A new agent on an established project calls `prime()` and describes the project accurately in its next message

✅ After 10 sessions with the skill, less than 10% of recorded episodes would be classified as "slop" (in-progress notes, already-in-codebase facts, transient debugging steps)

✅ When a developer changes a decision, the old decision appears as superseded in `prime()` output within 1 session

✅ `prime()` response time for a project with > 50 episodes: < 100ms (from cache)

✅ The graph does not accumulate `status=failed` episodes older than 30 days

✅ `consolidate()` runs successfully and returns correct counts without deleting any graph edges

✅ 100% of existing tests still pass

✅ All new code has test coverage following existing patterns

---

## 13. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Skill is too prescriptive — agents follow rules rigidly and miss edge cases | Medium | Keep SKILL.md body high-level; move detailed rules to `references/` loaded on demand. Test on varied project types. |
| Graphiti contradiction detection misses a fact update | Medium | The `update-workflow.md` reference teaches agents to phrase updates with explicit contradiction language. Also: `prime()` temporal filtering means old facts don't show up. |
| Briefing cache goes stale — agent primes with outdated briefing | Low | Cache is invalidated on any new episode for the project. Episode count comparison is the key. |
| `consolidate()` is never called — background pruning doesn't run | Medium | Implement automatic background pruning as default (configurable off). Consolidate() becomes the explicit manual version of what runs automatically. |
| Skill iteration loop is never run — skill stays at v1.0 forever | High | The loop must be treated as a first-class deliverable, not an afterthought. A session review template in `references/` would help. |

---

## 14. Future Considerations

**Post-Phase 2 (Phase 3 and beyond):**

- **LLM consolidation pass**: If the skill doesn't eliminate slop sufficiently, add an optional LLM pass that reviews episodes and suggests merges. This is the full autoDream equivalent — build it only if Phase 2 evidence shows it's needed.

- **Team skill distribution**: When the skill is stable, publish it as a `.skill` file alongside the PyPI package. Users install via `claude install agent-harness.skill`.

- **Cross-project knowledge**: Some facts are project-independent (e.g., "we always use snake_case for Python"). A global `team` project namespace could hold shared conventions.

- **Skill auto-improvement**: Use karpathy/autoresearch's loop not just for humans but for the agent itself: after each session, the agent proposes one improvement to SKILL.md for human review. The skill evolves collaboratively.

- **`prime()` + `awaySummary` integration**: A "while you were away" card in the dashboard showing what changed since last session, mirroring Claude Code's awaySummary pattern.

- **Episode analytics**: Track which episodes are hit most frequently in `recall()` results. High-hit episodes are "crystallized knowledge" — never delete them. Low-hit old episodes are candidates for LLM consolidation review.

---

## 15. Appendix

### Key Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Phase 1 PRD | `.claude/PRD.md` | Original requirements, architecture decisions |
| autoDream research | `.agents/reference/context_update.md` | Full analysis of Claude Code's memory system |
| Graphiti API reference | `.agents/reference/graphiti.md` | Graphiti patterns, search API |
| FastMCP reference | `.agents/reference/mcp-server.md` | MCP tool patterns |
| Skill Creator | `.claude/skills/skill-creator/SKILL.md` | Skill structure and creation process |

### External References

- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic: Equipping Agents for the Real World with Agent Skills](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills)
- [Anthropic: Building Agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — Skill iteration feedback loop pattern
- [Agent Skills for Context Engineering (community)](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) — Community patterns

### Current Implementation Status

- Phase 1: ✅ Complete — 148 tests, all passing
- Phase 2a (Skill): 🔲 Not started
- Phase 2b (Server maintenance): 🔲 Not started
- Phase 2c (Improved prime()): 🔲 Not started
- Phase 2d (Iteration loop): 🔲 Ongoing process
