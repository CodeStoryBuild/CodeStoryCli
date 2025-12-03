import typer
from colorama import Fore, Style
from loguru import logger

from codestory.context import CommitContext, FixContext, GlobalContext
from codestory.core.exceptions import (
    DetachedHeadError,
    GitError,
    handle_codestory_exception,
)
from codestory.core.git_interface.interface import GitInterface
from codestory.core.logging.utils import time_block
from codestory.core.validation import validate_commit_hash, validate_git_repository


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
        raise DetachedHeadError("Detached HEAD is not supported for codestory fix")

    # Verify commit exists and is on current branch history
    resolved = (
        git_interface.run_git_text_out(["rev-parse", fix_context.commit_hash]) or ""
    ).strip()
    if not resolved:
        raise GitError(f"Commit not found: {fix_context.commit_hash}")

    is_ancestor = git_interface.run_git_text(
        ["merge-base", "--is-ancestor", resolved, head_hash]
    )
    if is_ancestor is None or is_ancestor.returncode != 0:
        raise GitError("The commit must be an ancestor of HEAD (linear history only).")

    # Determine parent commit (base) TODO Test empty tree hash (also this isnt perfect as git moves to sha256)
    parent = (
        git_interface.run_git_text_out(["rev-parse", f"{resolved}^"]) or ""
    ).strip()

    if not parent:
        raise GitError("Fixing the root commit is not supported yet!")

    return parent, resolved, current_branch


@handle_codestory_exception
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
    """Fix a past commit by splitting into smaller logical commits safely, then updating the history with the new commits

    Examples:
        # Fix a specific commit
        codestory fix abc123
    """
    global_context: GlobalContext = ctx.obj
    validate_git_repository(global_context.git_interface)

    validated_hash = validate_commit_hash(commit_hash)

    fix_context = FixContext(validated_hash)

    logger.debug("Fix command started", fix_context=fix_context)

    base_hash, new_hash, base_branch = get_info(
        global_context.git_interface, fix_context
    )

    commit_context = CommitContext(
        target=None,
        message=None,
        relevance_filter_level="none",
        relevance_filter_intent=None,
        secret_scanner_aggression="none",
    )  # TODO add custom fix message

    from codestory.pipelines.commit_init import create_commit_pipeline
    from codestory.pipelines.fix_pipeline import FixPipeline

    commit_pipeline = create_commit_pipeline(
        global_context, commit_context, base_hash, new_hash, "fix"
    )

    # Execute expansion
    with time_block("Fix Pipeline E2E"):
        service = FixPipeline(global_context, fix_context, commit_pipeline)
        final_head = service.run()

    if final_head is not None:
        final_head = final_head.strip()

        # Update the branch reference and sync the working directory
        logger.debug(
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
        logger.warning(f"{Fore.RED}Failed to fix commit{Style.RESET_ALL}")
