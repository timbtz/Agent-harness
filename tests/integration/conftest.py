"""Integration test configuration.

These tests require live FalkorDB and a valid OpenAI API key.
They are skipped by default unless INTEGRATION_TESTS=1 is set.

Usage:
    INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v
"""
import os

import pytest
import pytest_asyncio
from unittest.mock import MagicMock

from src.config import get_settings
from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService


def pytest_runtest_setup(item):
    if "integration" in item.keywords and not os.getenv("INTEGRATION_TESTS"):
        pytest.skip(
            "Integration tests require: INTEGRATION_TESTS=1, "
            "docker compose up -d, and valid OPENAI_API_KEY"
        )


@pytest_asyncio.fixture(scope="module")
async def live_projects(tmp_path_factory):
    """ProjectsService backed by a real (but temp) SQLite database."""
    tmp = tmp_path_factory.mktemp("integration")
    settings = MagicMock()
    settings.sqlite_path_resolved = tmp / "integration.db"
    svc = await ProjectsService.create(settings)
    return svc


@pytest_asyncio.fixture(scope="module")
async def live_knowledge():
    """KnowledgeService backed by real FalkorDB (requires docker compose up -d)."""
    settings = get_settings()
    svc = await KnowledgeService.create(settings)
    return svc
