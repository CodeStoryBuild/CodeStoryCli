from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from vibe.core.data.r_diff_chunk import RenameDiffChunk
from vibe.core.data.s_diff_chunk import StandardDiffChunk
from ..data.models import DiffChunk, CommitGroup, CommitResult

from dataclasses import dataclass
from typing import List

@dataclass
class HunkWrapper:
    file_path: str
    hunk_lines: List[str]
    old_start: int
    new_start: int


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
    def get_working_diff(self, target: Optional[str] = None) -> List[HunkWrapper]:
        """Return the working diff as a list of DiffChunks for the given target."""

    @abstractmethod
    def get_rename_map(self, target: Optional[str] = None, similarity: int = 50) -> Dict[str, str]:
        """ Detect renames in the repo against HEAD for a given target """

    @abstractmethod
    def commit_to_new_branch(self, group: CommitGroup) -> CommitResult:
        """ Create a new branch from HEAD, apply the commit group as a commit """

    @abstractmethod
    def reset(self) -> None:
        """Reset staged changes / optionally clean the working directory."""

    @abstractmethod
    def track_untracked(self, target: Optional[str] = None) -> None:
        """Make untracked files tracked (git add) without staging any other changes."""

    @abstractmethod
    def need_reset(self) -> bool:
        """Checks if there are staged changes that need to be reset"""

    @abstractmethod
    def need_track_untracked(self, target: Optional[str] = None) -> bool:
        """Checks if there are any untracked files within a target that need to be tracked."""

    def get_processed_diff(
        self,
        target : str = None,
    ) -> List[DiffChunk]:
        """
        Converts a list of HunkWrapper objects into StandardDiffChunk or
        RenameDiffChunk instances, avoiding duplicate hunks for renames.
        Combines old and new path hunks for RenameDiffChunk content.
        """
        hunks = self.get_working_diff(target)

        rename_map = self.get_rename_map(target)
        
        chunks: List[DiffChunk] = []

        # Build a lookup of file_path -> list of hunk lines
        hunk_lookup: Dict[str, List[str]] = {}
        for h in hunks:
            if h.file_path in hunk_lookup:
                hunk_lookup[h.file_path].extend(h.hunk_lines)
            else:
                hunk_lookup[h.file_path] = list(h.hunk_lines)

        processed_paths = set()  # track old + new paths already handled

        for old_path, new_path in rename_map.items():
            old_hunks = hunk_lookup.get(old_path, [])
            new_hunks = hunk_lookup.get(new_path, [])

            combined_content = "\n".join(old_hunks + new_hunks)

            chunk = RenameDiffChunk(
                old_file_path=old_path,
                new_file_path=new_path,
                content=combined_content
            )

            processed_paths.add(old_path)
            processed_paths.add(new_path)
            chunks.append(chunk)

        # Now add non-rename hunks
        for h in hunks:
            if h.file_path in processed_paths:
                continue  # skip any hunk already part of a rename

            chunk = StandardDiffChunk.from_patch(
                file_path=h.file_path,
                patch_lines=h.hunk_lines,
                old_start=h.old_start,
                new_start=h.new_start
            )
            chunks.append(chunk)

        return chunks
