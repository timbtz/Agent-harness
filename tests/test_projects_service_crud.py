"""Full CRUD coverage for ProjectsService using a real SQLite database in a temp directory."""
from unittest.mock import MagicMock

from src.services.projects import ProjectsService


def _make_settings(tmp_path):
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp_path / "test.db"
    return settings


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


async def test_create_project(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))

    project = await svc.create_project("My SaaS App", "A great app")

    assert project.project_id == "my-saas-app"
    assert project.name == "My SaaS App"
    assert project.description == "A great app"
    assert project.repo_path is None
    assert project.episode_count == 0


async def test_create_project_with_repo_path(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))

    project = await svc.create_project("Test Project", "desc", repo_path="/some/repo")

    assert project.repo_path == "/some/repo"


async def test_get_existing(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")

    project = await svc.get("test-project")

    assert project is not None
    assert project.project_id == "test-project"
    assert project.name == "Test Project"


async def test_get_missing(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))

    result = await svc.get("does-not-exist")

    assert result is None


async def test_list_all_empty(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))

    result = await svc.list_all()

    assert result == []


async def test_list_all_multiple(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Alpha Project", "first")
    await svc.create_project("Beta Project", "second")
    await svc.create_project("Gamma Project", "third")

    result = await svc.list_all()

    assert len(result) == 3
    ids = [p.project_id for p in result]
    assert "gamma-project" in ids
    assert "alpha-project" in ids
    # Newest created is gamma-project (last inserted), should appear first
    assert ids[0] == "gamma-project"


async def test_count_empty(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))

    result = await svc.count()

    assert result == 0


