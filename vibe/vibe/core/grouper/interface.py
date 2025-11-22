"""
GrouperInterface

This interface is responsible for grouping atomic diff chunks into semantically-related sets.

Responsibilities:
- Analyze chunks and produce groups (ChunkGroup)
- Grouping can be based on:
  - AI semantic analysis (feature, refactor, bug fix)
  - Keyword linking (variable/function references)
  - File or directory heuristics
  - User-provided rules

Notes:
- Each ChunkGroup is intended to become one commit
- Can include optional group descriptions for AI-generated commit messages
- Supports flexibility in commit granularity and logical separation
"""

from abc import ABC, abstractmethod
from typing import Callable

from ..data.chunk import Chunk
from ..data.immutable_chunk import ImmutableChunk
from ..data.commit_group import CommitGroup


class LogicalGrouper(ABC):
    @abstractmethod
    def group_chunks(
        self,
        chunks: list[Chunk],
        immut_chunks: list[ImmutableChunk],
        message: str,
        on_progress: Callable[[int], None] | None = None,
    ) -> list[CommitGroup]:
        """Return a list of ChunkGroup"""
