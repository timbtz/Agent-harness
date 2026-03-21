# Phase 4 — PyPI Publishing, Dashboard Frontend & E2E Validation

## Overview

Phase 3 delivered 122 unit/integration tests (all passing), a complete README, and a clean codebase. Phase 4 covers the remaining work to make Agent Harness production-ready and publicly usable.

---

## Deliverables

| # | Deliverable | Owner | Status |
|---|-------------|-------|--------|
| 4.1 | PyPI publishing pipeline | deployment-engineer | Pending |
| 4.2 | Dashboard frontend (Lovable / Next.js) | frontend dev | Pending |
| 4.3 | End-to-end integration tests (live services) | test-automator | Pending |
| 4.4 | Manual validation checklist | you (human) | Pending |

---

## 4.1 — PyPI Publishing

### What needs to be done

1. **Register on PyPI** — create account at pypi.org, enable 2FA, create API token
2. **Finalize `pyproject.toml` metadata**:
   ```toml
   [project]
   name = "agent-harness"
   version = "0.1.0"
   description = "Persistent knowledge graph memory for AI coding agents"
   readme = "README.md"
   license = { text = "MIT" }
   requires-python = ">=3.11"
   keywords = ["mcp", "claude", "knowledge-graph", "ai-agent", "memory"]
   classifiers = [
     "Development Status :: 4 - Beta",
     "Intended Audience :: Developers",
     "License :: OSI Approved :: MIT License",
     "Programming Language :: Python :: 3.11",
   ]
   [project.urls]
   Homepage = "https://github.com/your-org/agent-harness"
   Repository = "https://github.com/your-org/agent-harness"
   ```
3. **Create GitHub Actions CI/CD pipeline** (`.github/workflows/publish.yml`):
   - Trigger: push to `main` + version tag (`v*`)
   - Jobs: lint → test → build → publish to PyPI
   - Use `uv build` + `uv publish` with PyPI trusted publisher (OIDC, no stored secrets)
4. **Test `uvx agent-harness` locally** before publishing:
   ```bash
   uv build
   uvx --from ./dist/agent_harness-0.1.0-py3-none-any.whl agent-harness
   ```
5. **Versioning strategy**: CalVer (`2026.03.0`) or SemVer (`0.1.0`) — decide before first publish

### Files to create/modify
- `.github/workflows/publish.yml`
- `.github/workflows/ci.yml` (separate lint+test on every PR)
- `pyproject.toml` (metadata additions)
- `CHANGELOG.md` (start one)

---

## 4.2 — Dashboard Frontend

### Architecture decision needed

Choose one of:

| Option | Pros | Cons |
|--------|------|------|
| **Lovable** (AI-generated) | Fast to bootstrap, no frontend expertise needed | Less control, external dependency |
| **Next.js + shadcn/ui** | Full control, TypeScript, production-ready | More setup time |
| **Simple HTML + HTMX** | Zero build step, served by FastAPI directly | Limited interactivity |

**Recommendation:** Start with Lovable for a working prototype, migrate to Next.js when the API stabilizes.

### Dashboard pages to implement

1. **Overview** — project list cards, total insights count, FalkorDB connection status
2. **Project detail** — name, description, episode count, last updated
3. **Knowledge graph** — D3.js / Cytoscape.js visualization of nodes + edges (from `/api/projects/{id}/graph`)
4. **Insights feed** — paginated table with category filter, search box (from `/api/projects/{id}/insights`)
5. **Timeline** — chronological episode list (from `/api/projects/{id}/timeline`)

### API additions needed for dashboard

The current REST API is sufficient for Phase 4. Possible additions in Phase 5:
- `DELETE /api/projects/{id}` — project deletion
- `PATCH /api/projects/{id}/episodes/{ep_id}` — manual episode edit
- `POST /api/projects/{id}/search` — expose `recall()` over HTTP

### CORS configuration

`ALLOWED_ORIGINS` env var already exists. Set to `http://localhost:3000` (Lovable dev) or frontend URL.

---

## 4.3 — End-to-End Integration Tests

These tests **require live services** (FalkorDB running + real OpenAI API key). They cannot run in CI without Docker Compose service spin-up. Mark with `@pytest.mark.integration` and skip by default.

### Test scenarios

```python
# tests/integration/test_e2e_remember_recall.py
# Requires: docker compose up -d + OPENAI_API_KEY set

@pytest.mark.integration
async def test_remember_then_recall_finds_content():
    """Store an episode, wait for extraction, recall it."""
    # 1. init_project
    # 2. remember("chose Redis because session storage was slow", "decision")
    # 3. asyncio.sleep(15)  # wait for Graphiti extraction
    # 4. recall("why did we choose Redis?")
    # 5. assert "Redis" in result

@pytest.mark.integration
async def test_prime_after_multiple_episodes():
    """prime() returns structured briefing with real data."""
    # 1. init_project
    # 2. remember(3 decisions + 1 error)
    # 3. asyncio.sleep(15)
    # 4. prime()
    # 5. assert "## Project:" in result
    # 5. assert "### Key Decisions" in result

@pytest.mark.integration
async def test_graph_data_populated_after_extraction():
    """GET /api/projects/{id}/graph returns nodes after extraction completes."""
    # 1. init_project
    # 2. remember("FastAPI chosen for REST layer because of async support", "architecture")
    # 3. asyncio.sleep(20)
    # 4. GET /api/projects/{id}/graph
    # 5. assert len(data["nodes"]) > 0
```

### Running integration tests

