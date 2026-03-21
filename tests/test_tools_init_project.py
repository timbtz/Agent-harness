"""Tests for the init_project MCP tool."""
import asyncio
from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.services.projects import ProjectsService
from src.tools.init_project import make_init_project


def _make_settings(tmp_path):
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    return settings


async def _setup(tmp_path):
    """Return (mcp, projects, queue)."""
    projects = await ProjectsService.create(_make_settings(tmp_path))
    queue = asyncio.Queue()
    mcp = FastMCP("test")
    make_init_project(mcp, projects, queue)
    return mcp, projects, queue


async def test_init_project_creates_new(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("init_project", {
        "name": "My Test App",
        "description": "A test application",
    })

    assert result.structured_content["status"] == "created"
    assert result.structured_content["project_id"] == "my-test-app"


async def test_init_project_returns_name_and_description(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("init_project", {
        "name": "My Test App",
        "description": "A test application for CI",
    })

    assert result.structured_content["name"] == "My Test App"
    assert result.structured_content["description"] == "A test application for CI"


async def test_init_project_existing(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    await mcp.call_tool("init_project", {
        "name": "My Test App",
        "description": "A test application",
    })
    result = await mcp.call_tool("init_project", {
        "name": "My Test App",
        "description": "Different description now",
    })

    assert result.structured_content["status"] == "existing"
    assert result.structured_content["project_id"] == "my-test-app"


async def test_init_project_existing_preserves_original_description(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    await mcp.call_tool("init_project", {
        "name": "My Test App",
        "description": "Original description",
    })
    result = await mcp.call_tool("init_project", {
        "name": "My Test App",
        "description": "New description attempt",
    })

    assert result.structured_content["description"] == "Original description"


async def test_init_project_empty_name(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("init_project", {
            "name": "",
            "description": "Some description",
        })


async def test_init_project_name_too_long(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("init_project", {
            "name": "a" * 129,
            "description": "Some description",
        })


async def test_init_project_name_exactly_128_chars(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("init_project", {
        "name": "a" * 128,
        "description": "Max length name test",
    })

    assert result.structured_content["status"] == "created"


async def test_init_project_empty_description(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    with pytest.raises(ToolError):
        await mcp.call_tool("init_project", {
            "name": "Valid Name",
            "description": "",
        })


async def test_init_project_slug_generation(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("init_project", {
        "name": "My SaaS App",
        "description": "A SaaS application",
    })

    assert result.structured_content["project_id"] == "my-saas-app"


async def test_init_project_slug_strips_special_chars(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("init_project", {
        "name": "Hello, World!",
        "description": "Test special character stripping",
    })

    assert result.structured_content["project_id"] == "hello-world"


async def test_init_project_scan_repo_queued(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("init_project", {
        "name": "Scan Test Project",
        "description": "Testing scan_repo flag",
        "scan_repo": True,
        "repo_path": str(tmp_path),
    })

    assert result.structured_content.get("scan_repo_queued") is True


async def test_init_project_scan_repo_not_queued_by_default(tmp_path):
    mcp, projects, queue = await _setup(tmp_path)

    result = await mcp.call_tool("init_project", {
        "name": "No Scan Project",
        "description": "scan_repo defaults to False",
    })

    assert "scan_repo_queued" not in result.structured_content


async def test_init_project_scan_repo_existing_project(tmp_path):
    """scan_repo=True on an already-existing project must not set scan_repo_queued."""
    mcp, projects, queue = await _setup(tmp_path)

    await mcp.call_tool("init_project", {
        "name": "Existing Project",
        "description": "Already exists",
    })

    result = await mcp.call_tool("init_project", {
        "name": "Existing Project",
        "description": "Already exists",
        "scan_repo": True,
        "repo_path": str(tmp_path),
    })

    assert result.structured_content["status"] == "existing"
    assert "scan_repo_queued" not in result.structured_content
