from __future__ import annotations

from pathlib import Path

import click
import uvicorn
from alembic import command
from alembic.config import Config

from ya_claw.bridge.cli import bridge
from ya_claw.config import ClawSettings, get_settings


class ClawCliApplication:
    def settings(self) -> ClawSettings:
        return get_settings()

    def alembic_config(self) -> Config:
        ini_path = Path(__file__).parent / "alembic.ini"
        return Config(str(ini_path))

    def resolved_database_url(self) -> str:
        settings = self.settings()
        return settings.resolved_database_url

    def upgrade_database(self, revision: str = "head") -> None:
        self.resolved_database_url()
        command.upgrade(self.alembic_config(), revision)

    def downgrade_database(self, revision: str = "-1") -> None:
        self.resolved_database_url()
        command.downgrade(self.alembic_config(), revision)

    def create_revision(self, message: str) -> None:
        self.resolved_database_url()
        command.revision(self.alembic_config(), message=message, autogenerate=True)

    def show_current(self) -> None:
        self.resolved_database_url()
        command.current(self.alembic_config(), verbose=True)

    def show_history(self) -> None:
        self.resolved_database_url()
        command.history(self.alembic_config(), verbose=True)

    def serve(
        self,
        host: str | None,
        port: int | None,
        reload: bool | None,
        migrate: bool | None,
    ) -> None:
        settings = self.settings()

        try:
            settings.require_api_token()
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

        resolved_host = settings.host if host is None else host
        resolved_port = settings.port if port is None else port
        resolved_reload = settings.reload if reload is None else reload
        resolved_migrate = settings.auto_migrate if migrate is None else migrate

        if resolved_migrate:
            self.upgrade_database()
            click.echo("Database migrations applied.")

        uvicorn.run(
            "ya_claw.app:create_app",
            factory=True,
            host=resolved_host,
            port=resolved_port,
            reload=resolved_reload,
        )


cli_application = ClawCliApplication()


@click.group()
def cli() -> None:
    """YA Claw management CLI."""


@cli.command()
@click.option("--host", default=None, help="Bind host for the HTTP server.")
@click.option("--port", default=None, type=int, help="Bind port for the HTTP server.")
@click.option("--reload/--no-reload", default=None, help="Enable or disable code reload.")
@click.option("--migrate/--no-migrate", default=None, help="Run database migrations before starting the server.")
def serve(host: str | None, port: int | None, reload: bool | None, migrate: bool | None) -> None:
    cli_application.serve(host=host, port=port, reload=reload, migrate=migrate)


@cli.group()
def db() -> None:
    """Database migration and management commands."""


@db.command("upgrade")
@click.option("--revision", default="head", help="Target revision (default: head).")
def db_upgrade(revision: str) -> None:
    cli_application.upgrade_database(revision)
    click.echo(f"Database upgraded to {revision}.")


@db.command("downgrade")
@click.option("--revision", default="-1", help="Target revision (default: -1, one step back).")
def db_downgrade(revision: str) -> None:
    cli_application.downgrade_database(revision)
    click.echo(f"Database downgraded to {revision}.")


@db.command("revision")
@click.argument("message")
def db_revision(message: str) -> None:
    cli_application.create_revision(message)
    click.echo(f"Migration generated: {message}")


@db.command("current")
def db_current() -> None:
    cli_application.show_current()


@db.command("history")
def db_history() -> None:
    cli_application.show_history()


cli.add_command(bridge)
