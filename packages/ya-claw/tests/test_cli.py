from __future__ import annotations

import secrets

import ya_claw.cli as claw_cli
from click.testing import CliRunner
from ya_claw.config import ClawSettings

runner = CliRunner()
TEST_API_TOKEN = secrets.token_hex(16)


def test_db_upgrade_invokes_upgrade(monkeypatch) -> None:
    revisions: list[str] = []

    monkeypatch.setattr(
        claw_cli.cli_application, "upgrade_database", lambda revision="head": revisions.append(revision)
    )

    result = runner.invoke(claw_cli.cli, ["db", "upgrade"])

    assert result.exit_code == 0
    assert revisions == ["head"]
    assert "Database upgraded to head." in result.output


def test_serve_runs_auto_migrate_with_default_sqlite(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, object]] = []
    settings = ClawSettings(
        host="127.0.0.1",
        port=9042,
        reload=False,
        auto_migrate=True,
        api_token=TEST_API_TOKEN,
        database_url=None,
        data_dir=tmp_path,
        workspace_root=tmp_path / "workspace",
    )

    monkeypatch.setattr(claw_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        claw_cli.cli_application,
        "upgrade_database",
        lambda revision="head": calls.append(("migrate", revision)),
    )
    monkeypatch.setattr(claw_cli.uvicorn, "run", lambda *args, **kwargs: calls.append(("serve", kwargs)))

    result = runner.invoke(claw_cli.cli, ["serve"])

    assert result.exit_code == 0
    assert calls[0] == ("migrate", "head")
    assert calls[1][0] == "serve"


def test_serve_requires_api_token(monkeypatch, tmp_path) -> None:
    settings = ClawSettings(
        host="127.0.0.1",
        port=9042,
        reload=False,
        auto_migrate=True,
        api_token=None,
        database_url=None,
        data_dir=tmp_path,
        workspace_root=tmp_path / "workspace",
    )

    monkeypatch.setattr(claw_cli, "get_settings", lambda: settings)

    result = runner.invoke(claw_cli.cli, ["serve"])

    assert result.exit_code == 1
    assert "YA_CLAW_API_TOKEN must be configured before starting YA Claw." in result.output


def test_serve_skips_auto_migrate_when_disabled(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, object]] = []
    settings = ClawSettings(
        host="127.0.0.1",
        port=9042,
        reload=False,
        auto_migrate=True,
        api_token=TEST_API_TOKEN,
        database_url=None,
        data_dir=tmp_path,
        workspace_root=tmp_path / "workspace",
    )

    monkeypatch.setattr(claw_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        claw_cli.cli_application,
        "upgrade_database",
        lambda revision="head": calls.append(("migrate", revision)),
    )
    monkeypatch.setattr(claw_cli.uvicorn, "run", lambda *args, **kwargs: calls.append(("serve", kwargs)))

    result = runner.invoke(claw_cli.cli, ["serve", "--no-migrate"])

    assert result.exit_code == 0
    assert calls == [
        (
            "serve",
            {
                "factory": True,
                "host": "127.0.0.1",
                "port": 9042,
                "reload": False,
            },
        )
    ]


def test_bridge_ls_command() -> None:
    result = runner.invoke(claw_cli.cli, ["bridge", "ls"])

    assert result.exit_code == 0
    assert "No bridge adapters registered yet." in result.output


def test_bridge_run_command() -> None:
    result = runner.invoke(claw_cli.cli, ["bridge", "run", "lark"])

    assert result.exit_code == 0
    assert "Bridge adapter run requested: lark" in result.output


def test_bridge_serve_command() -> None:
    result = runner.invoke(claw_cli.cli, ["bridge", "serve", "lark"])

    assert result.exit_code == 0
    assert "Bridge adapter service requested: lark" in result.output
