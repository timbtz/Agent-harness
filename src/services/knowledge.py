import asyncio
import logging
from datetime import datetime, timezone

from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.embedder import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.nodes import EpisodeType

from src.models import SearchResult

logger = logging.getLogger(__name__)


def _graphiti_group_id(project_id: str) -> str:
    """Sanitize project_id for use as Graphiti group_id.

    RediSearch treats hyphens as NOT operators in query strings.
    Replace with underscores which have no special meaning in RediSearch.
    The FalkorDB graph name (database=) keeps the original hyphenated project_id.
    """
    return project_id.replace("-", "_")


class KnowledgeService:
    def __init__(self, settings, llm_client, embedder):
        self._settings = settings
        self._llm_client = llm_client
        self._embedder = embedder
        self._graphiti_cache: dict[str, Graphiti] = {}

    @classmethod
    async def create(cls, settings) -> "KnowledgeService":
        llm_client = cls._build_llm_client(settings)
        embedder = cls._build_embedder(settings)
        svc = cls(settings, llm_client, embedder)
        await svc._verify_connection()
        logger.info("KnowledgeService initialized")
        return svc

    @staticmethod
    def _build_llm_client(settings):
        if settings.llm_provider == "anthropic":
            from graphiti_core.llm_client.anthropic_client import AnthropicClient

            return AnthropicClient(
                config=LLMConfig(
                    api_key=settings.llm_api_key,
                    model=settings.llm_model,
                )
            )
        # Default: openai
        return OpenAIClient(
            config=LLMConfig(
                api_key=settings.llm_api_key or settings.openai_api_key,
                model=settings.llm_model,
            )
        )

    @staticmethod
    def _build_embedder(settings):
        return OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=settings.openai_api_key or settings.llm_api_key,
                embedding_dim=1536,
                embedding_model="text-embedding-3-small",
            )
        )

    async def _verify_connection(self):
        delays = [1, 2, 4, 8, 15]
        for attempt, delay in enumerate(delays, 1):
            try:
                healthy = await self.check_connection()
                if healthy:
                    logger.info("FalkorDB connection verified")
                    return
            except Exception as e:
                logger.warning(f"FalkorDB attempt {attempt} failed: {e}")
            if attempt < len(delays):
                await asyncio.sleep(delay)
        raise RuntimeError("FalkorDB unavailable after 5 attempts")

    async def check_connection(self) -> bool:
        try:
            from falkordb import FalkorDB

            db = FalkorDB(host=self._settings.falkordb_host, port=self._settings.falkordb_port)
            g = db.select_graph("_health_check")
            g.query("RETURN 1")
            return True
        except Exception:
            return False

    async def get_graphiti(self, project_id: str) -> Graphiti:
        if project_id not in self._graphiti_cache:
            driver = FalkorDriver(
                host=self._settings.falkordb_host,
                port=self._settings.falkordb_port,
                database=project_id,
            )
            g = Graphiti(
                graph_driver=driver,
                llm_client=self._llm_client,
                embedder=self._embedder,
            )
            await g.build_indices_and_constraints()
            self._graphiti_cache[project_id] = g
            logger.info(f"Graphiti instance created for project: {project_id}")
        return self._graphiti_cache[project_id]

    async def add_episode(self, episode_id: str, content: str, category: str, project_id: str) -> str:
        g = await self.get_graphiti(project_id)
        result = await g.add_episode(
            name=f"ep-{episode_id}",
            episode_body=f"[{category.upper()}] {content}",
            source=EpisodeType.text,
            source_description=f"Agent knowledge capture — category: {category}",
            reference_time=datetime.now(timezone.utc),
            group_id=_graphiti_group_id(project_id),
        )
        return result.episode.uuid

    async def search(self, query: str, project_id: str, limit: int = 10) -> list[SearchResult]:
        try:
            g = await self.get_graphiti(project_id)
            # search() returns list[EntityEdge]
            edges = await g.search(
                query=query,
                group_ids=[_graphiti_group_id(project_id)],
                num_results=limit,
            )
        except Exception as e:
            logger.warning(f"Graph search failed for {project_id}: {e}")
            return []

        search_results: list[SearchResult] = []
        for edge in edges:
            search_results.append(
                SearchResult(
                    content=edge.fact,
                    score=1.0,
                    source="graph",
                    entity_name=edge.name,
                    created_at=getattr(edge, "created_at", None),
                )
            )

        return search_results[:limit]

    async def get_graph_data(self, project_id: str) -> dict:
        def _query() -> dict:
            from falkordb import FalkorDB

            db = FalkorDB(
                host=self._settings.falkordb_host,
                port=self._settings.falkordb_port,
            )
            g = db.select_graph(project_id)
            nodes_result = g.query(
                "MATCH (n:Entity) WHERE n.group_id = $gid RETURN n.uuid, n.name, n.summary",
                params={"gid": _graphiti_group_id(project_id)},
            )
            nodes = [{"id": row[0], "name": row[1], "summary": row[2]} for row in nodes_result.result_set if row[0]]
            edges_result = g.query(
                "MATCH (a:Entity)-[r]->(b:Entity) "
                "WHERE r.group_id = $gid AND r.invalid_at IS NULL "
                "RETURN a.uuid, b.uuid, r.fact, type(r)",
                params={"gid": _graphiti_group_id(project_id)},
            )
            edges = [
                {"source": row[0], "target": row[1], "fact": row[2], "type": row[3]}
                for row in edges_result.result_set
                if row[0] and row[1]
            ]
            return {"nodes": nodes, "edges": edges}

        try:
            return await asyncio.to_thread(_query)
        except Exception as e:
            logger.warning(f"Graph data query failed for {project_id}: {e}")
            return {"nodes": [], "edges": []}
