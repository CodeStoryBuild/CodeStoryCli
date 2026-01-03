"""
Deterministic test helpers for predictable end-to-end testing.
"""

from typing import List
from vibe.core.chunker.interface import MechanicalChunker
from vibe.core.grouper.interface import LogicalGrouper, Groupable
from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.models import CommitGroup
from vibe.core.data.line_changes import Addition, Removal


class DeterministicChunker(MechanicalChunker):
    """
    A deterministic chunker that splits chunks based on predefined rules for testing.
    This chunker will split chunks at specific keywords or patterns to create predictable results.
    """

    def __init__(self, split_keywords: List[str] = None):
        """
        Initialize with optional keywords that trigger chunk splitting.
        Default splits on 'SPLIT_HERE' comments.
        """
        self.split_keywords = split_keywords or ["SPLIT_HERE", "# SPLIT", "// SPLIT"]

    def chunk(self, diff_chunks: List[DiffChunk]) -> List[DiffChunk]:
        """
        Split chunks when split keywords are found in the content.
        For testing, we'll keep chunks as-is unless they contain split markers.
        """
        result_chunks = []

        for chunk in diff_chunks:
            # Check if chunk should be split
            should_split = any(
                keyword in chunk.format_json() for keyword in self.split_keywords
            )

            if should_split:
                # For testing purposes, split into individual line changes
                sub_chunks = self._split_chunk_by_lines(chunk)
                result_chunks.extend(sub_chunks)
            else:
                result_chunks.append(chunk)

        return result_chunks

    def _split_chunk_by_lines(self, chunk: DiffChunk) -> List[DiffChunk]:
        """
        Split a chunk into atomic chunks, then group them for testing.
        Uses the split_into_atomic_chunks method from ChunkerInterface.
        """
        from vibe.core.data.composite_diff_chunk import CompositeDiffChunk

        # Split into atomic chunks
        atomic_chunks = chunk.split_into_atomic_chunks()

        if not atomic_chunks:
            return [chunk]

        # Group consecutive atomic chunks (2-3 chunks per group) to avoid too many tiny chunks
        sub_chunks = []
        i = 0
        while i < len(atomic_chunks):
            # Determine the range for this sub-group (2-3 atomic chunks)
            end_idx = min(i + 2, len(atomic_chunks))
            chunk_group = atomic_chunks[i:end_idx]

            if len(chunk_group) == 1:
                # Single atomic chunk, add as-is
                sub_chunks.append(chunk_group[0])
            else:
                # Multiple atomic chunks, wrap in CompositeDiffChunk
                sub_chunks.append(CompositeDiffChunk(chunks=chunk_group))

            # Move to next group
            i = end_idx

        return sub_chunks if sub_chunks else [chunk]


class DeterministicGrouper(LogicalGrouper):
    """
    A deterministic grouper that groups chunks based on file patterns and content for testing.
    """

    def __init__(self, group_by_file: bool = True, max_chunks_per_group: int = 3):
        """
        Initialize with grouping strategy.

        Args:
            group_by_file: If True, group chunks by file. If False, group by content patterns.
            max_chunks_per_group: Maximum chunks to include in a single group.
        """
        self.group_by_file = group_by_file
        self.max_chunks_per_group = max_chunks_per_group

    def group_chunks(
        self, chunks: List[Groupable], message: str, on_progress=None
    ) -> List[CommitGroup]:
        """
        Group chunks deterministically for predictable testing.
        """
        if not chunks:
            return []

        if self.group_by_file:
            return self._group_by_file(chunks)
        else:
            return self._group_by_content_patterns(chunks)

    def _group_by_file(self, chunks: List[Groupable]) -> List[CommitGroup]:
        """Group chunks by file path."""
        file_groups = {}

        for chunk in chunks:
            file_path = chunk.canonical_path()

            if file_path not in file_groups:
                file_groups[file_path] = []
            file_groups[file_path].append(chunk)

        groups = []
        group_counter = 1

        for file_path, file_chunks in file_groups.items():
            # Split into smaller groups if too many chunks
            while file_chunks:
                current_chunks = file_chunks[: self.max_chunks_per_group]
                file_chunks = file_chunks[self.max_chunks_per_group :]

                # Generate deterministic commit message
                action = self._determine_action(current_chunks)
                commit_message = f"{action} {file_path}"

                groups.append(
                    CommitGroup(
                        chunks=current_chunks,
                        group_id=f"g{group_counter}",
                        commit_message=commit_message,
                        extended_message=f"Deterministic group {group_counter} for {file_path}",
                    )
                )
                group_counter += 1

        return groups

    def _group_by_content_patterns(self, chunks: List[DiffChunk]) -> List[CommitGroup]:
        """Group chunks by content patterns for more complex testing."""
        groups = []
        group_counter = 1

        # Group chunks with similar patterns
        feature_chunks = []
        refactor_chunks = []
        bug_fix_chunks = []
        other_chunks = []

        for chunk in chunks:
            content = "\n".join(line.content.lower() for line in chunk.parsed_content)
            if any(keyword in content for keyword in ["feature", "add", "new"]):
                feature_chunks.append(chunk)
            elif any(keyword in content for keyword in ["refactor", "rename", "move"]):
                refactor_chunks.append(chunk)
            elif any(keyword in content for keyword in ["fix", "bug", "error"]):
                bug_fix_chunks.append(chunk)
            else:
                other_chunks.append(chunk)

        # Create groups from categorized chunks
        categories = [
            (feature_chunks, "Add new features"),
            (refactor_chunks, "Refactor code"),
            (bug_fix_chunks, "Fix bugs"),
            (other_chunks, "Update code"),
        ]

        for category_chunks, base_message in categories:
            while category_chunks:
                current_chunks = category_chunks[: self.max_chunks_per_group]
                category_chunks = category_chunks[self.max_chunks_per_group :]

                if current_chunks:
                    groups.append(
                        CommitGroup(
                            chunks=current_chunks,
                            group_id=f"g{group_counter}",
                            commit_message=base_message,
                            extended_message=f"Deterministic {base_message.lower()} group {group_counter}",
                        )
                    )
                    group_counter += 1

        return groups

    def _determine_action(self, chunks: List[DiffChunk]) -> str:
        """Determine the primary action for a group of chunks."""
        if any(chunk.is_file_rename for chunk in chunks):
            return "Rename"

        if any(chunk.is_file_addition for chunk in chunks):
            return "Add"

        if any(chunk.is_file_deletion for chunk in chunks):
            return "Remove"

        additions = sum(
            1
            for chunk in chunks
            for item in chunk.parsed_content
            if isinstance(item, Addition)
        )
        removals = sum(
            1
            for chunk in chunks
            for item in chunk.parsed_content
            if isinstance(item, Removal)
        )

        if additions > 0 and removals == 0:
            return "Add"
        elif additions == 0 and removals > 0:
            return "Remove"
        elif additions > removals:
            return "Update"
        else:
            return "Modify"
