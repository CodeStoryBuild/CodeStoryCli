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

from typing import Literal

from colorama import Fore, Style

from codestory.context import CommitContext, GlobalContext
from codestory.core.exceptions import (
    GitError,
)
from codestory.core.git_commands.git_commands import GitCommands
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.synthesizer.git_sandbox import GitSandbox
from codestory.core.temp_commiter.temp_commiter import TempCommitCreator
from codestory.core.validation import (
    sanitize_user_input,
    validate_message_length,
    validate_target_path,
)
from codestory.pipelines.diff_context import DiffContext
from codestory.pipelines.grouping_context import GroupingConfig, GroupingContext


def verify_repo_state(commands: GitCommands, target: list[str] | None) -> bool:
    from loguru import logger

    logger.debug(f"{Fore.GREEN} Checking repository status... {Style.RESET_ALL}")

    if commands.is_bare_repository():
        raise GitError("The 'commit' command cannot be run on a bare repository.")

    # always track all files that are not explicitly excluded using gitignore or target path selector
    # this is a very explicit design choice to simplify (remove) the concept of staged/unstaged changes
    if commands.need_track_untracked(target):
        target_desc = f'"{target}"' if target else "all files"
        logger.debug(
            f"Untracked files detected within {target_desc}, starting to track them.",
        )

        commands.track_untracked(target)


def run_commit(
    global_context: GlobalContext,
    target: str | list[str] | None,
    message: str | None,
    secret_scanner_aggression: Literal["safe", "standard", "strict", "none"],
    relevance_filter_level: Literal["safe", "standard", "strict", "none"],
    intent: str | None,
    fail_on_syntax_errors: bool,
) -> bool:
    from loguru import logger

    # Validate inputs
    validated_target = validate_target_path(target)

    if message:
        validated_message = validate_message_length(message)
        validated_message = sanitize_user_input(validated_message)
    else:
        validated_message = None

    if intent:
        validated_intent = validate_message_length(intent)
        validated_intent = sanitize_user_input(validated_intent)
    else:
        validated_intent = None

    # verify repo state specifically for commit command
    verify_repo_state(
        global_context.git_commands,
        validated_target,
    )

    commit_context = CommitContext(
        target=validated_target,
        message=validated_message,
        relevance_filter_level=relevance_filter_level,
        relevance_filter_intent=intent,
        secret_scanner_aggression=secret_scanner_aggression,
        fail_on_syntax_errors=fail_on_syntax_errors,
    )

    # check if branch is empty
    current_branch = global_context.current_branch
    try:
        head_commit = global_context.git_commands.get_commit_hash(current_branch)
    except ValueError:
        head_commit = ""

    if not head_commit:
        logger.debug(
            f"Branch '{current_branch}' is empty: creating initial empty commit"
        )
        # Create an empty tree
        empty_tree_hash = global_context.git_commands.write_tree()
        if not empty_tree_hash:
            raise GitError("Failed to create empty tree")

        # Create initial commit
        head_commit = global_context.git_commands.commit_tree(
            empty_tree_hash, [], "Initial commit"
        )
        if not head_commit:
            raise GitError("Failed to create initial commit")

        # Update branch to point to initial commit
        global_context.git_commands.update_ref(current_branch, head_commit)

    # Create a dangling commit for the current working tree state.
    # This also runs in a sandbox to avoid polluting the main object directory.
    with GitSandbox.from_context(global_context) as tempcommit_sandbox:
        new_working_commit_hash = TempCommitCreator.create_reference_commit(
            global_context.git_commands,
            commit_context.target,
            head_commit,
        )

        # Sync the temp commit to the real object store so the rewrite pipeline can see it
        tempcommit_sandbox.sync(new_working_commit_hash)

    # now, create the diff context
    with ProgressBarManager.set_pbar(
        description="Initialize diff context", silent=global_context.config.silent
    ):
        diff_context = DiffContext(
            global_context.git_commands,
            head_commit,
            new_working_commit_hash,
            validated_target,
            global_context.config.chunking_level,
            fail_on_syntax_errors,
        )

    if not diff_context.has_changes():
        logger.info("No changes to process.")
        logger.info(
            f"{Fore.YELLOW}If you meant to modify existing git history, please use codestory fix or codestory clean commands{Style.RESET_ALL}"
        )
        return False

    # now, calculate groups
    with ProgressBarManager.set_pbar(
        description="Grouping Changes", silent=global_context.config.silent
    ):
        grouping_config = GroupingConfig(
            fallback_grouping_strategy=global_context.config.fallback_grouping_strategy,
            relevance_filter_level=global_context.config.relevance_filter_level,
            secret_scanner_aggression=global_context.config.secret_scanner_aggression,
            batching_strategy=global_context.config.batching_strategy,
            cluster_strictness=global_context.config.cluster_strictness,
            relevance_intent=validated_intent,
            guidance_message=validated_message,
            model=global_context.get_model(),
            embedder=global_context.get_embedder(),
        )

        grouping_context = GroupingContext(diff_context, grouping_config)

    # now, let the user filter out what they want
    from codestory.core.user_filter.cmd_user_filter import CMDUserFilter

    filter_ = CMDUserFilter(
        auto_accept=global_context.config.auto_accept,
        ask_for_commit_message=global_context.config.ask_for_commit_message,
        can_partially_reject_changes=True,
        silent=global_context.config.silent,
        context_manager=(
            diff_context.get_context_manager()
            if global_context.config.display_diff_type == "semantic"
            else None
        ),
    )
    final_groups = filter_.filter(grouping_context.final_logical_groups)

    if not final_groups:
        # User rejected all groups or no groups were created
        return False

    from codestory.pipelines.rewrite_pipeline import RewritePipeline

    with GitSandbox.from_context(global_context) as sandbox:
        pipeline = RewritePipeline(global_context.git_commands)

        new_commit_hash = pipeline.run(head_commit, final_groups)

        if new_commit_hash and new_commit_hash != head_commit:
            sandbox.sync(new_commit_hash)

    # now that we rewrote our changes into a clean link of commits, update the current branch to reference this
    if new_commit_hash is not None and new_commit_hash != head_commit:
        current_branch = global_context.current_branch

        global_context.git_commands.update_ref(current_branch, new_commit_hash)

        logger.debug(
            "Branch updated: branch={branch} new_head={head}",
            branch=current_branch,
            head=new_commit_hash,
        )

        # Sync the Git Index (Staging Area) to the new branch tip.
        # This makes the files you just committed show up as "Clean".
        # Files you skipped (outside target) will show up as "Modified" (Unstaged).
        # We use 'read-tree' WITHOUT '-u' so it doesn't touch physical files.
        global_context.git_commands.read_tree(current_branch)

        logger.success(
            "Commit command completed successfully",
        )
        return True
    else:
        logger.error(f"{Fore.YELLOW}No commits were created{Style.RESET_ALL}")
        return False
