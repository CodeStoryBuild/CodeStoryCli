import os
import shutil
import tempfile
from typing import Optional, Callable

from rich.console import Console

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

    def expand_commit(
        self,
        commit_hash: str,
        console: Console,
        auto_yes: bool
    ) -> bool:
        # Ensure we're in a git repo
        if not _run_git(self.git, ["rev-parse", "--is-inside-work-tree"]):
            console.print("[red]Not a git repository.[/red]")
            return False

        # Resolve current branch and head
        current_branch = (
            _run_git(self.git, ["rev-parse", "--abbrev-ref", "HEAD"]) or ""
        ).strip()
        head_hash = (_run_git(self.git, ["rev-parse", "HEAD"]) or "").strip()

        if not current_branch:
            console.print("[red]Detached HEAD is not supported for expand.[/red]")
            return False

        # Verify commit exists and is on current branch history
        resolved = (_run_git(self.git, ["rev-parse", commit_hash]) or "").strip()
        if not resolved:
            console.print(f"[red]Commit '{commit_hash}' not found.[/red]")
            return False

        if not _is_ancestor(self.git, resolved, head_hash):
            console.print(
                f"[red]Commit {_short(resolved)} is not an ancestor of the current branch HEAD; only linear expansions are supported.[/red]"
            )
            return False

        # Determine parent commit (base)
        parent = _run_git(self.git, ["rev-parse", f"{resolved}^"])
        if parent is None:
            console.print(
                "[red]Expanding the root commit is not yet supported in this version.[/red]"
            )
            return False
        parent = parent.strip()

        # Create worktree at parent commit and a temp branch
        wt1_dir = tempfile.mkdtemp(prefix="vibe-expand-wt1-")
        rewrite_branch: Optional[str] = None
        try:
            console.print(
                f"[green]Creating temporary worktree at { _short(parent) }...[/green]"
            )
            _run_git(self.git, ["worktree", "add", "--detach", wt1_dir, parent])
            wt1_git = SubprocessGitInterface(wt1_dir)

            temp_branch = f"vibe-expand-{_short(resolved)}"
            _run_git(wt1_git, ["checkout", "-b", temp_branch])

            # Run expand pipeline on diff(parent, resolved)
            console.print("[green]Analyzing and proposing groups...[/green]")
            pipeline = create_expand_pipeline(
                wt1_dir,
                base_commit_hash=parent,
                new_commit_hash=resolved,
                console=console,
            )
            plan = pipeline.run(target=".", auto_yes=auto_yes)
            if not plan:
                console.print(
                    "[yellow]Expansion cancelled; no changes applied.[/yellow]"
                )
                return False

            new_base = (_run_git(wt1_git, ["rev-parse", "HEAD"]) or "").strip()
            console.print(f"[green]Created new base at {_short(new_base)}.[/green]")

            # Prepare rebase of upstream commits onto the new base in a separate worktree
            wt2_dir = tempfile.mkdtemp(prefix="vibe-expand-wt2-")
            try:
                rewrite_branch = f"vibe-expand-rewrite-{_short(resolved)}"
                console.print("[green]Preparing rebase in isolated worktree...[/green]")
                _run_git(
                    self.git,
                    ["worktree", "add", "-b", rewrite_branch, wt2_dir, head_hash],
                )
                wt2_git = SubprocessGitInterface(wt2_dir)

                # Rebase: move commits after resolved onto new_base
                # git rebase --onto <new_base> <resolved> <rewrite_branch>
                rebase_ok = (
                    _run_git(
                        wt2_git,
                        ["rebase", "--onto", new_base, resolved, rewrite_branch],
                    )
                    is not None
                )
                if not rebase_ok:
                    # Try to abort if needed
                    _run_git(wt2_git, ["rebase", "--abort"])
                    console.print(
                        "[red]Rebase failed; repository left untouched.[/red]"
                    )
                    return False

                new_head = (
                    _run_git(wt2_git, ["rev-parse", rewrite_branch]) or ""
                ).strip()

                # Update original branch ref and working tree
                if (
                    _run_git(
                        self.git,
                        ["update-ref", f"refs/heads/{current_branch}", new_head],
                    )
                    is None
                ):
                    console.print("[red]Failed to update branch ref; aborting.[/red]")
                    return False

                # If on that branch, sync working tree
                _run_git(self.git, ["reset", "--hard", new_head])
                console.print("[green]Commit expansion successful![/green]")
                return True

            finally:
                _cleanup_worktree(self.git, wt2_dir)
                # Delete temporary rewrite branch if it exists
                if rewrite_branch:
                    _run_git(self.git, ["branch", "-D", rewrite_branch])

        finally:
            _cleanup_worktree(self.git, wt1_dir)
            # Delete temp expand branch
            _run_git(self.git, ["branch", "-D", f"vibe-expand-{_short(resolved)}"])
        return False
