# FalkorDB Reference — Agent Harness

> **Image:** `falkordb/falkordb:latest` (pin to specific version for production)
> **Python client:** `pip install "falkordb>=1.0.0,<2.0.0"`
> **License:** SSPL (free for self-hosting; restriction only on SaaS redistribution)
> **Wire protocol:** Redis-compatible (RESP)
> **Port:** 6379 (Redis default)

---

## Overview

FalkorDB is a graph database with native vector search built as a Redis module. Agent Harness uses it as the backing store for Graphiti's knowledge graph. Key features:

- **Graph queries:** Cypher query language (subset of openCypher)
- **Native vector search:** HNSW index with cosine similarity
- **BM25 full-text search:** Built-in full-text indexing
- **Namespace isolation:** Separate named graphs via `db.select_graph("name")`
- **Redis-compatible:** Uses RESP wire protocol, works with Redis clients

**SSPL Note:** SSPL only restricts using FalkorDB to build a managed database service for others. Self-hosting for your own application is completely unrestricted. Agent Harness is always self-hosted.

---

## Docker Setup

### docker-compose.yml

```yaml
services:
  falkordb:
    image: falkordb/falkordb:latest
    container_name: agent-harness-falkordb
    restart: unless-stopped
    ports:
      - "127.0.0.1:6379:6379"  # localhost only — not externally exposed
    volumes:
      - falkordb_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  falkordb_data:
    driver: local
```

**CRITICAL: Bind to `127.0.0.1:6379` only — never `0.0.0.0:6379`.**

On Linux Docker with the default bridge network, the host cannot reach the container at `localhost:6379` without a `ports:` mapping. The `127.0.0.1:6379:6379` binding exposes the port only on the loopback interface — it is not accessible from outside the machine. Docker Desktop on macOS/Windows has automatic localhost forwarding, but the explicit binding works on both platforms.

### Start / Stop

```bash
# Start FalkorDB in background
docker compose up -d

# Verify healthy
docker compose ps
# Expected: falkordb   Up (healthy)

# Stop
docker compose down

# Stop and delete data (destructive!)
docker compose down -v
```

### Verify Connection

```bash
# Test FalkorDB is responding
docker exec agent-harness-falkordb redis-cli ping
# Expected: PONG

# Check from host (once MCP server is running)
curl http://localhost:8080/api/health
# Expected: {"status":"ok","falkordb_connected":true}
```

---

## Python Client

Graphiti manages FalkorDB interaction internally. Direct FalkorDB client usage is rarely needed in Agent Harness code, but here's the reference:

### Connection

```python
from falkordb import FalkorDB

# Connect to FalkorDB (same host/port as FalkorDriver for Graphiti)
db = FalkorDB(host="localhost", port=6379)

# Select a named graph (creates if doesn't exist)
graph = db.select_graph("my-project-slug")
```

### Basic Queries

```python
# Execute a Cypher query
result = graph.query("MATCH (n) RETURN n LIMIT 10")
for record in result.result_set:
    print(record)

# Parameterized query (always use params, never f-strings for user input)
result = graph.query(
    "MATCH (n {name: $name}) RETURN n",
    params={"name": "Supabase Auth"}
)
```

### Namespace Isolation

Each Agent Harness project gets its own named graph in FalkorDB:

```python
# Project "my-saas-app" → graph named "my-saas-app"
graph = db.select_graph("my-saas-app")

# Project "other-project" → completely separate graph
other_graph = db.select_graph("other-project")

# Listing all graphs
graphs = db.list_graphs()
```

Graphiti handles this automatically via the `group_id` parameter — you don't call `select_graph()` directly.

---

## Vector Search

### Creating a Vector Index

FalkorDB uses HNSW (Hierarchical Navigable Small World) for approximate nearest neighbor search.

```cypher
-- Create vector index on node embedding property
CREATE VECTOR INDEX FOR (n:Entity)
ON (n.embedding)
OPTIONS {
  dimension: 1536,                  -- Must match embedding model output dim
  similarityFunction: 'cosine'      -- 'cosine' or 'euclidean'
}
```

