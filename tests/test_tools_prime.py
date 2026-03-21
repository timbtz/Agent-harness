"""Tests for the prime MCP tool."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.services.projects import ProjectsService
from src.tools.prime import make_prime


def _make_settings(tmp_path):
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    return settings


def _make_knowledge(search_results=None):
    knowledge = MagicMock()
    knowledge.search = AsyncMock(return_value=search_results or [])
    return knowledge


async def _setup(tmp_path, search_results=None):
    """Return (mcp, projects, knowledge) with a pre-created 'my-test-project'."""
    projects = await ProjectsService.create(_make_settings(tmp_path))
    await projects.create_project("My Test Project", "A project for testing prime")

    knowledge = _make_knowledge(search_results)
    mcp = FastMCP("test")
    make_prime(mcp, knowledge, projects)
    return mcp, projects, knowledge


async def test_prime_project_not_found(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("prime", {"project_id": "nonexistent-project"})


async def test_prime_empty_project(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)

    result = await mcp.call_tool("prime", {"project_id": "my-test-project"})

    assert "No knowledge stored yet" in result.content[0].text


async def test_prime_with_episodes(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)
    await projects.create_episode("my-test-project", "We decided to use FastAPI for the REST layer", "decision")

    result = await mcp.call_tool("prime", {"project_id": "my-test-project"})

    text = result.content[0].text
    assert "## Project:" in text
    assert "### Last Session" in text


async def test_prime_includes_project_name(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)
    await projects.create_episode("my-test-project", "JWT tokens will be used for API authentication here", "decision")

    result = await mcp.call_tool("prime", {"project_id": "my-test-project"})

    assert "My Test Project" in result.content[0].text


async def test_prime_empty_project_contains_project_name(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)

    result = await mcp.call_tool("prime", {"project_id": "my-test-project"})

    assert "My Test Project" in result.content[0].text


async def test_prime_with_episodes_shows_episode_content(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)
    await projects.create_episode(
        "my-test-project",
        "Decided to use Pydantic v2 for all data validation across the codebase",
        "decision",
    )

    result = await mcp.call_tool("prime", {"project_id": "my-test-project"})

    assert "Pydantic v2" in result.content[0].text


async def test_prime_returns_string(tmp_path):
    mcp, projects, knowledge = await _setup(tmp_path)

    result = await mcp.call_tool("prime", {"project_id": "my-test-project"})

    assert isinstance(result.content[0].text, str)
    assert len(result.content[0].text) > 0
