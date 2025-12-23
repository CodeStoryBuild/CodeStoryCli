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

from codestory.core.exceptions import DetachedHeadError, GitError
from codestory.core.git_commands.git_commands import GitCommands


class TempCommitCreator:
    """Save working directory changes into a dangling commit and restore them."""

    def __init__(
        self, git_commands: GitCommands, current_branch: str, pathspec: list[str] | None
    ):
        self.git_commands = git_commands
        self.current_branch = current_branch
        self.pathspec = pathspec

    def _branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists using `git rev-parse --verify --quiet`."""
        try:
            self.git_commands.get_commit_hash(branch_name)
            return True
        except ValueError:
            return False

    def create_reference_commit(self) -> tuple[str, str]:
        """
        Save the current working directory into a dangling commit using index manipulation.

        - Creates a tree object from the current working directory state.
        - Commits this tree as a dangling commit (not attached to any branch).
        - Returns the old commit hash (HEAD) and the new dangling commit hash.
        """
        from loguru import logger

        logger.debug("Creating dangling commit for current state...")
        original_branch = self.current_branch
        # check that not a detached branch
        if not original_branch:
            msg = "Cannot backup: currently on a detached HEAD."
            raise DetachedHeadError(msg)

        # TODO remove this logic from here into better place
        # check if branch is empty
        try:
            head_commit = self.git_commands.get_commit_hash(self.current_branch)
        except ValueError:
            head_commit = ""

        if not head_commit:
            logger.debug(
                f"Branch '{original_branch}' is empty: creating initial empty commit"
            )
            # Create an empty tree
            empty_tree_hash = self.git_commands.write_tree()
            if not empty_tree_hash:
                raise GitError("Failed to create empty tree")

            # Create initial commit
            head_commit = self.git_commands.commit_tree(
                empty_tree_hash, [], "Initial commit"
            )
            if not head_commit:
                raise GitError("Failed to create initial commit")

            # Update branch to point to initial commit
            self.git_commands.update_ref(original_branch, head_commit)

        old_commit_hash = self.git_commands.get_commit_hash(self.current_branch)

        logger.debug("Creating dangling commit from working directory state")

        # Create a temporary index file to build the backup commit
        temp_index_fd, temp_index_path = tempfile.mkstemp(prefix="codestory_backup_")
        os.close(temp_index_fd)
        # Git read-tree fails if the index file exists but is empty (0 bytes).
        if os.path.exists(temp_index_path):
            os.unlink(temp_index_path)

        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = temp_index_path

        try:
            # Load the current branch tip into the temporary index
            self.git_commands.read_tree(self.current_branch, env=env)

            # Add working directory changes to the temporary index
            # Uses the pathspec if provided, otherwise adds current directory
            add_args = self.pathspec if self.pathspec else ["."]
            self.git_commands.add(add_args, env=env)

            # Write the index state to a tree object
            new_tree_hash = self.git_commands.write_tree(env=env)
            if not new_tree_hash:
                raise GitError("Failed to write-tree for backup")

            # Create a commit from this tree
            commit_msg = f"Temporary backup of working state from {original_branch}"
            new_commit_hash = self.git_commands.commit_tree(
                new_tree_hash, [old_commit_hash], commit_msg, env=env
            )

            if not new_commit_hash:
                raise GitError("Failed to create backup commit")

            logger.debug(f"Dangling commit created: {new_commit_hash[:8]}")

        finally:
            # Cleanup the temporary index file
            if os.path.exists(temp_index_path):
                os.unlink(temp_index_path)

        return (
            old_commit_hash,
            new_commit_hash,
        )
