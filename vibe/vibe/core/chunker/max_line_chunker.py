"""
MaxLineChunker

This implementation of ChunkerInterface splits diff hunks into smaller chunks
based on a maximum line count threshold.

Responsibilities:
- Split hunks that exceed a maximum line count into smaller chunks
- Preserve hunk metadata (file paths, line numbers) in the resulting chunks
- Ensure each chunk can still be applied as a valid patch
"""

import math
from typing import List
from .interface import ChunkerInterface
from ..data.models import DiffChunk
from ..data.r_diff_chunk import RenameDiffChunk
from ..data.s_diff_chunk import StandardDiffChunk


class MaxLineChunker(ChunkerInterface):
    def __init__(self, max_lines: int = 50):
        """
        Initialize the chunker with a maximum line threshold.

        Args:
            max_lines: Maximum number of lines allowed in a single chunk
        """
        self.max_lines = max_lines

    def chunk(self, diff_chunks: List[DiffChunk]) -> List[DiffChunk]:
        """
        Split hunks into smaller chunks if they exceed the maximum line count.

        Args:
            diff_chunks: List of input DiffChunks to potentially split

        Returns:
            List of DiffChunks, where any chunk exceeding max_lines is split
        """
        result: List[DiffChunk] = []

        for chunk in diff_chunks:
            if isinstance(chunk, StandardDiffChunk):
                start_num = None
                cur_num = None
                num_seen = 0

                for line in chunk.parsed_content:
                    if start_num is None:
                        start_num = line.line_number
                    if cur_num != line.line_number:
                        cur_num = line.line_number
                        num_seen += 1

                    if num_seen >= self.max_lines:
                        sub_chunk = chunk.extract_by_lines(start_num, cur_num)
                        if sub_chunk:
                            result.append(sub_chunk)

                        # reset for next slice
                        start_num = None
                        cur_num = None
                        num_seen = 0

                # handle remaining lines
                if start_num is not None:
                    sub_chunk = chunk.extract_by_lines(start_num, cur_num)
                    if sub_chunk:
                        result.append(sub_chunk)

        return result
