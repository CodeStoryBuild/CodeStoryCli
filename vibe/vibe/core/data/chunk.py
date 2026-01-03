from typing import Protocol
from .diff_chunk import DiffChunk


class Chunk(Protocol):
    def format_json(self) -> str:
        """
        Formats content changes as JSON, for ai representation.

        Returns:
            A JSON string representing self.
        """
        ...

    def canonical_paths(self) -> list[bytes]:
        """
        List of affected file paths that this chunk touches (as bytes).
        The canonical path is always the most relevant path for a chunk
        For file_additions/modifications/renames, it is the new file path
        For file_deletions it is the old file path
        """
        ...

    def get_chunks(self) -> list[DiffChunk]:
        """
        Get all diff chunks inside the chunk
        """
        ...
