from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from ya_claw import config as config_module
from ya_claw.bridge import BridgeAdapterType, BridgeDispatchMode
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


def test_settings_use_official_workspace_image_by_default(monkeypatch) -> None:
    monkeypatch.delenv("YA_CLAW_WORKSPACE_PROVIDER_DOCKER_IMAGE", raising=False)
    settings = ClawSettings(api_token="test-token", _env_file=None)  # noqa: S106

    assert settings.workspace_provider_docker_image == "ghcr.io/wh1isper/ya-claw-workspace:latest"


def test_settings_default_workspace_docker_identity_uses_process_uid_gid(monkeypatch) -> None:
    monkeypatch.delenv("YA_CLAW_WORKSPACE_PROVIDER_DOCKER_UID", raising=False)
    monkeypatch.delenv("YA_CLAW_WORKSPACE_PROVIDER_DOCKER_GID", raising=False)
    with patch.object(os, "getuid", return_value=1234), patch.object(os, "getgid", return_value=2345):
        settings = ClawSettings(api_token="test-token", _env_file=None)  # noqa: S106
        assert settings.resolved_workspace_provider_docker_uid == 1234
        assert settings.resolved_workspace_provider_docker_gid == 2345


def test_settings_workspace_docker_identity_can_be_configured() -> None:
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        workspace_provider_docker_uid=3456,
        workspace_provider_docker_gid=4567,
        _env_file=None,
    )

    assert settings.resolved_workspace_provider_docker_uid == 3456
    assert settings.resolved_workspace_provider_docker_gid == 4567


def test_settings_resolves_bridge_and_lark_cli_environment(monkeypatch) -> None:
    monkeypatch.delenv("LARK_APP_ID", raising=False)
    monkeypatch.delenv("LARK_APP_SECRET", raising=False)
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        bridge_enabled_adapters="lark",
        bridge_lark_app_id="cli_test",
        bridge_lark_app_secret="secret-value",  # noqa: S106
        bridge_lark_default_profile="lark-profile",
        _env_file=None,
    )

    assert settings.bridge_dispatch_mode == BridgeDispatchMode.EMBEDDED
    assert settings.resolved_bridge_enabled_adapters == {BridgeAdapterType.LARK}
    assert settings.resolved_bridge_lark_event_types == [
        "im.chat.member.bot.added_v1",
        "im.chat.member.user.added_v1",
        "im.message.receive_v1",
        "drive.notice.comment_add_v1",
    ]
    assert settings.resolved_bridge_lark_profile == "lark-profile"
    assert settings.resolved_lark_cli_environment == {
        "LARK_APP_ID": "cli_test",
        "LARK_APP_SECRET": "secret-value",
    }


def test_settings_lark_cli_environment_prefers_process_environment(monkeypatch) -> None:
    monkeypatch.setenv("LARK_APP_ID", "process-cli")
    monkeypatch.setenv("LARK_APP_SECRET", "process-secret")
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        bridge_lark_app_id="settings-cli",
        bridge_lark_app_secret="settings-secret",  # noqa: S106
        _env_file=None,
    )

    assert settings.resolved_lark_cli_environment == {
        "LARK_APP_ID": "process-cli",
        "LARK_APP_SECRET": "process-secret",
    }


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
