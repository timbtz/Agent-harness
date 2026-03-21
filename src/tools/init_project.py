import logging
import re

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.services.projects import ProjectsService

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:64]


def make_init_project(mcp: FastMCP, projects: ProjectsService) -> None:
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

        if scan_repo:
            logger.warning("scan_repo=True is not yet implemented (Phase 2). Ignoring.")

        project = await projects.create_project(name, description, repo_path)
        return {
            "project_id": project.project_id,
            "status": "created",
            "name": project.name,
            "description": project.description,
        }
