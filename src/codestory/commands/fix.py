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

from codestory.context import FixContext, GlobalContext
from codestory.core.exceptions import (
    DetachedHeadError,
    GitError,
)
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.logging.utils import time_block
from codestory.core.synthesizer.git_sandbox import GitSandbox
from codestory.core.validation import (
    is_root_commit,
    validate_commit_hash,
    validate_no_merge_commits_in_range,
)
from codestory.pipelines.diff_context import DiffContext
from codestory.pipelines.grouping_context import GroupingConfig, GroupingContext


def get_info(global_context: GlobalContext, fix_context: FixContext):
    # Resolve current branch and head
    current_branch = global_context.current_branch
    if not current_branch:
        raise DetachedHeadError("Detached HEAD is not supported for codestory fix")

    # Resolve branch tip (use branch instead of ambiguous HEAD)
    branch_head_hash = global_context.git_commands.get_commit_hash(current_branch)
    if not branch_head_hash:
        raise GitError(f"Failed to resolve branch: {current_branch}")

    # Verify end commit exists and is on target branch history
    try:
        end_resolved = global_context.git_commands.get_commit_hash(
            fix_context.end_commit_hash
        )
    except ValueError:
        raise GitError(f"Commit not found: {fix_context.end_commit_hash}")

    if not global_context.git_commands.is_ancestor(end_resolved, branch_head_hash):
        raise GitError(
            f"The end commit must be an ancestor of the branch: {current_branch}."
        )

    # Determine base commit (start)
    if fix_context.start_commit_hash:
        # User provided explicit start commit
        try:
            start_resolved = global_context.git_commands.get_commit_hash(
                fix_context.start_commit_hash
            )
        except ValueError:
            raise GitError(f"Start commit not found: {fix_context.start_commit_hash}")

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
        global_context.git_commands, base_hash, current_branch
    )

    return base_hash, end_resolved, current_branch


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

    fix_context = FixContext(
        end_commit_hash=validated_end_hash, start_commit_hash=validated_start_hash
    )

    logger.debug("Fix command started", fix_context=fix_context)

    base_hash, new_hash, base_branch = get_info(global_context, fix_context)

    # Create diff context for the fix range
    with ProgressBarManager.set_pbar(
        description="Analyzing commit changes", silent=global_context.config.silent
    ):
        diff_context = DiffContext(
            global_context.git_commands,
            base_hash,
            new_hash,
            target=None,
            chunking_level=global_context.config.chunking_level,
            fail_on_syntax_errors=False,
        )

    if not diff_context.has_changes():
        logger.info("No changes to process.")
        logger.info(f"{Fore.YELLOW}Is this an empty commit?{Style.RESET_ALL}")
        return False

    # Create grouping context (no filtering for fix - we can't reject changes)
    with ProgressBarManager.set_pbar(
        description="Grouping Changes", silent=global_context.config.silent
    ):
        grouping_config = GroupingConfig(
            fallback_grouping_strategy=global_context.config.fallback_grouping_strategy,
            relevance_filter_level="none",  # No filtering for fix
            secret_scanner_aggression="none",  # No filtering for fix
            batching_strategy=global_context.config.batching_strategy,
            cluster_strictness=global_context.config.cluster_strictness,
            relevance_intent=None,
            guidance_message=message,
            model=global_context.get_model(),
            embedder=global_context.get_embedder(),
        )

        grouping_context = GroupingContext(diff_context, grouping_config)

    # For fix command, we don't allow partial rejection
    # Let user review and optionally modify commit messages
    from codestory.core.user_filter.cmd_user_filter import CMDUserFilter

    filter_ = CMDUserFilter(
        auto_accept=global_context.config.auto_accept,
        ask_for_commit_message=global_context.config.ask_for_commit_message,
        can_partially_reject_changes=False,  # Cannot reject changes in fix
        silent=global_context.config.silent,
        context_manager=(
            diff_context.get_context_manager()
            if global_context.config.display_diff_type == "semantic"
            else None
        ),
    )
    final_groups = filter_.filter(grouping_context.final_logical_groups)

    if not final_groups:
        logger.info("No AI groups proposed; aborting pipeline")
        return False

    from codestory.pipelines.fix_pipeline import FixPipeline
    from codestory.pipelines.rewrite_pipeline import RewritePipeline

    with GitSandbox(global_context) as sandbox:
        rewrite_pipeline = RewritePipeline(global_context.git_commands)

        with time_block("Fix Pipeline E2E"):
            service = FixPipeline(
                global_context,
                fix_context,
                rewrite_pipeline,
                base_hash,
                new_hash,
            )
            final_head = service.run(final_groups)

        if final_head:
            sandbox.sync(final_head)

    if final_head is not None:
        final_head = final_head.strip()

        # Update the branch reference and sync the working directory
        logger.debug(
            "Finalizing update: {branch} -> {head}",
            branch=base_branch,
            head=final_head,
        )

        # Update the reference pointer
        global_context.git_commands.update_ref(base_branch, final_head)

        # Sync the working directory to the new head (use branch name rather than ambiguous HEAD)
        global_context.git_commands.read_tree(base_branch)

        logger.success("Fix command completed successfully")
        return True
    else:
        logger.error(f"{Fore.RED}Failed to fix commit{Style.RESET_ALL}")
        return False
