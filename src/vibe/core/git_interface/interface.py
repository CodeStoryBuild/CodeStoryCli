from abc import ABC, abstractmethod
from typing import List, Optional
from ..data.models import DiffChunk, ChunkGroup, CommitResult

class GitInterface(ABC):
    """
    Minimal Git interface for AI Git pipeline, fully patch-based.

    Responsibilities:
    - Extract working diffs as DiffChunks
    - Apply patches from ChunkGroups and commit them
    - Reset staged changes / clean working directory
    - Track previously untracked files

    Notes:
    - Staging is handled internally by applying patches; no separate stage_files method is needed.
    - All DiffChunks must retain enough metadata to generate patches via to_patch().
    """

    @abstractmethod
    def get_working_diff(self, target: Optional[str] = None) -> List[DiffChunk]:
        """Return the working diff as a list of DiffChunks for the given target."""

    @abstractmethod
    def commit(self, group: ChunkGroup, message: Optional[str] = None) -> CommitResult:
        """Apply the ChunkGroup patch to the index and commit it."""

    @abstractmethod
    def reset(self) -> None:
        """Reset staged changes / optionally clean the working directory."""

    @abstractmethod
    def track_untracked(self, target: Optional[str] = None) -> None:
        """Make untracked files tracked (git add) without staging any other changes."""