```python
# Python equivalent
graph.query("""
    CREATE VECTOR INDEX FOR (n:Entity)
    ON (n.embedding)
    OPTIONS {dimension: 1536, similarityFunction: 'cosine'}
""")
```

Graphiti calls `build_indices_and_constraints()` which creates all required indices automatically. You don't create vector indices manually.

### Vector Search Query

```cypher
-- Find top 5 nodes by cosine similarity to a query embedding
CALL db.idx.vector.queryNodes('Entity', 'embedding', 5, vecf32([0.1, 0.2, ...]))
YIELD node, score
RETURN node.name, node.summary, score
ORDER BY score DESC
```

---

## BM25 Full-Text Search

### Creating a Full-Text Index

```cypher
-- Create BM25 full-text index on node properties
CREATE FULLTEXT INDEX FOR (n:Episode) ON (n.content)
```

### BM25 Search Query

```cypher
-- Search episodes with BM25 scoring
CALL db.idx.fulltext.queryNodes('Episode', 'JWT authentication')
YIELD node, score
RETURN node.name, node.content, score
ORDER BY score DESC
LIMIT 10
```

---

## Cypher Query Reference

### Node Patterns

```cypher
-- Match any node
MATCH (n) RETURN n

-- Match by label
MATCH (n:Entity) RETURN n

-- Match by property
MATCH (n:Entity {name: "Supabase"}) RETURN n

-- Match by group_id (project namespace)
MATCH (n:Entity) WHERE n.group_id = 'my-saas-app' RETURN n
```

### Relationship Patterns

```cypher
-- Match relationship type
MATCH (a)-[:RELATES_TO]->(b) RETURN a, b

-- Match any relationship
MATCH (a)-[r]->(b) RETURN a, type(r), b

-- Match with constraints
MATCH (a:Entity {group_id: 'project-a'})-[r]->(b:Entity)
WHERE r.invalid_at IS NULL
RETURN a.name, type(r), b.name
```

### Temporal Queries

```cypher
-- Get currently valid facts (not superseded)
MATCH (a)-[r:FACT]->(b)
WHERE r.invalid_at IS NULL AND r.group_id = 'my-saas-app'
RETURN a.name, r.fact, b.name

-- Get all facts including historical
MATCH (a)-[r:FACT]->(b)
WHERE r.group_id = 'my-saas-app'
RETURN a.name, r.fact, r.valid_at, r.invalid_at, b.name
ORDER BY r.valid_at DESC
```

### Graph Statistics

```cypher
-- Count nodes by label
MATCH (n) RETURN labels(n) AS label, count(n) AS count

-- Count edges by type
MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count

-- Get recent episodes
MATCH (e:Episode)
WHERE e.group_id = 'my-saas-app'
RETURN e.name, e.content, e.created_at
ORDER BY e.created_at DESC
LIMIT 10
```

---

## Data Persistence

FalkorDB stores data in Redis's RDB/AOF format. The Docker volume `falkordb_data` persists across container restarts.

```yaml
# In docker-compose.yml (already included in base config)
volumes:
  falkordb_data:
    driver: local
```

**Backup:**
```bash
# Trigger RDB snapshot
docker exec agent-harness-falkordb redis-cli BGSAVE

# Copy snapshot file
docker cp agent-harness-falkordb:/data/dump.rdb ./backup/
```

**Restore:**
```bash
# Stop container
docker compose down

# Replace dump.rdb in volume (varies by host OS)
# Then restart
docker compose up -d
```

---

## Connection Configuration

```python
# In src/config.py (Pydantic Settings)
class Settings(BaseSettings):
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379

    model_config = SettingsConfigDict(env_prefix="FALKORDB_")

# In .env (optional overrides)
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
```

