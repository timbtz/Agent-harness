# autoDream — Memory Consolidation Research

> Source: Claude Code `services/autoDream/`, `services/extractMemories/`, `services/compact/`, `services/SessionMemory/`, `services/AgentSummary/`
> Purpose: Research how these patterns can improve the Agent Harness knowledge graph
> Audience: Future Claude sessions working on this repository
> Status: Research only — no implementation decisions made; read and draw your own conclusions

---

## What is autoDream?

Claude Code has a background process called **autoDream** — a memory consolidation engine that fires periodically as a forked subagent. The naming is deliberate: while the user sleeps (literally between sessions), Claude consolidates fragmented, redundant, and contradicting knowledge into cleaner, more structured memories.

The concept is not a gimmick. It solves a real problem: **knowledge accumulates faster than it can be curated**. Without consolidation, memory stores drift toward:
- Redundant facts about the same topic stored in multiple places
- Stale facts that were true in a past version but are now wrong
- Relative dates ("yesterday", "last week") that become meaningless after time passes
- Contradictory facts where both old and new co-exist with no resolution
- Oversized indexes that hit size limits and get truncated, losing their purpose

autoDream runs a structured 4-phase pass to fix all of these, using the LLM itself as the curator. The result is a leaner, more accurate, more trustworthy memory store.

---

## The autoDream Architecture (Claude Code)

### Overview

```
[Main session ends]
      ↓
[Post-sampling hook fires: executeAutoDream()]
      ↓
Gate 1: isGateOpen() → feature flag + autoMemoryEnabled + not remote mode
Gate 2: Time gate  → hours since lastConsolidatedAt >= 24h
Gate 3: Scan throttle → 10min between session scans
Gate 4: Session gate → N completed sessions since last consolidation >= 5
Gate 5: Lock gate  → tryAcquireConsolidationLock() → PID-based mutex
      ↓
[Build consolidation prompt]
      ↓
[runForkedAgent()] → isolated Claude subagent (read-only Bash, write only in memory dir)
      ↓
Phase 1 — Orient: ls memory dir, read MEMORY.md, skim topic files
Phase 2 — Gather signal: daily logs → drifted memories → transcript search
Phase 3 — Consolidate: merge, convert dates, delete contradictions, update topic files
Phase 4 — Prune: keep MEMORY.md < 200 lines / 25KB, remove stale pointers
      ↓
[completeDreamTask()] → success, update lock mtime
[OR rollbackConsolidationLock()] → failure, rewind mtime so time-gate fires again
```

### Gate System (Cheapest-first Ordering)

Gates are evaluated in cheapest-first order to avoid expensive I/O when earlier gates fail:

1. **Feature flag / user setting**: single synchronous read from cached settings. `isAutoDreamEnabled()` checks `settings.autoDreamEnabled` first, then falls back to a GrowthBook feature flag (`tengu_onyx_plover`). This is pure memory, no disk.

2. **Time gate**: reads `stat()` on a lock file. The lock file's **mtime IS `lastConsolidatedAt`** — no separate timestamp file. One `stat()` per trigger attempt. Default: 24 hours.

3. **Scan throttle**: closure-scoped variable `lastSessionScanAt`. When the time gate passes but the session gate doesn't, the lock mtime doesn't advance (no dream ran), so the time gate passes again every turn. The throttle prevents re-scanning sessions every turn by enforcing a 10-minute minimum between scans.

4. **Session gate**: reads session transcript file mtimes from disk. Any session with mtime after `lastConsolidatedAt` is counted. The *current* session is excluded (its mtime is always recent). Default: 5 sessions must have passed.

5. **Lock gate**: write-then-verify PID-based mutex. Acquires by writing `process.pid` to the lock file, then re-reading to confirm no race winner overwrote it. Stale locks (> 1h with dead PID) are reclaimed. Prevents concurrent dreams across multiple Claude Code windows.

### Lock File as State Machine

