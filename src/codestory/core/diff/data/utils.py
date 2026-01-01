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

from codestory.core.diff.data.atomic_chunk import AtomicDiffChunk
from codestory.core.diff.data.atomic_container import AtomicContainer


def flatten_containers(
    containers: list[AtomicContainer],
    type_filter: type | tuple[type, ...] | None = None,
) -> list[AtomicDiffChunk]:
    """Flatten an AtomicContainer into its atomic chunks."""
    return [
        chunk
        for container in containers
        for chunk in flatten_container(container, type_filter)
    ]


def flatten_container(
    container: AtomicContainer, type_filter: type | tuple[type, ...] | None = None
) -> list[AtomicDiffChunk]:
    """Flatten an AtomicContainer into its atomic chunks."""
    return [
        chunk
        for chunk in container.get_atomic_chunks()
        if type_filter is None or isinstance(chunk, type_filter)
    ]


def partition_chunks_by_type(
    chunks: list[AtomicDiffChunk], type_filter: type | tuple[type, ...] | None = None
) -> tuple[list[AtomicDiffChunk], list[AtomicDiffChunk]]:
    """Partition a list of AtomicDiffChunks into two lists based on a type filter."""
    matching = [
        chunk
        for chunk in chunks
        if type_filter is None or isinstance(chunk, type_filter)
    ]
    non_matching = [
        chunk
        for chunk in chunks
        if type_filter is not None and not isinstance(chunk, type_filter)
    ]
    return matching, non_matching
