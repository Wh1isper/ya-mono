from __future__ import annotations

from types import SimpleNamespace

import ya_agent_platform.cli as platform_cli
from click.testing import CliRunner

runner = CliRunner()


def test_migrate_command_invokes_upgrade(monkeypatch) -> None:
    revisions: list[str] = []

    monkeypatch.setattr(platform_cli, "_apply_database_migrations", lambda revision="head": revisions.append(revision))

    result = runner.invoke(platform_cli.cli, ["migrate"])

    assert result.exit_code == 0
    assert revisions == ["head"]
    assert "Database upgraded to head." in result.output


def test_serve_runs_auto_migrate_when_database_url_present(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    settings = SimpleNamespace(
        host="127.0.0.1",
        port=9042,
        reload=False,
        auto_migrate=True,
        database_url="postgresql+psycopg://ya_platform:ya_platform@localhost:15433/ya_platform",
    )

    monkeypatch.setattr(platform_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        platform_cli, "_apply_database_migrations", lambda revision="head": calls.append(("migrate", revision))
    )
    monkeypatch.setattr(platform_cli.uvicorn, "run", lambda *args, **kwargs: calls.append(("serve", kwargs)))

    result = runner.invoke(platform_cli.cli, ["serve"])

    assert result.exit_code == 0
    assert calls[0] == ("migrate", "head")
    assert calls[1][0] == "serve"


def test_serve_skips_auto_migrate_when_database_url_missing(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    settings = SimpleNamespace(
        host="127.0.0.1",
        port=9042,
        reload=False,
        auto_migrate=True,
        database_url=None,
    )

    monkeypatch.setattr(platform_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        platform_cli, "_apply_database_migrations", lambda revision="head": calls.append(("migrate", revision))
    )
    monkeypatch.setattr(platform_cli.uvicorn, "run", lambda *args, **kwargs: calls.append(("serve", kwargs)))

    result = runner.invoke(platform_cli.cli, ["serve"])

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
