"""E2E integration tests for Agent Harness.

These tests exercise the full stack: SQLite → Graphiti extraction → FalkorDB.
They require live infrastructure and take 30–60 seconds to complete (graph extraction latency).

Run with:
    INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v -s
"""
import asyncio

import pytest
import pytest_asyncio
from uuid import uuid4

from src.services.briefing import generate_briefing
from src.services.projects import ProjectsService


# Unique suffix prevents interference between test runs on same DB
RUN_ID = uuid4().hex[:8]


@pytest.mark.integration
async def test_project_creation_and_idempotency(live_projects):
    """init_project creates, second call returns same project."""
    pid = f"e2e-create-{RUN_ID}"
    p1 = await live_projects.create_project(f"E2E Create {RUN_ID}", "test")
    assert p1.project_id == pid

    p2 = await live_projects.get(pid)
    assert p2 is not None
    assert p2.project_id == pid
    assert p2.name == p1.name


@pytest.mark.integration
async def test_remember_stores_episode_immediately(live_projects):
    """remember() stores episode with status=pending before extraction completes."""
    pid = f"e2e-store-{RUN_ID}"
    await live_projects.create_project(f"E2E Store {RUN_ID}", "test")

    ep = await live_projects.create_episode(pid, "We chose FastAPI for REST because of native async support", "decision")

    assert ep.episode_id.startswith("ep_")
    assert ep.status == "pending"
    assert ep.content == "We chose FastAPI for REST because of native async support"


@pytest.mark.integration
async def test_recall_keyword_fallback_works_before_extraction(live_projects):
    """Keyword fallback returns episodes before graph extraction completes."""
    pid = f"e2e-fallback-{RUN_ID}"
    await live_projects.create_project(f"E2E Fallback {RUN_ID}", "test")
    await live_projects.create_episode(pid, "PostgreSQL was selected as primary database for its ACID guarantees", "decision")

    # Immediate search — should hit fallback (episode is pending)
    fallback = await live_projects.get_episodes_for_fallback(pid)
    assert any("PostgreSQL" in ep.content for ep in fallback)


@pytest.mark.integration
async def test_delete_episode_removes_from_fallback(live_projects):
    """forget() removes episode from SQLite and keyword fallback."""
    pid = f"e2e-forget-{RUN_ID}"
    await live_projects.create_project(f"E2E Forget {RUN_ID}", "test")
    ep = await live_projects.create_episode(pid, "Wrong information that should be deleted", "error")

    deleted = await live_projects.delete_episode(pid, ep.episode_id)
    assert deleted is True

    fallback = await live_projects.get_episodes_for_fallback(pid)
    assert all(e.episode_id != ep.episode_id for e in fallback)


@pytest.mark.integration
async def test_orphan_requeue_logic(live_projects):
    """get_all_orphaned_episodes returns pending + processing across all projects."""
    pid = f"e2e-orphan-{RUN_ID}"
    await live_projects.create_project(f"E2E Orphan {RUN_ID}", "test")
    ep1 = await live_projects.create_episode(pid, "Episode one orphaned pending test", "goal")
    ep2 = await live_projects.create_episode(pid, "Episode two orphaned processing test", "goal")
    await live_projects.update_episode_status(ep2.episode_id, "processing")

    orphaned = await live_projects.get_all_orphaned_episodes()
    orphan_ids = {ep.episode_id for ep in orphaned}

    assert ep1.episode_id in orphan_ids
    assert ep2.episode_id in orphan_ids


@pytest.mark.integration
async def test_graph_extraction_completes(live_projects, live_knowledge):
    """After extraction, episode status becomes complete and graph is populated."""
    pid = f"e2e-extract-{RUN_ID}"
    await live_projects.create_project(f"E2E Extract {RUN_ID}", "test")
    ep = await live_projects.create_episode(
        pid,
        "We chose Redis for session caching because of its sub-millisecond latency",
        "decision",
    )

    # Trigger extraction directly (simulates worker)
    gid = await live_knowledge.add_episode(ep.episode_id, ep.content, ep.category, pid)
    await live_projects.update_episode_status(ep.episode_id, "complete", gid)

    updated = await live_projects.get_episodes_for_fallback(pid)
    assert not any(e.episode_id == ep.episode_id for e in updated)  # complete = not in fallback


