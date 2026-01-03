import typer
from loguru import logger

from dslate.context import CommitContext, FixContext, GlobalContext
from dslate.core.exceptions import DetachedHeadError, GitError
from dslate.core.git_interface.interface import GitInterface
from dslate.core.logging.utils import time_block
from dslate.core.validation import validate_commit_hash, validate_git_repository
from dslate.pipelines.commit_init import create_commit_pipeline
from dslate.pipelines.fix_pipeline import FixPipeline


def _help_callback(ctx: typer.Context, param, value: bool):
    if not value or ctx.resilient_parsing:
        return
    typer.echo(ctx.get_help())
    raise typer.Exit()


def get_info(git_interface: GitInterface, fix_context: FixContext):
    # Resolve current branch and head
    current_branch = (
        git_interface.run_git_text_out(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        or ""
    )
    head_hash = git_interface.run_git_text_out(["rev-parse", "HEAD"]).strip() or ""

    if not current_branch:
        raise DetachedHeadError("Detached HEAD is not supported for dslate fix")

    # Verify commit exists and is on current branch history
    resolved = (
        git_interface.run_git_text_out(["rev-parse", fix_context.commit_hash]).strip()
        or ""
    )
    if not resolved:
        raise GitError(f"Commit not found: {fix_context.commit_hash}")

    if (
        git_interface.run_git_text(
            ["merge-base", "--is-ancestor", resolved, head_hash]
        ).returncode
        != 0
    ):
        raise GitError(
            f"The commit must be an ancestor of HEAD (linear history only)."
        )

    # Determine parent commit (base) TODO Test empty tree hash (also this isnt perfect as git moves to sha256)
    parent = git_interface.run_git_text_out(["rev-parse", f"{resolved}^"])

    if not parent:
        raise GitError("Fixing the root commit is not supported yet!")

    parent = parent.strip()

    return parent, resolved, current_branch


def main(
    ctx: typer.Context,
    help: bool = typer.Option(
        False,
        "--help",
        callback=_help_callback,
        is_eager=True,
        help="Show this message and exit.",
    ),
    commit_hash: str = typer.Argument(..., help="Hash of the commit to split or fix"),
) -> None:
    """Fix a past commit by splitting into smaller logical commits safely.

    Examples:
        # Fix a specific commit
        dslate fix abc123
    """
    global_context: GlobalContext = ctx.obj
    validate_git_repository(global_context.git_interface)
    
    validated_hash = validate_commit_hash(commit_hash)

    fix_context = FixContext(validated_hash)

    logger.info("Fix command started", fix_context=fix_context)

    base_hash, new_hash, base_branch = get_info(
        global_context.git_interface, fix_context
    )

    commit_context = CommitContext(
        target=None, message=None
    )  # TODO add custom fix message
    commit_pipeline = create_commit_pipeline(
        global_context, commit_context, base_hash, new_hash
    )

    # Execute expansion
    with time_block("Fix Pipeline E2E"):
        service = FixPipeline(global_context, fix_context, commit_pipeline)
        final_head = service.run()

    if final_head is not None:
        final_head = final_head.strip()

        # Update the branch reference and sync the working directory
        logger.info(
            "Finalizing update: {branch} -> {head}",
            branch=base_branch,
            head=final_head,
        )

        # Update the reference pointer
        global_context.git_interface.run_git_text_out(
            ["update-ref", f"refs/heads/{base_branch}", final_head]
        )

        # Sync the working directory to the new head
        global_context.git_interface.run_git_text_out(["read-tree", "HEAD"])
        logger.info("Fix command completed successfully")

    else:
        logger.error("Fix operation failed")
        logger.warning("[red]Failed to fix commit[/red]")
        raise typer.Exit(1)
