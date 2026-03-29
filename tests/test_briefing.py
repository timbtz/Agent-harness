"""Tests for briefing generation (src/services/briefing.py)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from src.models import SearchResult
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


async def test_briefing_key_decisions_shows_fact_content(tmp_path):
    """Key Decisions section shows fact content, not just the relationship type name."""
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    await projects.create_episode(project.project_id, "Some decision was captured here", "decision")

    graph_result = SearchResult(
        content="We migrated from PostgreSQL to SQLite",
        score=1.0,
        source="graph",
        entity_name="MIGRATED_AWAY_TO",
        created_at=datetime.now(timezone.utc),
    )
    knowledge = _make_knowledge(search_results=[graph_result])

    result = await generate_briefing(project, knowledge, projects)

    assert "We migrated from PostgreSQL to SQLite" in result
    # The relationship type may appear as a label prefix, but the fact content must also be present
    # The line must NOT consist solely of the edge type name with no fact appended
    assert "MIGRATED_AWAY_TO: We migrated from PostgreSQL to SQLite" in result


async def test_briefing_filters_superseded_facts_when_current_available(tmp_path):
    """When both current and superseded facts exist, only current appears in Key Decisions."""
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    await projects.create_episode(project.project_id, "Some decision was captured", "decision")

    superseded = SearchResult(
        content="Old approach using PostgreSQL",
        score=0.9,
        source="graph",
        entity_name="USED",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        invalid_at=datetime(2026, 2, 1, tzinfo=timezone.utc),  # superseded
    )
    current = SearchResult(
        content="New approach using SQLite",
        score=0.8,
        source="graph",
        entity_name="NOW_USES",
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        invalid_at=None,  # still valid
    )
    knowledge = _make_knowledge(search_results=[superseded, current])

    result = await generate_briefing(project, knowledge, projects)

    assert "New approach using SQLite" in result
    assert "~~" not in result   # No strikethrough when a current fact exists


async def test_briefing_marks_superseded_as_fallback_when_no_current_exists(tmp_path):
    """When all search results are superseded, shows them with strikethrough marker."""
    projects = await ProjectsService.create(_make_settings(tmp_path))
    project = await projects.create_project("Test Project", "desc")
    await projects.create_episode(project.project_id, "Some decision was captured", "decision")

    all_superseded = SearchResult(
        content="Ancient approach no longer used",
        score=1.0,
        source="graph",
        entity_name="USED_TO_USE",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        invalid_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    knowledge = _make_knowledge(search_results=[all_superseded])

    result = await generate_briefing(project, knowledge, projects)

    # Falls back to showing superseded fact with visual marker
    assert "Ancient approach no longer used" in result
    assert "~~" in result
    assert "superseded" in result
