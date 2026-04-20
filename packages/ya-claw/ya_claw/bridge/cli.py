from __future__ import annotations

import click


@click.group()
def bridge() -> None:
    """Bridge management commands."""


@bridge.command("ls")
def list_bridges() -> None:
    click.echo("No bridge adapters registered yet.")


@bridge.command("run")
@click.argument("adapter")
def run_bridge(adapter: str) -> None:
    click.echo(f"Bridge adapter run requested: {adapter}")


@bridge.command("serve")
@click.argument("adapter")
def serve_bridge(adapter: str) -> None:
    click.echo(f"Bridge adapter service requested: {adapter}")