async def test_count_with_projects(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Project One", "desc one")
    await svc.create_project("Project Two", "desc two")

    result = await svc.count()

    assert result == 2


# ---------------------------------------------------------------------------
# Episode CRUD
# ---------------------------------------------------------------------------


async def test_create_episode(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")

    episode = await svc.create_episode("test-project", "We chose JWT for authentication", "decision")

    assert episode.episode_id.startswith("ep_")
    assert episode.project_id == "test-project"
    assert episode.content == "We chose JWT for authentication"
    assert episode.category == "decision"
    assert episode.status == "pending"
    assert episode.graphiti_episode_id is None


async def test_update_episode_status_to_processing(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")
    episode = await svc.create_episode("test-project", "Some content about the API", "insight")

    await svc.update_episode_status(episode.episode_id, "processing")

    pending = await svc.get_pending_episodes("test-project")
    assert len(pending) == 1
    assert pending[0].status == "processing"


async def test_update_episode_status_to_complete_with_graphiti_id(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")
    episode = await svc.create_episode("test-project", "Architecture decision recorded", "architecture")

    await svc.update_episode_status(episode.episode_id, "complete", graphiti_episode_id="gep_abc123")

    # complete episodes must not appear in pending list
    pending = await svc.get_pending_episodes("test-project")
    assert len(pending) == 0

    # verify graphiti_episode_id was persisted
    recent = await svc.get_recent_episodes("test-project", limit=1)
    assert recent[0].graphiti_episode_id == "gep_abc123"
    assert recent[0].status == "complete"


async def test_get_pending_episodes_returns_pending_and_processing(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")
    ep1 = await svc.create_episode("test-project", "Decision content here to check", "decision")
    ep2 = await svc.create_episode("test-project", "Insight content here to check", "insight")
    ep3 = await svc.create_episode("test-project", "Error content here to check out", "error")

    await svc.update_episode_status(ep2.episode_id, "processing")
    await svc.update_episode_status(ep3.episode_id, "complete")

    result = await svc.get_pending_episodes("test-project")

    returned_ids = {ep.episode_id for ep in result}
    assert ep1.episode_id in returned_ids
    assert ep2.episode_id in returned_ids
    assert ep3.episode_id not in returned_ids


async def test_get_pending_episodes_excludes_complete(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")
    episode = await svc.create_episode("test-project", "Some content that will complete", "goal")
    await svc.update_episode_status(episode.episode_id, "complete")

    result = await svc.get_pending_episodes("test-project")

    assert result == []


async def test_get_recent_episodes(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")
    for i in range(7):
        await svc.create_episode("test-project", f"Episode number {i} stored here for recall", "insight")

    result = await svc.get_recent_episodes("test-project", limit=5)

    assert len(result) == 5


async def test_get_recent_episodes_newest_first(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")
    ep1 = await svc.create_episode("test-project", "First episode content that was created", "decision")
    ep2 = await svc.create_episode("test-project", "Second episode content that was created", "insight")

    result = await svc.get_recent_episodes("test-project", limit=5)

    assert result[0].episode_id == ep2.episode_id
    assert result[1].episode_id == ep1.episode_id


async def test_get_recent_episodes_empty_project(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")

    result = await svc.get_recent_episodes("test-project", limit=5)

    assert result == []


async def test_count_episodes(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")
    await svc.create_episode("test-project", "First episode content here about jwt", "decision")
    await svc.create_episode("test-project", "Second episode content here about db", "insight")
    await svc.create_episode("test-project", "Third episode content here about auth", "error")

    result = await svc.count_episodes("test-project")

    assert result == 3


async def test_count_episodes_empty(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")

    result = await svc.count_episodes("test-project")

    assert result == 0


async def test_count_episodes_scoped_to_project(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Project Alpha", "desc")
    await svc.create_project("Project Beta", "desc")
    await svc.create_episode("project-alpha", "Alpha episode content here to store", "decision")
    await svc.create_episode("project-alpha", "Another alpha episode to store here", "insight")
    await svc.create_episode("project-beta", "Beta episode content here to store", "goal")

    alpha_count = await svc.count_episodes("project-alpha")
    beta_count = await svc.count_episodes("project-beta")

    assert alpha_count == 2
    assert beta_count == 1


async def test_get_existing_project_episode_count(tmp_path):
    """get() should return the up-to-date episode_count via the subquery."""
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")
    await svc.create_episode("test-project", "Episode one content here to record", "decision")
    await svc.create_episode("test-project", "Episode two content here to record", "insight")

    project = await svc.get("test-project")

    assert project is not None
    assert project.episode_count == 2


async def test_get_episodes_for_fallback_includes_failed(tmp_path):
    """get_episodes_for_fallback returns pending+processing+failed but NOT complete."""
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Test Project", "desc")

    ep1 = await svc.create_episode("test-project", "Episode one content here to record", "decision")
    ep2 = await svc.create_episode("test-project", "Episode two content here to record", "insight")
    ep3 = await svc.create_episode("test-project", "Episode three content here to record", "error")

    await svc.update_episode_status(ep1.episode_id, "complete")
    await svc.update_episode_status(ep2.episode_id, "failed")
    # ep3 stays pending

    results = await svc.get_episodes_for_fallback("test-project")

    returned_ids = {ep.episode_id for ep in results}
    assert ep1.episode_id not in returned_ids  # complete — excluded
    assert ep2.episode_id in returned_ids      # failed — included
    assert ep3.episode_id in returned_ids      # pending — included
    assert len(results) == 2
    assert {"failed", "pending"} == {ep.status for ep in results}


# ---------------------------------------------------------------------------
# get_all_orphaned_episodes (Task 4)
# ---------------------------------------------------------------------------


async def test_get_all_orphaned_episodes_returns_pending_and_processing(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    p1 = await svc.create_project("Project One", "desc")
    p2 = await svc.create_project("Project Two", "desc")

    ep1 = await svc.create_episode(p1.project_id, "Episode one content here", "decision")
    ep2 = await svc.create_episode(p2.project_id, "Episode two content here", "insight")
    ep3 = await svc.create_episode(p1.project_id, "Episode three content", "goal")

    # ep1 → processing (interrupted mid-extraction), ep2 → complete, ep3 → pending (default)
    await svc.update_episode_status(ep1.episode_id, "processing")
    await svc.update_episode_status(ep2.episode_id, "complete")

    orphaned = await svc.get_all_orphaned_episodes()

    assert len(orphaned) == 2
    ids = {ep.episode_id for ep in orphaned}
    assert ep1.episode_id in ids   # processing
    assert ep3.episode_id in ids   # pending
    assert ep2.episode_id not in ids  # complete — must NOT appear


async def test_get_all_orphaned_episodes_empty_when_all_complete(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    p = await svc.create_project("Project", "desc")
    ep = await svc.create_episode(p.project_id, "Some content here yes", "decision")
    await svc.update_episode_status(ep.episode_id, "complete")

    orphaned = await svc.get_all_orphaned_episodes()

    assert orphaned == []


async def test_get_all_orphaned_episodes_empty_db(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))

    orphaned = await svc.get_all_orphaned_episodes()

    assert orphaned == []


async def test_get_all_orphaned_episodes_orders_oldest_first(tmp_path):
    """Orphaned episodes are returned ASC (oldest first) for sequential re-extraction."""
    svc = await ProjectsService.create(_make_settings(tmp_path))
    p = await svc.create_project("Project", "desc")
    ep1 = await svc.create_episode(p.project_id, "First episode created here for ordering", "decision")
    ep2 = await svc.create_episode(p.project_id, "Second episode created here for ordering", "insight")

    orphaned = await svc.get_all_orphaned_episodes()

    assert orphaned[0].episode_id == ep1.episode_id
    assert orphaned[1].episode_id == ep2.episode_id


# ---------------------------------------------------------------------------
# delete_episode (Task 11)
# ---------------------------------------------------------------------------


async def test_delete_episode_returns_true_when_found(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    p = await svc.create_project("My Project", "desc")
    ep = await svc.create_episode(p.project_id, "Content to be deleted here", "decision")

    result = await svc.delete_episode(p.project_id, ep.episode_id)

    assert result is True
    # Episode no longer retrievable
    remaining = await svc.get_recent_episodes(p.project_id, limit=10)
    assert all(e.episode_id != ep.episode_id for e in remaining)


async def test_delete_episode_returns_false_when_not_found(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    p = await svc.create_project("My Project", "desc")

    result = await svc.delete_episode(p.project_id, "ep_nonexistent000")

    assert result is False


async def test_delete_episode_cannot_delete_across_projects(tmp_path):
    """project_id boundary: cannot delete another project's episode."""
    svc = await ProjectsService.create(_make_settings(tmp_path))
    p1 = await svc.create_project("Project One", "desc")
    p2 = await svc.create_project("Project Two", "desc")
    ep = await svc.create_episode(p1.project_id, "Content in project one here", "decision")

    result = await svc.delete_episode(p2.project_id, ep.episode_id)  # wrong project_id

    assert result is False
    # Original episode still exists
    remaining = await svc.get_recent_episodes(p1.project_id, limit=10)
    assert any(e.episode_id == ep.episode_id for e in remaining)


# ---------------------------------------------------------------------------
# delete_project
# ---------------------------------------------------------------------------


async def test_delete_project_returns_true(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("My Project", "desc")

    result = await svc.delete_project("my-project")

    assert result is True


async def test_delete_project_removes_from_list(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("My Project", "desc")

    await svc.delete_project("my-project")

    assert await svc.get("my-project") is None
    assert await svc.count() == 0


async def test_delete_project_cascades_episodes(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    project = await svc.create_project("My Project", "desc")
    await svc.create_episode(project.project_id, "Episode content to be cascade deleted", "decision")
    await svc.create_episode(project.project_id, "Another episode content cascade delete", "insight")

    await svc.delete_project(project.project_id)

    assert await svc.count_episodes(project.project_id) == 0


async def test_delete_project_not_found_returns_false(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))

    result = await svc.delete_project("nonexistent-project")

    assert result is False


async def test_delete_project_does_not_affect_other_projects(tmp_path):
    svc = await ProjectsService.create(_make_settings(tmp_path))
    await svc.create_project("Project A", "desc")
    await svc.create_project("Project B", "desc")

    await svc.delete_project("project-a")

    assert await svc.get("project-b") is not None
    assert await svc.count() == 1
