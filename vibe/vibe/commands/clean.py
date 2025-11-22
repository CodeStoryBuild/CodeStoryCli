import typer
from loguru import logger
from rich.console import Console

from vibe.core.exceptions import GitError, ValidationError, VibeError
from vibe.pipelines.clean_pipeline import CleanOptions, CleanPipeline
from vibe.core.logging.logging import setup_logger
from vibe.core.validation import (
    validate_commit_hash,
    validate_git_repository,
    validate_ignore_patterns,
    validate_min_size,
)


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
    start_from: str | None = typer.Argument(
        None,
        help="Commit hash (or prefix) to start cleaning from (inclusive). If not provided, starts from HEAD.",
    ),
) -> None:
    """Run 'vibe expand' iteratively from HEAD (or start_from) to the second commit with filtering.

    Examples:
        # Clean all commits with auto-confirmation
        vibe clean --yes

        # Clean starting from a specific commit
        vibe clean abc123 --min-size 5

        # Clean while ignoring certain commits
        vibe clean --ignore def456 --ignore ghi789
    """
    console = Console()

    # Validate inputs
    validate_git_repository(".")
    validated_ignore = validate_ignore_patterns(ignore)
    validated_min_size = validate_min_size(min_size)
    validated_start_from = None

    if start_from:
        validated_start_from = validate_commit_hash(start_from)

    # Setup logging
    setup_logger("clean", console)

    logger.info(
        "Clean command started",
        ignore_patterns=validated_ignore,
        min_size=validated_min_size,
        auto_yes=yes,
        start_from=validated_start_from,
    )

    # Execute cleaning
    runner = CleanPipeline(".")
    success = runner.run(
        CleanOptions(
            ignore=validated_ignore,
            min_size=validated_min_size,
            auto_yes=yes,
            start_from=validated_start_from,
        ),
        console=console,
    )

    if not success:
        console.print("[red]Clean operation failed[/red]")
        logger.error("Clean operation failed")
        raise typer.Exit(1)

    logger.info("Clean command completed successfully")
    console.print("[green]Repository cleaned successfully![/green]")
