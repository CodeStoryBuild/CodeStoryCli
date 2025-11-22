import typer
from loguru import logger
from rich.console import Console

from vibe.pipelines.expand_pipeline import ExpandPipeline
from vibe.pipelines.commit_init import create_commit_pipeline
from vibe.core.git_interface.interface import GitInterface
from vibe.core.validation import validate_commit_hash
from vibe.context import GlobalContext, ExpandContext
from vibe.core.commands.git_const import EMPTYTREEHASH


def get_info(git_interface : GitInterface, expand_context: ExpandContext):
    
    # Resolve current branch and head
    current_branch = git_interface.run_git_text(["rev-parse", "--abbrev-ref", "HEAD"]).strip() or ""
    head_hash = git_interface.run_git_text(["rev-parse", "HEAD"]).strip() or ""

    if not current_branch:
        logger.error("Detached HEAD is not supported for expand")
        return False

    # Verify commit exists and is on current branch history
    resolved = git_interface.run_git_text(["rev-parse", expand_context.commit_hash]).strip() or ""
    if not resolved:
        logger.error("Commit not found: {commit}", commit=expand_context.commit_hash)
        return False

    if not git_interface.run_git_text(["merge-base", "--is-ancestor", resolved, head_hash]):
        logger.error(
            "Commit {commit} is not an ancestor of HEAD {head}; only linear expansions are supported",
            commit=resolved[:7],
            head=resolved[:7],
        )
        return False

    # Determine parent commit (base) TODO Test empty tree hash (also this isnt perfect as git moves to sha256)
    parent = git_interface.run_git_text(["rev-parse", f"{resolved}^"]).strip() or EMPTYTREEHASH

    return parent, resolved, current_branch




def main(
    ctx: typer.Context,
    commit_hash: str = typer.Argument(..., help="Commit hash to expand"),
) -> None:
    """Expand a past commit into smaller logical commits safely.

    Examples:
        # Expand a specific commit
        vibe expand abc123

        # Expand with auto-confirmation
        vibe expand abc123 --yes

        # Use specific model
        vibe --model anthropic:claude-3-5-sonnet-20241022 expand abc123
    """
    validated_hash = validate_commit_hash(commit_hash)

    global_context : GlobalContext = ctx.obj
    expand_context = ExpandContext(validated_hash)

    logger.info("Expand command started", expand_context=expand_context)

    base_hash, new_hash, base_branch = get_info(global_context.git_interface, expand_context)
    commit_pipeline = create_commit_pipeline(global_context, base_hash, new_hash, base_branch)

    # Execute expansion
    service = ExpandPipeline(".", model=model)
    success = service.run(validated_hash, console=console, auto_yes=auto_yes)

    if not success:
        console.print("[red]Failed to expand commit[/red]")
        logger.error("Expand operation failed")
        raise typer.Exit(1)

    logger.info("Expand command completed successfully")
    console.print("[green]Commit expanded successfully![/green]")
