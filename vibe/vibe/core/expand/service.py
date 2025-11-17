import os
import shutil
from tempfile import TemporaryDirectory
from typing import Optional, Callable

from rich.console import Console
from loguru import logger

from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface
from vibe.core.context.expand_init import create_expand_pipeline


def _run_git(
    git: SubprocessGitInterface, args: list[str], cwd: Optional[str] = None
) -> Optional[str]:
    return git.run_git_text(args, cwd=cwd)


def _is_ancestor(git: SubprocessGitInterface, commit: str, ref: str) -> bool:
    # Returns True if commit is ancestor of ref
    # Success: empty stdout, exit 0 => run_git_text returns "" (not None)
    return _run_git(git, ["merge-base", "--is-ancestor", commit, ref]) is not None


def _short(hash_: str) -> str:
    return (hash_ or "")[:7]


def _cleanup_worktree(git: SubprocessGitInterface, path: str):
    try:
        _run_git(git, ["worktree", "remove", "--force", path])
    finally:
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)


class ExpandService:
    """Core orchestration for expanding a commit safely using temporary worktrees."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
        self.git = SubprocessGitInterface(repo_path)

    def expand_commit(self, commit_hash: str, console: Console, auto_yes: bool) -> bool:
        # Ensure we're in a git repo
        if not _run_git(self.git, ["rev-parse", "--is-inside-work-tree"]):
            logger.error("Not a git repository")
            return False

        # Resolve current branch and head
        current_branch = (
            _run_git(self.git, ["rev-parse", "--abbrev-ref", "HEAD"]) or ""
        ).strip()
        head_hash = (_run_git(self.git, ["rev-parse", "HEAD"]) or "").strip()

        if not current_branch:
            logger.error("Detached HEAD is not supported for expand")
            return False

        # Verify commit exists and is on current branch history
        resolved = (_run_git(self.git, ["rev-parse", commit_hash]) or "").strip()
        if not resolved:
            logger.error("Commit not found: {commit}", commit=commit_hash)
            return False

        if not _is_ancestor(self.git, resolved, head_hash):
            logger.error(
                "Commit {commit} is not an ancestor of HEAD {head}; only linear expansions are supported",
                commit=_short(resolved),
                head=_short(head_hash),
            )
            return False

        # Determine parent commit (base)
        parent = _run_git(self.git, ["rev-parse", f"{resolved}^"])
        if parent is None:
            logger.error("Expanding the root commit is not yet supported")
            return False
        parent = parent.strip()

        # Use TemporaryDirectory context managers for automatic cleanup
        with TemporaryDirectory(prefix="vibe-expand-wt1-") as wt1_dir:
            rewrite_branch: Optional[str] = None
            temp_branch = f"vibe-expand-{_short(resolved)}"
            wt1_created = False

            try:
                logger.info(
                    "Creating temporary worktree at {parent}", parent=_short(parent)
                )
                _run_git(self.git, ["worktree", "add", "--detach", wt1_dir, parent])
                wt1_created = True
                wt1_git = SubprocessGitInterface(wt1_dir)

                _run_git(wt1_git, ["checkout", "-b", temp_branch])

                # Run expand pipeline on diff(parent, resolved)
                logger.info(
                    "Analyzing and proposing groups for commit {commit}",
                    commit=_short(resolved),
                )
                pipeline = create_expand_pipeline(
                    wt1_dir,
                    base_commit_hash=parent,
                    new_commit_hash=resolved,
                    console=console,
                )
                plan = pipeline.run(target=".", auto_yes=auto_yes)
                if not plan:
                    logger.warning("Expansion cancelled; no changes applied")
                    return False

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
