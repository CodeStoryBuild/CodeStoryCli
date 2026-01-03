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
from typing import List, Dict, Optional
from ..data.models import CommitGroup, ProgressCallback


class LogicalGrouper(ABC):
    @abstractmethod
    def group_chunks(
        self,
        chunks: List["Groupable"],
        message: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[CommitGroup]:
        """Return a list of ChunkGroup"""


class Groupable(ABC):
    @abstractmethod
    def format_json(self) -> Dict:
        """Format the object as json, describing what it does"""
