import asyncio
import logging
import os
import signal
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

# Configure logging to stderr BEFORE anything else
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _extraction_worker(
    queue: asyncio.Queue,
    knowledge,
    projects,
) -> None:
    logger.info("Extraction worker started")
    while True:
        item = await queue.get()
        if item is None:  # shutdown sentinel
            queue.task_done()
            return
        episode_id, content, category, project_id = item
        try:
            await projects.update_episode_status(episode_id, "processing")
            gid = await knowledge.add_episode(episode_id, content, category, project_id)
            await projects.update_episode_status(episode_id, "complete", gid)
            logger.info(f"Extraction complete: {episode_id}")
        except Exception as e:
            logger.error(f"Extraction failed {episode_id}: {e}", exc_info=True)
            await projects.update_episode_status(episode_id, "failed")
        finally:
            queue.task_done()


async def main_async() -> None:
    # Load MCP_ENV_FILE if set (before get_settings)
    env_file = os.environ.get("MCP_ENV_FILE")
    if env_file:
        from dotenv import load_dotenv

        load_dotenv(env_file, override=True)
        logger.info(f"Loaded env from MCP_ENV_FILE: {env_file}")

    from src.config import get_settings

    settings = get_settings()

    # Set log level from settings
    logging.getLogger().setLevel(settings.log_level.upper())

    from src.api.routes import create_router
    from src.services.knowledge import KnowledgeService
    from src.services.projects import ProjectsService
    from src.tools import register_tools

    # Initialize services
    logger.info("Initializing ProjectsService...")
    projects = await ProjectsService.create(settings)

    logger.info("Initializing KnowledgeService (connecting to FalkorDB)...")
    knowledge = await KnowledgeService.create(settings)

    # Create extraction queue and workers
    extraction_queue: asyncio.Queue = asyncio.Queue()
    worker_tasks = []
    for _ in range(settings.extraction_workers):
        t = asyncio.create_task(_extraction_worker(extraction_queue, knowledge, projects))
        worker_tasks.append(t)
    logger.info(f"Started {settings.extraction_workers} extraction workers")

    # Create FastMCP server
    mcp = FastMCP(name="agent-harness", version="0.1.0")
    register_tools(mcp, knowledge, projects, extraction_queue)
    logger.info("MCP tools registered")

    # Create FastAPI app
    app = FastAPI(title="Agent Harness", version="0.1.0")

    origins = [o.strip() for o in settings.allowed_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    router = create_router(knowledge, projects)
    app.include_router(router, prefix="/api")
    logger.info("REST routes registered")

    # Configure Uvicorn
    config = uvicorn.Config(
        app=app,
        host=settings.uvicorn_host,
        port=settings.http_port,
        loop="asyncio",
        workers=1,
        log_config=None,
        access_log=False,
    )
    http_server = uvicorn.Server(config)

    # Graceful shutdown handler
    def handle_shutdown(sig, frame):
        logger.info(f"Signal {sig} received — initiating shutdown")
        http_server.should_exit = True

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    logger.info(f"Starting Agent Harness — HTTP on {settings.uvicorn_host}:{settings.http_port}")

    try:
        await asyncio.gather(mcp.run_async(), http_server.serve())
    finally:
        logger.info("Draining extraction queue (30s timeout)...")
        for _ in range(settings.extraction_workers):
            await extraction_queue.put(None)  # sentinel per worker
        try:
            await asyncio.wait_for(extraction_queue.join(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("Extraction queue drain timed out after 30s")
        for t in worker_tasks:
            t.cancel()
        logger.info("Shutdown complete")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
