from __future__ import annotations

import os
import socket
from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import dotenv_values, load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DATABASE_FILENAME = "ya_claw.sqlite3"
_DEFAULT_DATA_DIR = Path("~/.ya-claw/data")
_DEFAULT_WORKSPACE_ROOT = Path("~/.ya-claw/workspace")
_DEFAULT_RUN_STORE_DIRNAME = "run-store"
_DEFAULT_WORKSPACE_DOCKER_IMAGE = "ghcr.io/wh1isper/ya-claw-workspace:latest"


def _default_instance_id() -> str:
    hostname = socket.gethostname().split(".", 1)[0] or "host"
    return f"{hostname}-{os.getpid()}-{uuid4().hex[:8]}"


def load_runtime_environment() -> dict[str, str]:
    package_env_file = (_PACKAGE_ROOT / ".env").expanduser()
    cwd_env_file = Path(".env").expanduser()

    merged: dict[str, str] = {}
    for env_file in (package_env_file, cwd_env_file):
        if env_file.exists():
            merged.update({
                key: value
                for key, value in dotenv_values(env_file).items()
                if isinstance(key, str) and isinstance(value, str)
            })

    for env_file in (cwd_env_file, package_env_file):
        if env_file.exists():
            load_dotenv(env_file, override=False, encoding="utf-8")

    return merged


class ClawSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YA_CLAW_",
        env_file=(_PACKAGE_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "YA Claw"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 9042
    reload: bool = False
    public_base_url: str = "http://127.0.0.1:9042"
    instance_id: str = Field(default_factory=_default_instance_id)
    web_dist_dir: Path | None = None
    api_token: SecretStr | None = None
    data_dir: Path = Field(default_factory=lambda: _DEFAULT_DATA_DIR)
    workspace_root: Path = Field(default_factory=lambda: _DEFAULT_WORKSPACE_ROOT)
    allow_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"])

    database_url: str | None = None
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_recycle_seconds: int = 3600

    workspace_provider_backend: Literal["local", "docker"] = "docker"
    workspace_provider_docker_image: str = _DEFAULT_WORKSPACE_DOCKER_IMAGE
    workspace_provider_docker_uid: int | None = None
    workspace_provider_docker_gid: int | None = None
    default_profile: str = "default"
    profile_seed_file: Path | None = None
    auto_seed_profiles: bool = False
    mcp_config_file: Path | None = None
    project_mcp_config_path: str = ".ya-claw/mcp.json"
    execution_model: str | None = None
    execution_model_settings_preset: str | None = None
    execution_model_config_preset: str | None = None
    execution_system_prompt: str | None = None
    execution_context_window: int = 200_000

    auto_migrate: bool = True

    @property
    def runtime_root(self) -> Path:
        return self.data_dir.expanduser().parent

    @property
    def runtime_data_dir(self) -> Path:
        return self.data_dir.expanduser()

    @property
    def resolved_workspace_root(self) -> Path:
        return self.workspace_root.expanduser()

    @property
    def resolved_profile_seed_file(self) -> Path | None:
        if self.profile_seed_file is None:
            return None
        return self.profile_seed_file.expanduser()

    @property
    def resolved_mcp_config_file(self) -> Path:
        if self.mcp_config_file is not None:
            return self.mcp_config_file.expanduser()
        return self.runtime_root / "mcp.json"

    @property
    def resolved_project_mcp_config_path(self) -> Path | None:
        normalized_value = self.project_mcp_config_path.strip()
        if normalized_value == "":
            return None
        resolved_path = Path(normalized_value)
        if resolved_path.is_absolute():
            raise ValueError("YA_CLAW_PROJECT_MCP_CONFIG_PATH must be a relative path inside each workspace.")
        return resolved_path

    @property
    def run_store_dir(self) -> Path:
        return self.runtime_data_dir / _DEFAULT_RUN_STORE_DIRNAME

    @property
    def resolved_workspace_provider_docker_uid(self) -> int:
        if isinstance(self.workspace_provider_docker_uid, int):
            return self.workspace_provider_docker_uid
        return os.getuid()

    @property
    def resolved_workspace_provider_docker_gid(self) -> int:
        if isinstance(self.workspace_provider_docker_gid, int):
            return self.workspace_provider_docker_gid
        return os.getgid()

    @property
    def api_token_value(self) -> str | None:
        if self.api_token is None:
            return None

        normalized_value = self.api_token.get_secret_value().strip()
        return normalized_value or None

    def require_api_token(self) -> str:
        api_token = self.api_token_value
        if api_token is None:
            raise RuntimeError("YA_CLAW_API_TOKEN must be configured before starting YA Claw.")
        return api_token

    @property
    def database_path(self) -> Path:
        return self.runtime_root / _DEFAULT_DATABASE_FILENAME

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url

        return f"sqlite+aiosqlite:///{self.database_path.resolve()}"

    def ensure_runtime_directories(self) -> None:
        self.runtime_data_dir.mkdir(parents=True, exist_ok=True)
        self.run_store_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_workspace_root.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> ClawSettings:
    load_runtime_environment()
    return ClawSettings()
