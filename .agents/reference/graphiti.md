# Graphiti Reference — Agent Harness

> **Version:** graphiti-core 0.28.2 (March 11, 2026)
> **Install:** `pip install graphiti-core[falkordb]`
> **License:** Apache 2.0
> **Python:** 3.10+

---

## Overview

Graphiti is a temporal knowledge graph library. It extracts entities and relationships from free-text "episodes" using LLM calls, stores them in FalkorDB, and supports hybrid retrieval (semantic + BM25 + graph traversal). Unlike RAG, it builds a structured graph of knowledge rather than embedding raw documents.

**Key characteristics:**
- 4–10 LLM calls per `add_episode()` (entity extraction + relationship extraction + deduplication)
- Non-blocking architecture — store raw episode synchronously, extract asynchronously
- Temporal awareness — facts have `valid_at`/`invalid_at` timestamps; old facts are never deleted
- Deduplication — existing entities are merged, not duplicated
- `group_id` parameter provides namespace isolation (one namespace per project)

---

## Installation

```bash
# With FalkorDB driver (required for Agent Harness)
pip install "graphiti-core[falkordb]"

# Or via uv
uv add "graphiti-core[falkordb]"
```

---

## Core Setup

### FalkorDB Driver

```python
from graphiti_core.driver.falkordb_driver import FalkorDriver

driver = FalkorDriver(
    host="localhost",    # FalkorDB host
    port=6379,           # FalkorDB port (Redis-compatible)
    database=0,          # Database index (default 0)
)
```

### LLM Client (OpenAI)

```python
from graphiti_core.llm_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig

llm_client = OpenAIClient(
    config=LLMConfig(
        api_key="sk-...",
        model="gpt-4.1-mini",   # Recommended for cost/quality balance
    )
)
```

### LLM Client (Anthropic)

```python
from graphiti_core.llm_client.anthropic_client import AnthropicClient
from graphiti_core.llm_client.config import LLMConfig

llm_client = AnthropicClient(
    config=LLMConfig(
        api_key="sk-ant-...",
        model="claude-haiku-4-5-20251001",  # Verify model ID before use
    )
)
```

### Embedder (OpenAI)

```python
from graphiti_core.embedder import OpenAIEmbedder
from graphiti_core.embedder.config import EmbedderConfig

embedder = OpenAIEmbedder(
    config=EmbedderConfig(
        api_key="sk-...",
        embedding_dim=1536,
        model="text-embedding-3-small",
    )
)
```

### Graphiti Instance

```python
from graphiti_core import Graphiti

graphiti = Graphiti(
    graph_driver=driver,
    llm_client=llm_client,
    embedder=embedder,
)
```

---

## Startup Initialization

**CRITICAL:** Must be called once on server startup before any `add_episode()` or `search()` calls. Creates vector indices (HNSW), BM25 indices, and graph constraints in FalkorDB.

```python
await graphiti.build_indices_and_constraints()
```

This is idempotent — safe to call on every startup. If indices already exist, it's a no-op.

---

## Adding Episodes

### Method Signature

```python
result = await graphiti.add_episode(
    name="episode-name",            # str: unique identifier for this episode
    episode_body="...",             # str: free-text content to extract knowledge from
    source=EpisodeType.text,        # EpisodeType enum
    source_description="...",       # str: context about the source
    reference_time=datetime.now(),  # datetime: when this knowledge was captured
    group_id="project-slug",        # str: namespace for isolation (= project_id)
)
```

### EpisodeType Enum

```python
from graphiti_core.nodes import EpisodeType

EpisodeType.text     # Free-text prose (decisions, insights, errors)
EpisodeType.message  # Conversational/chat messages
EpisodeType.json     # Structured JSON data (repo scans, config files)
```

### Returns: `AddEpisodeResult`

```python
result.episode_id     # str: unique ID for this episode
result.nodes          # list[EntityNode]: extracted entities
result.edges          # list[EntityEdge]: extracted relationships
```

### Example Usage

