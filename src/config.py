from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM
    llm_provider: Literal["openai", "anthropic", "ollama"] = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: str = ""

    # FalkorDB — must be passed explicitly, NOT read from env automatically by FalkorDriver
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379

    # Server
    http_port: int = 8080
    uvicorn_host: str = "127.0.0.1"
    log_level: str = "info"
    allowed_origins: str = "http://localhost:3000"

    # SQLite
    sqlite_path: str = "~/.agent-harness/projects.db"

    # Background extraction worker count (controls concurrency to LLM API)
    extraction_workers: int = 4

    # Optional env file path (for MCP env isolation)
    mcp_env_file: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def sqlite_path_resolved(self) -> Path:
        return Path(self.sqlite_path).expanduser()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
