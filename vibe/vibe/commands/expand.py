from typing import Callable

import typer
import inquirer
from rich.console import Console

from vibe.core.expand.service import ExpandService


def main(
    ctx: typer.Context,
    commit_hash: str = typer.Argument(..., help="Commit hash to expand"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically accept rewrite confirmation (non-interactive).",
    ),
):
    """Expand a past commit into smaller logical commits safely."""
    console = Console()
    service = ExpandService(".")

    ok = service.expand_commit(commit_hash, console=console, auto_yes=yes)
    if not ok:
        raise typer.Exit(1)
