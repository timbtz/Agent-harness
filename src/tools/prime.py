import logging

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.services.briefing import generate_briefing
from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService

logger = logging.getLogger(__name__)


def make_prime(
    mcp: FastMCP, knowledge: KnowledgeService, projects: ProjectsService
) -> None:
    @mcp.tool
    async def prime(project_id: str) -> str:
        """Load compressed project context at the start of every coding session.

        Call this immediately when starting work on a project. Returns a structured
        briefing with key decisions, known pitfalls, and recent session summary
        in under 400 tokens.
        """
        project = await projects.get(project_id)
        if project is None:
            raise ToolError(
                f"Project '{project_id}' not found. Call init_project first."
            )

        return await generate_briefing(project, knowledge, projects)
