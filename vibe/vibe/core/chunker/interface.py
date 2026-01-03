"""
ChunkerInterface

This interface is responsible for subdividing raw diff hunks into smaller, atomic chunks.

Responsibilities:
- Split hunks into sub-hunks, functions, logical blocks, or line-level chunks
- Provide input suitable for semantic grouping
- Optional: syntax-aware or AI-driven splitting

Possible Implementations:
- HunkChunker: returns hunks unchanged
- SubHunkChunker: splits hunks based on syntax, blank lines, or functions
- AIChunker: uses an AI model to propose atomic chunks semantically
- CustomChunker: user-defined rules for splitting

Notes:
- Must propagate old/new line numbers and file paths so chunks can be committed individually
- Sub-hunk splitting is an optional but powerful enhancement
- Should preserve metadata like file_path and line numbers
- Enables fine-grained commits later in the pipeline
"""

from abc import ABC, abstractmethod
from typing import List
from ..data.models import DiffChunk, Removal, Addition
from ..data.s_diff_chunk import StandardDiffChunk


class ChunkerInterface(ABC):
    @abstractmethod
    def chunk(self, diff_chunks: List[DiffChunk]) -> List[DiffChunk]:
        """Split hunks into smaller chunks or sub-hunks"""

    def split_into_atomic_chunks(chunk) -> List["StandardDiffChunk"]:
        """
        Splits the chunk into its most atomic units using a single-pass,
        two-pointer merge algorithm.
        """
        if not isinstance(chunk, StandardDiffChunk):
            raise ValueError("Chunk must be an instance of StandardDiffChunk!")

        removals = [r for r in chunk.parsed_content if isinstance(r, Removal)]
        additions = [a for a in chunk.parsed_content if isinstance(a, Addition)]

        atomic_chunks: List[StandardDiffChunk] = []
        r_ptr, a_ptr = 0, 0

        # A single loop merges removals and additions until both lists are exhausted.
        while r_ptr < len(removals) or a_ptr < len(additions):
            # Use float('inf') as a sentinel when a pointer is out of bounds.
            # This ensures the other list's items are always processed.
            rel_r_idx = (
                removals[r_ptr].line_number - chunk.old_start
                if r_ptr < len(removals)
                else float("inf")
            )
            rel_a_idx = (
                additions[a_ptr].line_number - chunk.new_start
                if a_ptr < len(additions)
                else float("inf")
            )

            sub_slice = []
            # Case 1: Matched pair (Modification)
            if rel_r_idx == rel_a_idx:
                sub_slice = [removals[r_ptr], additions[a_ptr]]
                r_ptr += 1
                a_ptr += 1
            # Case 2: Unmatched removal comes first (Pure Deletion)
            # This condition also handles leftover removals when additions are exhausted (rel_a_idx is 'inf').
            elif rel_r_idx < rel_a_idx:
                sub_slice = [removals[r_ptr]]
                r_ptr += 1
            # Case 3: Unmatched addition comes first (Pure Addition)
            # This condition also handles leftover additions when removals are exhausted (rel_r_idx is 'inf').
            else:  # rel_a_idx < rel_r_idx
                sub_slice = [additions[a_ptr]]
                a_ptr += 1

            # Create the atomic chunk from the determined slice.
            # The factory method handles the details of chunk creation.
            atomic_chunk = chunk.from_parsed_content_slice(
                chunk._file_path,
                sub_slice,
                chunk.file_mode,
                chunk.is_file_addition,
                chunk.is_file_deletion,
            )
            if chunk:
                atomic_chunks.append(atomic_chunk)

        return atomic_chunks
