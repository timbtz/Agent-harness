"""Tests for MCP tool registration (src/tools/__init__.py).

Verifies all 5 tools are registered with the correct names and parameter schemas.
asyncio_mode=auto: no @pytest.mark.asyncio needed.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP

from src.tools import register_tools


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_knowledge():
    k = MagicMock()
    k.search = AsyncMock(return_value=[])
    return k


@pytest.fixture
async def registered_mcp(tmp_path, mock_knowledge):
    from src.services.projects import ProjectsService

    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    projects = await ProjectsService.create(settings)
    queue = asyncio.Queue()

    mcp = FastMCP("test-harness")
    register_tools(mcp, mock_knowledge, projects, queue)
    return mcp


# ---------------------------------------------------------------------------
# Registration coverage
# ---------------------------------------------------------------------------


async def test_all_tools_registered(registered_mcp):
    """All 5 expected MCP tools are registered."""
    tools = await registered_mcp.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {"prime", "remember", "recall", "init_project", "forget"}


async def test_tool_count(registered_mcp):
    """Exactly 5 tools are registered — no accidental extras."""
    tools = await registered_mcp.list_tools()
    assert len(tools) == 5


# ---------------------------------------------------------------------------
# prime
# ---------------------------------------------------------------------------


async def test_prime_tool_has_correct_parameter(registered_mcp):
    """prime tool declares a 'project_id' input parameter."""
    tools = await registered_mcp.list_tools()
    prime = next(t for t in tools if t.name == "prime")
    params = prime.parameters.get("properties", {})
    assert "project_id" in params


async def test_prime_tool_project_id_required(registered_mcp):
    """prime tool marks 'project_id' as required."""
    tools = await registered_mcp.list_tools()
    prime = next(t for t in tools if t.name == "prime")
    required = prime.parameters.get("required", [])
    assert "project_id" in required


# ---------------------------------------------------------------------------
# remember
# ---------------------------------------------------------------------------


async def test_remember_tool_has_required_params(registered_mcp):
    """remember tool declares project_id, content, and category parameters."""
    tools = await registered_mcp.list_tools()
    remember = next(t for t in tools if t.name == "remember")
    params = remember.parameters.get("properties", {})
    assert "project_id" in params
    assert "content" in params
    assert "category" in params


async def test_remember_all_params_required(registered_mcp):
    """All three remember parameters are marked required."""
    tools = await registered_mcp.list_tools()
    remember = next(t for t in tools if t.name == "remember")
    required = set(remember.parameters.get("required", []))
    assert {"project_id", "content", "category"}.issubset(required)


# ---------------------------------------------------------------------------
# recall
# ---------------------------------------------------------------------------


async def test_recall_tool_has_query_parameter(registered_mcp):
    """recall tool declares both 'project_id' and 'query' parameters."""
    tools = await registered_mcp.list_tools()
    recall = next(t for t in tools if t.name == "recall")
    params = recall.parameters.get("properties", {})
    assert "project_id" in params
    assert "query" in params


async def test_recall_params_required(registered_mcp):
    """Both recall parameters are marked required."""
    tools = await registered_mcp.list_tools()
    recall = next(t for t in tools if t.name == "recall")
    required = set(recall.parameters.get("required", []))
    assert {"project_id", "query"}.issubset(required)


# ---------------------------------------------------------------------------
# init_project
# ---------------------------------------------------------------------------


async def test_init_project_has_required_params(registered_mcp):
    """init_project declares name and description parameters."""
    tools = await registered_mcp.list_tools()
    init_project = next(t for t in tools if t.name == "init_project")
    params = init_project.parameters.get("properties", {})
    assert "name" in params
    assert "description" in params


async def test_init_project_has_optional_params(registered_mcp):
    """init_project declares scan_repo and repo_path as optional parameters."""
    tools = await registered_mcp.list_tools()
    init_project = next(t for t in tools if t.name == "init_project")
    params = init_project.parameters.get("properties", {})
    assert "scan_repo" in params
    assert "repo_path" in params

    required = set(init_project.parameters.get("required", []))
    assert "scan_repo" not in required
    assert "repo_path" not in required


async def test_init_project_name_and_description_required(registered_mcp):
    """name and description are required fields on init_project."""
    tools = await registered_mcp.list_tools()
    init_project = next(t for t in tools if t.name == "init_project")
    required = set(init_project.parameters.get("required", []))
    assert "name" in required
    assert "description" in required
