import logging
from datetime import datetime, timezone

from src.models import Project
from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService

logger = logging.getLogger(__name__)


def _sort_by_recency(results):
    """Sort SearchResults newest-first; treat None created_at as oldest."""
    _epoch = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(results, key=lambda r: r.created_at or _epoch, reverse=True)


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
        current = _sort_by_recency([r for r in decisions if r.invalid_at is None])
        historical = _sort_by_recency([r for r in decisions if r.invalid_at is not None])
        to_show = (current or historical)[:4]
        lines.append("### Key Decisions")
        for r in to_show:
            label = r.entity_name or ""
            content = r.content[:100]
            if r.invalid_at is not None:
                lines.append(f"- ~~{label + ': ' if label else ''}{content}~~ *(superseded)*")
            else:
                lines.append(f"- {label + ': ' if label else ''}{content}")
        lines.append("")

    if pitfalls:
        current_p = _sort_by_recency([r for r in pitfalls if r.invalid_at is None])
        historical_p = _sort_by_recency([r for r in pitfalls if r.invalid_at is not None])
        to_show_p = (current_p or historical_p)[:3]
        lines.append("### Known Pitfalls")
        for r in to_show_p:
            label = r.entity_name or ""
            content = r.content[:100]
            if r.invalid_at is not None:
                lines.append(f"- ~~{label + ': ' if label else ''}{content}~~ *(superseded)*")
            else:
                lines.append(f"- {label + ': ' if label else ''}{content}")
        lines.append("")

    lines.append("### Last Session")
    for ep in recent[:5]:
        lines.append(f"- [{ep.category}] {ep.content[:80]}")

    return "\n".join(lines)
