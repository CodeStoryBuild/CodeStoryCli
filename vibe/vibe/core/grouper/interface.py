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
from itertools import groupby
from typing import List, Dict, Optional
from ..data.models import CommitGroup, ProgressCallback
from ..data.chunk import Chunk
from ..synthesizer.git_synthesizer import GitSynthesizer


class LogicalGrouper(ABC):
    @abstractmethod
    def group_chunks(
        self,
        chunks: list[Chunk],
        message: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[CommitGroup]:
        """Return a list of ChunkGroup"""

    def get_total_chunks_per_file(self, all_chunks: list[Chunk]):
        all_chunks = []
        for chunk in all_chunks:
            all_chunks.extend(chunk.get_chunks())

        total_chunks_per_file = {}
        for file_path, file_chunks_iter in groupby(
            sorted(all_chunks, key=lambda c: c.canonical_path()),
            key=lambda c: c.canonical_path(),
        ):
            total_chunks_per_file[file_path] = len(list(file_chunks_iter))

        return total_chunks_per_file

    def get_descriptive_patch(self, chunk: Chunk, total_chunks: list[Chunk]):
        diff = GitSynthesizer._generate_unified_diff(chunk.get_chunks(), total_chunks)

        return "\n\n".join(diff.values())
