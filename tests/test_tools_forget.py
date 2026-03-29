"""Tests for the forget MCP tool."""
import json

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from unittest.mock import MagicMock

from src.services.projects import ProjectsService
from src.tools.forget import make_forget


def _make_settings(tmp_path):
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    return settings


async def _setup(tmp_path):
    projects = await ProjectsService.create(_make_settings(tmp_path))
    await projects.create_project("Test Project", "desc")
    mcp = FastMCP("test")
    make_forget(mcp, projects)
    return mcp, projects


async def test_forget_deletes_existing_episode(tmp_path):
    mcp, projects = await _setup(tmp_path)
    ep = await projects.create_episode("test-project", "Content to be deleted here", "decision")

    result = await mcp.call_tool("forget", {
        "project_id": "test-project",
        "episode_id": ep.episode_id,
    })

    assert result.content[0].text
    data = json.loads(result.content[0].text)
    assert data["deleted"] is True
    assert data["episode_id"] == ep.episode_id


async def test_forget_project_not_found(tmp_path):
    mcp, projects = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("forget", {
            "project_id": "nonexistent-project",
            "episode_id": "ep_abc123",
        })


async def test_forget_episode_not_found(tmp_path):
    mcp, projects = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("forget", {
            "project_id": "test-project",
            "episode_id": "ep_doesnotexist",
        })


async def test_forget_episode_no_longer_in_fallback(tmp_path):
    """After forget(), episode does not appear in get_episodes_for_fallback."""
    mcp, projects = await _setup(tmp_path)
    ep = await projects.create_episode("test-project", "Redis was chosen for caching layer", "architecture")

    await mcp.call_tool("forget", {
        "project_id": "test-project",
        "episode_id": ep.episode_id,
    })

    remaining = await projects.get_episodes_for_fallback("test-project")
    assert all(e.episode_id != ep.episode_id for e in remaining)


async def test_forget_response_contains_note(tmp_path):
    """forget() response includes a note about graph entity persistence."""
    mcp, projects = await _setup(tmp_path)
    ep = await projects.create_episode("test-project", "Some content that will be deleted now", "insight")

    result = await mcp.call_tool("forget", {
        "project_id": "test-project",
        "episode_id": ep.episode_id,
    })

    data = json.loads(result.content[0].text)
    assert "note" in data
    assert "SQLite" in data["note"]
