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

from loguru import logger

from codestory.core.data.chunk import Chunk
from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.data.line_changes import Addition, Removal
from codestory.core.git_commands.git_const import DEVNULLBYTES


class DiffGenerator:
    def __init__(self, all_chunks: list[Chunk | ImmutableChunk | CommitGroup]):
        diff_chunks = []
        for chunk in all_chunks:
            if isinstance(chunk, Chunk):
                diff_chunks.extend(chunk.get_chunks())
            elif isinstance(chunk, CommitGroup):
                for group_chunk in chunk.chunks:
                    if isinstance(group_chunk, Chunk):
                        diff_chunks.extend(group_chunk.get_chunks())
            # else skip Immutable Chunks, they dont use total chunks per file

        self.total_chunks_per_file = self.__get_total_chunks_per_file(diff_chunks)

    def __get_total_chunks_per_file(self, chunks: list[DiffChunk]):
        total_chunks_per_file = {}
        for file_path, file_chunks_iter in groupby(
            sorted(chunks, key=lambda c: c.canonical_path()),
            key=lambda c: c.canonical_path(),
        ):
            total_chunks_per_file[file_path] = len(list(file_chunks_iter))

        return total_chunks_per_file

    def generate_unified_diff(
        self,
        chunks: list[DiffChunk | ImmutableChunk],
    ) -> dict[bytes, bytes]:
        """
        Generates a dictionary of valid, cumulative unified diffs (patches) for each file.
        This method is stateful and correctly recalculates hunk headers for subsets of chunks.
        """
        regular_chunks = [chunk for chunk in chunks if isinstance(chunk, DiffChunk)]
        immutable_chunks = [
            chunk for chunk in chunks if isinstance(chunk, ImmutableChunk)
        ]

        # Ensure chunks are disjoint before generating patches
        self.__validate_chunks_are_disjoint(regular_chunks)

        patches: dict[bytes, bytes] = {}

        # process immutable chunks
        for immutable_chunk in immutable_chunks:
            # add newline delimiter to sepatate from other patches in the stream
            patches[immutable_chunk.canonical_path] = immutable_chunk.file_patch + b"\n"

        # process regular chunks
        sorted_chunks = sorted(regular_chunks, key=lambda c: c.canonical_path())

        for file_path, file_chunks_iter in groupby(
            sorted_chunks, key=lambda c: c.canonical_path()
        ):
            file_chunks: list[DiffChunk] = list(file_chunks_iter)

            if not file_chunks:
                continue

            current_count = len(file_chunks)
            total_expected = self.total_chunks_per_file.get(file_path)

            patch_lines = []
            single_chunk = file_chunks[0]

            # we need all chunks to mark as deletion
            file_deletion = (
                all([file_chunk.is_file_deletion for file_chunk in file_chunks])
                and current_count >= total_expected
            )
            file_addition = all(
                [file_chunk.is_file_addition for file_chunk in file_chunks]
            )
            standard_modification = all(
                [file_chunk.is_standard_modification for file_chunk in file_chunks]
            ) or (
                all([file_chunk.is_file_deletion for file_chunk in file_chunks])
                and current_count < total_expected
            )
            file_rename = all([file_chunk.is_file_rename for file_chunk in file_chunks])

            # Determine file change type for hunk calculation
            if file_addition:
                file_change_type = "added"
            elif file_deletion:
                file_change_type = "deleted"
            elif file_rename:
                file_change_type = "renamed"
            else:
                file_change_type = "modified"

            old_file_path = (
                self.__sanitize_filename(single_chunk.old_file_path)
                if single_chunk.old_file_path
                else None
            )
            new_file_path = (
                self.__sanitize_filename(single_chunk.new_file_path)
                if single_chunk.new_file_path
                else None
            )

            if standard_modification:
                if single_chunk.is_file_deletion:
                    # use old file and "pretend its a modification as we dont have all deletion chunks yet"
                    patch_lines.append(
                        b"diff --git a/" + old_file_path + b" b/" + old_file_path
                    )
                else:
                    patch_lines.append(
                        b"diff --git a/" + new_file_path + b" b/" + new_file_path
                    )
            elif file_rename:
                patch_lines.append(
                    b"diff --git a/" + old_file_path + b" b/" + new_file_path
                )
                patch_lines.append(b"rename from " + old_file_path)
                patch_lines.append(b"rename to " + new_file_path)
            elif file_deletion:
                # Treat partial deletions as a modification for the header
                patch_lines.append(
                    b"diff --git a/" + old_file_path + b" b/" + old_file_path
                )
                patch_lines.append(
                    b"deleted file mode " + (single_chunk.file_mode or b"100644")
                )
            elif file_addition:
                patch_lines.append(
                    b"diff --git a/" + new_file_path + b" b/" + new_file_path
                )
                patch_lines.append(
                    b"new file mode " + (single_chunk.file_mode or b"100644")
                )

            old_file_header = b"a/" + old_file_path if old_file_path else DEVNULLBYTES
            new_file_header = b"b/" + new_file_path if new_file_path else DEVNULLBYTES
            if single_chunk.is_file_deletion and current_count < total_expected:
                new_file_header = old_file_header

            patch_lines.append(b"--- " + old_file_header)
            patch_lines.append(b"+++ " + new_file_header)

            if not any(c.has_content for c in file_chunks):
                patch_lines.append(b"@@ -0,0 +0,0 @@")
            else:
                # Sort chunks by their sort key (old_start, then abs_new_line)
                # This maintains correct ordering even for chunks at the same old_start
                sorted_file_chunks = sorted(file_chunks, key=lambda c: c.get_sort_key())
                # you must merge chunks to get valid patches
                sorted_file_chunks = self.__merge_chunks(sorted_file_chunks)

                # CRITICAL: new_start is calculated HERE and ONLY HERE!
                # We calculate it based on old_start + cumulative_offset.
                #
                # The cumulative_offset tracks how many net lines have been added
                # (additions - deletions) by all prior chunks in this file.
                #
                # For each chunk:
                # - old_start tells us where the change occurs in the old file
                # - new_start = old_start + cumulative_offset (where it lands in new file)

                cumulative_offset = 0  # Net lines added so far (additions - deletions)

                for chunk in sorted_file_chunks:
                    if not chunk.has_content:
                        continue

                    old_len = chunk.old_len()
                    new_len = chunk.new_len()
                    is_pure_addition = old_len == 0

                    # Use the helper function to calculate hunk starts
                    hunk_old_start, hunk_new_start = self.__calculate_hunk_starts(
                        file_change_type=file_change_type,
                        old_start=chunk.old_start,
                        is_pure_addition=is_pure_addition,
                        cumulative_offset=cumulative_offset,
                    )

                    hunk_header = f"@@ -{hunk_old_start},{old_len} +{hunk_new_start},{new_len} @@".encode()
                    patch_lines.append(hunk_header)

                    for item in chunk.parsed_content:
                        if isinstance(item, Removal):
                            patch_lines.append(b"-" + item.content)
                        elif isinstance(item, Addition):
                            patch_lines.append(b"+" + item.content)

                    # Update cumulative offset for next chunk
                    cumulative_offset += new_len - old_len

                # Handle the no-newline marker fallback for the last chunk in the file
                # (added if a hunk has only this marker and thus no other changes to attach itself to)
                if (
                    sorted_file_chunks
                    and sorted_file_chunks[-1].contains_newline_fallback
                ):
                    patch_lines.append(b"\\ No newline at end of file")

            file_patch = b"\n".join(patch_lines) + b"\n"
            patches[file_path] = file_patch

        return patches

    def __sanitize_filename(self, filename: bytes) -> bytes:
        """
        Sanitize a filename for use in git patch headers.

        - Escapes spaces with backslashes.
        - Removes any trailing tabs.
        - Leaves other characters unchanged.
        """
        return filename.rstrip(b"\t").strip()  # remove trailing tabs

    def __validate_chunks_are_disjoint(self, chunks: list[DiffChunk]) -> bool:
        """Validate that all chunks are pairwise disjoint in old file coordinates.

        This is a critical invariant: chunks must not overlap in the old file
        for them to be safely applied in any order.

        Returns True if all chunks are disjoint, raises RuntimeError otherwise.
        """
        from itertools import groupby

        # Group by file
        sorted_chunks = sorted(chunks, key=lambda c: c.canonical_path())
        for file_path, file_chunks_iter in groupby(
            sorted_chunks, key=lambda c: c.canonical_path()
        ):
            file_chunks = list(file_chunks_iter)

            # Sort by old_start within each file
            file_chunks.sort(key=lambda c: c.old_start or 0)

            # Check each adjacent pair for overlap
            for i in range(len(file_chunks) - 1):
                chunk_a = file_chunks[i]
                chunk_b = file_chunks[i + 1]

                if not chunk_a.is_disjoint_from(chunk_b):
                    raise RuntimeError(
                        f"INVARIANT VIOLATION: Chunks are not disjoint!\n"
                        f"File: {file_path}\n"
                        f"Chunk A: old_start={chunk_a.old_start}, old_len={chunk_a.old_len()}\n"
                        f"Chunk B: old_start={chunk_b.old_start}, old_len={chunk_b.old_len()}\n"
                        f"These chunks overlap in old file coordinates!"
                    )

        return True

    def __calculate_hunk_starts(
        self,
        file_change_type: str,
        old_start: int,
        is_pure_addition: bool,
        cumulative_offset: int,
    ) -> tuple[int, int]:
        """
        Calculate the old_start and new_start for a hunk header based on file change type.

        Args:
            file_change_type: One of "added", "deleted", "modified", "renamed"
            old_start: The old_start from the chunk (in old file coordinates)
            is_pure_addition: Whether this is a pure addition (old_len == 0)
            cumulative_offset: Cumulative net lines added so far

        Returns:
            Tuple of (hunk_old_start, hunk_new_start) for the @@ header
        """
        if file_change_type == "added":
            # File addition: old side is always -0,0
            hunk_old_start = 0
            # new_start adjustment: +1 unless already at line 1
            hunk_new_start = old_start + cumulative_offset + 1
        elif file_change_type == "deleted":
            # File deletion: new side is always +0,0
            hunk_old_start = old_start
            hunk_new_start = 0
        elif is_pure_addition:
            # Pure addition (not a new file): @@ -N,0 +M,len @@
            hunk_old_start = old_start
            # new_start adjustment: +1 unless already at line 1
            hunk_new_start = old_start + cumulative_offset + 1
        else:
            # Deletion, modification, or rename: @@ -N,len +M,len @@
            hunk_old_start = old_start
            hunk_new_start = old_start + cumulative_offset

        return (hunk_old_start, hunk_new_start)

    def __is_contiguous(
        self, last_chunk: "DiffChunk", current_chunk: "DiffChunk"
    ) -> bool:
        """
        Determines if two DiffChunks are contiguous and can be merged.

        We check contiguity based STRICTLY on old file coordinates.
        """
        # Always use old_len to determine the end in the old file.
        # Pure additions have old_len=0, meaning they end where they start.
        last_old_end = (last_chunk.old_start or 0) + last_chunk.old_len()
        current_old_start = current_chunk.old_start or 0

        # 1. Strict Overlap: Always merge (handles standard modifications)
        if last_old_end > current_old_start:
            return True

        # 2. Touching: Merge only if types are compatible (Same Type)
        if last_old_end == current_old_start:
            # Pure Add + Pure Add (at same line) -> Merge
            return (last_chunk.pure_addition() and current_chunk.pure_addition()) or (
                last_chunk.pure_deletion() and current_chunk.pure_deletion()
            )

        # Disjoint
        return False

    def __merge_chunks(self, sorted_chunks: list["DiffChunk"]) -> list["DiffChunk"]:
        """
        Merges a list of sorted, atomic DiffChunks into the smallest possible
        list of larger, valid DiffChunks.

        This acts as the inverse of the `split_into_atomic_chunks` method. It
        first groups adjacent chunks and then merges each group into a single
        new chunk using the `from_parsed_content_slice` factory.
        """
        if not sorted_chunks:
            return []

        # Step 1: Group all contiguous chunks together.
        groups = []
        current_group = [sorted_chunks[0]]
        for i in range(1, len(sorted_chunks)):
            last_chunk = current_group[-1]
            current_chunk = sorted_chunks[i]

            if self.__is_contiguous(last_chunk, current_chunk):
                current_group.append(current_chunk)
            else:
                logger.debug(f"Current merge group: {current_group}")
                groups.append(current_group)
                current_group = [current_chunk]

        logger.debug(f"Current merge group: {current_group}")
        groups.append(current_group)

        # Step 2: Merge each group into a single new DiffChunk.
        final_chunks = []
        for group in groups:
            if len(group) == 1:
                # No merging needed for groups of one.
                final_chunks.append(group[0])
                continue

            # Flatten the content from all chunks in the group.
            # It's crucial that removals come before additions for from_parsed_content_slice.
            merged_parsed_content = []
            removals = []
            additions = []

            # Also combine the newline markers.
            contains_newline_fallback = False
            contains_newline_marker = False

            for chunk in group:
                removals.extend(
                    [c for c in chunk.parsed_content if isinstance(c, Removal)]
                )
                additions.extend(
                    [c for c in chunk.parsed_content if isinstance(c, Addition)]
                )
                contains_newline_fallback |= chunk.contains_newline_fallback
                contains_newline_marker |= chunk.contains_newline_marker

            merged_parsed_content.extend(removals)
            merged_parsed_content.extend(additions)

            # Let the factory method do the hard work of creating the new valid chunk.
            merged_chunk = DiffChunk.from_parsed_content_slice(
                old_file_path=group[0].old_file_path,
                new_file_path=group[0].new_file_path,
                file_mode=group[0].file_mode,
                contains_newline_fallback=contains_newline_fallback,
                contains_newline_marker=contains_newline_marker,
                parsed_slice=merged_parsed_content,
            )
            final_chunks.append(merged_chunk)

        return final_chunks
