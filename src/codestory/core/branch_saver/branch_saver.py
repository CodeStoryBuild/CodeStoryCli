# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

import os
import tempfile
from pathlib import Path

from loguru import logger

from codestory.core.exceptions import DetachedHeadError, GitError
from codestory.core.git_interface.interface import GitInterface


class BranchSaver:
    """Save working directory changes into a branch-specific backup branch and restore them."""

    BACKUP_PREFIX = "backup-"

    def __init__(self, git: GitInterface):
        self.git = git

    def _run(
        self,
        args: list[str],
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> str | None:
        """Run a git command via the GitInterface and return stdout as string."""
        return self.git.run_git_text_out(args, cwd=cwd, input_text=input_text)

    def _run_git_binary(
        self,
        *args: str,
        cwd: str | Path | None = None,
        env: dict | None = None,
        stdin_content: str | bytes | None = None,
    ) -> bytes:
        """Helper to run Git commands via the binary interface."""
        input_data = None
        if isinstance(stdin_content, str):
            input_data = stdin_content.encode("utf-8")
        elif isinstance(stdin_content, bytes):
            input_data = stdin_content

        result = self.git.run_git_binary_out(
            args=list(args), input_bytes=input_data, env=env, cwd=cwd
        )

        if result is None:
            raise GitError(f"Git command failed: {' '.join(args)}")

        return result

    def _run_git_decoded(self, *args: str, **kwargs) -> str:
        """Helper to run Git and get a decoded string."""
        output_bytes = self._run_git_binary(*args, **kwargs)
        return output_bytes.decode("utf-8", errors="replace").strip()

    def _branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists using `git rev-parse --verify --quiet`."""
        result = self._run(["rev-parse", "--verify", "--quiet", branch_name])
        return result is not None and result.strip() != ""

    def save_working_state(self) -> tuple[str, str, str]:
        """
        Save the current working directory into a backup branch using index manipulation.

        - Creates a tree object from the current working directory state.
        - Commits this tree to a backup branch WITHOUT checking it out.
        - Returns the old commit hash (main's HEAD), the new commit hash (backup branch's HEAD),
          and the backup branch name.
        """
        logger.debug("Backing up current state...")
        original_branch = (self._run(["branch", "--show-current"]) or "").strip()
        # check that not a detached branch
        if not original_branch:
            msg = "Cannot backup: currently on a detached HEAD."
            raise DetachedHeadError(msg)

        # check if branch is empty
        head_commit = (self._run(["rev-parse", "HEAD"]) or "").strip()
        if not head_commit:
            logger.debug(
                f"Branch '{original_branch}' is empty: creating initial empty commit"
            )
            self._run(["commit", "--allow-empty", "-m", "Initial commit"])

        backup_branch = f"{self.BACKUP_PREFIX}{original_branch}"
        old_commit_hash = (self._run(["rev-parse", "HEAD"]) or "").strip()

        logger.debug(f"Creating/Updating backup branch name={backup_branch}")

        # Create a temporary index file to build the backup commit
        temp_index_fd, temp_index_path = tempfile.mkstemp(prefix="codestory_backup_")
        os.close(temp_index_fd)

        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = temp_index_path

        try:
            # Load the current HEAD into the temporary index
            self._run_git_binary("read-tree", "HEAD", env=env)

            # Add all working directory changes to the temporary index
            # This includes untracked files
            self._run_git_binary("add", "-A", env=env)

            # Write the index state to a tree object
            new_tree_hash = self._run_git_decoded("write-tree", env=env)

            # Create a commit from this tree
            commit_msg = f"Backup of working state from {original_branch}"
            new_commit_hash = self._run_git_decoded(
                "commit-tree",
                new_tree_hash,
                "-p",
                old_commit_hash,
                "-m",
                commit_msg,
            )

            # Update the backup branch to point to this new commit
            self._run(["branch", "-f", backup_branch, new_commit_hash])

            logger.debug(
                f"Backup created: {new_commit_hash[:8]} on branch {backup_branch}"
            )

        finally:
            # Cleanup the temporary index file
            if os.path.exists(temp_index_path):
                os.unlink(temp_index_path)

        return (
            old_commit_hash,
            new_commit_hash,
            original_branch,
        )

    def restore_from_backup(self, exclude_path: str | None = None) -> bool:
        """
        Restore state from the backup branch for the current branch.

        - Applies all changes as uncommitted, unstaged changes.
        - If `exclude_paths` is provided, those paths will not be touched during the restore.
        """
        original_branch = (self._run(["branch", "--show-current"]) or "").strip()
        if not original_branch:
            raise DetachedHeadError("Cannot restore: currently on a detached HEAD.")

        backup_branch = f"{self.BACKUP_PREFIX}{original_branch}"

        if not self._branch_exists(backup_branch):
            logger.warning(f"No backup branch found for {original_branch}")
            return False

        try:
            # Build the restore command dynamically
            cmd = [
                "restore",
                "--source",
                backup_branch,
                "--staged",
                "--worktree",
                "--",
            ]

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
            logger.warning(f"Failed to restore from backup: {e}")
            return False
