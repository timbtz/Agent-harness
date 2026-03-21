import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def fake_repo(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "test", "dependencies": {"react": "^18"}})
    )
    (tmp_path / "README.md").write_text("# Test Project\nA test project for unit testing.")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").touch()
    return tmp_path


@pytest.mark.asyncio
async def test_scan_repo_basic(fake_repo):
    from src.services.scanner import scan_repo

    projects_mock = AsyncMock()
    projects_mock.create_episode.return_value = MagicMock(episode_id="ep_test001")
    queue = asyncio.Queue()
    count = await scan_repo(str(fake_repo), "test-project", projects_mock, queue)
    assert count >= 2  # package.json + README.md at minimum
    assert not queue.empty()


@pytest.mark.asyncio
async def test_scan_repo_missing_path():
    from src.services.scanner import scan_repo

    projects_mock = AsyncMock()
    queue = asyncio.Queue()
    count = await scan_repo("/nonexistent/path", "test-project", projects_mock, queue)
    assert count == 0
    assert queue.empty()


@pytest.mark.asyncio
async def test_scan_repo_file_path(tmp_path):
    from src.services.scanner import scan_repo

    file_path = tmp_path / "somefile.txt"
    file_path.write_text("hello")
    projects_mock = AsyncMock()
    queue = asyncio.Queue()
    count = await scan_repo(str(file_path), "test-project", projects_mock, queue)
    assert count == 0


@pytest.mark.asyncio
async def test_scan_repo_no_config_files(tmp_path):
    from src.services.scanner import scan_repo

    # Create repo with only a source file (no recognized config files)
    (tmp_path / "main.py").write_text("print('hello')")
    projects_mock = AsyncMock()
    projects_mock.create_episode.return_value = MagicMock(episode_id="ep_tree001")
    queue = asyncio.Queue()
    count = await scan_repo(str(tmp_path), "test-project", projects_mock, queue)
    # Should still get folder tree episode
    assert count >= 1


@pytest.mark.asyncio
async def test_scan_repo_truncates_large_file(tmp_path):
    from src.services.scanner import scan_repo

    # Write a file larger than 1800 chars
    large_content = "x" * 3000
    (tmp_path / "README.md").write_text(large_content)
    captured_contents = []

    async def mock_create_episode(project_id, content, category):
        captured_contents.append(content)
        return MagicMock(episode_id="ep_trunc001")

    projects_mock = AsyncMock()
    projects_mock.create_episode.side_effect = mock_create_episode
    queue = asyncio.Queue()
    await scan_repo(str(tmp_path), "test-project", projects_mock, queue)

    # Find the README episode and verify it was truncated
    readme_episodes = [c for c in captured_contents if "README.md" in c]
    assert readme_episodes
    assert "...[truncated]" in readme_episodes[0]
