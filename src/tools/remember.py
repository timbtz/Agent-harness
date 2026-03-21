import asyncio
import logging
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService

logger = logging.getLogger(__name__)


def make_remember(
    mcp: FastMCP,
    knowledge: KnowledgeService,
    projects: ProjectsService,
    extraction_queue: asyncio.Queue,
) -> None:
    @mcp.tool
    async def remember(
        project_id: str,
        content: str,
        category: Literal["decision", "insight", "error", "goal", "architecture"],
    ) -> dict:
        """Store a piece of project knowledge in the persistent knowledge graph.

        Call this whenever you discover something new about an API, make an
        architectural decision, encounter a failure, or receive a new requirement.
        """
        if len(content) < 10:
            raise ToolError("Content must be at least 10 characters.")
        if len(content) > 2000:
            raise ToolError("Content must be 2000 characters or fewer.")

        project = await projects.get(project_id)
        if project is None:
            raise ToolError(
                f"Project '{project_id}' not found. Call init_project first."
            )

        episode = await projects.create_episode(project_id, content, category)
        await extraction_queue.put((episode.episode_id, content, category, project_id))

        return {
            "status": "stored",
            "episode_id": episode.episode_id,
            "category": category,
            "processing": "async — graph extraction in progress",
        }
