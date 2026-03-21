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
from graphiti_core.embedder import OpenAIEmbedder, OpenAIEmbedderConfig

# Note: EmbedderConfig does NOT exist — use OpenAIEmbedderConfig
embedder = OpenAIEmbedder(
    config=OpenAIEmbedderConfig(
        api_key="sk-...",
        embedding_dim=1536,
        embedding_model="text-embedding-3-small",  # param is embedding_model, not model
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

### Returns: `AddEpisodeResults`

```python
result.episode        # EpisodicNode: the stored episode (use result.episode.uuid for ID)
result.nodes          # list[EntityNode]: extracted entities
result.edges          # list[EntityEdge]: extracted relationships
result.episodic_edges # list[EpisodicEdge]: edges from episode to entities
result.communities    # list[CommunityNode]
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
# search() returns list[EntityEdge] — NOT a SearchResults object
edges = await graphiti.search(
    query="why did we choose JWT?",   # str: natural language or keyword query
    group_ids=["my-saas-app"],         # list[str]: namespace filter (use this, not filters=)
    num_results=10,                    # int: max results (NOT limit=)
    search_filter=None,                # optional SearchFilters for date/label filtering
)
```

### SearchFilters (for date/label filtering)

```python
# Import from search_filters, NOT search_config
from graphiti_core.search.search_filters import SearchFilters

filters = SearchFilters(
    node_labels=["Entity"],
    edge_types=["RELATES_TO"],
    # date filters also available
)
# Pass as: search_filter=filters
```

**Note:** Namespace isolation is achieved via `group_ids=` parameter directly on `search()`, not via `SearchFilters`. `SearchFilters` is for label/type/date filtering only.

### Returns: `list[EntityEdge]`

```python
# search() returns a flat list of EntityEdge objects
for edge in edges:
    print(f"Fact: {edge.fact}")
    print(f"Edge name: {edge.name}")
    print(f"Created: {edge.created_at}")
```

### Example: Search with Namespace Isolation

```python
edges = await graphiti.search(
    query="Supabase authentication issues",
    group_ids=["my-saas-app"],
    num_results=10,
)

for edge in edges[:5]:
    print(f"- {edge.name}: {edge.fact}")
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

`remember()` stores raw episode synchronously and triggers Graphiti extraction asynchronously via a **Queue + worker pool** (not a semaphore — workers provide back-pressure and graceful shutdown).

```python
import asyncio

# server.py: create queue + start N workers at startup
extraction_queue: asyncio.Queue = asyncio.Queue()
worker_tasks = [
    asyncio.create_task(_extraction_worker(extraction_queue, knowledge, projects))
    for _ in range(settings.extraction_workers)  # default: 4
]

async def _extraction_worker(queue, knowledge, projects):
    while True:
        item = await queue.get()
        if item is None:   # shutdown sentinel
            queue.task_done()
            return
        episode_id, content, category, project_id = item
        try:
            await projects.update_episode_status(episode_id, "processing")
            gid = await knowledge.add_episode(episode_id, content, category, project_id)
            await projects.update_episode_status(episode_id, "complete", gid)
        except Exception as e:
            logger.error(f"Extraction failed {episode_id}: {e}", exc_info=True)
            await projects.update_episode_status(episode_id, "failed")
        finally:
            queue.task_done()

# In remember() / scanner.py: enqueue item (non-blocking put)
episode = await projects.create_episode(project_id, content, category)
await extraction_queue.put((episode.episode_id, content, category, project_id))

# Graceful shutdown: send one None sentinel per worker, then wait for drain
for _ in range(settings.extraction_workers):
    await extraction_queue.put(None)
await asyncio.wait_for(extraction_queue.join(), timeout=30.0)
```

**Why Queue+workers over Semaphore+tasks:**
- Workers provide natural back-pressure (queue fills up if workers can't keep pace)
- Graceful shutdown via sentinel pattern (None item signals each worker to exit)
- Task references are stored in `worker_tasks` list — prevents garbage collection
- `queue.join()` waits for all in-flight items to complete on shutdown

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
            graphiti = Graphiti(graph_driver=driver, llm_client=llm, embedder=emb)  # graph_driver=, not driver=
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
    # Primary: graph search — group_ids is a direct param, NOT via SearchFilters
    graph_results = await graphiti.search(
        query=query,
        group_ids=[project_id],   # namespace isolation — direct param
        num_results=10,           # NOT limit=
    )

    # Fallback: search raw episodes with status=pending or status=processing
    raw_results = await projects.get_pending_episodes(project_id)

    return merge_and_deduplicate(graph_results, raw_results)
```

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ConnectionError` to FalkorDB | FalkorDB not running | `docker compose up -d`, check `docker compose ps` |
| `AuthenticationError` | Bad LLM API key | Check `LLM_API_KEY` in `.env` |
| `RateLimitError` | Too many concurrent extractions | Reduce `EXTRACTION_WORKERS` count, or switch to cheaper model |
| Index not found | `build_indices_and_constraints()` not called | Always call at startup |
| Cross-project contamination | Missing `group_ids` filter | Always pass `group_ids=[project_id]` directly to `search()` — NOT via `SearchFilters` |

---

## Version Notes

- **0.28.x:** Current stable series. API shape is stable.
- **Breaking changes:** Check graphiti-core CHANGELOG before upgrading minor versions.
- **FalkorDB driver:** Part of core package when installed with `[falkordb]` extra.

---

*See also: [FalkorDB reference](.agents/reference/falkordb.md) for database setup and Cypher queries.*
