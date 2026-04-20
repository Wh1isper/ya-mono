from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClawSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YA_CLAW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "YA Claw"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 9042
    reload: bool = False
    public_base_url: str = "http://127.0.0.1:9042"
    web_dist_dir: Path | None = None
    data_dir: Path = Path("data")
    allow_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"])

    database_url: str | None = None
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_recycle_seconds: int = 3600

    redis_url: str | None = None

    auto_migrate: bool = True


@lru_cache(maxsize=1)
def get_settings() -> ClawSettings:
    return ClawSettings()
