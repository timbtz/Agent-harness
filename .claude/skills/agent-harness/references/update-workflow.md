# Update Workflow: Recording a Changed Fact

When a decision or fact changes, use this procedure to record it so that
Graphiti automatically supersedes the old version in the knowledge graph.

## Why This Matters

Graphiti detects contradictions by comparing new episode content against
existing graph entities. If you just state the new fact without mentioning
what changed, Graphiti may add it as a second fact alongside the old one —
not replace it. Including explicit contradiction language ("reverses prior X",
"replaces X with Y") reliably triggers the supersession logic, which sets
`invalid_at` on the old graph edge automatically.

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
