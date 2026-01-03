from pathlib import Path
from typing import Optional, List
from ..git_interface.interface import GitInterface


class DetachedHeadError(Exception):
    """Raised when trying to backup a detached HEAD."""
    pass


class BranchSaver:
    """Save working directory changes into a branch-specific backup branch and restore them."""

    BACKUP_PREFIX = "backup-"

    def __init__(self, git: GitInterface):
        self.git = git

    def _run(self, args: List[str], cwd: Optional[Path] = None, input_text: Optional[str] = None) -> Optional[str]:
        """Run a git command via the GitInterface and return stdout as string."""
        return self.git.run_git_text(args, cwd=cwd, input_text=input_text)

    def _branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists using `git rev-parse --verify --quiet`."""
        result = self._run(["rev-parse", "--verify", "--quiet", branch_name])
        return result is not None and result.strip() != ""

    def save_working_state(self) -> str:
        """
        Save the current working directory into a backup branch.
        - Branch name: backup-<current-branch>
        - Commits all changes, including previously untracked files
        - Stores untracked files list in memory
        - Returns commit hash of backup commit
        """

        # Determine current branch
        original_branch = (self._run(["branch", "--show-current"]) or "").strip()
        if not original_branch:
            msg = "Cannot backup: currently on a detached HEAD."
            print(msg)
            raise DetachedHeadError(msg)

        backup_branch = f"{self.BACKUP_PREFIX}{original_branch}"

        # Stage all files to be backed up (tracked + previously untracked)
        self._run(["add", "-N", "."])

        # delete backup if exists (very ugly - just for playing around)
        if self._branch_exists(backup_branch):
            self._run(["branch -D", backup_branch])
        
        self._run(["checkout", "-b", backup_branch])

        # stage files to be commited as backup
        self._run(["add", "-A"])

        # Commit changes
        commit_msg = f"Backup of working state from {original_branch}"
        self._run(["commit", "-m", commit_msg])

        # Get commit hash
        commit_hash = (self._run(["rev-parse", "HEAD"]) or "").strip()

        # Return to original branch
        self._run(["checkout", original_branch])

        return commit_hash, backup_branch

    def restore_from_backup(self) -> bool:
        """
        Restore state from the backup branch for the given target branch.
        - Applies all changes as uncommitted changes
        - Restores originally untracked files
        """

        # Determine current branch
        original_branch = (self._run(["branch", "--show-current"]) or "").strip()
        if not original_branch:
            msg = "Cannot backup: currently on a detached HEAD."
            print(msg)
            raise DetachedHeadError(msg)

        backup_branch = f"{self.BACKUP_PREFIX}{original_branch}"

        if not self._branch_exists(backup_branch):
            print(f"No backup branch found for {original_branch}")
            return False

        try:
            # Switch to target branch
            self._run(["checkout", original_branch])

            # Restore all tracked changes from backup branch as uncommitted changes
            self._run(["restore", "--source", backup_branch, "--staged", "--worktree", "."])

            # # Make files that were originally untracked back into untracked
            # self._run(["reset"])

            return True

        except Exception as e:
            print(f"Failed to restore from backup: {e}")
            return False