```python
from graphiti_core.nodes import EpisodeType
from datetime import datetime, timezone

result = await graphiti.add_episode(
    name=f"decision-{episode_id}",
    episode_body="Chose custom JWT over Supabase Auth because Supabase RLS "
                 "is incompatible with service-role keys in our multi-tenant setup.",
    source=EpisodeType.text,
    source_description="Architecture decision — authentication strategy",
    reference_time=datetime.now(timezone.utc),
    group_id="my-saas-app",
)
```

### LLM Cost Per Episode

| Model | Cost per episode (approx) |
|-------|--------------------------|
| gpt-4.1-mini | ~$0.002–0.008 |
| claude-haiku-4-5 | ~$0.001–0.005 |
| Ollama (local) | Free |

With 4–10 LLM calls per episode, budget accordingly for intensive usage.

---

## Searching the Knowledge Graph

### Method Signature

```python
results = await graphiti.search(
    query="why did we choose JWT?",   # str: natural language or keyword query
    config=SearchConfig(...),          # optional: tune search parameters
    filters=SearchFilters(...),        # optional: filter by group_id, date, etc.
    limit=10,                          # int: max results to return
)
```

### SearchConfig

```python
from graphiti_core.search.search_config import SearchConfig

config = SearchConfig(
    bm25_limit=5,        # Max results from BM25 keyword search
    vector_limit=5,      # Max results from vector similarity search
    bfs_limit=5,         # Max results from graph BFS traversal
    reranker="rrf",      # Reranking algorithm: "rrf" (Reciprocal Rank Fusion, default)
)
```

### SearchFilters (Namespace Isolation)

```python
from graphiti_core.search.search_config import SearchFilters

filters = SearchFilters(
    group_ids=["my-saas-app"],   # IMPORTANT: always filter by project's group_id
)
```

**CRITICAL:** Always pass `group_ids` in filters to prevent cross-project knowledge contamination.

### Returns: `SearchResults`

```python
results.nodes    # list[EntityNode]: matching entity nodes
results.edges    # list[EntityEdge]: matching relationships
results.episodes # list[EpisodeNode]: matching raw episodes
```

### Example: Hybrid Search with Namespace Isolation

```python
from graphiti_core.search.search_config import SearchConfig, SearchFilters

results = await graphiti.search(
    query="Supabase authentication issues",
    config=SearchConfig(bm25_limit=5, vector_limit=5, bfs_limit=3),
    filters=SearchFilters(group_ids=["my-saas-app"]),
    limit=10,
)

# Format top results
for node in results.nodes[:5]:
    print(f"Entity: {node.name} — {node.summary}")
for edge in results.edges[:3]:
    print(f"Relationship: {edge.source_node_id} → {edge.target_node_id}: {edge.fact}")
```

---

## Key Data Models

### EntityNode

```python
node.uuid          # str: unique identifier
node.name          # str: entity name (e.g., "Supabase Auth", "JWT")
node.summary       # str: LLM-generated description of the entity
node.labels        # list[str]: graph node labels
node.group_id      # str: namespace this node belongs to
node.created_at    # datetime
node.valid_at      # datetime | None: when this fact became true
node.invalid_at    # datetime | None: when this fact was superseded (None = still valid)
```

### EntityEdge

```python
edge.uuid           # str: unique identifier
edge.source_node_id # str: UUID of source entity
edge.target_node_id # str: UUID of target entity
edge.fact           # str: relationship description (e.g., "uses", "replaced by")
edge.group_id       # str: namespace
edge.created_at     # datetime
edge.valid_at       # datetime | None
edge.invalid_at     # datetime | None
```

### EpisodeNode

```python
episode.uuid             # str: unique identifier
episode.name             # str: episode name passed to add_episode
episode.content          # str: original episode body
episode.source           # EpisodeType
episode.source_description # str
episode.group_id         # str: namespace
episode.created_at       # datetime
episode.valid_at         # datetime
```

---

## Temporal Knowledge Management

Graphiti never deletes facts — it manages temporal validity:

