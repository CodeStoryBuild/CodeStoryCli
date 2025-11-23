import typer
from loguru import logger

from vibe.pipelines.clean_pipeline import CleanPipeline
from vibe.core.validation import (
    validate_commit_hash,
    validate_ignore_patterns,
    validate_min_size,
)
from vibe.core.logging.utils import time_block
from vibe.context import CleanContext

from .expand import main as expand_main

from functools import partial


def main(
    ctx: typer.Context,
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
    skip_merge: bool | None = typer.Argument(
        False,
        help="Should the clean command skip cleaning merge commits?",
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
    expand_command = partial(expand_main, ctx)
    
    validated_ignore = validate_ignore_patterns(ignore)
    validated_min_size = validate_min_size(min_size)
    validated_start_from = None

    if start_from:
        validated_start_from = validate_commit_hash(start_from)

    global_context = ctx.obj
    clean_context = CleanContext(
        ignore=validated_ignore,
        min_size=validated_min_size,
        start_from=validated_start_from,
        skip_merge=skip_merge,
    )

    logger.info(
        "Clean command started",
        ignore_patterns=validated_ignore,
        min_size=validated_min_size,
        start_from=validated_start_from,
    )

    # Execute cleaning
    with time_block("Clean Runner E2E"):
        runner = CleanPipeline(global_context, clean_context, expand_command)
        success = runner.run()

    if success:
        logger.info("Clean command completed successfully")        
    else:
        logger.error("Clean operation failed")
        raise typer.Exit(1)
