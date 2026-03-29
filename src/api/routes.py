import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.models import SearchResult
from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    limit: int = Field(10, ge=1, le=50)

logger = logging.getLogger(__name__)


def create_router(knowledge: KnowledgeService, projects: ProjectsService) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health():
        ok = await knowledge.check_connection()
        count = await projects.count()
        return {
            "status": "ok" if ok else "degraded",
            "falkordb_connected": ok,
            "projects_count": count,
        }

    @router.get("/projects")
    async def list_projects():
        return await projects.list_all()

    @router.get("/projects/{project_id}")
    async def get_project(project_id: str):
        p = await projects.get(project_id)
        if not p:
            raise HTTPException(404, detail=f"Project '{project_id}' not found")
        return p

    @router.get("/projects/{project_id}/graph")
    async def get_graph(project_id: str):
        await _require_project(project_id, projects)
        return await knowledge.get_graph_data(project_id)

    @router.get("/projects/{project_id}/insights")
    async def get_insights(
        project_id: str,
        page: int = 1,
        limit: int = 20,
        category: str | None = None,
    ):
        await _require_project(project_id, projects)
        return await projects.get_insights(project_id, page, limit, category)

    @router.get("/projects/{project_id}/timeline")
    async def get_timeline(project_id: str):
        await _require_project(project_id, projects)
        return await projects.get_timeline(project_id)

    @router.delete("/projects/{project_id}/episodes/{episode_id}")
    async def delete_episode(project_id: str, episode_id: str):
        await _require_project(project_id, projects)
        deleted = await projects.delete_episode(project_id, episode_id)
        if not deleted:
            raise HTTPException(404, detail=f"Episode '{episode_id}' not found")
        return {"deleted": True, "episode_id": episode_id}

    @router.delete("/projects/{project_id}")
    async def delete_project(project_id: str):
        await _require_project(project_id, projects)
        await projects.delete_project(project_id)
        return {
            "deleted": True,
            "project_id": project_id,
            "note": "SQLite records removed. Graph entities in FalkorDB may persist.",
        }

    @router.post("/projects/{project_id}/search")
    async def search_project(project_id: str, body: SearchRequest) -> dict:
        await _require_project(project_id, projects)

        # Primary: graph search
        graph_results = await knowledge.search(body.query, project_id, limit=body.limit)

        # Fallback: keyword match over pending/processing/failed episodes
        raw_episodes = await projects.get_episodes_for_fallback(project_id)
        query_words = set(body.query.lower().split())
        raw_matches = [ep for ep in raw_episodes if any(w in ep.content.lower() for w in query_words)][: body.limit]

        results: list[SearchResult] = list(graph_results)
        for ep in raw_matches:
            results.append(
                SearchResult(
                    content=ep.content,
                    score=0.5,
                    source="raw_episode",
                    created_at=ep.created_at,
                )
            )

        return {"query": body.query, "results": results, "total": len(results)}

    return router


async def _require_project(project_id: str, projects: ProjectsService):
    if not await projects.get(project_id):
        raise HTTPException(404, detail=f"Project '{project_id}' not found")
