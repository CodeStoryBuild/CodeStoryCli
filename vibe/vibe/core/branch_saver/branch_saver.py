from pathlib import Path
from typing import Optional, List, Tuple
from ..git_interface.interface import GitInterface


class DetachedHeadError(Exception):
    """Raised when trying to backup a detached HEAD."""

    pass


class BranchSaver:
    """Save working directory changes into a branch-specific backup branch and restore them."""

    BACKUP_PREFIX = "backup-"

    def __init__(self, git: GitInterface):
        self.git = git

    def _run(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        input_text: Optional[str] = None,
    ) -> Optional[str]:
        """Run a git command via the GitInterface and return stdout as string."""
        return self.git.run_git_text(args, cwd=cwd, input_text=input_text)

    def _branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists using `git rev-parse --verify --quiet`."""
        result = self._run(["rev-parse", "--verify", "--quiet", branch_name])
        return result is not None and result.strip() != ""

    def save_working_state(self) -> Tuple[str, str, str]:
        """
        Save the current working directory into a backup branch.

        - If the backup branch exists, it fast-forwards it to the main branch's HEAD.
        - Commits all changes, including previously untracked files.
        - Returns the old commit hash (main's HEAD), the new commit hash (backup branch's HEAD),
          and the backup branch name.
        """
        original_branch = (self._run(["branch", "--show-current"]) or "").strip()
        # check that not a detached branch
        if not original_branch:
            msg = "Cannot backup: currently on a detached HEAD."
            print(msg)
            raise DetachedHeadError(msg)

        # check if branch is empty
        head_commit = (self._run(["rev-parse", "HEAD"]) or "").strip()
        if not head_commit:
            print(f"Branch '{original_branch}' is empty: creating initial empty commit")
            self._run(["commit", "--allow-empty", "-m", "Initial commit"])

        backup_branch = f"{self.BACKUP_PREFIX}{original_branch}"
        old_commit_hash = (self._run(["rev-parse", "HEAD"]) or "").strip()

        print(f"{backup_branch=}")

        # Create or update the backup branch to point to the current branch's HEAD
        self._run(["branch", "-f", backup_branch, original_branch])

        # Temporarily switch to the backup branch to commit the working changes
        # Using a try/finally block to ensure we always switch back
        try:
            self._run(["checkout", backup_branch])
            self._run(["add", "-A"])
            commit_msg = f"Backup of working state from {original_branch}"
            # Using --no-verify to skip any pre-commit hooks for this temporary commit
            self._run(["commit", "--no-verify", "-m", commit_msg])
            new_commit_hash = (self._run(["rev-parse", "HEAD"]) or "").strip()
        finally:
            # Always return to the original branch
            self._run(["checkout", original_branch])
            # once we have created the save, bring back the changes
            self.restore_from_backup()

        return (
            original_branch,
            old_commit_hash,
            backup_branch,
            new_commit_hash,
        )

    def restore_from_backup(self, exclude_path: Optional[str] = None) -> bool:
        """
        Restore state from the backup branch for the current branch.

        - Applies all changes as uncommitted, unstaged changes.
        - If `exclude_paths` is provided, those paths will not be touched during the restore.
        """
        original_branch = (self._run(["branch", "--show-current"]) or "").strip()
        if not original_branch:
            msg = "Cannot restore: currently on a detached HEAD."
            print(msg)
            raise DetachedHeadError(msg)

        backup_branch = f"{self.BACKUP_PREFIX}{original_branch}"

        if not self._branch_exists(backup_branch):
            print(f"No backup branch found for {original_branch}")
            return False

        try:
            # Build the restore command dynamically
            cmd = ["restore", "--source", backup_branch, "--staged", "--worktree", "--"]

            # Add the pathspecs
            if exclude_path is not None:
                # Restore everything BUT the excluded paths
                cmd.append(".")
                cmd.append(f":(exclude){exclude_path}")
            else:
                # Default behavior: restore everything
                cmd.append(".")

            # Restore all tracked changes from the backup branch
            self._run(cmd)

            # Unstage all the restored changes to make them appear as local modifications
            self._run(["reset"])

            return True

        except Exception as e:
            print(f"Failed to restore from backup: {e}")
            return False
