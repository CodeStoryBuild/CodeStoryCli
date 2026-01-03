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
from ..data.diff_chunk import DiffChunk
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
            List of DiffChunks, where any DiffChunks exceeding max_chunks is split
            into DiffChunks containing DiffChunks atoms
        """
        result: List[DiffChunk] = []

        for chunk in diff_chunks:
            # Split into atomic chunks
            atomic_chunks = chunk.split_into_atomic_chunks()

            # If atomic chunks fit within limit, add them individually
            if len(atomic_chunks) <= self.max_chunks:
                result.extend(atomic_chunks)
            else:
                # Group atomic chunks into composite chunks
                for i in range(0, len(atomic_chunks), self.max_chunks):
                    chunk_group = atomic_chunks[i : i + self.max_chunks]
                    composite = CompositeDiffChunk(chunks=chunk_group)
                    result.append(composite)

        return result
