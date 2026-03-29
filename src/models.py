from datetime import datetime
from typing import Literal

from pydantic import BaseModel

EpisodeStatus = Literal["pending", "processing", "complete", "failed"]
KnowledgeCategory = Literal["decision", "insight", "error", "goal", "architecture"]


class Project(BaseModel):
    project_id: str  # slug, e.g. "my-saas-app"
    name: str
    description: str
    created_at: datetime
    repo_path: str | None = None
    episode_count: int = 0


class Episode(BaseModel):
    episode_id: str  # "ep_" + uuid4().hex[:12]
    project_id: str
    content: str
    category: KnowledgeCategory
    status: EpisodeStatus = "pending"
    created_at: datetime
    graphiti_episode_id: str | None = None


class SearchResult(BaseModel):
    content: str
    score: float
    source: Literal["graph", "raw_episode"]
    entity_name: str | None = None
    created_at: datetime | None = None
    invalid_at: datetime | None = None
