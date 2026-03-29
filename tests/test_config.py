"""Tests for Settings loading with defaults."""
from src.config import Settings


def test_settings_defaults(monkeypatch):
    # graphiti_core calls load_dotenv() at import time, leaking .env into os.environ.
    # Unset the vars we're testing so Settings() reads its built-in defaults.
    for var in ("HTTP_PORT", "FALKORDB_HOST", "FALKORDB_PORT", "UVICORN_HOST",
                "EXTRACTION_WORKERS", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.falkordb_host == "localhost"
    assert s.falkordb_port == 6379
    assert s.http_port == 8080
    assert s.uvicorn_host == "127.0.0.1"
    assert s.extraction_workers == 4
    assert s.llm_model == "gpt-4.1-mini"


def test_sqlite_path_resolved():
    s = Settings()
    path = s.sqlite_path_resolved
    assert path.name == "projects.db"
    assert "agent-harness" in str(path)
