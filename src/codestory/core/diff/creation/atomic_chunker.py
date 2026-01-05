# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

from typing import Literal

from codestory.core.diff.data.atomic_chunk import AtomicDiffChunk
from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_analysis.annotation.context_manager import ContextManager


class AtomicChunker:
    """Mechanical chunker that splits pure add/delete chunks into per-line atomic
    chunks.

    Uses a sliding window approach to:
    1. Split each line into its own atomic chunk
    2. Attach context-only lines (blank/comment) to the next non-context line
    3. Return StandardDiffChunks (when context attaches to non-context)
    """

    def __init__(
        self,
        context_manager: ContextManager | None = None,
        chunking_level: Literal["none", "full_files", "all_files"] = "all_files",
    ):
        self.context_manager = context_manager
        self.chunking_level = chunking_level

    @staticmethod
    def _is_blank(line_text: bytes) -> bool:
        return line_text.strip() == b""

    def _line_is_context(
        self,
        change: Addition | Removal,
        parent_chunk: StandardDiffChunk,
    ) -> bool:
        """Return True if the line is blank or a pure comment."""
        # Blank lines are always treated as context
        if self._is_blank(change.content):
            return True

        if self.context_manager is None:
            return False

        # Determine which file path + version applies
        if isinstance(change, Addition):
            file_path = parent_chunk.new_file_path
            commit_hash = parent_chunk.new_hash
            line_idx = change.abs_new_line - 1
        else:  # Removal
            file_path = parent_chunk.old_file_path
            commit_hash = parent_chunk.base_hash
            line_idx = change.old_line - 1

        if not file_path:
            return False

        file_ctx = self.context_manager.get_context(file_path, commit_hash)
        if not file_ctx:
            return False

        comment_lines = file_ctx.comment_map.pure_comment_lines
        return line_idx in comment_lines

    def chunk(
        self,
        diff_chunks: list[AtomicDiffChunk],
    ) -> list[AtomicDiffChunk]:
        """Split and group diff chunks into mechanical chunks.

        Returns a list of StandardDiffChunk objects (contiguous lines
        merged into single chunks). ImmutableDiffChunks are passed
        through unchanged.
        """
        pbar = ProgressBarManager.get_pbar()
        mechanical_chunks: list[AtomicDiffChunk] = []

        for i, chunk in enumerate(diff_chunks):
            if pbar is not None:
                pbar.set_postfix({"phase": f"chunking {i + 1}/{len(diff_chunks)}"})

            if not isinstance(chunk, StandardDiffChunk):
                # Pass through ImmutableDiffChunks unchanged
                mechanical_chunks.append(chunk)
                continue

            if self.chunking_level == "none":
                mechanical_chunks.append(chunk)
                continue

            if self.chunking_level == "full_files" and not (
                chunk.is_file_addition or chunk.is_file_deletion
            ):
                mechanical_chunks.append(chunk)
                continue

            # Apply sliding window split+group
            split_chunks = self._split_and_group_chunk(chunk)
            mechanical_chunks.extend(split_chunks)

        return mechanical_chunks

    def _split_and_group_chunk(
        self,
        chunk: StandardDiffChunk,
    ) -> list[StandardDiffChunk]:
        """Split pure add/delete chunks into per-line atomic chunks and attach context.

        For each line:
        - If context (blank/comment): accumulate to attach to next non-context
        - If non-context: create atomic chunk (with pending context attached)

        Returns a list of StandardDiffChunk objects (contiguous lines merged into single chunks).
        """
        # If chunk has no content, return as-is
        if not chunk.has_content or not chunk.parsed_content:
            return [chunk]

        # Only split pure additions/deletions
        if not (chunk.pure_addition() or chunk.pure_deletion()):
            return [chunk]

        parsed = chunk.parsed_content
        final_chunks: list[StandardDiffChunk] = []
        pending_lines: list[Addition | Removal] = []

        for line in parsed:
            is_ctx = self._line_is_context(line, chunk)

            if is_ctx:
                # Accumulate context lines to attach to next non-context line
                pending_lines.append(line)
            else:
                # Non-context line: add to pending and flush as a single chunk
                pending_lines.append(line)

                # Create a single StandardDiffChunk from all pending lines (context + non-context)
                merged_chunk = StandardDiffChunk.from_parsed_content_slice(
                    base_hash=chunk.base_hash,
                    new_hash=chunk.new_hash,
                    old_file_path=chunk.old_file_path,
                    new_file_path=chunk.new_file_path,
                    file_mode=chunk.file_mode,
                    contains_newline_fallback=chunk.contains_newline_fallback,
                    parsed_slice=pending_lines,
                )
                final_chunks.append(merged_chunk)
                pending_lines = []

        # Handle trailing context with no following non-context
        if pending_lines:
            if final_chunks:
                # Merge trailing context with the last chunk
                last_chunk = final_chunks[-1]
                combined_lines = list(last_chunk.parsed_content) + pending_lines

                merged_chunk = StandardDiffChunk.from_parsed_content_slice(
                    base_hash=chunk.base_hash,
                    new_hash=chunk.new_hash,
                    old_file_path=chunk.old_file_path,
                    new_file_path=chunk.new_file_path,
                    file_mode=chunk.file_mode,
                    contains_newline_fallback=chunk.contains_newline_fallback,
                    parsed_slice=combined_lines,
                )
                final_chunks[-1] = merged_chunk
            else:
                # All lines were context - create a single chunk
                context_chunk = StandardDiffChunk.from_parsed_content_slice(
                    base_hash=chunk.base_hash,
                    new_hash=chunk.new_hash,
                    old_file_path=chunk.old_file_path,
                    new_file_path=chunk.new_file_path,
                    file_mode=chunk.file_mode,
                    contains_newline_fallback=chunk.contains_newline_fallback,
                    parsed_slice=pending_lines,
                )
                final_chunks.append(context_chunk)

        return final_chunks if final_chunks else [chunk]
