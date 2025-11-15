from typing import Optional, List

import typer
from rich.console import Console
from loguru import logger

from vibe.core.expand.clean_runner import CleanRunner, CleanOptions
from vibe.core.logging.logging import setup_logger


def main(
    ignore: list[str] | None = typer.Option(
        None,
        "--ignore",
        help="Commit hashes to skip (can be prefixes). Use multiple times to specify more.",
    ),
    min_size: int | None = typer.Option(
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
    start_from: str | None = typer.Argument(
        None,
        help="Commit hash (or prefix) to start cleaning from (inclusive). If not provided, starts from HEAD.",
    ),
) -> None:
    """Run 'vibe expand' iteratively from HEAD (or start_from) to the second commit with filtering."""

    console = Console()
    setup_logger("clean", console)

    logger.info(
        "Clean command invoked: ignore={ignore} min_size={min_size} auto_yes={auto} start_from={start_from}",
        ignore=ignore or [],
        min_size=min_size,
        auto=yes,
        start_from=start_from,
    )

    runner = CleanRunner(".")
    ok = runner.run(
        CleanOptions(
            ignore=ignore or [], min_size=min_size, auto_yes=yes, start_from=start_from
        ),
        console=console,
    )
    if not ok:
        raise typer.Exit(1)
