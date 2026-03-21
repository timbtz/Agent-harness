"""Tests for the remember MCP tool."""
import asyncio
from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.services.projects import ProjectsService
from src.tools.remember import make_remember


def _make_settings(tmp_path):
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    return settings


async def _setup(tmp_path):
    """Return (mcp, projects, queue) with a pre-created 'test-project'."""
    projects = await ProjectsService.create(_make_settings(tmp_path))
    await projects.create_project("Test Project", "desc")
    knowledge = MagicMock()
    queue = asyncio.Queue()
    mcp = FastMCP("test")
    make_remember(mcp, knowledge, projects, queue)
    return mcp, projects, queue


async def test_remember_success(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("remember", {
        "project_id": "test-project",
        "content": "We decided to use JWT for auth",
        "category": "decision",
    })

    assert result.structured_content["status"] == "stored"
    assert result.structured_content["category"] == "decision"
    assert "episode_id" in result.structured_content


async def test_remember_episode_id_format(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("remember", {
        "project_id": "test-project",
        "content": "We decided to use PostgreSQL for the primary database",
        "category": "architecture",
    })

    assert result.structured_content["episode_id"].startswith("ep_")


async def test_remember_processing_field_present(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("remember", {
        "project_id": "test-project",
        "content": "Redis caching layer was chosen over Memcached",
        "category": "decision",
    })

    assert "processing" in result.structured_content


async def test_remember_content_too_short(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("remember", {
            "project_id": "test-project",
            "content": "too short",  # 9 chars
            "category": "decision",
        })


async def test_remember_content_too_long(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("remember", {
            "project_id": "test-project",
            "content": "x" * 2001,
            "category": "decision",
        })


async def test_remember_content_exact_minimum(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("remember", {
        "project_id": "test-project",
        "content": "1234567890",  # exactly 10 chars
        "category": "insight",
    })

    assert result.structured_content["status"] == "stored"


async def test_remember_content_exact_maximum(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("remember", {
        "project_id": "test-project",
        "content": "a" * 2000,
        "category": "insight",
    })

    assert result.structured_content["status"] == "stored"


async def test_remember_project_not_found(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("remember", {
            "project_id": "nonexistent-project",
            "content": "This project does not exist anywhere in the system",
            "category": "decision",
        })


async def test_remember_enqueues_to_extraction_queue(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    await mcp.call_tool("remember", {
        "project_id": "test-project",
        "content": "We decided to use Redis for session storage in production",
        "category": "decision",
    })

    assert queue.qsize() == 1


async def test_remember_queue_item_contains_correct_fields(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)
    content = "We decided to use Celery for background task processing"

    await mcp.call_tool("remember", {
        "project_id": "test-project",
        "content": content,
        "category": "architecture",
    })

    item = queue.get_nowait()
    episode_id, queued_content, queued_category, queued_project_id = item
    assert episode_id.startswith("ep_")
    assert queued_content == content
    assert queued_category == "architecture"
    assert queued_project_id == "test-project"


async def test_remember_all_categories(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)
    categories = ["decision", "insight", "error", "goal", "architecture"]

    for category in categories:
        result = await mcp.call_tool("remember", {
            "project_id": "test-project",
            "content": f"Some content for category {category} test here",
            "category": category,
        })
        assert result.structured_content["status"] == "stored"
        assert result.structured_content["category"] == category
