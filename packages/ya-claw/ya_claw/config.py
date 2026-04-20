from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DATABASE_FILENAME = "ya_claw.sqlite3"
_DEFAULT_DATA_DIR = Path("~/.ya-claw/data")
_DEFAULT_WORKSPACE_ROOT = Path("~/.ya-claw/workspace")
_DEFAULT_SESSION_STORE_DIRNAME = "session-store"


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
    def session_store_dir(self) -> Path:
        return self.runtime_data_dir / _DEFAULT_SESSION_STORE_DIRNAME

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
        self.session_store_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_workspace_root.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> ClawSettings:
    return ClawSettings()