The `consolidate-lock` file is elegant in its dual role:

- **Present with live PID and recent mtime**: dream in progress, block
- **Present with dead PID**: orphaned/crashed dream, reclaim
- **Present with old mtime (> 1h)**: stale lock, reclaim
- **Absent**: never dreamed, `lastConsolidatedAt = 0`, always passes time gate
- **mtime = lastConsolidatedAt**: updated by `writeFile()` on successful dream

Rollback (on failure) calls `utimes()` to rewind the mtime to the pre-dream value, so the time gate fires again on the next session. The scan throttle acts as backoff — it won't recheck for 10 minutes even if the time gate passes immediately.

### The Consolidation Prompt (Four Phases)

The prompt is structured, ordered, and explicit:

```
Phase 1 — Orient
  - ls memory directory
  - read MEMORY.md (the index)
  - skim existing topic files to avoid creating duplicates

Phase 2 — Gather recent signal (priority order)
  1. Daily logs if present (append-only stream)
  2. Existing memories that drifted (facts contradicting current codebase)
  3. Transcript search for specific context (grep JSONL, narrow terms only)
  Note: "Don't exhaustively read transcripts. Look only for things you already suspect matter."

Phase 3 — Consolidate
  - Merge new signal into existing topic files (not new files for each thing)
  - Convert relative dates ("yesterday") to absolute dates (2026-03-31)
  - Delete contradicted facts at the source

Phase 4 — Prune and index
  - Update MEMORY.md to stay < 200 lines AND < 25KB
  - Each MEMORY.md entry: one line, ~150 chars max, format: "- [Title](file.md) — one-line hook"
  - Remove stale/wrong/superseded pointers
  - Demote verbose entries: if a line is > ~200 chars, its content belongs in the topic file
  - Resolve contradictions between files
```

The subagent has **read-only Bash** (ls, find, grep, cat, stat, wc, head, tail). It can read anywhere, write only inside the memory directory. This is enforced by a `canUseTool` permission callback.

### Related Services: The Memory Ecosystem

Claude Code has a full memory ecosystem. autoDream is just one component:

#### `extractMemories` — Per-turn extraction

Fires after every completed query loop (when the model produces a final response). Uses a cursor (`lastMemoryMessageUuid`) to process only new messages since the last extraction. Throttled via turn count (default: every N turns). Avoids running if the main agent already wrote to memory during the turn. Maximum 5 turns per extraction run (prevents rabbit holes).

**Trigger logic**: after each stop hook, if enabled, if new model-visible messages exist since cursor.

**Key insight**: it's not "extract everything" — it's "extract from the delta since last time." The cursor is the key mechanism for incremental processing.

#### `SessionMemory` — Intra-session rolling notes

A different system from autoDream. Maintains a rolling notes file about the *current* conversation. Triggered by token + tool-call thresholds. When the session gets long (context window approaching limits), this provides a compressed summary that survives compaction.

**Trigger**: token threshold (context size) AND tool-call count threshold, both must be met.

#### `AgentSummary` — Real-time sub-agent progress

Fires every 30 seconds during a running sub-agent to generate a 3-5 word summary for the UI. Pure summarization, no writes.

#### `microCompact` / `autoCompact` — Context window management

Not memory consolidation but context compression. Removes old tool results from the conversation history to keep the context window under the limit. Two variants:
- **microCompact**: removes individual tool results inline, without regenerating the full summary
- **autoCompact**: full context compaction, generates a summary and truncates history

---

## How Agent Harness Differs (Critical Architectural Gaps)

Before mapping autoDream to Agent Harness, understand what's fundamentally different:

