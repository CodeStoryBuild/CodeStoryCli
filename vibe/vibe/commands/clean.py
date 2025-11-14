from typing import Optional, List

import typer
from rich.console import Console
from loguru import logger

from vibe.core.expand.clean_runner import CleanRunner, CleanOptions
from vibe.core.logging.logging import setup_logger


def main(
    ignore: List[str] = typer.Option(
        None,
        "--ignore",
        help="Commit hashes to skip (can be prefixes). Use multiple times to specify more.",
    ),
    min_size: Optional[int] = typer.Option(
        None,
        "--min-size",
        help="Skip commits with fewer than this many line changes (additions + deletions).",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically confirm rewrites without prompting.",
    ),
):
    """Run 'vibe expand' iteratively from HEAD to the second commit with filtering."""

    console = Console()
    setup_logger("clean", console)

    logger.info(
        "Clean command invoked: ignore={ignore} min_size={min_size} auto_yes={auto}",
        ignore=ignore or [],
        min_size=min_size,
        auto=yes,
    )

    runner = CleanRunner(".")
    ok = runner.run(
        CleanOptions(ignore=ignore or [], min_size=min_size, auto_yes=yes),
        console=console,
    )
    if not ok:
        raise typer.Exit(1)
