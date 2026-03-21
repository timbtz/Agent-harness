import logging

from fastapi import APIRouter, HTTPException

from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService

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

    return router


async def _require_project(project_id: str, projects: ProjectsService):
    if not await projects.get(project_id):
        raise HTTPException(404, detail=f"Project '{project_id}' not found")
