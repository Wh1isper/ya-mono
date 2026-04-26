from __future__ import annotations

import asyncio
from pathlib import Path

import click
import uvicorn
from alembic import command
from alembic.config import Config
from loguru import logger

from ya_claw.bridge.cli import bridge
from ya_claw.config import ClawSettings, get_settings
from ya_claw.db.engine import create_engine, create_session_factory
from ya_claw.execution.profile import ProfileResolver
from ya_claw.logging import configure_claw_logging


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

    def seed_profiles(
        self,
        *,
        prune_missing: bool,
        migrate: bool,
        seed_file: str | None,
    ) -> list[str]:
        settings = self.settings()
        effective_settings = settings.model_copy(
            update={"profile_seed_file": Path(seed_file).expanduser()} if isinstance(seed_file, str) else {}
        )
        resolved_seed_file = effective_settings.resolved_profile_seed_file
        if resolved_seed_file is None or not resolved_seed_file.exists():
            raise click.ClickException("Profile seed file is not configured or does not exist.")

        if migrate:
            self.upgrade_database()

        async def _run() -> list[str]:
            engine = create_engine(effective_settings.resolved_database_url)
            session_factory = create_session_factory(engine)
            try:
                resolver = ProfileResolver(settings=effective_settings, session_factory=session_factory)
                return await resolver.seed_profiles(prune_missing=prune_missing)
            finally:
                await engine.dispose()

        return asyncio.run(_run())

    def serve(
        self,
        host: str | None,
        port: int | None,
        reload: bool | None,
        migrate: bool | None,
    ) -> None:
        settings = self.settings()
        configure_claw_logging(settings.log_level)
        logger.info("YA Claw serve requested")

        try:
            settings.require_api_token()
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

        resolved_host = settings.host if host is None else host
        resolved_port = settings.port if port is None else port
        resolved_reload = settings.reload if reload is None else reload
        resolved_migrate = settings.auto_migrate if migrate is None else migrate

        logger.info(
            "Resolved serve options host={} port={} reload={} migrate={} log_level={} shutdown_timeout_seconds={}",
            resolved_host,
            resolved_port,
            resolved_reload,
            resolved_migrate,
            settings.log_level,
            settings.shutdown_timeout_seconds,
        )

        if resolved_migrate:
            logger.info("Applying database migrations before serving")
            self.upgrade_database()
            click.echo("Database migrations applied.")

        logger.info("Starting uvicorn server")
        uvicorn.run(
            "ya_claw.app:create_app",
            factory=True,
            host=resolved_host,
            port=resolved_port,
            reload=resolved_reload,
            log_level=settings.log_level.lower(),
            timeout_graceful_shutdown=settings.shutdown_timeout_seconds,
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


@cli.command()
@click.option("--host", default=None, help="Bind host for the HTTP server.")
@click.option("--port", default=None, type=int, help="Bind port for the HTTP server.")
def start(host: str | None, port: int | None) -> None:
    """Production startup: migrate, seed, then serve."""
    settings = cli_application.settings()

    try:
        settings.require_api_token()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    if settings.auto_migrate:
        cli_application.upgrade_database()
        click.echo("Database migrations applied.")

    if settings.auto_seed_profiles:
        seeded_names = cli_application.seed_profiles(prune_missing=False, migrate=False, seed_file=None)
        if seeded_names:
            click.echo(f"Seeded {len(seeded_names)} profile(s): {', '.join(seeded_names)}")

    cli_application.serve(host=host, port=port, reload=False, migrate=False)


@cli.group()
def db() -> None:
    """Database migration and management commands."""


@cli.group()
def profiles() -> None:
    """Profile management commands."""


@profiles.command("seed")
@click.option(
    "--prune-missing/--keep-missing",
    default=False,
    help="Delete seeded DB profiles that are missing from the seed file.",
)
@click.option("--migrate/--no-migrate", default=True, help="Run database migrations before seeding profiles.")
@click.option("--seed-file", default=None, help="Override the configured profile seed YAML path.")
def profiles_seed(prune_missing: bool, migrate: bool, seed_file: str | None) -> None:
    seeded_names = cli_application.seed_profiles(
        prune_missing=prune_missing,
        migrate=migrate,
        seed_file=seed_file,
    )
    click.echo(f"Seeded {len(seeded_names)} profile(s): {', '.join(seeded_names)}")


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
