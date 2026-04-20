from __future__ import annotations

from types import SimpleNamespace

import ya_claw.cli as claw_cli
from click.testing import CliRunner

runner = CliRunner()


def test_migrate_command_invokes_upgrade(monkeypatch) -> None:
    revisions: list[str] = []

    monkeypatch.setattr(claw_cli, "_apply_database_migrations", lambda revision="head": revisions.append(revision))

    result = runner.invoke(claw_cli.cli, ["migrate"])

    assert result.exit_code == 0
    assert revisions == ["head"]
    assert "Database upgraded to head." in result.output


def test_serve_runs_auto_migrate_with_default_sqlite(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, object]] = []
    settings = SimpleNamespace(
        host="127.0.0.1",
        port=9042,
        reload=False,
        auto_migrate=True,
        database_url=None,
        data_dir=tmp_path,
    )

    monkeypatch.setattr(claw_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        claw_cli, "_apply_database_migrations", lambda revision="head": calls.append(("migrate", revision))
    )
    monkeypatch.setattr(claw_cli.uvicorn, "run", lambda *args, **kwargs: calls.append(("serve", kwargs)))

    result = runner.invoke(claw_cli.cli, ["serve"])

    assert result.exit_code == 0
    assert calls[0] == ("migrate", "head")
    assert calls[1][0] == "serve"


def test_serve_skips_auto_migrate_when_disabled(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, object]] = []
    settings = SimpleNamespace(
        host="127.0.0.1",
        port=9042,
        reload=False,
        auto_migrate=True,
        database_url=None,
        data_dir=tmp_path,
    )

    monkeypatch.setattr(claw_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        claw_cli, "_apply_database_migrations", lambda revision="head": calls.append(("migrate", revision))
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
