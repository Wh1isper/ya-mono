from __future__ import annotations

import os
from pathlib import Path

from ya_claw import config as config_module


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
