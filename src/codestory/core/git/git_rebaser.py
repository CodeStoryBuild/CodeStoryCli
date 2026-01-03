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

from codestory.core.exceptions import GitRebaseFailed
from codestory.core.git.git_commands import GitCommands


class GitRebaser:
    def __init__(self, git_commands: GitCommands):
        self.git_commands = git_commands

    def rebase(self, old_base_hash: str, new_base_hash: str, branch: str):
        # Get list of downstream commits (oldest to newest)
        downstream_commits = self.git_commands.get_rev_list(
            f"{old_base_hash}..{branch}", reverse=True
        )

        if not downstream_commits:
            # No downstream commits, we're done
            return new_base_hash

        import os

        new_parent = new_base_hash

        for commit in downstream_commits:
            # Get commit metadata
            log_format = "%an%n%ae%n%aI%n%cn%n%ce%n%cI%n%B"
            meta_out = self.git_commands.get_commit_metadata(commit, log_format)

            if not meta_out:
                raise GitRebaseFailed(f"Failed to get metadata for commit {commit[:7]}")

            lines = meta_out.splitlines()
            if len(lines) < 7:
                raise GitRebaseFailed(f"Invalid metadata for commit {commit[:7]}")

            author_name = lines[0]
            author_email = lines[1]
            author_date = lines[2]
            committer_name = lines[3]
            committer_email = lines[4]
            committer_date = lines[5]
            message = "\n".join(lines[6:])

            # Get the parent of the original commit
            original_parent = self.git_commands.try_get_parent_hash(commit)
            if not original_parent:
                raise GitRebaseFailed(f"Failed to get parent of commit {commit[:7]}")

            # Use merge-tree to compute the new tree
            new_tree = self.git_commands.merge_tree(original_parent, new_parent, commit)

            if not new_tree:
                raise GitRebaseFailed(f"Failed to merge-tree for commit {commit[:7]}")

            # Create commit with the new tree
            cmd_env = os.environ.copy()
            cmd_env["GIT_AUTHOR_NAME"] = author_name
            cmd_env["GIT_AUTHOR_EMAIL"] = author_email
            cmd_env["GIT_AUTHOR_DATE"] = author_date
            cmd_env["GIT_COMMITTER_NAME"] = committer_name
            cmd_env["GIT_COMMITTER_EMAIL"] = committer_email
            cmd_env["GIT_COMMITTER_DATE"] = committer_date

            new_commit = self.git_commands.commit_tree(
                new_tree, [new_parent], message, env=cmd_env
            )

            if not new_commit:
                raise GitRebaseFailed(f"Failed to create commit for {commit[:7]}")

            new_parent = new_commit

        return new_parent.strip()
