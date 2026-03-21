import asyncio
import logging
import re

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.services.projects import ProjectsService

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:64]


async def _do_scan(
    repo_path: str,
    project_id: str,
    projects: ProjectsService,
    extraction_queue: asyncio.Queue,
) -> None:
    try:
        from src.services.scanner import scan_repo

        count = await scan_repo(repo_path, project_id, projects, extraction_queue)
        logger.info(f"scan_repo completed: {count} episodes queued for {project_id}")
    except Exception as e:
        logger.error(f"scan_repo failed for {project_id}: {e}", exc_info=True)


def make_init_project(mcp: FastMCP, projects: ProjectsService, extraction_queue: asyncio.Queue) -> None:
    @mcp.tool
    async def init_project(
        name: str,
        description: str,
        scan_repo: bool = False,
        repo_path: str | None = None,
    ) -> dict:
        """Create or retrieve a project with its own isolated knowledge graph namespace.

        Idempotent: safe to call multiple times with the same name.
        Returns existing project if name already exists.
        """
        if not name or len(name) > 128:
            raise ToolError("name must be 1–128 characters.")
        if not description or len(description) > 2000:
            raise ToolError("description must be 1–2000 characters.")

        project_id = slugify(name)
        if not project_id:
            raise ToolError("name produces empty slug — use alphanumeric characters.")

        existing = await projects.get(project_id)
        if existing:
            return {
                "project_id": project_id,
                "status": "existing",
                "name": existing.name,
                "description": existing.description,
            }

        project = await projects.create_project(name, description, repo_path)
        result: dict = {
            "project_id": project.project_id,
            "status": "created",
            "name": project.name,
            "description": project.description,
        }

        if scan_repo:
            actual_path = repo_path or "."
            asyncio.create_task(_do_scan(actual_path, project_id, projects, extraction_queue))
            result["scan_repo_queued"] = True

        return result