- **New fact contradicts old fact:** Old fact's `invalid_at` is set to `now()`; new fact has `valid_at = now()`, `invalid_at = None`
- **Querying current state:** Filter for `invalid_at = None` to get only active facts
- **Querying history:** All facts are always available for historical analysis

This is handled automatically by Graphiti — you don't need to manage timestamps manually.

---

## Background Processing Pattern (Agent Harness)

`remember()` stores raw episode synchronously and triggers Graphiti extraction asynchronously:

```python
import asyncio
from asyncio import Semaphore

# Limit concurrent extractions to prevent LLM rate limit errors
extraction_semaphore = Semaphore(4)   # 3-5 concurrent tasks max

async def run_extraction(episode_id: str, content: str, group_id: str):
    async with extraction_semaphore:
        try:
            await update_episode_status(episode_id, "processing")
            await graphiti.add_episode(
                name=f"ep-{episode_id}",
                episode_body=content,
                source=EpisodeType.text,
                source_description="agent knowledge",
                reference_time=datetime.now(timezone.utc),
                group_id=group_id,
            )
            await update_episode_status(episode_id, "complete")
        except Exception as e:
            logger.error(f"Extraction failed for {episode_id}: {e}", exc_info=True)
            await update_episode_status(episode_id, "failed")

# In remember() tool handler:
task = asyncio.create_task(run_extraction(episode_id, content, project_id))
# Store task reference to prevent GC before completion
_background_tasks.add(task)
task.add_done_callback(_background_tasks.discard)
```

---

## Startup with Retry

FalkorDB may not be immediately ready on server start. Use exponential backoff:

```python
import asyncio
from graphiti_core.driver.falkordb_driver import FalkorDriver

async def init_graphiti_with_retry() -> Graphiti:
    delays = [1, 2, 4, 8, 15]  # ~30s total
    last_error = None
    for attempt, delay in enumerate(delays, 1):
        try:
            driver = FalkorDriver(host="localhost", port=6379)
            graphiti = Graphiti(driver=driver, llm_client=llm, embedder=emb)
            await graphiti.build_indices_and_constraints()
            logger.info("FalkorDB connected and indices ready")
            return graphiti
        except Exception as e:
            last_error = e
            logger.warning(f"FalkorDB connect attempt {attempt} failed: {e}")
            if attempt < len(delays):
                await asyncio.sleep(delay)
    raise RuntimeError(f"FalkorDB unavailable after {len(delays)} attempts: {last_error}")
```

---

## Fallback Search for Unextracted Episodes

When `recall()` is called before background extraction completes, also search raw episode text:

```python
async def hybrid_recall(query: str, project_id: str) -> list[dict]:
    # Primary: graph search
    graph_results = await graphiti.search(
        query=query,
        filters=SearchFilters(group_ids=[project_id]),
        limit=10,
    )

    # Fallback: search raw episodes with status=pending or status=processing
    raw_results = await search_raw_episodes(
        query=query,
        project_id=project_id,
        statuses=["pending", "processing"],
    )

    return merge_and_deduplicate(graph_results, raw_results)
```

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ConnectionError` to FalkorDB | FalkorDB not running | `docker compose up -d`, check `docker compose ps` |
| `AuthenticationError` | Bad LLM API key | Check `LLM_API_KEY` in `.env` |
| `RateLimitError` | Too many concurrent extractions | Reduce semaphore limit, or switch to cheaper model |
| Index not found | `build_indices_and_constraints()` not called | Always call at startup |
| Cross-project contamination | Missing `group_ids` filter | Always pass `filters=SearchFilters(group_ids=[project_id])` |

---

## Version Notes

- **0.28.x:** Current stable series. API shape is stable.
- **Breaking changes:** Check graphiti-core CHANGELOG before upgrading minor versions.
- **FalkorDB driver:** Part of core package when installed with `[falkordb]` extra.

---

*See also: [FalkorDB reference](.agents/reference/falkordb.md) for database setup and Cypher queries.*
