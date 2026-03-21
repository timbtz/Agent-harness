import logging

from src.models import Project
from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService

logger = logging.getLogger(__name__)


async def generate_briefing(
    project: Project,
    knowledge: KnowledgeService,
    projects: ProjectsService,
) -> str:
    recent = await projects.get_recent_episodes(project.project_id, limit=5)

    if not recent:
        return (
            f"## Project: {project.name}\n"
            "No knowledge stored yet. Use remember() to capture decisions, insights, and errors."
        )

    total_count = await projects.count_episodes(project.project_id)

    decisions = await knowledge.search("key decisions architecture choices", project.project_id, limit=4)
    pitfalls = await knowledge.search("errors failures pitfalls issues problems", project.project_id, limit=3)

    lines = [
        f"## Project: {project.name}",
        f"**Stack:** {project.description[:120]}",
        f"**Status:** {total_count} insights stored",
        "",
    ]

    if decisions:
        lines.append("### Key Decisions")
        for r in decisions[:4]:
            label = r.entity_name or r.content[:100]
            lines.append(f"- {label[:100]}")
        lines.append("")

    if pitfalls:
        lines.append("### Known Pitfalls")
        for r in pitfalls[:3]:
            label = r.entity_name or r.content[:100]
            lines.append(f"- {label[:100]}")
        lines.append("")

    lines.append("### Last Session")
    for ep in recent[:5]:
        lines.append(f"- [{ep.category}] {ep.content[:80]}")

    return "\n".join(lines)
