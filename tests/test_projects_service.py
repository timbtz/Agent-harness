from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_get_insights_empty(tmp_path):
    from src.services.projects import ProjectsService

    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    svc = await ProjectsService.create(settings)
    result = await svc.get_insights("nonexistent", 1, 20, None)
    assert result == {"items": [], "total": 0, "page": 1, "limit": 20}


@pytest.mark.asyncio
async def test_get_timeline_empty(tmp_path):
    from src.services.projects import ProjectsService

    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    svc = await ProjectsService.create(settings)
    result = await svc.get_timeline("nonexistent")
    assert result == []


@pytest.mark.asyncio
async def test_get_insights_with_data(tmp_path):
    from src.services.projects import ProjectsService

    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    svc = await ProjectsService.create(settings)
    await svc.create_project("Test Project", "A test project")
    await svc.create_episode("test-project", "A decision was made here", "decision")
    await svc.create_episode("test-project", "An insight about the API", "insight")

    result = await svc.get_insights("test-project", 1, 20, None)
    assert result["total"] == 2
    assert len(result["items"]) == 2
    assert result["page"] == 1
    assert result["limit"] == 20


@pytest.mark.asyncio
async def test_get_insights_category_filter(tmp_path):
    from src.services.projects import ProjectsService

    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    svc = await ProjectsService.create(settings)
    await svc.create_project("Test Project", "A test project")
    await svc.create_episode("test-project", "A decision was made here", "decision")
    await svc.create_episode("test-project", "An insight about the API", "insight")

    result = await svc.get_insights("test-project", 1, 20, "decision")
    assert result["total"] == 1
    assert result["items"][0].category == "decision"


@pytest.mark.asyncio
async def test_get_timeline_ordered(tmp_path):
    from src.services.projects import ProjectsService

    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    svc = await ProjectsService.create(settings)
    await svc.create_project("Test Project", "A test project")
    await svc.create_episode("test-project", "First episode content here", "goal")
    await svc.create_episode("test-project", "Second episode content here", "decision")

    result = await svc.get_timeline("test-project")
    assert len(result) == 2
    # Oldest first
    assert result[0].created_at <= result[1].created_at


@pytest.mark.asyncio
async def test_get_insights_pagination(tmp_path):
    from src.services.projects import ProjectsService

    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    svc = await ProjectsService.create(settings)
    await svc.create_project("Test Project", "A test project")
    for i in range(5):
        await svc.create_episode("test-project", f"Episode content number {i} here", "insight")

    page1 = await svc.get_insights("test-project", 1, 3, None)
    assert page1["total"] == 5
    assert len(page1["items"]) == 3

    page2 = await svc.get_insights("test-project", 2, 3, None)
    assert page2["total"] == 5
    assert len(page2["items"]) == 2
