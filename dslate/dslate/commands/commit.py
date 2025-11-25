import inquirer
import typer
from loguru import logger

from dslate.context import CommitContext, GlobalContext
from dslate.core.branch_saver.branch_saver import BranchSaver
from dslate.core.commands.git_commands import GitCommands
from dslate.core.exceptions import ValidationError
from dslate.core.logging.utils import time_block
from dslate.core.validation import (
    sanitize_user_input,
    validate_message_length,
    validate_target_path,
)
from dslate.pipelines.commit_init import create_commit_pipeline


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
            logger.info(
                "[yellow]Auto-confirm:[/yellow] Unstaging all changes to proceed."
            )
        else:
            unstage = inquirer.confirm(
                "Staged changes detected. dslate requires a clean staging area. Unstage all changes?",
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
        logger.info(
            f'Untracked files detected within "{target}", temporarily staging changes',
        )

        commands.track_untracked(target)

    return True


def main(
    ctx: typer.Context,
    target: str | None = typer.Argument(
        None, help="Path to file or directory to commit."
    ),
    message: str | None = typer.Argument(None, help="Context or instructions for the AI to generate the commit message"),
) -> None:
    """
    Commits changes with AI-powered messages.

    Examples:
        # Commit all changes interactively
        dslate commit

        # Commit specific directory with message
        dslate commit src/ "Refactor user authentication"
    """

    # Validate inputs
    validated_target = validate_target_path(target)
    validated_message = validate_message_length(message)

    # Sanitize message if provided
    if validated_message:
        validated_message = sanitize_user_input(validated_message)

    global_context: GlobalContext = ctx.obj
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
            global_context, commit_context, base_commit_hash, new_commit_hash
        )

        new_commit_hash = runner.run()

    # Update branch reference
    if new_commit_hash is not None and new_commit_hash != base_commit_hash:
        global_context.git_interface.run_git_binary_out(
            ["update-ref", f"refs/heads/{current_branch}", new_commit_hash]
        )

        logger.info(
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
