import logging

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.services.projects import ProjectsService

logger = logging.getLogger(__name__)


def make_forget(mcp: FastMCP, projects: ProjectsService) -> None:
    @mcp.tool
    async def forget(project_id: str, episode_id: str) -> dict:
        """Delete a stored knowledge item by its episode ID.

        Use this to remove incorrectly stored information. The episode_id is
        returned by remember() in the 'episode_id' field of its response.

        Note: If the episode was already extracted into the knowledge graph,
        graph entities derived from it may persist in FalkorDB. Only the
        SQLite record and future keyword fallback results are affected.
        """
        project = await projects.get(project_id)
        if project is None:
            raise ToolError(f"Project '{project_id}' not found. Call init_project first.")

        deleted = await projects.delete_episode(project_id, episode_id)
        if not deleted:
            raise ToolError(
                f"Episode '{episode_id}' not found in project '{project_id}'. "
                "Check the episode_id returned by remember()."
            )

        logger.info(f"Episode deleted: {episode_id} from project {project_id}")
        return {
            "deleted": True,
            "episode_id": episode_id,
            "note": "SQLite record removed. Graph entities from extraction may persist.",
        }
