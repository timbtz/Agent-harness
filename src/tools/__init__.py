import asyncio

from fastmcp import FastMCP

from src.services.knowledge import KnowledgeService
from src.services.projects import ProjectsService


def register_tools(
    mcp: FastMCP,
    knowledge: KnowledgeService,
    projects: ProjectsService,
    extraction_queue: asyncio.Queue,
) -> None:
    from src.tools.forget import make_forget
    from src.tools.init_project import make_init_project
    from src.tools.prime import make_prime
    from src.tools.recall import make_recall
    from src.tools.remember import make_remember

    make_init_project(mcp, projects, extraction_queue)
    make_remember(mcp, knowledge, projects, extraction_queue)
    make_recall(mcp, knowledge, projects)
    make_prime(mcp, knowledge, projects)
    make_forget(mcp, projects)
