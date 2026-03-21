"""Smoke tests — verify imports and basic model validation."""
from datetime import datetime, timezone

import pytest

from src.models import Episode, Project, SearchResult
from src.tools.init_project import slugify


def test_slugify():
    assert slugify("My SaaS App") == "my-saas-app"
    assert slugify("Hello World!") == "hello-world"
    assert slugify("test") == "test"


def test_episode_model():
    ep = Episode(
        episode_id="ep_abc123",
        project_id="test",
        content="test content",
        category="decision",
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    assert ep.episode_id == "ep_abc123"


def test_project_model():
    p = Project(
        project_id="test",
        name="Test",
        description="desc",
        created_at=datetime.now(timezone.utc),
    )
    assert p.project_id == "test"


def test_search_result_model():
    r = SearchResult(
        content="some content",
        score=0.9,
        source="graph",
        entity_name="Entity",
        created_at=datetime.now(timezone.utc),
    )
    assert r.source == "graph"
    assert r.score == 0.9