| Aspect | Claude Code (autoDream) | Agent Harness |
|--------|------------------------|---------------|
| Memory format | Markdown files in `~/.claude/projects/…/memory/` | Episodes in SQLite + entity/edge graph in FalkorDB via Graphiti |
| Consolidation actor | LLM subagent (forked Claude) | Could be: LLM via API call, OR rule-based Python, OR Graphiti/FalkorDB queries |
| Trigger context | In-process, hooks into post-sampling lifecycle | Separate server process; must be triggered externally or on a timer |
| Session awareness | Knows exactly which sessions have new data (JSONL transcripts) | Only knows episode timestamps — no direct session concept |
| Read permission scope | Subagent can grep any project file (read-only) | MCP tools are read/write; no forked-subagent pattern exists |
| Granularity | File-level (topic files + MEMORY.md index) | Triple-level (episodes → Graphiti entity extraction → FalkorDB edges) |
| Contradiction detection | LLM-reasoned: "this fact contradicts what I see in the codebase now" | Partially automated: Graphiti computes `invalid_at` on edges when new contradicting facts arrive |
| Drift detection | LLM scans codebase to check if memories are still true | Not implemented |
| Redundancy detection | LLM merges near-duplicate topic files | Not implemented |

The most important difference: **Graphiti already does some of this automatically**. When a new episode contradicts an existing graph edge, Graphiti sets `invalid_at` on the old edge. Agent Harness *partially* handles contradiction automatically at the graph level. What it doesn't handle is the SQLite episode layer, which accumulates without limit.

---

## Problems in the Current Agent Harness Knowledge Graph

Understanding autoDream is most useful when mapped to concrete problems in this codebase:

### 1. SQLite Episodes Accumulate Without Limit

Every `remember()` call adds a new row. After 100 sessions on a project, there are hundreds of raw episodes. `prime()` and `recall()` search across all of them. Quality degrades as the database grows, because:
- Old, now-wrong episodes contaminate recall results
- Near-duplicate episodes about the same topic add noise
- `pending` and `failed` episodes (Graphiti extraction failed) linger as low-quality fallback search material

### 2. No Cross-Session Knowledge Quality Pass

Graphiti computes `invalid_at` per-edge when processing a *new* episode that contradicts an old one. But:
- If no new contradicting episode arrives, old wrong edges stay valid forever
- There's no periodic check: "is this graph edge still consistent with what's in the codebase?"
- Raw SQLite episodes are never marked stale — only graph edges get `invalid_at`

### 3. `prime()` Generates Briefing Fresh Each Call

`generate_briefing()` in `briefing.py` runs two `knowledge.search()` calls against Graphiti + a SQLite episode query every time `prime()` is called. This costs ~300ms P95 per call and returns the same output until new episodes arrive. No caching.

### 4. No Deduplication Layer

If a developer runs five sessions all talking about "we use JWT for auth", there are five separate `[DECISION] We use JWT for authentication` episodes in SQLite, five Graphiti extraction jobs, and multiple redundant graph edges. The graph will consolidate some of these via Graphiti's entity merging, but the raw SQLite layer will keep all five.

### 5. Pending/Failed Episode Noise

Episodes with `status=failed` are searchable via `get_episodes_for_fallback()` as a quality-loss mitigation. But after hundreds of sessions, failed episodes become a significant fraction of the fallback search pool. There's no "garbage collection" that removes genuinely useless failed episodes.

### 6. MEMORY.md Is Always Loaded (200-line Limit)

