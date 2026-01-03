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


import inquirer
import typer
from loguru import logger

from codestory.context import CommitContext, GlobalContext
from codestory.core.branch_saver.branch_saver import BranchSaver
from codestory.core.commands.git_commands import GitCommands
from codestory.core.exceptions import ValidationError
from codestory.core.logging.utils import time_block
from codestory.core.validation import (
    sanitize_user_input,
    validate_git_repository,
    validate_message_length,
    validate_target_path,
)
from codestory.pipelines.commit_init import create_commit_pipeline


def _help_callback(ctx: typer.Context, param, value: bool):
    # Typer/Click help callback: show help and exit when --help is provided
    if not value or ctx.resilient_parsing:
        return
    typer.echo(ctx.get_help())
    raise typer.Exit()


def verify_repo(commands: GitCommands, target: str, auto_yes: bool = False) -> bool:
    # Step -1: ensure we're inside a git repository
    if not commands.is_git_repo():
        raise RuntimeError(
            "Not a git repository (or any of the parent directories). Please run this command inside a Git repo."
        )

    # Step 0: clean working area
    if commands.need_reset():
        if auto_yes:
            unstage = True
            logger.debug(
                "[yellow]Auto-confirm:[/yellow] Unstaging all changes to proceed."
            )
        else:
            unstage = inquirer.confirm(
                "Staged changes detected. codestory requires a clean staging area. Unstage all changes?",
                default=False,
            )

        if unstage:
            commands.reset()
        else:
            logger.info(
                "[yellow]Operation cancelled. Please unstage changes to proceed.[/yellow]"
            )
            return False

    if commands.need_track_untracked(target):
        logger.debug(
            f'Untracked files detected within "{target}", temporarily staging changes',
        )

        commands.track_untracked(target)

    return True


def main(
    ctx: typer.Context,
    help: bool = typer.Option(
        False,
        "--help",
        callback=_help_callback,
        is_eager=True,
        help="Show this message and exit.",
    ),
    target: str | None = typer.Argument(
        None, help="Path to file or directory to commit."
    ),
    message: str | None = typer.Option(
        None, "-m", help="Context or instructions for the AI to generate the commit message"
    ),
) -> None:
    """
    Commits current working directory changes into smaller logical commits.
    (If you wish to modify existing history, use codestory fix or codestory clean)

    Examples:
        # Commit all changes interactively
        codestory commit

        # Commit specific directory with message
        codestory commit src/  -m "Make 2 commits, one for refactor, one for feature A..."
    """
    global_context: GlobalContext = ctx.obj
    validate_git_repository(global_context.git_interface)

    # Validate inputs
    validated_target = validate_target_path(target)
    validated_message = validate_message_length(message)

    # Sanitize message if provided
    if validated_message:
        validated_message = sanitize_user_input(validated_message)

    commit_context = CommitContext(validated_target, validated_message)

    logger.debug("[green] Checking repository status... [/green]")
    # verify repo state specifically for commit command
    if not verify_repo(
        global_context.git_commands,
        str(commit_context.target),
        global_context.auto_accept,
    ):
        raise ValidationError("Cannot proceed without unstaging changes, exiting.")

    # next we create our base/new commits + backup branch for later
    branch_saver = BranchSaver(global_context.git_interface)

    logger.debug("[green] Backing up current state... [/green]")
    base_commit_hash, new_commit_hash, current_branch = (
        branch_saver.save_working_state()
    )

    with time_block("Commit Command E2E"):
        runner = create_commit_pipeline(
            global_context, commit_context, base_commit_hash, new_commit_hash, "commit"
        )

        new_commit_hash = runner.run()

    # Update branch reference
    if new_commit_hash is not None and new_commit_hash != base_commit_hash:
        global_context.git_interface.run_git_binary_out(
            ["update-ref", f"refs/heads/{current_branch}", new_commit_hash]
        )

        logger.debug(
            "Branch updated: branch={branch} new_head={head}",
            branch=current_branch,
            head=new_commit_hash,
        )

        # Sync the Git Index (Staging Area) to the new HEAD.
        # This makes the files you just committed show up as "Clean".
        # Files you skipped (outside target) will show up as "Modified" (Unstaged).
        # We use 'read-tree' WITHOUT '-u' so it doesn't touch physical files.
        global_context.git_interface.run_git_binary_out(["read-tree", "HEAD"])

        logger.info(
            "Commit command completed successfully",
        )
    else:
        logger.info("[yellow]No commits were created[/yellow]")
        raise typer.Exit(1)
