"""Tests for FastAPI REST routes (src/api/routes.py).

Uses httpx.AsyncClient with ASGITransport — no live server required.
asyncio_mode=auto: no @pytest.mark.asyncio needed.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from src.api.routes import create_router
from src.models import Project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_knowledge():
    k = MagicMock()
    k.check_connection = AsyncMock(return_value=True)
    k.get_graph_data = AsyncMock(return_value={"nodes": [], "edges": []})
    return k


@pytest.fixture
def mock_projects():
    p = MagicMock()
    p.count = AsyncMock(return_value=0)
    p.list_all = AsyncMock(return_value=[])
    p.get = AsyncMock(return_value=None)
    p.get_insights = AsyncMock(return_value={"items": [], "total": 0, "page": 1, "limit": 20})
    p.get_timeline = AsyncMock(return_value=[])
    return p


@pytest.fixture
def test_app(mock_knowledge, mock_projects):
    app = FastAPI()
    router = create_router(mock_knowledge, mock_projects)
    app.include_router(router, prefix="/api")
    return app


def _make_project(project_id: str = "test-proj") -> Project:
    return Project(
        project_id=project_id,
        name="Test Project",
        description="A description",
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------


async def test_health_ok(test_app):
    """GET /api/health returns 200 with status=ok when FalkorDB is reachable."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["falkordb_connected"] is True
    assert data["projects_count"] == 0


async def test_health_degraded(test_app, mock_knowledge):
    """GET /api/health returns status=degraded when FalkorDB is unreachable."""
    mock_knowledge.check_connection = AsyncMock(return_value=False)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["falkordb_connected"] is False


# ---------------------------------------------------------------------------
# /api/projects
# ---------------------------------------------------------------------------


async def test_list_projects_empty(test_app):
    """GET /api/projects returns 200 with an empty list when no projects exist."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects")

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_projects_returns_projects(test_app, mock_projects):
    """GET /api/projects returns serialized Project objects."""
    mock_projects.list_all = AsyncMock(return_value=[_make_project("proj-a"), _make_project("proj-b")])

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert items[0]["project_id"] == "proj-a"
    assert items[1]["project_id"] == "proj-b"


# ---------------------------------------------------------------------------
# /api/projects/{project_id}
# ---------------------------------------------------------------------------


async def test_get_project_not_found(test_app):
    """GET /api/projects/missing returns 404."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects/missing")

    assert resp.status_code == 404


async def test_get_project_found(test_app, mock_projects):
    """GET /api/projects/{project_id} returns 200 with project data when found."""
    mock_projects.get = AsyncMock(return_value=_make_project("test-proj"))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects/test-proj")

    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "test-proj"
    assert data["name"] == "Test Project"


# ---------------------------------------------------------------------------
# /api/projects/{project_id}/graph
# ---------------------------------------------------------------------------


async def test_graph_not_found(test_app):
    """GET /api/projects/missing/graph returns 404 when project does not exist."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects/missing/graph")

    assert resp.status_code == 404


async def test_graph_found(test_app, mock_projects, mock_knowledge):
    """GET /api/projects/{project_id}/graph returns 200 with nodes/edges."""
    mock_projects.get = AsyncMock(return_value=_make_project("test-proj"))
    mock_knowledge.get_graph_data = AsyncMock(
        return_value={"nodes": [{"id": "n1", "name": "Entity", "summary": "s"}], "edges": []}
    )

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects/test-proj/graph")

    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert data["nodes"][0]["id"] == "n1"


# ---------------------------------------------------------------------------
# /api/projects/{project_id}/insights
# ---------------------------------------------------------------------------


async def test_insights_not_found(test_app):
    """GET /api/projects/missing/insights returns 404."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects/missing/insights")

    assert resp.status_code == 404


async def test_insights_found(test_app, mock_projects):
    """GET /api/projects/{project_id}/insights returns 200 with pagination envelope."""
    mock_projects.get = AsyncMock(return_value=_make_project("test-proj"))
    mock_projects.get_insights = AsyncMock(
        return_value={"items": [], "total": 0, "page": 1, "limit": 20}
    )

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects/test-proj/insights")

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data


async def test_insights_passes_query_params(test_app, mock_projects):
    """Pagination query parameters page and limit are forwarded to the service."""
    mock_projects.get = AsyncMock(return_value=_make_project("test-proj"))
    mock_projects.get_insights = AsyncMock(
        return_value={"items": [], "total": 5, "page": 2, "limit": 3}
    )

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects/test-proj/insights?page=2&limit=3")

    assert resp.status_code == 200
    mock_projects.get_insights.assert_awaited_once_with("test-proj", 2, 3, None)


# ---------------------------------------------------------------------------
# /api/projects/{project_id}/timeline
# ---------------------------------------------------------------------------


async def test_timeline_not_found(test_app):
    """GET /api/projects/missing/timeline returns 404."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects/missing/timeline")

    assert resp.status_code == 404


async def test_timeline_found(test_app, mock_projects):
    """GET /api/projects/{project_id}/timeline returns 200 with list."""
    mock_projects.get = AsyncMock(return_value=_make_project("test-proj"))
    mock_projects.get_timeline = AsyncMock(return_value=[])

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/projects/test-proj/timeline")

    assert resp.status_code == 200
    assert resp.json() == []
