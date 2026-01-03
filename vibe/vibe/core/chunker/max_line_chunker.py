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
from ..data.models import DiffChunk, Addition, Removal

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
            # Count the total number of lines in this chunk
            total_lines = chunk.get_total_lines()
            max_line = chunk.get_max_line()

            
            if total_lines <= self.max_lines:
                # If chunk is small enough, keep it as is
                result.append(chunk)
                continue
            
            # Calculate how many sub-chunks we need
            num_subchunks = math.ceil(total_lines // self.max_lines)

            
            # Split the chunk into roughly equal parts
            for i in range(num_subchunks):
                start_idx = i * self.max_lines + 1
                end_idx = min((i + 1) * self.max_lines, max_line)
                
                # Extract a portion of the chunk
                sub_chunk = chunk.extract_by_lines(start_idx, end_idx)
                result.append(sub_chunk)
        
        return result
