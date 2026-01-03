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
from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk


def __is_contiguous(
    last_chunk: StandardDiffChunk, current_chunk: StandardDiffChunk
) -> bool:
    """Determines if two StandardDiffChunks are contiguous and can be merged.

    We check contiguity based on old file coordinates.
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
        # Check if they really are at same line (old_start)
        lasts_same_start = (last_chunk.old_start or 0) == (current_chunk.old_start or 0)

        if (
            last_chunk.pure_addition()
            and current_chunk.pure_addition()
            and lasts_same_start
        ):
            return True

        # Pure deletion + Pure deletion -> Merge
        if last_chunk.pure_deletion() and current_chunk.pure_deletion():
            return True

    # Disjoint
    return False


def __merge_diff_chunks(
    sorted_chunks: list[StandardDiffChunk],
) -> list[StandardDiffChunk]:
    """Merges a list of sorted, atomic StandardDiffChunks into the smallest possible
    list of larger, valid StandardDiffChunks.

    This method groups adjacent chunks and then merges each group into a single
    new chunk using the `from_parsed_content_slice` factory.

    Args:
        sorted_chunks: List of StandardDiffChunks sorted by their sort key (old_start, then abs_new_line).
                      Should all be from the same file.

    Returns:
        List of merged StandardDiffChunks with redundant splits removed.
    """
    if not sorted_chunks:
        return []

    if len(sorted_chunks) <= 1:
        return sorted_chunks

    # Group all contiguous chunks together.
    groups = []
    current_group = [sorted_chunks[0]]
    for i in range(1, len(sorted_chunks)):
        last_chunk = current_group[-1]
        current_chunk = sorted_chunks[i]

        if __is_contiguous(last_chunk, current_chunk):
            current_group.append(current_chunk)
        else:
            groups.append(current_group)
            current_group = [current_chunk]

    groups.append(current_group)

    # Merge each group into a single new StandardDiffChunk.
    final_chunks = []
    for group in groups:
        if len(group) == 1:
            # No merging needed for groups of one.
            final_chunks.append(group[0])
            continue

        # Flatten the content from all chunks in the group.
        merged_parsed_content = []
        removals = []
        additions = []

        # Also combine the newline markers.
        contains_newline_fallback = False

        for chunk in group:
            removals.extend([c for c in chunk.parsed_content if isinstance(c, Removal)])
            additions.extend(
                [c for c in chunk.parsed_content if isinstance(c, Addition)]
            )
            contains_newline_fallback |= chunk.contains_newline_fallback

        merged_parsed_content.extend(removals)
        merged_parsed_content.extend(additions)

        # Let the factory method do the hard work of creating the new valid chunk.
        merged_chunk = StandardDiffChunk.from_parsed_content_slice(
            base_hash=group[0].base_hash,
            new_hash=group[0].new_hash,
            old_file_path=group[0].old_file_path,
            new_file_path=group[0].new_file_path,
            file_mode=group[0].file_mode,
            contains_newline_fallback=contains_newline_fallback,
            parsed_slice=merged_parsed_content,
        )
        final_chunks.append(merged_chunk)

    return final_chunks


def merge_diff_chunks_by_file(
    diff_chunks: list[StandardDiffChunk],
) -> list[StandardDiffChunk]:
    """Groups StandardDiffChunks by file path, then merges chunks within each file.

    This is the core method that takes a list of StandardDiffChunks (potentially from multiple files),
    groups them by their canonical path, sorts them within each file group, and merges
    contiguous chunks.

    Args:
        diff_chunks: List of StandardDiffChunks potentially from multiple files.

    Returns:
        List of merged StandardDiffChunks with redundant splits removed.
    """
    if not diff_chunks:
        return []

    if len(diff_chunks) <= 1:
        return diff_chunks

    merged_chunks = []

    # Group by file path
    sorted_by_file = sorted(diff_chunks, key=lambda c: c.canonical_path())

    for _, file_chunks_iter in groupby(
        sorted_by_file, key=lambda c: c.canonical_path()
    ):
        file_chunks = list(file_chunks_iter)

        # Sort chunks within the file by their sort key
        sorted_file_chunks = sorted(file_chunks, key=lambda c: c.get_sort_key())

        # Merge contiguous chunks within this file
        merged_file_chunks = __merge_diff_chunks(sorted_file_chunks)
        merged_chunks.extend(merged_file_chunks)

    return merged_chunks


def merge_container(container: AtomicContainer) -> AtomicContainer:
    """Convenience method to merge chunks inside a container, if possible.

    Done by merging contiguous StandardDiffChunks within the container.
    """
    from codestory.core.diff.data.composite_container import CompositeContainer
    from codestory.core.diff.data.utils import partition_chunks_by_type

    atomic_chunks = container.get_atomic_chunks()

    if len(atomic_chunks) <= 1:
        return container

    standard_diff_chunks, other_chunks = partition_chunks_by_type(
        atomic_chunks, StandardDiffChunk
    )

    merged_standard_chunks = merge_diff_chunks_by_file(standard_diff_chunks)

    return CompositeContainer(containers=merged_standard_chunks + other_chunks)


def merge_containers(chunks: list[AtomicContainer]) -> list[AtomicContainer]:
    """Convenience method to merge chunks inside multiple containers."""
    return [merge_container(chunk) for chunk in chunks]
