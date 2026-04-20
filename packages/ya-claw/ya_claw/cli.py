from __future__ import annotations

from pathlib import Path

import click
import uvicorn

from ya_claw.bridge.cli import bridge
from ya_claw.config import get_settings, resolve_database_url


@click.group()
def cli() -> None:
    """YA Claw management CLI."""


def _alembic_config():
    from alembic.config import Config

    ini_path = Path(__file__).parent / "alembic.ini"
    return Config(str(ini_path))


def _ensure_database_url() -> str:
    settings = get_settings()
    return resolve_database_url(settings)


def _apply_database_migrations(revision: str = "head") -> None:
    from alembic import command

    _ensure_database_url()
    command.upgrade(_alembic_config(), revision)


@cli.command("serve")
@click.option("--host", default=None, help="Bind host for the HTTP server.")
@click.option("--port", default=None, type=int, help="Bind port for the HTTP server.")
@click.option("--reload/--no-reload", default=None, help="Enable or disable code reload.")
@click.option("--migrate/--no-migrate", default=None, help="Run database migrations before starting the server.")
def serve(host: str | None, port: int | None, reload: bool | None, migrate: bool | None) -> None:
    settings = get_settings()
    resolved_host = host or settings.host
    resolved_port = port or settings.port
    resolved_reload = settings.reload if reload is None else reload
    resolved_migrate = settings.auto_migrate if migrate is None else migrate

    if resolved_migrate:
        _apply_database_migrations()
        click.echo("Database migrations applied.")

    uvicorn.run(
        "ya_claw.app:create_app",
        factory=True,
        host=resolved_host,
        port=resolved_port,
        reload=resolved_reload,
    )


cli.add_command(bridge)


@cli.command("migrate")
@click.option("--revision", default="head", help="Target revision for the migration run.")
def migrate_command(revision: str) -> None:
    _apply_database_migrations(revision)
    click.echo(f"Database upgraded to {revision}.")


@cli.group()
def db() -> None:
    """Database migration and management commands."""


@db.command()
@click.option("--revision", default="head", help="Target revision (default: head).")
def upgrade(revision: str) -> None:
    _apply_database_migrations(revision)
    click.echo(f"Database upgraded to {revision}.")


@db.command()
@click.option("--revision", default="-1", help="Target revision (default: -1, one step back).")
def downgrade(revision: str) -> None:
    from alembic import command

    _ensure_database_url()
    command.downgrade(_alembic_config(), revision)
    click.echo(f"Database downgraded to {revision}.")


@db.command("migrate")
@click.argument("message")
def create_migration(message: str) -> None:
    from alembic import command

    _ensure_database_url()
    command.revision(_alembic_config(), message=message, autogenerate=True)
    click.echo(f"Migration generated: {message}")


@db.command()
def current() -> None:
    from alembic import command

    _ensure_database_url()
    command.current(_alembic_config(), verbose=True)


@db.command()
def history() -> None:
    from alembic import command

    _ensure_database_url()
    command.history(_alembic_config(), verbose=True)
