from functools import partial

import typer
from loguru import logger

from dslate.context import CleanContext
from dslate.core.logging.utils import time_block
from dslate.core.validation import (
    validate_commit_hash,
    validate_ignore_patterns,
    validate_min_size,
)
from dslate.pipelines.clean_pipeline import CleanPipeline

from .fix import main as fix_main


def main(
    ctx: typer.Context,
    ignore: list[str] | None = typer.Option(
        None,
        "--ignore",
        help="Commit hashes to skip (can be prefixes). Eg --ignore hash1 hash2...",
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
    """Run 'dslate fix' iteratively from HEAD (or start_from) to the start of the repository fixing each commit.

    Examples:
        # Clean all commits with auto-confirmation
        dslate clean --yes

        # Clean starting from a specific commit
        dslate clean abc123 --min-size 5

        # Clean while ignoring certain commits
        dslate clean --ignore def456 --ignore ghi789
    """
    fix_command = partial(fix_main, ctx)

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
        runner = CleanPipeline(global_context, clean_context, fix_command)
        success = runner.run()

    if success:
        logger.info("Clean command completed successfully")
    else:
        logger.error("Clean operation failed")
        raise typer.Exit(1)
