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

from codestory.context import GlobalContext
from codestory.core.exceptions import GitError
from codestory.core.git.git_sandbox import GitSandbox
from codestory.core.logging.utils import time_block
from codestory.core.validation import (
    is_root_commit,
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
    end_at: str | None = None,
    unpushed: bool = False,
) -> bool:
    from loguru import logger

    from codestory.core.exceptions import ValidationError

    if unpushed and (start_from or end_at):
        raise ValidationError(
            "The --unpushed flag cannot be used with --start or --end flags."
        )

    validated_ignore = validate_ignore_patterns(ignore)
    validated_min_size = validate_min_size(min_size)
    validated_start_from = None
    validated_end_at = None

    # Resolve Branch Head
    branch_head_hash = global_context.git_commands.get_commit_hash(
        global_context.current_branch
    )

    # 1. Validate End At (if provided)
    if end_at:
        validated_end_at = validate_commit_hash(
            end_at, global_context.git_commands, global_context.current_branch
        )
        try:
            validated_end_at = global_context.git_commands.get_commit_hash(
                validated_end_at
            )
        except ValueError:
            raise GitError(f"End commit not found: {validated_end_at}")

        # Verify end_at is in history of HEAD
        if (
            validated_end_at != branch_head_hash
            and not global_context.git_commands.is_ancestor(
                validated_end_at, branch_head_hash
            )
        ):
            raise GitError(
                f"End commit {validated_end_at[:7]} is not in the target branch history ({global_context.current_branch})."
            )
    else:
        validated_end_at = branch_head_hash

    # 2. Validate Start From (if provided)
    if start_from:
        validated_start_from = validate_commit_hash(
            start_from, global_context.git_commands, global_context.current_branch
        )
        try:
            validated_start_from = global_context.git_commands.get_commit_hash(
                validated_start_from
            )
        except ValueError:
            raise GitError(f"Start commit not found: {validated_start_from}")

        # Verify start < end
        if (
            validated_start_from != validated_end_at
            and not global_context.git_commands.is_ancestor(
                validated_start_from, validated_end_at
            )
        ):
            raise GitError(
                f"Start commit {validated_start_from[:7]} is not an ancestor of end commit {validated_end_at[:7]}."
            )

        # 3. Validate No Merges in Range
        # start_from is INCLUSIVE. To validate it, we check from its parent.
        if is_root_commit(global_context.git_commands, validated_start_from):
            raise GitError(
                "Cleaning starting from the root commit is not supported yet!"
            )

        start_parent = global_context.git_commands.try_get_parent_hash(
            validated_start_from
        )
        validate_no_merge_commits_in_range(
            global_context.git_commands,
            start_parent,
            validated_end_at,
        )

    # Execute cleaning
    from codestory.pipelines.clean_pipeline import CleanPipeline

    with GitSandbox.from_context(global_context) as sandbox:
        with time_block("Clean Runner E2E"):
            runner = CleanPipeline(
                global_context,
                validated_start_from,
                validated_end_at,
                validated_ignore,
                validated_min_size,
                unpushed,
            )
            final_head = runner.run()

        if final_head:
            sandbox.sync(final_head)

    if final_head:
        # Update references
        # If we stopped at end_at, we might need to rebase downstream or update HEAD
        # The pipeline handles downstream rebasing if end_at != HEAD.
        # So we just update the branch pointer to the final result of the pipeline.
        logger.info(
            "Finalizing branch update: {branch} -> {head}",
            branch=global_context.current_branch,
            head=final_head,
        )

        global_context.git_commands.update_ref(
            global_context.current_branch, final_head
        )
        global_context.git_commands.read_tree(global_context.current_branch)

        logger.success("Clean command completed successfully")
        return True
    else:
        logger.error("Clean operation failed")
        return False
