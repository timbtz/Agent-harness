"""Tests for KnowledgeService using mocked Graphiti and FalkorDB.

No live FalkorDB required — all external I/O is mocked.
asyncio_mode=auto in pyproject.toml: no @pytest.mark.asyncio needed.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import SearchResult
from src.services.knowledge import KnowledgeService


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    s = MagicMock()
    s.falkordb_host = "localhost"
    s.falkordb_port = 6379
    s.llm_provider = "openai"
    s.llm_api_key = "sk-test"
    s.openai_api_key = "sk-test"
    s.llm_model = "gpt-4.1-mini"
    return s


@pytest.fixture
def svc(settings):
    """KnowledgeService constructed directly (bypasses _verify_connection)."""
    return KnowledgeService(settings, MagicMock(), MagicMock())


# ---------------------------------------------------------------------------
# check_connection
# ---------------------------------------------------------------------------


async def test_check_connection_success(svc):
    """Returns True when FalkorDB query succeeds."""
    mock_graph = MagicMock()
    mock_graph.query.return_value = MagicMock()
    mock_db = MagicMock()
    mock_db.select_graph.return_value = mock_graph

    # FalkorDB is imported inside the function body, so patch at source module
    with patch("falkordb.FalkorDB", return_value=mock_db):
        result = await svc.check_connection()

    assert result is True


async def test_check_connection_failure(svc):
    """Returns False when FalkorDB raises an exception."""
    with patch("falkordb.FalkorDB", side_effect=ConnectionError("refused")):
        result = await svc.check_connection()

    assert result is False


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


async def test_search_returns_empty_on_error(svc):
    """Returns empty list when get_graphiti raises."""
    with patch.object(svc, "get_graphiti", side_effect=RuntimeError("boom")):
        results = await svc.search("some query", "my-project", limit=5)

    assert results == []


async def test_search_converts_edges_to_results(svc):
    """Maps EntityEdge-like objects to SearchResult instances."""
    edge1 = MagicMock()
    edge1.fact = "Use asyncio.to_thread for sync FalkorDB calls"
    edge1.name = "FalkorDB Rule"
    edge1.created_at = None

    edge2 = MagicMock()
    edge2.fact = "Prefer deterministic slugs for project IDs"
    edge2.name = "SlugRule"
    edge2.created_at = None

    mock_graphiti = AsyncMock()
    mock_graphiti.search = AsyncMock(return_value=[edge1, edge2])

    with patch.object(svc, "get_graphiti", return_value=mock_graphiti):
        results = await svc.search("falkordb", "my-project", limit=10)

    assert len(results) == 2
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].content == "Use asyncio.to_thread for sync FalkorDB calls"
    assert results[0].entity_name == "FalkorDB Rule"
    assert results[0].source == "graph"
    assert results[1].content == "Prefer deterministic slugs for project IDs"


async def test_search_respects_limit(svc):
    """Does not return more results than limit."""
    # name is a special MagicMock constructor arg — set it as attribute instead
    edges = []
    for i in range(10):
        e = MagicMock()
        e.fact = f"fact-{i}"
        e.name = f"name-{i}"
        e.created_at = None
        edges.append(e)

    mock_graphiti = AsyncMock()
    mock_graphiti.search = AsyncMock(return_value=edges)

    with patch.object(svc, "get_graphiti", return_value=mock_graphiti):
        results = await svc.search("query", "proj", limit=3)

    assert len(results) <= 3


# ---------------------------------------------------------------------------
# add_episode
# ---------------------------------------------------------------------------


async def test_add_episode_calls_graphiti(svc):
    """add_episode returns the uuid string from the Graphiti result."""
    mock_graphiti = AsyncMock()
    mock_result = MagicMock()
    mock_result.episode.uuid = "test-uuid-123"
    mock_graphiti.add_episode = AsyncMock(return_value=mock_result)

    with patch.object(svc, "get_graphiti", return_value=mock_graphiti):
        result = await svc.add_episode("ep_001", "a decision was made", "decision", "my-project")

    assert result == "test-uuid-123"
    mock_graphiti.add_episode.assert_awaited_once()


async def test_add_episode_passes_category_in_body(svc):
    """Episode body is prefixed with the category label in uppercase."""
    captured_kwargs: dict = {}

    async def fake_add_episode(**kwargs):
        captured_kwargs.update(kwargs)
        result = MagicMock()
        result.episode.uuid = "uuid-abc"
        return result

    mock_graphiti = AsyncMock()
    mock_graphiti.add_episode = fake_add_episode

    with patch.object(svc, "get_graphiti", return_value=mock_graphiti):
        await svc.add_episode("ep_002", "API rate limit is 100/min", "insight", "proj-x")

    assert "[INSIGHT]" in captured_kwargs.get("episode_body", "")
    assert "API rate limit is 100/min" in captured_kwargs.get("episode_body", "")


# ---------------------------------------------------------------------------
# get_graph_data
# ---------------------------------------------------------------------------


async def test_get_graph_data_returns_empty_on_error(svc):
    """Returns empty nodes/edges dict when FalkorDB query raises."""
    with patch("falkordb.FalkorDB", side_effect=RuntimeError("connection refused")):
        data = await svc.get_graph_data("my-project")

    assert data == {"nodes": [], "edges": []}


async def test_get_graph_data_structure(svc):
    """Returns dict with 'nodes' and 'edges' keys on success."""
    mock_nodes_result = MagicMock()
    mock_nodes_result.result_set = [
        ["uuid-1", "EntityA", "Summary A"],
        ["uuid-2", "EntityB", "Summary B"],
    ]

    mock_edges_result = MagicMock()
    mock_edges_result.result_set = [
        ["uuid-1", "uuid-2", "A relates to B", "RELATES_TO"],
    ]

    mock_graph = MagicMock()
    mock_graph.query.side_effect = [mock_nodes_result, mock_edges_result]

    mock_db = MagicMock()
    mock_db.select_graph.return_value = mock_graph

    with patch("falkordb.FalkorDB", return_value=mock_db):
        data = await svc.get_graph_data("my-project")

    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["nodes"][0]["id"] == "uuid-1"
    assert data["nodes"][0]["name"] == "EntityA"
    assert data["edges"][0]["fact"] == "A relates to B"
