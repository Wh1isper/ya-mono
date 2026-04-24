from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from ya_claw import config as config_module
from ya_claw.config import ClawSettings
from ya_claw.mcp import ClawMCPConfigResolver


def test_load_runtime_environment_exports_non_prefixed_provider_variables(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_root = tmp_path / "package-root"
    package_root.mkdir(parents=True, exist_ok=True)
    package_env_file = package_root / ".env"
    package_env_file.write_text(
        "YA_CLAW_API_TOKEN=package-token\nGATEWAY_API_KEY=package-key\n",
        encoding="utf-8",
    )

    cwd = tmp_path / "cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    cwd_env_file = cwd / ".env"
    cwd_env_file.write_text(
        "GATEWAY_API_KEY=cwd-key\nGATEWAY_BASE_URL=https://gateway.example.test\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(cwd)
    monkeypatch.setattr(config_module, "_PACKAGE_ROOT", package_root)
    monkeypatch.delenv("YA_CLAW_API_TOKEN", raising=False)
    monkeypatch.delenv("GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("GATEWAY_BASE_URL", raising=False)
    config_module.get_settings.cache_clear()

    loaded = config_module.load_runtime_environment()
    settings = config_module.get_settings()

    assert loaded["YA_CLAW_API_TOKEN"] == "package-token"  # noqa: S105
    assert loaded["GATEWAY_API_KEY"] == "cwd-key"
    assert loaded["GATEWAY_BASE_URL"] == "https://gateway.example.test"
    assert os.environ["GATEWAY_API_KEY"] == "cwd-key"
    assert os.environ["GATEWAY_BASE_URL"] == "https://gateway.example.test"
    assert settings.api_token_value == "package-token"  # noqa: S105

    config_module.get_settings.cache_clear()


def test_load_runtime_environment_preserves_existing_process_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_root = tmp_path / "package-root"
    package_root.mkdir(parents=True, exist_ok=True)
    package_env_file = package_root / ".env"
    package_env_file.write_text(
        "GATEWAY_API_KEY=package-key\n",
        encoding="utf-8",
    )

    cwd = tmp_path / "cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    cwd_env_file = cwd / ".env"
    cwd_env_file.write_text(
        "GATEWAY_API_KEY=cwd-key\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(cwd)
    monkeypatch.setattr(config_module, "_PACKAGE_ROOT", package_root)
    monkeypatch.setenv("GATEWAY_API_KEY", "process-key")
    config_module.get_settings.cache_clear()

    loaded = config_module.load_runtime_environment()

    assert loaded["GATEWAY_API_KEY"] == "cwd-key"
    assert os.environ["GATEWAY_API_KEY"] == "process-key"

    config_module.get_settings.cache_clear()


def test_settings_resolve_global_and_project_mcp_paths(tmp_path: Path) -> None:
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
        project_mcp_config_path=".config/mcp.json",
    )

    assert settings.resolved_mcp_config_file == tmp_path / "mcp.json"
    assert settings.resolved_project_mcp_config_path == Path(".config/mcp.json")


def test_settings_reject_absolute_project_mcp_paths(tmp_path: Path) -> None:
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
        project_mcp_config_path=str((tmp_path / "mcp.json").resolve()),
    )

    with pytest.raises(ValueError, match="relative path"):
        _ = settings.resolved_project_mcp_config_path


def test_mcp_config_resolver_prefers_project_file_over_global_file(tmp_path: Path) -> None:
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
    )
    global_mcp_file = settings.resolved_mcp_config_file
    global_mcp_file.write_text(
        json.dumps({
            "servers": {
                "github": {
                    "transport": "stdio",
                    "command": "npx",
                }
            }
        }),
        encoding="utf-8",
    )
    workspace_root = tmp_path / "workspace" / "repo-a"
    project_mcp_file = workspace_root / ".ya-claw" / "mcp.json"
    project_mcp_file.parent.mkdir(parents=True, exist_ok=True)
    project_mcp_file.write_text(
        json.dumps({
            "servers": {
                "context7": {
                    "transport": "streamable_http",
                    "url": "https://mcp.context7.com/mcp",
                }
            }
        }),
        encoding="utf-8",
    )
    resolver = ClawMCPConfigResolver(settings=settings)

    loaded = resolver.load_for_workspace(workspace_root)

    assert loaded is not None
    assert loaded.scope == "project"
    assert loaded.path == project_mcp_file.resolve()
    assert list(loaded.config.servers) == ["context7"]
