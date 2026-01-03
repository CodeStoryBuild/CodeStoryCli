from collections import defaultdict
from typing import Callable

from .interface import MechanicalChunker
from ..data.chunk import Chunk
from ..data.diff_chunk import DiffChunk
from ..data.composite_diff_chunk import CompositeDiffChunk
from ..data.line_changes import Addition, Removal
from ..semantic_grouper.context_manager import ContextManager


class AtomicChunker(MechanicalChunker):
    """Mechanical chunker that merges adjacent context-only atomic chunks into
    their neighboring non-context chunk. A context line is either blank or a
    pure comment line (as determined via `CommentMap`).
    """

    @staticmethod
    def _is_blank(line_text: bytes) -> bool:
        return line_text.strip() == b""

    def _line_is_context(
        self,
        change: Addition | Removal,
        parent_chunk: DiffChunk,
        context_manager: ContextManager,
    ) -> bool:
        """Return True if the line is blank or a pure comment.

        Uses the appropriate file version's `CommentMap` if available, falling
        back to blank-line only classification if context is missing.
        """
        # Blank lines are always treated as context
        if self._is_blank(change.content):
            return True

        # Determine which file path + version applies
        if isinstance(change, Addition):
            file_path = parent_chunk.new_file_path
            is_old = False
        else:  # Removal
            file_path = parent_chunk.old_file_path
            is_old = True

        if not file_path:
            return False

        file_ctx = context_manager.get_context(file_path, is_old)
        if not file_ctx:
            # Without analysis context we can't confirm pure comment
            return False

        comment_lines = file_ctx.comment_map.pure_comment_lines
        # Diff line numbers are 1-indexed; comment map uses 0-indexed
        line_idx = change.line_number - 1
        return line_idx in comment_lines

    def _chunk_is_context(
        self, atomic_chunk: DiffChunk, ctx_mgr: ContextManager
    ) -> bool:
        if not atomic_chunk.parsed_content:
            return False
        for change in atomic_chunk.parsed_content:
            if not self._line_is_context(change, atomic_chunk, ctx_mgr):
                return False

        return True

    def chunk(
        self, diff_chunks: list[Chunk], context_manager: ContextManager
    ) -> list[Chunk]:
        mechanical_chunks: list[Chunk] = []
        for chunk in diff_chunks:
            if isinstance(chunk, DiffChunk):
                atomic_chunks = chunk.split_into_atomic_chunks()
                mechanical_chunks.extend(
                    self._group_by_chunk_predicate(
                        lambda c: self._chunk_is_context(c, context_manager),
                        atomic_chunks,
                    )
                )
            else:
                mechanical_chunks.append(chunk)
        return mechanical_chunks

    def _group_by_chunk_predicate(
        self, predicate: Callable[[DiffChunk], bool], chunks: list[DiffChunk]
    ) -> list[Chunk]:
        """Group contiguous atomic chunks where `predicate` holds, then attach
        those groups to the adjacent non-predicate chunk (mirroring prior
        whitespace behavior)."""
        n = len(chunks)
        i = 0
        grouped: list[tuple[Chunk, bool]] = []

        while i < n:
            current_chunk = chunks[i]
            combined_indices: list[int] = []

            while i < n and predicate(chunks[i]):
                combined_indices.append(i)
                i += 1

            if combined_indices:
                # Build composite for multiple consecutive context chunks
                if len(combined_indices) > 1:
                    group_chunk = CompositeDiffChunk(
                        [chunks[idx] for idx in combined_indices]
                    )
                else:
                    group_chunk: Chunk = chunks[combined_indices[0]]
                grouped.append((group_chunk, True))
            else:
                grouped.append((current_chunk, False))
                i += 1

        if len(grouped) == 1:
            return [grouped[0][0]]

        links: dict[int, list[Chunk]] = defaultdict(list)
        for idx, (group, is_ctx) in enumerate(grouped):
            if is_ctx:
                # Attach context group to neighbor non-context group
                # preference for next group if possible, else previous
                if idx < len(grouped) - 1:
                    links[idx + 1].append(group)
                else:
                    links[idx - 1].append(group)
            else:
                links[idx].append(group)

        if not links and grouped:
            # This handles the case where all chunks were context chunks
            # We should return them as a single group.
            all_chunks = [g[0] for g in grouped]
            if len(all_chunks) > 1:
                return [CompositeDiffChunk(all_chunks)]
            return all_chunks  # Or just [grouped[0][0]]

        final_groups: list[Chunk] = []
        for idx in sorted(links.keys()):
            chunk_list = links[idx]
            if len(chunk_list) > 1:
                final_groups.append(CompositeDiffChunk(chunk_list))
            else:
                final_groups.append(chunk_list[0])
        return final_groups
