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

from colorama import Fore, Style

from codestory.context import GlobalContext
from codestory.core.exceptions import (
    DetachedHeadError,
    GitError,
)
from codestory.core.git.git_rebaser import GitRebaser
from codestory.core.git.git_sandbox import GitSandbox
from codestory.core.validation import (
    is_root_commit,
    validate_commit_hash,
    validate_no_merge_commits_in_range,
)
from codestory.pipelines.standard_cli_pipeline import StandardCLIPipeline


def get_info(
    global_context: GlobalContext, start_commit_hash: str | None, end_commit_hash: str
):
    # Resolve current branch and head
    if not global_context.current_branch:
        raise DetachedHeadError("Detached HEAD is not supported for codestory fix")

    # Resolve branch tip (use branch instead of ambiguous HEAD)
    branch_head_hash = global_context.git_commands.get_commit_hash(
        global_context.current_branch
    )
    if not branch_head_hash:
        raise GitError(f"Failed to resolve branch: {global_context.current_branch}")

    # Verify end commit exists and is on target branch history
    try:
        end_resolved = global_context.git_commands.get_commit_hash(end_commit_hash)
    except ValueError:
        raise GitError(f"Commit not found: {end_commit_hash}")

    if not global_context.git_commands.is_ancestor(end_resolved, branch_head_hash):
        raise GitError(
            f"The end commit must be an ancestor of the branch: {global_context.current_branch}."
        )

    # Determine base commit (start)
    if start_commit_hash:
        # User provided explicit start commit
        try:
            start_resolved = global_context.git_commands.get_commit_hash(
                start_commit_hash
            )
        except ValueError:
            raise GitError(f"Start commit not found: {start_commit_hash}")

        # Validate that start < end (start is ancestor of end)
        if not global_context.git_commands.is_ancestor(start_resolved, end_resolved):
            raise GitError(
                "Start commit must be an ancestor of end commit (start < end)."
            )

        # Ensure start != end
        if start_resolved == end_resolved:
            raise GitError("Start and end commits cannot be the same.")

        base_hash = start_resolved
    else:
        # Default: use end's parent as start (original behavior)
        if is_root_commit(global_context.git_commands, end_resolved):
            raise GitError("Fixing the root commit is not supported yet!")

        base_hash = global_context.git_commands.try_get_parent_hash(end_resolved)

    # Validate that there are no merge commits in the range to be fixed
    validate_no_merge_commits_in_range(
        global_context.git_commands, base_hash, global_context.current_branch
    )

    return base_hash, end_resolved


def run_fix(
    global_context: GlobalContext,
    commit_hash: str,
    start_commit: str | None,
    message: str | None,
):
    from loguru import logger

    validated_end_hash = validate_commit_hash(
        commit_hash, global_context.git_commands, global_context.current_branch
    )
    validated_start_hash = (
        validate_commit_hash(
            start_commit, global_context.git_commands, global_context.current_branch
        )
        if start_commit
        else None
    )

    base_hash, new_hash = get_info(
        global_context, validated_start_hash, validated_end_hash
    )

    # Create diff context for the fix range
    with GitSandbox.from_context(global_context) as sandbox:
        pipeline = StandardCLIPipeline(
            global_context, allow_filtering=False, source="fix"
        )
        new_commit_hash = pipeline.run(base_hash, new_hash, user_message=message)
        if new_commit_hash:
            rebaser = GitRebaser(global_context.git_commands)
            final_head = rebaser.rebase(
                new_hash, new_commit_hash, global_context.current_branch
            )
            sandbox.sync(final_head)
        else:
            final_head = None

    if final_head is not None:
        # Update the branch reference and sync the working directory
        logger.info(
            "Finalizing branch update: {branch} -> {head}",
            branch=global_context.current_branch,
            head=final_head,
        )

        # Update the reference pointer
        global_context.git_commands.update_ref(
            global_context.current_branch, final_head
        )

        # Sync the working directory to the new head
        global_context.git_commands.read_tree(global_context.current_branch)

        logger.success("Fix command completed successfully")
        return True
    else:
        logger.error(f"{Fore.RED}Failed to fix commit{Style.RESET_ALL}")
        return False
