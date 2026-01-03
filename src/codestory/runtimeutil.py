# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

import importlib
import signal
import sys

import typer
from colorama import Fore, Style
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
        logger.info(f"\n{Fore.YELLOW}Operation cancelled by user{Style.RESET_ALL}")
        raise typer.Exit(130)  # Standard exit code for Ctrl+C

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        try:
            version = importlib.metadata.version("codestory")
            typer.echo(f"codestory version {version}")
        except importlib.metadata.PackageNotFoundError:
            typer.echo("codestory version: development")
        raise typer.Exit()


def get_log_dir_callback(value: bool):
    """Show version and exit."""
    if value:
        from codestory.core.logging.logging import LOG_DIR

        typer.echo(f"{str(LOG_DIR)}")
        raise typer.Exit()
