"""Tests for the recall MCP tool."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.models import SearchResult
from src.services.projects import ProjectsService
from src.tools.recall import make_recall


def _make_settings(tmp_path):
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    return settings


def _make_search_result(content: str, entity_name: str = "TestEntity") -> SearchResult:
    return SearchResult(
        content=content,
        score=1.0,
        source="graph",
        entity_name=entity_name,
        created_at=datetime.now(timezone.utc),
    )


async def _setup(tmp_path, search_results=None):
    """Return (mcp, projects, knowledge) with a pre-created 'test-project'."""
    projects = await ProjectsService.create(_make_settings(tmp_path))
    await projects.create_project("Test Project", "desc")

    knowledge = MagicMock()
    knowledge.search = AsyncMock(return_value=search_results or [])

    mcp = FastMCP("test")
    make_recall(mcp, knowledge, projects)
    return mcp, projects, knowledge


async def test_recall_query_too_short(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("recall", {
            "project_id": "test-project",
            "query": "ab",  # 2 chars
        })


async def test_recall_query_too_long(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("recall", {
            "project_id": "test-project",
            "query": "q" * 501,
        })


async def test_recall_query_exact_minimum(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)

    result = await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "JWT",
    })

    assert isinstance(result.content[0].text, str)


async def test_recall_project_not_found(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("recall", {
            "project_id": "nonexistent-project",
            "query": "some query about the project",
        })


async def test_recall_no_results(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path, search_results=[])

    result = await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "completely obscure query term xyz",
    })

    assert "No matching knowledge found" in result.content[0].text


async def test_recall_graph_results(tmp_path):
    graph_results = [_make_search_result("JWT chosen for auth", entity_name="AuthDecision")]
    mcp, projects, knowledge = await _setup(tmp_path, search_results=graph_results)

    result = await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "authentication approach",
    })

    assert "From knowledge graph:" in result.content[0].text


async def test_recall_graph_results_contain_content(tmp_path):
    graph_results = [_make_search_result("JWT chosen for auth pipeline", entity_name="AuthDecision")]
    mcp, projects, knowledge = await _setup(tmp_path, search_results=graph_results)

    result = await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "authentication approach",
    })

    assert "JWT chosen for auth pipeline" in result.content[0].text


async def test_recall_raw_fallback(tmp_path):
    """When graph returns nothing but a pending episode matches the query, show raw fallback."""
    mcp, projects, knowledge = await _setup(tmp_path, search_results=[])

    await projects.create_episode("test-project", "We chose JWT for authentication in this project", "decision")

    result = await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "JWT authentication",
    })

    assert "From recent unprocessed episodes:" in result.content[0].text


async def test_recall_raw_fallback_episode_not_matching(tmp_path):
    """Pending episode that does not share any query words should not appear in raw fallback."""
    mcp, projects, knowledge = await _setup(tmp_path, search_results=[])

    await projects.create_episode("test-project", "Redis caching configuration for production use", "architecture")

    result = await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "database migration strategy",
    })

    assert "No matching knowledge found" in result.content[0].text


async def test_recall_combined_results(tmp_path):
    """When both graph and raw results exist, both sections appear."""
    graph_results = [_make_search_result("PostgreSQL chosen as primary database", entity_name="DbDecision")]
    mcp, projects, knowledge = await _setup(tmp_path, search_results=graph_results)

    await projects.create_episode("test-project", "PostgreSQL connection pooling via pgBouncer was set up", "architecture")

    result = await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "PostgreSQL database",
    })

    text = result.content[0].text
    assert "From knowledge graph:" in text
    assert "From recent unprocessed episodes:" in text


async def test_recall_result_header_contains_query(tmp_path):
    graph_results = [_make_search_result("Some relevant content about auth systems")]
    mcp, projects, knowledge = await _setup(tmp_path, search_results=graph_results)

    result = await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "auth systems query",
    })

    assert "auth systems query" in result.content[0].text


async def test_recall_passes_project_id_to_knowledge_search(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path, search_results=[])

    await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "what database are we using here",
    })

    knowledge.search.assert_called_once()
    call_args = knowledge.search.call_args
    assert "test-project" in call_args.args or "test-project" in call_args.kwargs.values()


async def test_recall_fallback_includes_failed_episodes(tmp_path):
    """Failed episodes (from extraction errors) must appear in the keyword fallback."""
    mcp, projects, knowledge = await _setup(tmp_path, search_results=[])

    ep = await projects.create_episode("test-project", "We chose Redis for caching", "architecture")
    await projects.update_episode_status(ep.episode_id, "failed")

    result = await mcp.call_tool("recall", {
        "project_id": "test-project",
        "query": "Redis caching",
    })

    assert "From recent unprocessed episodes:" in result.content[0].text
