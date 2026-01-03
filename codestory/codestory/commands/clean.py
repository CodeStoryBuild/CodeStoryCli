# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of codestory.
#
# codestory is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
# -----------------------------------------------------------------------------


from functools import partial

from codestory.core.exceptions import handle_codestory_exception
import typer
from loguru import logger

from codestory.context import CleanContext
from codestory.core.logging.utils import time_block
from codestory.core.validation import (
    validate_commit_hash,
    validate_git_repository,
    validate_ignore_patterns,
    validate_min_size,
)
from codestory.pipelines.clean_pipeline import CleanPipeline

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
    with time_block("Clean Runner E2E"):
        runner = CleanPipeline(global_context, clean_context, fix_command)
        success = runner.run()
    
    if success:
        logger.info("Clean command completed successfully")
    else:
        logger.error("Clean operation failed")
