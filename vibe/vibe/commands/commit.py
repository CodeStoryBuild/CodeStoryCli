import typer
import inquirer
from loguru import logger

from vibe.context import GlobalContext, CommitContext
from vibe.pipelines.commit_init import create_commit_pipeline
from vibe.core.validation import (
    sanitize_user_input,
    validate_message_length,
    validate_target_path,
)
from vibe.core.exceptions import ValidationError
from vibe.core.logging.utils import time_block
from vibe.core.branch_saver.branch_saver import BranchSaver
from vibe.core.commands.git_commands import GitCommands



def verify_repo(
    commands: GitCommands, target: str, auto_yes: bool = False
) -> bool:
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
                "Staged changes detected, you must unstage all changes. Do you accept?",
                default=False,
            )

        if unstage:
            commands.reset()
        else:
            logger.info(
                "[yellow]Cannot proceed without unstaging changes, exiting.[/yellow]"
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
    target: str = typer.Argument(".", help="The target path to check for changes."),
    message: str | None = typer.Argument(None, help="Message to the AI model"),
) -> None:
    """
    Commits changes with AI-powered messages.

    Examples:
        # Commit all changes interactively
        vibe commit

        # Commit specific directory with message
        vibe commit src/ "Refactor user authentication"

        # Auto-accept all suggestions
        vibe commit --yes

        # Use specific model
        vibe --model openai:gpt-4 commit
    """

    # Validate inputs
    validated_target = validate_target_path(target)
    validated_message = validate_message_length(message)

    # Sanitize message if provided
    if validated_message:
        validated_message = sanitize_user_input(validated_message)


    global_context : GlobalContext = ctx.obj
    commit_context = CommitContext(validated_target, validated_message)

    logger.debug("[green] Verifying Repo State... [/green]")
    # verify repo state specifically for commit command
    if not verify_repo(global_context.git_commands, str(commit_context.target), global_context.auto_accept):
        raise ValidationError("Cannot proceed without unstaging changes, exiting.")
    
    # next we create our base/new commits + backup branch for later
    branch_saver = BranchSaver(global_context.git_interface)

    logger.debug("[green] Creating backup of working state... [/green]")
    base_commit_hash, new_commit_hash, base_branch = (
        branch_saver.save_working_state()
    )

    with time_block("Commit Command E2E"):
        runner = create_commit_pipeline(
            global_context, commit_context, base_commit_hash, new_commit_hash, base_branch, branch_saver 
        )

        result = runner.run()

    if not result:
        logger.info("[yellow]No commits were created[/yellow]")
    else:
        logger.info(
            "Commit command completed successfully",
        )
