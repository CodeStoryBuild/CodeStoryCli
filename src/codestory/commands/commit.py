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
    GitError,
)
from codestory.core.git.git_commands import GitCommands
from codestory.core.git.git_sandbox import GitSandbox
from codestory.core.git.git_temp_commiter import TempCommitCreator
from codestory.core.validation import (
    sanitize_user_input,
    validate_message_length,
)
from codestory.pipelines.standard_cli_pipeline import StandardCLIPipeline


def verify_repo_state(commands: GitCommands) -> bool:
    from loguru import logger

    logger.debug(f"{Fore.GREEN} Checking repository status... {Style.RESET_ALL}")

    if commands.is_bare_repository():
        raise GitError("The 'commit' command cannot be run on a bare repository.")


def run_commit(
    global_context: GlobalContext,
    target: str | list[str] | None,
    message: str | None,
    intent: str | None,
    fail_on_syntax_errors: bool,
) -> bool:
    from loguru import logger

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
    )

    # check if branch is empty
    try:
        head_commit = global_context.git_commands.get_commit_hash(
            global_context.current_branch
        )
    except ValueError:
        head_commit = ""

    if not head_commit:
        logger.debug(
            f"Branch '{global_context.current_branch}' is empty: creating initial empty commit"
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
        global_context.git_commands.update_ref(
            global_context.current_branch, head_commit
        )

    # Create a dangling commit for the current working tree state.
    # This also runs in a sandbox to avoid polluting the main object directory.
    with GitSandbox.from_context(global_context) as sandbox:
        new_working_commit_hash = TempCommitCreator.create_reference_commit(
            global_context.git_commands,
            target,
            head_commit,
        )

        pipeline = StandardCLIPipeline(
            global_context,
            allow_filtering=True,
            source="commit",
            fail_on_syntax_errors=fail_on_syntax_errors,
        )
        new_commit_hash = pipeline.run(
            head_commit,
            new_working_commit_hash,
            target,
            user_message=message,
            user_intent=intent,
        )
        if new_commit_hash is not None:
            sandbox.sync(new_commit_hash)

    # now that we rewrote our changes into a clean link of commits, update the current branch to reference this
    if new_commit_hash is not None:
        logger.info(
            "Finalizing branch update: {branch} -> {head}",
            branch=global_context.current_branch,
            head=new_commit_hash,
        )

        global_context.git_commands.update_ref(
            global_context.current_branch, new_commit_hash
        )
        global_context.git_commands.read_tree(global_context.current_branch)

        logger.success(
            "Commit command completed successfully",
        )
        return True
    else:
        logger.error(f"{Fore.YELLOW}No commits were created{Style.RESET_ALL}")
        return False
