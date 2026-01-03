from typing import Callable

import typer
from rich.console import Console

from vibe.core.expand.service import ExpandService


def main(commit_hash: str = typer.Argument(..., help="Commit hash to expand")):
    """Expand a past commit into smaller logical commits safely."""
    console = Console()
    service = ExpandService(".")

    def confirm(prompt: str) -> bool:
        console.rule("[bold green]Rewrite confirmation")
        return typer.confirm(prompt, default=True)

    ok = service.expand_commit(commit_hash, console=console, confirm_rewrite=confirm)
    if not ok:
        raise typer.Exit(1)
