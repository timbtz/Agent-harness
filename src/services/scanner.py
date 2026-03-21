import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
}

_CONFIG_FILES = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "docker-compose.yml",
    "docker-compose.yaml",
    "README.md",
    "README.rst",
]


def _read_file_content(path: Path, label: str) -> str | None:
    try:
        text = path.read_text(errors="replace")
    except Exception as e:
        logger.warning(f"scan_repo: could not read {path}: {e}")
        return None
    if not text.strip():
        return None
    if len(text) > 1800:
        text = text[:1800] + "...[truncated]"
    return f"Repository {label} ({path.name}):\n{text}"


def _build_folder_tree(root: Path, max_depth: int = 2) -> str | None:
    lines: list[str] = []

    def _walk(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        count = 0
        for entry in entries:
            if count >= 30:
                lines.append("  " * depth + "...")
                break
            if entry.name.startswith("."):
                continue
            if entry.is_dir() and entry.name in _IGNORE_DIRS:
                continue
            indent = "  " * depth
            if entry.is_dir():
                lines.append(f"{indent}{entry.name}/")
                _walk(entry, depth + 1)
            else:
                lines.append(f"{indent}{entry.name}")
            count += 1

    _walk(root, 0)
    if not lines:
        return None
    return "Repository folder structure:\n" + "\n".join(lines)


async def scan_repo(
    repo_path: str,
    project_id: str,
    projects,
    extraction_queue: asyncio.Queue,
) -> int:
    path = Path(repo_path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        logger.warning(f"scan_repo: path not found or not a directory: {path}")
        return 0

    count = 0
    contents: list[str] = []

    # Config files
    for filename in _CONFIG_FILES:
        file_path = path / filename
        if file_path.exists() and file_path.is_file():
            content = _read_file_content(file_path, filename)
            if content and len(content) >= 10:
                contents.append(content)
                logger.info(f"scan_repo: queued episode for {filename}")

    # docs/*.md (up to 5 files, sorted)
    docs_dir = path / "docs"
    if docs_dir.is_dir():
        doc_files = sorted(docs_dir.glob("*.md"))[:5]
        for doc_file in doc_files:
            content = _read_file_content(doc_file, f"docs/{doc_file.name}")
            if content and len(content) >= 10:
                contents.append(content)
                logger.info(f"scan_repo: queued episode for docs/{doc_file.name}")

    # Folder tree
    tree = _build_folder_tree(path)
    if tree and len(tree) >= 10:
        contents.append(tree)
        logger.info("scan_repo: queued folder tree episode")

    # Enqueue all episodes
    for content in contents:
        episode = await projects.create_episode(project_id, content, "architecture")
        await extraction_queue.put((episode.episode_id, content, "architecture", project_id))
        count += 1

    logger.info(f"scan_repo: {count} episodes queued for project {project_id}")
    return count
