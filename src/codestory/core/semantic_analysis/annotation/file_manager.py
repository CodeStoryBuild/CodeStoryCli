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

"""FileManager for centralized file content caching."""

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.git.git_commands import GitCommands


class FileManager:
    """Centralized manager for file content caching.

    This class handles efficient batch fetching and caching of file contents
    from Git. It is used by both ContextManagerBuilder and PatchGenerator
    to avoid redundant git cat-file calls.

    Usage:
        file_manager = FileManager(containers, git_commands)
        content = file_manager.get_file_content(b"path/to/file.py", "abc123")
    """

    def __init__(
        self,
        containers: list[AtomicContainer],
        git_commands: GitCommands,
    ):
        """Initialize the FileManager.

        Args:
            containers: List of AtomicContainer objects to extract file paths from
            git_commands: GitCommands instance for fetching file contents
        """
        self._content_cache: dict[tuple[bytes, str], bytes | None] = {}
        self._line_counts: dict[tuple[bytes, str], int | None] = {}
        self._lines_cache: dict[tuple[bytes, str], list[str]] = {}

        # Extract all unique (file_path, commit_hash) pairs from containers
        self._prefetch_contents(containers, git_commands)

    def _prefetch_contents(
        self,
        containers: list[AtomicContainer],
        git_commands: GitCommands,
    ) -> None:
        """Pre-fetch file contents for all files in the containers."""
        seen_pairs: list[tuple[bytes, str]] = []
        seen_keys: set[tuple[bytes, str]] = set()

        for container in containers:
            for chunk in container.get_atomic_chunks():
                if isinstance(chunk, StandardDiffChunk):
                    # For standard chunks, we need both base and new versions
                    if chunk.old_file_path:
                        key = (chunk.old_file_path, chunk.base_hash)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            seen_pairs.append(key)

                    if chunk.new_file_path:
                        key = (chunk.new_file_path, chunk.new_hash)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            seen_pairs.append(key)

                    # Also get the canonical path with base_hash for line counts
                    canonical_key = (chunk.canonical_path(), chunk.base_hash)
                    if canonical_key not in seen_keys:
                        seen_keys.add(canonical_key)
                        seen_pairs.append(canonical_key)

        if not seen_pairs:
            return

        # Prepare batch objects for git cat-file --batch
        objs = [
            f"{commit_hash}:{file_path.decode('utf-8', errors='replace')}".encode()
            for file_path, commit_hash in seen_pairs
        ]

        contents = git_commands.cat_file_batch(objs)

        for (file_path, commit_hash), content in zip(seen_pairs, contents, strict=True):
            self._content_cache[(file_path, commit_hash)] = content
            if content is None:
                self._line_counts[(file_path, commit_hash)] = None
            else:
                self._line_counts[(file_path, commit_hash)] = len(content.splitlines())

    def get_file_content(self, file_path: bytes, commit_hash: str) -> bytes | None:
        """Get the content of a file at a specific commit.

        Returns:
            File content as bytes, or None if the file does not exist.
        """
        return self._content_cache.get((file_path, commit_hash))

    def get_line_count(self, file_path: bytes, commit_hash: str) -> int | None:
        """Get the number of lines in a file at a specific commit.

        Returns:
            Number of lines, or None if the file does not exist.
        """
        return self._line_counts.get((file_path, commit_hash))

    def get_file_lines(self, file_path: bytes, commit_hash: str) -> list[str]:
        """Get the lines of a file as a list of strings.

        This caches the decoded and split result for efficiency.

        Returns:
            List of lines as strings, or empty list if file does not exist.
        """
        key = (file_path, commit_hash)
        if key in self._lines_cache:
            return self._lines_cache[key]

        content = self._content_cache.get(key)
        if content is None:
            return []

        lines = content.decode("utf-8", errors="replace").splitlines()
        self._lines_cache[key] = lines
        return lines

    def has_file(self, file_path: bytes, commit_hash: str) -> bool:
        """Check if a file exists at a specific commit."""
        return self._content_cache.get((file_path, commit_hash)) is not None
