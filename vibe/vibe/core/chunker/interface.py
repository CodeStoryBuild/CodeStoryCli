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
from ..data.chunk import Chunk


class MechanicalChunker(ABC):
    @abstractmethod
    def chunk(self, diff_chunks: List[Chunk]) -> List[Chunk]:
        """Split hunks into smaller chunks or sub-hunks"""