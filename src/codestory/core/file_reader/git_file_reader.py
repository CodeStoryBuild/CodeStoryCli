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

from codestory.core.git_commands.git_commands import GitCommands


class GitFileReader:
    def __init__(self, git_commands: GitCommands):
        self.git_commands = git_commands

    def read_all(
        self,
        old_commit_hash: str,
        new_commit_hash: str,
        old_files: list[str],
        new_files: list[str],
    ) -> tuple[list[str | None], list[str | None]]:
        """
        Returns the content of multiple files from base and patched commits using git cat-file --batch.
        """
        # Prepare all objects to read
        old_objs = [
            f"{old_commit_hash}:{path.replace('\\', '/').strip()}" for path in old_files
        ]
        new_objs = [
            f"{new_commit_hash}:{path.replace('\\', '/').strip()}" for path in new_files
        ]

        all_objs = old_objs + new_objs
        all_contents = self.git_commands.cat_file_batch(all_objs)

        # Split back into old and new
        old_contents_bytes = all_contents[: len(old_files)]
        new_contents_bytes = all_contents[len(old_files) :]

        def to_str(content: bytes | None) -> str | None:
            if content is None:
                return None
            return content.decode("utf-8", errors="replace")

        return (
            [to_str(c) for c in old_contents_bytes],
            [to_str(c) for c in new_contents_bytes],
        )
