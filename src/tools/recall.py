import logging

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService

logger = logging.getLogger(__name__)


def make_recall(mcp: FastMCP, knowledge: KnowledgeService, projects: ProjectsService) -> None:
    @mcp.tool
    async def recall(project_id: str, query: str) -> str:
        """Search the knowledge graph for specific information.

        Use natural language questions or keyword phrases. Call this when
        unsure if something was already tried or decided.
        """
        if len(query) < 3:
            raise ToolError("Query must be at least 3 characters.")
        if len(query) > 500:
            raise ToolError("Query must be 500 characters or fewer.")

        project = await projects.get(project_id)
        if project is None:
            raise ToolError(f"Project '{project_id}' not found. Call init_project first.")

        # Primary: graph search
        graph_results = await knowledge.search(query, project_id, limit=8)

        # Fallback: search raw pending/processing/failed episodes
        raw_episodes = await projects.get_episodes_for_fallback(project_id)
        query_words = set(query.lower().split())
        raw_matches = [ep for ep in raw_episodes if any(w in ep.content.lower() for w in query_words)][:3]

        if not graph_results and not raw_matches:
            return "No matching knowledge found for this query."

        lines = [f'### Recall Results: "{query}"', ""]
        if graph_results:
            lines.append("**From knowledge graph:**")
            for r in graph_results[:6]:
                label = r.entity_name or ""
                snippet = r.content[:120]
                lines.append(f"- {label + ': ' if label else ''}{snippet}")
            lines.append("")
        if raw_matches:
            lines.append("**From recent unprocessed episodes:**")
            for ep in raw_matches:
                lines.append(f"- [{ep.category}] {ep.content[:120]}")

        return "\n".join(lines)
