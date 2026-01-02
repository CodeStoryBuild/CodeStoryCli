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

from itertools import groupby

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.immutable_diff_chunk import ImmutableDiffChunk
from codestory.core.diff.data.line_changes import Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.diff.patch.patch_generator import PatchGenerator
from codestory.core.semantic_analysis.annotation.file_manager import FileManager


class SemanticPatchGenerator(PatchGenerator):
    """Generates semantic patches with configurable amount of context lines.

    The output format is tagged per-line to assist LLMs in distinguishing
    metadata, context, and code changes:
    [h]   - Header / Metadata
    [add] - Added lines
    [rem] - Removed lines
    [ctx] - Context lines
    """

    def __init__(
        self,
        containers: list[AtomicContainer],
        file_manager: FileManager,
        context_lines: int = 3,
        skip_whitespace: bool = False,
    ):
        super().__init__(containers, file_manager=file_manager)
        self.context_lines = context_lines
        self.skip_whitespace = skip_whitespace

    def _generate_diff(
        self,
        immutable_chunks: list[ImmutableDiffChunk],
        standard_diff_chunks: list[StandardDiffChunk],
    ) -> dict[bytes, bytes]:
        patches: dict[bytes, bytes] = {}

        # 1. Binary/Immutable Chunks
        for immutable_chunk in immutable_chunks:
            patches[immutable_chunk.canonical_path()] = (
                b"[h] ### BEGIN BINARY PATCH\n"
                + immutable_chunk.file_patch
                + b"[h] ### END BINARY PATCH\n"
            )

        sorted_chunks = sorted(standard_diff_chunks, key=lambda c: c.canonical_path())

        # 3. Process by File
        for file_path, file_chunks_iter in groupby(
            sorted_chunks, key=lambda c: c.canonical_path()
        ):
            file_chunks: list[StandardDiffChunk] = list(file_chunks_iter)
            if not file_chunks:
                continue

            base_hash = file_chunks[0].base_hash
            if not all(c.base_hash == base_hash for c in file_chunks):
                raise RuntimeError(
                    f"INVARIANT VIOLATION: Chunks for file {file_path.decode('utf-8', errors='replace')} have inconsistent base hashes!"
                )

            # Determine if this set of chunks constitutes a full file deletion or addition
            lines_deleted = sum(c.old_len() for c in file_chunks)
            lines_added = sum(c.new_len() for c in file_chunks)
            lines_in_original = self._get_line_count(file_path, base_hash)

            # Check rename FIRST (it's metadata-based, not content-based)
            file_rename = all(file_chunk.is_file_rename for file_chunk in file_chunks)

            file_deletion = (
                all(file_chunk.is_file_deletion for file_chunk in file_chunks)
                and lines_in_original is not None
                and lines_deleted >= lines_in_original
                and lines_added == 0
            )
            file_addition = all(
                file_chunk.is_file_addition for file_chunk in file_chunks
            ) and (lines_in_original is None)

            header = self._generate_header(
                file_chunks, file_rename, file_addition, file_deletion
            )

            out_lines = [f"[h] {header}"]

            # Short-circuit for empty renames
            if "RENAMED" in header and not any(c.has_content for c in file_chunks):
                patches[file_path] = ("\n".join(out_lines) + "\n").encode("utf-8")
                continue

            old_file_lines = self._get_file_lines(file_path, base_hash)
            sorted_file_chunks = sorted(file_chunks, key=lambda c: c.get_sort_key())

            last_line_emitted = 0
            is_pure_addition = all(c.is_file_addition for c in file_chunks)

            for i, chunk in enumerate(sorted_file_chunks):
                if not chunk.has_content:
                    continue

                curr_start = chunk.old_start or 1
                curr_end = curr_start + (chunk.old_len() - 1)

                # Determine where context should start for this chunk
                ideal_context_start = max(1, curr_start - self.context_lines)

                # Gap Filling Logic
                if ideal_context_start > last_line_emitted + 1:
                    skipped_lines = ideal_context_start - (last_line_emitted + 1)
                    if skipped_lines <= self.context_lines:
                        context_start = last_line_emitted + 1
                    else:
                        context_start = ideal_context_start
                else:
                    context_start = max(last_line_emitted + 1, ideal_context_start)

                # --- VISUAL HUNK START ---
                is_gap = context_start > last_line_emitted + 1
                is_start_of_hunk = (i == 0) or is_gap

                if is_start_of_hunk:
                    if is_gap and last_line_emitted > 0:
                        out_lines.append("[h] ...")

                    # PRINT HEADER FIRST (Before Context)
                    if not is_pure_addition:
                        out_lines.append(f"[h] Line {curr_start}:")

                # --- LEADING CONTEXT ---
                if old_file_lines:
                    for ln in range(context_start, curr_start):
                        if 1 <= ln <= len(old_file_lines):
                            if (
                                self.skip_whitespace
                                and old_file_lines[ln - 1].strip() == ""
                            ):
                                continue
                            out_lines.append(f"[ctx] {old_file_lines[ln - 1]}")

                # --- CHUNK CONTENT ---
                if chunk.parsed_content:
                    for item in chunk.parsed_content:
                        text = item.content.decode("utf-8", errors="replace").rstrip()
                        tag = "[rem]" if isinstance(item, Removal) else "[add]"
                        out_lines.append(f"{tag} {text}")
                        if item.newline_marker:
                            out_lines.append("[ctx] \\ No newline at end of file")

                # Update last_line_emitted to include the current chunk's content range
                last_line_emitted = max(last_line_emitted, curr_end)

                # --- TRAILING CONTEXT (With Lookahead) ---
                if old_file_lines:
                    # Look ahead to next chunk to avoid overlapping context
                    next_chunk_start = (
                        sorted_file_chunks[i + 1].old_start
                        if i + 1 < len(sorted_file_chunks)
                        else float("inf")
                    )

                    # Stop context at context_limit OR just before next chunk
                    after_end = min(
                        curr_end + self.context_lines,
                        len(old_file_lines),
                        next_chunk_start - 1,
                    )

                    # START at max(curr_end + 1, last_line_emitted + 1)
                    start_ln = max(curr_end + 1, last_line_emitted + 1)

                    for ln in range(start_ln, int(after_end) + 1):
                        if (
                            self.skip_whitespace
                            and old_file_lines[ln - 1].strip() == ""
                        ):
                            continue
                        out_lines.append(f"[ctx] {old_file_lines[ln - 1]}")
                        last_line_emitted = ln

            patches[file_path] = ("\n".join(out_lines) + "\n").encode("utf-8")

        return patches

    def _get_file_lines(self, file_path: bytes, commit_hash: str) -> list[str]:
        """Get file lines using FileManager's cached content."""
        return self.file_manager.get_file_lines(file_path, commit_hash)

    def _generate_header(
        self,
        chunks: list[StandardDiffChunk],
        file_rename: bool,
        file_addition: bool,
        file_deletion: bool,
    ) -> str:
        single = chunks[0]
        old_path = (single.old_file_path or b"dev/null").decode(
            "utf-8", errors="replace"
        )
        new_path = (single.new_file_path or b"dev/null").decode(
            "utf-8", errors="replace"
        )

        # Logic mirroring Git behavior
        # file_rename is passed in (checked first in caller)
        standard_modification = not (file_rename or file_addition or file_deletion)

        if standard_modification:
            # For partial deletions, we refer to the old path (git behavior)
            path = old_path if single.is_file_deletion else new_path
            return f"### MODIFIED FILE: {path}"
        elif file_rename:
            return f"### RENAMED FILE: {old_path} -> {new_path}"
        elif file_deletion:
            return f"### DELETED FILE: {old_path}"
        elif file_addition:
            return f"### NEW FILE: {new_path}"

        return f"### MODIFIED FILE: {new_path}"
