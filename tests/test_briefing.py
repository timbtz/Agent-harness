"""Tests for briefing generation (src/services/briefing.py)."""
from unittest.mock import AsyncMock, MagicMock

from src.services.briefing import generate_briefing
from src.services.projects import ProjectsService


def _make_settings(tmp_path):
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    return settings


def _make_knowledge(search_results=None):
    knowledge = MagicMock()
    knowledge.search = AsyncMock(return_value=search_results or [])
    return knowledge


async def test_briefing_empty_project(tmp_path):
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    knowledge = _make_knowledge()

    result = await generate_briefing(project, knowledge, projects)

    assert "No knowledge stored yet" in result


async def test_briefing_empty_project_contains_project_name(tmp_path):
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("My Important Project", "desc")
    knowledge = _make_knowledge()

    result = await generate_briefing(project, knowledge, projects)

    assert "My Important Project" in result


async def test_briefing_with_episodes(tmp_path):
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "A test project description here")
    await projects.create_episode(project.project_id, "We chose FastAPI for the REST API layer", "decision")
    knowledge = _make_knowledge()

    result = await generate_briefing(project, knowledge, projects)

    assert "## Project:" in result
    assert "### Last Session" in result


async def test_briefing_shows_episode_content(tmp_path):
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    await projects.create_episode(
        project.project_id,
        "Pydantic v2 is used for all data validation throughout the app",
        "insight",
    )
    knowledge = _make_knowledge()

    result = await generate_briefing(project, knowledge, projects)

    assert "Pydantic v2" in result


async def test_briefing_shows_episode_category(tmp_path):
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    await projects.create_episode(
        project.project_id,
        "Attempted to use Redis pub/sub for events, it failed due to connection limits",
        "error",
    )
    knowledge = _make_knowledge()

    result = await generate_briefing(project, knowledge, projects)

    assert "[error]" in result


async def test_briefing_caps_length(tmp_path):
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    for i in range(10):
        await projects.create_episode(
            project.project_id,
            f"Episode {i}: some lengthy knowledge content that could inflate the briefing significantly",
            "insight",
        )
    knowledge = _make_knowledge()

    result = await generate_briefing(project, knowledge, projects)

    assert isinstance(result, str)
    assert len(result) < 4000


async def test_briefing_shows_status_count(tmp_path):
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    await projects.create_episode(project.project_id, "First knowledge insight stored for this project", "insight")
    await projects.create_episode(project.project_id, "Second knowledge decision stored for this project", "decision")
    knowledge = _make_knowledge()

    result = await generate_briefing(project, knowledge, projects)

    assert "2" in result


async def test_briefing_no_knowledge_search_when_empty(tmp_path):
    """When there are no episodes, generate_briefing returns early without calling knowledge.search."""
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    knowledge = _make_knowledge()

    await generate_briefing(project, knowledge, projects)

    knowledge.search.assert_not_called()


async def test_briefing_calls_knowledge_search_when_episodes_exist(tmp_path):
    """When episodes exist, generate_briefing calls knowledge.search for decisions and pitfalls."""
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    await projects.create_episode(project.project_id, "Some decision content that was captured here", "decision")
    knowledge = _make_knowledge()

    await generate_briefing(project, knowledge, projects)

    assert knowledge.search.call_count == 2
