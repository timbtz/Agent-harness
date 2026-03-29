import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import aiosqlite

from src.models import Episode, Project

logger = logging.getLogger(__name__)

CREATE_PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    repo_path TEXT
)
"""

CREATE_EPISODES_TABLE = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    graphiti_episode_id TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
)
"""


def slugify(name: str) -> str:
    import re

    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:64]


class ProjectsService:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    @classmethod
    async def create(cls, settings) -> "ProjectsService":
        db_path = settings.sqlite_path_resolved
        db_path.parent.mkdir(parents=True, exist_ok=True)
        svc = cls(db_path)
        await svc._init_db()
        logger.info(f"ProjectsService initialized at {db_path}")
        return svc

    async def _init_db(self):
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(CREATE_PROJECTS_TABLE)
            await db.execute(CREATE_EPISODES_TABLE)
            await db.commit()

    async def get(self, project_id: str) -> Project | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT p.*, (SELECT COUNT(*) FROM episodes WHERE project_id = p.project_id) AS episode_count "
                "FROM projects p WHERE p.project_id = ?",
                (project_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return Project(
                    project_id=row["project_id"],
                    name=row["name"],
                    description=row["description"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    repo_path=row["repo_path"],
                    episode_count=row["episode_count"],
                )

    async def create_project(self, name: str, description: str, repo_path: str | None = None) -> Project:
        project_id = slugify(name)
        created_at = datetime.now(timezone.utc)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO projects (project_id, name, description, created_at, repo_path) VALUES (?, ?, ?, ?, ?)",
                (project_id, name, description, created_at.isoformat(), repo_path),
            )
            await db.commit()
        logger.info(f"Project created: {project_id}")
        return Project(
            project_id=project_id,
            name=name,
            description=description,
            created_at=created_at,
            repo_path=repo_path,
            episode_count=0,
        )

    async def list_all(self) -> list[Project]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT p.*, (SELECT COUNT(*) FROM episodes WHERE project_id = p.project_id) AS episode_count "
                "FROM projects p ORDER BY p.created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    Project(
                        project_id=row["project_id"],
                        name=row["name"],
                        description=row["description"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        repo_path=row["repo_path"],
                        episode_count=row["episode_count"],
                    )
                    for row in rows
                ]

    async def count(self) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM projects") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def create_episode(self, project_id: str, content: str, category: str) -> Episode:
        episode_id = "ep_" + uuid4().hex[:12]
        created_at = datetime.now(timezone.utc)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO episodes (episode_id, project_id, content, category, status, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?)",
                (episode_id, project_id, content, category, created_at.isoformat()),
            )
            await db.commit()
        return Episode(
            episode_id=episode_id,
            project_id=project_id,
            content=content,
            category=category,  # type: ignore[arg-type]
            status="pending",
            created_at=created_at,
        )

    async def update_episode_status(
        self,
        episode_id: str,
        status: str,
        graphiti_episode_id: str | None = None,
    ) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE episodes SET status = ?, graphiti_episode_id = ? WHERE episode_id = ?",
                (status, graphiti_episode_id, episode_id),
            )
            await db.commit()

    async def get_pending_episodes(self, project_id: str) -> list[Episode]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM episodes WHERE project_id = ? AND status IN ('pending', 'processing') "
                "ORDER BY created_at DESC",
                (project_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_episode(row) for row in rows]

    async def get_episodes_for_fallback(self, project_id: str) -> list[Episode]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM episodes WHERE project_id = ? AND status IN ('pending', 'processing', 'failed') "
                "ORDER BY created_at DESC",
                (project_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_episode(row) for row in rows]

    async def get_all_orphaned_episodes(self) -> list[Episode]:
        """Return all pending/processing episodes across ALL projects.

        Called at startup to re-queue episodes that were interrupted by a
        server restart. Returns oldest first (ASC) so they re-extract in
        original order.
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM episodes WHERE status IN ('pending', 'processing') ORDER BY created_at ASC",
            ) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_episode(row) for row in rows]

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its episodes. Returns True if deleted, False if not found."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM episodes WHERE project_id = ?", (project_id,))
            async with db.execute("DELETE FROM projects WHERE project_id = ?", (project_id,)) as cursor:
                await db.commit()
                return cursor.rowcount > 0

    async def delete_episode(self, project_id: str, episode_id: str) -> bool:
        """Delete an episode by ID. Returns True if deleted, False if not found.

        Note: Only deletes the SQLite record. If the episode was already extracted
        into the Graphiti knowledge graph, those entities may persist in FalkorDB.
        """
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "DELETE FROM episodes WHERE episode_id = ? AND project_id = ?",
                (episode_id, project_id),
            ) as cursor:
                await db.commit()
                return cursor.rowcount > 0

    async def get_recent_episodes(self, project_id: str, limit: int = 5) -> list[Episode]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM episodes WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_episode(row) for row in rows]

    async def count_episodes(self, project_id: str) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM episodes WHERE project_id = ?", (project_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_insights(
        self,
        project_id: str,
        page: int,
        limit: int,
        category: str | None,
    ) -> dict:
        offset = (page - 1) * limit
        if category:
            count_sql = "SELECT COUNT(*) FROM episodes WHERE project_id = ? AND category = ?"
            count_params = (project_id, category)
            items_sql = (
                "SELECT * FROM episodes WHERE project_id = ? AND category = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            items_params = (project_id, category, limit, offset)
        else:
            count_sql = "SELECT COUNT(*) FROM episodes WHERE project_id = ?"
            count_params = (project_id,)
            items_sql = "SELECT * FROM episodes WHERE project_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            items_params = (project_id, limit, offset)
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(count_sql, count_params) as cur:
                row = await cur.fetchone()
                total = row[0] if row else 0
            async with db.execute(items_sql, items_params) as cur:
                rows = await cur.fetchall()
                items = [_row_to_episode(row) for row in rows]
        return {"items": items, "total": total, "page": page, "limit": limit}

    async def get_timeline(self, project_id: str, limit: int = 100) -> list:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM episodes WHERE project_id = ? ORDER BY created_at ASC LIMIT ?",
                (project_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_episode(row) for row in rows]


def _row_to_episode(row) -> Episode:
    return Episode(
        episode_id=row["episode_id"],
        project_id=row["project_id"],
        content=row["content"],
        category=row["category"],  # type: ignore[arg-type]
        status=row["status"],  # type: ignore[arg-type]
        created_at=datetime.fromisoformat(row["created_at"]),
        graphiti_episode_id=row["graphiti_episode_id"],
    )
