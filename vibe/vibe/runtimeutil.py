import importlib
import sys
import signal

import typer

from loguru import logger


def ensure_utf8_output():
    # force utf-8 encoding
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def setup_signal_handlers():
    """Set up graceful shutdown on Ctrl+C."""

    def signal_handler(sig, frame):
        logger.info("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(130)  # Standard exit code for Ctrl+C

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        try:
            version = importlib.metadata.version("vibe")
            typer.echo(f"vibe version {version}")
        except importlib.metadata.PackageNotFoundError:
            typer.echo("vibe version: development")
        raise typer.Exit()