```bash
# Start FalkorDB
docker compose up -d

# Set API key
export OPENAI_API_KEY=sk-...
export LLM_API_KEY=sk-...

# Run only integration tests
uv run pytest tests/integration/ -v -m integration

# Run all including integration
uv run pytest tests/ -v
```

### CI/CD integration

Add optional job to GitHub Actions triggered manually or on `main` pushes:

```yaml
integration-tests:
  runs-on: ubuntu-latest
  if: github.event_name == 'workflow_dispatch'
  services:
    falkordb:
      image: falkordb/falkordb:latest
      ports: ["6379:6379"]
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    LLM_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

---

## 4.4 — Manual Validation Checklist

These items **cannot be automated** and require human verification:

### First-time setup

- [ ] `docker compose up -d` starts FalkorDB and shows `healthy` in `docker compose ps`
- [ ] `cp .env.example .env` + fill in real API keys
- [ ] `uv run python -m src.server` starts without errors; logs show `FalkorDB connected` and `Uvicorn running on http://127.0.0.1:8080`
- [ ] `curl http://localhost:8080/api/health` returns `{"status":"ok","falkordb_connected":true,"projects_count":0}`

### MCP integration with Claude Code

- [ ] Add `agent-harness` server to `~/.claude/mcp.json` using `uvx agent-harness`
- [ ] Claude Code starts and lists the 4 MCP tools: `prime`, `remember`, `recall`, `init_project`
- [ ] Call `init_project("Test Project", "Testing agent harness")` — returns `{"status":"created","project_id":"test-project",...}`
- [ ] Call `remember("test-project", "chose SQLite for simplicity over Postgres", "decision")` — returns `{"status":"stored",...}`
- [ ] Wait ~15 seconds for Graphiti extraction
- [ ] Call `recall("test-project", "why did we choose SQLite?")` — returns text mentioning "SQLite"
- [ ] Call `prime("test-project")` — returns formatted briefing with "## Project:" header

### Graphiti extraction pipeline

- [ ] After `remember()`, verify episode status goes: `pending` → `processing` → `complete`
  - Check via `GET /api/projects/test-project/insights`
- [ ] Verify FalkorDB graph is populated: `GET /api/projects/test-project/graph` returns nodes after extraction
- [ ] Test with Anthropic provider: set `LLM_PROVIDER=anthropic`, `LLM_API_KEY=sk-ant-...` — verify extraction still works
- [ ] Test extraction failure path: use invalid API key, verify episode status becomes `failed` and `recall()` still returns raw episode text

### Edge cases

- [ ] Call `init_project` twice with same name — second call returns `{"status":"existing",...}` with no data change
- [ ] Call `remember` with 10-char content (boundary) — succeeds
- [ ] Call `remember` with 9-char content — returns error
- [ ] Call `prime("nonexistent-project")` — returns error JSON `{"error":"project_not_found",...}`
- [ ] Restart the server mid-extraction — verify pending episodes are NOT re-queued (they stay as `pending`; known limitation, document in README)

### Performance

- [ ] `recall()` response time < 500ms with ~20 stored episodes (P95)
- [ ] `remember()` response time < 50ms (sync store only, extraction is async)
- [ ] `prime()` response time < 300ms

### Security

- [ ] Verify FalkorDB is NOT accessible from another machine on the network (only `127.0.0.1:6379`)
- [ ] Verify dashboard API is NOT accessible from another machine (only `127.0.0.1:8080`)
- [ ] Verify `.env` is NOT committed to git (check `git log --all --full-history -- .env`)
- [ ] Verify `uvx agent-harness` works without a local clone (install from PyPI)

---

## 4.5 — Known Limitations to Document

These are architectural constraints to document explicitly in the README and/or CLAUDE.md:

1. **Pending episodes lost on restart** — episodes with `status=pending` at shutdown are not re-queued. They remain as `pending` in SQLite but are never processed. Workaround: check `/api/projects/{id}/insights?category=all` and manually re-submit if needed.

2. **OpenAI embeddings always required** — even when using Anthropic as the LLM provider, `OPENAI_API_KEY` is required for `text-embedding-3-small` embeddings. Graphiti does not support Anthropic embeddings.

3. **FalkorDB is not persistent by default** — the Docker Compose setup uses a named volume (`falkordb-data`). If the volume is deleted, all graph data is lost. SQLite (episodes, projects) survives because it's on the host filesystem.

4. **No multi-tenancy** — all projects share one FalkorDB instance. Project isolation is logical (via `group_id`), not physical.

5. **Extraction latency** — Graphiti entity extraction makes 4-10 LLM API calls per episode. With default `gpt-4.1-mini`, this takes 5-15 seconds. `recall()` falls back to raw episode text during this window.

6. **`scan_repo=True` only runs once** — repo scanning only triggers for new projects. To re-scan after structural changes, delete the project and re-create it.

---

## Phase 5 Preview (Future)

After Phase 4 ships, consider:

| Feature | Complexity | Value |
|---------|-----------|-------|
| Cross-project search | Medium | High — find patterns across all projects |
| Episode deletion / editing | Low | High — fix mistakes |
| Ollama local LLM support | Medium | High — zero-cost extraction |
| `export` tool (Markdown/JSON dump) | Low | Medium — portability |
| VS Code extension | High | High — no CLI needed |
| Multi-user / auth | High | Medium — team use cases |
| Periodic re-indexing | Medium | Medium — improve graph quality over time |

---

*Phase 4 written: 2026-03-21*
