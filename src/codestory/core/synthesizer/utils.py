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

from codestory.core.data.chunk import Chunk
from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.synthesizer.diff_generator import DiffGenerator


def get_patches_chunk(chunks: list[Chunk]) -> dict[int, str]:
    diff_generator = DiffGenerator(chunks)

    patch_map = {}
    for i, chunk in enumerate(chunks):
        patches = diff_generator.generate_unified_diff(chunk.get_chunks())

        if patches:
            # sort by file name
            ordered_items = sorted(patches.items(), key=lambda kv: kv[0])
            combined_patch = b"".join(patch for _, patch in ordered_items)
        else:
            combined_patch = ""

        patch_map[i] = combined_patch.decode("utf-8", errors="replace")

    return patch_map


def get_patches(groups: list[CommitGroup]) -> dict[int, str]:
    diff_generator = DiffGenerator(groups)

    patch_map = {}
    for i, group in enumerate(groups):
        group_chunks = []
        for chunk in group.chunks:
            if isinstance(chunk, ImmutableChunk):
                group_chunks.append(chunk)
            else:
                group_chunks.extend(chunk.get_chunks())

        patches = diff_generator.generate_unified_diff(group_chunks)

        if patches:
            # sort by file name
            ordered_items = sorted(patches.items(), key=lambda kv: kv[0])
            combined_patch = b"".join(patch for _, patch in ordered_items)
        else:
            combined_patch = b""

        patch_map[i] = combined_patch.decode("utf-8", errors="replace")

    return patch_map
