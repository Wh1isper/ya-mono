from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YA_PLATFORM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "YA Agent Platform"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 9042
    reload: bool = False
    public_base_url: str = "http://127.0.0.1:9042"
    admin_mount_path: str = "/admin"
    chat_mount_path: str = "/chat"
    bridge_mount_path: str = "/bridges"
    web_dist_dir: Path | None = None
    allow_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"])


@lru_cache(maxsize=1)
def get_settings() -> PlatformSettings:
    return PlatformSettings()
