from __future__ import annotations

import click
import uvicorn

from ya_agent_platform.config import get_settings


@click.group()
def cli() -> None:
    """YA Agent Platform management CLI."""


@cli.command("serve")
@click.option("--host", default=None, help="Bind host for the HTTP server.")
@click.option("--port", default=None, type=int, help="Bind port for the HTTP server.")
@click.option("--reload/--no-reload", default=None, help="Enable or disable code reload.")
def serve(host: str | None, port: int | None, reload: bool | None) -> None:
    settings = get_settings()
    resolved_host = host or settings.host
    resolved_port = port or settings.port
    resolved_reload = settings.reload if reload is None else reload

    uvicorn.run(
        "ya_agent_platform.app:create_app",
        factory=True,
        host=resolved_host,
        port=resolved_port,
        reload=resolved_reload,
    )
