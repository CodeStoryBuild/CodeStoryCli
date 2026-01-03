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

from codestory.core.diff.data.immutable_diff_chunk import ImmutableDiffChunk
from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.diff.patch.patch_generator import PatchGenerator
from codestory.core.git.git_const import DEVNULLBYTES


class GitPatchGenerator(PatchGenerator):
    def _generate_diff(
        self,
        immutable_chunks: list[ImmutableDiffChunk],
        diff_chunks: list[StandardDiffChunk],
    ) -> dict[bytes, bytes]:
        """Generates a dictionary of valid, cumulative unified diffs (patches) for each
        file.

        Each diff has no context lines, and is only intended for direct
        patch application.
        """
        patches: dict[bytes, bytes] = {}

        # process immutable chunks first
        for immutable_chunk in immutable_chunks:
            # add newline delimiter to sepatate from other patches in the stream
            patches[immutable_chunk.canonical_path()] = (
                immutable_chunk.file_patch + b"\n"
            )

        # process regular chunks
        sorted_chunks = sorted(diff_chunks, key=lambda c: c.canonical_path())

        for file_path, file_chunks_iter in groupby(
            sorted_chunks, key=lambda c: c.canonical_path()
        ):
            file_chunks: list[StandardDiffChunk] = list(file_chunks_iter)

            if not file_chunks:
                continue

            patch_lines = []
            single_chunk = file_chunks[0]

            # Determine if this set of chunks constitutes a full file deletion or addition
            lines_deleted = sum(c.old_len() for c in file_chunks)
            lines_added = sum(c.new_len() for c in file_chunks)
            lines_in_original = self._get_line_count(file_path, single_chunk.base_hash)

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

            standard_modification = not (file_deletion or file_addition or file_rename)

            # Determine file change type for hunk calculation
            # Order matters: rename is metadata-based and takes precedence
            if file_rename:
                file_change_type = "renamed"
            elif file_addition:
                file_change_type = "added"
            elif file_deletion:
                file_change_type = "deleted"
            else:
                file_change_type = "modified"

            old_file_path = (
                self.sanitize_filename(single_chunk.old_file_path)
                if single_chunk.old_file_path
                else None
            )
            new_file_path = (
                self.sanitize_filename(single_chunk.new_file_path)
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

            if not any(c.has_content for c in file_chunks):
                # If there are no content changes (e.g. pure rename, or empty file add/del),
                # we are done. Do NOT add ---/+++ headers or @@ chunks.
                file_patch = b"\n".join(patch_lines) + b"\n"
                patches[file_path] = file_patch
                continue

            old_file_header = b"a/" + old_file_path if old_file_path else DEVNULLBYTES
            new_file_header = b"b/" + new_file_path if new_file_path else DEVNULLBYTES
            if not file_addition and not file_deletion and not file_rename:
                # For modification, ensure path consistency
                if single_chunk.is_file_deletion:
                    new_file_header = old_file_header
                else:
                    old_file_header = new_file_header

            patch_lines.append(b"--- " + old_file_header)
            patch_lines.append(b"+++ " + new_file_header)

            # Sort chunks by their sort key (old_start, then abs_new_line)
            # This maintains correct ordering even for chunks at the same old_start
            sorted_file_chunks = sorted(file_chunks, key=lambda c: c.get_sort_key())

            # new_start is calculated here and only here!
            # We calculate it based on old_start + cumulative_offset.
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
                    if item.newline_marker:
                        patch_lines.append(b"\\ No newline at end of file")

                # Update cumulative offset for next chunk
                cumulative_offset += new_len - old_len

            # Handle the no-newline marker fallback for the last chunk in the file
            # (added if a hunk has only this marker and thus no other changes to attach itself to)
            if sorted_file_chunks and sorted_file_chunks[-1].contains_newline_fallback:
                patch_lines.append(b"\\ No newline at end of file")

            file_patch = b"\n".join(patch_lines) + b"\n"
            patches[file_path] = file_patch

        return patches

    def __calculate_hunk_starts(
        self,
        file_change_type: str,
        old_start: int,
        is_pure_addition: bool,
        cumulative_offset: int,
    ) -> tuple[int, int]:
        """Calculate the old_start and new_start for a hunk header based on file change
        type.

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