```python
# In src/services/knowledge.py
from graphiti_core.driver.falkordb_driver import FalkorDriver

driver = FalkorDriver(
    host=settings.falkordb_host,
    port=settings.falkordb_port,
    database=project_id,  # Named database for per-project isolation (NOT integer 0)
)
```

---

## Connection Health Check

```python
async def check_falkordb_health() -> bool:
    """Returns True if FalkorDB is reachable and responding."""
    try:
        from falkordb import FalkorDB
        db = FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port)
        # Simple ping - select a graph and run a trivial query
        g = db.select_graph("_health_check")
        g.query("RETURN 1")
        return True
    except Exception:
        return False
```

---

## Using the Sync Client in Async Code

The `falkordb` Python client is **fully synchronous**. Calling it directly in an `async def` blocks the asyncio event loop for the full query duration.

**Rule:** Use `asyncio.to_thread()` for any non-trivial FalkorDB query in async code.

```python
import asyncio
from falkordb import FalkorDB

async def get_graph_data(self, project_id: str) -> dict:
    def _query() -> dict:
        db = FalkorDB(host=self._settings.falkordb_host, port=self._settings.falkordb_port)
        g = db.select_graph(project_id)
        result = g.query(
            "MATCH (n:Entity) WHERE n.group_id = $gid RETURN n.uuid, n.name, n.summary",
            params={"gid": project_id},
        )
        return {"nodes": [{"id": r[0], "name": r[1], "summary": r[2]} for r in result.result_set if r[0]]}

    try:
        return await asyncio.to_thread(_query)  # Runs sync code in thread pool
    except Exception as e:
        logger.warning(f"Graph query failed for {project_id}: {e}")
        return {"nodes": [], "edges": []}
```

**Exception:** `check_connection()` (health check) calls the client directly in `async def` — acceptable for a single brief `RETURN 1` query, not for multi-query data fetches.

### Local import pattern — mock target

`KnowledgeService` imports `FalkorDB` **inside function bodies** (not at module level):

```python
# Inside check_connection() and _query() helpers:
from falkordb import FalkorDB   # local import inside the function
db = FalkorDB(host=..., port=...)
```

This means when mocking in tests, you must patch at the **source module**, not the importing module:

```python
# CORRECT — patches the class where it is defined
with patch("falkordb.FalkorDB", return_value=mock_db):
    ...

# WRONG — src.services.knowledge never holds a module-level reference
with patch("src.services.knowledge.FalkorDB", ...):  # AttributeError
    ...
```

---

## Troubleshooting

### FalkorDB Not Responding

```bash
# 1. Check container is running
docker compose ps

# 2. Check container logs
docker compose logs falkordb

# 3. Test from inside container
docker exec agent-harness-falkordb redis-cli ping

# 4. Check if port is in use on host
lsof -i :6379
```

### Data Corruption / Recovery

```bash
# If FalkorDB won't start due to corrupted data
# WARNING: This deletes all knowledge graphs!
docker compose down -v
docker compose up -d
```

### Performance Tuning

FalkorDB defaults are appropriate for Agent Harness usage (single-user, <10K nodes). No tuning needed at MVP scale.

For larger deployments:
```bash
# Set max memory in docker-compose.yml
command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

---

## SSPL License — What It Means for Developers

**SSPL restricts:** Using FalkorDB to build a managed database *service* that you sell to others.

**SSPL does NOT restrict:**
- Using FalkorDB in your own self-hosted application
- Running it locally for development
- Open-source projects that self-host it
- Any scenario where you're not reselling FalkorDB as a database service

Agent Harness is always self-hosted by the developer — SSPL has zero impact on usage.

**Alternative backends** (if SSPL is a concern): The Graphiti library supports other backends. Neo4j (Apache 2.0) and Apache AGE (PostgreSQL extension, Apache 2.0) are potential alternatives, but require different `graph_driver` configuration.

---

*See also: [Graphiti reference](.agents/reference/graphiti.md) for the graph library that wraps FalkorDB.*