The per-project `MEMORY.md` in `~/.claude/projects/…/memory/` (Claude Code's auto-memory) has a hard 200-line truncation. Agent Harness's knowledge graph has no equivalent size constraint — it grows forever. Large graphs degrade FalkorDB query performance and increase recall result noise.

---

## Mapping autoDream Concepts to Agent Harness

Below are the concrete mechanisms from autoDream and how each might translate. These are **possibilities**, not prescriptions. Each has trade-offs.

### Concept 1: Time + Session Gate → Triggered Consolidation

**Claude Code**: dream fires when `hours_since_last_consolidation >= 24` AND `completed_sessions_since_last >= 5`.

**Agent Harness mapping options**:

- **Episode count gate**: trigger consolidation when new episode count since last consolidation >= N (e.g., 20 episodes). Simpler than session tracking, no session concept needed. SQLite query: `SELECT COUNT(*) FROM episodes WHERE project_id=? AND created_at > ?`.

- **Calendar gate**: on first `prime()` call each day, check if consolidation is due. Cheap — just read a `last_consolidated_at` timestamp from SQLite.

- **Manual trigger**: add `POST /api/projects/{id}/consolidate` REST endpoint + `consolidate(project_id)` MCP tool. Never runs automatically; called explicitly when the developer decides. Low risk, maximum control.

- **Background scheduler**: asyncio periodic task (e.g., every 6 hours) checking all projects for consolidation eligibility. Runs in the same server process alongside existing background workers.

**Trade-off**: Automatic triggers require careful gate design to avoid over-firing. A manual trigger is always safe. If budget and simplicity matter, start with a manual trigger.

### Concept 2: Consolidation Lock → Prevent Concurrent Consolidation

**Claude Code**: file-based PID lock. mtime = lastConsolidatedAt. Rollback on failure rewinds mtime.

**Agent Harness mapping**: Agent Harness already has SQLite. A simple `consolidation_lock` table or a `last_consolidated_at` + `consolidation_in_progress` column on the `projects` table achieves the same effect. Python's asyncio ensures single-process safety; a DB-level lock (SQLite `EXCLUSIVE` transaction or a `locked_by` column) handles multi-process cases if uvicorn workers ever scale.

The key insight from the lock design: **the timestamp that gates the trigger IS the lock's write time**. If consolidation fails, you rollback the timestamp so the gate fires again. If consolidation succeeds, the timestamp advances and the gate won't fire for another period. This is elegant — one field serves two purposes.

### Concept 3: Four-Phase Prompt → Structured Consolidation Pass

**Claude Code**: 4-phase prompt (Orient → Gather → Consolidate → Prune).

**Agent Harness mapping**:

If using an LLM for consolidation (most aligned with autoDream), a structured prompt would look like:

```
Phase 1 — Orient
  - Read all episodes for project {id} since last consolidation
  - Read current graph entities and edges from FalkorDB via API
  - Note which episodes have status=complete (graph-extracted) vs failed/pending

Phase 2 — Gather signal
  - Find near-duplicate episodes (same topic, different wording)
  - Find episodes where the graph edge has invalid_at set (Graphiti already detected contradiction)
  - Find episodes older than N days with no corresponding valid graph edge (extraction failed + old)

Phase 3 — Consolidate
  - For near-duplicates: draft a merged summary episode that replaces them
  - For explicitly superseded facts (invalid_at set by Graphiti): mark the source SQLite episode as consolidated
  - For stale-but-valid facts: decide if they're still true or should be marked outdated

Phase 4 — Prune
  - Delete merged-into/superseded SQLite episodes
  - Record one "consolidation" episode summarizing what was merged
  - Update project metadata: last_consolidated_at, episode_count_at_consolidation
```

However, LLM consolidation is expensive (many API calls) and adds complexity. See alternative approaches below.

### Concept 4: Read-Only Scope → Safe Exploration Without Side Effects

**Claude Code**: subagent can read anything, write only in the memory directory. `canUseTool` enforces this.

**Agent Harness mapping**: a consolidation pass (LLM or rule-based) should be able to call:
- `GET /api/projects/{id}/insights` — read all episodes
- `GET /api/projects/{id}/graph` — read graph data
- `POST /api/projects/{id}/search` — search recall

And write only via:
- `DELETE /api/projects/{id}/episodes/{episode_id}` — remove superseded episodes
- `POST /api/projects/{id}/remember` — add consolidation summary episodes

No free-form graph mutation needed. If an LLM consolidation agent is used, restrict it to these endpoints.

### Concept 5: Cursor / Incremental Processing → Process Only New Data

**Claude Code**: `lastMemoryMessageUuid` cursor in `extractMemories` — only processes messages since the last extraction run.

**Agent Harness mapping**: a `last_consolidated_at` timestamp on projects already exists (or could be added). During consolidation, only examine episodes created after this timestamp. Graph edges are already timestamped (`valid_at`, `invalid_at`). No need to re-process everything on every run.

**Key insight**: the cursor design is what makes Claude Code's extraction lightweight. Without it, every trigger would re-process the entire history. Always process incrementally.

### Concept 6: Drift Detection → Codebase Validation

**Claude Code**: the LLM subagent can grep the actual codebase (read-only Bash) and check if memories still reflect reality. "Did we actually migrate to PostgreSQL? Let me check the schema files."

**Agent Harness mapping**: Agent Harness already has the `scan_repo` capability for initial scanning. The same mechanism could be used in reverse during consolidation:

```
For each architecture/decision episode:
  - Re-scan the relevant file mentioned in the episode
  - If the file no longer exists or no longer contains the relevant pattern,
    mark the episode as potentially stale (add a flag or tag)
```

This is the most powerful but also most complex feature. It requires knowing *which* file each episode was about (not stored currently). A simpler version: just flag episodes > 90 days old with status=complete as "potentially stale" and surface them in the dashboard for human review.

### Concept 7: Pruning + Index Maintenance → Keep the Graph Lean

**Claude Code**: Phase 4 keeps MEMORY.md under 200 lines / 25KB. Removes stale pointers. Demotes verbose lines.

**Agent Harness mapping**: there's no equivalent size constraint on the knowledge graph. Over time, the FalkorDB graph grows with:
- Superseded edges (invalid_at set) that are kept for temporal graph view but never contribute to recall
- Orphaned entity nodes with no recent edges
- Episodic nodes for failed extractions that left dangling references

A periodic prune could:
1. Delete edges with `invalid_at` older than N days (e.g., 180 days) — they're no longer in the temporal window anyone would use
2. Delete orphaned entity nodes (no edges, no mentions)
3. Remove SQLite episodes with status=failed older than N days (they failed LLM extraction and are now just noise)

This is **rule-based**, no LLM needed, low risk, and has a clear measurable effect on graph size.

---

## Concrete Implementation Approaches (From Simple to Complex)

The following are distinct, composable approaches. A future implementer can choose any subset. They are ordered from low-risk/low-cost to high-value/high-complexity.

---

### Approach A: Episode Pruning (No LLM, Pure Rule-Based)

**What**: Periodic background job that deletes clearly-useless SQLite episodes.

**Rules**:
- Delete `failed` episodes older than 30 days (Graphiti extraction failed; old enough that retry won't help)
- Delete `pending` episodes older than 1 hour (server probably crashed mid-queue; mark as failed first, then re-queue or delete)

**Existing support**: `projects.py` already has `delete_episode()`. `get_all_orphaned_episodes()` re-queues `pending` episodes on restart. A pruning step that *deletes* failed old ones is the natural complement.

**Impact**: Reduces SQLite episode count for old projects. Cleaner fallback search results. No quality loss (failed episodes were already lowest-quality recall candidates).

**Implementation surface**: Add `prune_stale_episodes(project_id, days=30)` to `ProjectsService`. Call it in the background worker or as a periodic asyncio task.

---

### Approach B: Graph Edge Pruning (FalkorDB, No LLM)

**What**: Delete FalkorDB edges where `invalid_at` is more than N days ago.

**Rationale**: The temporal graph view in the dashboard already shows superseded edges. But edges accumulate forever. After 6 months, there are thousands of `invalid_at` edges that no one will view via the temporal scrubber. They slow down queries and add recall noise (even though `briefing.py` already filters them, `search()` results may include them if Graphiti doesn't filter `invalid_at` in its edge ranking).

**Implementation surface**: Add `prune_stale_edges(project_id, days=180)` to `KnowledgeService`. Uses `asyncio.to_thread()` per the existing pattern. Cypher:
```cypher
MATCH ()-[r]->()
WHERE r.group_id = $gid AND r.invalid_at IS NOT NULL
AND r.invalid_at < datetime() - duration({days: $days})
DELETE r
```

**Trade-off**: Permanently destroys historical temporal data. Make `days` configurable. Consider a soft-delete option (mark but don't delete) for projects that need audit trails.

---

### Approach C: Briefing Pre-computation / Caching

**What**: Cache the generated briefing in SQLite. Invalidate when new episodes arrive.

**Rationale**: `prime()` always calls `generate_briefing()`, which runs two `knowledge.search()` Graphiti calls + a SQLite episodes query. These are ~300ms P95. If the project hasn't changed since last `prime()`, the output is identical. Cache it.

**Implementation surface**: Add `cached_briefing TEXT` and `briefing_generated_at TIMESTAMP` and `episode_count_at_briefing INT` to the `projects` table. In `prime.py`: check if `episode_count == episode_count_at_briefing`; if so, return cached briefing. Otherwise, regenerate and cache.

**Impact**: Near-instant `prime()` for projects with no new episodes since last session. Very common case.

**Alternative**: Cache at the API layer with a short TTL (60 seconds) using `functools.lru_cache` or `cachetools`. Simpler but doesn't survive server restarts.

---

### Approach D: Episode Deduplication (Embedding-Based, No LLM)

**What**: After a batch of new episodes finishes Graphiti extraction, compute cosine similarity between new episode embeddings and existing episodes. If similarity > 0.92, mark the older one as superseded.

**Rationale**: "We use JWT for auth" and "Authentication uses JWT tokens" are near-duplicates. Graphiti may or may not merge their extracted entities (depends on entity extraction quality). The raw SQLite episodes will always be two separate rows. Deduplication at the episode layer removes one.

**Implementation surface**: Graphiti's embedder (`self._embedder`) can compute embeddings outside of `add_episode()`. Store embeddings in SQLite (`episode_embedding BLOB`) on episode creation. During extraction completion, run cosine similarity against recent episodes for the same project.

**Challenge**: Storing 1536-float embeddings in SQLite per episode (~6KB each) adds storage. For 1000 episodes that's ~6MB — acceptable. Similarity search over all episodes is O(N) — fine up to ~10k episodes, after which a vector index is needed (FalkorDB already has one).

**Alternative**: Skip the SQLite embedding storage and use FalkorDB's existing vector index via Graphiti's search to find near-duplicate episodic nodes after extraction. If two Episodic nodes have similarity > threshold, delete the older one's source SQLite episode.

---

### Approach E: LLM Consolidation Pass (autoDream-Equivalent)

**What**: Periodic background job that uses an LLM to reflectively reorganize all knowledge for a project.

**Trigger**: When `new_episodes_since_last_consolidation >= N` (e.g., 15).

**Prompt structure** (autoDream's four phases adapted):
```
Phase 1 — Orient
  Read all episodes for project (category, status, content, created_at)
  Read recent graph summary (entities + active edges from /api/projects/{id}/graph)

Phase 2 — Gather signal
  Identify: near-duplicate episodes (same topic, redundant)
  Identify: episodes where Graphiti set invalid_at (explicitly superseded by new fact)
  Identify: old episodes (> 60 days) in categories "architecture" or "decision" that might be stale

Phase 3 — Consolidate
  For each group of near-duplicates:
    Draft a single merged episode that captures all nuance
    Recommend deleting the redundant originals

Phase 4 — Output
  Return a structured JSON: {
    "to_delete": [list of episode_ids],
    "to_add": [list of {content, category}],
    "summary": "what was consolidated and why"
  }
```

The consolidation runner (Python code) then executes the LLM's decisions: calling `delete_episode()` for each item in `to_delete`, `remember()` for each item in `to_add`.

**Why structured JSON output**: unlike autoDream (which lets the LLM directly write files), Agent Harness should keep the LLM in an advisory role. The Python code validates and applies the changes. This prevents the LLM from deleting things it shouldn't, and adds an audit trail.

**Cost**: depends on episode count. For a project with 50 episodes, roughly 2-4 LLM calls to read + reason + output. With `gpt-4.1-mini` at ~$0.0004/1k input tokens, reading 50 episodes (~5k tokens) costs ~$0.002 per consolidation run. Acceptable.

**Risk**: LLM may incorrectly merge distinct concepts. Mitigate by: (1) only suggesting merges for episodes with cosine similarity > 0.88 in the same category, (2) requiring the LLM to explain each merge, (3) logging all decisions for human review.

---

### Approach F: Consolidation Episode as "Dream Record"

**What**: After any consolidation pass (LLM or rule-based), store a consolidation record as an episode with category `architecture` or a new category `consolidation`.

**Content**: "Consolidation on 2026-04-01: merged 3 JWT auth episodes into 1, pruned 2 failed episodes. Decisions section now has 8 active facts. Total episodes: 32 (was 41)."

**Rationale**: autoDream returns a summary of what it did. This creates an audit trail. The agent can also `recall()` past consolidation events to understand the project's knowledge health over time.

**This is low-cost to add to any other approach.**

---

## What Agent Harness Already Does (vs. What autoDream Does)

This section prevents duplicate work — don't reinvent what exists:

| autoDream Capability | Agent Harness Equivalent | Gap |
|---------------------|--------------------------|-----|
| Contradiction detection | Graphiti sets `invalid_at` on superseded edges automatically | Graphiti does this well at the graph level; SQLite episodes remain unaffected |
| Temporal filtering | `briefing.py` filters `invalid_at IS NOT NULL` | Done; works correctly |
| Stale pointer removal | Phase 4 removes MEMORY.md pointers | No equivalent; episodes/edges accumulate forever |
| Near-duplicate detection | Not present | Not present; biggest gap |
| Date normalization | Phase 3 converts relative to absolute | Not needed in Agent Harness (timestamps are stored as datetimes, not free text) |
| Index size control | MEMORY.md < 200 lines / 25KB | No equivalent size constraint; `prime()` output is bounded by code logic |
| Orphan re-queue | `get_all_orphaned_episodes()` on server restart | Done (Phase 5) |
| Session awareness | Knows which sessions contributed data | Not tracked; only episode timestamps |
| Read-only exploration | Subagent can grep the codebase | `scan_repo` on project init; no periodic re-scan |

---

## Implementation Considerations

### Async Safety

Any consolidation work must respect the existing asyncio architecture:
- Background consolidation should run as an `asyncio.Task` (like the existing extraction workers)
- Consolidation should hold a "soft lock" in SQLite (not a hard file lock) to prevent multiple concurrent consolidations
- FalkorDB mutations must use `asyncio.to_thread()` per CLAUDE.md rule #9

### Backward Compatibility

Any new SQLite columns (e.g., `last_consolidated_at`, `cached_briefing`) must be added via migrations that add the column with a `DEFAULT NULL` or `DEFAULT 0` to avoid breaking existing databases. No existing tables should be dropped.

### The Graphiti Layer is Opaque

Graphiti entity extraction runs asynchronously and cannot be directly interrupted or modified by a consolidation pass. The safe approach:
- **SQLite layer**: fully under our control; can delete/update episodes freely
- **FalkorDB graph layer**: partially under our control; `delete_node()` and `delete_edge()` are implemented in `knowledge.py`; but we cannot retroactively fix what Graphiti extracted
- **Graphiti's `add_episode()`**: cannot be replayed selectively; if you delete a graph node, the knowledge is gone from the semantic graph

**Implication**: consolidation should be conservative about deleting graph entities. Deleting SQLite episodes is safe (they're the raw input layer). Deleting FalkorDB edges/nodes is lossy (the semantic knowledge is gone).

### The Flag Question

autoDream is feature-flagged and user-configurable. Should Agent Harness consolidation be?

- **Yes, if**: the feature might be unexpected or costly for users
- **No, if**: it's purely rule-based pruning with no risk of data loss

Rule-based pruning (Approaches A, B) of clearly-stale data can default-on. LLM consolidation (Approach E) should be configurable via `.env` (e.g., `CONSOLIDATION_ENABLED=true`, `CONSOLIDATION_MIN_EPISODES=15`).

---

## Recommended Reading Order for Implementers

If you plan to implement any of the above, read in this order:

1. `src/services/projects.py` — understand the SQLite schema, `delete_episode()`, `get_all_orphaned_episodes()`
2. `src/services/knowledge.py` — understand `delete_node()`, `delete_edge()`, `get_graph_data()`
3. `src/server.py` — understand how background tasks/workers are managed (the `_extraction_worker` pattern)
4. `CLAUDE.md` §7 (Code Patterns) — especially `asyncio.to_thread()` and the worker queue pattern
5. `src/api/routes.py` — understand what REST endpoints exist (consolidation could be a new route here)
6. `tests/test_knowledge_service.py` and `tests/test_projects_service.py` — test patterns to follow

For the LLM consolidation approach (E), additionally read:
- `src/tools/remember.py` — how episodes are created
- `src/tools/forget.py` — how episodes are deleted via MCP

---

## Summary of Opportunities

Ranked by impact-to-effort ratio:

| Priority | Approach | Impact | Effort | Risk |
|----------|----------|--------|--------|------|
| High | A: Prune failed/stale SQLite episodes | Cleaner recall | Low | None |
| High | C: Cache briefing | Faster prime() | Low | None |
| Medium | B: Prune stale FalkorDB edges | Smaller graph, faster queries | Low-Medium | Low (configurable days threshold) |
| Medium | D: Episode deduplication via embeddings | Less redundancy | Medium | Medium (need embedding storage) |
| Low-Medium | F: Consolidation audit record | Observability | Very Low | None |
| Low | E: LLM consolidation pass | Best quality improvement | High | Medium (LLM errors) |
| Low | Drift detection (repo re-scan) | Accuracy | High | Medium (file not always present) |

The highest-leverage starting point is probably **A + C together** — prune obviously bad episodes and cache briefings. Both are low-risk, low-effort, and deliver immediate improvements to `prime()` quality and speed.

**Approach E (LLM consolidation)** is the true autoDream equivalent and would deliver the biggest quality improvement, but is the most complex to implement safely. It should be attempted only after A-C are in place.

---

## Open Questions for Implementers

These are unresolved design questions that a future implementer should decide:

1. **What's the right deduplication threshold?** Cosine similarity 0.88? 0.92? Too low = merging distinct things. Too high = missing obvious duplicates.

2. **Should consolidation episodes be searchable?** If you store a `[consolidation]` episode, it shows up in `recall()` results, which might be surprising. Either use a new category that's excluded from search, or don't store them at all.

3. **How to handle the embedding storage dilemma?** FalkorDB already has vector indices; duplicate storage in SQLite might not be worth it. But querying FalkorDB for similarity during SQLite consolidation creates a cross-service dependency. What's the right boundary?

4. **When should graph entities be deleted vs. left?** The dashboard temporal graph view depends on having historical edges (including `invalid_at` ones). If we prune them, the temporal scrubber becomes less useful. Is the temporal view important enough to justify keeping old edges?

5. **Is there a multi-project consolidation story?** Some knowledge (e.g., "our team uses snake_case for Python") might apply across projects. autoDream only operates per-project-dir. Agent Harness has the project isolation model baked in. Cross-project consolidation is outside scope but worth flagging.

6. **Should `prime()` tell the agent when consolidation is overdue?** If a project has 200 episodes and hasn't been consolidated in 30 days, `prime()` could add a note: "⚠️ 187 unconslidated episodes — consider running consolidate()". This makes the feature discoverable.
