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

from codestory.core.exceptions import GitError
from codestory.core.git.git_commands import GitCommands


class TempCommitCreator:
    """Save working directory changes into a dangling commit."""

    @staticmethod
    def create_reference_commit(
        git_commands: GitCommands,
        pathspec: list[str] | None,
        head_hash: str,
    ) -> str:
        """Save the current working directory into a dangling commit using index
        manipulation.

        - Creates a tree object from the current working directory state.
        - Commits this tree as a dangling commit (not attached to any branch).
        - Returns the new dangling commit hash.
        """
        from loguru import logger

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
            # Load the head tip into the temporary index
            git_commands.read_tree(head_hash, env=env)

            # Add working directory changes to the temporary index
            # Uses the pathspec if provided, otherwise adds current directory
            add_args = pathspec if pathspec else ["."]
            git_commands.add(add_args, env=env)

            # Write the index state to a tree object
            new_tree_hash = git_commands.write_tree(env=env)
            if not new_tree_hash:
                raise GitError("Failed to write-tree for backup")

            # Create a commit from this tree
            commit_msg = f"Temporary backup of working state from {head_hash}"
            new_commit_hash = git_commands.commit_tree(
                new_tree_hash, [head_hash], commit_msg, env=env
            )

            if not new_commit_hash:
                raise GitError("Failed to create backup commit")

            logger.debug(f"Dangling commit created: {new_commit_hash[:8]}")

        finally:
            # Cleanup the temporary index file
            if os.path.exists(temp_index_path):
                os.unlink(temp_index_path)

        return new_commit_hash
