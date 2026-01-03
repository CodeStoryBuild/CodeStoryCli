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

from codestory.context import CleanContext, GlobalContext
from codestory.core.exceptions import GitError
from codestory.core.logging.utils import time_block
from codestory.core.validation import (
    validate_commit_hash,
    validate_ignore_patterns,
    validate_min_size,
    validate_no_merge_commits_in_range,
)


def run_clean(
    global_context: GlobalContext,
    ignore: list[str] | None,
    min_size: int | None,
    start_from: str | None,
):
    from loguru import logger

    validated_ignore = validate_ignore_patterns(ignore)
    validated_min_size = validate_min_size(min_size)
    validated_start_from = None

    if start_from:
        validated_start_from = validate_commit_hash(start_from)

        # Verify the commit exists
        resolved_commit = global_context.git_interface.run_git_text_out(
            ["rev-parse", validated_start_from]
        )
        if not resolved_commit or not resolved_commit.strip():
            raise GitError(f"Commit not found: {validated_start_from}")

        validated_start_from = resolved_commit.strip()

        # Verify the commit is an ancestor of HEAD (exists in current branch history)
        head_hash = global_context.git_interface.run_git_text_out(["rev-parse", "HEAD"])
        if not head_hash or not head_hash.strip():
            raise GitError("Failed to resolve HEAD")

        head_hash = head_hash.strip()

        is_ancestor = global_context.git_interface.run_git_text(
            ["merge-base", "--is-ancestor", validated_start_from, head_hash]
        )
        if is_ancestor is None or is_ancestor.returncode != 0:
            raise GitError(
                f"Commit {validated_start_from[:7]} is not in the current branch history. "
                "The start_from commit must be an ancestor of HEAD."
            )

        # Validate that there are no merge commits in the range to be cleaned
        validate_no_merge_commits_in_range(
            global_context.git_interface, validated_start_from, "HEAD"
        )

    clean_context = CleanContext(
        ignore=validated_ignore,
        min_size=validated_min_size,
        start_from=validated_start_from,
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
        runner = CleanPipeline(global_context, clean_context)
        success = runner.run()

    if success:
        logger.success("Clean command completed successfully")
    else:
        logger.error("Clean operation failed")
