"""
-----------------------------------------------------------------------------
/*
 * Copyright (C) 2025 CodeStory
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; Version 2.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, you can contact us at support@codestory.build
 */
-----------------------------------------------------------------------------
"""

from functools import partial

import typer
from loguru import logger

from codestory.context import CleanContext
from codestory.core.exceptions import handle_codestory_exception
from codestory.core.logging.utils import time_block
from codestory.core.validation import (
    validate_commit_hash,
    validate_git_repository,
    validate_ignore_patterns,
    validate_min_size,
)

from .fix import main as fix_main


def _help_callback(ctx: typer.Context, param, value: bool):
    if not value or ctx.resilient_parsing:
        return
    typer.echo(ctx.get_help())
    raise typer.Exit()


@handle_codestory_exception
def main(
    ctx: typer.Context,
    help: bool = typer.Option(
        False,
        "--help",
        callback=_help_callback,
        is_eager=True,
        help="Show this message and exit.",
    ),
    ignore: list[str] | None = typer.Option(
        None,
        "--ignore",
        help="Commit hashes or prefixes to ignore.",
    ),
    min_size: int | None = typer.Option(
        None,
        "--min-size",
        help="Minimum change size (lines) to process.",
    ),
    start_from: str | None = typer.Argument(
        None,
        help="Starting commit hash or prefix (inclusive). Defaults to HEAD.",
    ),
    skip_merge: bool | None = typer.Argument(
        False,
        help="Skip merge commits during cleaning.",
    ),
) -> None:
    """Run 'codestory fix' iteratively from HEAD (or start_from) to the start of the repository fixing each commit.

    Examples:
        # Clean all commits with auto-confirmation
        codestory clean --yes

        # Clean starting from a specific commit
        codestory clean abc123 --min-size 5

        # Clean while ignoring certain commits
        codestory clean --ignore def456 --ignore ghi789
    """
    global_context = ctx.obj
    validate_git_repository(global_context.git_interface)
    fix_command = partial(fix_main, ctx)

    validated_ignore = validate_ignore_patterns(ignore)
    validated_min_size = validate_min_size(min_size)
    validated_start_from = None

    if start_from:
        validated_start_from = validate_commit_hash(start_from)

    clean_context = CleanContext(
        ignore=validated_ignore,
        min_size=validated_min_size,
        start_from=validated_start_from,
        skip_merge=skip_merge,
    )

    logger.debug(
        "Clean command started",
        ignore_patterns=validated_ignore,
        min_size=validated_min_size,
        start_from=validated_start_from,
    )

    # Execute cleaning
    from codestory.pipelines.clean_pipeline import CleanPipeline

    with time_block("Clean Runner E2E"):
        runner = CleanPipeline(global_context, clean_context, fix_command)
        success = runner.run()

    if success:
        logger.info("Clean command completed successfully")
    else:
        logger.error("Clean operation failed")
