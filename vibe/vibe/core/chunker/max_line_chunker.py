"""
MaxLineChunker

This implementation of ChunkerInterface splits diff hunks into smaller chunks
based on a maximum atomic chunk count threshold.

Responsibilities:
- Split hunks that exceed a maximum atomic chunk count into smaller composite chunks
- Preserve hunk metadata (file paths, line numbers) in the resulting chunks
- Ensure each chunk can still be applied as a valid patch
"""

from typing import List
from .interface import ChunkerInterface
from ..data.models import DiffChunk
from ..data.r_diff_chunk import RenameDiffChunk
from ..data.s_diff_chunk import StandardDiffChunk
from ..data.c_diff_chunk import CompositeDiffChunk


class MaxLineChunker(ChunkerInterface):
    def __init__(self, max_chunks: int = 50):
        """
        Initialize the chunker with a maximum atomic chunk threshold.

        Args:
            max_chunks: Maximum number of atomic chunks allowed in a single composite chunk
        """
        self.max_chunks = max_chunks

    def chunk(self, diff_chunks: List[DiffChunk]) -> List[DiffChunk]:
        """
        Split hunks into smaller composite chunks if they exceed the maximum atomic chunk count.

        Args:
            diff_chunks: List of input DiffChunks to potentially split

        Returns:
            List of DiffChunks, where any StandardDiffChunk exceeding max_chunks is split
            into CompositeDiffChunks containing StandardDiffChunk atoms
        """
        result: List[DiffChunk] = []

        for chunk in diff_chunks:
            if isinstance(chunk, StandardDiffChunk):
                # Split into atomic chunks
                atomic_chunks = ChunkerInterface.split_into_atomic_chunks(chunk)

                # If atomic chunks fit within limit, add them individually
                if len(atomic_chunks) <= self.max_chunks:
                    result.extend(atomic_chunks)
                else:
                    # Group atomic chunks into composite chunks
                    for i in range(0, len(atomic_chunks), self.max_chunks):
                        chunk_group = atomic_chunks[i : i + self.max_chunks]
                        composite = CompositeDiffChunk(
                            chunks=chunk_group, _file_path=chunk._file_path
                        )
                        result.append(composite)
            else:
                # Non-standard chunks (e.g., RenameDiffChunk) pass through unchanged
                result.append(chunk)

        return result
