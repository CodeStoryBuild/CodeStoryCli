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
from codestory.core.synthesizer.git_sandbox import GitSandbox


def run_clean(
    global_context: GlobalContext,
    ignore: list[str] | None,
    min_size: int | None,
    start_from: str | None,
) -> bool:
    from loguru import logger

    validated_ignore = validate_ignore_patterns(ignore)
    validated_min_size = validate_min_size(min_size)
    validated_start_from = None

    if start_from:
        validated_start_from = validate_commit_hash(
            start_from, global_context.git_commands, global_context.current_branch
        )

        # Verify the commit exists
        try:
            validated_start_from = global_context.git_commands.get_commit_hash(
                validated_start_from
            )
        except ValueError:
            raise GitError(f"Commit not found: {validated_start_from}")

        # Verify the commit is an ancestor of the branch tip (exists in target branch history)
        branch_head_hash = global_context.git_commands.get_commit_hash(
            global_context.current_branch
        )

        if not global_context.git_commands.is_ancestor(
            validated_start_from, branch_head_hash
        ):
            raise GitError(
                f"Commit {validated_start_from[:7]} is not in the target branch history. "
                f"The start_from commit must be an ancestor of {global_context.current_branch}."
            )

        # Validate that there are no merge commits in the range to be cleaned
        validate_no_merge_commits_in_range(
            global_context.git_commands,
            validated_start_from,
            global_context.current_branch,
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

    with GitSandbox(global_context) as sandbox:
        with time_block("Clean Runner E2E"):
            runner = CleanPipeline(global_context, clean_context)
            final_head = runner.run() # Now returns the hash string
        
        if final_head:
            sandbox.sync(final_head)

    if final_head:
        # Update references
        target_ref = global_context.current_branch
        global_context.git_commands.update_ref(target_ref, final_head)
        
        if global_context.current_branch:
             global_context.git_commands.read_tree(target_ref)
        
        logger.success("Clean command completed successfully")
        return True
    else:
        logger.error("Clean operation failed")
        return False