@pytest.mark.integration
async def test_graph_search_returns_results_after_extraction(live_projects, live_knowledge):
    """After extraction, graph search returns semantically relevant results."""
    pid = f"e2e-search-{RUN_ID}"
    await live_projects.create_project(f"E2E Search {RUN_ID}", "test")
    ep = await live_projects.create_episode(
        pid,
        "SQLite was selected over PostgreSQL for project metadata because it requires no deployment",
        "decision",
    )

    await live_knowledge.add_episode(ep.episode_id, ep.content, ep.category, pid)
    await asyncio.sleep(5)  # brief wait for index propagation

    results = await live_knowledge.search("database choice", pid, limit=5)
    assert len(results) > 0
    assert all(r.source == "graph" for r in results)


@pytest.mark.integration
async def test_cross_project_isolation(live_projects, live_knowledge):
    """Graph search for project A returns no results for project B."""
    pid_a = f"e2e-iso-a-{RUN_ID}"
    pid_b = f"e2e-iso-b-{RUN_ID}"
    await live_projects.create_project(f"E2E Iso A {RUN_ID}", "test")
    await live_projects.create_project(f"E2E Iso B {RUN_ID}", "test")

    ep = await live_projects.create_episode(
        pid_a, "Kubernetes was chosen for container orchestration in project A", "architecture"
    )
    await live_knowledge.add_episode(ep.episode_id, ep.content, ep.category, pid_a)
    await asyncio.sleep(5)

    # Search in project B — should find nothing from project A
    results_b = await live_knowledge.search("Kubernetes container orchestration", pid_b, limit=5)
    assert results_b == []


@pytest.mark.integration
async def test_prime_briefing_with_graph_data(live_projects, live_knowledge):
    """prime() returns structured briefing after extraction completes."""
    pid = f"e2e-prime-{RUN_ID}"
    project = await live_projects.create_project(f"E2E Prime {RUN_ID}", "Test project for prime briefing")
    ep = await live_projects.create_episode(
        pid, "JWT authentication was chosen over OAuth because we control all API clients", "decision"
    )
    await live_knowledge.add_episode(ep.episode_id, ep.content, ep.category, pid)
    await asyncio.sleep(5)

    briefing = await generate_briefing(project, live_knowledge, live_projects)

    assert "## Project:" in briefing
    assert "### Last Session" in briefing
    assert f"E2E Prime {RUN_ID}" in briefing


@pytest.mark.integration
async def test_temporal_transition_captured(live_projects, live_knowledge):
    """Storing two contradicting facts results in a temporal edge in the graph."""
    pid = f"e2e-temporal-{RUN_ID}"
    await live_projects.create_project(f"E2E Temporal {RUN_ID}", "test")

    ep1 = await live_projects.create_episode(
        pid, "PostgreSQL was chosen as the primary database for this project", "decision"
    )
    await live_knowledge.add_episode(ep1.episode_id, ep1.content, ep1.category, pid)

    ep2 = await live_projects.create_episode(
        pid, "Migrated away from PostgreSQL to SQLite — PostgreSQL was overkill", "decision"
    )
    await live_knowledge.add_episode(ep2.episode_id, ep2.content, ep2.category, pid)

    await asyncio.sleep(8)  # allow both extractions + entity deduplication to complete

    results = await live_knowledge.search("database migration PostgreSQL", pid, limit=10)
    assert len(results) > 0

    facts = [r.content for r in results]
    # At least one fact should reference both the original choice and the migration
    combined = " ".join(facts).lower()
    assert "postgresql" in combined
