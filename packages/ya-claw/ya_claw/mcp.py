from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ya_agent_sdk.mcp import MCPConfig, load_mcp_config_file

from ya_claw.config import ClawSettings

_DEFAULT_PROJECT_MCP_CONFIG_PATH = Path(".ya-claw/mcp.json")


@dataclass(frozen=True, slots=True)
class LoadedMCPConfig:
    scope: str
    path: Path
    config: MCPConfig


@dataclass(slots=True)
class _CachedMCPConfig:
    mtime_ns: int
    size: int
    config: MCPConfig


class ClawMCPConfigResolver:
    def __init__(self, *, settings: ClawSettings) -> None:
        self._settings = settings
        self._cache: dict[Path, _CachedMCPConfig] = {}

    def load_for_workspace(self, workspace_root: Path | None = None) -> LoadedMCPConfig | None:
        project_file = self.resolve_project_mcp_config_file(workspace_root)
        if isinstance(project_file, Path) and project_file.exists():
            return LoadedMCPConfig(scope="project", path=project_file, config=self._load_cached(project_file))

        global_file = self._settings.resolved_mcp_config_file
        if global_file.exists():
            return LoadedMCPConfig(scope="global", path=global_file, config=self._load_cached(global_file))

        return None

    def resolve_project_mcp_config_file(self, workspace_root: Path | None) -> Path | None:
        if not isinstance(workspace_root, Path):
            return None
        relative_path = self._settings.resolved_project_mcp_config_path
        if relative_path is None:
            return None
        return (workspace_root / relative_path).resolve()

    def _load_cached(self, file_path: Path) -> MCPConfig:
        stat_result = file_path.stat()
        cached = self._cache.get(file_path)
        if (
            isinstance(cached, _CachedMCPConfig)
            and cached.mtime_ns == stat_result.st_mtime_ns
            and cached.size == stat_result.st_size
        ):
            return cached.config

        loaded = load_mcp_config_file(file_path)
        self._cache[file_path] = _CachedMCPConfig(
            mtime_ns=stat_result.st_mtime_ns,
            size=stat_result.st_size,
            config=loaded,
        )
        return loaded


def default_project_mcp_config_path() -> Path:
    return _DEFAULT_PROJECT_MCP_CONFIG_PATH
