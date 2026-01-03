"""
Deterministic test helpers for predictable end-to-end testing.
"""

from typing import List
from dataclasses import dataclass
from vibe.core.chunker.interface import ChunkerInterface
from vibe.core.grouper.interface import GrouperInterface
from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.s_diff_chunk import StandardDiffChunk
from vibe.core.data.models import CommitGroup, Addition, Removal


class DeterministicChunker(ChunkerInterface):
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
                keyword in chunk.content for keyword in self.split_keywords
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
        Split a chunk into individual line-level chunks for testing.
        """
        sub_chunks = []

        # Group consecutive changes to avoid creating too many tiny chunks
        current_group = []

        for i, ai_item in enumerate(chunk.parsed_content):
            current_group.append(ai_item)

            # Create chunk every 2-3 items or at the end
            if len(current_group) >= 2 or i == len(chunk.parsed_content) - 1:
                # Calculate correct old_start and new_start from the actual content
                removals = [item for item in current_group if isinstance(item, Removal)]
                additions = [
                    item for item in current_group if isinstance(item, Addition)
                ]

                # old_start should be the first removal's line number, or one before first addition if no removals
                if removals:
                    old_start = min(r.line_number for r in removals)
                elif additions:
                    old_start = min(a.line_number for a in additions) - 1
                else:
                    old_start = chunk.old_start

                # new_start should be the first addition's line number, or one before first removal if no additions
                if additions:
                    new_start = min(a.line_number for a in additions)
                elif removals:
                    new_start = min(r.line_number for r in removals) - 1
                else:
                    new_start = chunk.new_start

                # Create content string from current group
                content_lines = []
                for item in current_group:
                    if isinstance(item, Addition):
                        content_lines.append(f"+{item.content}")
                    elif isinstance(item, Removal):
                        content_lines.append(f"-{item.content}")

                sub_chunk = StandardDiffChunk(
                    file_path=chunk.file_path,
                    content="\n".join(content_lines),
                    parsed_content=current_group.copy(),
                    old_start=old_start,
                    new_start=new_start,
                )

                sub_chunks.append(sub_chunk)
                current_group = []

        return sub_chunks if sub_chunks else [chunk]


class DeterministicGrouper(GrouperInterface):
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

    def group_chunks(self, chunks: List[DiffChunk]) -> List[CommitGroup]:
        """
        Group chunks deterministically for predictable testing.
        """
        if not chunks:
            return []

        if self.group_by_file:
            return self._group_by_file(chunks)
        else:
            return self._group_by_content_patterns(chunks)

    def _group_by_file(self, chunks: List[DiffChunk]) -> List[CommitGroup]:
        """Group chunks by file path."""
        file_groups = {}

        for chunk in chunks:
            if hasattr(chunk, "file_path"):
                file_path = chunk.file_path
            elif hasattr(chunk, "new_file_path"):
                # Handle RenameDiffChunk - use new file path as key
                file_path = chunk.new_file_path
            else:
                # Fallback for unknown chunk types
                file_path = str(chunk)

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
                        commmit_message=commit_message,
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
            content = chunk.content.lower()
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
                            commmit_message=base_message,
                            extended_message=f"Deterministic {base_message.lower()} group {group_counter}",
                        )
                    )
                    group_counter += 1

        return groups

    def _determine_action(self, chunks: List[DiffChunk]) -> str:
        """Determine the primary action for a group of chunks."""
        from vibe.core.data.r_diff_chunk import RenameDiffChunk

        if any(isinstance(chunk, RenameDiffChunk) for chunk in chunks):
            return "Rename"

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
