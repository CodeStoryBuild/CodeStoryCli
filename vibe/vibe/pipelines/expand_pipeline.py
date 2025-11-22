import os
import shutil
from tempfile import TemporaryDirectory

from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from vibe.context import GlobalContext, ExpandContext
from vibe.pipelines.commit_pipeline import CommitPipeline
from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface


def _run_git(
    git: SubprocessGitInterface, args: list[str], cwd: str | None = None
) -> str | None:
    return git.run_git_text(args, cwd=cwd)





def _short(hash_: str) -> str:
    return (hash_ or "")[:7]


def _cleanup_worktree(git: SubprocessGitInterface, path: str):
    try:
        _run_git(git, ["worktree", "remove", "--force", path])
    finally:
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)


class ExpandPipeline:
    """Core orchestration for expanding a commit safely using temporary worktrees."""
    def __init__(self, global_context : GlobalContext, expand_context : ExpandContext, commit_pipeline : CommitPipeline):
        self.global_context = global_context
        self.expand_context = expand_context
        self.commit_pipeline = commit_pipeline

    def run(self) -> bool:

        # Use TemporaryDirectory context managers for automatic cleanup
        with TemporaryDirectory(prefix="vibe-expand-wt1-") as wt1_dir:
            rewrite_branch: str | None = None
            temp_branch = f"vibe-expand-{_short(self.commit_pipeline.branch_to_update or "tmp")}"
            wt1_created = False

            try:
                logger.info(
                    "Creating temporary worktree at {parent}", parent=_short(self.commit_pipeline.base_commit_hash)
                )
                _run_git(self.git, ["worktree", "add", "--detach", wt1_dir, self.commit_pipeline.base_commit_hash])
                wt1_created = True
                wt1_git = SubprocessGitInterface(wt1_dir)

                wt1_git.run_git_text(["checkout", "-b", temp_branch])

                # Run expand pipeline on diff(parent, resolved)
                logger.info(
                    "Analyzing and proposing groups for commit {commit}",
                    commit=_short(self.commit_pipeline.base_commit_hash),
                )
                pipeline = create_expand_pipeline(
                    wt1_dir,
                    base_commit_hash=parent,
                    new_commit_hash=resolved,
                    console=console,
                    model=self.model,
                )
                plan = pipeline.run(target=".", auto_yes=auto_yes)
                if plan:
                    new_base = (_run_git(wt1_git, ["rev-parse", "HEAD"]) or "").strip()
                    logger.info("Created new base at {base}", base=_short(new_base))

                    # Prepare rebase of upstream commits onto the new base in a separate worktree
                    with TemporaryDirectory(prefix="vibe-expand-wt2-") as wt2_dir:
                        wt2_created = False
                        try:
                            rewrite_branch = f"vibe-expand-rewrite-{_short(resolved)}"
                            logger.info("Preparing rebase in isolated worktree")
                            _run_git(
                                self.git,
                                [
                                    "worktree",
                                    "add",
                                    "-b",
                                    rewrite_branch,
                                    wt2_dir,
                                    head_hash,
                                ],
                            )
                            wt2_created = True
                            wt2_git = SubprocessGitInterface(wt2_dir)

                            # Rebase: move commits after resolved onto new_base
                            # git rebase --onto <new_base> <resolved> <rewrite_branch>
                            rebase_ok = (
                                _run_git(
                                    wt2_git,
                                    [
                                        "rebase",
                                        "--onto",
                                        new_base,
                                        resolved,
                                        rewrite_branch,
                                    ],
                                )
                                is not None
                            )
                            if not rebase_ok:
                                # Try to abort if needed
                                _run_git(wt2_git, ["rebase", "--abort"])
                                logger.error("Rebase failed during expansion")
                                return False

                            new_head = (
                                _run_git(wt2_git, ["rev-parse", rewrite_branch]) or ""
                            ).strip()

                            # Update original branch ref and working tree
                            if (
                                _run_git(
                                    self.git,
                                    [
                                        "update-ref",
                                        f"refs/heads/{current_branch}",
                                        new_head,
                                    ],
                                )
                                is None
                            ):
                                logger.error(
                                    "Failed to update branch ref for {branch}",
                                    branch=current_branch,
                                )
                                return False

                            # If on that branch, sync working tree
                            _run_git(self.git, ["reset", "--hard", new_head])
                            logger.info(
                                "Commit expansion successful for {commit}",
                                commit=_short(resolved),
                            )
                            return True

                        finally:
                            # Clean up git worktree (if it was created)
                            if wt2_created:
                                _cleanup_worktree(self.git, wt2_dir)
                            # Delete temporary rewrite branch if it exists
                            if rewrite_branch:
                                _run_git(self.git, ["branch", "-D", rewrite_branch])
            finally:
                # Clean up git worktree (if it was created)
                if wt1_created:
                    _cleanup_worktree(self.git, wt1_dir)
                # Delete temp expand branch (if it exists)
                _run_git(self.git, ["branch", "-D", temp_branch])

        return False
