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

from abc import abstractmethod
from itertools import groupby

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.immutable_diff_chunk import ImmutableDiffChunk
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.diff.data.utils import flatten_containers, partition_chunks_by_type
from codestory.core.diff.utils.chunk_merger import merge_diff_chunks_by_file
from codestory.core.semantic_analysis.annotation.file_manager import FileManager


class PatchGenerator:
    def __init__(self, containers: list[AtomicContainer], file_manager: FileManager):
        self.file_manager = file_manager
        # TODO: this can move somewhere else
        standard_diff_chunks = flatten_containers(containers, (StandardDiffChunk,))
        self.__validate_chunks_are_disjoint(standard_diff_chunks)

    def __validate_chunks_are_disjoint(self, chunks: list[StandardDiffChunk]) -> bool:
        """Validate that all chunks are pairwise disjoint in old file coordinates.

        This is a critical invariant: chunks must not overlap in the old file
        for them to be safely applied in any order.

        Returns True if all chunks are disjoint, raises RuntimeError otherwise.
        """

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

    def _get_line_count(self, file_path: bytes, base_hash: str) -> int | None:
        """Get the total number of lines in a file in the base commit."""
        return self.file_manager.get_line_count(file_path, base_hash)

    @abstractmethod
    def generate_diff(
        self,
        containers: list[AtomicContainer],
    ) -> dict[bytes, bytes]:
        atomic_chunks = flatten_containers(containers)
        immutable_diff_chunks, standard_diff_chunks = partition_chunks_by_type(
            atomic_chunks, (ImmutableDiffChunk,)
        )
        merged_standard_chunks = merge_diff_chunks_by_file(standard_diff_chunks)

        return self._generate_diff(immutable_diff_chunks, merged_standard_chunks)

    @abstractmethod
    def _generate_diff(
        self,
        immutable_chunks: list[ImmutableDiffChunk],
        standard_diff_chunks: list[StandardDiffChunk],
    ) -> dict[bytes, bytes]:
        pass

    @staticmethod
    def sanitize_filename(filename: bytes) -> bytes:
        """Sanitize a filename for use in git patch headers.

        - Escapes spaces with backslashes.
        - Removes any trailing tabs.
        - Leaves other characters unchanged.
        """
        return filename.rstrip(b"\t").strip()  # remove trailing tabs

    def get_patch(
        self, container: AtomicContainer, is_bytes: bool = False
    ) -> str | bytes:
        patches = self.generate_diff([container])

        if patches:
            # sort by file name
            ordered_items = sorted(patches.items(), key=lambda kv: kv[0])
            combined_patch = b"".join(patch for _, patch in ordered_items)
        else:
            combined_patch = b""

        if is_bytes:
            return combined_patch
        else:
            return combined_patch.decode("utf-8", errors="replace")

    def get_patches(
        self, chunks: list[AtomicContainer], is_bytes: bool = False
    ) -> dict[int, str | bytes]:
        patch_map = {}
        for i, chunk in enumerate(chunks):
            patch_map[i] = self.get_patch(chunk, is_bytes=is_bytes)

        return patch_map
